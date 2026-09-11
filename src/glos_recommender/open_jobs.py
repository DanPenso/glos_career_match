"""Live 'Open jobs' flags from Reed Jobseeker API — decorate-only.

Does not drive the intake live-apprenticeship filter. Apprenticeship-titled
Reed rows are dropped so Find an apprenticeship keeps those matches.
"""

from __future__ import annotations

import base64
import json
import os
import re
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from .etl.vacancies import normalise_employer_name

PROJECT_ROOT = Path(__file__).resolve().parents[2]
LIVE_DIR = PROJECT_ROOT / "data" / "live"
CACHE_PATH = LIVE_DIR / "reed_jobs.json"

REED_SEARCH_URL = "https://www.reed.co.uk/api/1.0/search"
JOBS_OPEN_LABEL = "Open jobs"
JOBS_SOURCE = "reed_jobseeker"

_SEARCH_HUBS = (
    {"location": "Gloucester", "miles": 28},
    {"location": "Bristol", "miles": 18},
)
_PAGE_SIZE = 100
_MAX_PAGES_PER_QUERY = 8
_APPRENTICE_TITLE = re.compile(r"\bapprentice", re.I)
_NON_LOCAL_LOCATIONS = {
    "uk",
    "united kingdom",
    "great britain",
    "england",
    "nationwide",
    "national",
    "work from home",
    "working from home",
    "home based",
    "home-based",
    "remote",
    "anywhere",
}

_CLOSED_FIELDS = {
    "jobs_open_now": False,
    "jobs_open_label": "",
    "jobs_open_url": "",
    "jobs_open_count": 0,
    "jobs_open_as_of": None,
    "jobs_open_source": "",
    "jobs_open_titles": [],
}

_cache_memo: tuple[float, dict[str, Any]] | None = None


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _today() -> date:
    return _utc_now().date()


def _reed_api_key() -> str:
    return os.getenv("REED_API_KEY", "").strip()


def _cache_max_age_hours() -> float:
    raw = os.getenv("REED_CACHE_MAX_AGE_HOURS", "12").strip() or "12"
    try:
        return max(1.0, float(raw))
    except ValueError:
        return 12.0


def _allow_fetch() -> bool:
    if os.getenv("PYTEST_CURRENT_TEST"):
        return False
    flag = os.getenv("REED_REFRESH_ON_MATCH", "1").strip().lower()
    return flag not in {"0", "false", "no", "off"}


def closed_jobs_fields() -> dict[str, Any]:
    return dict(_CLOSED_FIELDS)


def _jobs_open_fields(
    *,
    url: str,
    count: int,
    as_of: str | None,
    titles: list[str],
) -> dict[str, Any]:
    if not url:
        return closed_jobs_fields()
    extra = [t for t in titles if t]
    return {
        "jobs_open_now": True,
        "jobs_open_label": JOBS_OPEN_LABEL,
        "jobs_open_url": url,
        "jobs_open_count": max(1, int(count or 1)),
        "jobs_open_as_of": as_of,
        "jobs_open_source": JOBS_SOURCE,
        "jobs_open_titles": extra[:6],
    }


def is_apprenticeship_title(title: Any) -> bool:
    return bool(_APPRENTICE_TITLE.search(str(title or "")))


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


def _parse_reed_date(value: Any) -> date | None:
    text = str(value or "").strip()
    if not text:
        return None
    iso = _parse_iso_datetime(text)
    if iso is not None:
        return iso.date()
    for fmt in ("%d/%m/%Y", "%d/%m/%Y %H:%M:%S", "%Y-%m-%d", "%Y-%m-%dT%H:%M:%S"):
        try:
            return datetime.strptime(text[:19] if len(text) > 10 else text, fmt).date()
        except ValueError:
            continue
    return None


def _job_still_open(item: dict[str, Any], today: date | None = None) -> bool:
    today = today or _today()
    expiry = _parse_reed_date(item.get("expiration_date") or item.get("expirationDate"))
    if expiry is not None and expiry < today:
        return False
    return True


def _location_is_local(location_name: Any) -> bool:
    name = str(location_name or "").strip().lower()
    if not name:
        return False
    return name not in _NON_LOCAL_LOCATIONS


def _job_url(raw: dict[str, Any], job_id: str) -> str:
    given = str(raw.get("jobUrl") or raw.get("job_url") or "").strip()
    if given.startswith("http") and "reed.co.uk" in given:
        return given
    if job_id:
        return f"https://www.reed.co.uk/jobs/{job_id}"
    return given if given.startswith("http") else ""


def slim_reed_job(raw: dict[str, Any]) -> dict[str, Any] | None:
    """Normalise one Reed search row; drop apprenticeships and unusable listings."""
    job_id = str(raw.get("jobId") or raw.get("job_id") or "").strip()
    if not job_id:
        return None
    title = str(raw.get("jobTitle") or raw.get("job_title") or raw.get("title") or "").strip()
    if not title or is_apprenticeship_title(title):
        return None
    employer = str(raw.get("employerName") or raw.get("employer_name") or "").strip()
    if not employer:
        return None
    location = str(raw.get("locationName") or raw.get("location_name") or "").strip()
    if not _location_is_local(location):
        return None
    url = _job_url(raw, job_id)
    if not url:
        return None
    expiry_raw = raw.get("expirationDate") or raw.get("expiration_date") or ""
    return {
        "job_id": job_id,
        "title": title,
        "employer_name": employer,
        "employer_key": normalise_employer_name(employer),
        "location_name": location,
        "expiration_date": str(expiry_raw),
        "job_url": url,
    }


def _basic_auth_header(api_key: str) -> str:
    token = base64.b64encode(f"{api_key}:".encode("utf-8")).decode("ascii")
    return f"Basic {token}"


def _http_json(url: str, headers: dict[str, str]) -> dict[str, Any]:
    req = Request(url, headers=headers)
    with urlopen(req, timeout=45) as resp:
        payload = json.loads(resp.read().decode("utf-8"))
    return payload if isinstance(payload, dict) else {}


def _search_queries() -> list[dict[str, str]]:
    queries: list[dict[str, str]] = []
    for hub in _SEARCH_HUBS:
        queries.append(
            {
                "locationName": hub["location"],
                "distanceFromLocation": str(hub["miles"]),
                "graduate": "true",
            }
        )
        queries.append(
            {
                "locationName": hub["location"],
                "distanceFromLocation": str(hub["miles"]),
                "postedByDirectEmployer": "true",
            }
        )
    return queries


def fetch_reed_jobs(*, api_key: str | None = None) -> dict[str, Any]:
    """Call Reed Jobseeker search for GL/BS live jobs and return a cache document."""
    key = (api_key if api_key is not None else _reed_api_key()).strip()
    if not key:
        raise RuntimeError(
            "Set REED_API_KEY to fetch live Reed job listings. "
            "If you just pasted the key, save .env and try again."
        )
    headers = {
        "Authorization": _basic_auth_header(key),
        "Accept": "application/json",
        "User-Agent": "MatchKite/1.0 (non-commercial demo; Gloucestershire careers matcher)",
    }
    by_id: dict[str, dict[str, Any]] = {}
    for extra in _search_queries():
        skip = 0
        total = None
        page = 0
        while page < _MAX_PAGES_PER_QUERY:
            params = {
                "resultsToTake": str(_PAGE_SIZE),
                "resultsToSkip": str(skip),
                **extra,
            }
            url = f"{REED_SEARCH_URL}?{urlencode(params)}"
            try:
                data = _http_json(url, headers)
            except HTTPError as exc:
                raise RuntimeError(f"Reed Jobseeker API returned HTTP {exc.code}.") from exc
            except URLError as exc:
                raise RuntimeError("Could not reach the Reed Jobseeker API.") from exc
            if total is None:
                total = int(data.get("totalResults") or 0)
            results = data.get("results") or []
            if not results:
                break
            for raw in results:
                if not isinstance(raw, dict):
                    continue
                slim = slim_reed_job(raw)
                if slim:
                    by_id[slim["job_id"]] = slim
            skip += _PAGE_SIZE
            page += 1
            if total is not None and skip >= total:
                break

    today = _today()
    jobs = [
        item
        for item in by_id.values()
        if _job_still_open(item, today) and item.get("employer_key")
    ]
    jobs.sort(key=lambda v: (v.get("employer_key") or "", v.get("title") or ""))
    return {
        "fetched_at": _utc_now().isoformat(),
        "source": JOBS_SOURCE,
        "jobs": jobs,
    }


def save_reed_jobs(doc: dict[str, Any], path: Path | None = None) -> Path:
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


def load_reed_jobs(
    *,
    path: Path | None = None,
    allow_fetch: bool | None = None,
) -> dict[str, Any]:
    """Load the local Reed cache, optionally refreshing when stale and a key is set."""
    dest = path or CACHE_PATH
    global _cache_memo
    mtime = dest.stat().st_mtime if dest.exists() else 0.0
    if _cache_memo and _cache_memo[0] == mtime:
        doc = _cache_memo[1]
    else:
        doc = _read_cache_file(dest) or {}
        _cache_memo = (mtime, doc)

    do_fetch = _allow_fetch() if allow_fetch is None else allow_fetch
    if do_fetch and not _cache_is_fresh(doc) and _reed_api_key():
        try:
            doc = fetch_reed_jobs()
            save_reed_jobs(doc, dest)
            mtime = dest.stat().st_mtime if dest.exists() else 0.0
            _cache_memo = (mtime, doc)
        except Exception:
            if not (doc.get("jobs") or []):
                raise
    return doc if doc else {"fetched_at": None, "source": JOBS_SOURCE, "jobs": []}


def _live_jobs(doc: dict[str, Any] | None, today: date | None = None) -> list[dict[str, Any]]:
    today = today or _today()
    out: list[dict[str, Any]] = []
    for item in (doc or {}).get("jobs") or []:
        if not isinstance(item, dict):
            continue
        if not _job_still_open(item, today):
            continue
        if is_apprenticeship_title(item.get("title")):
            continue
        row = dict(item)
        if not row.get("employer_key"):
            row["employer_key"] = normalise_employer_name(row.get("employer_name"))
        if row.get("employer_key") and row.get("job_url"):
            out.append(row)
    return out


def open_jobs_index(
    doc: dict[str, Any] | None = None,
) -> dict[str, list[dict[str, Any]]]:
    grouped: dict[str, list[dict[str, Any]]] = {}
    as_of = str((doc or {}).get("fetched_at") or "")
    for item in _live_jobs(doc):
        key = str(item.get("employer_key") or "")
        if not key:
            continue
        row = dict(item)
        row["fetched_at"] = as_of
        grouped.setdefault(key, []).append(row)
    return grouped


def open_fields_for_employer_jobs(
    name: Any,
    *,
    index: dict[str, list[dict[str, Any]]] | None = None,
) -> dict[str, Any]:
    grouped = index if index is not None else open_jobs_index(
        load_reed_jobs(allow_fetch=False)
    )
    key = normalise_employer_name(name)
    rows = grouped.get(key) or []
    if not rows:
        return closed_jobs_fields()
    first = rows[0]
    titles = [str(r.get("title") or "").strip() for r in rows]
    return _jobs_open_fields(
        url=str(first.get("job_url") or ""),
        count=len(rows),
        as_of=str(first.get("fetched_at") or ""),
        titles=titles,
    )
