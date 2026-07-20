"""Curate train/holdout leaver rows for persona K-Means.

Sources (in priority mix):
  1. Glos persona_priors synthetic seeds (always)
  2. JobCannon RIASEC (+ career_match) when present under data/external/jobcannon/
  3. Occupation bridge rows (data/curated/occupation_to_sector.csv) as onet_bridge

Run from project root:
  .venv\\Scripts\\python scripts/curate_leaver_dataset.py
"""

from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from glos_recommender.live_learning import events_to_training_rows  # noqa: E402
from glos_recommender.personas import (  # noqa: E402
    RIASEC,
    SECTORS,
    load_persona_priors,
)

CURATED = ROOT / "data" / "curated"
EXTERNAL = ROOT / "data" / "external"
BRIDGE_PATH = CURATED / "occupation_to_sector.csv"
JOBCANNON_DIR = EXTERNAL / "jobcannon"

RIASEC_COLS = ["r", "i", "a", "s", "e", "c"]
RIASEC_FULL = ["Realistic", "Investigative", "Artistic", "Social", "Enterprising", "Conventional"]

# Mix targets (approximate)
N_GLOs_VARIANTS = 10  # variants per persona prior
N_BRIDGE_SAMPLES = 480
N_JOBCANNON_MAX = 1200
HOLDOUT_FRAC = 0.18
RANDOM_SEED = 42
GLOs_PRIOR_WEIGHT = 3.5
JOBCANNON_WEIGHT = 0.85
BRIDGE_WEIGHT = 0.75
GLOs_NUDGE_P = 0.35

# RIASEC letter → persona seed (refined in _persona_seed_from_top)
_LETTER_PERSONA = {
    "R": "Hands-on Maker",
    "I": "Technical Specialist",
    "A": "Creative / Commercial",
    "S": "People & Care",
    "E": "Creative / Commercial",
    "C": "Technical Specialist",
}


def _persona_seed_from_top(top: str) -> str:
    """Map JobCannon top_result (e.g. RIE) onto the four Glos personas."""
    t = "".join(ch for ch in str(top).upper() if ch in "RIASEC")
    if not t:
        return ""
    letters = t[:3]
    if letters[0] == "R":
        return "Hands-on Maker"
    if letters[0] == "I":
        return "Technical Specialist"
    if letters[0] == "S":
        return "People & Care"
    if letters[0] in {"A", "E"}:
        return "Creative / Commercial"
    if letters[0] == "C":
        return "Technical Specialist"
    return _LETTER_PERSONA.get(letters[0], "")


def _norm_vec(vals: np.ndarray) -> np.ndarray:
    v = np.asarray(vals, dtype="float64")
    v = np.clip(v, 0, None)
    s = float(v.sum())
    if s <= 1e-9:
        return np.ones_like(v) / len(v)
    return v / s


def _dominant_from_scores(scores: dict[str, float], k: int = 2) -> list[str]:
    ordered = sorted(scores.items(), key=lambda kv: kv[1], reverse=True)
    return [name for name, _ in ordered[:k] if _ > 0]


def _load_bridge() -> pd.DataFrame:
    df = pd.read_csv(BRIDGE_PATH)
    for c in RIASEC_COLS:
        df[c] = pd.to_numeric(df[c], errors="coerce").fillna(0.0)
    df["sector_list"] = df["sectors"].fillna("").apply(
        lambda s: [x for x in str(s).split("|") if x in SECTORS]
    )
    df = df[df["sector_list"].map(bool)].copy()
    mats = df[RIASEC_COLS].to_numpy(dtype="float64")
    df["riasec_norm"] = [_norm_vec(row) for row in mats]
    return df


def _nearest_occupations(
    bridge: pd.DataFrame, query: np.ndarray, top_k: int = 3
) -> list[dict]:
    q = _norm_vec(query)
    sims = []
    for _, row in bridge.iterrows():
        sim = float(np.dot(q, row["riasec_norm"]))
        sims.append((sim, row))
    sims.sort(key=lambda x: -x[0])
    return [r for _, r in sims[:top_k]]


def _sectors_from_occupations(occs: list[dict], rng: np.random.Generator) -> list[str]:
    tags: list[str] = []
    for occ in occs:
        tags.extend(occ["sector_list"])
    # unique preserve order
    seen = set()
    out = []
    for t in tags:
        if t not in seen:
            seen.add(t)
            out.append(t)
    if len(out) > 3:
        out = list(rng.choice(out, size=3, replace=False))
    return out


def _nudge_glos_sectors(
    sectors: list[str], rng: np.random.Generator, priors: dict
) -> list[str]:
    if rng.random() > GLOs_NUDGE_P or not priors:
        return sectors
    name = rng.choice(list(priors.keys()))
    typical = list((priors[name] or {}).get("typical_sectors") or [])
    typical = [t for t in typical if t in SECTORS]
    if not typical:
        return sectors
    merged = list(dict.fromkeys(sectors + typical[:2]))
    return merged[:3]


def rows_from_glos_priors(rng: np.random.Generator) -> list[dict]:
    priors = load_persona_priors().get("personas") or {}
    riasec_hints = {
        "Technical Specialist": ["Investigative", "Conventional"],
        "Hands-on Maker": ["Realistic", "Conventional"],
        "People & Care": ["Social", "Conventional"],
        "Creative / Commercial": ["Artistic", "Enterprising"],
    }
    # Order: R I A S E C
    score_templates = {
        "Technical Specialist": [2, 7, 2, 2, 3, 6],
        "Hands-on Maker": [7, 4, 2, 2, 3, 5],
        "People & Care": [3, 3, 2, 7, 3, 5],
        "Creative / Commercial": [2, 3, 7, 4, 6.5, 3.5],
    }
    rows = []
    for name, meta in priors.items():
        typical = [t for t in (meta.get("typical_sectors") or []) if t in SECTORS]
        if not typical:
            continue
        base_scores = score_templates.get(name, [3, 3, 3, 3, 3, 3])
        for i in range(N_GLOs_VARIANTS):
            # sector subsets + noise on scores
            if i == 0:
                sectors = typical
            elif i == 1:
                sectors = typical[: max(1, len(typical) - 1)]
            else:
                k = int(rng.integers(1, min(3, len(typical)) + 1))
                sectors = list(rng.choice(typical, size=k, replace=False))
            noise = rng.normal(0, 0.45, size=6)
            scores_arr = np.clip(np.asarray(base_scores, dtype="float64") + noise, 0.5, 8)
            scores = {RIASEC_FULL[j]: float(scores_arr[j]) for j in range(6)}
            dominant = riasec_hints.get(name) or _dominant_from_scores(scores)
            rows.append(
                {
                    "leaver_id": f"glos_{name.replace(' ', '_').lower()}_{i}",
                    "interest_sectors": sectors,
                    "target_sectors": sectors,
                    "dominant_riasec": dominant,
                    "riasec_scores": scores,
                    "source": "glos_priors",
                    "cohort": "synthetic_glos",
                    "sample_weight": GLOs_PRIOR_WEIGHT,
                    "persona_seed": name,
                }
            )
    return rows


def rows_from_bridge(bridge: pd.DataFrame, rng: np.random.Generator) -> list[dict]:
    priors = load_persona_priors().get("personas") or {}
    rows = []
    n = min(N_BRIDGE_SAMPLES, max(1, len(bridge) * 6))
    for i in range(n):
        occ = bridge.iloc[int(rng.integers(0, len(bridge)))]
        # jitter occupation RIASEC to create person-like variation
        base = occ[RIASEC_COLS].to_numpy(dtype="float64")
        noisy = np.clip(base + rng.normal(0, 0.55, size=6), 0.5, 8)
        scores = {RIASEC_FULL[j]: float(noisy[j]) for j in range(6)}
        # also pull 1–2 nearest neighbours for multi-sector
        neighbours = _nearest_occupations(bridge, noisy, top_k=2)
        sectors = _sectors_from_occupations(neighbours, rng)
        sectors = _nudge_glos_sectors(sectors, rng, priors)
        if not sectors:
            continue
        rows.append(
            {
                "leaver_id": f"bridge_{occ['occupation_key']}_{i}",
                "interest_sectors": sectors,
                "target_sectors": sectors,
                "dominant_riasec": _dominant_from_scores(scores),
                "riasec_scores": scores,
                "source": "onet_bridge",
                "cohort": "synthetic_occupation",
                "sample_weight": BRIDGE_WEIGHT,
                "persona_seed": "",
            }
        )
    return rows


def _parse_jobcannon_scores(row: pd.Series) -> dict[str, float] | None:
    """Accept score_r / score_realistic / R / Realistic style columns."""
    scores: dict[str, float] = {}
    aliases = {
        "Realistic": ["score_r", "score_realistic", "r", "realistic", "R"],
        "Investigative": ["score_i", "score_investigative", "i", "investigative", "I"],
        "Artistic": ["score_a", "score_artistic", "a", "artistic", "A"],
        "Social": ["score_s", "score_social", "s", "social", "S"],
        "Enterprising": ["score_e", "score_enterprising", "e", "enterprising", "E"],
        "Conventional": ["score_c", "score_conventional", "c", "conventional", "C"],
    }
    cols_lower = {str(c).lower(): c for c in row.index}
    for name, keys in aliases.items():
        val = None
        for k in keys:
            col = cols_lower.get(k.lower())
            if col is not None and pd.notna(row[col]):
                try:
                    val = float(row[col])
                    break
                except (TypeError, ValueError):
                    continue
        if val is None:
            return None
        scores[name] = val
    return scores


def rows_from_jobcannon(
    bridge: pd.DataFrame, rng: np.random.Generator
) -> list[dict]:
    paths = [
        JOBCANNON_DIR / "riasec.csv",
        JOBCANNON_DIR / "career_match.csv",
    ]
    frames = []
    for p in paths:
        if p.exists():
            frames.append(pd.read_csv(p))
            print(f"Loaded {p.name}: {len(frames[-1])} rows")
    if not frames:
        print("No JobCannon CSVs found — skip (run fetch_external_clustering_data.py).")
        return []

    priors = load_persona_priors().get("personas") or {}
    rows = []
    for fi, df in enumerate(frames):
        # subsample for balance
        if len(df) > N_JOBCANNON_MAX // max(1, len(frames)):
            df = df.sample(
                n=N_JOBCANNON_MAX // max(1, len(frames)),
                random_state=RANDOM_SEED + fi,
            )
        for idx, row in df.iterrows():
            scores = _parse_jobcannon_scores(row)
            if not scores:
                continue
            arr = np.array([scores[n] for n in RIASEC_FULL], dtype="float64")
            occs = _nearest_occupations(bridge, arr, top_k=3)
            sectors = _sectors_from_occupations(occs, rng)
            sectors = _nudge_glos_sectors(sectors, rng, priors)
            if not sectors:
                continue
            seed = _persona_seed_from_top(str(row.get("top_result") or ""))

            rows.append(
                {
                    "leaver_id": f"jc_{fi}_{idx}",
                    "interest_sectors": sectors,
                    "target_sectors": sectors,
                    "dominant_riasec": _dominant_from_scores(scores),
                    "riasec_scores": scores,
                    "source": "jobcannon",
                    "cohort": "adult_online",
                    "sample_weight": JOBCANNON_WEIGHT,
                    "persona_seed": seed,
                }
            )
    return rows


def _to_frame(rows: list[dict]) -> pd.DataFrame:
    out = []
    for r in rows:
        scores = r.get("riasec_scores") or {}
        # normalise continuous to 0–1 for export
        arr = np.array([float(scores.get(n, 0.0)) for n in RIASEC_FULL], dtype="float64")
        arr_n = _norm_vec(arr)
        out.append(
            {
                "leaver_id": r["leaver_id"],
                "interest_sectors": "|".join(sorted(set(r["interest_sectors"]))),
                "target_sectors": "|".join(sorted(set(r["target_sectors"]))),
                "dominant_riasec": "|".join(r["dominant_riasec"]),
                "r": round(float(arr_n[0]), 4),
                "i": round(float(arr_n[1]), 4),
                "a": round(float(arr_n[2]), 4),
                "s": round(float(arr_n[3]), 4),
                "e": round(float(arr_n[4]), 4),
                "c": round(float(arr_n[5]), 4),
                "source": r["source"],
                "cohort": r["cohort"],
                "sample_weight": float(r["sample_weight"]),
                "persona_seed": r.get("persona_seed") or "",
            }
        )
    return pd.DataFrame(out)


def _train_holdout_split(df: pd.DataFrame, rng: np.random.Generator) -> pd.DataFrame:
    df = df.copy()
    df["split"] = "train"
    # stratify loosely by dominant first code
    df["_strata"] = df["dominant_riasec"].str.split("|").str[0].fillna("Unknown")
    hold_ids = []
    for _, grp in df.groupby("_strata"):
        n_hold = max(1, int(round(len(grp) * HOLDOUT_FRAC))) if len(grp) >= 6 else 0
        if n_hold:
            pick = list(rng.choice(grp.index.to_numpy(), size=n_hold, replace=False))
            hold_ids.extend(pick)
    df.loc[hold_ids, "split"] = "holdout"
    return df.drop(columns=["_strata"])


def main() -> None:
    rng = np.random.default_rng(RANDOM_SEED)
    CURATED.mkdir(parents=True, exist_ok=True)
    bridge = _load_bridge()
    print(f"Bridge occupations: {len(bridge)}")

    rows: list[dict] = []
    rows.extend(rows_from_glos_priors(rng))
    print(f"Glos priors rows: {sum(1 for r in rows if r['source']=='glos_priors')}")
    rows.extend(rows_from_bridge(bridge, rng))
    print(f"Bridge rows: {sum(1 for r in rows if r['source']=='onet_bridge')}")
    jc = rows_from_jobcannon(bridge, rng)
    rows.extend(jc)
    print(f"JobCannon rows: {len(jc)}")
    live = events_to_training_rows()
    rows.extend(live)
    print(f"Live intake rows: {len(live)}")

    df = _to_frame(rows)
    # drop empty sector rows
    df = df[df["interest_sectors"].str.len() > 0].drop_duplicates(subset=["leaver_id"])
    df = _train_holdout_split(df, rng)

    train = df[df["split"] == "train"].drop(columns=["split"])
    hold = df[df["split"] == "holdout"].drop(columns=["split"])

    train_path = CURATED / "leavers_train.csv"
    hold_path = CURATED / "leavers_holdout.csv"
    train.to_csv(train_path, index=False)
    hold.to_csv(hold_path, index=False)

    # parquet if engine available
    try:
        train.to_parquet(CURATED / "leavers_train.parquet", index=False)
        hold.to_parquet(CURATED / "leavers_holdout.parquet", index=False)
    except Exception:
        pass

    manifest = {
        "version": "v1",
        "created_utc": datetime.now(timezone.utc).isoformat(),
        "n_train": int(len(train)),
        "n_holdout": int(len(hold)),
        "sources": train["source"].value_counts().to_dict(),
        "sectors": SECTORS,
        "riasec": RIASEC,
        "bridge_path": str(BRIDGE_PATH.relative_to(ROOT)),
        "jobcannon_present": (JOBCANNON_DIR / "riasec.csv").exists(),
        "notes": (
            "Mixed Glos priors + occupation bridge (+ JobCannon if fetched) "
            "+ anonymous live intakes when present. "
            "Not a Gloucestershire population sample."
        ),
    }
    (CURATED / "CURATED_MANIFEST.json").write_text(
        json.dumps(manifest, indent=2), encoding="utf-8"
    )

    print(f"Wrote {train_path} ({len(train)} rows)")
    print(f"Wrote {hold_path} ({len(hold)} rows)")
    print("Source mix (train):")
    print(train["source"].value_counts().to_string())
    print(f"Manifest → {CURATED / 'CURATED_MANIFEST.json'}")


if __name__ == "__main__":
    main()
