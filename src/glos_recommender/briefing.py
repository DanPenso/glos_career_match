"""RAG briefing prompts addressed directly to the leaver."""

from __future__ import annotations

import os
import re
from functools import lru_cache
from typing import Any

import pandas as pd

from .intake_config import load_intake_options, pathways_for_sectors
from .labels import public_employer_website
from .matching import match_reasons
from .programmes import format_programmes_for_prompt, programmes_for_company
from .provenance import (
    annotate_retrieved_chunk,
    classify_employer_source,
    employer_facts_block,
    source_label,
)
from .rag import build_retrieval_query, filter_retrieved_hits_for_employer, retrieve
from .travel import commute_hint


EMPLOYER_SYSTEM_PROMPT = """You are a friendly Gloucestershire careers coach speaking directly to a young person.
Write in second person ("you"). Be practical, encouraging, and specific.
Keep each section to at most 3–5 short lines. Do not use bullet dashes (-) — plain sentences only.
Do not invent vacancy closing dates, salaries, culture claims, or personal probabilities of getting a job.
Only use VERIFIED EMPLOYER FACTS, the verified programmes block for this employer, and STRATEGY advice provided.
Separate facts from advice: company claims come only from VERIFIED EMPLOYER FACTS and verified programmes;
careers actions come from STRATEGY cards — never invent employer programmes or open roles.
Matcher tags and entry-route labels are internal matching hints, not programmes this employer ran.
In "Why this company fits you", only mention leaver interests that overlap this employer's
matcher sector tags. Do not say they work in healthcare, aerospace, data, or finance unless
those tags are on the employer. Do not invent culture, values, or mission.
You are careers guidance only — not a counsellor or crisis service. Do not give medical advice.
If the person discloses self-harm, abuse, or immediate danger, urge them to seek real-world help
(999 / Childline 0800 1111 / Samaritans 116 123) and do not dig for details.

PROVENANCE RULES:
- If data source is Companies House / registry facts: describe location and sector tags only;
  do not invent apprenticeships, graduate schemes, or "they are hiring".
- If data source is Find an apprenticeship open data: treat any role titles as historical;
  say they may be closed — this product is guidance, not a live jobs board.
- Catalogue snapshots in retrieved context are not live vacancies.
- Seed fact summaries are location and sector tags only; they are not programmes.

VERIFIED PROGRAMMES VOICE:
- Name a scheme only if it appears in the verified programmes block for this employer.
- Use British collective have: "{company name} have previously run a…".
- Do not write "on file" or "last year".
- Treat programmes as guidance only — not open now.
- If a verified programme does not fit the leaver's qualification level, say it is aimed at
  degree-level entry, so it is not the next step for their qualification-level currently.
- If there are no verified programmes, do not invent titles. Mention generic local college
  or apprenticeship options in Gloucestershire only.

RESEARCH-BACKED ADVICE RULES:
When RETRIEVED CONTEXT includes STRATEGY cards, use helpful "Do" actions in
"What to build or develop next".
Prefer a balanced mix: one personal project you can show or talk about, one study or
research stretch, and optionally one real-world encounter or application practice.
Cite sources in plain language once or twice, e.g. "Careers research suggests…"
or "Youth employment evidence suggests…". Do not name the underlying research body.
Do not invent statistics.
Obey each card's "Do not claim" constraints.
Use plain words for projects (e.g. a small CAD build, a short website, helping at a club
and noting what you learned) — no jargon like "reflection logs".

Structure your answer with these exact markdown headings:
# Your match — {company name}
## Why this company fits you
## Training routes that fit your interests
## What to build or develop next

Do not add a fourth H2. Do not add a separate programmes / roles / jobs section — fit and routes are already covered above.
Do not invent job titles or imply roles are open now.
Do not repeat registry metadata like SIC codes, accounts category, or registered-office notes.
Do not name other employers' jobs or pathway-card titles.
"""


COURSE_SYSTEM_PROMPT = """You are a friendly Gloucestershire careers coach speaking directly to a young person.
Write in second person ("you"). Be practical, encouraging, and specific.
Keep each section to at most 3–5 short lines. Do not use bullet dashes (-) — plain sentences only.
Do not invent fees, entry requirements, start dates, guaranteed places, or funding entitlement.
Only use the course facts, pathway cards, and retrieved context provided.
If the course summary looks like generic college boilerplate, do not lean on it —
ground the briefing in the course title, provider, level/type, sectors, and the leaver profile.

RESEARCH-BACKED ADVICE RULES:
When RETRIEVED CONTEXT includes STRATEGY cards, use helpful "Do" actions in
"What to build or develop next" and "Your first steps this month".
Prefer a mix of skills practice / a small project and provider checks.
Cite sources in plain language once or twice. Do not invent statistics.
Obey each card's "Do not claim" constraints.

Structure your answer with these exact markdown headings:
# Your course match — {course title}
## Why this course fits you
## How it connects to your career interests
## What to check with the provider
## What to build or develop next
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
When RETRIEVED CONTEXT includes STRATEGY cards, use helpful "Do" actions in
"What to build or develop next" and "Your first steps this month".
Cite sources in plain language once or twice. Do not invent statistics.
Obey each card's "Do not claim" constraints.

Structure your answer with these exact markdown headings:
# Your military pathway match — {pathway title}
## Why this pathway fits you
## How it connects to your interests
## What to check officially
## What to build or develop next
## Your first steps this month
"""

# Backward-compatible alias
SYSTEM_PROMPT = EMPLOYER_SYSTEM_PROMPT

BUILD_NEXT_SYSTEM_PROMPT = """You are a friendly Gloucestershire careers coach speaking directly to a young person.
Write in second person ("you"). Be practical, encouraging, and specific.
Write only the "What to build or develop next" paragraph — no markdown headings,
no Why section, and no Training routes. Those are filled in separately.
Keep it to at most 3–5 short lines. Do not use bullet dashes (-) — plain sentences only.
Do not name employers, programmes, scheme titles, vacancies, or job titles.
Do not claim any employer works in a sector. Do not invent culture, values, or mission.
You are writing personal next-step advice from one focus area only.
Use only the single focus area listed in the user message.
Do not mention or build toward any other intake interest (healthcare, aerospace, cyber, data, finance, and so on) unless it is that focus area.
If the focus area is none, write a generic local project — do not name extra sectors.
Prefer a real way to get experience this month over a generic craft project:
helping, volunteering, shadowing, coaching, or making something they can show.
If a listed passion fits the focus area (for example sport plus education → coaching at a youth club), use it.
This is personal experience — never say a named employer is hiring or runs that activity.
You are careers guidance only — not a counsellor or crisis service. Do not give medical advice.
If the person discloses self-harm, abuse, or immediate danger, urge them to seek real-world help
(999 / Childline 0800 1111 / Samaritans 116 123) and do not dig for details.

RESEARCH-BACKED ADVICE RULES:
When RETRIEVED CONTEXT includes STRATEGY cards, use helpful "Do" actions.
Prefer a real local experience they could ask for this month, matched to the focus area,
plus a short learning stretch if it helps.
For education or training, good examples are helping in a school, youth club, after-school
club, or as a sports coach — only if that fits this leaver.
Cite sources in plain language only when it helps. Do not invent statistics.
Obey each card's "Do not claim" constraints.
Do not start every answer with the same stock phrase.
"""

_TYPE_SUFFIX = re.compile(r"\s*Type:\s*.+$", re.I)

_THIN_WORK_SOURCES = frozenset({"companies_house", "vacancies", "seed"})
_SECTOR_LABELS = {
    "cyber_digital": "cyber / digital",
    "aerospace_manufacturing": "aerospace / manufacturing",
    "agri_tech_food": "agri-tech / food",
    "health_care": "health / care",
    "public_sector": "public sector",
    "creative_events": "creative / events",
    "construction_green": "construction / green built environment",
    "hospitality_tourism": "hospitality / tourism",
    "hospitality_retail": "hospitality / retail",
    "business_professional": "business / professional services",
    "education_training": "education / training",
}
_GENERIC_BUILD_EXAMPLE = "a small making or repair task you can photograph"
_BUILD_EXAMPLES_BY_SECTOR = {
    "education_training": (
        "helping at a school, youth club, or sports session as a volunteer helper or coach"
    ),
    "health_care": "a first-aid practice note or a care-skills checklist you can talk through",
    "cyber_digital": "a small website, script, or a short write-up of a tool you tried",
    "aerospace_manufacturing": "a small CAD sketch, 3D print, or a photographed making task",
    "construction_green": "a small making or repair task you can photograph",
    "agri_tech_food": "a growing, cooking, or food-hygiene task you can photograph",
    "public_sector": "a short note on a local service, or volunteering you can talk through",
    "creative_events": "a one-page event plan, poster, or a short video you can show",
    "hospitality_tourism": "a sample menu, welcome card, or a short service checklist",
    "hospitality_retail": "a product-display photo or a short customer-service checklist",
    "business_professional": "a one-page process map or a spreadsheet that solves a real task",
}
_GROUNDED_H2 = (
    "## Why this company fits you",
    "## Training routes that fit your interests",
    "## What to build or develop next",
)


# Shorten/clean a catalogue summary for display.
def clean_catalogue_summary(summary: Any, *, max_len: int = 280) -> str:
    """Trim NCS/catalogue summaries; strip trailing 'Type: …' noise."""
    text = " ".join(str(summary or "").split())
    text = _TYPE_SUFFIX.sub("", text).strip()
    if len(text) > max_len:
        text = text[: max_len - 1].rstrip() + "…"
    return text


# Display name for the match being briefed.
def _subject_name(row: dict[str, Any]) -> str:
    return str(row.get("name") or row.get("title") or "this match").strip()


# Join words for a natural English list.
def _join_natural(parts: list[str], *, conj: str = "and") -> str:
    items = [str(p).strip() for p in parts if str(p).strip()]
    if not items:
        return ""
    if len(items) == 1:
        return items[0]
    if len(items) == 2:
        return f"{items[0]} {conj} {items[1]}"
    return f"{', '.join(items[:-1])}, {conj} {items[-1]}"


# Human matcher sector tags for the grounded work template.
def _ordered_company_sectors(company: dict[str, Any]) -> list[str]:
    raw = company.get("sectors")
    if isinstance(raw, (list, tuple)):
        tags = [str(x).strip() for x in raw if str(x).strip()]
    else:
        tags = [p.strip() for p in str(raw or "").split("|") if p.strip()]
    seen: list[str] = []
    for tag in tags:
        if tag not in seen:
            seen.append(tag)
    return seen


def _matcher_sector_label(company: dict[str, Any]) -> str:
    labels = [
        _SECTOR_LABELS.get(tag, tag.replace("_", " "))
        for tag in _ordered_company_sectors(company)
    ]
    return _join_natural(labels) or "this sector"


@lru_cache(maxsize=1)
def _interest_to_sector_map() -> dict[str, tuple[str, ...]]:
    raw = load_intake_options().get("interest_to_sector") or {}
    return {
        str(label): tuple(str(s).strip() for s in (sectors or []) if str(s).strip())
        for label, sectors in raw.items()
    }


# The single most relevant overlapping interest: company's first sector the leaver also has.
def _overlapping_interest_labels(
    leaver: dict[str, Any], company: dict[str, Any]
) -> list[str]:
    mapping = _interest_to_sector_map()
    user_labels: list[str] = []
    for item in leaver.get("interests") or []:
        label = str(item).strip()
        if label and label not in user_labels:
            user_labels.append(label)
    for sector in _ordered_company_sectors(company):
        for label in user_labels:
            mapped = set(mapping.get(label) or ())
            if sector in mapped:
                return [label]
    return []


# The one employer sector that matches that primary interest.
def _overlapping_sector_ids(
    leaver: dict[str, Any], company: dict[str, Any]
) -> list[str]:
    mapping = _interest_to_sector_map()
    labels = _overlapping_interest_labels(leaver, company)
    if not labels:
        return []
    mapped = set(mapping.get(labels[0]) or ())
    for sector in _ordered_company_sectors(company):
        if sector in mapped:
            return [sector]
    return []


# Human phrase for the overlapping work area (not every matcher tag).
def _work_in_phrase(leaver: dict[str, Any], company: dict[str, Any]) -> str:
    labels = [
        _SECTOR_LABELS.get(sector, sector.replace("_", " "))
        for sector in _overlapping_sector_ids(leaver, company)
    ]
    return _join_natural(labels) or _matcher_sector_label(company)


# Concrete project example tied to the overlapping sector.
def _build_example(leaver: dict[str, Any], company: dict[str, Any]) -> str:
    for sector in _overlapping_sector_ids(leaver, company):
        example = _BUILD_EXAMPLES_BY_SECTOR.get(sector)
        if example:
            return example
    return _GENERIC_BUILD_EXAMPLE


# True when work-mode CH/vacancy/seed rows have no verified programmes.
def _is_thin_work_record(company: dict[str, Any], mode: str) -> bool:
    if (mode or "work").strip().lower() != "work":
        return False
    if classify_employer_source(company) not in _THIN_WORK_SOURCES:
        return False
    return not programmes_for_company(str(company.get("company_id") or ""))


# Grounded 3-section work briefing for thin CH / vacancy / seed rows.
def _grounded_work_briefing(
    leaver: dict[str, Any],
    company: dict[str, Any],
) -> str:
    return _assemble_work_briefing(
        leaver,
        company,
        [],
        _work_build_next(leaver, company, None),
    )


# Format pathway cards into prompt text.
def _pathway_text(leaver: dict[str, Any]) -> str:
    sectors = set(leaver.get("interest_sectors") or leaver.get("target_sectors") or [])
    pathway_bits = []
    for p in pathways_for_sectors(sectors):
        steps = "; ".join(p.get("steps", [])[:3])
        pathway_bits.append(
            f"- {p['title']}: {p.get('summary', '').strip()} Steps: {steps}"
        )
    return "\n".join(pathway_bits) if pathway_bits else "None listed."


# Format retrieved RAG chunks for the briefing prompt.
def _format_chunks(retrieved_chunks: list[dict[str, Any]] | None) -> str:
    if not retrieved_chunks:
        return "No extra corpus chunks."
    parts: list[str] = []
    for c in retrieved_chunks:
        src = str(c.get("source", "doc"))
        raw = str(c.get("chunk", c.get("text", "")))
        parts.append(f"[{src}]:\n{annotate_retrieved_chunk(src, raw)}")
    return "\n\n".join(parts)


# Format leaver profile lines for the briefing prompt.
def _leaver_block(leaver: dict[str, Any]) -> str:
    return f"""LEAVER PROFILE:
{leaver['profile_text']}

Interests: {', '.join(leaver.get('interests', []))}
Passions: {', '.join(leaver.get('passions', []))}
Experience: {', '.join(leaver.get('work_experience', []))}
Availability: {leaver.get('availability', '')}
Qualification level: {leaver.get('qualification_level', '')}"""


# Build the OpenAI prompt for an employer briefing.
def build_employer_briefing_prompt(
    leaver: dict[str, Any],
    company: pd.Series | dict[str, Any],
    retrieved_chunks: list[dict[str, Any]] | None = None,
) -> tuple[str, str]:
    company = company if isinstance(company, dict) else company.to_dict()
    reasons = match_reasons(leaver, pd.Series(company))
    name = _subject_name(company)
    if retrieved_chunks:
        retrieved_chunks = filter_retrieved_hits_for_employer(retrieved_chunks, name)

    kind = classify_employer_source(company)
    programmes = programmes_for_company(str(company.get("company_id") or ""))
    programmes_block = format_programmes_for_prompt(
        programmes, employer_name=name
    )
    prompt_reasons = [
        r
        for r in reasons
        if "entry-route" not in r.lower()
        and "entry route" not in r.lower()
        and not str(r).startswith("Your interests:")
    ]
    overlap = _overlapping_interest_labels(leaver, company)
    overlap_phrase = _join_natural(overlap) or "none — do not claim a personal sector fit"
    if overlap:
        prompt_reasons.append(
            "Overlapping interests (cite only these in Why): " + ", ".join(overlap)
        )
    reason_text = (
        "\n".join(f"- {r}" for r in prompt_reasons)
        or "- Internal matcher overlap with this profile."
    )

    user_prompt = f"""Create a personalised employer briefing for this leaver.

{_leaver_block(leaver)}

{employer_facts_block(company)}
Match score (internal): {company.get('final_score', 'n/a')}
Source label: {source_label(kind)}

WHY MATCHED (matcher reasons — internal tags only, not live programmes):
{reason_text}

VERIFIED PROGRAMMES FOR THIS EMPLOYER (the only scheme titles you may name):
{programmes_block}

RETRIEVED CONTEXT (STRATEGY advice only — not employer programmes):
{_format_chunks(retrieved_chunks)}

Write the briefing now, speaking directly to the leaver.
Keep employer claims inside VERIFIED EMPLOYER FACTS and the verified programmes block only.
Fact summary and matcher tags are location/sector hints only — not evidence they ran apprenticeships, internships, or graduate schemes.
In "Why this company fits you", cite only overlapping interests: {overlap_phrase}.
Do not mention other intake interests as if this employer works in those fields. Do not invent culture, values, or mission.
Do not add a programmes, roles, or jobs section.
In "Training routes that fit your interests", fold in an official careers-page check and a Careers Hub or adviser chat.
If verified programmes are listed, write them as "{name} have previously run …" (guidance only, not open now).
If a listed programme does not fit the leaver's qualification level, keep the tactful line that it is aimed at degree-level entry, so it is not the next step for their qualification-level currently.
If none are listed, do not invent titles — mention generic local college or apprenticeship options in Gloucestershire only.
In "What to build or develop next", include at least one concrete personal project
(something they can show or talk about) and one study or research stretch tied to
their interests, plus optional encounter or application practice from STRATEGY cards.
If a STRATEGY card supports a real encounter, you may write "Careers research suggests…".
Use plain language — no academic jargon.
Do not frame the briefing as live job hunting.
Use the heading "# Your match — {name}".
Use only these H2 headings: Why this company fits you; Training routes that fit your interests; What to build or develop next.
"""
    return EMPLOYER_SYSTEM_PROMPT, user_prompt


# Distinctive phrases from a leaver interest label (full label plus long stems).
def _interest_mention_markers(label: str) -> list[str]:
    text = str(label or "").strip()
    if not text:
        return []
    markers = [text.lower()]
    for part in re.split(r"\s*[&/]\s*", text):
        part = part.strip().lower()
        if len(part) >= 8:
            markers.append(part)
    return markers


# Redact non-overlap interest labels from free-text so the model cannot copy them.
def _profile_text_without_non_overlap(
    leaver: dict[str, Any], overlap: list[str]
) -> str:
    text = str(leaver.get("profile_text") or "")
    allowed = {item.lower() for item in overlap}
    for item in leaver.get("interests") or []:
        label = str(item).strip()
        if not label or label.lower() in allowed:
            continue
        for marker in _interest_mention_markers(label):
            text = re.sub(re.escape(marker), "another interest", text, flags=re.I)
    return text


# OpenAI prompt for the work-mode "What to build" paragraph only.
def build_work_build_next_prompt(
    leaver: dict[str, Any],
    company: pd.Series | dict[str, Any],
    retrieved_chunks: list[dict[str, Any]] | None = None,
) -> tuple[str, str]:
    company = company if isinstance(company, dict) else company.to_dict()
    name = _subject_name(company)
    if retrieved_chunks:
        retrieved_chunks = filter_retrieved_hits_for_employer(retrieved_chunks, name)
    overlap = _overlapping_interest_labels(leaver, company)
    overlap_phrase = (
        overlap[0]
        if overlap
        else "none — write a generic local project; do not name other intake interests"
    )
    proud = " ".join(str(leaver.get("proud_example") or "").split()).strip() or "none logged"
    passions = ", ".join(
        str(p).strip() for p in (leaver.get("passions") or []) if str(p).strip()
    ) or "none logged"
    profile = _profile_text_without_non_overlap(leaver, overlap)
    user_prompt = f"""Write only the "What to build or develop next" paragraph for this leaver.
Do not write Why this company fits you or Training routes. Those are filled in separately.

LEAVER PROFILE:
{profile}

Passions: {passions}
Experience: {', '.join(leaver.get('work_experience', []))}
Availability: {leaver.get('availability', '')}
Qualification level: {leaver.get('qualification_level', '')}

Focus area (use this one only): {overlap_phrase}
Logged proud example (you may echo its spirit, without switching sector): {proud}
Suggest one concrete way to get experience this month in that focus area.
If the focus is education or training, prefer asking to help at a school, youth club, after-school activity, or as a sports coach when that fits.
This is personal experience — do not claim any employer runs it or is hiring.
Do not mention any other intake interest. Do not name programmes or vacancies.

RETRIEVED CONTEXT (STRATEGY advice only — not employer programmes):
{_format_chunks(retrieved_chunks)}

Write 3–5 short sentences in second person. No markdown headings. No employer names. No scheme titles.
Lead with the experience or practice, then a short learning stretch if useful.
Do not start every paragraph with "Start one small project" or "Make something small".
Use plain language — no academic jargon.
"""
    return BUILD_NEXT_SYSTEM_PROMPT, user_prompt


# Pull the build-next body from a free paragraph or a full three-section briefing.
def _extract_build_next_body(text: str) -> str:
    blob = str(text or "").strip()
    if not blob:
        return ""
    marker = _GROUNDED_H2[2].lower()
    lowered = blob.lower()
    if marker in lowered:
        start = lowered.index(marker) + len(marker)
        rest = blob[start:].lstrip("\n")
        nxt = rest.find("\n## ")
        if nxt >= 0:
            rest = rest[:nxt]
        blob = rest.strip()
    lines = [line for line in blob.splitlines() if not line.startswith("#")]
    return "\n".join(lines).strip()


# True when the model paragraph does not name schemes, extra headings, or non-overlap interests.
def _build_next_is_safe(
    text: str,
    programmes: list[dict[str, Any]],
    *,
    leaver: dict[str, Any],
    company: dict[str, Any],
) -> bool:
    blob = str(text or "").strip()
    if not blob:
        return False
    lowered = blob.lower()
    if any(
        token in lowered
        for token in (
            "have previously run",
            "they offer",
            "## why this company",
            "## training routes",
        )
    ):
        return False
    for programme in programmes:
        title = str(programme.get("programme_title") or "").strip()
        if title and title.lower() in lowered:
            return False
    overlap = {item.lower() for item in _overlapping_interest_labels(leaver, company)}
    for item in leaver.get("interests") or []:
        label = str(item).strip()
        if not label or label.lower() in overlap:
            continue
        if any(marker in lowered for marker in _interest_mention_markers(label)):
            return False
    return True


# Stitch locked Why + Training routes with a (model or template) build-next paragraph.
def _assemble_work_briefing(
    leaver: dict[str, Any],
    company: dict[str, Any],
    programmes: list[dict[str, Any]],
    build_next: str,
) -> str:
    name = _subject_name(company)
    return "\n".join(
        [
            f"# Your match — {name}",
            "",
            _GROUNDED_H2[0],
            _work_why_paragraph(leaver, company),
            "",
            _GROUNDED_H2[1],
            _work_training_routes(leaver, company, programmes),
            "",
            _GROUNDED_H2[2],
            str(build_next or "").strip(),
        ]
    )


# Build the OpenAI prompt for a course briefing.
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


# Build the OpenAI prompt for a military pathway briefing.
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


# Dispatch to the right briefing prompt builder by mode.
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


# Run RAG retrieval for this leaver + match briefing.
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
    name = str(row.get("name") or "").strip()
    hits = retrieve(
        query, top_k=top_k, prefer_evidence=True, employer_name=name
    )
    return filter_retrieved_hits_for_employer(hits, name)


def generate_briefing(
    leaver: dict[str, Any],
    company: pd.Series | dict[str, Any],
    *,
    use_openai: bool = True,
    retrieved_chunks: list[dict[str, Any]] | None = None,
    mode: str = "work",
    related_microcreds: list[dict[str, Any]] | None = None,
) -> tuple[str, str]:
    """Return (briefing_markdown, source).

    Source is 'openai', 'grounded_template', or 'offline'.
    Why and Training routes are always filled in code. OpenAI may write
    "What to build or develop next" only, including for thin work rows.
    """
    company_dict = company if isinstance(company, dict) else company.to_dict()
    mode = (mode or "work").strip().lower()
    chunks = retrieved_chunks
    if chunks is None:
        try:
            chunks = _retrieve_for_briefing(leaver, company_dict)
        except Exception:
            chunks = []

    if mode != "work":
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
                temperature=0.3,
                max_tokens=900,
            )
            text = (resp.choices[0].message.content or "").strip()
            if not text:
                return offline, "offline"
            return text, "openai"
        except Exception:
            return offline, "offline"

    programmes = programmes_for_company(str(company_dict.get("company_id") or ""))
    thin = _is_thin_work_record(company_dict, mode)
    locked_programmes: list[dict[str, Any]] = [] if thin else programmes
    template_build = _work_build_next(leaver, company_dict, chunks)
    assembled = _assemble_work_briefing(
        leaver, company_dict, locked_programmes, template_build
    )
    fallback_source = "grounded_template" if thin else "offline"
    if not use_openai:
        return assembled, fallback_source
    api_key = os.getenv("OPENAI_API_KEY", "").strip()
    if not api_key:
        return assembled, fallback_source
    try:
        from openai import OpenAI

        system, user = build_work_build_next_prompt(
            leaver, company_dict, retrieved_chunks=chunks
        )
        client = OpenAI(api_key=api_key)
        resp = client.chat.completions.create(
            model=os.getenv("OPENAI_MODEL", "gpt-4o-mini"),
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            temperature=0.5,
            max_tokens=400,
        )
        text = (resp.choices[0].message.content or "").strip()
        if not text:
            return assembled, fallback_source
        body = _extract_build_next_body(text)
        if not _build_next_is_safe(
            body, programmes, leaver=leaver, company=company_dict
        ):
            body = template_build
        return (
            _assemble_work_briefing(leaver, company_dict, locked_programmes, body),
            "openai",
        )
    except Exception:
        return assembled, fallback_source


# Pull concrete 'Do' actions from evidence cards.
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


# True when a verified programme is aimed at degree-level entry.
def _programme_is_degree_aimed(programme: dict[str, Any]) -> bool:
    ptype = str(programme.get("programme_type") or "").lower()
    if "graduate" in ptype:
        return True
    level = str(programme.get("level") or "").lower()
    if re.search(r"level\s*6\s*\+", level) or re.search(r"level\s*7", level):
        return True
    if "degree" in level and not re.search(r"level\s*[1-5]", level):
        return True
    return False


# Choose a / an for a programme title.
def _indefinite_article(title: str) -> str:
    word = str(title or "").strip()
    return "an" if word[:1].lower() in "aeiou" else "a"


# True when retrieved STRATEGY cards support a real employer encounter.
def _strategy_supports_encounter(retrieved_chunks: list[dict[str, Any]] | None) -> bool:
    for chunk_hit in retrieved_chunks or []:
        blob = " ".join(
            [
                str(chunk_hit.get("chunk") or ""),
                str(chunk_hit.get("source") or ""),
            ]
        ).lower()
        if "strategy:" not in blob and "evidence:" not in blob:
            continue
        if any(
            key in blob
            for key in ("visit", "encounter", "open day", "mentor", "workplace experience")
        ):
            return True
    return False


# Offline work-mode "why this company" paragraph.
def _work_why_paragraph(leaver: dict[str, Any], company: dict[str, Any]) -> str:
    name = _subject_name(company)
    town = str(company.get("town") or "").strip() or "Gloucestershire"
    overlap = _overlapping_interest_labels(leaver, company)
    fit_phrase = _join_natural(overlap)
    work_in = _work_in_phrase(leaver, company)
    why = f"{name} is based in {town}."
    travel = commute_hint(leaver.get("location"), town)
    if travel:
        why = f"{why} {travel}"
    if fit_phrase:
        why = f"{why} They work in {work_in}, which matches your interest in {fit_phrase}."
    else:
        why = f"{why} They are a local employer."
    return why


# Offline work-mode training routes: verified programmes + generic college sentence.
def _work_training_routes(
    leaver: dict[str, Any],
    company: dict[str, Any],
    programmes: list[dict[str, Any]],
) -> str:
    name = _subject_name(company)
    overlap = _overlapping_interest_labels(leaver, company)
    interest_route = _join_natural(
        [item.lower() for item in overlap],
        conj="or",
    ) or "this sector"
    website = public_employer_website(company.get("website"))
    bits: list[str] = []
    used = False
    for programme in programmes:
        title = str(programme.get("programme_title") or "programme").strip()
        level = str(programme.get("level") or "").strip()
        summary = " ".join(str(programme.get("summary") or "").split())
        article = _indefinite_article(title)
        level_bit = f" ({level})" if level else ""
        if _programme_is_degree_aimed(programme):
            lead = f"{name} have also run" if used else f"{name} have previously run"
            bits.append(
                f"{lead} {article} {title}{level_bit}; that is aimed at degree-level entry, "
                "so it is not the next step for your qualification-level currently."
            )
            used = True
            continue
        cover = f" covering {summary}" if summary else ""
        if not used:
            bits.append(
                f"{name} have previously run {article} {title}{level_bit}{cover}. "
                "That is the route that matches where you are now."
            )
        else:
            bits.append(
                f"They have also previously run {article} {title}{level_bit}{cover}."
            )
        used = True
    also = " as well as the routes above" if programmes else ""
    look = (
        f"Check {name}'s careers page ({website}) to see how they recruit. "
        if website
        else "Check the company's official careers page to see how they recruit. "
    )
    if overlap:
        route_lead = (
            f"If you want a structured way into {interest_route}, local college courses "
            f"and apprenticeships are the usual next step{also}."
        )
    else:
        route_lead = (
            f"Local college courses and apprenticeships are the usual structured "
            f"next step{also}."
        )
    bits.append(
        f"{route_lead} {look}"
        "A careers adviser or Careers Hub session can help you compare those options."
    )
    return " ".join(bits)


# Offline work-mode "what to build next" paragraph.
def _work_build_next(
    leaver: dict[str, Any],
    company: dict[str, Any],
    retrieved_chunks: list[dict[str, Any]] | None,
) -> str:
    overlap = _overlapping_interest_labels(leaver, company)
    interests_phrase = _join_natural(overlap) or "your target sector"
    proud = " ".join(str(leaver.get("proud_example") or "").split()).strip()
    example = _build_example(leaver, company)
    if proud:
        project = (
            f"Make something small you can show, in the same spirit as {proud}, "
            f"tied to {interests_phrase}."
        )
    else:
        project = (
            f"Make something small you can show or talk about in {interests_phrase} "
            f"— for example {example}."
        )
    study = (
        "Then spend an hour on one skill that kind of work actually uses "
        "(a free tutorial, a library book, or an open online lesson)."
    )
    parts = [project, study]
    if _strategy_supports_encounter(retrieved_chunks):
        parts.append(
            "If you can, go to an open day or ask for a short chat this month."
        )
    return " ".join(parts)


# Pathway card lines for education / military offline templates only.
def _fallback_pathway_lines(leaver: dict[str, Any]) -> list[str]:
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
    return pathway_lines


# Template briefing when OpenAI is off or fails.
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
    pathway_lines: list[str] = []
    if mode in {"education", "military"}:
        pathway_lines = _fallback_pathway_lines(leaver)

    if retrieved_chunks is None:
        try:
            retrieved_chunks = _retrieve_for_briefing(leaver, company)
        except Exception:
            retrieved_chunks = []

    if mode == "work" and retrieved_chunks:
        retrieved_chunks = filter_retrieved_hits_for_employer(retrieved_chunks, name)

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
                "## What to build or develop next",
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
                "## What to build or develop next",
                *build_next,
                "",
                "## Your first steps this month",
                *first_steps,
            ]
        )

    # Employer (default)
    programmes = programmes_for_company(str(company.get("company_id") or ""))
    return _assemble_work_briefing(
        leaver,
        company,
        programmes,
        _work_build_next(leaver, company, retrieved_chunks),
    )
