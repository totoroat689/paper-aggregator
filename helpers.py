"""
helpers.py  —  밑받침 로직 모음 (네트워크 접속 없음, 순수 데이터 처리만)

담고 있는 것:
  1) 공통 형식(모든 논문이 따르는 하나의 형태) + 안전 도우미
  2) 연구유형 판별 (실험/메타분석 등)
  3) 중복 합치기 (같은 논문을 하나로)

collect.py가 이 파일을 가져다 씁니다.
"""

import re

# ── 데이터베이스 표(papers)의 칸 이름과 정확히 일치 ──────────────
PAPER_FIELDS = [
    "doi", "pmid",
    "title_en", "abstract_en",
    "authors", "countries",
    "publication_year", "publication_date", "source_indexed_date",
    "study_type", "is_retracted", "citation_count",
    "primary_category",
    "sources", "source_ids",
    "fulltext_url", "is_open_access", "journal_name",
]


def blank_paper():
    """모든 칸이 안전한 기본값으로 채워진 빈 논문 한 건."""
    return {
        "doi": None, "pmid": None,
        "title_en": None, "abstract_en": None,
        "authors": [], "countries": [],
        "publication_year": None, "publication_date": None, "source_indexed_date": None,
        "study_type": "unclassified", "is_retracted": False, "citation_count": 0,
        "primary_category": None,
        "sources": [], "source_ids": {},
        "fulltext_url": None, "is_open_access": False, "journal_name": None,
    }


def deep_get(data, *keys, default=None):
    """중첩 데이터에서 안전하게 값 꺼내기. 중간이 비어도 절대 안 넘어짐."""
    cur = data
    for key in keys:
        if isinstance(cur, dict):
            cur = cur.get(key)
        else:
            return default
    return cur if cur is not None else default


def normalize_doi(doi):
    """DOI 앞 주소 제거 + 소문자 통일 (출처마다 모양이 달라서 필수)."""
    if not doi or not isinstance(doi, str):
        return None
    doi = doi.strip().lower()
    doi = re.sub(r"^https?://(dx\.)?doi\.org/", "", doi)
    return doi or None


def clean_date(value):
    """'YYYY-MM-DD' 형태만 통과. 연도만 있거나 이상하면 None (저장 오류 방지)."""
    if not value or not isinstance(value, str):
        return None
    m = re.match(r"(\d{4}-\d{2}-\d{2})", value.strip())
    return m.group(1) if m else None


def safe_int(value):
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


# ── 연구유형 판별 ────────────────────────────────────────────────
_META = ["meta-analysis", "meta analysis", "systematic review"]
_RCT = ["randomized controlled trial", "randomised controlled trial",
        "randomized clinical trial", "rct"]
_EXPERIMENT_WORDS = [
    "randomized", "randomised", "randomly assigned", "randomly allocated",
    "control group", "placebo", "double-blind", "double blind", "single-blind",
]


def classify_study_type(hints, abstract_en):
    """1) 출처가 준 유형 표시를 먼저 보고, 2) 없으면 초록에서 실험 흔적을 찾음."""
    combined = " ".join(str(t).lower() for t in (hints or []) if t)

    if any(m in combined for m in _META):
        return "meta_analysis"
    if any(m in combined for m in _RCT):
        return "rct"

    if abstract_en and isinstance(abstract_en, str):
        text = abstract_en.lower()
        if any(m in text for m in _META):
            return "meta_analysis"
        if sum(1 for w in _EXPERIMENT_WORDS if w in text) >= 2:
            return "experimental_likely"

    if "review" in combined:
        return "review"
    return "unclassified"


# ── 중복 합치기 (버그 수정판) ────────────────────────────────────
# 합칠 때 어느 출처 값을 먼저 채울지 정하는 '단일 순서'.
# 이 순서로 '빈 칸만 채우기'를 하면 칸마다 알맞은 출처가 자연스럽게 선택됨:
#   - 초록/저널/PMID -> europepmc (가장 깔끔)
#   - 국가/분류 -> europepmc엔 없으므로 자동으로 openalex 값이 채워짐
_MERGE_ORDER = {"europepmc": 0, "openalex": 1, "semanticscholar": 2}

# '빈 칸이면 채우기' 규칙을 적용할 칸들
_FILL_FIELDS = [
    "doi", "pmid", "title_en", "abstract_en", "countries", "primary_category",
    "publication_year", "publication_date", "source_indexed_date",
    "journal_name", "fulltext_url",
]

_TYPE_STRENGTH = {
    "meta_analysis": 5, "rct": 4, "experimental_likely": 3,
    "review": 2, "unclassified": 1, None: 0,
}


def dedupe_and_merge(papers):
    """공통 형식 논문 목록 -> 중복을 합친 목록."""
    groups = {}
    for p in papers:
        key = _key_for(p)
        if key is None:
            continue
        groups.setdefault(key, []).append(p)
    return [_combine(group) for group in groups.values()]


def _key_for(paper):
    """같은 논문인지 가리는 열쇠. DOI 우선, 없으면 (제목+연도)."""
    doi = paper.get("doi")
    if doi:
        return ("doi", doi)
    title = paper.get("title_en")
    if title:
        norm = re.sub(r"[^a-z0-9]", "", title.lower())
        if norm:
            return ("title", norm, paper.get("publication_year"))
    return None


def _combine(group):
    """
    같은 논문(단일 출처짜리들)의 묶음을 하나로 합침.
    핵심: 원본을 건드리지 않고, 정해진 출처 순서로 '빈 칸만 채우기'.
    -> 각 논문이 '단일 출처'인 상태에서만 출처를 판단하므로 값이 꼬이지 않음(버그 해결).
    """
    ordered = sorted(group, key=lambda p: _MERGE_ORDER.get(_source_of(p), 99))

    base = blank_paper()
    for p in ordered:
        base["sources"] = sorted(set(base["sources"] + (p.get("sources") or [])))
        merged_ids = dict(base["source_ids"])
        merged_ids.update(p.get("source_ids") or {})
        base["source_ids"] = merged_ids

        base["citation_count"] = max(base["citation_count"] or 0, p.get("citation_count") or 0)
        base["is_retracted"] = base["is_retracted"] or bool(p.get("is_retracted"))
        base["is_open_access"] = base["is_open_access"] or bool(p.get("is_open_access"))
        base["study_type"] = _stronger_type(base["study_type"], p.get("study_type"))

        if not base["authors"] and p.get("authors"):
            base["authors"] = p["authors"]

        for field in _FILL_FIELDS:
            if not base.get(field) and p.get(field):
                base[field] = p[field]

    return base


def _source_of(paper):
    srcs = paper.get("sources") or []
    return srcs[0] if srcs else ""


def _stronger_type(a, b):
    return a if _TYPE_STRENGTH.get(a, 0) >= _TYPE_STRENGTH.get(b, 0) else b


# ── 저장 직전 최종 정리 ──────────────────────────────────────────
def to_db_row(paper):
    """
    데이터베이스가 받아들일 안전한 형태로 마지막 정리.
    제목이 없으면 저장 불가이므로 None을 반환하여 건너뛰게 함.
    """
    if not paper.get("title_en"):
        return None

    row = {field: paper.get(field) for field in PAPER_FIELDS}
    row["publication_date"] = clean_date(paper.get("publication_date"))
    row["source_indexed_date"] = clean_date(paper.get("source_indexed_date"))
    row["publication_year"] = safe_int(paper.get("publication_year"))
    row["citation_count"] = safe_int(paper.get("citation_count")) or 0
    row["countries"] = paper.get("countries") or []
    row["sources"] = paper.get("sources") or []
    row["source_ids"] = paper.get("source_ids") or {}
    row["is_retracted"] = bool(paper.get("is_retracted"))
    row["is_open_access"] = bool(paper.get("is_open_access"))
    return row
