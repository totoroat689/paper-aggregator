"""
Europe PMC에서 논문을 가져오는 파일.
키가 필요 없는 출처입니다.
"""

import re
import time
from datetime import date, timedelta

import requests

BASE_URL = "https://www.ebi.ac.uk/europepmc/webservices/rest/search"


def fetch_recent(days_back=3, page_size=100, max_pages=5):
    """최근 N일 동안 나온 논문을 폭넓게 가져옵니다 (주제로 좁히지 않음)."""
    start_date = (date.today() - timedelta(days=days_back)).isoformat()
    end_date = date.today().isoformat()
    query = f"FIRST_PDATE:[{start_date} TO {end_date}]"

    results = []
    cursor_mark = "*"

    for _ in range(max_pages):
        params = {
            "query": query,
            "format": "json",
            "resultType": "core",
            "pageSize": page_size,
            "cursorMark": cursor_mark,
        }
        resp = requests.get(BASE_URL, params=params, timeout=30)
        resp.raise_for_status()
        data = resp.json()

        page_results = data.get("resultList", {}).get("result", [])
        results.extend(page_results)

        next_cursor = data.get("nextCursorMark")
        if not next_cursor or next_cursor == cursor_mark or not page_results:
            break
        cursor_mark = next_cursor
        time.sleep(0.5)

    return results


def normalize(raw):
    """원본 논문 데이터를 우리 공통 양식으로 바꿉니다."""
    pub_types = raw.get("pubTypeList", {}).get("pubType", [])

    return {
        "doi_raw": raw.get("doi"),
        "pmid": raw.get("pmid"),
        "title_en": (raw.get("title") or "").rstrip("."),
        "abstract_en": _strip_html_tags(raw.get("abstractText")),
        "authors": [{"name": a.get("fullName")} for a in raw.get("authorList", {}).get("author", [])],
        "countries": [],
        "publication_year": _safe_int(raw.get("pubYear")),
        "publication_date": raw.get("firstPublicationDate"),
        "source_indexed_date": raw.get("firstIndexDate"),
        "study_type_hint": pub_types,
        "is_retracted": _has_retraction_notice(raw),
        "citation_count": raw.get("citedByCount", 0) or 0,
        "primary_category": None,
        "journal_name": (raw.get("journalInfo", {}).get("journal") or {}).get("title"),
        "is_open_access": raw.get("isOpenAccess") == "Y",
        "fulltext_url": _best_fulltext_url(raw),
        "source": "europepmc",
        "source_id": raw.get("id"),
        "raw_data": raw,
    }


def _strip_html_tags(text):
    """초록에 섞인 <h4> 같은 표시를 없애서 읽기 좋게 만듭니다."""
    if not text:
        return None
    text = re.sub(r"<h4>", "\n\n", text)
    text = re.sub(r"</h4>", ": ", text)
    text = re.sub(r"<[^>]+>", "", text)
    return text.strip()


def _has_retraction_notice(raw):
    for c in raw.get("commentCorrectionList", {}).get("commentCorrection", []):
        if "retraction" in (c.get("type") or "").lower():
            return True
    return False


def _best_fulltext_url(raw):
    urls = raw.get("fullTextUrlList", {}).get("fullTextUrl", [])
    for u in urls:
        if u.get("availabilityCode") in ("F", "OA"):
            return u.get("url")
    if urls:
        return urls[0].get("url")
    doi = raw.get("doi")
    return f"https://doi.org/{doi}" if doi else None


def _safe_int(v):
    try:
        return int(v)
    except (TypeError, ValueError):
        return None
