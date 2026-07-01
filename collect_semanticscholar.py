"""
Semantic Scholar에서 논문을 가져오는 파일.
키가 없어도 되지만, 전 세계가 같은 무료 창구를 나눠 씁니다.
가끔 "너무 많은 요청"이라는 응답이 오는데, 우리 잘못이 아니라
그 순간 다른 사람들이 몰린 것뿐입니다.

이 출처는 느리므로 "보조" 역할로만 씁니다:
- 다른 두 곳(OpenAlex, Europe PMC)이 약한 분야만 골라서 가져옵니다.
- 전체 시간이 상한을 넘으면 즉시 멈춥니다 (전체 수집이 늘어지지 않게).
"""

import os
import time
from datetime import date, timedelta

import requests

BASE_URL = "https://api.semanticscholar.org/graph/v1/paper/search/bulk"
API_KEY = os.environ.get("SEMANTICSCHOLAR_API_KEY", "")

# 23개 전체가 아니라, 다른 두 출처가 약한 "사회·심리·행동" 계열만 보조로 가져옵니다.
FIELDS_OF_STUDY = [
    "Psychology",
    "Economics",
    "Business",
    "Sociology",
]

REQUEST_FIELDS = (
    "title,abstract,year,publicationDate,citationCount,"
    "publicationTypes,externalIds,venue,openAccessPdf,fieldsOfStudy"
)

MAX_RETRIES = 2          # 막히면 빨리 포기
PER_FIELD_LIMIT = 50     # 분야당 개수도 축소
TIME_BUDGET_SECONDS = 90  # 이 시간을 넘으면 즉시 중단


def fetch_recent(days_back=3, per_field_limit=PER_FIELD_LIMIT):
    """대표 분야만, 시간 상한 안에서만 가져옵니다."""
    start_date = (date.today() - timedelta(days=days_back)).isoformat()
    today = date.today().isoformat()

    headers = {"x-api-key": API_KEY} if API_KEY else {}
    started = time.time()

    all_results = []
    for field in FIELDS_OF_STUDY:
        if time.time() - started > TIME_BUDGET_SECONDS:
            print(f"[Semantic Scholar] 시간 상한({TIME_BUDGET_SECONDS}초) 도달, 여기서 중단")
            break

        params = {
            "fields": REQUEST_FIELDS,
            "fieldsOfStudy": field,
            "publicationDateOrYear": f"{start_date}:{today}",
            "limit": per_field_limit,
        }
        for attempt in range(MAX_RETRIES):
            try:
                resp = requests.get(BASE_URL, params=params, headers=headers, timeout=20)
                if resp.status_code == 429:
                    wait = 3 * (attempt + 1)
                    print(f"[Semantic Scholar] {field}: 사용량 초과, {wait}초 대기")
                    time.sleep(wait)
                    continue
                resp.raise_for_status()
                data = resp.json()
                got = data.get("data", []) or []
                all_results.extend(got)
                print(f"[Semantic Scholar] {field}: {len(got)}건")
                break
            except requests.RequestException as e:
                print(f"[Semantic Scholar] {field} 분야에서 오류: {e}")
                break
        time.sleep(0.5)

    return all_results


def normalize(raw):
    """원본 논문 데이터를 우리 공통 양식으로 바꿉니다."""
    ext_ids = raw.get("externalIds") or {}
    return {
        "doi_raw": ext_ids.get("DOI"),
        "pmid": ext_ids.get("PubMed"),
        "title_en": raw.get("title"),
        "abstract_en": raw.get("abstract"),
        "authors": [{"name": a.get("name")} for a in (raw.get("authors") or [])],
        "countries": [],
        "publication_year": raw.get("year"),
        "publication_date": raw.get("publicationDate"),
        "source_indexed_date": None,
        "study_type_hint": raw.get("publicationTypes") or [],
        "is_retracted": False,
        "citation_count": raw.get("citationCount", 0) or 0,
        "primary_category": (raw.get("fieldsOfStudy") or [None])[0],
        "journal_name": raw.get("venue"),
        "is_open_access": bool(raw.get("openAccessPdf")),
        "fulltext_url": (raw.get("openAccessPdf") or {}).get("url"),
        "source": "semanticscholar",
        "source_id": raw.get("paperId"),
        "raw_data": raw,
    }
