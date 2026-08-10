"""RAG briefing prompts addressed directly to the leaver."""

from __future__ import annotations

import os
import re
from typing import Any

import pandas as pd

from .labels import clean_company_summary
from .intake_config import pathways_for_sectors
from .matching import match_reasons
from .programmes import (
    format_programmes_for_briefing,
    format_programmes_for_prompt,
    programmes_for_company,
)
from .rag import build_retrieval_query, retrieve


EMPLOYER_SYSTEM_PROMPT = """You are a friendly Gloucestershire careers coach speaking directly to a young person.
Write in second person ("you"). Be practical, encouraging, and specific.
Keep each section to at most 3–5 short lines. Do not use bullet dashes (-) — plain sentences only.
Do not invent vacancy closing dates, salaries, or personal probabilities of getting a job.
Only use the company facts, pathway cards, and retrieved context provided.
If pathway cards are supplied, weave in concrete training routes — not only the employer brand.
You are careers guidance only — not a counsellor or crisis service. Do not give medical advice.
If the person discloses self-harm, abuse, or immediate danger, urge them to seek real-world help
(999 / Childline 0800 1111 / Samaritans 116 123) and do not dig for details.

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


COURSE_SYSTEM_PROMPT = """You are a friendly Gloucestershire careers coach speaking directly to a young person.
Write in second person ("you"). Be practical, encouraging, and specific.
Keep each section to at most 3–5 short lines. Do not use bullet dashes (-) — plain sentences only.
Do not invent fees, entry requirements, start dates, guaranteed places, or funding entitlement.
Only use the course facts, pathway cards, and retrieved context provided.
If the course summary looks like generic college boilerplate, do not lean on it —
ground the briefing in the course title, provider, level/type, sectors, and the leaver profile.

RESEARCH-BACKED ADVICE RULES:
When RETRIEVED CONTEXT includes STRATEGY cards, use their "Do" actions especially in
"What to build next" and "Your first steps this month".
Prefer multi-element plans (provider check + skills practice + adviser chat).
Cite sources in plain language once or twice. Do not invent statistics.
Obey each card's "Do not claim" constraints.

Structure your answer with these exact markdown headings:
# Your course match — {course title}
## Why this course fits you
## How it connects to your career interests
## What to check with the provider
## What to build next
## Your first steps this month
"""


MILITARY_SYSTEM_PROMPT = """You are a friendly Gloucestershire careers coach speaking directly to a young person
exploring Armed Forces pathways. Write in second person ("you"). Be practical and respectful.
Keep each section to at most 3–5 short lines. Do not use bullet dashes (-) — plain sentences only.
This is guidance only — not official recruitment advice and not an offer of employment.
Do not invent eligibility, medical standards, pay, posting locations, or Enhanced Learning Credits
(ELCAS) approval. If micro-credentials are listed, treat them as things to explore and always
say ELC eligibility must be checked on ELCAS and with Education Staff.
You are careers guidance only — not a counsellor or crisis service. Do not give medical advice.
If the person discloses self-harm, abuse, or immediate danger, urge real-world help
(999 / Childline 0800 1111 / Samaritans 116 123) and do not dig for details.
If they may be under 18, remind them to check official entry ages and talk with a trusted adult.

RESEARCH-BACKED ADVICE RULES:
When RETRIEVED CONTEXT includes STRATEGY cards, use their "Do" actions especially in
"What to build next" and "Your first steps this month".
Cite sources in plain language once or twice. Do not invent statistics.
Obey each card's "Do not claim" constraints.

Structure your answer with these exact markdown headings:
# Your military pathway match — {pathway title}
## Why this pathway fits you
## How it connects to your interests
## What to check officially
## What to build next
## Your first steps this month
"""

# Backward-compatible alias
SYSTEM_PROMPT = EMPLOYER_SYSTEM_PROMPT

_TYPE_SUFFIX = re.compile(r"\s*Type:\s*.+$", re.I)


def clean_catalogue_summary(summary: Any, *, max_len: int = 280) -> str:
    """Trim NCS/catalogue summaries; strip trailing 'Type: …' noise."""
    text = " ".join(str(summary or "").split())
    text = _TYPE_SUFFIX.sub("", text).strip()
    if len(text) > max_len:
        text = text[: max_len - 1].rstrip() + "…"
    return text


def _subject_name(row: dict[str, Any]) -> str:
    return str(row.get("name") or row.get("title") or "this match").strip()


def _pathway_text(leaver: dict[str, Any]) -> str:
    sectors = set(leaver.get("interest_sectors") or leaver.get("target_sectors") or [])
    pathway_bits = []
    for p in pathways_for_sectors(sectors):
        steps = "; ".join(p.get("steps", [])[:3])
        pathway_bits.append(
            f"- {p['title']}: {p.get('summary', '').strip()} Steps: {steps}"
        )
    return "\n".join(pathway_bits) if pathway_bits else "None listed."


def _format_chunks(retrieved_chunks: list[dict[str, Any]] | None) -> str:
    if not retrieved_chunks:
        return "No extra corpus chunks."
    return "\n\n".join(
        f"[{c.get('source', 'doc')}]: {c.get('chunk', c.get('text', ''))}"
        for c in retrieved_chunks
    )


def _leaver_block(leaver: dict[str, Any]) -> str:
    return f"""LEAVER PROFILE:
{leaver['profile_text']}

Interests: {', '.join(leaver.get('interests', []))}
Passions: {', '.join(leaver.get('passions', []))}
Experience: {', '.join(leaver.get('work_experience', []))}
Availability: {leaver.get('availability', '')}
Qualification level: {leaver.get('qualification_level', '')}"""


def build_employer_briefing_prompt(
    leaver: dict[str, Any],
    company: pd.Series | dict[str, Any],
    retrieved_chunks: list[dict[str, Any]] | None = None,
) -> tuple[str, str]:
    company = company if isinstance(company, dict) else company.to_dict()
    reasons = match_reasons(leaver, pd.Series(company))
    verified = programmes_for_company(str(company.get("company_id") or ""))
    programmes_text = format_programmes_for_prompt(verified)
    name = _subject_name(company)

    user_prompt = f"""Create a personalised employer briefing for this leaver.

{_leaver_block(leaver)}

MATCHED COMPANY:
Name: {name}
Town: {company.get('town', '')}
Summary: {clean_company_summary(company.get('summary', ''))}
Sectors: {company.get('sectors', '')}
Entry routes: {company.get('entry_routes', '')}
Website: {company.get('website', '')}
Match score: {company.get('final_score', 'n/a')}

WHY MATCHED:
{chr(10).join('- ' + r for r in reasons)}

TRAINING PATHWAY CARDS (use these explicitly):
{_pathway_text(leaver)}

VERIFIED PROGRAMMES (only cite these in "Roles and programmes you could work towards"):
{programmes_text}

RETRIEVED CONTEXT (company facts + research-backed STRATEGY cards):
{_format_chunks(retrieved_chunks)}

Write the briefing now, speaking directly to the leaver.
Ground "What to build next" and "Your first steps this month" in the STRATEGY cards when present.
Use the heading "# Your match — {name}".
"""
    return EMPLOYER_SYSTEM_PROMPT, user_prompt


def build_course_briefing_prompt(
    leaver: dict[str, Any],
    course: pd.Series | dict[str, Any],
    retrieved_chunks: list[dict[str, Any]] | None = None,
) -> tuple[str, str]:
    course = course if isinstance(course, dict) else course.to_dict()
    reasons = match_reasons(leaver, pd.Series(course))
    title = _subject_name(course)
    summary = clean_catalogue_summary(course.get("summary"), max_len=400)
    type_label = course.get("course_type_label") or ""
    level = course.get("level") or ""

    user_prompt = f"""Create a personalised education-course briefing for this leaver.

{_leaver_block(leaver)}

MATCHED COURSE:
Title: {title}
Provider: {course.get('provider', '')}
Town: {course.get('town', '')}
Level: {level}
Course type: {type_label}
Study mode: {course.get('study_mode', '')}
Summary (catalogue — may be generic): {summary}
Sectors: {course.get('sectors', '')}
Entry routes: {course.get('entry_routes', '')}
Website: {course.get('website', '')}
Match score: {course.get('final_score', 'n/a')}

WHY MATCHED:
{chr(10).join('- ' + r for r in reasons)}

TRAINING PATHWAY CARDS (link the course to career directions):
{_pathway_text(leaver)}

RETRIEVED CONTEXT (research-backed STRATEGY cards):
{_format_chunks(retrieved_chunks)}

Write the briefing now, speaking directly to the leaver.
Explain why this course fits their profile and interests — do not paste generic age policies.
In "What to check with the provider", tell them to confirm entry requirements, fees/funding, and start dates on the provider site.
Use the heading "# Your course match — {title}".
"""
    return COURSE_SYSTEM_PROMPT, user_prompt


def build_military_briefing_prompt(
    leaver: dict[str, Any],
    pathway: pd.Series | dict[str, Any],
    retrieved_chunks: list[dict[str, Any]] | None = None,
    related_microcreds: list[dict[str, Any]] | None = None,
) -> tuple[str, str]:
    pathway = pathway if isinstance(pathway, dict) else pathway.to_dict()
    reasons = match_reasons(leaver, pd.Series(pathway))
    title = _subject_name(pathway)
    summary = clean_catalogue_summary(pathway.get("summary"), max_len=400)

    micro_lines = "None listed for this match."
    if related_microcreds:
        bits = []
        for m in related_microcreds[:5]:
            bits.append(
                f"- {m.get('title', '')} ({m.get('provider', '')}, {m.get('town', '')}) "
                f"— ELCAS status: check only, never claim approved"
            )
        micro_lines = "\n".join(bits)

    user_prompt = f"""Create a personalised military-pathway briefing for this leaver.

{_leaver_block(leaver)}

MATCHED MILITARY PATHWAY:
Title: {title}
Service: {pathway.get('service', '')}
Summary: {summary}
Sectors: {pathway.get('sectors', '')}
Entry routes: {pathway.get('entry_routes', '')}
Website: {pathway.get('website', '')}
Match score: {pathway.get('final_score', 'n/a')}

WHY MATCHED:
{chr(10).join('- ' + r for r in reasons)}

RELATED LOCAL MICRO-CREDENTIALS (explore only; ELC must be checked on ELCAS):
{micro_lines}

TRAINING PATHWAY CARDS (civilian skills overlap where relevant):
{_pathway_text(leaver)}

RETRIEVED CONTEXT (research-backed STRATEGY cards):
{_format_chunks(retrieved_chunks)}

Write the briefing now, speaking directly to the leaver.
Remind them to use official Armed Forces careers pages and speak to a recruiter / careers adviser.
Never claim ELCAS approval or guaranteed enlistment.
Use the heading "# Your military pathway match — {title}".
"""
    return MILITARY_SYSTEM_PROMPT, user_prompt


def build_briefing_prompt(
    leaver: dict[str, Any],
    company: pd.Series | dict[str, Any],
    retrieved_chunks: list[dict[str, Any]] | None = None,
    *,
    mode: str = "work",
    related_microcreds: list[dict[str, Any]] | None = None,
) -> tuple[str, str]:
    mode = (mode or "work").strip().lower()
    if mode == "education":
        return build_course_briefing_prompt(leaver, company, retrieved_chunks)
    if mode == "military":
        return build_military_briefing_prompt(
            leaver, company, retrieved_chunks, related_microcreds=related_microcreds
        )
    return build_employer_briefing_prompt(leaver, company, retrieved_chunks)


def _retrieve_for_briefing(
    leaver: dict[str, Any],
    subject: dict[str, Any],
    *,
    top_k: int = 6,
) -> list[dict[str, Any]]:
    # Retrieval query expects a name — map title for courses/pathways
    row = dict(subject)
    if not row.get("name"):
        row["name"] = row.get("title") or ""
    query = build_retrieval_query(leaver, row)
    return retrieve(query, top_k=top_k, prefer_evidence=True)


def generate_briefing(
    leaver: dict[str, Any],
    company: pd.Series | dict[str, Any],
    *,
    use_openai: bool = True,
    retrieved_chunks: list[dict[str, Any]] | None = None,
    mode: str = "work",
    related_microcreds: list[dict[str, Any]] | None = None,
) -> tuple[str, str]:
    """Return (briefing_markdown, source) where source is 'openai' or 'offline'.

    When use_openai is True and OPENAI_API_KEY is set, calls gpt-4o-mini with RAG context.
    Falls back to the offline template on any failure or missing key.
    """
    company_dict = company if isinstance(company, dict) else company.to_dict()
    mode = (mode or "work").strip().lower()
    chunks = retrieved_chunks
    if chunks is None:
        try:
            chunks = _retrieve_for_briefing(leaver, company_dict)
        except Exception:
            chunks = []

    offline = fallback_briefing(
        leaver,
        company_dict,
        retrieved_chunks=chunks,
        mode=mode,
        related_microcreds=related_microcreds,
    )
    if not use_openai:
        return offline, "offline"

    api_key = os.getenv("OPENAI_API_KEY", "").strip()
    if not api_key:
        return offline, "offline"

    try:
        from openai import OpenAI

        system, user = build_briefing_prompt(
            leaver,
            company_dict,
            retrieved_chunks=chunks,
            mode=mode,
            related_microcreds=related_microcreds,
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
    *,
    mode: str = "work",
    related_microcreds: list[dict[str, Any]] | None = None,
) -> str:
    """Offline template if OpenAI is unavailable."""
    company = company if isinstance(company, dict) else company.to_dict()
    mode = (mode or "work").strip().lower()
    name = _subject_name(company)
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

    if mode == "education":
        provider = company.get("provider") or "the provider"
        website = company.get("website") or "the course webpage"
        type_label = company.get("course_type_label") or "this course"
        build_next = evidence_actions[:2] or [
            "List the skills this course should give you for your target sector.",
            "Add one short project, volunteering, or reading goal linked to the subject.",
        ]
        first_steps = [
            f"Open the {provider} page and confirm entry requirements and start dates.",
            f"Check funding / fees information on {website}.",
            "Book a chat with a college adviser or careers hub about whether this route fits.",
            "Note one next qualification or role this course could lead to.",
        ][:4]
        return "\n".join(
            [
                f"# Your course match — {name}",
                "",
                "## Why this course fits you",
                *reason_lines[:5],
                "",
                "## How it connects to your career interests",
                *pathway_lines[:5],
                "",
                "## What to check with the provider",
                f"Confirm that {type_label} is still running and what level/entry rules apply.",
                "Ask about study mode, fees or Free Courses for Jobs eligibility if relevant, and next steps after the course.",
                "",
                "## What to build next",
                *build_next,
                "",
                "## Your first steps this month",
                *first_steps,
            ]
        )

    if mode == "military":
        website = company.get("website") or "the official careers page"
        build_next = evidence_actions[:2] or [
            "Map your interests and experience to the skills this pathway develops.",
            "Practise a short STAR example that shows teamwork or resilience.",
        ]
        first_steps = [
            f"Read the official information at {website}.",
            "Speak to a careers adviser or Armed Forces careers office about eligibility.",
            "If exploring ELC-funded learning, check courses on ELCAS — never assume approval.",
            "Note one civilian skill from this pathway you could also build locally.",
        ][:4]
        micro_lines = []
        for m in (related_microcreds or [])[:3]:
            micro_lines.append(
                f"Explore: {m.get('title')} at {m.get('provider')} (check ELCAS separately)."
            )
        check_official = micro_lines or [
            "Use official Armed Forces careers pages — this demo is guidance only.",
            "Ask about medical, fitness, and entry requirements with a recruiter.",
        ]
        return "\n".join(
            [
                f"# Your military pathway match — {name}",
                "",
                "## Why this pathway fits you",
                *reason_lines[:5],
                "",
                "## How it connects to your interests",
                *pathway_lines[:5],
                "",
                "## What to check officially",
                *check_official[:5],
                "",
                "## What to build next",
                *build_next,
                "",
                "## Your first steps this month",
                *first_steps,
            ]
        )

    # Employer (default)
    build_next = evidence_actions[:2] or [
        "Map your quals to their typical entry requirements.",
        "Add one portfolio, volunteering, or project piece for this sector.",
    ]
    first_steps = evidence_actions[2:3] + [
        f"Visit {company.get('website', 'their website')} careers page.",
        "Note one apprenticeship or graduate role to target.",
        "Book a chat with a careers adviser or local Careers Hub event.",
    ]
    first_steps = first_steps[:4]

    verified = programmes_for_company(str(company.get("company_id") or ""))
    programme_lines = format_programmes_for_briefing(verified)

    lines = [
        f"# Your match — {name}",
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
