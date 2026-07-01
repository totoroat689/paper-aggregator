"""
OpenAlex에서 논문을 가져오는 파일.
키가 필요한 출처입니다 (GitHub Secrets에 OPENALEX_API_KEY로 저장).
"""

import os
import time
from datetime import date, timedelta

import requests

BASE_URL = "https://api.openalex.org/works"
FIELDS_URL = "https://api.openalex.org/fields"

API_KEY = os.environ.get("OPENALEX_API_KEY", "")


def get_all_field_ids():
    """OpenAlex의 26개 분야 목록을 실시간으로 가져옵니다."""
    params = {"api_key": API_KEY, "per_page": 50}
    resp = requests.get(FIELDS_URL, params=params, timeout=30)
    resp.raise_for_status()
    data = resp.json()
    return [{"id": f["id"], "name": f["display_name"]} for f in data.get("results", [])]


def fetch_recent(days_back=3, per_field_limit=100):
    """26개 분야를 돌면서 최근 N일 동안 나온 논문을 가져옵니다."""
    start_date = (date.today() - timedelta(days=days_back)).isoformat()
    fields = get_all_field_ids()

    all_results = []
    for field in fields:
        params = {
            "api_key": API_KEY,
            "filter": f"primary_topic.field.id:{field['id']},from_publication_date:{start_date}",
            "per_page": per_field_limit,
            "sort": "publication_date:desc",
        }
        try:
            resp = requests.get(BASE_URL, params=params, timeout=30)
            resp.raise_for_status()
            data = resp.json()
            got = data.get("results", [])
            all_results.extend(got)
            print(f"[OpenAlex] {field['name']}: {len(got)}건")
        except requests.RequestException as e:
            print(f"[OpenAlex] {field['name']} 분야에서 오류: {e}")
        time.sleep(0.2)

    return all_results


def normalize(raw):
    """원본 논문 데이터를 우리 공통 양식으로 바꿉니다."""
    authorships = raw.get("authorships", [])
    countries = []
    for a in authorships:
        countries.extend(a.get("countries", []))

    primary_topic = raw.get("primary_topic") or {}
    field = primary_topic.get("field") or {}

    return {
        "doi_raw": raw.get("doi"),
        "pmid": None,
        "title_en": raw.get("title") or raw.get("display_name"),
        "abstract_en": reconstruct_abstract(raw.get("abstract_inverted_index")),
        "authors": [{"name": a.get("author", {}).get("display_name")} for a in authorships],
        "countries": list(set(countries)),
        "publication_year": raw.get("publication_year"),
        "publication_date": raw.get("publication_date"),
        "source_indexed_date": raw.get("created_date"),
        "study_type_hint": [raw.get("type")],
        "is_retracted": raw.get("is_retracted", False),
        "citation_count": raw.get("cited_by_count", 0) or 0,
        "primary_category": field.get("display_name"),
        "journal_name": (raw.get("primary_location") or {}).get("source", {}).get("display_name"),
        "is_open_access": (raw.get("open_access") or {}).get("is_oa", False),
        "fulltext_url": (raw.get("primary_location") or {}).get("landing_page_url"),
        "source": "openalex",
        "source_id": raw.get("id"),
        "raw_data": raw,
    }


def reconstruct_abstract(inverted_index):
    """OpenAlex는 초록을 '단어 위치 목록'으로 줍니다. 이걸 원래 문장으로 다시 조립합니다."""
    if not inverted_index:
        return None
    position_word = {}
    for word, positions in inverted_index.items():
        for pos in positions:
            position_word[pos] = word
    if not position_word:
        return None
    max_pos = max(position_word.keys())
    return " ".join(position_word.get(i, "") for i in range(max_pos + 1))
