"""FE/HE course matching for Gloucestershire + Bristol (NCS open data).

Seed built by scripts/06_1_build_courses_seed_from_ncs.py from the National Careers
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
from .matching import build_leaver_profile
from .role_families import ensure_role_families_column
from .scoring import (
    rounded_score_dict,
    score_catalogue_components,
    split_pipe,
)

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


# Load FE/HE courses seed CSV.
def load_courses(path: Path | None = None) -> pd.DataFrame:
    chosen = path or COURSES_PATH
    if not chosen.exists():
        alt = APP_DATA_DIR / "courses_seed.csv"
        if alt.exists():
            chosen = alt
        else:
            raise FileNotFoundError(
                "No courses_seed.csv — run scripts/06_1_build_courses_seed_from_ncs.py"
            )
    return ensure_role_families_column(pd.read_csv(chosen))


# Score one course row vs the leaver.
def score_course(leaver: dict[str, Any], row: pd.Series) -> dict[str, float]:
    course_sectors = split_pipe(row.get("sectors"))
    course_routes = split_pipe(row.get("entry_routes"))
    course_roles = split_pipe(row.get("role_families"))

    scores = score_catalogue_components(
        leaver,
        item_sectors=course_sectors,
        item_routes=course_routes,
        item_roles=course_roles,
        profile_text_b=str(row.get("profile_text") or row.get("summary") or ""),
        weights=WEIGHTS,
        sector_interest_weight=0.75,
        sector_psych_weight=0.25,
    )
    final = scores["final_score"]
    if leaver["entry_routes"] and course_routes and not (
        leaver["entry_routes"] & course_routes
    ):
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

    scores["final_score"] = final
    return rounded_score_dict(scores)


# Rank top course matches.
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
