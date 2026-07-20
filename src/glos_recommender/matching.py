"""Hybrid company matching for Gloucestershire leavers.

Hybrid score =
  0.35 * sector_overlap
+ 0.20 * entry_route_fit
+ 0.20 * text_overlap
+ 0.15 * psych_role_fit
+ 0.10 * hiring_signal

When company MiniLM embeddings are present (scripts/build_company_embeddings.py):
  final_score = 0.7 * hybrid + 0.3 * cosine_sim
"""

from __future__ import annotations

from collections import Counter
from pathlib import Path
from typing import Any

import pandas as pd

from .embeddings import cosine_map_for_leaver, load_company_embeddings
from .intake_config import load_intake_options, load_psych_questions

PROJECT_ROOT = Path(__file__).resolve().parents[2]
SEED_DIR = PROJECT_ROOT / "data" / "seed"
APP_DATA_DIR = PROJECT_ROOT / "app" / "app_data"
PROCESSED_DIR = PROJECT_ROOT / "data" / "processed"

# Blend with notebook 04 (hybrid + embedding cosine)
HYBRID_WEIGHT = 0.7
COSINE_WEIGHT = 0.3

WEIGHTS = {
    "sector": 0.35,
    "entry": 0.20,
    "text": 0.20,
    "psych": 0.15,
    "hiring": 0.10,
}

HIRING_MAP = {"high": 1.0, "medium": 0.6, "low": 0.3}


def _first_existing(*paths: Path) -> Path | None:
    for p in paths:
        if p.exists():
            return p
    return None


def _split_pipe(value: Any) -> set[str]:
    if pd.isna(value) or value is None:
        return set()
    return {p.strip() for p in str(value).split("|") if p.strip()}


def load_companies(path: Path | None = None) -> pd.DataFrame:
    """Prefer expanded master (seed + vacancies); fall back to seed CSV."""
    if path is not None:
        if path.suffix == ".pkl":
            return pd.read_pickle(path)
        return pd.read_csv(path)
    chosen = _first_existing(
        APP_DATA_DIR / "companies_master.csv",
        PROCESSED_DIR / "companies_master.pkl",
        SEED_DIR / "companies_seed.csv",
    )
    if chosen is None:
        raise FileNotFoundError("No companies table found (seed or master).")
    if chosen.suffix == ".pkl":
        return pd.read_pickle(chosen)
    return pd.read_csv(chosen)


def load_opportunities(path: Path | None = None) -> pd.DataFrame:
    if path is not None:
        if path.suffix == ".pkl":
            return pd.read_pickle(path)
        return pd.read_csv(path)
    chosen = _first_existing(
        APP_DATA_DIR / "opportunities_master.csv",
        PROCESSED_DIR / "opportunities_master.pkl",
        SEED_DIR / "opportunities_seed.csv",
    )
    if chosen is None:
        raise FileNotFoundError("No opportunities table found (seed or master).")
    if chosen.suffix == ".pkl":
        return pd.read_pickle(chosen)
    return pd.read_csv(chosen)


def score_psych_answers(answers: dict[str, str]) -> dict[str, Any]:
    """answers: {question_id: option_id}"""
    psych = load_psych_questions()
    riasec = Counter()
    role_hints: list[str] = []

    for q in psych["questions"]:
        chosen = answers.get(q["id"])
        if not chosen:
            continue
        for opt in q["options"]:
            if opt["id"] == chosen:
                for trait, w in opt.get("weights", {}).items():
                    riasec[trait] += w
                if "role_hint" in opt:
                    role_hints.append(opt["role_hint"])
                break

    dominant = [t for t, _ in riasec.most_common(2)] if riasec else []
    sector_prefs: set[str] = set()
    role_prefs: set[str] = set()
    mapping_s = psych.get("riasec_to_sectors", {})
    mapping_r = psych.get("riasec_to_role_families", {})
    for trait in dominant:
        sector_prefs.update(mapping_s.get(trait, []))
        role_prefs.update(mapping_r.get(trait, []))

    return {
        "riasec_scores": dict(riasec),
        "dominant_riasec": dominant,
        "sector_prefs": sector_prefs,
        "role_prefs": role_prefs,
        "role_hints": role_hints,
    }


def build_leaver_profile(form: dict[str, Any]) -> dict[str, Any]:
    """Build a structured leaver profile from intake form answers."""
    options = load_intake_options()
    interests = form.get("interests", []) or []
    courses = form.get("courses", []) or []
    passions = form.get("passions", []) or []
    experience = form.get("work_experience", []) or []

    interest_map = options.get("interest_to_sector", {})
    course_map = options.get("course_to_sector", {})
    sectors: set[str] = set()
    for interest in interests:
        sectors.update(interest_map.get(interest, []))
    for course in courses:
        sectors.update(course_map.get(course, []))

    leaver_type = form.get("leaver_type", "")
    entry_routes = set(options.get("leaver_to_entry_routes", {}).get(leaver_type, []))

    psych = score_psych_answers(form.get("psych_answers", {}) or {})
    # Keep psych sectors separate so stated interests dominate matching
    interest_sectors = set(sectors)
    psych_sectors = set(psych["sector_prefs"])

    profile_text = " | ".join(
        [
            f"Leaver: {leaver_type}",
            f"Location: {form.get('location', '')}",
            f"Courses: {', '.join(courses)}",
            f"Interests: {', '.join(interests)}",
            f"Passions: {', '.join(passions)}",
            f"Experience: {', '.join(experience)}",
            f"Qual level: {form.get('qualification_level', '')}",
            f"RIASEC: {', '.join(psych['dominant_riasec'])}",
        ]
    )

    return {
        "leaver_type": leaver_type,
        "location": form.get("location", ""),
        "courses": courses,
        "interests": interests,
        "passions": passions,
        "work_experience": experience,
        "qualification_level": form.get("qualification_level", ""),
        "availability": form.get("availability", ""),
        "target_sectors": interest_sectors | psych_sectors,
        "interest_sectors": interest_sectors,
        "psych_sectors": psych_sectors,
        "entry_routes": entry_routes,
        "psych": psych,
        "profile_text": profile_text,
    }


def _jaccard(a: set[str], b: set[str]) -> float:
    if not a or not b:
        return 0.0
    return len(a & b) / len(a | b)


def _token_overlap(a: str, b: str) -> float:
    ta = {t.lower() for t in a.replace("|", " ").replace(",", " ").split() if len(t) > 2}
    tb = {t.lower() for t in b.replace("|", " ").replace(",", " ").split() if len(t) > 2}
    return _jaccard(ta, tb)


def score_company(leaver: dict[str, Any], row: pd.Series) -> dict[str, float]:
    company_sectors = _split_pipe(row["sectors"])
    company_routes = _split_pipe(row["entry_routes"])
    company_roles = _split_pipe(row["role_families"])

    # Stated interests weigh more than psych-inferred sectors
    interest_sectors = leaver.get("interest_sectors") or leaver["target_sectors"]
    psych_sectors = leaver.get("psych_sectors") or set()
    sector = 0.75 * _jaccard(interest_sectors, company_sectors) + 0.25 * _jaccard(
        psych_sectors, company_sectors
    )
    entry = _jaccard(leaver["entry_routes"], company_routes)

    text = _token_overlap(leaver["profile_text"], str(row.get("profile_text", "")))

    psych_roles = leaver["psych"].get("role_prefs", set())
    psych = _jaccard(psych_roles, company_roles)

    hiring = HIRING_MAP.get(str(row.get("hiring_signal", "low")).lower(), 0.3)
    priority = int(row.get("priority_employer", 0)) == 1
    if priority:
        hiring = min(1.0, hiring + 0.15)

    final = (
        WEIGHTS["sector"] * sector
        + WEIGHTS["entry"] * entry
        + WEIGHTS["text"] * text
        + WEIGHTS["psych"] * psych
        + WEIGHTS["hiring"] * hiring
    )

    # Soft reject: no shared entry route at all
    if leaver["entry_routes"] and not (leaver["entry_routes"] & company_routes):
        final *= 0.35

    # Prefer true hotels/restaurants over hair/retail when tourism is a stated interest
    if "hospitality_tourism" in interest_sectors:
        if "hospitality_tourism" in company_sectors:
            final = min(1.0, final + 0.08)
        elif "hospitality_retail" in company_sectors and "hospitality_tourism" not in company_sectors:
            final *= 0.85

    # Prefer education-tagged employers when education is a stated interest
    if "education_training" in interest_sectors and "education_training" in company_sectors:
        final = min(1.0, final + 0.08)

    # Prefer construction / trades employers when built-environment interest is stated
    if "construction_green" in interest_sectors and "construction_green" in company_sectors:
        final = min(1.0, final + 0.08)

    # Curated priority employers that share a stated interest rise above long-tail noise
    if priority and (interest_sectors & company_sectors):
        final = min(1.0, final + 0.12)

    # Reliability guard: vacancy-derived long-tail employers rank below curated anchors
    # unless they have strong hiring evidence.
    source = str(row.get("source", "")).strip().lower()
    if source == "vacancies" and not priority:
        final *= 0.90
        if str(row.get("hiring_signal", "")).strip().lower() == "low":
            final *= 0.88

    return {
        "final_score": round(final, 4),
        "sector_score": round(sector, 4),
        "entry_score": round(entry, 4),
        "text_score": round(text, 4),
        "psych_score": round(psych, 4),
        "hiring_score": round(hiring, 4),
    }


def match_companies(
    form: dict[str, Any],
    companies: pd.DataFrame | None = None,
    top_n: int = 3,
) -> tuple[dict[str, Any], pd.DataFrame]:
    """Return (leaver_profile, top_n scored companies).

    Uses hybrid rules always; blends MiniLM cosine when
    app/app_data/company_embeddings.npz exists.
    """
    leaver = build_leaver_profile(form)
    df = companies if companies is not None else load_companies()

    rows = []
    for _, row in df.iterrows():
        scores = score_company(leaver, row)
        rows.append({**row.to_dict(), **scores})

    ranked = pd.DataFrame(rows)
    ranked["hybrid_score"] = ranked["final_score"]

    emb = load_company_embeddings()
    if emb is not None and len(ranked):
        try:
            ids = ranked["company_id"].astype(str).tolist()
            sim_map = cosine_map_for_leaver(
                str(leaver.get("profile_text") or ""),
                ids,
                embeddings=emb,
            )
            ranked["cosine_sim"] = ranked["company_id"].astype(str).map(sim_map).fillna(0.0)
            ranked["final_score"] = (
                HYBRID_WEIGHT * ranked["hybrid_score"]
                + COSINE_WEIGHT * ranked["cosine_sim"]
            ).round(4)
            leaver["matching_mode"] = "hybrid_plus_embeddings"
        except Exception:
            ranked["cosine_sim"] = 0.0
            leaver["matching_mode"] = "hybrid_only"
    else:
        ranked["cosine_sim"] = 0.0
        leaver["matching_mode"] = "hybrid_only"

    ranked = ranked.sort_values("final_score", ascending=False)
    return leaver, ranked.head(top_n).reset_index(drop=True)


def match_reasons(leaver: dict[str, Any], company_row: pd.Series) -> list[str]:
    """Human-readable match reasons for UI / RAG prompt."""
    reasons = []
    shared_sectors = leaver["target_sectors"] & _split_pipe(company_row["sectors"])
    shared_routes = set(leaver.get("entry_routes") or set()) & _split_pipe(
        company_row["entry_routes"]
    )
    shared_roles = leaver["psych"].get("role_prefs", set()) & _split_pipe(
        company_row["role_families"]
    )

    if shared_sectors:
        reasons.append(f"Sector fit: {', '.join(sorted(shared_sectors))}")
    if shared_routes:
        reasons.append(f"Entry routes they offer that suit you: {', '.join(sorted(shared_routes))}")
    if shared_roles:
        reasons.append(f"Role families aligned with your work style: {', '.join(sorted(shared_roles))}")
    if leaver["psych"].get("dominant_riasec"):
        reasons.append(
            "Work-style signals: " + ", ".join(leaver["psych"]["dominant_riasec"])
        )
    if leaver.get("interests"):
        reasons.append("Your interests: " + ", ".join(leaver["interests"][:4]))
    return reasons
