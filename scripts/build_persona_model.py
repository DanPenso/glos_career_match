"""Fit K-Means career personas and export artefacts for live assignment.

Uses sector + RIASEC one-hots (same space as src/glos_recommender/personas.py).

Preference order for training rows:
  1. data/curated/leavers_train.csv (from scripts/curate_leaver_dataset.py)
  2. data/processed/clustered_leavers.pkl
  3. Synthetic seeds from persona_priors.yaml

Run from project root:
  .venv\\Scripts\\python scripts/build_persona_model.py
"""

from __future__ import annotations

import sys
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
from sklearn.cluster import KMeans
from sklearn.decomposition import PCA
from sklearn.preprocessing import StandardScaler

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from glos_recommender.personas import (  # noqa: E402
    RIASEC,
    SECTORS,
    leaver_feature_vector,
    load_persona_priors,
)

PROCESSED = ROOT / "data" / "processed"
CURATED = ROOT / "data" / "curated"
APP_DATA = ROOT / "app" / "app_data"
MODEL_PATH = APP_DATA / "persona_kmeans.joblib"
CURATED_TRAIN = CURATED / "leavers_train.csv"

RIASEC_HINTS = {
    "Technical Specialist": ["Investigative", "Conventional"],
    "Hands-on Maker": ["Realistic", "Conventional"],
    "People & Care": ["Social", "Conventional"],
    "Creative / Commercial": ["Artistic", "Enterprising"],
}


def _synthetic_rows() -> list[dict]:
    """Seed a small training set from curated persona sector fingerprints."""
    priors = load_persona_priors().get("personas") or {}
    rows = []
    for name, meta in priors.items():
        typical = list(meta.get("typical_sectors") or [])
        # Two slight variants per persona for a more stable fit
        for i, subset in enumerate([typical, typical[: max(1, len(typical) - 1)]]):
            rows.append(
                {
                    "interest_sectors": set(subset),
                    "target_sectors": set(subset),
                    "psych": {"dominant_riasec": RIASEC_HINTS.get(name, ["Conventional"])},
                    "_persona_seed": name,
                    "_variant": i,
                    "_sample_weight": 2.0,
                }
            )
    return rows


def _rows_from_curated() -> list[dict] | None:
    if not CURATED_TRAIN.exists():
        return None
    df = pd.read_csv(CURATED_TRAIN)
    rows = []
    for _, r in df.iterrows():
        sectors = set(str(r.get("interest_sectors", "")).split("|")) - {""}
        sectors = {s for s in sectors if s in SECTORS}
        dominant = [d for d in str(r.get("dominant_riasec", "")).split("|") if d]
        scores = {
            name: float(r[col])
            for name, col in zip(RIASEC, ["r", "i", "a", "s", "e", "c"])
            if col in r.index and pd.notna(r[col])
        }
        psych: dict = {"dominant_riasec": dominant}
        if scores:
            psych["riasec_scores"] = scores
        seed_raw = r.get("persona_seed")
        seed = ""
        if pd.notna(seed_raw):
            seed = str(seed_raw).strip()
            if seed.lower() in {"", "nan", "none"}:
                seed = ""
        rows.append(
            {
                "interest_sectors": sectors,
                "target_sectors": sectors,
                "psych": psych,
                "_persona_seed": seed,
                "_sample_weight": float(r.get("sample_weight") or 1.0),
            }
        )
    return rows or None


def _rows_from_clustered() -> list[dict] | None:
    path = PROCESSED / "clustered_leavers.pkl"
    if not path.exists():
        return None
    df = pd.read_pickle(path)
    rows = []
    for _, r in df.iterrows():
        sectors = set(str(r.get("interest_sectors", "")).split("|")) - {""}
        dominant = str(r.get("dominant_riasec", "")).split("|")
        dominant = [d for d in dominant if d]
        rows.append(
            {
                "interest_sectors": sectors,
                "target_sectors": sectors,
                "psych": {"dominant_riasec": dominant},
                "_persona_seed": str(r.get("persona") or ""),
                "_sample_weight": 1.0,
            }
        )
    return rows or None


def _prior_fingerprint(name: str, meta: dict) -> np.ndarray:
    typical = set(meta.get("typical_sectors") or [])
    return leaver_feature_vector(
        {
            "interest_sectors": typical,
            "target_sectors": typical,
            "psych": {"dominant_riasec": RIASEC_HINTS.get(name, [])},
        }
    )


def _label_clusters(
    kmeans: KMeans,
    scaler: StandardScaler,
    seed_labels: list[str],
) -> dict[int, str]:
    """Map cluster ids → persona names via Glos prior fingerprints (Hungarian).

    External seed majority votes are too noisy for product naming.
    """
    del seed_labels  # retained for API compatibility / future diagnostics
    priors = load_persona_priors().get("personas") or {}
    persona_names = list(priors.keys())
    if not persona_names:
        return {cid: f"Cluster {cid}" for cid in range(kmeans.n_clusters)}

    fps = np.vstack([_prior_fingerprint(n, priors[n]) for n in persona_names])
    fps_scaled = scaler.transform(fps)
    centers = kmeans.cluster_centers_
    n_c = int(kmeans.n_clusters)
    n_p = len(persona_names)
    cost = np.zeros((n_c, n_p), dtype="float64")
    for i in range(n_c):
        for j in range(n_p):
            cost[i, j] = float(np.linalg.norm(centers[i] - fps_scaled[j]))

    if n_c == n_p:
        try:
            from scipy.optimize import linear_sum_assignment

            rows_i, cols_j = linear_sum_assignment(cost)
            return {int(i): persona_names[int(j)] for i, j in zip(rows_i, cols_j)}
        except Exception:
            pass

    persona_map: dict[int, str] = {}
    used: set[str] = set()
    for cid in sorted(range(n_c), key=lambda i: float(cost[i].min())):
        for j in np.argsort(cost[cid]):
            name = persona_names[int(j)]
            if name not in used:
                persona_map[cid] = name
                used.add(name)
                break
        persona_map.setdefault(cid, f"Cluster {cid}")

    for candidate in persona_names:
        if candidate in used:
            continue
        for cid in range(n_c):
            if str(persona_map.get(cid, "")).startswith("Cluster"):
                persona_map[cid] = candidate
                used.add(candidate)
                break
    return persona_map


def main() -> None:
    APP_DATA.mkdir(parents=True, exist_ok=True)
    rows = _rows_from_curated()
    source = "curated/leavers_train.csv"
    if rows is None:
        rows = _rows_from_clustered()
        source = "clustered_leavers.pkl"
    if rows is None:
        rows = _synthetic_rows()
        source = "persona_priors synthetic seed"

    X = np.vstack([leaver_feature_vector(r) for r in rows])
    seed_labels = [str(r.get("_persona_seed") or "") for r in rows]
    weights = np.asarray(
        [float(r.get("_sample_weight") or 1.0) for r in rows], dtype="float64"
    )

    scaler = StandardScaler()
    X_scaled = scaler.fit_transform(X)

    priors = load_persona_priors().get("personas") or {}
    n_personas = len(priors) or 4
    if len(rows) >= n_personas * 10:
        k = n_personas
    else:
        k = min(n_personas, max(2, len(rows) // 2), len(rows))

    # Anchor centroids on Glos prior fingerprints when k matches persona count
    init = "k-means++"
    n_init: int | str = 10
    persona_names = list(priors.keys())
    if k == len(persona_names) and persona_names:
        fps = np.vstack([_prior_fingerprint(n, priors[n]) for n in persona_names])
        init = scaler.transform(fps)
        n_init = 1

    kmeans = KMeans(n_clusters=k, init=init, n_init=n_init, random_state=42)
    try:
        kmeans.fit(X_scaled, sample_weight=weights)
    except TypeError:
        kmeans.fit(X_scaled)

    if k == len(persona_names) and persona_names:
        # Keep product names aligned with the seeded init order
        persona_map = {i: persona_names[i] for i in range(k)}
    else:
        persona_map = _label_clusters(kmeans, scaler, seed_labels)

    # 2D projection for the leaver-facing “where you sit” map
    pca = PCA(n_components=2, random_state=42)
    pca.fit(X_scaled)

    payload = {
        "scaler": scaler,
        "kmeans": kmeans,
        "pca": pca,
        "persona_map": persona_map,
        "sectors": SECTORS,
        "riasec": RIASEC,
        "source": source,
        "n_samples": len(rows),
    }
    joblib.dump(payload, MODEL_PATH)

    summary = (
        pd.DataFrame(
            [
                {
                    "cluster_id": cid,
                    "persona": name,
                    "n_train": int(np.sum(kmeans.labels_ == cid)),
                }
                for cid, name in sorted(persona_map.items())
            ]
        )
    )
    summary_path = APP_DATA / "persona_summary.csv"
    # Merge with pathway blurb counts for convenience
    summary.to_csv(summary_path, index=False)

    print(f"Source: {source} (n={len(rows)})")
    print(f"k={k}")
    print(summary.to_string(index=False))
    print(f"Wrote {MODEL_PATH}")


if __name__ == "__main__":
    main()
