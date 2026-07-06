"""
translate.py  —  제목·초록 한글화 (Azure Translator, 무료 등급)

작동 방식 (매일 수집 직후 실행):
  1) DB에서 아직 번역 안 된 논문(제목 또는 초록)을 최신순으로 가져옴
  2) Azure Translator(무료 F0: 월 200만 자)로 영어 → 한국어 번역
  3) title_ko / abstract_ko 에 저장 (영어 원문 title_en / abstract_en 은 그대로 보존)

비용 안전장치:
  - 실행 1회당 번역 글자수 상한 = TRANSLATE_CHAR_BUDGET (기본 60,000자)
    → 매일 6만 자 × 30일 ≈ 180만 자로 무료 한도(200만 자) 안에서 운영
  - 새 논문부터 먼저 번역하고, 남는 예산으로 과거 미번역분을 조금씩 채움
"""

import os
import time

import requests

SUPABASE_URL = os.environ.get("SUPABASE_URL", "").rstrip("/")
SERVICE_KEY = os.environ.get("SUPABASE_SERVICE_KEY", "")

AZURE_KEY = os.environ.get("AZURE_TRANSLATOR_KEY", "")
AZURE_REGION = os.environ.get("AZURE_TRANSLATOR_REGION", "koreacentral")
AZURE_URL = "https://api.cognitive.microsofttranslator.com/translate?api-version=3.0&from=en&to=ko"

# 실행 1회당 번역할 최대 글자수 (무료 한도 보호)
CHAR_BUDGET = int(os.environ.get("TRANSLATE_CHAR_BUDGET", "60000"))
# Azure 요청 1번에 담을 최대 글자수 / 항목수 (공식 상한: 5만 자, 1000항목)
REQ_CHAR_LIMIT = 40000
REQ_ITEM_LIMIT = 100


def _db_headers():
    return {
        "apikey": SERVICE_KEY,
        "Authorization": f"Bearer {SERVICE_KEY}",
        "Content-Type": "application/json",
    }


def _azure_headers():
    return {
        "Ocp-Apim-Subscription-Key": AZURE_KEY,
        "Ocp-Apim-Subscription-Region": AZURE_REGION,
        "Content-Type": "application/json",
    }


# ── 1) 번역 대상 조회 ────────────────────────────────────────────
def fetch_untranslated(limit=500):
    """제목 또는 초록이 아직 한글화되지 않은 논문을 최신순으로 가져온다."""
    url = (
        f"{SUPABASE_URL}/rest/v1/papers"
        f"?or=(title_ko.is.null,and(abstract_ko.is.null,abstract_en.not.is.null))"
        f"&select=id,title_en,abstract_en,title_ko,abstract_ko"
        f"&order=first_seen_at.desc&limit={limit}"
    )
    try:
        resp = requests.get(url, headers=_db_headers(), timeout=30)
        resp.raise_for_status()
        return resp.json()
    except requests.RequestException as e:
        print(f"[번역] 대상 조회 실패: {e}")
        return []


# ── 2) Azure 번역 호출 ───────────────────────────────────────────
def translate_texts(texts):
    """영어 문자열 목록을 한국어 목록으로. 실패 시 None."""
    if not texts:
        return []
    body = [{"Text": t} for t in texts]
    for attempt in range(3):
        try:
            resp = requests.post(AZURE_URL, headers=_azure_headers(), json=body, timeout=60)
            if resp.status_code == 429:  # 속도 제한 → 잠시 대기 후 재시도
                time.sleep(10 * (attempt + 1))
                continue
            resp.raise_for_status()
            data = resp.json()
            return [item["translations"][0]["text"] for item in data]
        except (requests.RequestException, KeyError, IndexError) as e:
            print(f"[번역] Azure 호출 실패({attempt + 1}/3): {e}")
            time.sleep(5)
    return None


# ── 3) DB 반영 ───────────────────────────────────────────────────
def save_translation(paper_id, title_ko=None, abstract_ko=None):
    patch = {}
    if title_ko:
        patch["title_ko"] = title_ko
    if abstract_ko:
        patch["abstract_ko"] = abstract_ko
        patch["abstract_ko_generated_at"] = "now()"
    if not patch:
        return False
    url = f"{SUPABASE_URL}/rest/v1/papers?id=eq.{paper_id}"
    try:
        resp = requests.patch(url, headers=_db_headers(), json=patch, timeout=15)
        resp.raise_for_status()
        return True
    except requests.RequestException as e:
        print(f"[번역] 저장 실패({paper_id}): {e}")
        return False


# ── 4) 실행 ──────────────────────────────────────────────────────
def run():
    if not AZURE_KEY:
        print("[번역] AZURE_TRANSLATOR_KEY 미설정 — 번역 건너뜀")
        return
    if not SUPABASE_URL or not SERVICE_KEY:
        print("[번역] Supabase 환경변수 미설정 — 번역 건너뜀")
        return

    papers = fetch_untranslated()
    if not papers:
        print("[번역] 번역할 논문 없음")
        return

    # 예산 안에서 작업 목록 구성: (paper, 'title'|'abstract', 원문)
    jobs, used = [], 0
    for p in papers:
        if not p.get("title_ko") and p.get("title_en"):
            n = len(p["title_en"])
            if used + n > CHAR_BUDGET:
                break
            jobs.append((p["id"], "title", p["title_en"]))
            used += n
        if not p.get("abstract_ko") and p.get("abstract_en"):
            n = len(p["abstract_en"])
            if used + n > CHAR_BUDGET:
                continue  # 이 초록은 크면 건너뛰고 다음 논문의 짧은 것 시도
            jobs.append((p["id"], "abstract", p["abstract_en"]))
            used += n

    if not jobs:
        print("[번역] 예산 내 작업 없음")
        return
    print(f"[번역] 대상 {len(jobs)}건 (약 {used:,}자, 예산 {CHAR_BUDGET:,}자)")

    # 요청 단위로 묶어서 번역
    done, failed = 0, 0
    batch, batch_chars = [], 0
    results = {}  # (paper_id) -> {"title": ..., "abstract": ...}

    def flush():
        nonlocal done, failed, batch, batch_chars
        if not batch:
            return
        translated = translate_texts([j[2] for j in batch])
        if translated is None:
            failed += len(batch)
        else:
            for (pid, kind, _), ko in zip(batch, translated):
                results.setdefault(pid, {})[kind] = ko
            done += len(batch)
        batch, batch_chars = [], 0
        time.sleep(1)  # 무료 등급 속도 제한 완화

    for job in jobs:
        if len(batch) >= REQ_ITEM_LIMIT or batch_chars + len(job[2]) > REQ_CHAR_LIMIT:
            flush()
        batch.append(job)
        batch_chars += len(job[2])
    flush()

    # DB 저장
    saved = 0
    for pid, vals in results.items():
        if save_translation(pid, vals.get("title"), vals.get("abstract")):
            saved += 1

    print(f"[번역] 번역 {done}건 / 실패 {failed}건 / 논문 {saved}편 저장")


if __name__ == "__main__":
    run()
