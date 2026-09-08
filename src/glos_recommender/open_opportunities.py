"""Live 'Open opportunities' flags from official catalogues — not EES history.

Work: DfE Display Advert API v2 (Find an apprenticeship), cached locally.
Education: National Careers Service live course directory fields on the seed.
Military: no official open-roles feed — never flagged.
"""

from __future__ import annotations

import json
import os
import re
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

import pandas as pd

from .etl.vacancies import normalise_employer_name

PROJECT_ROOT = Path(__file__).resolve().parents[2]
LIVE_DIR = PROJECT_ROOT / "data" / "live"
CACHE_PATH = LIVE_DIR / "open_apprenticeships.json"

FAA_VACANCY_URL = "https://www.findapprenticeship.service.gov.uk/apprenticeship/{ref}"
FAA_API_BASE = "https://api.apprenticeships.education.gov.uk/vacancies/vacancy"
FIND_A_COURSE_URL = (
    "https://nationalcareers.service.gov.uk/find-a-course/course-details"
    "?courseId={course_id}&runId={run_id}"
)

OPEN_LABEL = "Open opportunities"
WORK_SOURCE = "faa_display_advert"
EDU_SOURCE = "ncs_live_directory"

# NCS monthly file is "live" at publication; after this many days, don't infer Open
# from source_date alone (need start_date / flexible_start).
NCS_SNAPSHOT_MAX_AGE_DAYS = 45

# Gloucester + Bristol hubs (Display Advert lat/lon radius search).
_SEARCH_HUBS = (
    {"lat": 51.866, "lon": -2.248, "miles": 28},  # Gloucester / county
    {"lat": 51.4545, "lon": -2.5879, "miles": 18},  # Bristol
)

_CLOSED_FIELDS = {
    "open_now": False,
    "open_label": "",
    "open_url": "",
    "open_count": 0,
    "open_as_of": None,
    "open_source": "",
    "open_titles": [],
}

_cache_memo: tuple[float, dict[str, Any]] | None = None


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _today() -> date:
    return _utc_now().date()


def _parse_iso_datetime(value: Any) -> datetime | None:
    text = str(value or "").strip()
    if not text:
        return None
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    try:
        parsed = datetime.fromisoformat(text)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed


def _parse_ncs_date(value: Any) -> date | None:
    text = str(value or "").strip()
    if not text:
        return None
    for fmt in ("%Y-%m-%d", "%d/%m/%Y", "%d-%m-%Y", "%Y/%m/%d"):
        try:
            return datetime.strptime(text[:10], fmt).date()
        except ValueError:
            continue
    return None


def _truthy(value: Any) -> bool:
    return str(value or "").strip().lower() in {"1", "true", "yes", "y"}


def _local_postcode(postcode: Any) -> bool:
    compact = re.sub(r"\s+", "", str(postcode or "")).upper()
    return compact.startswith("GL") or compact.startswith("BS")


def _api_key() -> str:
    return (
        os.getenv("FAA_DISPLAY_API_KEY", "").strip()
        or os.getenv("APPRENTICESHIP_DISPLAY_API_KEY", "").strip()
    )


def _cache_max_age_hours() -> float:
    raw = os.getenv("FAA_CACHE_MAX_AGE_HOURS", "12").strip() or "12"
    try:
        return max(1.0, float(raw))
    except ValueError:
        return 12.0


def _allow_fetch() -> bool:
    if os.getenv("PYTEST_CURRENT_TEST"):
        return False
    flag = os.getenv("FAA_REFRESH_ON_MATCH", "1").strip().lower()
    return flag not in {"0", "false", "no", "off"}


def closed_open_fields() -> dict[str, Any]:
    return dict(_CLOSED_FIELDS)


def _open_fields(
    *,
    url: str,
    count: int,
    as_of: str | None,
    source: str,
    titles: list[str],
) -> dict[str, Any]:
    if not url:
        return closed_open_fields()
    extra = [t for t in titles if t]
    return {
        "open_now": True,
        "open_label": OPEN_LABEL,
        "open_url": url,
        "open_count": max(1, int(count or 1)),
        "open_as_of": as_of,
        "open_source": source,
        "open_titles": extra[:6],
    }


def vacancy_page_url(vacancy_reference: Any, vacancy_url: Any = "") -> str:
    given = str(vacancy_url or "").strip()
    if given.startswith("http") and "findapprenticeship.service.gov.uk" in given:
        return given
    ref = str(vacancy_reference or "").strip().lstrip("#")
    if not ref:
        return given if given.startswith("http") else ""
    return FAA_VACANCY_URL.format(ref=ref)


def _vacancy_still_open(item: dict[str, Any], today: date | None = None) -> bool:
    today = today or _today()
    closing = _parse_iso_datetime(item.get("closing_date") or item.get("closingDate"))
    if closing is not None and closing.date() < today:
        return False
    return True


def _slim_vacancy(raw: dict[str, Any]) -> dict[str, Any] | None:
    ref = str(raw.get("vacancyReference") or "").strip()
    if not ref:
        return None
    if raw.get("isNationalVacancy"):
        return None
    addresses = raw.get("addresses") or []
    postcode = ""
    for addr in addresses:
        if not isinstance(addr, dict):
            continue
        pc = str(addr.get("postcode") or "").strip()
        if _local_postcode(pc):
            postcode = pc
            break
        if pc and not postcode:
            postcode = pc
    if postcode and not _local_postcode(postcode):
        return None
    if not postcode:
        return None
    employer = str(raw.get("employerName") or "").strip()
    if not employer:
        return None
    course = raw.get("course") if isinstance(raw.get("course"), dict) else {}
    title = str(raw.get("title") or "").strip()
    course_title = str(course.get("title") or "").strip()
    return {
        "vacancy_reference": ref,
        "title": title,
        "course_title": course_title,
        "employer_name": employer,
        "employer_key": normalise_employer_name(employer),
        "postcode": postcode,
        "closing_date": str(raw.get("closingDate") or ""),
        "start_date": str(raw.get("startDate") or ""),
        "vacancy_url": vacancy_page_url(ref, raw.get("vacancyUrl")),
    }


def _http_json(url: str, headers: dict[str, str]) -> dict[str, Any]:
    req = Request(url, headers=headers)
    with urlopen(req, timeout=45) as resp:
        payload = json.loads(resp.read().decode("utf-8"))
    return payload if isinstance(payload, dict) else {}


def fetch_open_apprenticeships(*, api_key: str | None = None) -> dict[str, Any]:
    """Call Display Advert API v2 for GL/BS live adverts and return a cache document."""
    key = (api_key if api_key is not None else _api_key()).strip()
    if not key:
        raise RuntimeError(
            "Set FAA_DISPLAY_API_KEY to fetch live Find an apprenticeship adverts."
        )
    headers = {
        "Ocp-Apim-Subscription-Key": key,
        "X-Version": "2",
        "Accept": "application/json",
        # Default Python-urllib UA is blocked by the gateway (HTTP 403 HTML).
        "User-Agent": "MatchKite/1.0 (non-commercial demo; Gloucestershire careers matcher)",
    }
    by_ref: dict[str, dict[str, Any]] = {}
    for hub in _SEARCH_HUBS:
        page = 1
        total_pages = 1
        while page <= total_pages and page <= 40:
            query = urlencode(
                {
                    "Lat": hub["lat"],
                    "Lon": hub["lon"],
                    "DistanceInMiles": hub["miles"],
                    "PageNumber": page,
                    "PageSize": 100,
                    "Sort": "AgeDesc",
                    "ExcludeRecruitingNationally": "true",
                    "IncludeDetails": "false",
                }
            )
            url = f"{FAA_API_BASE}?{query}"
            try:
                data = _http_json(url, headers)
            except HTTPError as exc:
                hint = ""
                try:
                    raw = exc.read().decode("utf-8", errors="replace")[:200]
                    if "unavailable" in raw.lower():
                        hint = " Gateway blocked the request (try a non-default User-Agent)."
                except Exception:
                    hint = ""
                raise RuntimeError(
                    f"Display Advert API returned HTTP {exc.code}.{hint}"
                ) from exc
            except URLError as exc:
                raise RuntimeError("Could not reach the Display Advert API.") from exc
            total_pages = int(data.get("totalPages") or 1)
            for raw in data.get("vacancies") or []:
                if not isinstance(raw, dict):
                    continue
                slim = _slim_vacancy(raw)
                if slim:
                    by_ref[slim["vacancy_reference"]] = slim
            page += 1

    today = _today()
    vacancies = [
        item
        for item in by_ref.values()
        if _vacancy_still_open(item, today) and item.get("employer_key")
    ]
    vacancies.sort(key=lambda v: (v.get("employer_key") or "", v.get("title") or ""))
    return {
        "fetched_at": _utc_now().isoformat(),
        "source": WORK_SOURCE,
        "vacancies": vacancies,
    }


def save_open_apprenticeships(doc: dict[str, Any], path: Path | None = None) -> Path:
    dest = path or CACHE_PATH
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(json.dumps(doc, indent=2), encoding="utf-8")
    global _cache_memo
    _cache_memo = None
    return dest


def _read_cache_file(path: Path) -> dict[str, Any] | None:
    if not path.exists():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    return data if isinstance(data, dict) else None


def _cache_is_fresh(doc: dict[str, Any] | None) -> bool:
    if not doc:
        return False
    fetched = _parse_iso_datetime(doc.get("fetched_at"))
    if fetched is None:
        return False
    age_hours = (_utc_now() - fetched).total_seconds() / 3600.0
    return age_hours <= _cache_max_age_hours()


def load_open_apprenticeships(
    *,
    path: Path | None = None,
    allow_fetch: bool | None = None,
) -> dict[str, Any]:
    """Load the local FAA cache, optionally refreshing when stale and a key is set."""
    dest = path or CACHE_PATH
    global _cache_memo
    mtime = dest.stat().st_mtime if dest.exists() else 0.0
    if _cache_memo and _cache_memo[0] == mtime:
        doc = _cache_memo[1]
    else:
        doc = _read_cache_file(dest) or {}
        _cache_memo = (mtime, doc)

    do_fetch = _allow_fetch() if allow_fetch is None else allow_fetch
    if do_fetch and not _cache_is_fresh(doc) and _api_key():
        try:
            doc = fetch_open_apprenticeships()
            save_open_apprenticeships(doc, dest)
            mtime = dest.stat().st_mtime if dest.exists() else 0.0
            _cache_memo = (mtime, doc)
        except Exception:
            if not (doc.get("vacancies") or []):
                raise
    return doc if doc else {"fetched_at": None, "source": WORK_SOURCE, "vacancies": []}


def _live_vacancies(doc: dict[str, Any] | None, today: date | None = None) -> list[dict[str, Any]]:
    today = today or _today()
    out: list[dict[str, Any]] = []
    for item in (doc or {}).get("vacancies") or []:
        if not isinstance(item, dict):
            continue
        if not _vacancy_still_open(item, today):
            continue
        if not item.get("employer_key"):
            item = dict(item)
            item["employer_key"] = normalise_employer_name(item.get("employer_name"))
        if item.get("employer_key") and item.get("vacancy_url"):
            out.append(item)
    return out


def open_apprenticeship_index(
    doc: dict[str, Any] | None = None,
) -> dict[str, list[dict[str, Any]]]:
    grouped: dict[str, list[dict[str, Any]]] = {}
    as_of = str((doc or {}).get("fetched_at") or "")
    for item in _live_vacancies(doc):
        key = str(item.get("employer_key") or "")
        if not key:
            continue
        row = dict(item)
        row["fetched_at"] = as_of
        grouped.setdefault(key, []).append(row)
    return grouped


def cache_has_open_apprenticeships(doc: dict[str, Any] | None = None) -> bool:
    try:
        payload = doc if doc is not None else load_open_apprenticeships(allow_fetch=False)
    except Exception:
        payload = {}
    return bool(_live_vacancies(payload))


def open_fields_for_employer(
    name: Any,
    *,
    index: dict[str, list[dict[str, Any]]] | None = None,
) -> dict[str, Any]:
    grouped = index if index is not None else open_apprenticeship_index(
        load_open_apprenticeships(allow_fetch=False)
    )
    key = normalise_employer_name(name)
    rows = grouped.get(key) or []
    if not rows:
        return closed_open_fields()
    first = rows[0]
    titles = [str(r.get("title") or "").strip() for r in rows]
    return _open_fields(
        url=str(first.get("vacancy_url") or ""),
        count=len(rows),
        as_of=str(first.get("fetched_at") or ""),
        source=WORK_SOURCE,
        titles=titles,
    )


def filter_employers_with_open(
    companies: pd.DataFrame,
    *,
    index: dict[str, list[dict[str, Any]]] | None = None,
) -> pd.DataFrame:
    if companies is None or companies.empty:
        return companies
    grouped = index if index is not None else open_apprenticeship_index(
        load_open_apprenticeships(allow_fetch=False)
    )
    keys = set(grouped)
    if not keys or "name" not in companies.columns:
        return companies.iloc[0:0].copy()
    mask = companies["name"].map(normalise_employer_name).isin(keys)
    return companies.loc[mask].copy()


def _ncs_source_date(row: dict[str, Any]) -> date | None:
    raw = str(row.get("source_date") or "").strip()
    if not raw:
        return None
    if re.fullmatch(r"\d{4}-\d{2}$", raw):
        return _parse_ncs_date(raw + "-01")
    return _parse_ncs_date(raw)


def course_is_open(row: dict[str, Any] | None, *, today: date | None = None) -> bool:
    """True when this NCS row is listed as a live course run we can link to."""
    today = today or _today()
    data = row or {}
    src = str(data.get("source") or "").strip().lower()
    if src not in {"ncs", "ncs_course_directory", "catalogue", "national_careers", "dfe"}:
        return False
    website = str(data.get("website") or "").strip()
    run_id = str(data.get("course_run_id") or "").strip()
    course_id = str(data.get("course_id") or "").strip()
    has_link = website.startswith("http") or bool(run_id and course_id)
    if not has_link:
        return False
    if _truthy(data.get("flexible_start") or data.get("FLEXIBLE_STARTDATE")):
        return True
    start = _parse_ncs_date(data.get("start_date") or data.get("STARTDATE"))
    if start is not None:
        return start >= today
    published = _ncs_source_date(data)
    if published is None:
        return False
    return (today - published).days <= NCS_SNAPSHOT_MAX_AGE_DAYS


def course_open_url(row: dict[str, Any] | None) -> str:
    data = row or {}
    website = str(data.get("website") or "").strip()
    if website.startswith("http"):
        return website
    raw_id = str(data.get("course_id") or "")
    run_id = str(data.get("course_run_id") or "").strip()
    ncs_id = raw_id
    if raw_id.startswith("NCS-"):
        parts = raw_id.split("-", 2)
        if len(parts) == 3:
            ncs_id = parts[2]
    if ncs_id and run_id:
        return FIND_A_COURSE_URL.format(course_id=ncs_id, run_id=run_id)
    return ""


def open_fields_for_course(row: dict[str, Any] | None) -> dict[str, Any]:
    data = row or {}
    if not course_is_open(data):
        return closed_open_fields()
    url = course_open_url(data)
    as_of = str(data.get("source_date") or "")
    title = str(data.get("title") or data.get("name") or "").strip()
    return _open_fields(
        url=url,
        count=1,
        as_of=as_of,
        source=EDU_SOURCE,
        titles=[title] if title else [],
    )


def filter_courses_with_open(courses: pd.DataFrame) -> pd.DataFrame:
    if courses is None or courses.empty:
        return courses
    mask = courses.apply(lambda r: course_is_open(r.to_dict()), axis=1)
    return courses.loc[mask].copy()


def open_fields_for_military(_row: dict[str, Any] | None = None) -> dict[str, Any]:
    return closed_open_fields()


def work_open_unavailable_detail() -> str:
    if not _api_key() and not cache_has_open_apprenticeships():
        return (
            "Live apprenticeship listings are not loaded yet. Untick "
            "“Only show options with live apprenticeship opportunities” to see work matches."
        )
    return (
        "No local employers in our directory currently have an open apprenticeship "
        "on Find an apprenticeship. Untick “Only show options with live apprenticeship opportunities” "
        "to see other work matches."
    )


def education_open_unavailable_detail() -> str:
    return (
        "No courses currently count as open to apply. Untick "
        "“Only show options with live apprenticeship opportunities” to see all course matches."
    )


def military_open_unsupported_detail() -> str:
    return (
        "Military pathways do not have an official live-opportunities list. "
        "Untick “Only show options with live apprenticeship opportunities”, or choose work or education."
    )
