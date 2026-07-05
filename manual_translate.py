"""
수동 번역 파이프라인 (Claude 채팅 번역용)
──────────────────────────────────────────
Claude는 Supabase에 직접 접속할 수 없지만 GitHub에는 push할 수 있고,
GitHub Actions는 Supabase에 접속할 수 있다. 그래서 저장소를 '우체통'으로 쓴다.

동작 (auto 모드가 알아서 판별):
1) translation/done.json 이 있으면   → [반영] 번역 결과를 DB에 저장하고 파일 정리
2) translation/request.json 이 있으면 → [내보내기] 한글화 안 된 제목/초록을 pending.json으로 추출

흐름:
  Claude가 request.json push → Actions가 pending.json 커밋
  → Claude가 pull 받아 채팅에서 번역 → done.json push
  → Actions가 DB 반영 + 파일 정리
"""
import json
import os
import sys

import requests

SUPABASE_URL = os.environ.get("SUPABASE_URL", "").rstrip("/")
SERVICE_KEY = os.environ.get("SUPABASE_SERVICE_KEY", "")

DIR = "translation"
REQUEST = os.path.join(DIR, "request.json")
PENDING = os.path.join(DIR, "pending.json")
DONE = os.path.join(DIR, "done.json")


def _headers():
    return {
        "apikey": SERVICE_KEY,
        "Authorization": f"Bearer {SERVICE_KEY}",
        "Content-Type": "application/json",
        "Prefer": "return=minimal",
    }


def export_pending():
    """한글화 안 된 제목/초록을 뽑아 pending.json으로 저장"""
    try:
        with open(REQUEST, encoding="utf-8") as f:
            req = json.load(f)
    except (OSError, ValueError):
        req = {}
    title_limit = int(req.get("title_limit", 150))
    abstract_limit = int(req.get("abstract_limit", 25))

    out = {"titles": [], "abstracts": []}

    if title_limit > 0:
        url = (f"{SUPABASE_URL}/rest/v1/papers"
               f"?select=id,title_en"
               f"&title_ko=is.null&title_en=not.is.null&is_retracted=eq.false"
               f"&order=publication_date.desc.nullslast&limit={title_limit}")
        resp = requests.get(url, headers=_headers(), timeout=60)
        resp.raise_for_status()
        out["titles"] = resp.json()

    if abstract_limit > 0:
        url = (f"{SUPABASE_URL}/rest/v1/papers"
               f"?select=id,abstract_en"
               f"&abstract_ko=is.null&abstract_en=not.is.null&is_retracted=eq.false"
               f"&order=publication_date.desc.nullslast&limit={abstract_limit}")
        resp = requests.get(url, headers=_headers(), timeout=60)
        resp.raise_for_status()
        out["abstracts"] = resp.json()

    os.makedirs(DIR, exist_ok=True)
    with open(PENDING, "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=1)
    # 요청 파일은 소진 처리 (다음 실행에서 재추출 방지)
    if os.path.exists(REQUEST):
        os.remove(REQUEST)
    print(f"[내보내기] 제목 {len(out['titles'])}건 + 초록 {len(out['abstracts'])}건 -> {PENDING}")


def import_done():
    """done.json의 번역 결과를 DB에 반영하고 파일 정리"""
    with open(DONE, encoding="utf-8") as f:
        data = json.load(f)
    items = data.get("items", [])
    ok, fail = 0, 0
    for it in items:
        pid = it.get("id")
        payload = {}
        if it.get("title_ko"):
            payload["title_ko"] = it["title_ko"]
        if it.get("abstract_ko"):
            payload["abstract_ko"] = it["abstract_ko"]
            payload["abstract_ko_generated_at"] = "now()"
        if not pid or not payload:
            continue
        try:
            resp = requests.patch(
                f"{SUPABASE_URL}/rest/v1/papers?id=eq.{pid}",
                headers=_headers(), json=payload, timeout=30)
            if resp.status_code < 300:
                ok += 1
            else:
                fail += 1
                print(f"  실패 {pid}: {resp.status_code} {resp.text[:120]}")
        except requests.RequestException as e:
            fail += 1
            print(f"  실패 {pid}: {e}")
    # 처리 끝난 파일 정리
    for p in (DONE, PENDING):
        if os.path.exists(p):
            os.remove(p)
    print(f"[반영] 성공 {ok}건 / 실패 {fail}건 — 파일 정리 완료")


def main():
    if not SUPABASE_URL or not SERVICE_KEY:
        print("SUPABASE_URL / SUPABASE_SERVICE_KEY 환경변수 필요")
        sys.exit(1)
    if os.path.exists(DONE):
        import_done()
    elif os.path.exists(REQUEST):
        export_pending()
    else:
        print("처리할 파일 없음 (translation/request.json 또는 done.json)")


if __name__ == "__main__":
    main()
