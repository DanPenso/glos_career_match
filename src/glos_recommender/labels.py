"""Shared presentation labels for match fit / hiring signals."""

from __future__ import annotations

import re
from typing import Any


_SIC_CODE_PREFIX = re.compile(r"^\d{4,5}\s*[-–—]\s*")


def sic_activity(text: str) -> str:
    return _SIC_CODE_PREFIX.sub("", str(text or "").strip()).strip().rstrip(".")


def clean_company_summary(text: Any) -> str:
    """Turn Companies House boilerplate into leaver-friendly employer blurbs."""
    s = " ".join(str(text or "").split())
    if not s:
        return ""

    if "companies house" not in s.lower() and "nature of business" not in s.lower():
        return s

    activity = ""
    sic_match = re.search(
        r"Nature of business\s*\(SIC\)\s*:\s*(.+?)(?:\.\s*(?:Leaver|Routes)|\.\s*$)",
        s,
        re.I,
    )
    if sic_match:
        activity = sic_activity(sic_match.group(1))

    town_match = re.search(r"registered office in ([^.(]+)", s, re.I)
    town = town_match.group(1).strip() if town_match else ""

    if activity and activity.lower() not in ("see companies house record",):
        lead = f"{town}-based employer" if town else "Gloucestershire employer"
        return (
            f"{lead} working in {activity.lower()}. "
            "Routes vary — check their careers page and Find an Apprenticeship."
        )

    s = re.sub(r"Nature of business\s*\(SIC\)\s*:[^.]*\.?\s*", "", s, flags=re.I)
    s = re.sub(r"SIC\s*[:\-]\s*[^.]*\.?\s*", "", s, flags=re.I)
    s = re.sub(r"\(accounts?\s+category:[^)]+\)", "", s, flags=re.I)
    s = re.sub(r"accounts?\s+category\s*[:\-]\s*[^.]*\.?\s*", "", s, flags=re.I)
    s = re.sub(r"registered office in [^.]*\.?\s*", "", s, flags=re.I)
    s = re.sub(r"Companies House[–-]listed employer(?: with)?\.?\s*", "", s, flags=re.I)
    s = re.sub(r"^\s*with\s+", "", s, flags=re.I)
    s = re.sub(r"\s{2,}", " ", s).strip(" .")
    if town and len(s) < 40:
        return (
            f"{town}-based employer. "
            "Routes vary — check their careers page and Find an Apprenticeship."
        )
    return s or (
        f"{town}-based employer. "
        "Routes vary — check their careers page and Find an Apprenticeship."
        if town
        else "Local Gloucestershire employer — check careers pages and Find an Apprenticeship."
    )


def fit_label(score: float) -> str:
    s = float(score)
    if s >= 0.55:
        return "Strong"
    if s >= 0.30:
        return "Good"
    return "Worth exploring"


def hiring_label(row: dict[str, Any]) -> str:
    signal = str(row.get("hiring_signal", "")).strip().lower()
    if signal == "high" or float(row.get("hiring_score", 0) or 0) >= 0.85:
        return "Often hiring"
    if signal == "medium" or float(row.get("hiring_score", 0) or 0) >= 0.5:
        return "Sometimes hiring"
    return "Check current openings"


def overall_label(rank: int) -> str:
    if rank == 0:
        return "Your strongest match"
    if rank == 1:
        return "A strong option"
    return "Also worth a look"
