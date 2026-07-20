"""K-Means career personas, fit scores, and cluster-ranked training routes."""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Any

import numpy as np
import yaml

from .intake_config import load_pathways, pathways_for_sectors

PROJECT_ROOT = Path(__file__).resolve().parents[2]
TAXONOMY_DIR = PROJECT_ROOT / "data" / "taxonomy"
APP_DATA_DIR = PROJECT_ROOT / "app" / "app_data"
MODEL_PATH = APP_DATA_DIR / "persona_kmeans.joblib"
PRIORS_PATH = TAXONOMY_DIR / "persona_priors.yaml"

SECTORS = [
    "cyber_digital",
    "aerospace_manufacturing",
    "agri_tech_food",
    "health_care",
    "public_sector",
    "creative_events",
    "construction_green",
    "hospitality_tourism",
    "hospitality_retail",
    "business_professional",
    "education_training",
]

RIASEC = [
    "Realistic",
    "Investigative",
    "Artistic",
    "Social",
    "Enterprising",
    "Conventional",
]

# Soft-blend: include runner-up pathways when within this relative distance
RUNNER_UP_RATIO = 1.35


def load_persona_priors(path: Path | None = None) -> dict[str, Any]:
    with open(path or PRIORS_PATH, encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


def _as_sector_set(value: Any) -> set[str]:
    if isinstance(value, set):
        return {str(x) for x in value}
    if isinstance(value, (list, tuple)):
        return {str(x) for x in value}
    if value is None:
        return set()
    return {p.strip() for p in str(value).split("|") if p.strip()}


def leaver_feature_vector(leaver: dict[str, Any]) -> np.ndarray:
    """Sector + RIASEC one-hots — same space used to fit the persona K-Means model."""
    sectors = _as_sector_set(leaver.get("interest_sectors")) | _as_sector_set(
        leaver.get("target_sectors")
    )
    sec = [1.0 if s in sectors else 0.0 for s in SECTORS]

    psych = leaver.get("psych") or {}
    dominant = set(psych.get("dominant_riasec") or [])
    riasec_scores = psych.get("riasec_scores") or {}
    if not dominant and riasec_scores:
        dominant = {
            t
            for t, _ in sorted(riasec_scores.items(), key=lambda kv: kv[1], reverse=True)[:2]
        }
    ria = [1.0 if t in dominant else 0.0 for t in RIASEC]
    return np.asarray(sec + ria, dtype="float64")


def _load_model() -> dict[str, Any] | None:
    if not MODEL_PATH.exists():
        return None
    try:
        import joblib

        return joblib.load(MODEL_PATH)
    except Exception:
        return None


def _distance_to_similarity(distance: float) -> float:
    return 1.0 / (1.0 + max(0.0, float(distance)))


def _normalise_fit(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Scale similarity so the closest persona is 100 (relative closeness)."""
    if not rows:
        return rows
    peak = max(float(r["similarity_raw"]) for r in rows) or 1.0
    out = []
    for r in rows:
        closeness = round(100.0 * float(r["similarity_raw"]) / peak)
        out.append(
            {
                "persona": r["persona"],
                "cluster_id": r.get("cluster_id"),
                "distance": round(float(r["distance"]), 4),
                "closeness": closeness,
                "is_primary": bool(r.get("is_primary")),
                "is_runner_up": bool(r.get("is_runner_up")),
            }
        )
    out.sort(key=lambda x: (-x["closeness"], x["persona"]))
    return out


def _fit_from_priors(leaver: dict[str, Any]) -> list[dict[str, Any]]:
    priors = load_persona_priors().get("personas") or {}
    sectors = _as_sector_set(leaver.get("interest_sectors")) | _as_sector_set(
        leaver.get("target_sectors")
    )
    rows = []
    for name, meta in priors.items():
        typical = set(meta.get("typical_sectors") or [])
        if not typical and not sectors:
            j = 0.0
        elif not typical or not sectors:
            j = 0.0
        else:
            j = len(sectors & typical) / len(sectors | typical)
        # Treat (1-jaccard) as a pseudo-distance
        dist = 1.0 - j
        rows.append(
            {
                "persona": name,
                "cluster_id": None,
                "distance": dist,
                "similarity_raw": _distance_to_similarity(dist),
            }
        )
    rows.sort(key=lambda r: r["distance"])
    if rows:
        rows[0]["is_primary"] = True
        if len(rows) > 1 and rows[1]["distance"] <= rows[0]["distance"] * RUNNER_UP_RATIO:
            rows[1]["is_runner_up"] = True
    return _normalise_fit(rows)


def compute_persona_fit(leaver: dict[str, Any]) -> dict[str, Any]:
    """Distances / closeness to every persona + optional 2D map coords."""
    model = _load_model()
    vec = leaver_feature_vector(leaver)
    priors_root = load_persona_priors()
    disclaimer = str(priors_root.get("disclaimer") or "").strip()

    if model is None:
        fit = _fit_from_priors(leaver)
        primary = next((f for f in fit if f["is_primary"]), fit[0] if fit else None)
        runner = next((f for f in fit if f.get("is_runner_up")), None)
        blurb = ""
        if primary:
            meta = (priors_root.get("personas") or {}).get(primary["persona"]) or {}
            blurb = " ".join(str(meta.get("blurb") or "").split())
        return {
            "persona": primary["persona"] if primary else "Technical Specialist",
            "cluster_id": None,
            "distance": primary["distance"] if primary else None,
            "method": "priors_fallback",
            "persona_blurb": blurb,
            "persona_disclaimer": disclaimer,
            "persona_fit": fit,
            "runner_up": runner["persona"] if runner else None,
            "persona_map_2d": None,
        }

    scaler = model["scaler"]
    kmeans = model["kmeans"]
    persona_map = {int(k): v for k, v in model["persona_map"].items()}
    x = scaler.transform(vec.reshape(1, -1))[0]

    rows = []
    for cid, center in enumerate(kmeans.cluster_centers_):
        dist = float(np.linalg.norm(x - center))
        rows.append(
            {
                "persona": persona_map.get(cid, f"Cluster {cid}"),
                "cluster_id": cid,
                "distance": dist,
                "similarity_raw": _distance_to_similarity(dist),
            }
        )
    rows.sort(key=lambda r: r["distance"])
    rows[0]["is_primary"] = True
    if len(rows) > 1 and rows[1]["distance"] <= rows[0]["distance"] * RUNNER_UP_RATIO + 1e-9:
        rows[1]["is_runner_up"] = True

    fit = _normalise_fit(rows)
    primary = fit[0]
    runner = next((f for f in fit if f.get("is_runner_up")), None)
    meta = (priors_root.get("personas") or {}).get(primary["persona"]) or {}
    blurb = " ".join(str(meta.get("blurb") or "").split())

    map_2d = None
    pca = model.get("pca")
    if pca is not None:
        you_xy = pca.transform(x.reshape(1, -1))[0]
        centroids_2d = pca.transform(kmeans.cluster_centers_)
        map_2d = {
            "you": {"x": float(you_xy[0]), "y": float(you_xy[1])},
            "centroids": [
                {
                    "persona": persona_map.get(cid, f"Cluster {cid}"),
                    "x": float(centroids_2d[cid, 0]),
                    "y": float(centroids_2d[cid, 1]),
                    "is_primary": persona_map.get(cid) == primary["persona"],
                }
                for cid in range(len(kmeans.cluster_centers_))
            ],
        }

    return {
        "persona": primary["persona"],
        "cluster_id": primary.get("cluster_id"),
        "distance": primary["distance"],
        "method": "kmeans",
        "persona_blurb": blurb,
        "persona_disclaimer": disclaimer,
        "persona_fit": fit,
        "runner_up": runner["persona"] if runner else None,
        "persona_map_2d": map_2d,
    }


def assign_persona(leaver: dict[str, Any]) -> dict[str, Any]:
    """Backward-compatible thin wrapper around compute_persona_fit."""
    fit = compute_persona_fit(leaver)
    return {
        "persona": fit["persona"],
        "cluster_id": fit.get("cluster_id"),
        "distance": fit.get("distance"),
        "similarity": None,
        "method": fit.get("method"),
    }


def _pathway_by_id() -> dict[str, dict[str, Any]]:
    catalogue = load_pathways()
    out: dict[str, dict[str, Any]] = {}
    for sector, cards in catalogue.items():
        if not isinstance(cards, list):
            continue
        for card in cards:
            cid = card.get("id")
            if cid:
                out[str(cid)] = {**card, "sector": sector}
    return out


def _cards_for_persona(persona: str, *, limit: int = 6) -> list[dict[str, Any]]:
    priors = load_persona_priors().get("personas") or {}
    meta = priors.get(persona) or {}
    by_id = _pathway_by_id()
    cards: list[dict[str, Any]] = []
    for pid in meta.get("pathway_ids") or []:
        card = by_id.get(pid)
        if card:
            cards.append(card)
        if len(cards) >= limit:
            break
    if not cards:
        typical = set(meta.get("typical_sectors") or [])
        cards = pathways_for_sectors(typical)[:limit]
    return cards


def ranked_training_routes(
    leaver: dict[str, Any],
    *,
    primary: str,
    runner_up: str | None = None,
    limit: int = 4,
) -> list[dict[str, Any]]:
    """Merge interest + primary (+ runner-up) pathways into one ranked list."""
    sectors = set(leaver.get("interest_sectors") or leaver.get("target_sectors") or [])
    interest_cards = pathways_for_sectors(sectors)
    interest_ids = {str(c.get("id")) for c in interest_cards if c.get("id")}

    primary_cards = _cards_for_persona(primary)
    runner_cards = _cards_for_persona(runner_up) if runner_up else []
    primary_ids = {str(c.get("id")) for c in primary_cards if c.get("id")}
    runner_ids = {str(c.get("id")) for c in runner_cards if c.get("id")}

    scored: dict[str, dict[str, Any]] = {}

    def upsert(card: dict[str, Any], score: float, source: str, reason: str) -> None:
        cid = str(card.get("id") or card.get("title"))
        prev = scored.get(cid)
        if prev and prev["score"] >= score:
            # Keep higher score; maybe enrich tags
            tags = set(prev.get("tags") or [])
            tags.add(source)
            prev["tags"] = sorted(tags)
            return
        tags = {source}
        if cid in interest_ids:
            tags.add("interests")
        if cid in primary_ids:
            tags.add("group")
        if cid in runner_ids:
            tags.add("nearby")
        scored[cid] = {
            **card,
            "score": score,
            "source": source,
            "reason": reason,
            "tags": sorted(tags),
        }

    for card in interest_cards:
        upsert(card, 3.0, "interests", "Matches your selected interests")
    for card in primary_cards:
        upsert(
            card,
            2.5,
            "group",
            f"Common for {primary} profiles",
        )
    for card in runner_cards:
        upsert(
            card,
            1.5,
            "nearby",
            f"Also nearby — often explored by {runner_up} profiles",
        )

    ranked = sorted(scored.values(), key=lambda c: (-c["score"], c.get("title") or ""))
    # Prefer showing interest+group first; trim
    out = []
    for card in ranked[:limit]:
        clean = {k: v for k, v in card.items() if k != "score"}
        # Human chip label
        tags = clean.get("tags") or []
        if "interests" in tags and "group" in tags:
            clean["chip"] = "Your interests + your group"
        elif "interests" in tags:
            clean["chip"] = "From your interests"
        elif "group" in tags:
            clean["chip"] = "Common in your group"
        elif "nearby" in tags:
            clean["chip"] = "Nearby group"
        else:
            clean["chip"] = "Suggested route"
        out.append(clean)
    return out


def peer_pathways_for_persona(
    persona: str,
    *,
    exclude_ids: set[str] | None = None,
    limit: int = 4,
) -> tuple[list[dict[str, Any]], str, str]:
    """Legacy helper: peer-only cards (not in interest set)."""
    priors_root = load_persona_priors()
    disclaimer = str(priors_root.get("disclaimer") or "").strip()
    meta = (priors_root.get("personas") or {}).get(persona) or {}
    blurb = " ".join(str(meta.get("blurb") or "").split())
    exclude_ids = exclude_ids or set()
    cards = []
    for card in _cards_for_persona(persona, limit=limit + len(exclude_ids)):
        cid = str(card.get("id") or "")
        if cid in exclude_ids:
            continue
        cards.append({**card, "reason": f"Common for {persona} profiles"})
        if len(cards) >= limit:
            break
    return cards, blurb, disclaimer


def persona_bundle(
    leaver: dict[str, Any],
    *,
    interest_pathway_ids: set[str] | None = None,
    peer_limit: int = 4,
    route_limit: int = 4,
) -> dict[str, Any]:
    """Full persona payload: fit bars, 2D map, unified training routes, peer extras."""
    fit_payload = compute_persona_fit(leaver)
    primary = fit_payload["persona"]
    runner = fit_payload.get("runner_up")

    training_routes = ranked_training_routes(
        leaver,
        primary=primary,
        runner_up=runner,
        limit=route_limit,
    )

    # Peer-only list for backward compatibility / optional UI
    exclude = interest_pathway_ids or {
        str(c.get("id")) for c in pathways_for_sectors(
            set(leaver.get("interest_sectors") or leaver.get("target_sectors") or [])
        )
        if c.get("id")
    }
    peer, _, _ = peer_pathways_for_persona(
        primary, exclude_ids=exclude, limit=peer_limit
    )

    return {
        "persona": primary,
        "cluster_id": fit_payload.get("cluster_id"),
        "distance": fit_payload.get("distance"),
        "method": fit_payload.get("method"),
        "persona_blurb": fit_payload.get("persona_blurb") or "",
        "persona_disclaimer": fit_payload.get("persona_disclaimer") or "",
        "persona_fit": fit_payload.get("persona_fit") or [],
        "runner_up": runner,
        "persona_map_2d": fit_payload.get("persona_map_2d"),
        "training_routes": training_routes,
        "peer_pathways": peer,
    }


@lru_cache(maxsize=1)
def model_available() -> bool:
    return MODEL_PATH.exists()
