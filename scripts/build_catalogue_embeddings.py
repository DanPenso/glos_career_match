"""Build MiniLM embeddings for courses and military catalogue items.

Run from project root:
  .venv\\Scripts\\python scripts/build_catalogue_embeddings.py

Writes:
  app/app_data/course_embeddings.npz
  app/app_data/military_pathway_embeddings.npz
  app/app_data/military_microcred_embeddings.npz
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from glos_recommender.courses import load_courses  # noqa: E402
from glos_recommender.embeddings import (  # noqa: E402
    COURSE_EMBEDDINGS_PATH,
    MILITARY_MICRO_EMBEDDINGS_PATH,
    MILITARY_PATHWAY_EMBEDDINGS_PATH,
    MODEL_DIR,
    embed_texts,
    save_item_embeddings,
)
from glos_recommender.military import (  # noqa: E402
    load_military_microcreds,
    load_military_pathways,
)
from glos_recommender.role_families import ensure_role_families_column  # noqa: E402


def _item_text(row) -> str:
    text = str(row.get("profile_text") or "").strip()
    if text:
        roles = str(row.get("role_families") or "").replace("|", " ")
        if roles and roles.lower() != "nan":
            return f"{text} | roles: {roles}"
        return text
    parts = [
        str(row.get("title") or ""),
        str(row.get("provider") or row.get("service") or ""),
        str(row.get("sectors") or "").replace("|", " "),
        str(row.get("entry_routes") or "").replace("|", " "),
        str(row.get("role_families") or "").replace("|", " "),
        str(row.get("summary") or ""),
    ]
    return " ".join(p for p in parts if p and p.lower() != "nan").strip() or "item"


def _encode_frame(df, id_col: str, path: Path, id_key: str, label: str) -> None:
    if df is None or df.empty:
        print(f"Skip {label}: empty catalogue")
        return
    if id_col not in df.columns:
        raise SystemExit(f"{label} missing {id_col}")
    df = ensure_role_families_column(df)
    texts = [_item_text(row) for _, row in df.iterrows()]
    ids = df[id_col].astype(str).tolist()
    print(f"Encoding {len(texts)} {label}…")
    vectors = embed_texts(texts, batch_size=32)
    model_label = str(MODEL_DIR) if MODEL_DIR.exists() else "all-MiniLM-L6-v2"
    out = save_item_embeddings(
        path, ids, vectors, model_label=model_label, id_key=id_key
    )
    print(f"Wrote {out}  shape={vectors.shape}  model={model_label}")


def main() -> None:
    _encode_frame(
        load_courses(),
        "course_id",
        COURSE_EMBEDDINGS_PATH,
        "course_ids",
        "courses",
    )
    _encode_frame(
        load_military_pathways(),
        "pathway_id",
        MILITARY_PATHWAY_EMBEDDINGS_PATH,
        "pathway_ids",
        "military pathways",
    )
    micros = load_military_microcreds()
    if not micros.empty:
        _encode_frame(
            micros,
            "cred_id",
            MILITARY_MICRO_EMBEDDINGS_PATH,
            "cred_ids",
            "military microcreds",
        )
    else:
        print("Skip military microcreds: seed missing/empty")


if __name__ == "__main__":
    main()
