"""FAISS retrieval over the careers corpus, with evidence-card fallback."""

from __future__ import annotations

import pickle
import re
from functools import lru_cache
from pathlib import Path
from typing import Any

import yaml

PROJECT_ROOT = Path(__file__).resolve().parents[2]
FAISS_DIR = PROJECT_ROOT / "app" / "app_data" / "faiss_index"
MODEL_DIR = PROJECT_ROOT / "models" / "local_minilm_model"
EVIDENCE_YAML = PROJECT_ROOT / "data" / "corpus" / "evidence" / "strategies.yaml"
HOWTO_YAML = PROJECT_ROOT / "data" / "corpus" / "howto" / "howto.yaml"

_embedder = None
_index = None
_store: dict[str, Any] | None = None


def load_evidence_cards(path: Path | None = None) -> list[dict[str, Any]]:
    data = yaml.safe_load((path or EVIDENCE_YAML).read_text(encoding="utf-8")) or {}
    return list(data.get("cards") or [])


def card_to_chunk(card: dict[str, Any]) -> str:
    """Flatten a strategy card into one retrieval-friendly paragraph."""
    tags = ", ".join(card.get("tags") or [])
    return (
        f"STRATEGY: {card.get('strategy', '')} | "
        f"Source: {card.get('source_label', card.get('source_id', ''))} | "
        f"Strength: {card.get('strength', 'moderate')} | "
        f"Tags: {tags}. "
        f"Claim: {' '.join(str(card.get('claim', '')).split())} "
        f"Do: {' '.join(str(card.get('do', '')).split())} "
        f"Do not claim: {' '.join(str(card.get('do_not_claim', '')).split())}"
    )


def evidence_chunks_for_index() -> list[tuple[str, str]]:
    """Return (chunk_text, source_label) pairs for FAISS indexing."""
    out: list[tuple[str, str]] = []
    for card in load_evidence_cards():
        out.append((card_to_chunk(card), f"evidence:{card.get('id', 'card')}"))
    return out


def load_howto_cards(path: Path | None = None) -> list[dict[str, Any]]:
    data = yaml.safe_load((path or HOWTO_YAML).read_text(encoding="utf-8")) or {}
    return list(data.get("cards") or [])


def howto_to_chunk(card: dict[str, Any]) -> str:
    tags = ", ".join(card.get("tags") or [])
    return (
        f"HOWTO: {card.get('topic', '')} | "
        f"Source: {card.get('source_label', card.get('source_id', ''))} | "
        f"Tags: {tags}. "
        f"Tip: {' '.join(str(card.get('tip', '')).split())} "
        f"Do: {' '.join(str(card.get('do', '')).split())} "
        f"Do not claim: {' '.join(str(card.get('do_not_claim', '')).split())}"
    )


def howto_chunks_for_index() -> list[tuple[str, str]]:
    out: list[tuple[str, str]] = []
    for card in load_howto_cards():
        out.append((howto_to_chunk(card), f"howto:{card.get('id', 'card')}"))
    return out


def retrieve_howto_keyword(
    query: str,
    *,
    top_k: int = 4,
    cards: list[dict[str, Any]] | None = None,
) -> list[dict[str, Any]]:
    """Keyword retrieval over practical how-to cards (works without FAISS)."""
    cards = cards if cards is not None else load_howto_cards()
    q = _tokenize(query)
    if not q:
        q = {"cv", "application", "prepare", "check"}

    scored: list[tuple[float, dict[str, Any]]] = []
    for card in cards:
        blob = " ".join(
            [
                str(card.get("topic", "")),
                str(card.get("tip", "")),
                str(card.get("do", "")),
                " ".join(card.get("tags") or []),
            ]
        )
        tokens = _tokenize(blob)
        overlap = len(q & tokens)
        if overlap > 0:
            scored.append((float(overlap), card))

    scored.sort(key=lambda x: x[0], reverse=True)
    results: list[dict[str, Any]] = []
    for score, card in scored[:top_k]:
        results.append(
            {
                "chunk": howto_to_chunk(card),
                "source": f"howto:{card.get('id', 'card')}",
                "source_label": card.get("source_label", ""),
                "topic": card.get("topic", ""),
                "score": score,
                "card": card,
            }
        )
    return results


def retrieve_howto(query: str, *, top_k: int = 4) -> list[dict[str, Any]]:
    """Retrieve how-to cards; prefer FAISS howto:* hits, else keyword."""
    if not query.strip():
        return retrieve_howto_keyword(query, top_k=top_k)

    if not _load_faiss():
        return retrieve_howto_keyword(query, top_k=top_k)

    import faiss
    import numpy as np

    assert _embedder is not None and _index is not None and _store is not None
    chunks: list[str] = _store["chunks"]
    sources: list[str] = _store["sources"]

    q = _embedder.encode([query])
    q = np.asarray(q, dtype="float32")
    faiss.normalize_L2(q)
    fetch_k = min(max(top_k * 30, 120), len(chunks))
    scores, idxs = _index.search(q, fetch_k)

    howto_hits: list[dict[str, Any]] = []
    for j, i in enumerate(idxs[0]):
        if i < 0 or i >= len(chunks):
            continue
        src = str(sources[i])
        if not src.startswith("howto"):
            continue
        howto_hits.append(
            {
                "chunk": chunks[i],
                "source": src,
                "score": float(scores[0][j]),
            }
        )
        if len(howto_hits) >= top_k:
            break

    if len(howto_hits) < top_k:
        for extra in retrieve_howto_keyword(query, top_k=top_k):
            if any(extra["chunk"][:120] == h["chunk"][:120] for h in howto_hits):
                continue
            howto_hits.append(extra)
            if len(howto_hits) >= top_k:
                break

    return howto_hits[:top_k]


def _tokenize(text: str) -> set[str]:
    return {t for t in re.findall(r"[a-z0-9_]+", text.lower()) if len(t) > 2}


def retrieve_evidence_keyword(
    query: str,
    *,
    top_k: int = 4,
    cards: list[dict[str, Any]] | None = None,
) -> list[dict[str, Any]]:
    """Lightweight retrieval when FAISS/embedder is unavailable."""
    cards = cards if cards is not None else load_evidence_cards()
    q = _tokenize(query)
    if not q:
        q = {"apprenticeship", "employer", "application", "plan"}

    scored: list[tuple[float, dict[str, Any]]] = []
    for card in cards:
        blob = " ".join(
            [
                str(card.get("strategy", "")),
                str(card.get("claim", "")),
                str(card.get("do", "")),
                " ".join(card.get("tags") or []),
            ]
        )
        tokens = _tokenize(blob)
        overlap = len(q & tokens)
        # Prefer strong / youth_voice cards slightly when tied
        strength_bonus = {"strong": 0.3, "youth_voice": 0.15, "moderate": 0.0}.get(
            str(card.get("strength")), 0.0
        )
        score = overlap + strength_bonus
        if score > 0:
            scored.append((score, card))

    scored.sort(key=lambda x: x[0], reverse=True)
    results: list[dict[str, Any]] = []
    for score, card in scored[:top_k]:
        results.append(
            {
                "chunk": card_to_chunk(card),
                "source": f"evidence:{card.get('id', 'card')}",
                "source_label": card.get("source_label", ""),
                "strategy": card.get("strategy", ""),
                "strength": card.get("strength", ""),
                "score": float(score),
                "card": card,
            }
        )
    return results


def _load_faiss() -> bool:
    global _embedder, _index, _store
    if _index is not None and _store is not None and _embedder is not None:
        return True

    index_path = FAISS_DIR / "corpus.index"
    chunks_path = FAISS_DIR / "chunks.pkl"
    if not index_path.exists() or not chunks_path.exists():
        return False

    try:
        import faiss
        import numpy as np
        from sentence_transformers import SentenceTransformer

        if _embedder is None:
            if (MODEL_DIR / "config.json").exists():
                _embedder = SentenceTransformer(str(MODEL_DIR))
            else:
                _embedder = SentenceTransformer("all-MiniLM-L6-v2")

        if _index is None:
            _index = faiss.read_index(str(index_path))
        if _store is None:
            with open(chunks_path, "rb") as f:
                _store = pickle.load(f)
        return True
    except Exception:
        return False


def retrieve(
    query: str,
    *,
    top_k: int = 6,
    prefer_evidence: bool = True,
) -> list[dict[str, Any]]:
    """Retrieve corpus chunks for a briefing query.

    Prefers evidence:* sources when available, then fills with other corpus hits.
    Falls back to keyword evidence cards if FAISS is missing.
    """
    if not query.strip():
        return retrieve_evidence_keyword(query, top_k=top_k)

    if not _load_faiss():
        return retrieve_evidence_keyword(query, top_k=top_k)

    import faiss
    import numpy as np

    assert _embedder is not None and _index is not None and _store is not None
    chunks: list[str] = _store["chunks"]
    sources: list[str] = _store["sources"]

    q = _embedder.encode([query])
    q = np.asarray(q, dtype="float32")
    faiss.normalize_L2(q)
    # Over-fetch: evidence cards are few vs company/vacancy docs
    fetch_k = min(max(top_k * 40, 200), len(chunks))
    scores, idxs = _index.search(q, fetch_k)

    hits: list[dict[str, Any]] = []
    for j, i in enumerate(idxs[0]):
        if i < 0 or i >= len(chunks):
            continue
        src = str(sources[i])
        hits.append(
            {
                "chunk": chunks[i],
                "source": src,
                "score": float(scores[0][j]),
            }
        )

    evidence_n = min(4, top_k) if prefer_evidence else 0
    other_n = max(0, top_k - evidence_n)

    evidence = [h for h in hits if str(h["source"]).startswith("evidence")]
    other = [h for h in hits if not str(h["source"]).startswith("evidence")]

    # Guarantee strategy cards even if FAISS ranked them low
    if prefer_evidence and len(evidence) < evidence_n:
        for extra in retrieve_evidence_keyword(query, top_k=evidence_n):
            if any(extra["chunk"][:120] == h["chunk"][:120] for h in evidence):
                continue
            evidence.append(extra)
            if len(evidence) >= evidence_n:
                break

    ordered = evidence[:evidence_n] + other[: max(other_n, top_k - len(evidence[:evidence_n]))]

    seen: set[str] = set()
    unique: list[dict[str, Any]] = []
    for h in ordered:
        key = h["chunk"][:160]
        if key in seen:
            continue
        seen.add(key)
        unique.append(h)
        if len(unique) >= top_k:
            break

    return unique


def build_retrieval_query(leaver: dict[str, Any], company: dict[str, Any]) -> str:
    interests = ", ".join(leaver.get("interests") or [])
    courses = ", ".join(leaver.get("courses") or [])
    sectors = ", ".join(
        sorted(
            set(leaver.get("interest_sectors") or [])
            | set(leaver.get("target_sectors") or [])
        )
    )
    persona = leaver.get("persona") or ""
    return (
        f"careers advice first steps apprenticeship employer encounters "
        f"application practice mentoring workplace experience "
        f"persona group: {persona}. "
        f"interests: {interests}. courses: {courses}. sectors: {sectors}. "
        f"company: {company.get('name', '')}. "
        f"company sectors: {company.get('sectors', '')}. "
        f"entry routes: {company.get('entry_routes', '')}."
    )


@lru_cache(maxsize=1)
def evidence_card_count() -> int:
    return len(load_evidence_cards())
