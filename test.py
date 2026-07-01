"""
test.py  —  지금까지 터졌던 상황 + 이번에 고친 버그를 검증.
실행: python test.py
"""

import collect
from helpers import blank_paper, to_db_row, dedupe_and_merge


def test_openalex_dirty():
    """source=None, author=None, 초록 없음 등 지저분한 OpenAlex 논문"""
    raw = {
        "id": "https://openalex.org/W1",
        "doi": "https://doi.org/10.1/AbC",
        "title": "Dirty Paper",
        "publication_year": 2016, "publication_date": "2016-09-06",
        "created_date": "2025-10-10T00:00:00",
        "primary_location": {"source": None, "landing_page_url": "https://x.com"},
        "open_access": None,
        "authorships": [{"author": None, "countries": ["US"]}],
        "primary_topic": None, "abstract_inverted_index": None,
    }
    p = collect._openalex_to_paper(raw)
    assert p["doi"] == "10.1/abc"
    assert p["journal_name"] is None
    assert p["countries"] == ["US"]
    assert to_db_row(p)["publication_date"] == "2016-09-06"
    print("  OpenAlex 지저분한 데이터: 통과")


def test_epmc_dirty():
    raw = {
        "id": "9", "doi": "10.2/X", "title": "EPMC Paper.",
        "abstractText": "<h4>Design</h4>Randomized, double-blind study with placebo control group.",
        "journalInfo": {"journal": None},
        "pubTypeList": {"pubType": ["Randomized Controlled Trial"]},
        "pubYear": "2024", "firstPublicationDate": "2024-01-15",
    }
    p = collect._europepmc_to_paper(raw)
    assert p["doi"] == "10.2/x"
    assert "<h4>" not in (p["abstract_en"] or "")
    assert p["study_type"] == "rct"
    assert p["journal_name"] is None
    print("  Europe PMC 지저분한 데이터: 통과")


def test_merge_three_sources_correct_values():
    """★ 이번에 고친 버그: 3곳에 다 있는 논문 -> 값이 올바른 출처에서 오는가"""
    epmc = blank_paper(); epmc.update(
        doi="10.9/z", title_en="Shared", sources=["europepmc"],
        source_ids={"europepmc": "1"}, citation_count=5,
        abstract_en="clean abstract from epmc", countries=[], journal_name="Nature")
    oalex = blank_paper(); oalex.update(
        doi="10.9/z", title_en="Shared", sources=["openalex"],
        source_ids={"openalex": "2"}, citation_count=12,
        abstract_en="messy openalex abstract", countries=["GB"], primary_category="Psychology")
    s2 = blank_paper(); s2.update(
        doi="10.9/z", title_en="Shared", sources=["semanticscholar"],
        source_ids={"semanticscholar": "3"}, citation_count=8)

    # 일부러 순서를 섞어서 넣어도 결과가 같아야 함
    merged = dedupe_and_merge([s2, oalex, epmc])
    assert len(merged) == 1
    m = merged[0]
    assert m["sources"] == ["europepmc", "openalex", "semanticscholar"]
    assert m["citation_count"] == 12                         # 큰 값
    assert m["countries"] == ["GB"]                           # openalex에서
    assert m["primary_category"] == "Psychology"             # openalex에서
    assert m["abstract_en"] == "clean abstract from epmc"    # europepmc 우선(깔끔)
    assert m["journal_name"] == "Nature"                     # europepmc에서
    assert m["source_ids"] == {"europepmc": "1", "openalex": "2", "semanticscholar": "3"}
    print("  3곳 병합 값 정확성(버그수정): 통과")


def test_no_doi_merge():
    a = blank_paper(); a.update(title_en="No DOI Study", publication_year=2025,
                                sources=["europepmc"], citation_count=1)
    b = blank_paper(); b.update(title_en="No DOI Study", publication_year=2025,
                                sources=["openalex"], citation_count=9)
    merged = dedupe_and_merge([a, b])
    assert len(merged) == 1 and merged[0]["citation_count"] == 9
    print("  DOI 없는 논문 병합: 통과")


def test_title_missing_skipped():
    assert to_db_row(blank_paper()) is None
    print("  제목 없는 논문 제외: 통과")


def test_year_only_date():
    p = blank_paper(); p.update(title_en="X", publication_date="2016")
    assert to_db_row(p)["publication_date"] is None
    print("  연도만 있는 날짜 처리: 통과")


def test_save_chunk_isolates_bad(monkeypatch=None):
    """★ 저장 안전장치: 한 건이 실패해도 나머지는 저장되는가 (가짜 저장으로 검증)"""
    calls = {"bad_seen": 0}

    def fake_post(rows, upsert):
        # doi가 'BAD'인 행이 섞인 묶음은 실패로 처리
        if any(r.get("doi") == "BAD" for r in rows):
            return False
        return True

    original = collect._post
    collect._post = fake_post
    try:
        rows = [{"doi": f"ok{i}", "title_en": "t"} for i in range(10)]
        rows.insert(5, {"doi": "BAD", "title_en": "bad"})
        saved, failed = collect._save_chunk(rows, upsert=True)
        assert saved == 10, f"정상 10건 저장 기대, 실제 {saved}"
        assert failed == 1, f"실패 1건 기대, 실제 {failed}"
    finally:
        collect._post = original
    print("  저장 안전장치(한 건 격리): 통과")


if __name__ == "__main__":
    print("=== 검증 시작 ===")
    test_openalex_dirty()
    test_epmc_dirty()
    test_merge_three_sources_correct_values()
    test_no_doi_merge()
    test_title_missing_skipped()
    test_year_only_date()
    test_save_chunk_isolates_bad()
    print("\n모든 테스트 통과!")
