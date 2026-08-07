"""Gemini-backed 5-step action plans for matched employers/courses/pathways.

Requires GEMINI_API_KEY. Falls back to profile-aware templates when unavailable.

Plans and breakdowns branch on profile state (e.g. no experience yet) and match
kind (employer, course, professional body, military).
"""

from __future__ import annotations

import json
import os
import re
import uuid
from typing import Any

GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-3.5-flash")
_GEMINI_MODEL_FALLBACKS = tuple(
    dict.fromkeys(
        [
            GEMINI_MODEL,
            "gemini-3.5-flash",
            "gemini-3.6-flash",
            "gemini-flash-latest",
            "gemini-3.5-flash-lite",
            "gemini-3.1-flash-lite",
        ]
    )
)

_EMPTY_EXPERIENCE = {
    "none yet",
    "none",
    "n/a",
    "na",
    "no",
    "no experience",
    "not yet",
    "nothing yet",
    "nil",
    "-",
    "—",
}

_BANNED_PHRASES = (
    "one small thing",
    "do one small thing",
    "that's enough for today",
    "thats enough for today",
    "you've already started",
    "youve already started",
    "ask someone you trust",
    "none yet",
)

_PLACEHOLDER_LEAKS = (
    "none yet",
    "how none",
    "write how none",
    "{experience}",
    "{interest}",
    "your interests and are based",
)

_PROF_BODY_NAME_HINTS = (
    "association",
    "society",
    "institute",
    "institution",
    "federation",
    "council",
    "chamber",
    "chartered",
    "records association",
    "archives and records",
)

_PROF_BODY_URL_HINTS = (
    "archives.org.uk",
    "ica.org",
    "cipd.co.uk",
    "bcs.org",
    "theiet.org",
    "rsc.org",
    "iop.org",
)

_VOICE_CORE = """
You help young people in Bristol and Gloucestershire with next steps after school
or college. Many readers have lower English confidence. Some are not in work or
training right now. Treat every person with respect.

## Reading level (essential)
- Write so a 13–14 year old can follow easily.
- Use short, everyday words.
- One idea per sentence. Prefer under 20 words per sentence.
- Do not talk down. Clear adult respect — not baby talk.

## Warmth
- Calm careers mentor. Speak in second person ("you").
- Give concrete next actions (verb + object + where/how).
- Don't: corporate speak; shame; "just get a job"; vague filler.
- Avoid assuming parents can always help with applications or travel.

## Honesty & safety
- Guidance only — not an official careers service or recruitment advice.
- Never invent deadlines, salaries, entry requirements, medical/fitness rules,
  pay, postings, ELC/PD funding, or guaranteed outcomes.
- If a fact is missing, say to check the official website, then give a prep step.
- Prefer Bristol / Gloucestershire actions when location is known.

## Brand
- MatchKite voice: local, honest. Metaphor at most once — or not at all.
"""

_MODE_ADDENDA = {
    "work": """
## Mode: work
Be practical. Match kind may be employer OR professional body — do not treat
a membership body like a vacancy board.
""",
    "education": """
## Mode: education
Help them check the course with the college/provider. Never invent grades/fees.
""",
    "military": """
## Mode: military
Guidance only — never official recruitment advice. Never invent fitness/medical rules.
""",
}

_CHAT_FEW_SHOTS = """
## Chat tone
If stuck: point to the official page, then one concrete capture task.
If no experience yet: use courses, school projects, volunteering, or home skills as proof.
Never write the words "None yet" in advice sentences.
"""

_BREAKDOWN_RULES = """
## Breakdown rules (strict)
- Use PROFILE_STATE. Never print empty placeholders like "None yet".
- If has_experience is false, tell them to gather proof from courses/projects — do not
  ask how "none" experience matters.
- Respect match_kind (professional_body ≠ employer vacancy hunt).
- Stay on THIS step only. No repeated why line or step title in detail_markdown.
- Each action = verb + object + where/how.
- Ban: "one small thing", "ask someone you trust", "None yet".
- Ground tips in HOW_TO_CONTEXT when present.
"""

_SIMPLE_ENGLISH_REMINDER = """
LANGUAGE CHECK: short words, short sentences, kind and clear, no jargon.
"""


def _system_for_mode(mode: str) -> str:
    m = (mode or "work").strip().lower()
    if m not in _MODE_ADDENDA:
        m = "work"
    return (_VOICE_CORE + _MODE_ADDENDA[m] + _CHAT_FEW_SHOTS).strip()


def _system_for_breakdown(mode: str) -> str:
    m = (mode or "work").strip().lower()
    if m not in _MODE_ADDENDA:
        m = "work"
    return (_VOICE_CORE + _MODE_ADDENDA[m] + _BREAKDOWN_RULES).strip()


def _gemini_client():
    key = (os.getenv("GEMINI_API_KEY") or "").strip()
    if not key:
        return None
    try:
        from google import genai

        return genai.Client(api_key=key)
    except Exception:
        return None


def _extract_json(text: str) -> Any:
    raw = (text or "").strip()
    if not raw:
        raise ValueError("Empty model response")
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        m = re.search(r"\{[\s\S]*\}|\[[\s\S]*\]", raw)
        if not m:
            raise
        return json.loads(m.group(0))


def _match_label(match: dict[str, Any]) -> str:
    return str(match.get("name") or match.get("title") or "this option").strip()


def _offline_disclaimer() -> str:
    return (
        "This is a guide only — not an official careers service. "
        "Check the organisation's own website before you act."
    )


def _as_list(value: Any, *, limit: int = 8) -> list[str]:
    if value is None:
        return []
    if isinstance(value, str):
        text = value.strip()
        return [text] if text else []
    if isinstance(value, (list, tuple, set)):
        out: list[str] = []
        for item in value:
            s = str(item).strip()
            if s and s not in out:
                out.append(s)
            if len(out) >= limit:
                break
        return out
    s = str(value).strip()
    return [s] if s else []


def _is_empty_experience(value: str) -> bool:
    return value.strip().lower() in _EMPTY_EXPERIENCE


def _build_profile_state(leaver: dict[str, Any]) -> dict[str, Any]:
    interests = _as_list(leaver.get("interests"), limit=5) or _as_list(
        leaver.get("passions"), limit=5
    )
    raw_exp = _as_list(leaver.get("work_experience"), limit=6)
    experience = [x for x in raw_exp if not _is_empty_experience(x)]
    courses = _as_list(leaver.get("courses"), limit=5)
    location = str(leaver.get("location") or "").strip()
    quals = str(leaver.get("qualification_level") or "").strip()
    availability = str(leaver.get("availability") or "").strip()
    leaver_type = str(leaver.get("leaver_type") or "").strip()
    proud_example = " ".join(str(leaver.get("proud_example") or "").split()).strip()
    goal_sentence = " ".join(str(leaver.get("goal_sentence") or "").split()).strip()
    barriers = _as_list(leaver.get("barriers"), limit=6)
    must_haves = _as_list(leaver.get("must_haves"), limit=6)
    support_available = _as_list(leaver.get("support_available"), limit=4)
    apply_readiness = str(leaver.get("apply_readiness") or "").strip()

    proof: list[str] = []
    if proud_example:
        proof.append(proud_example[:160])
    proof.extend(experience[:3])
    for c in courses[:2]:
        label = f"course: {c}"
        if label not in proof:
            proof.append(label)
    if not proof:
        proof.append("a school project, club role, volunteering, or skill from home")

    # Typed work history only — proud examples still feed proof_label separately
    has_experience = bool(experience)
    hooks: list[str] = []
    if location:
        hooks.append(location)
    for item in interests[:2]:
        if item not in hooks:
            hooks.append(item)
    if experience:
        for item in experience[:2]:
            if item not in hooks:
                hooks.append(item)
    elif proud_example:
        short_proud = proud_example[:48] + ("…" if len(proud_example) > 48 else "")
        if short_proud not in hooks:
            hooks.append(short_proud)
    elif courses:
        for item in courses[:2]:
            if item not in hooks:
                hooks.append(item)
    elif "no paid experience yet" not in hooks:
        hooks.append("no paid experience yet")
    if goal_sentence and len(hooks) < 4:
        short_goal = goal_sentence[:48] + ("…" if len(goal_sentence) > 48 else "")
        if short_goal not in hooks:
            hooks.append(short_goal)
    if quals and quals not in hooks and len(hooks) < 4:
        hooks.append(quals)

    interest_label = ", ".join(interests[:2]) if interests else "your interests"
    if experience:
        experience_label = ", ".join(experience[:2])
        proof_label = experience_label
    elif proud_example:
        experience_label = ""
        proof_label = proud_example[:120]
    elif courses:
        experience_label = ""
        proof_label = ", ".join(courses[:2])
    else:
        experience_label = ""
        proof_label = "a school project, club, volunteering, or skill from home"

    return {
        "location": location,
        "interests": interests,
        "interest_label": interest_label,
        "has_experience": has_experience,
        "experience": experience,
        "experience_label": experience_label,
        "courses": courses,
        "proof_sources": proof,
        "proof_label": proof_label,
        "qualification_level": quals,
        "availability": availability,
        "leaver_type": leaver_type,
        "proud_example": proud_example,
        "goal_sentence": goal_sentence,
        "barriers": barriers,
        "must_haves": must_haves,
        "support_available": support_available,
        "apply_readiness": apply_readiness,
        "hooks": hooks[:4],
    }


def _classify_match_kind(mode: str, match: dict[str, Any]) -> str:
    kind = str(match.get("kind") or "").strip().lower()
    if mode == "military" or kind == "military":
        return "military"
    if mode == "education" or kind == "course":
        return "course"

    name = _match_label(match).lower()
    website = str(match.get("website") or "").lower()
    summary = str(match.get("summary") or "").lower()
    blob = f"{name} {website} {summary}"

    if any(h in website for h in _PROF_BODY_URL_HINTS) or any(
        h in blob for h in _PROF_BODY_NAME_HINTS
    ):
        return "professional_body"

    entry = str(match.get("entry_routes") or "").lower()
    hiring = str(match.get("hiring_label") or match.get("hiring_signal") or "").lower()
    if "apprentice" in entry or "vacanc" in summary or "hiring" in hiring:
        return "employer_with_vacancies"
    return "employer"


def _profile_hooks(leaver: dict[str, Any], *, limit: int = 4) -> list[str]:
    return list(_build_profile_state(leaver).get("hooks") or [])[:limit]


def _why_line(profile: dict[str, Any], match_name: str, *, angle: str) -> str:
    interest = profile["interest_label"]
    loc = profile["location"]
    base = f"Because you care about {interest}"
    if loc:
        base += f" and are based near {loc}"
    return f"{base}, {angle} with {match_name}."


def _step(
    sid: str,
    title: str,
    summary: str,
    timeframe: str,
    *,
    family: str,
) -> dict[str, Any]:
    return {
        "id": sid,
        "title": title[:60],
        "summary": summary[:220],
        "timeframe": timeframe,
        "family": family,
    }


def _offline_plan(
    mode: str,
    match: dict[str, Any],
    leaver: dict[str, Any] | None = None,
) -> dict[str, Any]:
    leaver = leaver or {}
    profile = _build_profile_state(leaver)
    match_kind = _classify_match_kind(mode, match)
    name = _match_label(match)
    website = str(match.get("website") or "").strip()
    site_hint = f" Start at {website}." if website else " Start on their official website."
    interest = profile["interest_label"]
    proof = profile["proof_label"]
    loc = profile["location"] or "your area"

    if match_kind == "course":
        steps = [
            _step(
                "s1",
                "Check the course page",
                f"On the official page for {name}, note what they ask for and how to apply.{site_hint}",
                "This week",
                family="course_check",
            ),
            _step(
                "s2",
                "Gather your proof points",
                (
                    f"List grades/predicted grades and two proof points from {proof} "
                    f"that link to {interest}."
                    if not profile["has_experience"]
                    else f"Note grades and two examples from {proof} that show fit for {name}."
                ),
                "This week",
                family="proof_gather",
            ),
            _step(
                "s3",
                "Ask a local adviser",
                f"Ask a teacher, tutor, or careers person whether {name} fits {interest}.",
                "This month",
                family="local_support",
            ),
            _step(
                "s4",
                "Apply or send a question",
                f"Apply for {name} the official way, or send one clear question if unsure.",
                "This month",
                family="apply_enquire",
            ),
            _step(
                "s5",
                "Keep a backup course",
                "Pick one other course or route if this one is full or needs more prep.",
                "Next",
                family="follow_up",
            ),
        ]
    elif match_kind == "military":
        steps = [
            _step(
                "s1",
                "Read the official page",
                f"Read about {name} on the official site and note unclear points.{site_hint}",
                "This week",
                family="fit_check",
            ),
            _step(
                "s2",
                "Write honest questions",
                "List questions about fitness, quals, and daily life for official sources only.",
                "This week",
                family="proof_gather",
            ),
            _step(
                "s3",
                "Find an official chat",
                "Find a local info event or official careers chat; take your top questions.",
                "This month",
                family="local_support",
            ),
            _step(
                "s4",
                "Build one useful skill",
                f"Look at one local short course that supports {interest} — don't assume funding.",
                "This month",
                family="apply_enquire",
            ),
            _step(
                "s5",
                "Choose your next contact",
                "Book an official info chat, or set a date to re-check the official pages.",
                "Next",
                family="follow_up",
            ),
        ]
    elif match_kind == "professional_body":
        prep_title = (
            "Gather proof from learning"
            if not profile["has_experience"]
            else "Link your experience"
        )
        prep_summary = (
            f"List two proof points from {proof} that connect {interest} to records, "
            f"heritage, or sector careers around {name}."
            if not profile["has_experience"]
            else f"Note how {proof} connects to sector themes around {name} and {interest}."
        )
        steps = [
            _step(
                "s1",
                "Learn what they do",
                f"Read what {name} is for (membership / sector body, not a job board).{site_hint}",
                "This week",
                family="fit_check",
            ),
            _step(
                "s2",
                prep_title,
                prep_summary,
                "This week",
                family="proof_gather",
            ),
            _step(
                "s3",
                "Find a local foothold",
                f"Look for local archive, museum, library, or volunteer routes near {loc} "
                f"linked to {interest}.",
                "This month",
                family="local_support",
            ),
            _step(
                "s4",
                "Explore careers or events",
                f"On the {name} site, find careers, training, or events and note one next contact.",
                "This month",
                family="apply_enquire",
            ),
            _step(
                "s5",
                "Add a backup employer",
                f"Pick one local employer or course in {interest} as a parallel route.",
                "Next",
                family="follow_up",
            ),
        ]
    else:
        # employer (with or without vacancy signal)
        if profile["has_experience"]:
            prep = _step(
                "s2",
                "Tailor a one-page CV",
                f"Update a one-page CV using {proof}, aimed at themes from {name}.",
                "This week",
                family="proof_gather",
            )
        else:
            prep = _step(
                "s2",
                "Build proof without a job history",
                f"Make a one-page skills sheet from {proof} that supports {interest} "
                f"for {name}.",
                "This week",
                family="proof_gather",
            )

        if match_kind == "employer_with_vacancies":
            openings = _step(
                "s3",
                "Search live openings",
                f"Check {name}'s careers page and Find an apprenticeship near {loc}.",
                "This month",
                family="openings",
            )
        else:
            openings = _step(
                "s3",
                "Check how people join",
                f"Find how people usually join {name} (apprenticeship, enquiry, or schemes).",
                "This month",
                family="openings",
            )

        steps = [
            _step(
                "s1",
                "Check they fit you",
                f"Read what {name} does and which themes match {interest}.{site_hint}",
                "This week",
                family="fit_check",
            ),
            prep,
            openings,
            _step(
                "s4",
                "Apply or ask",
                f"Apply the official way, or send {name} a short question if you cannot apply yet.",
                "This month",
                family="apply_enquire",
            ),
            _step(
                "s5",
                "Follow up and keep options",
                "Set a reminder to follow up. Keep one other employer or course ready.",
                "Next",
                family="follow_up",
            ),
        ]

    return {
        "plan_id": f"offline-{uuid.uuid4().hex[:10]}",
        "source": "offline",
        "match_name": name,
        "match_kind": match_kind,
        "steps": [{k: v for k, v in s.items() if k != "family"} for s in steps],
        "step_families": {s["id"]: s["family"] for s in steps},
        "disclaimer": _offline_disclaimer(),
    }


def _family_for_step(
    step: dict[str, Any],
    *,
    mode: str,
    match_kind: str,
    families: dict[str, str] | None = None,
) -> str:
    sid = str(step.get("id") or "")
    if families and sid in families:
        return families[sid]

    title = str(step.get("title") or "").lower()
    summary = str(step.get("summary") or "").lower()
    blob = f"{title} {summary} {sid}"

    if match_kind == "course" or any(
        k in blob for k in ("course page", "entry", "personal statement")
    ):
        if any(k in blob for k in ("proof", "basics", "grades", "cv", "ready")):
            return "proof_gather"
        if any(k in blob for k in ("adviser", "ask", "teacher", "tutor")):
            return "local_support"
        if any(k in blob for k in ("apply", "enquiry", "question")):
            return "apply_enquire"
        if any(k in blob for k in ("backup", "follow")):
            return "follow_up"
        return "course_check"

    if any(k in blob for k in ("cv", "proof", "basics", "ready", "skills sheet", "experience")):
        return "proof_gather"
    if any(k in blob for k in ("opening", "vacanc", "apprentice", "join", "search")):
        return "openings"
    if any(k in blob for k in ("apply", "enquiry", "ask", "contact", "event", "careers")):
        return "apply_enquire"
    if any(k in blob for k in ("backup", "follow", "reminder")):
        return "follow_up"
    if any(k in blob for k in ("local", "foothold", "volunteer", "adviser", "chat")):
        return "local_support"
    if match_kind == "professional_body":
        return "fit_check"
    return "fit_check"


def _offline_breakdown(
    step: dict[str, Any],
    *,
    leaver: dict[str, Any],
    match: dict[str, Any],
    mode: str,
    families: dict[str, str] | None = None,
) -> dict[str, Any]:
    profile = _build_profile_state(leaver)
    match_kind = _classify_match_kind(mode, match)
    family = _family_for_step(
        step, mode=mode, match_kind=match_kind, families=families
    )
    step_id = str(step.get("id") or "s1")
    name = _match_label(match)
    website = str(match.get("website") or "").strip()
    site = website or "their official website"
    interest = profile["interest_label"]
    proof = profile["proof_label"]
    loc = profile["location"] or "your area"
    hooks = list(profile["hooks"])

    if family == "fit_check" and match_kind == "professional_body":
        why = _why_line(
            profile,
            name,
            angle="this step helps you understand the sector body",
        )
        detail = (
            f"1. Open {site} and read the About / What we do section for {name}.\n"
            f"2. Write two themes that link {interest} to their work "
            f"(for example records about places, conservation, or community history).\n"
            f"3. Note one careers, training, or membership page — not a job advert guess.\n"
            f"4. Save the page and one question "
            f"(for example trainee routes or local volunteer ideas).\n\n"
            "_This is a sector body page, not a vacancy board. Check official details._"
        )
        sources = ["Organisation website"]
    elif family == "fit_check":
        why = _why_line(
            profile, name, angle="this step checks whether they are a real fit"
        )
        detail = (
            f"1. Open {site} and read what {name} does.\n"
            f"2. Write two themes that connect to {interest}.\n"
            f"3. Note how {proof} could support those themes "
            f"(course work counts if you do not have a job history yet).\n"
            f"4. Save the page and one question you still need answered.\n\n"
            "_Guidance only. Check official sites before you act._"
        )
        sources = []
    elif family == "proof_gather":
        if profile["has_experience"]:
            why = _why_line(
                profile, name, angle="this step turns your experience into clear proof"
            )
            detail = (
                f"1. Open a one-page CV draft (Word, Google Doc, or paper).\n"
                f"2. Write a 2-line profile naming {name} or this type of role and one strength.\n"
                f"3. Add two experience bullets from {proof} with what you did and a result.\n"
                f"4. From the match summary, list three themes and add one proof line each.\n\n"
                "_Tip based on National Careers Service / Prospects-style CV advice._"
            )
        else:
            why = _why_line(
                profile,
                name,
                angle="this step builds proof even without a job history yet",
            )
            detail = (
                f"1. Make a one-page skills sheet (not a long CV).\n"
                f"2. List education/courses, then two proof points from {proof}.\n"
                f"3. For each proof point, write what you did and what it shows "
                f"for {interest}.\n"
                f"4. Add one STAR example from school, volunteering, or a project "
                f"that could matter for {name}.\n\n"
                "_No paid experience yet is fine — use real learning and projects._"
            )
        sources = [
            "National Careers Service — CV sections",
            "Prospects — STAR technique",
        ]
    elif family == "openings":
        why = _why_line(
            profile, name, angle="this step checks real joining routes"
        )
        detail = (
            f"1. Open {site} and find Careers, Jobs, Vacancies, or Early careers.\n"
            f"2. Search {name} on Find an apprenticeship using {loc}.\n"
            f"3. Write down any live roles — or write “no vacancies found yet”.\n"
            f"4. Save links that mention skills linked to {interest}.\n\n"
            "_A match is not the same as an open vacancy._"
        )
        sources = ["GOV.UK — Find an apprenticeship"]
    elif family == "local_support" and match_kind == "professional_body":
        why = _why_line(
            profile, name, angle="this step finds a local way into the sector"
        )
        detail = (
            f"1. Search for a local archive, museum, library, or heritage project near {loc}.\n"
            f"2. Check whether they mention volunteers, open days, or young people.\n"
            f"3. Note how that local option connects to {interest} and to {name}.\n"
            f"4. Ask a teacher or careers person which local contact is realistic for you.\n\n"
            "_Do not assume unpaid roles are possible — check what they offer._"
        )
        sources = ["Gatsby Good Career Guidance (applied)"]
    elif family == "local_support":
        why = _why_line(
            profile, name, angle="this step gets a second view on your plan"
        )
        support = profile.get("support_available") or []
        support_bit = (
            f"Ask {', '.join(support[:2])}"
            if support and "None right now" not in support and "Not sure" not in support
            else "Ask a teacher, tutor, youth worker, or careers person"
        )
        detail = (
            f"1. {support_bit} for a short chat.\n"
            f"2. Take this match name ({name}) and your interest in {interest}.\n"
            f"3. Ask whether your proof from {proof} is enough to start an enquiry.\n"
            f"4. Write down one action they suggest for this week.\n\n"
            "_An app plan is not a replacement for personal guidance._"
        )
        sources = ["Gatsby Good Career Guidance (applied)"]
    elif family == "apply_enquire" and match_kind == "professional_body":
        why = _why_line(
            profile, name, angle="this step finds a real next contact on their site"
        )
        detail = (
            f"1. On {site}, open Careers, Training, Events, or Membership for {name}.\n"
            f"2. Note one event, training page, or contact route — do not invent dates.\n"
            f"3. Draft one short question linking {interest} to that page.\n"
            f"4. Send only via an official route, or save it for an adviser to check.\n\n"
            "_Sector bodies often guide careers; they may not hire you directly._"
        )
        sources = ["Organisation website"]
    elif family == "apply_enquire":
        why = _why_line(
            profile, name, angle="this step helps you apply or ask clearly"
        )
        detail = (
            f"1. Find the official apply or contact route on {site}.\n"
            f"2. Draft who you are, why {interest} fits {name}, and one clear question.\n"
            f"3. Mention proof from {proof} if the form asks for experience.\n"
            f"4. Send only via that official route and note today’s date.\n\n"
            "_Do not invent deadlines. Use the official page only._"
        )
        sources = ["National Careers Service — applications"]
    elif family == "course_check":
        why = _why_line(
            profile, name, angle="this step checks the real course details"
        )
        detail = (
            f"1. Open the official page for {name} ({site}).\n"
            f"2. Note what they ask for and how to apply — do not guess grades or fees.\n"
            f"3. Link two points from {proof} to the course themes around {interest}.\n"
            f"4. Write two questions if anything is unclear.\n\n"
            "_Always verify details on the provider’s own page._"
        )
        sources = ["UCAS / provider course pages (applied)"]
    else:  # follow_up
        why = _why_line(
            profile, name, angle="this step keeps you moving if replies are slow"
        )
        detail = (
            f"1. Note the date you applied, enquired, or saved {name}'s page.\n"
            f"2. Set a calendar reminder to check for a reply.\n"
            f"3. Pick one backup employer or course linked to {interest}.\n"
            f"4. Keep your proof notes from {proof} ready for the backup option.\n\n"
            "_Silence does not mean yes or no — keep one other route warm._"
        )
        sources = ["National Careers Service — applications"]

    return {
        "step_id": step_id,
        "source": "offline",
        "profile_hooks": hooks,
        "why_this_step": why,
        "detail_markdown": detail,
        "checklist": [],
        "sources_used": sources,
        "match_kind": match_kind,
        "step_family": family,
    }


def _howto_query(
    *,
    mode: str,
    leaver: dict[str, Any],
    match: dict[str, Any],
    step: dict[str, Any],
) -> str:
    profile = _build_profile_state(leaver)
    match_kind = _classify_match_kind(mode, match)
    title = str(step.get("title") or "")
    summary = str(step.get("summary") or "")
    exp_bit = (
        "has work experience"
        if profile["has_experience"]
        else "no paid experience yet skills sheet courses projects STAR"
    )
    return (
        f"{mode} {match_kind} step: {title}. {summary}. {exp_bit}. "
        f"cv application star interview enquiry apprenticeship course check "
        f"membership professional body volunteer. "
        f"interests: {profile['interest_label']}. "
        f"match: {_match_label(match)}."
    )


def _retrieve_howto_context(
    *,
    mode: str,
    leaver: dict[str, Any],
    match: dict[str, Any],
    step: dict[str, Any],
    top_k: int = 4,
) -> list[dict[str, Any]]:
    try:
        from .rag import retrieve_howto

        return retrieve_howto(
            _howto_query(mode=mode, leaver=leaver, match=match, step=step),
            top_k=top_k,
        )
    except Exception:
        return []


def _format_howto_blocks(hits: list[dict[str, Any]]) -> str:
    if not hits:
        return "No how-to cards retrieved."
    lines: list[str] = []
    for i, h in enumerate(hits, 1):
        label = h.get("source_label") or h.get("source") or "how-to"
        card = h.get("card") or {}
        if card:
            tip = " ".join(str(card.get("tip") or "").split())
            do = " ".join(str(card.get("do") or "").split())
            lines.append(f"{i}. [{label}] Tip: {tip} Do: {do}")
        else:
            chunk = " ".join(str(h.get("chunk") or "").split())[:500]
            lines.append(f"{i}. [{label}] {chunk}")
    return "\n".join(lines)


def _contains_banned(text: str) -> bool:
    low = (text or "").lower()
    return any(p in low for p in _BANNED_PHRASES)


def _has_placeholder_leak(text: str) -> bool:
    low = (text or "").lower()
    return any(p in low for p in _PLACEHOLDER_LEAKS)


def _strip_redundant_detail(
    detail: str,
    *,
    why: str,
    title: str,
) -> str:
    """Drop repeated step title / why line — those belong in the For you UI."""
    text = (detail or "").strip()
    if not text:
        return text

    why_norm = " ".join((why or "").split()).strip().lower()
    title_norm = " ".join((title or "").split()).strip().lower()

    blocks = [b.strip() for b in re.split(r"\n\s*\n", text) if b.strip()]
    kept: list[str] = []
    for block in blocks:
        lines = [ln.strip() for ln in block.splitlines() if ln.strip()]
        if not lines:
            continue
        first = lines[0]
        first_plain = re.sub(r"^#+\s*", "", first).strip().lower()
        block_plain = " ".join(
            re.sub(r"^#+\s*", "", ln).strip() for ln in lines
        ).lower()

        if title_norm and first_plain == title_norm and len(lines) == 1:
            continue
        if why_norm and (block_plain == why_norm or first_plain == why_norm):
            continue
        if title_norm and first_plain == title_norm:
            rest = "\n".join(lines[1:]).strip()
            if rest:
                kept.append(rest)
            continue
        kept.append(block)

    return "\n\n".join(kept).strip()


def _call_gemini_json(
    prompt: str,
    *,
    mode: str,
    system: str | None = None,
    temperature: float = 0.4,
) -> Any:
    client = _gemini_client()
    if client is None:
        raise RuntimeError("GEMINI_API_KEY not configured")
    from google.genai import types

    last_err: Exception | None = None
    for model_name in _GEMINI_MODEL_FALLBACKS:
        try:
            response = client.models.generate_content(
                model=model_name,
                contents=prompt,
                config=types.GenerateContentConfig(
                    system_instruction=system or _system_for_mode(mode),
                    temperature=temperature,
                    response_mime_type="application/json",
                ),
            )
            text = getattr(response, "text", None) or ""
            return _extract_json(text)
        except Exception as e:
            last_err = e
            err = str(e).lower()
            if any(
                x in err
                for x in (
                    "429",
                    "resource_exhausted",
                    "quota",
                    "404",
                    "not_found",
                    "no longer available",
                )
            ):
                continue
            raise
    raise last_err or RuntimeError("Gemini JSON call failed")


def _call_gemini_text(prompt: str, *, mode: str) -> str:
    client = _gemini_client()
    if client is None:
        raise RuntimeError("GEMINI_API_KEY not configured")
    from google.genai import types

    last_err: Exception | None = None
    for model_name in _GEMINI_MODEL_FALLBACKS:
        try:
            response = client.models.generate_content(
                model=model_name,
                contents=prompt,
                config=types.GenerateContentConfig(
                    system_instruction=_system_for_mode(mode),
                    temperature=0.5,
                ),
            )
            return (getattr(response, "text", None) or "").strip()
        except Exception as e:
            last_err = e
            err = str(e).lower()
            if any(
                x in err
                for x in (
                    "429",
                    "resource_exhausted",
                    "quota",
                    "404",
                    "not_found",
                    "no longer available",
                )
            ):
                continue
            raise
    raise last_err or RuntimeError("Gemini text call failed")


def _offline_chat_reply(
    *,
    message: str,
    leaver: dict[str, Any],
    match: dict[str, Any],
    step: dict[str, Any],
) -> str:
    profile = _build_profile_state(leaver)
    name = _match_label(match)
    interest = profile["interest_label"]
    proof = profile["proof_label"]
    msg = (message or "").lower()
    title = str(step.get("title") or "").lower()

    if any(k in msg for k in ("cv", "resume", "curriculum")) or "cv" in title:
        role_hint = ""
        for token in ("python", "software", "developer", "retail", "care", "warehouse"):
            if token in msg:
                role_hint = token
                break
        role_bit = (
            f"your {role_hint} work"
            if role_hint
            else (proof if profile["has_experience"] else "your strongest project or course work")
        )
        return (
            f"On your one-page CV for {name}, put {role_bit} under Experience.\n\n"
            "Use 2–3 bullets: what you built or did, tools you used, and one result "
            f"(for example a feature shipped, a bug fixed, or a skill gained). "
            f"In a short profile line, link that to {interest}.\n\n"
            "Keep it honest and easy to explain if they ask."
        )

    if any(k in msg for k in ("star", "example", "interview")):
        return (
            f"Pick one real example linked to {interest}. Write four short lines — "
            "Situation, Task, Action (what YOU did), Result. "
            f"Aim for under two minutes spoken. Tie the result to why {name} could care."
        )

    if any(k in msg for k in ("email", "enquiry", "message", "write")):
        return (
            f"Keep the message short: who you are, why {interest} fits {name}, "
            "one clear question (how to apply / next open day / entry needs), and thanks. "
            "Send only via their official contact route."
        )

    return (
        f"For this step on {name}: use the numbered actions above, "
        f"and ground them in {proof}. "
        "Check their official website before you act. "
        "Ask me one specific part if you want help wording it."
    )


def _context_blob(
    *,
    mode: str,
    leaver: dict[str, Any],
    match: dict[str, Any],
) -> str:
    profile = _build_profile_state(leaver)
    match_kind = _classify_match_kind(mode, match)
    return json.dumps(
        {
            "mode": mode,
            "match_kind": match_kind,
            "profile_state": {
                "location": profile["location"],
                "interests": profile["interests"],
                "has_experience": profile["has_experience"],
                "experience": profile["experience"],
                "courses": profile["courses"],
                "proof_sources": profile["proof_sources"],
                "qualification_level": profile["qualification_level"],
                "availability": profile["availability"],
                "leaver_type": profile["leaver_type"],
                "proud_example": profile.get("proud_example"),
                "goal_sentence": profile.get("goal_sentence"),
                "barriers": profile.get("barriers"),
                "must_haves": profile.get("must_haves"),
                "support_available": profile.get("support_available"),
                "apply_readiness": profile.get("apply_readiness"),
                "hooks": profile["hooks"],
            },
            "leaver_raw": {
                "leaver_type": leaver.get("leaver_type"),
                "location": leaver.get("location"),
                "courses": leaver.get("courses"),
                "interests": leaver.get("interests"),
                "passions": leaver.get("passions"),
                "work_experience": leaver.get("work_experience"),
                "qualification_level": leaver.get("qualification_level"),
                "availability": leaver.get("availability"),
                "proud_example": leaver.get("proud_example"),
                "goal_sentence": leaver.get("goal_sentence"),
                "barriers": leaver.get("barriers"),
                "must_haves": leaver.get("must_haves"),
                "support_available": leaver.get("support_available"),
                "apply_readiness": leaver.get("apply_readiness"),
                "profile_text": leaver.get("profile_text"),
                "interest_sectors": leaver.get("interest_sectors")
                or leaver.get("target_sectors"),
                "persona": leaver.get("persona"),
            },
            "match": {
                "name": match.get("name"),
                "kind": match.get("kind"),
                "town": match.get("town"),
                "provider": match.get("provider"),
                "service": match.get("service"),
                "website": match.get("website"),
                "summary": match.get("summary"),
                "course_type_label": match.get("course_type_label"),
                "level": match.get("level"),
                "sectors": match.get("sectors"),
                "entry_routes": match.get("entry_routes"),
                "overall_label": match.get("overall_label"),
                "sector_fit_label": match.get("sector_fit_label"),
                "entry_fit_label": match.get("entry_fit_label"),
                "hiring_label": match.get("hiring_label"),
            },
        },
        ensure_ascii=False,
    )


def generate_plan(
    *,
    mode: str,
    leaver: dict[str, Any],
    match: dict[str, Any],
) -> dict[str, Any]:
    mode = (mode or "work").strip().lower()
    if mode not in {"work", "education", "military"}:
        mode = "work"

    offline = _offline_plan(mode, match, leaver)
    if _gemini_client() is None:
        return offline

    profile = _build_profile_state(leaver)
    match_kind = offline.get("match_kind") or _classify_match_kind(mode, match)

    prompt = f"""Create a 5-step action plan personalised to this young person and match.

CONTEXT_JSON:
{_context_blob(mode=mode, leaver=leaver, match=match)}

OFFLINE_TEMPLATE_STEPS (you may rewrite titles/summaries but keep personalisation intent):
{json.dumps(offline["steps"], ensure_ascii=False)}

Return JSON only:
{{
  "steps": [
    {{
      "id": "s1",
      "title": "short title",
      "summary": "1-2 short sentences on what to do",
      "timeframe": "This week" | "This month" | "Next",
      "family": "fit_check|proof_gather|openings|local_support|apply_enquire|follow_up|course_check"
    }}
  ]
}}

Rules:
- Exactly 5 steps, ids s1..s5.
- match_kind is "{match_kind}". Shape steps for that kind.
- has_experience is {profile["has_experience"]}. If false, do NOT use a normal job-history CV step;
  use proof from courses/projects instead. Never write "None yet".
- Titles: max 6 simple words. Summaries: max 35 simple words.
- Mention real interests/location/proof where natural.
- No invented deadlines, fees, vacancies, or guarantees.
{_SIMPLE_ENGLISH_REMINDER}
"""
    try:
        data = _call_gemini_json(prompt, mode=mode)
        steps_in = data.get("steps") if isinstance(data, dict) else data
        if not isinstance(steps_in, list) or len(steps_in) < 5:
            return offline

        steps = []
        families: dict[str, str] = {}
        for i, raw in enumerate(steps_in[:5]):
            if not isinstance(raw, dict):
                return offline
            sid = str(raw.get("id") or f"s{i+1}")
            title = str(raw.get("title") or f"Step {i+1}")[:60]
            summary = str(raw.get("summary") or "")[:220]
            if _has_placeholder_leak(f"{title} {summary}"):
                return offline
            family = str(raw.get("family") or "").strip() or _family_for_step(
                {"id": sid, "title": title, "summary": summary},
                mode=mode,
                match_kind=match_kind,
                families=offline.get("step_families"),
            )
            families[sid] = family
            steps.append(
                {
                    "id": sid,
                    "title": title,
                    "summary": summary,
                    "timeframe": str(raw.get("timeframe") or "This month")[:40],
                }
            )
        return {
            "plan_id": f"gemini-{uuid.uuid4().hex[:10]}",
            "source": "gemini",
            "match_name": _match_label(match),
            "match_kind": match_kind,
            "steps": steps,
            "step_families": families,
            "disclaimer": offline["disclaimer"],
        }
    except Exception:
        return offline


def breakdown_step(
    *,
    mode: str,
    leaver: dict[str, Any],
    match: dict[str, Any],
    step: dict[str, Any],
    sibling_steps: list[dict[str, Any]] | None = None,
    step_families: dict[str, str] | None = None,
) -> dict[str, Any]:
    mode = (mode or "work").strip().lower()
    if mode not in {"work", "education", "military"}:
        mode = "work"

    # Infer families from sibling plan titles when client did not send them
    families = dict(step_families or {})
    if not families and sibling_steps:
        mk = _classify_match_kind(mode, match)
        for s in sibling_steps:
            if isinstance(s, dict) and s.get("id"):
                families[str(s["id"])] = _family_for_step(
                    s, mode=mode, match_kind=mk, families=None
                )

    offline = _offline_breakdown(
        step,
        leaver=leaver,
        match=match,
        mode=mode,
        families=families,
    )
    hooks = list(offline.get("profile_hooks") or _profile_hooks(leaver))
    profile = _build_profile_state(leaver)
    match_kind = str(offline.get("match_kind") or _classify_match_kind(mode, match))

    siblings = []
    for s in sibling_steps or []:
        if not isinstance(s, dict):
            continue
        if str(s.get("id") or "") == str(step.get("id") or ""):
            continue
        siblings.append(
            {
                "id": s.get("id"),
                "title": s.get("title"),
                "summary": s.get("summary"),
            }
        )

    howto_hits = _retrieve_howto_context(
        mode=mode, leaver=leaver, match=match, step=step, top_k=4
    )
    howto_block = _format_howto_blocks(howto_hits)
    source_labels = []
    for h in howto_hits:
        label = str(h.get("source_label") or "").strip()
        if not label:
            card = h.get("card") or {}
            label = str(card.get("source_label") or h.get("source") or "").strip()
        if label and label not in source_labels:
            source_labels.append(label)

    if _gemini_client() is None:
        if source_labels and not offline.get("sources_used"):
            offline["sources_used"] = source_labels[:4]
        return offline

    prompt = f"""Break down THIS single action-plan step for this young person.

CONTEXT_JSON:
{_context_blob(mode=mode, leaver=leaver, match=match)}

STEP_JSON:
{json.dumps(step, ensure_ascii=False)}

STEP_FAMILY: {offline.get("step_family")}
MATCH_KIND: {match_kind}
HAS_EXPERIENCE: {profile["has_experience"]}
PROOF_LABEL: {profile["proof_label"]}

OTHER_STEPS_IN_PLAN_JSON (do NOT cover these):
{json.dumps(siblings, ensure_ascii=False)}

HOW_TO_CONTEXT:
{howto_block}

Suggested profile_hooks:
{json.dumps(hooks, ensure_ascii=False)}

Return JSON only:
{{
  "profile_hooks": ["2 to 4 short facts from THEIR profile"],
  "why_this_step": "1 sentence linking profile + match + this step",
  "detail_markdown": "numbered concrete actions only (start at 1.) — no heading, no why",
  "checklist": [],
  "sources_used": ["source_label strings from HOW_TO_CONTEXT"]
}}

Rules:
- Never write "None yet" or ask how empty experience matters.
- If HAS_EXPERIENCE is false, use courses/projects/skills-sheet language.
- If MATCH_KIND is professional_body, do not treat it as a job vacancy board.
- detail_markdown must not repeat why_this_step or the step title.
- Keep detail_markdown under 180 words.
{_SIMPLE_ENGLISH_REMINDER}
"""
    try:
        data = _call_gemini_json(
            prompt,
            mode=mode,
            system=_system_for_breakdown(mode),
            temperature=0.35,
        )
        if not isinstance(data, dict):
            raise ValueError("bad shape")

        detail = str(data.get("detail_markdown") or "").strip()
        why = str(data.get("why_this_step") or "").strip()
        model_hooks = data.get("profile_hooks") or hooks
        if not isinstance(model_hooks, list):
            model_hooks = hooks
        model_hooks = [
            str(x)[:80]
            for x in model_hooks
            if str(x).strip() and not _is_empty_experience(str(x))
        ][:4]
        if not model_hooks:
            model_hooks = hooks

        sources = data.get("sources_used") or source_labels
        if not isinstance(sources, list):
            sources = source_labels
        sources = [str(x)[:120] for x in sources if str(x).strip()][:4]

        combined = f"{why}\n{detail}"
        if (
            not detail
            or _contains_banned(combined)
            or _has_placeholder_leak(combined)
        ):
            return offline

        if _match_label(match).lower() not in why.lower() and not any(
            h.lower() in why.lower() for h in model_hooks if h
        ):
            why = str(offline.get("why_this_step") or why)

        detail = _strip_redundant_detail(
            detail,
            why=why,
            title=str(step.get("title") or ""),
        )
        if not detail:
            detail = str(offline.get("detail_markdown") or "")

        return {
            "step_id": str(step.get("id") or "s1"),
            "source": "gemini",
            "profile_hooks": model_hooks or hooks,
            "why_this_step": why[:280],
            "detail_markdown": detail[:4000],
            "checklist": [],
            "sources_used": sources or source_labels[:4],
            "match_kind": match_kind,
            "step_family": offline.get("step_family"),
        }
    except Exception:
        return offline


def chat_about_step(
    *,
    mode: str,
    leaver: dict[str, Any],
    match: dict[str, Any],
    step: dict[str, Any],
    breakdown: dict[str, Any] | None,
    history: list[dict[str, str]],
    message: str,
) -> dict[str, Any]:
    mode = (mode or "work").strip().lower()
    if mode not in {"work", "education", "military"}:
        mode = "work"

    msg = (message or "").strip()
    if not msg:
        return {
            "reply_markdown": "Ask a short question about this step.",
            "source": "offline",
        }
    if len(msg) > 500:
        msg = msg[:500]

    hist = []
    for turn in (history or [])[-8:]:
        role = str(turn.get("role") or "")
        content = str(turn.get("content") or "").strip()
        if role in {"user", "assistant"} and content:
            hist.append({"role": role, "content": content[:800]})

    if _gemini_client() is None:
        return {
            "reply_markdown": _offline_chat_reply(
                message=msg, leaver=leaver, match=match, step=step
            ),
            "source": "offline",
        }

    profile = _build_profile_state(leaver)
    prompt = f"""Answer the young person's question about ONE action-plan step.

CONTEXT_JSON:
{_context_blob(mode=mode, leaver=leaver, match=match)}

STEP_JSON:
{json.dumps(step, ensure_ascii=False)}

BREAKDOWN_JSON:
{json.dumps(breakdown or {}, ensure_ascii=False)}

CHAT_HISTORY_JSON:
{json.dumps(hist, ensure_ascii=False)}

THEIR_MESSAGE:
{msg}

Reply in markdown.
- Under 120 words.
- has_experience={profile["has_experience"]}; proof_label={profile["proof_label"]}.
- Never write "None yet". If no job history, talk about courses/projects as proof.
- Concrete action (verb + object). No vague "one small thing".
- Stay on this step and match. No invented deadlines/vacancies/funding.
{_SIMPLE_ENGLISH_REMINDER}
"""
    try:
        reply = _call_gemini_text(prompt, mode=mode)
        if not reply:
            raise ValueError("empty")
        if _contains_banned(reply) or _has_placeholder_leak(reply):
            reply = _offline_chat_reply(
                message=msg, leaver=leaver, match=match, step=step
            )
            return {"reply_markdown": reply[:3000], "source": "offline"}
        return {"reply_markdown": reply[:3000], "source": "gemini"}
    except Exception:
        return {
            "reply_markdown": _offline_chat_reply(
                message=msg, leaver=leaver, match=match, step=step
            ),
            "source": "offline",
        }


def gemini_configured() -> bool:
    return _gemini_client() is not None
