"""Military pathway matching + local micro-credential suggestions.

Pathways: curated seed (guidance only — not official recruitment advice).
Micro-credentials: subset of NCS Course Directory courses (OGL) suitable as
Level 3+ PD exploration. ELC eligibility is NEVER asserted — UI must say
check ELCAS / Education Staff.

When pathway/microcred MiniLM embeddings exist, blends cosine with rules
hybrid (same pattern as employer / course matching).
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pandas as pd

from .embeddings import (
    COSINE_WEIGHT,
    HYBRID_WEIGHT,
    blend_hybrid_cosine,
    load_military_microcred_embeddings,
    load_military_pathway_embeddings,
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
PATHWAYS_PATH = SEED_DIR / "military_pathways_seed.csv"
MICRO_PATH = SEED_DIR / "military_microcreds_seed.csv"

WEIGHTS = {
    "sector": 0.40,
    "entry": 0.20,
    "text": 0.15,
    "psych": 0.25,
}


# Load curated military pathway seed.
def load_military_pathways(path: Path | None = None) -> pd.DataFrame:
    p = path or PATHWAYS_PATH
    if not p.exists():
        raise FileNotFoundError(f"Missing military pathways seed: {p}")
    return ensure_role_families_column(pd.read_csv(p))


# Load military-related micro-credential seed.
def load_military_microcreds(path: Path | None = None) -> pd.DataFrame:
    p = path or MICRO_PATH
    if not p.exists():
        return pd.DataFrame()
    return ensure_role_families_column(pd.read_csv(p))


# Score one military pathway or micro-cred row.
def _score_row(leaver: dict[str, Any], row: pd.Series) -> dict[str, float]:
    has_routes = "entry_routes" in row.index
    routes = split_pipe(row.get("entry_routes")) if has_routes else set()
    scores = score_catalogue_components(
        leaver,
        item_sectors=split_pipe(row.get("sectors")),
        item_routes=routes,
        item_roles=split_pipe(row.get("role_families")),
        profile_text_b=str(row.get("profile_text") or row.get("summary") or ""),
        weights=WEIGHTS,
        sector_interest_weight=0.8,
        sector_psych_weight=0.2,
        default_entry=0.35 if not routes else None,
    )
    return rounded_score_dict(scores)


# Rank military pathways plus related micro-creds.
def match_military(
    form: dict[str, Any],
    pathways: pd.DataFrame | None = None,
    microcreds: pd.DataFrame | None = None,
    top_n: int = 3,
    micro_n: int = 6,
) -> tuple[dict[str, Any], pd.DataFrame, pd.DataFrame]:
    leaver = build_leaver_profile(form)
    path_df = pathways if pathways is not None else load_military_pathways()
    if "role_families" not in path_df.columns:
        path_df = ensure_role_families_column(path_df)
    micro_df = microcreds if microcreds is not None else load_military_microcreds()
    if not micro_df.empty and "role_families" not in micro_df.columns:
        micro_df = ensure_role_families_column(micro_df)

    path_rows = []
    for _, row in path_df.iterrows():
        scores = _score_row(leaver, row)
        path_rows.append({**row.to_dict(), **scores})
    ranked_paths = pd.DataFrame(path_rows)
    ranked_paths, path_mode = blend_hybrid_cosine(
        ranked_paths,
        id_col="pathway_id",
        leaver_profile_text=str(leaver.get("profile_text") or ""),
        embeddings=load_military_pathway_embeddings(),
        hybrid_weight=HYBRID_WEIGHT,
        cosine_weight=COSINE_WEIGHT,
    )
    ranked_paths = ranked_paths.sort_values("final_score", ascending=False)

    micro_ranked = pd.DataFrame()
    if not micro_df.empty:
        # Prefer micro-creds that share sectors with top pathway or leaver interests
        top_sectors: set[str] = set(leaver.get("interest_sectors") or set())
        if len(ranked_paths):
            top_sectors |= split_pipe(ranked_paths.iloc[0].get("sectors"))
        mrows = []
        for _, row in micro_df.iterrows():
            scores = _score_row(leaver, row)
            # Soft boost if overlaps top military pathway sectors
            if top_sectors & split_pipe(row.get("sectors")):
                scores["final_score"] = round(min(1.0, scores["final_score"] + 0.08), 4)
            mrows.append({**row.to_dict(), **scores})
        micro_ranked = pd.DataFrame(mrows)
        micro_ranked, _micro_mode = blend_hybrid_cosine(
            micro_ranked,
            id_col="cred_id",
            leaver_profile_text=str(leaver.get("profile_text") or ""),
            embeddings=load_military_microcred_embeddings(),
            hybrid_weight=HYBRID_WEIGHT,
            cosine_weight=COSINE_WEIGHT,
        )
        micro_ranked = (
            micro_ranked.sort_values("final_score", ascending=False)
            .head(micro_n)
            .reset_index(drop=True)
        )

    leaver["matching_mode"] = f"military_{path_mode}"
    return (
        leaver,
        ranked_paths.head(top_n).reset_index(drop=True),
        micro_ranked,
    )
