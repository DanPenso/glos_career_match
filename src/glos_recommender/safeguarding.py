"""Age eligibility and lightweight safeguarding helpers for MatchKite.

Self-declared age bands only — not identity verification.
Crisis text is never logged; referral copy is fixed (not model-generated).
"""

from __future__ import annotations

import re
from typing import Any

AGE_BAND_UNDER_16 = "under_16"
AGE_BAND_16_17 = "16_17"
AGE_BAND_18_24 = "18_24"
AGE_BAND_25_PLUS = "25_plus"
AGE_BAND_PREFER_NOT = "prefer_not"

AGE_BANDS: tuple[str, ...] = (
    AGE_BAND_UNDER_16,
    AGE_BAND_16_17,
    AGE_BAND_18_24,
    AGE_BAND_25_PLUS,
    AGE_BAND_PREFER_NOT,
)

AGE_BAND_LABELS: dict[str, str] = {
    AGE_BAND_UNDER_16: "Under 16",
    AGE_BAND_16_17: "16–17",
    AGE_BAND_18_24: "18–24",
    AGE_BAND_25_PLUS: "25+",
    AGE_BAND_PREFER_NOT: "Prefer not to say",
}

# Fixed UK-facing referral (not AI-generated). Keep short and calm.
SAFEGUARDING_REPLY_MARKDOWN = """\
**If you need help now**

MatchKite is only for careers ideas. We cannot support you with personal safety \
or mental health.

- If you are in **immediate danger**, call **999**
- **Childline** (under 19): **0800 1111** · [childline.org.uk](https://www.childline.org.uk)
- **Samaritans**: **116 123** · [samaritans.org](https://www.samaritans.org)
- For careers help in person, ask a teacher, tutor, or local careers adviser

You can close this and go back to your matches when you are ready.
"""

UNDER_16_DETAIL = (
    "MatchKite is for people aged 16 and over. "
    "Please ask a parent, carer, teacher, or careers adviser to help you explore options."
)

MILITARY_AGE_NOTICE = (
    "Military pathways here are information only. Entry ages and rules come from "
    "official Armed Forces sites. If you are under 18, talk this through with a "
    "parent, carer, or careers adviser before taking any next step."
)

HEALTH_BARRIER_NOTE = (
    "This helps matching. It is not medical advice — check official course or "
    "employer pages and support services."
)

# Conservative keyword screen for free text / chat. Prefer false positives.
_SAFETY_PATTERNS: tuple[re.Pattern[str], ...] = tuple(
    re.compile(p, re.I)
    for p in (
        r"\bkill\s+my\s*self\b",
        r"\bkilling\s+myself\b",
        r"\bsuicid",
        r"\bself[-\s]?harm",
        r"\bcut(?:ting)?\s+myself\b",
        r"\bend\s+my\s+life\b",
        r"\bwant\s+to\s+die\b",
        r"\bdon'?t\s+want\s+to\s+(?:live|be\s+alive)\b",
        r"\boverdose\b",
        r"\bhang\s+myself\b",
        r"\bsexually\s+abus",
        r"\bbeing\s+abus(?:ed|e)\b",
        r"\bdomestic\s+abus",
        r"\brape\b",
        r"\bgroom(?:ing|ed)\b",
        r"\bin\s+danger\b",
        r"\bimmediate\s+danger\b",
        r"\bhurt\s+(?:me|myself)\b",
    )
)


def normalise_age_band(value: Any) -> str:
    raw = str(value or "").strip().lower().replace("–", "-").replace(" ", "_")
    aliases = {
        "under16": AGE_BAND_UNDER_16,
        "under-16": AGE_BAND_UNDER_16,
        "16-17": AGE_BAND_16_17,
        "16_17": AGE_BAND_16_17,
        "18-24": AGE_BAND_18_24,
        "18_24": AGE_BAND_18_24,
        "25+": AGE_BAND_25_PLUS,
        "25_plus": AGE_BAND_25_PLUS,
        "25-plus": AGE_BAND_25_PLUS,
        "prefer_not_to_say": AGE_BAND_PREFER_NOT,
        "prefer-not": AGE_BAND_PREFER_NOT,
        "prefer_not": AGE_BAND_PREFER_NOT,
    }
    if raw in AGE_BANDS:
        return raw
    return aliases.get(raw, "")


def age_band_allowed_for_match(age_band: str) -> bool:
    band = normalise_age_band(age_band)
    return bool(band) and band != AGE_BAND_UNDER_16


def age_band_allows_ai(age_band: str) -> bool:
    """AI opt-in only when the user has declared they are 16+."""
    band = normalise_age_band(age_band)
    return band in {
        AGE_BAND_16_17,
        AGE_BAND_18_24,
        AGE_BAND_25_PLUS,
    }


def show_military_age_notice(age_band: str) -> bool:
    band = normalise_age_band(age_band)
    return band in {AGE_BAND_16_17, AGE_BAND_PREFER_NOT, AGE_BAND_UNDER_16, ""}


def is_youth_band(age_band: str) -> bool:
    band = normalise_age_band(age_band)
    return band in {AGE_BAND_16_17, AGE_BAND_PREFER_NOT}


def looks_like_safety_concern(*texts: str) -> bool:
    blob = " ".join(str(t or "") for t in texts).strip()
    if not blob:
        return False
    return any(p.search(blob) for p in _SAFETY_PATTERNS)


def safeguarding_chat_response() -> dict[str, Any]:
    return {
        "reply_markdown": SAFEGUARDING_REPLY_MARKDOWN.strip(),
        "source": "safeguarding",
    }


def age_bands_for_taxonomy() -> list[dict[str, str]]:
    return [{"id": k, "label": AGE_BAND_LABELS[k]} for k in AGE_BANDS]
