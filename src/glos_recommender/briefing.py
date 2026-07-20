"""RAG briefing prompts addressed directly to the leaver."""

from __future__ import annotations

import os
import re
from typing import Any

import pandas as pd

from .intake_config import pathways_for_sectors
from .matching import match_reasons
from .programmes import (
    format_programmes_for_briefing,
    format_programmes_for_prompt,
    programmes_for_company,
)
from .rag import build_retrieval_query, retrieve


SYSTEM_PROMPT = """You are a friendly Gloucestershire careers coach speaking directly to a young person.
Write in second person ("you"). Be practical, encouraging, and specific.
Keep each section to at most 3–5 short lines. Do not use bullet dashes (-) — plain sentences only.
Do not invent vacancy closing dates, salaries, or personal probabilities of getting a job.
Only use the company facts, pathway cards, and retrieved context provided.
If pathway cards are supplied, weave in concrete training routes — not only the employer brand.

RESEARCH-BACKED ADVICE RULES:
When RETRIEVED CONTEXT includes STRATEGY cards, use their "Do" actions especially in
"What to build next" and "Your first steps this month".
Prefer multi-element plans (vacancy check + employer encounter + application practice).
Cite sources in plain language once or twice, e.g. "Careers research (Gatsby) suggests…"
or "Youth employment evidence suggests…". Do not invent statistics.
Obey each card's "Do not claim" constraints.

Structure your answer with these exact markdown headings:
# Your match — {company name}
## Why this company fits you
## Training routes that fit your interests
## Roles and programmes you could work towards
## What to build next
## Your first steps this month

For "Roles and programmes you could work towards", only mention programmes listed in
VERIFIED PROGRAMMES. Do not invent job titles or imply roles are open now.
Do not repeat registry metadata like SIC codes, accounts category, or registered-office notes.
"""


def _clean_company_summary(text: Any) -> str:
    """Remove Companies House admin fragments from summary text."""
    s = " ".join(str(text or "").split())
    if not s:
        return ""
    s = re.sub(r"Nature of business\s*\(SIC\)\s*:[^.]*\.?\s*", "", s, flags=re.I)
    s = re.sub(r"SIC\s*[:\-]\s*[^.]*\.?\s*", "", s, flags=re.I)
    s = re.sub(r"\(accounts?\s+category:[^)]+\)", "", s, flags=re.I)
    s = re.sub(r"accounts?\s+category\s*[:\-]\s*[^.]*\.?\s*", "", s, flags=re.I)
    s = re.sub(r"registered office in [^.]*\.?\s*", "", s, flags=re.I)
    s = re.sub(r"Companies House[–-]listed employer(?: with)?\.?\s*", "", s, flags=re.I)
    s = re.sub(r"^\s*with\s+", "", s, flags=re.I)
    s = re.sub(r"\s{2,}", " ", s).strip(" .")
    return s


def build_briefing_prompt(
    leaver: dict[str, Any],
    company: pd.Series | dict[str, Any],
    retrieved_chunks: list[dict[str, Any]] | None = None,
) -> tuple[str, str]:
    company = company if isinstance(company, dict) else company.to_dict()
    reasons = match_reasons(leaver, pd.Series(company))

    verified = programmes_for_company(str(company.get("company_id") or ""))
    programmes_text = format_programmes_for_prompt(verified)

    context = ""
    if retrieved_chunks:
        context = "\n\n".join(
            f"[{c.get('source', 'doc')}]: {c.get('chunk', c.get('text', ''))}"
            for c in retrieved_chunks
        )

    sectors = set(leaver.get("interest_sectors") or leaver.get("target_sectors") or [])
    pathway_bits = []
    for p in pathways_for_sectors(sectors):
        steps = "; ".join(p.get("steps", [])[:3])
        pathway_bits.append(f"- {p['title']}: {p.get('summary', '').strip()} Steps: {steps}")
    pathway_text = "\n".join(pathway_bits) if pathway_bits else "None listed."

    user_prompt = f"""Create a personalised employer briefing for this leaver.

LEAVER PROFILE:
{leaver['profile_text']}

Interests: {', '.join(leaver.get('interests', []))}
Passions: {', '.join(leaver.get('passions', []))}
Experience: {', '.join(leaver.get('work_experience', []))}
Availability: {leaver.get('availability', '')}

MATCHED COMPANY:
Name: {company['name']}
Town: {company.get('town', '')}
Summary: {_clean_company_summary(company.get('summary', ''))}
Sectors: {company.get('sectors', '')}
Entry routes: {company.get('entry_routes', '')}
Website: {company.get('website', '')}
Match score: {company.get('final_score', 'n/a')}

WHY MATCHED:
{chr(10).join('- ' + r for r in reasons)}

TRAINING PATHWAY CARDS (use these explicitly):
{pathway_text}

VERIFIED PROGRAMMES (only cite these in "Roles and programmes you could work towards"):
{programmes_text}

RETRIEVED CONTEXT (company facts + research-backed STRATEGY cards):
{context or 'No extra corpus chunks.'}

Write the briefing now, speaking directly to the leaver.
Ground "What to build next" and "Your first steps this month" in the STRATEGY cards when present.
"""
    return SYSTEM_PROMPT, user_prompt


def _retrieve_for_briefing(
    leaver: dict[str, Any],
    company: dict[str, Any],
    *,
    top_k: int = 6,
) -> list[dict[str, Any]]:
    query = build_retrieval_query(leaver, company)
    return retrieve(query, top_k=top_k, prefer_evidence=True)


def generate_briefing(
    leaver: dict[str, Any],
    company: pd.Series | dict[str, Any],
    *,
    use_openai: bool = True,
    retrieved_chunks: list[dict[str, Any]] | None = None,
) -> tuple[str, str]:
    """Return (briefing_markdown, source) where source is 'openai' or 'offline'.

    When use_openai is True and OPENAI_API_KEY is set, calls gpt-4o-mini with RAG context.
    Falls back to the offline template on any failure or missing key.
    """
    company_dict = company if isinstance(company, dict) else company.to_dict()
    chunks = retrieved_chunks
    if chunks is None:
        try:
            chunks = _retrieve_for_briefing(leaver, company_dict)
        except Exception:
            chunks = []

    offline = fallback_briefing(leaver, company_dict, retrieved_chunks=chunks)
    if not use_openai:
        return offline, "offline"

    api_key = os.getenv("OPENAI_API_KEY", "").strip()
    if not api_key:
        return offline, "offline"

    try:
        from openai import OpenAI

        system, user = build_briefing_prompt(
            leaver, company_dict, retrieved_chunks=chunks
        )
        client = OpenAI(api_key=api_key)
        resp = client.chat.completions.create(
            model=os.getenv("OPENAI_MODEL", "gpt-4o-mini"),
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            temperature=0.4,
            max_tokens=900,
        )
        text = (resp.choices[0].message.content or "").strip()
        if not text:
            return offline, "offline"
        return text, "openai"
    except Exception:
        return offline, "offline"


def _evidence_action_lines(retrieved_chunks: list[dict[str, Any]] | None) -> list[str]:
    """Pull concrete 'Do:' lines from STRATEGY chunks for the offline template."""
    if not retrieved_chunks:
        return []
    actions: list[str] = []
    for c in retrieved_chunks:
        chunk = str(c.get("chunk") or "")
        if "STRATEGY:" not in chunk and "evidence:" not in str(c.get("source", "")):
            continue
        if "Do:" in chunk:
            do_part = chunk.split("Do:", 1)[1]
            do_part = do_part.split("Do not claim:", 1)[0].strip()
            if do_part:
                # Optional plain-language source hint
                label = c.get("source_label") or ""
                if not label and "Source:" in chunk:
                    label = chunk.split("Source:", 1)[1].split("|", 1)[0].strip()
                line = do_part
                if label and len(actions) == 0:
                    line = f"{do_part} (guided by {label})"
                actions.append(line)
        if len(actions) >= 3:
            break
    return actions


def fallback_briefing(
    leaver: dict[str, Any],
    company: pd.Series | dict[str, Any],
    retrieved_chunks: list[dict[str, Any]] | None = None,
) -> str:
    """Offline template if OpenAI is unavailable."""
    company = company if isinstance(company, dict) else company.to_dict()
    reasons = match_reasons(leaver, pd.Series(company))
    reason_lines = list(reasons) or [
        "Based on your stated interests and entry route."
    ]
    sectors = set(leaver.get("interest_sectors") or leaver.get("target_sectors") or [])
    pathway_lines: list[str] = []
    for p in pathways_for_sectors(sectors)[:4]:
        summary = " ".join(str(p.get("summary") or "").split())
        if len(summary) > 110:
            summary = summary[:107].rstrip() + "…"
        pathway_lines.append(f"{p['title']}: {summary}" if summary else str(p["title"]))
    if not pathway_lines:
        pathway_lines = [
            "Ask a careers adviser about apprenticeships, college courses, and graduate training."
        ]

    if retrieved_chunks is None:
        try:
            retrieved_chunks = _retrieve_for_briefing(leaver, company)
        except Exception:
            retrieved_chunks = []

    evidence_actions = _evidence_action_lines(retrieved_chunks)
    build_next = evidence_actions[:2] or [
        "Map your quals to their typical entry requirements.",
        "Add one portfolio, volunteering, or project piece for this sector.",
    ]
    first_steps = evidence_actions[2:3] + [
        f"Visit {company.get('website', 'their website')} careers page.",
        "Note one apprenticeship or graduate role to target.",
        "Book a chat with a careers adviser or local Careers Hub event.",
    ]
    # Keep first steps to 4 lines max
    first_steps = first_steps[:4]

    verified = programmes_for_company(str(company.get("company_id") or ""))
    programme_lines = format_programmes_for_briefing(verified)

    lines = [
        f"# Your match — {company['name']}",
        "",
        "## Why this company fits you",
        *reason_lines[:5],
        "",
        "## Training routes that fit your interests",
        *pathway_lines[:5],
        "",
        "## Roles and programmes you could work towards",
        *programme_lines[:5],
        "",
        "## What to build next",
        *build_next,
        "Practise a short example of a challenge you solved (STAR).",
        "",
        "## Your first steps this month",
        *first_steps,
    ]
    return "\n".join(lines)
