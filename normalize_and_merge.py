"""
같은 논문인지 구분하고, 여러 출처의 정보를 하나로 합치는 규칙.
"""

import difflib
import re

RCT_MARKERS = ["randomized controlled trial", "randomised controlled trial", "rct"]
META_MARKERS = ["meta-analysis", "systematic review"]
EXPERIMENT_SIGNAL_WORDS = [
    "randomized", "randomised", "randomly assigned", "control group",
    "placebo", "double-blind", "double blind",
]

# 값이 여러 출처에서 다를 때, 어느 출처를 먼저 믿을지 순서
FIELD_PRIORITY = {
    "countries": ["openalex"],
    "abstract_en": ["europepmc", "semanticscholar", "openalex"],
    "study_type": ["europepmc", "semanticscholar", "openalex"],
    "primary_category": ["openalex"],
}


def normalize_doi(doi):
    """DOI 앞의 주소 부분을 떼고 소문자로 통일합니다."""
    if not doi:
        return None
    doi = doi.strip().lower()
    doi = re.sub(r"^https?://(dx\.)?doi\.org/", "", doi)
    return doi or None


def classify_study_type(study_type_hint, abstract_en):
    """
    1단계: 출처가 준 표시를 먼저 봅니다 (정확함).
    2단계: 표시가 없으면 초록에서 실험의 흔적을 찾습니다.
    """
    combined = " ".join(str(t).lower() for t in (study_type_hint or []))

    if any(m in combined for m in META_MARKERS):
        return "meta_analysis"
    if any(m in combined for m in RCT_MARKERS):
        return "rct"
    if "review" in combined:
        return "review"

    if abstract_en:
        text = abstract_en.lower()
        hits = sum(1 for w in EXPERIMENT_SIGNAL_WORDS if w in text)
        if hits >= 2:
            return "experimental_likely"

    return "unclassified"


def normalize_record(record):
    """DOI 정리 + 연구유형 분류까지 마친 최종 형태로 만듭니다."""
    r = dict(record)
    r["doi"] = normalize_doi(r.get("doi_raw"))
    r["study_type"] = classify_study_type(r.get("study_type_hint"), r.get("abstract_en"))
    return r


def titles_are_similar(title_a, title_b, threshold=0.92):
    """DOI가 둘 다 없을 때만 쓰는 마지막 수단 — 제목이 매우 비슷한지 확인."""
    norm_a = _normalize_title(title_a)
    norm_b = _normalize_title(title_b)
    if not norm_a or not norm_b:
        return False
    return difflib.SequenceMatcher(None, norm_a, norm_b).ratio() > threshold


def _normalize_title(title):
    if not title:
        return ""
    title = title.lower()
    title = re.sub(r"[^a-z0-9\s]", "", title)
    return re.sub(r"\s+", " ", title).strip()


def merge_records(existing, new):
    """같은 논문으로 판정된 두 레코드를 하나로 합칩니다."""
    merged = dict(existing)

    merged["sources"] = sorted(set(existing.get("sources", []) + [new["source"]]))
    merged["source_ids"] = dict(existing.get("source_ids") or {})
    merged["source_ids"][new["source"]] = new.get("source_id")

    merged["citation_count"] = max(existing.get("citation_count") or 0, new.get("citation_count") or 0)

    for field, priority in FIELD_PRIORITY.items():
        new_value = new.get(field)
        if not new_value:
            continue
        current_source = existing.get(f"_{field}_source")
        if current_source is None or priority.index(new["source"]) < priority.index(current_source):
            merged[field] = new_value
            merged[f"_{field}_source"] = new["source"]

    merged["is_retracted"] = existing.get("is_retracted", False) or new.get("is_retracted", False)

    return merged
