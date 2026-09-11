"""Data provenance labels and prompt-safe fact blocks for matches."""

from __future__ import annotations

from typing import Any

from .labels import clean_company_summary, is_registry_website, public_employer_website

FIND_APPRENTICESHIP_URL = "https://www.findapprenticeship.service.gov.uk/"
COMPANIES_HOUSE_HINTS = (
    "company-information.service.gov.uk",
    "companieshouse.gov.uk",
    "find-and-update.company-information",
)


# Normalise raw `source` column values from masters / seeds.
def raw_source(row: dict[str, Any] | None) -> str:
    return str((row or {}).get("source") or "").strip().lower()


# True when the row looks like Companies House registry facts, not careers copy.
def is_companies_house_style(row: dict[str, Any] | None) -> bool:
    row = row or {}
    website = str(row.get("website") or "").lower()
    summary = str(row.get("summary") or "").lower()
    if is_registry_website(website) or any(h in website for h in COMPANIES_HOUSE_HINTS):
        return True
    if "companies house" in summary or "nature of business" in summary:
        return True
    # Template used when CH employers are upserted into seed.
    if (
        "routes vary" in summary
        and "find an apprenticeship" in summary
        and ("working in" in summary or "-based employer" in summary)
    ):
        return True
    return False


# Classify employer provenance for UI + prompts.
def classify_employer_source(row: dict[str, Any] | None) -> str:
    """Return one of: vacancies | companies_house | seed | catalogue | unknown."""
    row = row or {}
    src = raw_source(row)
    if src == "vacancies":
        return "vacancies"
    if src in {"companies_house", "ch", "companies-house"}:
        return "companies_house"
    if is_companies_house_style(row):
        return "companies_house"
    if src in {"seed", "curated", "manual"}:
        return "seed"
    if src in {"ncs", "national_careers", "catalogue", "dfe"}:
        return "catalogue"
    if src:
        return src
    if is_companies_house_style(row):
        return "companies_house"
    return "seed" if (row.get("name") or row.get("title")) else "unknown"


# Short human label for match cards.
def source_label(kind: str, *, mode: str = "work") -> str:
    mode = (mode or "work").strip().lower()
    kind = (kind or "").strip().lower()
    if mode == "education":
        return {
            "ncs": "National Careers Service catalogue",
            "catalogue": "Course catalogue",
            "seed": "Curated course list",
        }.get(kind, "Course catalogue")
    if mode == "military":
        return "Armed Forces careers pathway"
    return {
        "vacancies": "Find an apprenticeship open data",
        "companies_house": "Companies House registry facts",
        "seed": "Curated local employer profile",
        "catalogue": "Open data catalogue",
    }.get(kind, "Employer directory")


# One-line caveat shown under the match header.
def source_note(kind: str, *, mode: str = "work") -> str:
    mode = (mode or "work").strip().lower()
    kind = (kind or "").strip().lower()
    if mode == "education":
        return "Confirm fees, entry rules, and start dates on the provider’s official page."
    if mode == "military":
        return "Guidance only — check eligibility and entry rules on official Armed Forces careers pages."
    if kind == "vacancies":
        return (
            "Based on Find an apprenticeship open data. Listings may be historical or closed — "
            "always check live openings."
        )
    if kind == "companies_house":
        return (
            "Registry facts only (location / nature of business). Not a careers page — "
            "verify openings on the employer site or Find an apprenticeship."
        )
    return "Check the employer’s official careers page before you apply."


# Location line used on match cards and in LLM fact blocks.
def _listed_location_line(row: dict[str, Any]) -> str:
    name = str(row.get("name") or "This employer").strip() or "This employer"
    town = str(row.get("town") or "").strip()
    postcode = str(row.get("postcode") or "").strip()
    if town:
        listed = f"{name} is listed in {town}"
        if postcode:
            listed = f"{listed} ({postcode})"
        return f"{listed}."
    return f"{name} is a Gloucestershire employer."


# Leaver-facing summary that stays factual for CH / vacancy / seed rows.
def display_summary(row: dict[str, Any] | None, *, mode: str = "work") -> str:
    row = row or {}
    mode = (mode or "work").strip().lower()
    raw = str(row.get("summary") or "").strip()
    if mode != "work":
        return raw

    kind = classify_employer_source(row)
    if kind == "companies_house":
        return clean_company_summary(raw) or (
            f"{row.get('town') or 'Local'}-based employer. "
            "Routes vary — check their careers page and Find an apprenticeship."
        )
    if kind == "vacancies":
        town = str(row.get("town") or "").strip()
        lead = f"{town} employer" if town else "Local employer"
        return (
            f"{lead} seen in Find an apprenticeship open data. "
            "Role titles in that feed may be historical — confirm live vacancies "
            "on the service. This is not a list of open jobs."
        )
    return ""


# Location/sector line for LLM facts — never curated marketing about routes.
def _prompt_fact_summary(
    row: dict[str, Any],
    *,
    kind: str,
    name: str,
    town: str,
    postcode: str,
) -> str:
    """Seed/CH marketing blurbs mention apprenticeships; those are not verified schemes."""
    if kind == "vacancies":
        return display_summary(row, mode="work") or "n/a"
    listed = _listed_location_line(
        {"name": name, "town": town, "postcode": postcode}
    )
    return f"{listed} Location and matcher sector tags only — not a programme list."


# Structured FACTS block for LLM employer briefings (no narrative invention).
def employer_facts_block(row: dict[str, Any] | None) -> str:
    row = row or {}
    kind = classify_employer_source(row)
    name = str(row.get("name") or "Employer").strip()
    town = str(row.get("town") or "").strip()
    postcode = str(row.get("postcode") or "").strip()
    sectors = str(row.get("sectors") or "").strip()
    routes = str(row.get("entry_routes") or "").strip()
    website = public_employer_website(row.get("website"))
    summary = _prompt_fact_summary(
        row, kind=kind, name=name, town=town, postcode=postcode
    )

    if kind == "vacancies":
        routes_line = f"- Entry routes (matcher tags): {routes or 'n/a'}"
    else:
        routes_line = "- Entry routes (matcher tags): unknown"
    lines = [
        "VERIFIED EMPLOYER FACTS (use only these as company claims):",
        f"- Name: {name}",
        f"- Town / area: {town or 'n/a'}",
        f"- Postcode: {postcode or 'n/a'}",
        f"- Sectors (matcher tags): {sectors or 'n/a'}",
        routes_line,
        f"- Website / careers link: {website or 'none on file — use Find an apprenticeship'}",
        f"- Data source: {source_label(kind)}",
        f"- Fact summary: {summary or 'n/a'}",
    ]
    open_url = str(row.get("open_url") or "").strip()
    if open_url.startswith("http"):
        lines.append(f"- Open opportunity (official listing): {open_url}")
    if kind == "vacancies":
        lines.append(
            "- Vacancy note: any role titles in the summary are from open data and may be closed."
        )
    if kind == "companies_house":
        lines.append(
            "- Registry note: do not invent apprenticeships, culture, or hiring claims beyond this block."
        )
    lines.append(f"- Official check URL: {FIND_APPRENTICESHIP_URL}")
    return "\n".join(lines)


# Prefix RAG chunks so the model knows catalogue vs strategy vs historical vacancies.
def annotate_retrieved_chunk(source: str, chunk: str) -> str:
    src = str(source or "").lower()
    text = str(chunk or "").strip()
    if not text:
        return text
    if "evidence" in src or text.startswith("STRATEGY:"):
        return f"[CAREERS ADVICE — research STRATEGY card]\n{text}"
    if "howto" in src:
        return f"[HOW-TO CARD — general guidance]\n{text}"
    if "opportunit" in src or text.lower().startswith("opportunity at"):
        return (
            "[HISTORICAL / MAY BE CLOSED — Find an apprenticeship or catalogue opportunity]\n"
            f"{text}"
        )
    if "company" in src or text.lower().startswith("company:"):
        return f"[CATALOGUE SNAPSHOT — verify on official site]\n{text}"
    if "sector" in src:
        return f"[SECTOR GUIDE — general]\n{text}"
    return text


# Payload fields shared by API match rows.
def provenance_payload(row: dict[str, Any] | None, *, mode: str = "work") -> dict[str, str]:
    kind = classify_employer_source(row) if mode == "work" else raw_source(row) or (
        "catalogue" if mode == "education" else "military"
    )
    if mode == "education" and not kind:
        kind = "catalogue"
    if mode == "military":
        kind = "military"
    return {
        "source": kind,
        "source_label": source_label(kind, mode=mode),
        "source_note": source_note(kind, mode=mode),
    }
