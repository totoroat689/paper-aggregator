"""
Semantic Scholar에서 논문을 가져오는 파일.
키가 없어도 되지만, 전 세계가 같은 무료 창구를 나눠 씁니다.
가끔 "너무 많은 요청"이라는 응답이 오는데, 우리 잘못이 아니라
그 순간 다른 사람들이 몰린 것뿐입니다 (자동으로 재시도합니다).
"""

import os
import time
from datetime import date, timedelta

import requests

BASE_URL = "https://api.semanticscholar.org/graph/v1/paper/search/bulk"
API_KEY = os.environ.get("SEMANTICSCHOLAR_API_KEY", "")

FIELDS_OF_STUDY = [
    "Computer Science", "Medicine", "Chemistry", "Biology", "Materials Science",
    "Physics", "Geology", "Psychology", "Art", "History", "Geography",
    "Sociology", "Business", "Political Science", "Economics", "Philosophy",
    "Mathematics", "Engineering", "Environmental Science",
    "Agricultural and Food Sciences", "Education", "Law", "Linguistics",
]

REQUEST_FIELDS = (
    "title,abstract,year,publicationDate,citationCount,"
    "publicationTypes,externalIds,venue,openAccessPdf,fieldsOfStudy"
)

MAX_RETRIES = 3


def fetch_recent(days_back=3, per_field_limit=100):
    """분야별로 돌면서 최근 N일 동안 나온 논문을 가져옵니다."""
    start_date = (date.today() - timedelta(days=days_back)).isoformat()
    today = date.today().isoformat()

    headers = {"x-api-key": API_KEY} if API_KEY else {}

    all_results = []
    for field in FIELDS_OF_STUDY:
        params = {
            "fields": REQUEST_FIELDS,
            "fieldsOfStudy": field,
            "publicationDateOrYear": f"{start_date}:{today}",
            "limit": per_field_limit,
        }
        for attempt in range(MAX_RETRIES):
            try:
                resp = requests.get(BASE_URL, params=params, headers=headers, timeout=30)
                if resp.status_code == 429:
                    wait = 5 * (attempt + 1)
                    print(f"[Semantic Scholar] {field}: 사용량 초과, {wait}초 대기")
                    time.sleep(wait)
                    continue
                resp.raise_for_status()
                data = resp.json()
                all_results.extend(data.get("data", []))
                break
            except requests.RequestException as e:
                print(f"[Semantic Scholar] {field} 분야에서 오류: {e}")
                break
        time.sleep(1.1)

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
