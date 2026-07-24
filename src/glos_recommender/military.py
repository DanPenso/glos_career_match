"""Military pathway matching + local micro-credential suggestions.

Pathways: curated seed (guidance only — not official recruitment advice).
Micro-credentials: subset of NCS Course Directory courses (OGL) suitable as
Level 3+ PD exploration. ELC eligibility is NEVER asserted — UI must say
check ELCAS / Education Staff.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pandas as pd

from .matching import _jaccard, _split_pipe, _token_overlap, build_leaver_profile

PROJECT_ROOT = Path(__file__).resolve().parents[2]
SEED_DIR = PROJECT_ROOT / "data" / "seed"
PATHWAYS_PATH = SEED_DIR / "military_pathways_seed.csv"
MICRO_PATH = SEED_DIR / "military_microcreds_seed.csv"

WEIGHTS = {
    "sector": 0.50,
    "entry": 0.20,
    "text": 0.20,
    "psych": 0.10,
}


def load_military_pathways(path: Path | None = None) -> pd.DataFrame:
    p = path or PATHWAYS_PATH
    if not p.exists():
        raise FileNotFoundError(f"Missing military pathways seed: {p}")
    return pd.read_csv(p)


def load_military_microcreds(path: Path | None = None) -> pd.DataFrame:
    p = path or MICRO_PATH
    if not p.exists():
        return pd.DataFrame()
    return pd.read_csv(p)


def _score_row(leaver: dict[str, Any], row: pd.Series) -> dict[str, float]:
    sectors = _split_pipe(row.get("sectors"))
    routes = _split_pipe(row.get("entry_routes")) if "entry_routes" in row.index else set()
    interest_sectors = leaver.get("interest_sectors") or leaver["target_sectors"]
    psych_sectors = leaver.get("psych_sectors") or set()
    sector = 0.8 * _jaccard(interest_sectors, sectors) + 0.2 * _jaccard(
        psych_sectors, sectors
    )
    entry = _jaccard(leaver["entry_routes"], routes) if routes else 0.35
    text = _token_overlap(
        leaver["profile_text"], str(row.get("profile_text") or row.get("summary") or "")
    )
    psych_roles = leaver["psych"].get("role_prefs", set())
    psych = _jaccard(psych_sectors | set(psych_roles), sectors)
    final = (
        WEIGHTS["sector"] * sector
        + WEIGHTS["entry"] * entry
        + WEIGHTS["text"] * text
        + WEIGHTS["psych"] * psych
    )
    return {
        "final_score": round(final, 4),
        "sector_score": round(sector, 4),
        "entry_score": round(entry, 4),
        "text_score": round(text, 4),
        "psych_score": round(psych, 4),
    }


def match_military(
    form: dict[str, Any],
    pathways: pd.DataFrame | None = None,
    microcreds: pd.DataFrame | None = None,
    top_n: int = 3,
    micro_n: int = 6,
) -> tuple[dict[str, Any], pd.DataFrame, pd.DataFrame]:
    leaver = build_leaver_profile(form)
    path_df = pathways if pathways is not None else load_military_pathways()
    micro_df = microcreds if microcreds is not None else load_military_microcreds()

    path_rows = []
    for _, row in path_df.iterrows():
        scores = _score_row(leaver, row)
        path_rows.append({**row.to_dict(), **scores})
    ranked_paths = pd.DataFrame(path_rows).sort_values("final_score", ascending=False)
    ranked_paths["hybrid_score"] = ranked_paths["final_score"]
    ranked_paths["cosine_sim"] = 0.0

    micro_ranked = pd.DataFrame()
    if not micro_df.empty:
        # Prefer micro-creds that share sectors with top pathway or leaver interests
        top_sectors: set[str] = set(leaver.get("interest_sectors") or set())
        if len(ranked_paths):
            top_sectors |= _split_pipe(ranked_paths.iloc[0].get("sectors"))
        mrows = []
        for _, row in micro_df.iterrows():
            scores = _score_row(leaver, row)
            # Soft boost if overlaps top military pathway sectors
            if top_sectors & _split_pipe(row.get("sectors")):
                scores["final_score"] = round(min(1.0, scores["final_score"] + 0.08), 4)
            mrows.append({**row.to_dict(), **scores})
        micro_ranked = (
            pd.DataFrame(mrows)
            .sort_values("final_score", ascending=False)
            .head(micro_n)
            .reset_index(drop=True)
        )

    leaver["matching_mode"] = "military_hybrid"
    return (
        leaver,
        ranked_paths.head(top_n).reset_index(drop=True),
        micro_ranked,
    )
