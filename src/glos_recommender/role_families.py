"""Infer employer-aligned role_families for courses and military pathways.

Psych scoring in matching.py uses role prefs from RIASEC
(technician, cyber, care, …). Courses/military historically lacked those
tags, so psych collapsed to sector Jaccard. This module maps titles,
sectors, and military role labels onto the same vocabulary.
"""

from __future__ import annotations

import re
from typing import Any

# Title / summary keywords → employer role_families vocabulary
_TITLE_ROLE_RULES: list[tuple[re.Pattern[str], list[str]]] = [
    (re.compile(r"\b(cyber|security|SOC|network.?secur)\b", re.I), ["cyber"]),
    (re.compile(r"\b(software|programming|coding|developer|web.?dev|app.?dev)\b", re.I), ["software"]),
    (re.compile(r"\b(data.?science|data.?analy|analytics|statistics|AI\b|machine.?learning)\b", re.I), ["data", "analyst"]),
    (re.compile(r"\b(IT support|ICT|computer|computing|digital)\b", re.I), ["software", "technician"]),
    (re.compile(r"\b(nurs|midwif|paramedic|care\b|social care|health.?care|physiotherap|dental|wellbeing)\b", re.I), ["care"]),
    (re.compile(r"\b(teach(?:ing|er)?|early.?year|childcare|learning.?support|teaching.?assistant|PGCE|QTS|trainee.?teacher)\b", re.I), ["teaching_support"]),
    (re.compile(r"\b(account|AAT|financ|bookkeep)\b", re.I), ["finance", "admin"]),
    (re.compile(r"\b(business|management|HR\b|admin|office)\b", re.I), ["admin", "project_support"]),
    (re.compile(r"\b(market|sales|retail|customer.?service)\b", re.I), ["sales", "customer_success"]),
    (re.compile(r"\b(engineer|mechanical|electrical|mechatronic|CNC|aerospace|manufactur)\b", re.I), ["engineer_ops", "technician", "manufacturing"]),
    (re.compile(r"\b(construct|plumb|brick|carpentr|electrician|survey)\b", re.I), ["technician", "field_ops"]),
    (re.compile(r"\b(design|creative|media|art\b|film|photography|ux)\b", re.I), ["design", "content"]),
    (re.compile(r"\b(event|hospitality|tourism|chef|cater|hotel)\b", re.I), ["events", "customer_success"]),
    (re.compile(r"\b(agricultur|horticultur|animal|veterinary|land-based|forestry)\b", re.I), ["field_ops", "technician"]),
    (re.compile(r"\b(logistics|HGV|LGV|warehouse|supply.?chain|transport)\b", re.I), ["field_ops", "ops"]),
    (re.compile(r"\b(lab|science|research|biology|chemistry|physics)\b", re.I), ["research_lab", "analyst"]),
    (re.compile(r"\b(project|coordinator|operations)\b", re.I), ["project_coord", "ops"]),
    (re.compile(r"\b(quality|compliance|audit)\b", re.I), ["quality", "compliance"]),
]

# Sector tags → default role families when title rules miss
_SECTOR_ROLES: dict[str, list[str]] = {
    "cyber_digital": ["cyber", "software", "analyst"],
    "aerospace_manufacturing": ["engineer_ops", "technician", "manufacturing"],
    "health_care": ["care"],
    "education_training": ["teaching_support"],
    "business_professional": ["admin", "finance", "project_support"],
    "creative_events": ["design", "content", "events"],
    "construction_green": ["technician", "field_ops"],
    "hospitality_tourism": ["events", "customer_success"],
    "hospitality_retail": ["sales", "customer_success"],
    "agri_tech_food": ["field_ops", "technician"],
    "public_sector": ["admin", "care", "project_support"],
}

# Military seed role_family labels → employer vocabulary
_MILITARY_ROLE_MAP: dict[str, list[str]] = {
    "cyber_digital": ["cyber", "software", "analyst"],
    "engineer_ops": ["engineer_ops", "technician"],
    "health_care": ["care"],
    "logistics": ["field_ops", "ops"],
    "analyst": ["analyst", "data"],
    "operations": ["field_ops", "ops"],
}


def _split_pipe(value: Any) -> list[str]:
    if value is None:
        return []
    text = str(value).strip()
    if not text or text.lower() == "nan":
        return []
    return [p.strip() for p in text.split("|") if p.strip()]


def infer_role_families(
    *,
    title: str = "",
    summary: str = "",
    sectors: Any = None,
    existing: Any = None,
    military_role: str = "",
    max_tags: int = 4,
) -> str:
    """Return pipe-joined role_families aligned with employer psych prefs."""
    found: list[str] = []

    def _add(tags: list[str]) -> None:
        for t in tags:
            if t and t not in found:
                found.append(t)

    # Preserve curated tags first
    _add(_split_pipe(existing))
    if military_role and str(military_role).lower() != "nan":
        mapped = _MILITARY_ROLE_MAP.get(str(military_role).strip(), [])
        if mapped:
            _add(mapped)
        elif str(military_role).strip():
            # Already employer-like (e.g. engineer_ops, analyst)
            _add([str(military_role).strip()])

    blob = f"{title} {summary}"
    for pat, tags in _TITLE_ROLE_RULES:
        if pat.search(blob):
            _add(tags)
        if len(found) >= max_tags:
            break

    if len(found) < 2:
        for sector in _split_pipe(sectors):
            _add(_SECTOR_ROLES.get(sector, []))
            if len(found) >= max_tags:
                break

    return "|".join(found[:max_tags])


def ensure_role_families_column(df) -> Any:
    """Add/fill role_families on a catalogue DataFrame (copy)."""
    out = df.copy()
    if "role_families" not in out.columns:
        out["role_families"] = ""

    filled = []
    for _, row in out.iterrows():
        mil = str(row.get("role_family") or "")
        tags = infer_role_families(
            title=str(row.get("title") or ""),
            summary=str(row.get("summary") or row.get("profile_text") or ""),
            sectors=row.get("sectors"),
            existing=row.get("role_families"),
            military_role=mil,
        )
        filled.append(tags)
    out["role_families"] = filled
    return out
