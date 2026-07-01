"""
지난번 실제로 받았던 API 응답(진짜 데이터)으로 정리 로직이 제대로 작동하는지 확인.
"""

import sys
sys.path.insert(0, ".")

import collect_europepmc
import collect_openalex
from normalize_and_merge import normalize_record

# 실제 Europe PMC 응답에서 가져온 논문 1건 (요약)
EUROPEPMC_SAMPLE = {
    "id": "15683137",
    "pmid": "15683137",
    "doi": "10.1093/sleep/27.7.1479",
    "title": "Sleep spindles and their significance for declarative memory consolidation.",
    "authorList": {"author": [{"fullName": "Schabus M"}, {"fullName": "Gruber G"}]},
    "pubYear": "2004",
    "abstractText": "<h4>Study objectives</h4>Functional significance of stage 2 sleep spindle activity.<h4>Design</h4>Randomized, within-subject, multicenter.",
    "pubTypeList": {"pubType": ["Clinical Trial", "Randomized Controlled Trial", "Journal Article"]},
    "citedByCount": 385,
    "isOpenAccess": "N",
    "firstPublicationDate": "2004-12-01",
    "firstIndexDate": "2009-01-30",
    "journalInfo": {"journal": {"title": "Sleep"}},
    "fullTextUrlList": {"fullTextUrl": [{"availabilityCode": "S", "url": "https://doi.org/10.1093/sleep/27.7.1479"}]},
}

# 실제 OpenAlex 응답에서 가져온 논문 1건 (요약)
OPENALEX_SAMPLE = {
    "id": "https://openalex.org/W2559720584",
    "doi": "https://doi.org/10.1093/acrefore/9780190236557.013.129",
    "title": "Habit Formation and Behavior Change",
    "publication_year": 2016,
    "publication_date": "2016-09-06",
    "created_date": "2025-10-10T00:00:00",
    "cited_by_count": 204,
    "type": "reference-entry",
    "is_retracted": False,
    "primary_topic": {"field": {"display_name": "Psychology"}},
    "primary_location": {"landing_page_url": "https://doi.org/x", "source": {"display_name": "Oxford Encyclopedia"}},
    "open_access": {"is_oa": False},
    "authorships": [
        {"author": {"display_name": "Benjamin Gardner"}, "countries": ["GB"]},
        {"author": {"display_name": "Amanda L. Rebar"}, "countries": ["AU"]},
    ],
    "abstract_inverted_index": {"Habit": [0], "formation": [1], "is": [2], "powerful.": [3]},
}


def test_europepmc():
    print("--- Europe PMC 테스트 ---")
    normalized = collect_europepmc.normalize(EUROPEPMC_SAMPLE)
    final = normalize_record(normalized)

    assert final["doi"] == "10.1093/sleep/27.7.1479", f"DOI 정리 실패: {final['doi']}"
    assert "<h4>" not in (final["abstract_en"] or ""), "초록에 태그가 남아있음"
    assert final["study_type"] == "rct", f"연구유형 분류 실패: {final['study_type']}"

    print(f"  DOI: {final['doi']}")
    print(f"  초록: {final['abstract_en'][:60]}...")
    print(f"  연구유형: {final['study_type']}")
    print("  통과\n")


def test_openalex():
    print("--- OpenAlex 테스트 ---")
    normalized = collect_openalex.normalize(OPENALEX_SAMPLE)
    final = normalize_record(normalized)

    assert final["doi"] == "10.1093/acrefore/9780190236557.013.129", f"DOI 정리 실패: {final['doi']}"
    assert final["abstract_en"] == "Habit formation is powerful.", f"초록 복원 실패: {final['abstract_en']}"
    assert set(final["countries"]) == {"GB", "AU"}, f"국가 추출 실패: {final['countries']}"

    print(f"  DOI: {final['doi']}")
    print(f"  초록 복원 결과: {final['abstract_en']}")
    print(f"  국가: {final['countries']}")
    print("  통과\n")


if __name__ == "__main__":
    test_europepmc()
    test_openalex()
    print("모든 테스트 통과!")
