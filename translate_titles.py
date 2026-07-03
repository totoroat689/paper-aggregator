"""
translate_titles.py  —  제목 한글화 (배치 방식, 반값)

작동 방식 (매일 수집 후 실행):
  1) 이전에 제출한 배치가 있으면 -> 결과 회수해서 DB에 저장
  2) 아직 번역 안 된 제목들 -> 새 배치로 제출 (24시간 내 처리, 보통 1시간 내)

즉 제목은 최대 하루 늦게 한글이 달립니다. 비용은 실시간의 절반.
배치 ID는 DB의 translation_batches 표에 기록해 이어서 처리합니다.
"""

import os
import json

import requests

ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY", "")
SUPABASE_URL = os.environ.get("SUPABASE_URL", "").rstrip("/")
SERVICE_KEY = os.environ.get("SUPABASE_SERVICE_KEY", "")

API_BASE = "https://api.anthropic.com/v1"
MODEL = "claude-haiku-4-5-20251001"
MAX_PER_BATCH = 2000   # 한 번에 최대 몇 건 번역할지 (비용 안전장치)


def _anthropic_headers():
    return {
        "x-api-key": ANTHROPIC_API_KEY,
        "anthropic-version": "2023-06-01",
        "content-type": "application/json",
    }


def _db_headers():
    return {
        "apikey": SERVICE_KEY,
        "Authorization": f"Bearer {SERVICE_KEY}",
        "Content-Type": "application/json",
    }


# ── 1) 이전 배치 회수 ────────────────────────────────────────────
def collect_finished_batches():
    """제출해둔 배치 중 끝난 것의 결과를 DB에 저장."""
    url = f"{SUPABASE_URL}/rest/v1/translation_batches?status=eq.submitted&select=*"
    try:
        rows = requests.get(url, headers=_db_headers(), timeout=15).json()
    except requests.RequestException as e:
        print(f"[제목번역] 배치 목록 조회 실패: {e}")
        return

    if not rows:
        print("[제목번역] 회수할 배치 없음")
        return

    for row in rows:
        batch_id = row["batch_id"]
        try:
            resp = requests.get(f"{API_BASE}/messages/batches/{batch_id}",
                                headers=_anthropic_headers(), timeout=30)
            resp.raise_for_status()
            info = resp.json()
        except requests.RequestException as e:
            print(f"[제목번역] 배치 {batch_id} 상태 조회 실패: {e}")
            continue

        status = info.get("processing_status")
        if status != "ended":
            print(f"[제목번역] 배치 {batch_id}: 아직 처리 중({status})")
            continue

        results_url = info.get("results_url")
        if not results_url:
            _mark_batch(batch_id, "failed")
            continue

        saved = _save_results(results_url)
        _mark_batch(batch_id, "done")
        print(f"[제목번역] 배치 {batch_id} 회수 완료 — {saved}건 저장")


def _save_results(results_url):
    """배치 결과(JSONL)를 내려받아 title_ko를 DB에 저장."""
    try:
        resp = requests.get(results_url, headers=_anthropic_headers(), timeout=60)
        resp.raise_for_status()
    except requests.RequestException as e:
        print(f"[제목번역] 결과 다운로드 실패: {e}")
        return 0

    saved = 0
    for line in resp.text.strip().split("\n"):
        if not line:
            continue
        try:
            item = json.loads(line)
            paper_id = item.get("custom_id")
            result = item.get("result", {})
            if result.get("type") != "succeeded":
                continue
            content = result.get("message", {}).get("content", [])
            text = "".join(b.get("text", "") for b in content).strip()
            if not paper_id or not text:
                continue
            requests.patch(
                f"{SUPABASE_URL}/rest/v1/papers?id=eq.{paper_id}",
                headers=_db_headers(),
                json={"title_ko": text},
                timeout=15,
            )
            saved += 1
        except (json.JSONDecodeError, requests.RequestException):
            continue
    return saved


def _mark_batch(batch_id, status):
    try:
        requests.patch(
            f"{SUPABASE_URL}/rest/v1/translation_batches?batch_id=eq.{batch_id}",
            headers=_db_headers(),
            json={"status": status},
            timeout=15,
        )
    except requests.RequestException:
        pass


# ── 2) 새 배치 제출 ──────────────────────────────────────────────
def submit_new_batch():
    """번역 안 된 제목들을 모아 배치 제출."""
    url = (f"{SUPABASE_URL}/rest/v1/papers"
           f"?select=id,title_en&title_ko=is.null&title_en=not.is.null"
           f"&order=publication_date.desc.nullslast&limit={MAX_PER_BATCH}")
    try:
        rows = requests.get(url, headers=_db_headers(), timeout=30).json()
    except requests.RequestException as e:
        print(f"[제목번역] 대상 조회 실패: {e}")
        return

    if not rows:
        print("[제목번역] 번역할 제목 없음")
        return

    batch_requests = []
    for r in rows:
        batch_requests.append({
            "custom_id": r["id"],
            "params": {
                "model": MODEL,
                "max_tokens": 200,
                "messages": [{
                    "role": "user",
                    "content": ("다음 학술 논문 제목을 자연스러운 한국어로 번역해줘. "
                                "전문용어는 통용되는 한국어 학술용어로. 번역문만 출력:\n\n"
                                + r["title_en"]),
                }],
            },
        })

    try:
        resp = requests.post(
            f"{API_BASE}/messages/batches",
            headers=_anthropic_headers(),
            json={"requests": batch_requests},
            timeout=120,
        )
        resp.raise_for_status()
        batch_id = resp.json().get("id")
    except requests.RequestException as e:
        detail = getattr(e.response, "text", "")[:200] if getattr(e, "response", None) else str(e)
        print(f"[제목번역] 배치 제출 실패: {detail}")
        return

    # 배치 ID 기록
    try:
        requests.post(
            f"{SUPABASE_URL}/rest/v1/translation_batches",
            headers=_db_headers(),
            json={"batch_id": batch_id, "status": "submitted", "item_count": len(batch_requests)},
            timeout=15,
        )
    except requests.RequestException:
        pass

    print(f"[제목번역] 새 배치 제출 — {len(batch_requests)}건 (배치 ID: {batch_id})")


def run():
    if not ANTHROPIC_API_KEY:
        print("[제목번역] ANTHROPIC_API_KEY 없음 — 건너뜀")
        return
    print("\n--- 제목 한글화 (배치) ---")
    collect_finished_batches()
    submit_new_batch()


if __name__ == "__main__":
    run()
