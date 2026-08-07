"""Catalogue embeddings (MiniLM) for companies, courses, and military items.

Build artefacts:
  .venv\\Scripts\\python scripts/build_company_embeddings.py
  .venv\\Scripts\\python scripts/build_catalogue_embeddings.py

→ app/app_data/company_embeddings.npz
→ app/app_data/course_embeddings.npz
→ app/app_data/military_pathway_embeddings.npz
→ app/app_data/military_microcred_embeddings.npz
"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Any

import numpy as np

PROJECT_ROOT = Path(__file__).resolve().parents[2]
APP_DATA_DIR = PROJECT_ROOT / "app" / "app_data"
MODEL_DIR = PROJECT_ROOT / "models" / "local_minilm_model"

COMPANY_EMBEDDINGS_PATH = APP_DATA_DIR / "company_embeddings.npz"
COURSE_EMBEDDINGS_PATH = APP_DATA_DIR / "course_embeddings.npz"
MILITARY_PATHWAY_EMBEDDINGS_PATH = APP_DATA_DIR / "military_pathway_embeddings.npz"
MILITARY_MICRO_EMBEDDINGS_PATH = APP_DATA_DIR / "military_microcred_embeddings.npz"

# Back-compat alias used by build_company_embeddings.py / matching.py
EMBEDDINGS_PATH = COMPANY_EMBEDDINGS_PATH

HYBRID_WEIGHT = 0.7
COSINE_WEIGHT = 0.3

_embedder = None
_ID_KEYS = ("item_ids", "company_ids", "course_ids", "pathway_ids", "cred_ids")


def _get_embedder():
    global _embedder
    if _embedder is not None:
        return _embedder
    from sentence_transformers import SentenceTransformer

    if MODEL_DIR.exists() and any(MODEL_DIR.iterdir()):
        _embedder = SentenceTransformer(str(MODEL_DIR))
    else:
        _embedder = SentenceTransformer("all-MiniLM-L6-v2")
    return _embedder


def embed_texts(texts: list[str], *, batch_size: int = 32) -> np.ndarray:
    """Return L2-normalised float32 matrix (n, d)."""
    model = _get_embedder()
    clean = [str(t or "").strip() or " " for t in texts]
    vecs = model.encode(
        clean,
        show_progress_bar=False,
        batch_size=batch_size,
        convert_to_numpy=True,
        normalize_embeddings=True,
    )
    return np.asarray(vecs, dtype="float32")


def embed_text(text: str) -> np.ndarray:
    return embed_texts([text])[0]


def save_item_embeddings(
    path: Path,
    ids: list[str],
    vectors: np.ndarray,
    *,
    model_label: str | None = None,
    id_key: str = "item_ids",
) -> Path:
    """Write a compressed npz with L2-normalised vectors."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    label = model_label or (
        str(MODEL_DIR) if MODEL_DIR.exists() else "all-MiniLM-L6-v2"
    )
    vecs = np.asarray(vectors, dtype="float32")
    norms = np.linalg.norm(vecs, axis=1, keepdims=True)
    norms = np.maximum(norms, 1e-9)
    vecs = vecs / norms
    np.savez_compressed(
        path,
        **{
            id_key: np.array([str(x) for x in ids], dtype=object),
            "vectors": vecs,
            "model": np.array([label]),
        },
    )
    return path


def _extract_ids(data: Any) -> list[str]:
    for key in _ID_KEYS:
        if key in data.files:
            return [str(x) for x in data[key].tolist()]
    raise KeyError(f"No id array in embeddings file (tried {_ID_KEYS})")


@lru_cache(maxsize=8)
def load_item_embeddings(path: str) -> dict[str, Any] | None:
    """Load precomputed item vectors. Returns None if missing."""
    p = Path(path)
    if not p.exists():
        return None
    data = np.load(p, allow_pickle=True)
    ids = _extract_ids(data)
    vectors = np.asarray(data["vectors"], dtype="float32")
    norms = np.linalg.norm(vectors, axis=1, keepdims=True)
    norms = np.maximum(norms, 1e-9)
    vectors = vectors / norms
    id_to_idx = {cid: i for i, cid in enumerate(ids)}
    return {
        "item_ids": ids,
        "company_ids": ids,  # back-compat for older callers
        "vectors": vectors,
        "id_to_idx": id_to_idx,
        "path": str(p),
        "model": str(data["model"][0]) if "model" in data.files else "all-MiniLM-L6-v2",
    }


def load_company_embeddings(path: str | None = None) -> dict[str, Any] | None:
    """Load company vectors (wrapper around load_item_embeddings)."""
    p = str(Path(path) if path else COMPANY_EMBEDDINGS_PATH)
    return load_item_embeddings(p)


def load_course_embeddings(path: str | None = None) -> dict[str, Any] | None:
    p = str(Path(path) if path else COURSE_EMBEDDINGS_PATH)
    return load_item_embeddings(p)


def load_military_pathway_embeddings(path: str | None = None) -> dict[str, Any] | None:
    p = str(Path(path) if path else MILITARY_PATHWAY_EMBEDDINGS_PATH)
    return load_item_embeddings(p)


def load_military_microcred_embeddings(path: str | None = None) -> dict[str, Any] | None:
    p = str(Path(path) if path else MILITARY_MICRO_EMBEDDINGS_PATH)
    return load_item_embeddings(p)


def clear_embedding_cache() -> None:
    load_item_embeddings.cache_clear()


def cosine_map_for_leaver(
    leaver_profile_text: str,
    item_ids: list[str],
    *,
    embeddings: dict[str, Any] | None = None,
) -> dict[str, float]:
    """item_id → cosine similarity clipped to [0, 1]."""
    emb = embeddings
    if emb is None:
        emb = load_company_embeddings()
    if emb is None or not item_ids:
        return {str(cid): 0.0 for cid in item_ids}
    q = embed_text(leaver_profile_text)
    mat = emb["vectors"]
    sims = mat @ q
    id_to_idx = emb["id_to_idx"]
    out: dict[str, float] = {}
    for cid in item_ids:
        i = id_to_idx.get(str(cid))
        if i is None:
            out[str(cid)] = 0.0
        else:
            out[str(cid)] = float(max(0.0, min(1.0, sims[i])))
    return out


def blend_hybrid_cosine(
    ranked,
    *,
    id_col: str,
    leaver_profile_text: str,
    embeddings: dict[str, Any] | None,
    hybrid_weight: float = HYBRID_WEIGHT,
    cosine_weight: float = COSINE_WEIGHT,
) -> tuple[Any, str]:
    """Mutate ranked frame: set cosine_sim + blended final_score.

    Returns (ranked, matching_mode).
    """
    ranked = ranked.copy()
    ranked["hybrid_score"] = ranked["final_score"]
    if embeddings is None or not len(ranked) or id_col not in ranked.columns:
        ranked["cosine_sim"] = 0.0
        return ranked, "hybrid_only"
    try:
        ids = ranked[id_col].astype(str).tolist()
        sim_map = cosine_map_for_leaver(
            leaver_profile_text,
            ids,
            embeddings=embeddings,
        )
        ranked["cosine_sim"] = ranked[id_col].astype(str).map(sim_map).fillna(0.0)
        ranked["final_score"] = (
            hybrid_weight * ranked["hybrid_score"] + cosine_weight * ranked["cosine_sim"]
        ).round(4)
        return ranked, "hybrid_plus_embeddings"
    except Exception:
        ranked["cosine_sim"] = 0.0
        return ranked, "hybrid_only"
