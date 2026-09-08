"""Shared matching primitives for employer / course / military catalogues.

Keep mode-specific boosts in matching.py, courses.py, and military.py —
this module only holds the overlapping set/overlap math and catalogue base score.
"""

from __future__ import annotations

from typing import Any

import pandas as pd


# Split a pipe-separated cell into a set of tags.
def split_pipe(value: Any) -> set[str]:
    if value is None:
        return set()
    try:
        if pd.isna(value):
            return set()
    except (TypeError, ValueError):
        pass
    return {p.strip() for p in str(value).split("|") if p.strip()}


# Overlap score between two sets (0 if either empty).
def jaccard(a: set[str], b: set[str]) -> float:
    if not a or not b:
        return 0.0
    return len(a & b) / len(a | b)


# Jaccard overlap of word tokens from two text strings.
def token_overlap(a: str, b: str) -> float:
    ta = {
        t.lower()
        for t in a.replace("|", " ").replace(",", " ").split()
        if len(t) > 2
    }
    tb = {
        t.lower()
        for t in b.replace("|", " ").replace(",", " ").split()
        if len(t) > 2
    }
    return jaccard(ta, tb)


# Shared sector/entry/text/psych score pieces for catalogues.
def score_catalogue_components(
    leaver: dict[str, Any],
    *,
    item_sectors: set[str],
    item_routes: set[str],
    item_roles: set[str],
    profile_text_b: str,
    weights: dict[str, float],
    sector_interest_weight: float = 0.75,
    sector_psych_weight: float = 0.25,
    default_entry: float | None = None,
    psych_role_weight: float = 0.85,
) -> dict[str, float]:
    """Shared sector / entry / text / psych components + weighted final.

    Does not apply mode-specific boosts or soft-rejects.
    """
    interest_sectors = leaver.get("interest_sectors") or leaver["target_sectors"]
    psych_sectors = leaver.get("psych_sectors") or set()
    sector = sector_interest_weight * jaccard(
        interest_sectors, item_sectors
    ) + sector_psych_weight * jaccard(psych_sectors, item_sectors)

    if item_routes:
        entry = jaccard(leaver["entry_routes"], item_routes)
    elif default_entry is not None:
        entry = default_entry
    else:
        entry = jaccard(leaver["entry_routes"], item_routes)

    text = token_overlap(
        str(leaver.get("profile_text") or ""),
        profile_text_b,
    )
    psych_roles = set(leaver.get("psych", {}).get("role_prefs") or set())
    if psych_roles and item_roles:
        psych = psych_role_weight * jaccard(psych_roles, item_roles) + (
            1.0 - psych_role_weight
        ) * jaccard(psych_sectors, item_sectors)
    elif psych_roles or psych_sectors:
        psych = jaccard(
            psych_sectors | psych_roles,
            item_sectors | item_roles,
        )
    else:
        psych = 0.0

    final = (
        weights["sector"] * sector
        + weights["entry"] * entry
        + weights["text"] * text
        + weights["psych"] * psych
    )
    return {
        "final_score": final,
        "sector_score": sector,
        "entry_score": entry,
        "text_score": text,
        "psych_score": psych,
    }


# Round score fields to 4 decimal places for the API/UI.
def rounded_score_dict(scores: dict[str, float]) -> dict[str, float]:
    return {k: round(float(v), 4) for k, v in scores.items()}


# Back-compat aliases used historically as private matching helpers
_split_pipe = split_pipe
_jaccard = jaccard
_token_overlap = token_overlap
