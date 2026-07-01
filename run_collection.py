"""
전체 수집의 시작점.
GitHub Actions가 매일 이 파일을 자동으로 실행합니다.

흐름: 3개 출처에서 가져오기 -> 정리하기 -> 중복 합치기 -> 저장하기
"""

import os
from datetime import date

import collect_europepmc
import collect_openalex
import collect_semanticscholar
from normalize_and_merge import normalize_record
from db import upsert_merged, log_collection_run

DAYS_BACK = int(os.environ.get("COLLECT_DAYS_BACK", "3"))


def run_source(source_module, source_name):
    print(f"\n=== {source_name} 수집 시작 ===")

    try:
        raw_results = source_module.fetch_recent(days_back=DAYS_BACK)
    except Exception as e:
        print(f"[{source_name}] 수집 실패: {e}")
        log_collection_run(source_name, 0, 0, 0, 0, error=str(e))
        return

    fetched = len(raw_results)
    print(f"[{source_name}] {fetched}건 받아옴")

    new_count = 0
    updated_count = 0
    failed_count = 0

    for raw in raw_results:
        try:
            normalized = source_module.normalize(raw)
            final_record = normalize_record(normalized)
            db_record = _to_db_schema(final_record)
            result = upsert_merged(db_record)
            if result == "new":
                new_count += 1
            else:
                updated_count += 1
        except Exception as e:
            failed_count += 1
            print(f"[{source_name}] 한 건 처리 실패: {e}")

    log_collection_run(source_name, fetched, new_count, updated_count, failed_count)
    print(f"[{source_name}] 완료 — 신규 {new_count} / 갱신 {updated_count} / 실패 {failed_count}")


def _to_db_schema(record):
    return {
        "doi": record.get("doi"),
        "pmid": record.get("pmid"),
        "title_en": record.get("title_en"),
        "abstract_en": record.get("abstract_en"),
        "authors": record.get("authors"),
        "countries": record.get("countries") or [],
        "publication_year": record.get("publication_year"),
        "publication_date": record.get("publication_date"),
        "source_indexed_date": record.get("source_indexed_date"),
        "study_type": record.get("study_type"),
        "is_retracted": record.get("is_retracted", False),
        "citation_count": record.get("citation_count", 0),
        "primary_category": record.get("primary_category"),
        "journal_name": record.get("journal_name"),
        "is_open_access": record.get("is_open_access", False),
        "fulltext_url": record.get("fulltext_url"),
        "sources": [record.get("source")],
        "source_ids": {record.get("source"): record.get("source_id")},
        "raw_data": record.get("raw_data"),
    }


if __name__ == "__main__":
    print(f"논문 수집 시작 — {date.today().isoformat()}, 최근 {DAYS_BACK}일 기준")

    run_source(collect_openalex, "openalex")
    run_source(collect_europepmc, "europepmc")
    run_source(collect_semanticscholar, "semanticscholar")

    print("\n전체 완료.")
