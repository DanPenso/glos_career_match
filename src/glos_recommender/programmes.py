"""Curated verified employer programmes for briefing copy.

Only programmes in data/seed/verified_programmes.csv with confidence=verified,
status active/seasonal, fresh last_verified_at, and an evidence_url are shown
in the "Roles and programmes you could work towards" briefing section.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from functools import lru_cache
from pathlib import Path
from typing import Any

import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[2]
SEED_DIR = PROJECT_ROOT / "data" / "seed"
VERIFIED_PATH = SEED_DIR / "verified_programmes.csv"

CONFIDENCE_OK = {"verified"}
STATUS_OK = {"active", "seasonal"}
FRESHNESS_DAYS = 180
MAX_PROGRAMMES = 4


def _parse_date(value: Any) -> datetime | None:
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return None
    text = str(value).strip()
    if not text:
        return None
    try:
        dt = pd.to_datetime(text, utc=True)
        if pd.isna(dt):
            return None
        return dt.to_pydatetime()
    except (TypeError, ValueError):
        return None


def _is_fresh(last_verified: datetime | None, *, now: datetime | None = None) -> bool:
    if last_verified is None:
        return False
    ref = now or datetime.now(timezone.utc)
    if last_verified.tzinfo is None:
        last_verified = last_verified.replace(tzinfo=timezone.utc)
    return last_verified >= ref - timedelta(days=FRESHNESS_DAYS)


@lru_cache(maxsize=1)
def load_verified_programmes(path: Path | None = None) -> pd.DataFrame:
    csv_path = path or VERIFIED_PATH
    if not csv_path.exists():
        return pd.DataFrame()
    return pd.read_csv(csv_path)


def clear_programmes_cache() -> None:
    load_verified_programmes.cache_clear()


def validate_programmes(df: pd.DataFrame | None = None) -> list[str]:
    """Return human-readable validation warnings for maintainers."""
    data = df if df is not None else load_verified_programmes()
    warnings: list[str] = []
    if data.empty:
        warnings.append("verified_programmes.csv is missing or empty.")
        return warnings

    required = {
        "programme_id",
        "company_id",
        "programme_title",
        "programme_type",
        "evidence_url",
        "last_verified_at",
        "status",
        "confidence",
    }
    missing = required - set(data.columns)
    if missing:
        warnings.append(f"Missing columns: {', '.join(sorted(missing))}")
        return warnings

    for _, row in data.iterrows():
        pid = str(row.get("programme_id") or "?")
        conf = str(row.get("confidence") or "").strip().lower()
        status = str(row.get("status") or "").strip().lower()
        url = str(row.get("evidence_url") or "").strip()
        verified = _parse_date(row.get("last_verified_at"))

        if conf not in CONFIDENCE_OK:
            warnings.append(f"{pid}: confidence must be 'verified' (got {conf!r})")
        if status not in STATUS_OK:
            warnings.append(f"{pid}: status must be active/seasonal (got {status!r})")
        if not url.startswith("http"):
            warnings.append(f"{pid}: evidence_url must be an http(s) URL")
        if not _is_fresh(verified):
            warnings.append(f"{pid}: last_verified_at is missing or older than {FRESHNESS_DAYS} days")
    return warnings


def programmes_for_company(
    company_id: str,
    *,
    programmes: pd.DataFrame | None = None,
    max_items: int = MAX_PROGRAMMES,
) -> list[dict[str, Any]]:
    """Return display-ready verified programmes for one employer."""
    df = programmes if programmes is not None else load_verified_programmes()
    if df.empty or not company_id:
        return []

    subset = df[df["company_id"].astype(str) == str(company_id)]
    rows: list[dict[str, Any]] = []
    for _, row in subset.iterrows():
        conf = str(row.get("confidence") or "").strip().lower()
        status = str(row.get("status") or "").strip().lower()
        url = str(row.get("evidence_url") or "").strip()
        verified = _parse_date(row.get("last_verified_at"))
        if conf not in CONFIDENCE_OK:
            continue
        if status not in STATUS_OK:
            continue
        if not url.startswith("http"):
            continue
        if not _is_fresh(verified):
            continue
        rows.append(
            {
                "programme_id": str(row.get("programme_id") or ""),
                "programme_title": str(row.get("programme_title") or "").strip(),
                "programme_type": str(row.get("programme_type") or "").strip(),
                "level": str(row.get("level") or "").strip(),
                "summary": str(row.get("summary") or "").strip(),
                "evidence_url": url,
            }
        )

    return rows[:max_items]


def format_programmes_for_prompt(programmes: list[dict[str, Any]]) -> str:
    if not programmes:
        return (
            "No recently verified programmes listed for this employer. "
            "Direct the leaver to the official careers page only."
        )
    lines: list[str] = []
    for p in programmes:
        bits = [p["programme_title"]]
        if p.get("programme_type"):
            bits.append(f"type: {p['programme_type']}")
        if p.get("level"):
            bits.append(f"level: {p['level']}")
        if p.get("summary"):
            bits.append(p["summary"])
        if p.get("evidence_url"):
            bits.append(f"Source: {p['evidence_url']}")
        lines.append("- " + " | ".join(bits))
    return "\n".join(lines)


def format_programmes_for_briefing(programmes: list[dict[str, Any]]) -> list[str]:
    """Plain lines for offline briefing markdown."""
    if not programmes:
        return [
            "No recently verified programmes are listed for this employer.",
            "Check their official careers page for current openings.",
        ]
    lines: list[str] = []
    for p in programmes:
        title = p.get("programme_title") or "Programme"
        route = p.get("programme_type") or ""
        level = p.get("level") or ""
        meta = " · ".join(x for x in (route, level) if x)
        summary = str(p.get("summary") or "").strip()
        if len(summary) > 120:
            summary = summary[:117].rstrip() + "…"
        line = f"{title} ({meta}): {summary}" if meta else f"{title}: {summary}"
        lines.append(line.strip(" :"))
    return lines
