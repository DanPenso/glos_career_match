"""Shared presentation labels for match fit / hiring signals."""

from __future__ import annotations

import re
from typing import Any


_SIC_CODE_PREFIX = re.compile(r"^\d{4,5}\s*[-–—]\s*")

# Companies House / registry pages are not employer websites.
_REGISTRY_HOST_HINTS = (
    "company-information.service.gov.uk",
    "find-and-update.company-information",
    "companieshouse.gov.uk",
    "companieshouse.gov",
)


# True when URL is a Companies House / registry page (not a careers site).
def is_registry_website(url: Any) -> bool:
    u = str(url or "").strip().lower()
    if not u:
        return False
    return any(h in u for h in _REGISTRY_HOST_HINTS)


# Public employer homepage only — blank if missing or registry-only.
def public_employer_website(url: Any) -> str:
    u = str(url or "").strip()
    if not u or is_registry_website(u):
        return ""
    if not u.lower().startswith(("http://", "https://")):
        return ""
    return u


# Short activity label from SIC text.
def sic_activity(text: str) -> str:
    return _SIC_CODE_PREFIX.sub("", str(text or "").strip()).strip().rstrip(".")


# Clean Companies House-style summary text for UI.
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


# Traffic-light style fit label from a 0–1 score.
def fit_label(score: float) -> str:
    s = float(score)
    if s >= 0.55:
        return "Strong"
    if s >= 0.30:
        return "Good"
    return "Worth exploring"


# Public hiring label — matcher tags are not live vacancies.
def hiring_label(row: dict[str, Any]) -> str:
    """Do not claim an employer is hiring from seed / vacancy matcher tags."""
    _ = row
    return "Check current openings"


# Rank label for match position (e.g. Strong match).
def overall_label(rank: int) -> str:
    if rank == 0:
        return "Your strongest match"
    if rank == 1:
        return "A strong option"
    return "Also worth a look"
