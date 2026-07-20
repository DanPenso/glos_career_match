"""Company profile embeddings for live matching (MiniLM).

Build artefact:
  .venv\\Scripts\\python scripts/build_company_embeddings.py
→ app/app_data/company_embeddings.npz
"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Any

import numpy as np

PROJECT_ROOT = Path(__file__).resolve().parents[2]
APP_DATA_DIR = PROJECT_ROOT / "app" / "app_data"
MODEL_DIR = PROJECT_ROOT / "models" / "local_minilm_model"
EMBEDDINGS_PATH = APP_DATA_DIR / "company_embeddings.npz"

_embedder = None


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


@lru_cache(maxsize=1)
def load_company_embeddings(
    path: str | None = None,
) -> dict[str, Any] | None:
    """Load precomputed company vectors. Returns None if missing."""
    p = Path(path) if path else EMBEDDINGS_PATH
    if not p.exists():
        return None
    data = np.load(p, allow_pickle=True)
    ids = [str(x) for x in data["company_ids"].tolist()]
    vectors = np.asarray(data["vectors"], dtype="float32")
    # Ensure L2-normalised
    norms = np.linalg.norm(vectors, axis=1, keepdims=True)
    norms = np.maximum(norms, 1e-9)
    vectors = vectors / norms
    id_to_idx = {cid: i for i, cid in enumerate(ids)}
    return {
        "company_ids": ids,
        "vectors": vectors,
        "id_to_idx": id_to_idx,
        "path": str(p),
        "model": str(data["model"][0]) if "model" in data.files else "all-MiniLM-L6-v2",
    }


def clear_embedding_cache() -> None:
    load_company_embeddings.cache_clear()


def cosine_map_for_leaver(
    leaver_profile_text: str,
    company_ids: list[str],
    *,
    embeddings: dict[str, Any] | None = None,
) -> dict[str, float]:
    """company_id → cosine similarity in [0, 1] (approx; MiniLM cosine often >0)."""
    emb = embeddings if embeddings is not None else load_company_embeddings()
    if emb is None or not company_ids:
        return {cid: 0.0 for cid in company_ids}
    q = embed_text(leaver_profile_text)
    mat = emb["vectors"]
    sims = mat @ q  # (n,)
    id_to_idx = emb["id_to_idx"]
    out: dict[str, float] = {}
    for cid in company_ids:
        i = id_to_idx.get(str(cid))
        if i is None:
            out[str(cid)] = 0.0
        else:
            # clip to [0, 1] for blending stability
            out[str(cid)] = float(max(0.0, min(1.0, sims[i])))
    return out
