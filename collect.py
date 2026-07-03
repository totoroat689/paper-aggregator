"""
collect.py  —  이 프로젝트의 메인 파일 (이 파일 하나가 전부 실행함)

흐름:
  1) 3곳(OpenAlex, Europe PMC, Semantic Scholar)에서 최근 논문 가져오기
  2) 메모리에서 중복 합치기
  3) 한꺼번에 저장 (한 건이 문제여도 나머지는 살림)

GitHub Actions가 매일 이 파일을 실행합니다.
밑받침 로직(형식/분류/합치기)은 helpers.py에 있습니다.
"""

import os
import re
import time
from datetime import date, timedelta

import requests

from helpers import (
    blank_paper, deep_get, normalize_doi, classify_study_type,
    dedupe_and_merge, to_db_row, passes_retention, strip_html,
)

DAYS_BACK = int(os.environ.get("COLLECT_DAYS_BACK", "3"))

SUPABASE_URL = os.environ.get("SUPABASE_URL", "").rstrip("/")
SERVICE_KEY = os.environ.get("SUPABASE_SERVICE_KEY", "")
OPENALEX_API_KEY = os.environ.get("OPENALEX_API_KEY", "")
SEMANTICSCHOLAR_API_KEY = os.environ.get("SEMANTICSCHOLAR_API_KEY", "")

BATCH_SIZE = 200


# ══════════════════════════════════════════════════════════════════
#  1) 출처별 수집  — 각 함수는 '공통 형식(paper dict)' 목록을 돌려줌
# ══════════════════════════════════════════════════════════════════

def fetch_openalex(days_back):
    """OpenAlex (주력). 26개 분야를 돌며 최근 논문 수집. 키 필요."""
    base = "https://api.openalex.org/works"
    fields_url = "https://api.openalex.org/fields"
    start = (date.today() - timedelta(days=days_back)).isoformat()

    try:
        r = requests.get(fields_url, params={"api_key": OPENALEX_API_KEY, "per_page": 50}, timeout=30)
        r.raise_for_status()
        fields = [{"id": f["id"], "name": f["display_name"]} for f in r.json().get("results", [])]
    except (requests.RequestException, ValueError, KeyError) as e:
        print(f"[openalex] 분야 목록 실패, 건너뜀: {e}")
        return []

    papers = []
    for field in fields:
        params = {
            "api_key": OPENALEX_API_KEY,
            "filter": (f"primary_topic.field.id:{field['id']},"
                       f"from_publication_date:{start},"
                       f"type:article|review"),
            "per_page": 100,
            "sort": "publication_date:desc",
        }
        try:
            resp = requests.get(base, params=params, timeout=30)
            resp.raise_for_status()
            results = resp.json().get("results", [])
        except (requests.RequestException, ValueError) as e:
            print(f"[openalex] {field['name']} 오류: {e}")
            continue
        papers.extend(_openalex_to_paper(raw) for raw in results)
        print(f"[openalex] {field['name']}: {len(results)}건")
        time.sleep(0.2)

    print(f"[openalex] 총 {len(papers)}건")
    return papers


def _openalex_to_paper(raw):
    p = blank_paper()
    p["doi"] = normalize_doi(deep_get(raw, "doi"))
    p["title_en"] = strip_html(deep_get(raw, "title") or deep_get(raw, "display_name"))
    p["abstract_en"] = strip_html(_rebuild_abstract(deep_get(raw, "abstract_inverted_index")))

    authorships = deep_get(raw, "authorships", default=[])
    p["authors"] = [{"name": deep_get(a, "author", "display_name")}
                    for a in authorships if isinstance(a, dict)]
    countries = []
    for a in authorships:
        if isinstance(a, dict):
            countries.extend(a.get("countries") or [])
    p["countries"] = sorted(set(countries))

    p["publication_year"] = deep_get(raw, "publication_year")
    p["publication_date"] = deep_get(raw, "publication_date")
    p["source_indexed_date"] = deep_get(raw, "created_date")
    p["citation_count"] = deep_get(raw, "cited_by_count", default=0)
    p["is_retracted"] = bool(deep_get(raw, "is_retracted", default=False))
    p["is_open_access"] = bool(deep_get(raw, "open_access", "is_oa", default=False))
    p["primary_category"] = deep_get(raw, "primary_topic", "field", "display_name")
    p["journal_name"] = deep_get(raw, "primary_location", "source", "display_name")
    p["fulltext_url"] = deep_get(raw, "primary_location", "landing_page_url")
    # 라이선스(cc-by 등): 오픈액세스 위치의 값을 우선, 없으면 기본 위치의 값
    p["license"] = (deep_get(raw, "best_oa_location", "license")
                    or deep_get(raw, "primary_location", "license"))
    p["study_type"] = classify_study_type([deep_get(raw, "type")], p["abstract_en"])
    p["sources"] = ["openalex"]
    p["source_ids"] = {"openalex": deep_get(raw, "id")}
    return p


def _rebuild_abstract(inverted_index):
    """OpenAlex는 초록을 '단어:위치' 목록으로 줌 -> 원래 문장으로 조립."""
    if not inverted_index or not isinstance(inverted_index, dict):
        return None
    pos_word = {}
    for word, positions in inverted_index.items():
        for pos in positions:
            pos_word[pos] = word
    if not pos_word:
        return None
    return " ".join(pos_word.get(i, "") for i in range(max(pos_word) + 1)).strip() or None


def fetch_europepmc(days_back):
    """Europe PMC. 키 불필요. 최근 논문을 날짜순으로 수집."""
    base = "https://www.ebi.ac.uk/europepmc/webservices/rest/search"
    start = (date.today() - timedelta(days=days_back)).isoformat()
    end = date.today().isoformat()
    query = f"(FIRST_PDATE:[{start} TO {end}]) sort_date:y"

    papers = []
    cursor = "*"
    for _ in range(5):
        params = {"query": query, "format": "json", "resultType": "core",
                  "pageSize": 100, "cursorMark": cursor}
        try:
            resp = requests.get(base, params=params, timeout=30)
            resp.raise_for_status()
            data = resp.json()
        except (requests.RequestException, ValueError) as e:
            print(f"[europepmc] 오류: {e}")
            break

        results = deep_get(data, "resultList", "result", default=[])
        papers.extend(_europepmc_to_paper(raw) for raw in results)

        nxt = data.get("nextCursorMark")
        if not nxt or nxt == cursor or not results:
            break
        cursor = nxt
        time.sleep(0.4)

    print(f"[europepmc] 총 {len(papers)}건")
    return papers


def _europepmc_to_paper(raw):
    p = blank_paper()
    p["doi"] = normalize_doi(deep_get(raw, "doi"))
    p["pmid"] = deep_get(raw, "pmid")
    p["title_en"] = strip_html((deep_get(raw, "title") or "").rstrip("."))
    p["abstract_en"] = strip_html(deep_get(raw, "abstractText"))
    p["authors"] = [{"name": a.get("fullName")}
                    for a in deep_get(raw, "authorList", "author", default=[])
                    if isinstance(a, dict)]
    p["publication_year"] = deep_get(raw, "pubYear")
    p["publication_date"] = deep_get(raw, "firstPublicationDate")
    p["source_indexed_date"] = deep_get(raw, "firstIndexDate")
    p["citation_count"] = deep_get(raw, "citedByCount", default=0)
    p["is_open_access"] = deep_get(raw, "isOpenAccess") == "Y"
    p["is_retracted"] = _has_retraction(raw)
    p["journal_name"] = deep_get(raw, "journalInfo", "journal", "title")
    p["fulltext_url"] = _epmc_url(raw)
    hints = deep_get(raw, "pubTypeList", "pubType", default=[])
    p["study_type"] = classify_study_type(hints, p["abstract_en"])
    p["sources"] = ["europepmc"]
    p["source_ids"] = {"europepmc": deep_get(raw, "id")}
    return p


def _has_retraction(raw):
    for c in deep_get(raw, "commentCorrectionList", "commentCorrection", default=[]):
        if isinstance(c, dict) and "retraction" in (c.get("type") or "").lower():
            return True
    return False


def _epmc_url(raw):
    for u in deep_get(raw, "fullTextUrlList", "fullTextUrl", default=[]):
        if isinstance(u, dict) and u.get("availabilityCode") in ("F", "OA"):
            return u.get("url")
    doi = deep_get(raw, "doi")
    return f"https://doi.org/{doi}" if doi else None


def fetch_semanticscholar(days_back):
    """Semantic Scholar (보조). 느려서 사회·심리 계열만, 90초 시간상한."""
    base = "https://api.semanticscholar.org/graph/v1/paper/search/bulk"
    fields = ["Psychology", "Economics", "Business", "Sociology"]
    req_fields = ("title,abstract,year,publicationDate,citationCount,"
                  "publicationTypes,externalIds,venue,openAccessPdf,fieldsOfStudy")
    headers = {"x-api-key": SEMANTICSCHOLAR_API_KEY} if SEMANTICSCHOLAR_API_KEY else {}
    start = (date.today() - timedelta(days=days_back)).isoformat()
    today = date.today().isoformat()

    papers = []
    started = time.time()
    for field in fields:
        if time.time() - started > 90:
            print("[semanticscholar] 시간 상한 도달, 중단")
            break
        params = {"fields": req_fields, "fieldsOfStudy": field,
                  "publicationTypes": "JournalArticle,Review,Conference",
                  "publicationDateOrYear": f"{start}:{today}", "limit": 50}
        results = _s2_request(base, params, headers)
        papers.extend(_s2_to_paper(raw) for raw in results)
        print(f"[semanticscholar] {field}: {len(results)}건")
        time.sleep(0.5)

    print(f"[semanticscholar] 총 {len(papers)}건")
    return papers


def _s2_request(base, params, headers):
    for attempt in range(2):
        try:
            resp = requests.get(base, params=params, headers=headers, timeout=20)
            if resp.status_code == 429:
                wait = 3 * (attempt + 1)
                print(f"[semanticscholar] 사용량 초과, {wait}초 대기")
                time.sleep(wait)
                continue
            resp.raise_for_status()
            return resp.json().get("data", []) or []
        except (requests.RequestException, ValueError) as e:
            print(f"[semanticscholar] 오류: {e}")
            return []
    return []


def _s2_to_paper(raw):
    p = blank_paper()
    ext = deep_get(raw, "externalIds", default={}) or {}
    p["doi"] = normalize_doi(ext.get("DOI"))
    p["pmid"] = ext.get("PubMed")
    p["title_en"] = strip_html(deep_get(raw, "title"))
    p["abstract_en"] = strip_html(deep_get(raw, "abstract"))
    p["authors"] = [{"name": a.get("name")}
                    for a in deep_get(raw, "authors", default=[]) if isinstance(a, dict)]
    p["publication_year"] = deep_get(raw, "year")
    p["publication_date"] = deep_get(raw, "publicationDate")
    p["citation_count"] = deep_get(raw, "citationCount", default=0)
    p["primary_category"] = (deep_get(raw, "fieldsOfStudy", default=[]) or [None])[0]
    p["journal_name"] = deep_get(raw, "venue")
    p["is_open_access"] = bool(deep_get(raw, "openAccessPdf"))
    p["fulltext_url"] = deep_get(raw, "openAccessPdf", "url")
    hints = deep_get(raw, "publicationTypes", default=[])
    p["study_type"] = classify_study_type(hints, p["abstract_en"])
    p["sources"] = ["semanticscholar"]
    p["source_ids"] = {"semanticscholar": deep_get(raw, "paperId")}
    return p


# ══════════════════════════════════════════════════════════════════
#  2) 저장  — 한꺼번에, 단 한 건이 문제여도 나머지는 살림
# ══════════════════════════════════════════════════════════════════

def _db_headers(upsert):
    h = {"apikey": SERVICE_KEY, "Authorization": f"Bearer {SERVICE_KEY}",
         "Content-Type": "application/json",
         "Prefer": "return=minimal"}
    if upsert:
        h["Prefer"] = "resolution=merge-duplicates,return=minimal"
    return h


def _post(rows, upsert):
    url = f"{SUPABASE_URL}/rest/v1/papers" + ("?on_conflict=doi" if upsert else "")
    try:
        resp = requests.post(url, headers=_db_headers(upsert), json=rows, timeout=60)
        resp.raise_for_status()
        return True
    except requests.RequestException:
        return False


def _save_chunk(rows, upsert):
    """
    묶음 저장. 실패하면 반씩 쪼개서 다시 시도 -> 문제 있는 한 건만 걸러지고
    나머지 정상 논문은 모두 저장됨. (한 개 때문에 200개가 버려지는 문제 해결)
    돌려주는 값: (성공수, 실패수)
    """
    if not rows:
        return 0, 0
    if _post(rows, upsert):
        return len(rows), 0
    if len(rows) == 1:
        print(f"[db] 저장 실패 1건 건너뜀: {rows[0].get('doi') or rows[0].get('title_en')}")
        return 0, 1
    mid = len(rows) // 2
    s1, f1 = _save_chunk(rows[:mid], upsert)
    s2, f2 = _save_chunk(rows[mid:], upsert)
    return s1 + s2, f1 + f2


def save_all(papers):
    rows, skipped = [], 0
    for p in papers:
        row = to_db_row(p)
        if row is None:
            skipped += 1
        else:
            rows.append(row)

    with_doi = [r for r in rows if r.get("doi")]
    without_doi = [r for r in rows if not r.get("doi")]

    print(f"[저장] 시작 — DOI있음 {len(with_doi)}건, DOI없음 {len(without_doi)}건")
    saved = failed = 0
    for i in range(0, len(with_doi), BATCH_SIZE):
        s, f = _save_chunk(with_doi[i:i + BATCH_SIZE], upsert=True)
        saved += s; failed += f
        print(f"[저장] {min(i+BATCH_SIZE, len(with_doi))}/{len(with_doi)} (DOI있음)")
    for i in range(0, len(without_doi), BATCH_SIZE):
        s, f = _save_chunk(without_doi[i:i + BATCH_SIZE], upsert=False)
        saved += s; failed += f
        print(f"[저장] {min(i+BATCH_SIZE, len(without_doi))}/{len(without_doi)} (DOI없음)")

    return saved, skipped, failed


def log_run(fetched, saved, skipped, failed):
    url = f"{SUPABASE_URL}/rest/v1/collection_runs"
    payload = {"source": "all", "records_fetched": fetched, "records_new": saved,
               "records_updated": 0, "records_failed": failed,
               "error_message": f"건너뜀 {skipped}건" if skipped else None}
    try:
        requests.post(url, headers=_db_headers(False), json=payload, timeout=15)
    except requests.RequestException:
        pass


def enrich_categories(papers):
    """
    분야(primary_category)가 빈 논문을, DOI로 OpenAlex에 물어서 채움.
    50개씩 묶어서 한 번에 조회 -> 하나씩 묻는 것보다 수십 배 빠름.
    """
    need = [p for p in papers
            if (not p.get("primary_category") or not p.get("license")) and p.get("doi")]
    total = len(need)
    if not total:
        print("[분야보완] 채울 대상 없음")
        return 0

    print(f"[분야보완] 대상 {total}건(분야/라이선스), 50개씩 묶어서 조회 시작")
    by_doi = {p["doi"]: p for p in need}
    filled = 0
    dois = list(by_doi.keys())

    for i in range(0, len(dois), 50):
        chunk = dois[i:i + 50]
        # OpenAlex: doi:A|B|C 형태로 여러 개를 한 번에 요청
        filter_val = "doi:" + "|".join(chunk)
        params = {
            "api_key": OPENALEX_API_KEY,
            "filter": filter_val,
            "select": "doi,primary_topic,best_oa_location,primary_location",
            "per_page": 50,
        }
        try:
            resp = requests.get("https://api.openalex.org/works", params=params, timeout=30)
            if resp.status_code != 200:
                print(f"[분야보완] {i+len(chunk)}/{total} (이 묶음 응답 {resp.status_code}, 건너뜀)")
                continue
            for work in resp.json().get("results", []):
                doi = normalize_doi(deep_get(work, "doi"))
                if not doi or doi not in by_doi:
                    continue
                target = by_doi[doi]
                changed = False
                field = deep_get(work, "primary_topic", "field", "display_name")
                if field and not target.get("primary_category"):
                    target["primary_category"] = field
                    changed = True
                lic = (deep_get(work, "best_oa_location", "license")
                       or deep_get(work, "primary_location", "license"))
                if lic and not target.get("license"):
                    target["license"] = lic
                    changed = True
                if changed:
                    filled += 1
        except (requests.RequestException, ValueError) as e:
            print(f"[분야보완] {i+len(chunk)}/{total} 오류(건너뜀): {e}")
            continue
        print(f"[분야보완] {min(i+50, total)}/{total} 진행 (누적 {filled}건 채움)")
        time.sleep(0.2)

    print(f"[분야보완] 완료 — 총 {filled}건 채움")
    return filled


def existing_titles_without_doi():
    """
    이미 저장된, DOI 없는 논문들의 제목을 모아옴 (중복 방지용).
    DOI 없는 논문은 제목으로만 중복을 판단할 수 있어서 필요함.
    """
    import re
    titles = set()
    url = (f"{SUPABASE_URL}/rest/v1/papers"
           f"?select=title_en&doi=is.null&limit=10000")
    try:
        resp = requests.get(url, headers=_db_headers(False), timeout=30)
        resp.raise_for_status()
        for r in resp.json():
            t = r.get("title_en")
            if t:
                titles.add(re.sub(r"[^a-z0-9]", "", t.lower()))
    except requests.RequestException:
        pass
    return titles


# ══════════════════════════════════════════════════════════════════
#  3) 전체 실행
# ══════════════════════════════════════════════════════════════════

def main():
    print(f"=== 논문 수집 시작 ({date.today().isoformat()}, 최근 {DAYS_BACK}일) ===\n")

    all_papers = []
    # 순서: 주력(OpenAlex) -> Europe PMC -> 느린 Semantic Scholar 마지막
    for name, fetch in (("openalex", fetch_openalex),
                        ("europepmc", fetch_europepmc),
                        ("semanticscholar", fetch_semanticscholar)):
        print(f"--- {name} ---")
        try:
            all_papers.extend(fetch(DAYS_BACK))
        except Exception as e:
            print(f"[{name}] 전체 실패(건너뜀): {e}")
        print()

    fetched = len(all_papers)
    print(f"=== 수집 합계: {fetched}건 (합치기 전) ===")

    merged = dedupe_and_merge(all_papers)
    print(f"=== 중복 합친 뒤: {len(merged)}건 ===")

    # 수명 규칙: 최근 3개월 전부 / 그 이후 검증된 것만 / 미래·초과 제외
    kept = [p for p in merged if passes_retention(p)]
    print(f"=== 수명 규칙 통과: {len(kept)}건 (제외 {len(merged) - len(kept)}건) ===")

    # DOI 없는 논문은 이미 DB에 같은 제목이 있으면 제외 (누적 중복 방지)
    import re
    existing = existing_titles_without_doi()
    deduped = []
    for p in kept:
        if not p.get("doi") and p.get("title_en"):
            norm = re.sub(r"[^a-z0-9]", "", p["title_en"].lower())
            if norm in existing:
                continue
        deduped.append(p)
    print(f"=== DOI없는 중복 제외 뒤: {len(deduped)}건 ===")

    # 분야 빈 논문을 DOI로 OpenAlex 조회해 보완
    filled = enrich_categories(deduped)
    print(f"=== 분야 보완: {filled}건 채움 ===")

    saved, skipped, failed = save_all(deduped)
    print(f"=== 저장: 성공 {saved} / 건너뜀 {skipped} / 실패 {failed} ===")

    log_run(fetched, saved, skipped, failed)

    # 제목 한글화 (배치): 이전 배치 회수 + 새 배치 제출
    try:
        import translate_titles
        translate_titles.run()
    except Exception as e:
        print(f"[제목번역] 오류(수집에는 영향 없음): {e}")


if __name__ == "__main__":
    main()
