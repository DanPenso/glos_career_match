"""FastAPI wrapper around glos_recommender for the Next.js web app.

Run from project root:
  .venv\\Scripts\\uvicorn api.main:app --reload --port 8000
"""

from __future__ import annotations

import os
import sys
from pathlib import Path
from typing import Any

import pandas as pd
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
load_dotenv(ROOT / ".env")

from glos_recommender.briefing import clean_catalogue_summary, generate_briefing
from glos_recommender.courses import load_courses, match_courses
from glos_recommender.intake_config import (
    load_intake_options,
    load_psych_questions,
    pathways_for_sectors,
)
from glos_recommender.labels import clean_company_summary, fit_label, hiring_label, overall_label
from glos_recommender.matching import (
    load_companies,
    match_companies,
)
from glos_recommender.live_learning import log_match_event, record_persona_feedback
from glos_recommender.military import match_military
from glos_recommender.online_courses import match_online_courses
from glos_recommender.personas import persona_bundle
from glos_recommender.programmes import programmes_for_company


def _cors_origins() -> list[str]:
    raw = os.getenv("CORS_ORIGINS", "").strip()
    if raw:
        return [origin.strip() for origin in raw.split(",") if origin.strip()]
    return [
        "http://localhost:3000",
        "http://127.0.0.1:3000",
        "http://localhost:3001",
        "http://127.0.0.1:3001",
    ]


app = FastAPI(title="Glos Career Match API", version="0.1.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=_cors_origins(),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class MatchRequest(BaseModel):
    leaver_type: str
    location: str = ""
    courses: list[str] = Field(default_factory=list)
    interests: list[str] = Field(default_factory=list)
    passions: list[str] = Field(default_factory=list)
    work_experience: list[str] = Field(default_factory=list)
    qualification_level: str = ""
    availability: str = ""
    psych_answers: dict[str, str] = Field(default_factory=dict)
    use_openai_briefing: bool = False
    allow_anonymous_logging: bool = True
    top_n: int = 3
    mode: str = "work"  # work | education | military


class PersonaFeedbackRequest(BaseModel):
    event_id: str
    helpful: bool


def _jsonable_leaver(leaver: dict[str, Any]) -> dict[str, Any]:
    out = dict(leaver)
    for key in ("target_sectors", "interest_sectors", "psych_sectors", "entry_routes"):
        if key in out and isinstance(out[key], set):
            out[key] = sorted(out[key])
    psych = out.get("psych") or {}
    if isinstance(psych, dict):
        p = dict(psych)
        for key in ("sector_prefs", "role_prefs"):
            if key in p and isinstance(p[key], set):
                p[key] = sorted(p[key])
        out["psych"] = p
    return out


def _company_payload(
    leaver: dict[str, Any],
    row: pd.Series,
    rank: int,
    *,
    use_openai_briefing: bool,
) -> dict[str, Any]:
    data = {k: (None if pd.isna(v) else v) for k, v in row.to_dict().items()}
    # Drop list-like cells that break JSON
    for k in list(data.keys()):
        if isinstance(data[k], (list, tuple)) or str(k).endswith("_list"):
            if k.endswith("_list"):
                data.pop(k, None)
    briefing = ""
    briefing_source = None
    if use_openai_briefing:
        briefing, briefing_source = generate_briefing(leaver, row, use_openai=True)
        if briefing_source != "openai":
            briefing = ""
            briefing_source = None
    sector_fit = fit_label(float(data.get("sector_score") or 0))
    # Avoid "Strong" sector signal on vacancy-derived employers without verified programmes.
    if (
        str(data.get("source", "")).strip().lower() == "vacancies"
        and sector_fit == "Strong"
        and not programmes_for_company(str(data.get("company_id") or ""))
    ):
        sector_fit = "Good"
    return {
        "company_id": data.get("company_id"),
        "name": data.get("name"),
        "town": data.get("town"),
        "postcode": data.get("postcode"),
        "sectors": data.get("sectors"),
        "entry_routes": data.get("entry_routes"),
        "summary": clean_company_summary(data.get("summary")),
        "website": data.get("website"),
        "hiring_signal": data.get("hiring_signal"),
        "priority_employer": int(data.get("priority_employer") or 0),
        "final_score": float(data.get("final_score") or 0),
        "sector_score": float(data.get("sector_score") or 0),
        "entry_score": float(data.get("entry_score") or 0),
        "hiring_score": float(data.get("hiring_score") or 0),
        "hybrid_score": float(data.get("hybrid_score") or data.get("final_score") or 0),
        "cosine_sim": float(data.get("cosine_sim") or 0),
        "sector_fit_label": sector_fit,
        "entry_fit_label": fit_label(float(data.get("entry_score") or 0)),
        "hiring_label": hiring_label(data),
        "overall_label": overall_label(rank),
        "briefing_markdown": briefing,
        "briefing_source": briefing_source,
    }


def _attach_briefing(
    payload: dict[str, Any],
    leaver: dict[str, Any],
    row: pd.Series,
    *,
    mode: str,
    use_openai_briefing: bool,
    related_microcreds: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    briefing = ""
    briefing_source = None
    if use_openai_briefing:
        briefing, briefing_source = generate_briefing(
            leaver,
            row,
            use_openai=True,
            mode=mode,
            related_microcreds=related_microcreds,
        )
        if briefing_source != "openai":
            briefing = ""
            briefing_source = None
    payload["briefing_markdown"] = briefing
    payload["briefing_source"] = briefing_source
    return payload


def _course_payload(
    leaver: dict[str, Any],
    row: pd.Series,
    rank: int,
    *,
    use_openai_briefing: bool,
) -> dict[str, Any]:
    data = {k: (None if pd.isna(v) else v) for k, v in row.to_dict().items()}
    type_label = str(data.get("course_type_label") or "").strip()
    # Prefer qualification-style labels over funding programme tags in the live seed.
    title = str(data.get("title") or "")
    if type_label in {"Free Courses for Jobs", "Essential skills", "Multiply"}:
        lower = title.lower()
        if "access to" in lower:
            type_label = "Access to HE"
        elif "nvq" in lower:
            type_label = "NVQ"
        elif "bootcamp" in lower:
            type_label = "Skills Bootcamp"
        elif "t level" in lower or "t-level" in lower:
            type_label = "T Level"
        elif "btec" in lower:
            type_label = "BTEC"
        elif "a level" in lower or "a-level" in lower or " gce" in lower:
            type_label = "A Level"
        elif "diploma" in lower:
            type_label = "Diploma"
        elif "certificate" in lower:
            type_label = "Certificate"
    level = str(data.get("level") or "").strip()
    type_level = " · ".join(
        x for x in (type_label, level if level and level != "See provider" else "") if x
    )
    payload = {
        "kind": "course",
        "course_id": data.get("course_id"),
        "company_id": data.get("course_id"),  # UI tab key compatibility
        "name": data.get("title"),
        "provider": data.get("provider"),
        "town": data.get("town"),
        "postcode": data.get("postcode"),
        "region": data.get("region"),
        "level": data.get("level"),
        "course_type": data.get("course_type"),
        "course_type_label": type_label or None,
        "study_mode": data.get("study_mode"),
        "sectors": data.get("sectors"),
        "entry_routes": data.get("entry_routes"),
        "summary": clean_catalogue_summary(data.get("summary")),
        "website": data.get("website"),
        "final_score": float(data.get("final_score") or 0),
        "sector_score": float(data.get("sector_score") or 0),
        "entry_score": float(data.get("entry_score") or 0),
        "hiring_score": None,
        "hybrid_score": float(data.get("hybrid_score") or data.get("final_score") or 0),
        "cosine_sim": float(data.get("cosine_sim") or 0),
        "sector_fit_label": fit_label(float(data.get("sector_score") or 0)),
        "entry_fit_label": fit_label(float(data.get("entry_score") or 0)),
        "hiring_label": type_level or type_label or level or "See provider",
        "hiring_signal": None,
        "overall_label": overall_label(rank),
        "source": data.get("source"),
    }
    return _attach_briefing(
        payload, leaver, row, mode="education", use_openai_briefing=use_openai_briefing
    )


def _military_payload(
    leaver: dict[str, Any],
    row: pd.Series,
    rank: int,
    *,
    use_openai_briefing: bool,
    related_microcreds: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    data = {k: (None if pd.isna(v) else v) for k, v in row.to_dict().items()}
    payload = {
        "kind": "military",
        "pathway_id": data.get("pathway_id"),
        "company_id": data.get("pathway_id"),
        "name": data.get("title"),
        "service": data.get("service"),
        "town": data.get("service") or "UK Armed Forces",
        "provider": data.get("service"),
        "sectors": data.get("sectors"),
        "entry_routes": data.get("entry_routes"),
        "summary": clean_catalogue_summary(data.get("summary")),
        "website": data.get("website"),
        "final_score": float(data.get("final_score") or 0),
        "sector_score": float(data.get("sector_score") or 0),
        "entry_score": float(data.get("entry_score") or 0),
        "hiring_score": None,
        "hybrid_score": float(data.get("hybrid_score") or data.get("final_score") or 0),
        "cosine_sim": 0.0,
        "sector_fit_label": fit_label(float(data.get("sector_score") or 0)),
        "entry_fit_label": fit_label(float(data.get("entry_score") or 0)),
        "hiring_label": str(data.get("service") or "Armed Forces"),
        "hiring_signal": None,
        "overall_label": overall_label(rank),
    }
    return _attach_briefing(
        payload,
        leaver,
        row,
        mode="military",
        use_openai_briefing=use_openai_briefing,
        related_microcreds=related_microcreds,
    )


def _microcred_payload(row: pd.Series) -> dict[str, Any]:
    data = {k: (None if pd.isna(v) else v) for k, v in row.to_dict().items()}
    return {
        "cred_id": data.get("cred_id"),
        "title": data.get("title"),
        "provider": data.get("provider"),
        "town": data.get("town"),
        "region": data.get("region"),
        "level": data.get("level"),
        "sectors": data.get("sectors"),
        "summary": data.get("summary"),
        "website": data.get("website"),
        "elcas_status": data.get("elcas_status") or "check_on_elcas",
        "final_score": float(data.get("final_score") or 0),
    }


@app.get("/health")
def health() -> dict[str, Any]:
    out: dict[str, Any] = {"ok": True}
    try:
        out["companies"] = len(load_companies())
    except Exception as e:
        out["ok"] = False
        out["error"] = str(e)
    try:
        out["courses"] = len(load_courses())
    except Exception as e:
        out["courses_error"] = str(e)
    return out


@app.get("/taxonomy")
def taxonomy() -> dict[str, Any]:
    return {
        "intake": load_intake_options(),
        "psych": load_psych_questions(),
    }


@app.post("/match")
def match(req: MatchRequest) -> dict[str, Any]:
    if not req.interests and not req.courses:
        raise HTTPException(
            status_code=400,
            detail="Please select at least one course or interest.",
        )
    mode = (req.mode or "work").strip().lower()
    if mode not in {"work", "education", "military"}:
        raise HTTPException(
            status_code=400,
            detail="mode must be one of: work, education, military",
        )
    form = req.model_dump()
    use_openai_briefing = bool(form.pop("use_openai_briefing", False))
    allow_anonymous_logging = bool(form.pop("allow_anonymous_logging", True))
    top_n = form.pop("top_n", 3)
    form.pop("mode", None)

    microcredentials: list[dict[str, Any]] = []
    try:
        if mode == "education":
            leaver, ranked = match_courses(form, load_courses(), top_n=top_n)
            matches = [
                _course_payload(
                    leaver, row, i, use_openai_briefing=use_openai_briefing
                )
                for i, (_, row) in enumerate(ranked.iterrows())
            ]
        elif mode == "military":
            leaver, ranked, micro_df = match_military(form, top_n=top_n, micro_n=6)
            if micro_df is not None and len(micro_df):
                microcredentials = [
                    _microcred_payload(row) for _, row in micro_df.iterrows()
                ]
            matches = [
                _military_payload(
                    leaver,
                    row,
                    i,
                    use_openai_briefing=use_openai_briefing,
                    related_microcreds=microcredentials,
                )
                for i, (_, row) in enumerate(ranked.iterrows())
            ]
        else:
            leaver, ranked = match_companies(form, load_companies(), top_n=top_n)
            matches = [
                _company_payload(leaver, row, i, use_openai_briefing=use_openai_briefing)
                for i, (_, row) in enumerate(ranked.iterrows())
            ]
            for m in matches:
                m["kind"] = "employer"
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e)) from e

    sectors = set(leaver.get("interest_sectors") or leaver.get("target_sectors") or [])
    pathways = pathways_for_sectors(sectors)
    interest_ids = {str(p.get("id")) for p in pathways if p.get("id")}
    persona = persona_bundle(leaver, interest_pathway_ids=interest_ids, peer_limit=4)
    leaver["persona"] = persona.get("persona")
    live_event = None
    if allow_anonymous_logging:
        try:
            live_event = log_match_event(leaver, persona, channel=f"web:{mode}")
        except Exception:
            live_event = None
    leaver_out = _jsonable_leaver(leaver)
    leaver_out["persona"] = persona.get("persona")
    leaver_out["cluster_id"] = persona.get("cluster_id")
    online_courses, online_disclaimer = match_online_courses(leaver=leaver, top_n=3)
    return {
        "mode": mode,
        "leaver": leaver_out,
        "briefings_enabled": use_openai_briefing,
        "pathways": pathways,
        "training_routes": (persona.get("training_routes") or pathways)[:4],
        "persona": persona.get("persona"),
        "runner_up": persona.get("runner_up"),
        "persona_blurb": persona.get("persona_blurb") or "",
        "persona_disclaimer": persona.get("persona_disclaimer") or "",
        "persona_fit": persona.get("persona_fit") or [],
        "persona_map_2d": persona.get("persona_map_2d"),
        "learning_event_id": (live_event or {}).get("event_id"),
        "matches": matches,
        "microcredentials": microcredentials,
        "online_courses": online_courses,
        "online_courses_disclaimer": online_disclaimer,
        "data_note": {
            "work": "Employer matches from curated + Companies House / DfE open data.",
            "education": (
                "Course matches from the National Careers Service course directory "
                "(Open Government Licence v3.0), filtered to Gloucestershire and Bristol."
            ),
            "military": (
                "Military pathways are guidance only (not official recruitment advice). "
                "Micro-credentials use NCS open course data; ELC/PD eligibility must be "
                "checked on ELCAS and with Education Staff."
            ),
        }.get(mode, ""),
    }


@app.post("/feedback/persona")
def persona_feedback(req: PersonaFeedbackRequest) -> dict[str, Any]:
    """Optional: was the career group useful? Strengthens next retrain."""
    ok = record_persona_feedback(req.event_id, req.helpful)
    if not ok:
        raise HTTPException(status_code=404, detail="Unknown learning event_id.")
    return {"ok": True, "event_id": req.event_id, "helpful": req.helpful}
