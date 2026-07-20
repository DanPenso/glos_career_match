"""Build / rebuild FAISS index from data/corpus (including evidence strategies).

Run from project root:
  .venv\\Scripts\\python scripts/build_faiss_corpus.py
"""

from __future__ import annotations

import pickle
import sys
from collections import Counter
from pathlib import Path

import faiss
import numpy as np
from sentence_transformers import SentenceTransformer

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from glos_recommender.rag import evidence_chunks_for_index  # noqa: E402

CORPUS_DIR = ROOT / "data" / "corpus"
FAISS_DIR = ROOT / "app" / "app_data" / "faiss_index"
MODEL_DIR = ROOT / "models" / "local_minilm_model"
EVIDENCE_TXT = CORPUS_DIR / "evidence_strategies.txt"


def chunk_text(text: str, chunk_size: int = 180, overlap: int = 30) -> list[str]:
    words = text.split()
    chunks: list[str] = []
    start = 0
    while start < len(words):
        chunks.append(" ".join(words[start : start + chunk_size]))
        start += max(1, chunk_size - overlap)
    return chunks


def export_evidence_txt() -> list[tuple[str, str]]:
    pairs = evidence_chunks_for_index()
    EVIDENCE_TXT.write_text("\n\n".join(c for c, _ in pairs), encoding="utf-8")
    return pairs


def collect_chunks(evidence_pairs: list[tuple[str, str]]) -> tuple[list[str], list[str]]:
    all_chunks: list[str] = []
    sources: list[str] = []

    skip_names = {"evidence_strategies.txt"}

    for fpath in sorted(CORPUS_DIR.rglob("*.txt")):
        if fpath.name in skip_names:
            continue
        rel = fpath.relative_to(CORPUS_DIR)
        stem = (
            fpath.stem
            if rel.parent == Path(".")
            else f"{rel.parent.as_posix()}/{fpath.stem}"
        )
        for para in [
            p.strip() for p in fpath.read_text(encoding="utf-8").split("\n\n") if p.strip()
        ]:
            for chunk in chunk_text(para):
                all_chunks.append(chunk)
                sources.append(stem)

    # Append each evidence strategy as a single chunk with stable source id
    for chunk, src in evidence_pairs:
        all_chunks.append(chunk)
        sources.append(src)

    return all_chunks, sources


def main() -> None:
    FAISS_DIR.mkdir(parents=True, exist_ok=True)
    evidence_pairs = export_evidence_txt()
    print(f"Exported {len(evidence_pairs)} evidence cards → {EVIDENCE_TXT}")

    all_chunks, sources = collect_chunks(evidence_pairs)
    print(f"Total chunks: {len(all_chunks)}")
    print("By source (top):", Counter(sources).most_common(12))

    if (MODEL_DIR / "config.json").exists():
        embedder = SentenceTransformer(str(MODEL_DIR))
        print(f"Embedder: local {MODEL_DIR.name}")
    else:
        embedder = SentenceTransformer("all-MiniLM-L6-v2")
        print("Embedder: all-MiniLM-L6-v2")

    embeddings = embedder.encode(all_chunks, show_progress_bar=True, batch_size=64)
    embeddings = np.asarray(embeddings, dtype="float32")
    faiss.normalize_L2(embeddings)

    index = faiss.IndexFlatIP(embeddings.shape[1])
    index.add(embeddings)

    faiss.write_index(index, str(FAISS_DIR / "corpus.index"))
    with open(FAISS_DIR / "chunks.pkl", "wb") as f:
        pickle.dump({"chunks": all_chunks, "sources": sources}, f)

    n_evidence = sum(1 for s in sources if str(s).startswith("evidence"))
    print(f"FAISS index: {index.ntotal} vectors ({n_evidence} evidence) → {FAISS_DIR}")


if __name__ == "__main__":
    main()
