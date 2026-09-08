"""Build company MiniLM embeddings for live matching.

Run from project root (after companies_master exists):
  .venv\\Scripts\\python scripts/05_build_company_embeddings.py

Writes: app/app_data/company_embeddings.npz
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from glos_recommender.embeddings import (  # noqa: E402
    EMBEDDINGS_PATH,
    MODEL_DIR,
    embed_texts,
)
from glos_recommender.matching import load_companies  # noqa: E402


def _profile_text(row) -> str:
    text = str(row.get("profile_text") or "").strip()
    if text:
        return text
    parts = [
        str(row.get("name") or ""),
        str(row.get("town") or ""),
        str(row.get("sectors") or "").replace("|", " "),
        str(row.get("entry_routes") or "").replace("|", " "),
        str(row.get("summary") or ""),
    ]
    return " ".join(p for p in parts if p).strip() or "employer"


def main() -> None:
    companies = load_companies()
    if "company_id" not in companies.columns:
        raise SystemExit("companies table missing company_id")

    texts = [_profile_text(row) for _, row in companies.iterrows()]
    ids = companies["company_id"].astype(str).tolist()
    print(f"Encoding {len(texts)} companies…")
    vectors = embed_texts(texts, batch_size=32)
    EMBEDDINGS_PATH.parent.mkdir(parents=True, exist_ok=True)
    model_label = str(MODEL_DIR) if MODEL_DIR.exists() else "all-MiniLM-L6-v2"
    np.savez_compressed(
        EMBEDDINGS_PATH,
        company_ids=np.array(ids, dtype=object),
        vectors=vectors.astype("float32"),
        model=np.array([model_label]),
    )
    print(f"Wrote {EMBEDDINGS_PATH}  shape={vectors.shape}  model={model_label}")


if __name__ == "__main__":
    main()
