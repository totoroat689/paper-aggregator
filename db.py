"""
Supabase(데이터베이스)에 저장하고 갱신하는 파일.
Flare[V]와는 완전히 다른, 새로 만든 프로젝트에 저장합니다.
"""

import os

import requests

from normalize_and_merge import merge_records

SUPABASE_URL = os.environ.get("SUPABASE_URL", "").rstrip("/")
SUPABASE_SERVICE_KEY = os.environ.get("SUPABASE_SERVICE_KEY", "")


def _headers():
    return {
        "apikey": SUPABASE_SERVICE_KEY,
        "Authorization": f"Bearer {SUPABASE_SERVICE_KEY}",
        "Content-Type": "application/json",
    }


def get_existing_by_doi(doi):
    if not doi:
        return None
    url = f"{SUPABASE_URL}/rest/v1/papers"
    params = {"doi": f"eq.{doi}", "select": "*"}
    resp = requests.get(url, headers=_headers(), params=params, timeout=15)
    resp.raise_for_status()
    results = resp.json()
    return results[0] if results else None


def insert_paper(record):
    url = f"{SUPABASE_URL}/rest/v1/papers"
    resp = requests.post(url, headers=_headers(), json=record, timeout=30)
    resp.raise_for_status()


def update_paper(doi, record):
    url = f"{SUPABASE_URL}/rest/v1/papers"
    params = {"doi": f"eq.{doi}"}
    resp = requests.patch(url, headers=_headers(), params=params, json=record, timeout=30)
    resp.raise_for_status()


def upsert_merged(new_record):
    """같은 doi가 이미 있으면 합쳐서 갱신, 없으면 새로 추가합니다."""
    doi = new_record.get("doi")
    existing = get_existing_by_doi(doi) if doi else None

    if existing:
        merged = merge_records(existing, new_record)
        update_paper(doi, merged)
        return "updated"

    insert_paper(new_record)
    return "new"


def log_collection_run(source, fetched, new, updated, failed, error=None):
    url = f"{SUPABASE_URL}/rest/v1/collection_runs"
    payload = {
        "source": source,
        "records_fetched": fetched,
        "records_new": new,
        "records_updated": updated,
        "records_failed": failed,
        "error_message": error,
    }
    try:
        requests.post(url, headers=_headers(), json=payload, timeout=15)
    except requests.RequestException:
        pass
