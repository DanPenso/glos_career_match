"""Curated Coursera/Udemy-style online course suggestions (option 2).

Seed: data/taxonomy/online_courses.yaml
Links prefer stable platform search URLs so destinations stay current.
Not an official catalog feed — refresh the YAML quarterly.
"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Any

import yaml

from .matching import _jaccard, _token_overlap, build_leaver_profile

PROJECT_ROOT = Path(__file__).resolve().parents[2]
TAXONOMY_DIR = PROJECT_ROOT / "data" / "taxonomy"
COURSES_PATH = TAXONOMY_DIR / "online_courses.yaml"


@lru_cache(maxsize=1)
def load_online_catalogue(path: str | None = None) -> dict[str, Any]:
    p = Path(path) if path else COURSES_PATH
    if not p.exists():
        return {"disclaimer": "", "courses": []}
    with open(p, encoding="utf-8") as f:
        return yaml.safe_load(f) or {"disclaimer": "", "courses": []}


def clear_online_courses_cache() -> None:
    load_online_catalogue.cache_clear()


def _as_sector_set(value: Any) -> set[str]:
    if isinstance(value, set):
        return {str(x) for x in value}
    if isinstance(value, (list, tuple)):
        return {str(x) for x in value}
    if value is None:
        return set()
    return {p.strip() for p in str(value).split("|") if p.strip()}


def score_online_course(leaver: dict[str, Any], course: dict[str, Any]) -> float:
    interest = set(leaver.get("interest_sectors") or set())
    target = set(leaver.get("target_sectors") or set())
    psych = set(leaver.get("psych_sectors") or set())
    course_sectors = _as_sector_set(course.get("sectors"))

    sector = 0.7 * _jaccard(interest, course_sectors) + 0.2 * _jaccard(
        target, course_sectors
    ) + 0.1 * _jaccard(psych, course_sectors)

    blob = " ".join(
        [
            str(course.get("title") or ""),
            str(course.get("description") or ""),
            " ".join(course_sectors),
        ]
    )
    text = _token_overlap(str(leaver.get("profile_text") or ""), blob)
    score = 0.75 * sector + 0.25 * text

    # Soft boost when title echoes stated interests / courses
    title = str(course.get("title") or "").lower()
    interest_blob = " ".join(leaver.get("interests") or []).lower()
    course_blob = " ".join(leaver.get("courses") or []).lower()
    for term in (
        "python",
        "cyber",
        "web",
        "data",
        "sql",
        "marketing",
        "design",
        "cad",
        "construction",
        "hospitality",
        "care",
        "teach",
        "agricult",
        "project",
        "ai ",
    ):
        if term.strip() in title and (
            term.strip() in interest_blob or term.strip() in course_blob
        ):
            score = min(1.0, score + 0.1)
            break
    return round(score, 4)


def match_online_courses(
    form: dict[str, Any] | None = None,
    *,
    leaver: dict[str, Any] | None = None,
    top_n: int = 3,
) -> tuple[list[dict[str, Any]], str]:
    """Return (top courses, disclaimer). Uses existing leaver profile when provided."""
    profile = leaver if leaver is not None else build_leaver_profile(form or {})
    catalogue = load_online_catalogue()
    disclaimer = " ".join(str(catalogue.get("disclaimer") or "").split())
    rows: list[dict[str, Any]] = []
    for course in catalogue.get("courses") or []:
        if not isinstance(course, dict):
            continue
        score = score_online_course(profile, course)
        rows.append(
            {
                "course_id": str(course.get("id") or course.get("title") or ""),
                "title": str(course.get("title") or "").strip(),
                "description": " ".join(str(course.get("description") or "").split()),
                "provider": str(course.get("provider") or "").strip(),
                "url": str(course.get("url") or "").strip(),
                "sectors": "|".join(sorted(_as_sector_set(course.get("sectors")))),
                "score": score,
            }
        )
    rows.sort(key=lambda r: (-r["score"], r["title"]))
    return rows[:top_n], disclaimer
