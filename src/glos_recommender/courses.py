"""FE/HE course matching for Gloucestershire + Bristol (NCS open data).

Seed built by scripts/build_courses_seed_from_ncs.py from the National Careers
Service course directory (Open Government Licence v3.0).

When app/app_data/course_embeddings.npz exists, blends MiniLM cosine with
rules hybrid (same pattern as employer matching).
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pandas as pd

from .embeddings import (
    COSINE_WEIGHT,
    HYBRID_WEIGHT,
    blend_hybrid_cosine,
    load_course_embeddings,
)
from .matching import _jaccard, _split_pipe, _token_overlap, build_leaver_profile
from .role_families import ensure_role_families_column

PROJECT_ROOT = Path(__file__).resolve().parents[2]
SEED_DIR = PROJECT_ROOT / "data" / "seed"
APP_DATA_DIR = PROJECT_ROOT / "app" / "app_data"
COURSES_PATH = SEED_DIR / "courses_seed.csv"

WEIGHTS = {
    "sector": 0.40,
    "entry": 0.20,
    "text": 0.15,
    "psych": 0.25,
}


def load_courses(path: Path | None = None) -> pd.DataFrame:
    chosen = path or COURSES_PATH
    if not chosen.exists():
        alt = APP_DATA_DIR / "courses_seed.csv"
        if alt.exists():
            chosen = alt
        else:
            raise FileNotFoundError(
                "No courses_seed.csv — run scripts/build_courses_seed_from_ncs.py"
            )
    return ensure_role_families_column(pd.read_csv(chosen))


def score_course(leaver: dict[str, Any], row: pd.Series) -> dict[str, float]:
    course_sectors = _split_pipe(row.get("sectors"))
    course_routes = _split_pipe(row.get("entry_routes"))
    course_roles = _split_pipe(row.get("role_families"))

    interest_sectors = leaver.get("interest_sectors") or leaver["target_sectors"]
    psych_sectors = leaver.get("psych_sectors") or set()
    sector = 0.75 * _jaccard(interest_sectors, course_sectors) + 0.25 * _jaccard(
        psych_sectors, course_sectors
    )
    entry = _jaccard(leaver["entry_routes"], course_routes)
    text = _token_overlap(
        leaver["profile_text"], str(row.get("profile_text") or row.get("summary") or "")
    )
    psych_roles = leaver["psych"].get("role_prefs", set())
    # Prefer role-family overlap (employer-aligned); soft-mix sector psych as fallback
    if psych_roles and course_roles:
        psych = 0.85 * _jaccard(psych_roles, course_roles) + 0.15 * _jaccard(
            psych_sectors, course_sectors
        )
    elif psych_roles or psych_sectors:
        psych = _jaccard(psych_sectors | set(psych_roles), course_sectors | course_roles)
    else:
        psych = 0.0

    final = (
        WEIGHTS["sector"] * sector
        + WEIGHTS["entry"] * entry
        + WEIGHTS["text"] * text
        + WEIGHTS["psych"] * psych
    )
    if leaver["entry_routes"] and course_routes and not (leaver["entry_routes"] & course_routes):
        final *= 0.45

    # Soft boost when course title clearly echoes stated interests
    title = str(row.get("title") or "").lower()
    interest_blob = " ".join(leaver.get("interests") or []).lower()
    course_blob = " ".join(leaver.get("courses") or []).lower()
    boost_terms = (
        "cyber",
        "software",
        "comput",
        "digital",
        "nurs",
        "health",
        "engineer",
        "construct",
        "business",
        "educat",
        "creat",
        "media",
        "agricult",
        "hospitality",
        "tourism",
    )
    for term in boost_terms:
        if term in title and (term in interest_blob or term in course_blob):
            final = min(1.0, final + 0.12)
            break

    provider = str(row.get("provider") or "").lower()
    if "college" in provider or "university" in provider or provider.startswith("uwe"):
        final = min(1.0, final + 0.05)

    # Prefer vocational routes when present in the catalogue
    type_label = str(row.get("course_type_label") or "").lower()
    if "nvq" in type_label or "nvq" in title:
        final = min(1.0, final + 0.06)
    if "bootcamp" in type_label or "bootcamp" in title:
        final = min(1.0, final + 0.06)

    return {
        "final_score": round(final, 4),
        "sector_score": round(sector, 4),
        "entry_score": round(entry, 4),
        "text_score": round(text, 4),
        "psych_score": round(psych, 4),
    }


def match_courses(
    form: dict[str, Any],
    courses: pd.DataFrame | None = None,
    top_n: int = 3,
) -> tuple[dict[str, Any], pd.DataFrame]:
    leaver = build_leaver_profile(form)
    df = courses if courses is not None else load_courses()
    if "role_families" not in df.columns or df["role_families"].isna().all():
        df = ensure_role_families_column(df)

    rows = []
    for _, row in df.iterrows():
        scores = score_course(leaver, row)
        rows.append({**row.to_dict(), **scores})
    ranked = pd.DataFrame(rows)

    ranked, mode = blend_hybrid_cosine(
        ranked,
        id_col="course_id",
        leaver_profile_text=str(leaver.get("profile_text") or ""),
        embeddings=load_course_embeddings(),
        hybrid_weight=HYBRID_WEIGHT,
        cosine_weight=COSINE_WEIGHT,
    )
    leaver["matching_mode"] = f"courses_{mode}"
    ranked = ranked.sort_values("final_score", ascending=False)
    return leaver, ranked.head(top_n).reset_index(drop=True)
