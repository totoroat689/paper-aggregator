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
    "license",
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
        "license": None,
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


def strip_html(text):
    """제목·초록의 HTML 태그와 특수기호를 제거/복원. 이중 인코딩까지 처리."""
    if not text or not isinstance(text, str):
        return None
    import re as _re
    import html as _html
    # 이중 인코딩 대비 두 번 해제 (&amp;quot; -> &quot; -> ")
    text = _html.unescape(_html.unescape(text))
    # 태그 제거 (속성 있는 것 포함)
    text = _re.sub(r"</?h4[^>]*>", " ", text)
    text = _re.sub(r"<[^>]+>", "", text)
    # 남은 실체참조·비가시 공백 정리
    text = text.replace("\u00a0", " ").replace("\xa0", " ")
    return _re.sub(r"\s+", " ", text).strip() or None


# ── 26개 분야 영어 -> 한글 대응표 (번역 없이 무료로 한글화) ──────
CATEGORY_KO = {
    "Agricultural and Biological Sciences": "농업·생물학",
    "Arts and Humanities": "예술·인문학",
    "Biochemistry, Genetics and Molecular Biology": "생화학·유전·분자생물학",
    "Business, Management and Accounting": "경영·회계",
    "Chemical Engineering": "화학공학",
    "Chemistry": "화학",
    "Computer Science": "컴퓨터과학",
    "Decision Sciences": "의사결정학",
    "Earth and Planetary Sciences": "지구·행성과학",
    "Economics, Econometrics and Finance": "경제·금융",
    "Energy": "에너지",
    "Engineering": "공학",
    "Environmental Science": "환경과학",
    "Immunology and Microbiology": "면역·미생물학",
    "Materials Science": "재료공학",
    "Mathematics": "수학",
    "Medicine": "의학",
    "Neuroscience": "신경과학",
    "Nursing": "간호학",
    "Pharmacology, Toxicology and Pharmaceutics": "약리·독성학",
    "Physics and Astronomy": "물리·천문학",
    "Psychology": "심리학",
    "Social Sciences": "사회과학",
    "Veterinary": "수의학",
    "Dentistry": "치의학",
    "Health Professions": "보건의료",
    # Semantic Scholar 계열 이름도 흡수
    "Biology": "생물학", "Sociology": "사회과학", "Business": "경영·회계",
    "Political Science": "정치학", "Geography": "지리학", "Geology": "지질학",
    "Art": "예술·인문학", "History": "예술·인문학", "Philosophy": "예술·인문학",
    "Education": "교육학", "Law": "법학", "Linguistics": "언어학",
    "Agricultural and Food Sciences": "농업·식품과학",
}


def category_ko(name):
    """영어 분야명 -> 한글. 대응표에 없으면 원문 그대로, 비었으면 '기타'."""
    if not name:
        return "기타"
    return CATEGORY_KO.get(name, name)


def is_future_date(date_str):
    """오늘보다 미래 날짜인지 (아직 출판 안 된 이상 데이터 거르기용)."""
    clean = clean_date(date_str)
    if not clean:
        return False
    from datetime import date as _date
    return clean > _date.today().isoformat()


# ── 수명 규칙: 최근 3개월은 전부, 그 이후는 검증된 것만, 너무 오래되면 제외 ──
STRONG_TYPES = {"meta_analysis", "rct", "experimental_likely"}
RECENT_DAYS = 90          # 최근 3개월
MAX_AGE_YEARS = 3         # 3년 넘으면 수집 안 함
CITATION_THRESHOLD = 20   # 오래된 논문이 통과하려면 필요한 최소 인용수


def passes_retention(paper):
    """
    이 논문을 저장할 가치가 있는지 판정.
    - 미래 날짜 / 3년 초과: 제외
    - 최근 3개월: 전부 통과
    - 그 이후: 강한 연구유형(실험·메타) 또는 인용수 문턱 넘으면 통과
    """
    from datetime import date as _date, timedelta as _td

    pub = clean_date(paper.get("publication_date"))
    if is_future_date(paper.get("publication_date")):
        return False

    # 날짜를 모르면 일단 통과(버리기 아까움) — 단 미래 연도는 위에서 이미 거름
    if not pub:
        return True

    today = _date.today()
    pub_date = _date.fromisoformat(pub)
    age_days = (today - pub_date).days

    if age_days > MAX_AGE_YEARS * 365:
        return False
    if age_days <= RECENT_DAYS:
        return True

    # 3개월~3년: 검증된 것만
    if paper.get("study_type") in STRONG_TYPES:
        return True
    if (paper.get("citation_count") or 0) >= CITATION_THRESHOLD:
        return True
    return False


# ── 연구유형 판별 ────────────────────────────────────────────────
_META = ["meta-analysis", "meta analysis", "systematic review"]
_RCT = ["randomized controlled trial", "randomised controlled trial",
        "randomized clinical trial", "randomised clinical trial",
        "double-blind", "placebo-controlled", "rct"]

# 실험 연구임을 시사하는 신호들 (대폭 확장)
_EXPERIMENT_WORDS = [
    "randomized", "randomised", "randomly assigned", "randomly allocated",
    "control group", "control condition", "placebo", "double-blind", "double blind",
    "single-blind", "experimental group", "experimental condition",
    "participants were", "subjects were", "we recruited", "we conducted",
    "were assigned to", "intervention group", "treatment group",
    "pre-test", "post-test", "pretest", "posttest", "crossover",
    "we performed a", "in this experiment", "experimental design",
]

# 표본/통계 신호 (실험·정량연구의 강한 단서)
_QUANT_SIGNALS = [
    "participants", "subjects", "n =", "n=", "sample of", "p <", "p<",
    "p =", "p=", "confidence interval", "95% ci", "significant difference",
    "effect size", "cohen's d", "odds ratio", "regression",
]

_OBSERVATIONAL = ["cohort study", "case-control", "cross-sectional",
                  "longitudinal study", "observational study", "survey of"]


def classify_study_type(hints, abstract_en):
    """
    1) 출처가 준 유형 표시를 먼저 봄 (가장 정확).
    2) 없으면 초록에서 흔적을 찾음 (신호를 넓게 봄).
    """
    combined = " ".join(str(t).lower() for t in (hints or []) if t)

    # 1단계: 출처 표시
    if any(m in combined for m in _META):
        return "meta_analysis"
    if any(m in combined for m in _RCT):
        return "rct"

    # 2단계: 초록 분석
    if abstract_en and isinstance(abstract_en, str):
        text = abstract_en.lower()
        if any(m in text for m in _META):
            return "meta_analysis"
        if any(m in text for m in _RCT):
            return "rct"

        exp_hits = sum(1 for w in _EXPERIMENT_WORDS if w in text)
        quant_hits = sum(1 for w in _QUANT_SIGNALS if w in text)

        # 실험 신호 1개 + 정량 신호 1개, 또는 실험 신호 2개면 실험으로 추정
        if (exp_hits >= 1 and quant_hits >= 1) or exp_hits >= 2:
            return "experimental_likely"
        # 관찰연구 신호
        if any(m in text for m in _OBSERVATIONAL):
            return "observational"

    # 3단계: 유형 표시의 나머지
    if "review" in combined:
        return "review"
    if any(m in combined for m in ("editorial", "comment", "letter", "news")):
        return "other"
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
    "journal_name", "fulltext_url", "license",
]

_TYPE_STRENGTH = {
    "meta_analysis": 6, "rct": 5, "experimental_likely": 4,
    "observational": 3, "review": 2, "other": 1, "unclassified": 1, None: 0,
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
