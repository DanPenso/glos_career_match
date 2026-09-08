"""Grounded thin-record work briefings skip OpenAI and pathway-card invention."""

from __future__ import annotations

import sys
from types import SimpleNamespace
from typing import Any

import pandas as pd
import pytest

from glos_recommender.briefing import (
    BUILD_NEXT_SYSTEM_PROMPT,
    EMPLOYER_SYSTEM_PROMPT,
    build_employer_briefing_prompt,
    build_work_build_next_prompt,
    fallback_briefing,
    generate_briefing,
)
from glos_recommender.intake_config import pathways_for_sectors
from glos_recommender.matching import match_reasons
from glos_recommender.provenance import employer_facts_block
from glos_recommender.rag import build_retrieval_query, filter_retrieved_hits_for_employer

_GROUNDED_H2 = [
    "## Why this company fits you",
    "## Training routes that fit your interests",
    "## What to build or develop next",
]
_REGISTER_SENTENCE = (
    "That is a location and sector clue from the company register — "
    "not a careers page and not a sign they are hiring."
)

_MOCK_PROGRAMMES = [
    {
        "programme_id": "OPP001",
        "programme_title": "Engineering Apprenticeship",
        "programme_type": "apprenticeship",
        "level": "Level 3-6",
        "summary": "Design manufacture and test of precision measurement systems.",
        "evidence_url": "https://www.renishaw.com/en/careers",
    },
    {
        "programme_id": "OPP002",
        "programme_title": "Graduate Software / Engineering",
        "programme_type": "graduate",
        "level": "Level 6+",
        "summary": "Graduate routes into software metrology and engineering teams.",
        "evidence_url": "https://www.renishaw.com/en/careers",
    },
]


def _assert_grounded(md: str, source: str, *, pathway_titles: list[str]) -> None:
    assert source == "grounded_template"
    headings = [line for line in md.splitlines() if line.startswith("## ")]
    assert headings == _GROUNDED_H2
    lowered = md.lower()
    assert "hiring you" not in lowered
    assert "we do not have a verified programme list" not in lowered
    assert "treat that as careers advice" not in lowered
    assert "nothing you must enrol on" not in lowered
    assert "## Your first steps this month" not in md
    for title in pathway_titles:
        assert title not in md


def _leaver(**overrides: Any) -> dict[str, Any]:
    base: dict[str, Any] = {
        "profile_text": "career changer interested in construction",
        "interests": ["Construction & built environment"],
        "passions": ["Making products people use"],
        "work_experience": [],
        "availability": "Exploring only",
        "qualification_level": "No formal qualifications yet",
        "interest_sectors": {"construction_green"},
        "target_sectors": {"construction_green"},
        "proud_example": "bike repair",
        "entry_routes": {"apprenticeship"},
    }
    base.update(overrides)
    return base


def _renishaw_leaver(**overrides: Any) -> dict[str, Any]:
    return _leaver(
        profile_text="school leaver interested in aerospace and making things",
        interests=["Aerospace", "Making things", "Trade or engineering"],
        interest_sectors={"aerospace_manufacturing"},
        target_sectors={"aerospace_manufacturing"},
        **overrides,
    )


def _ch_row(**overrides: Any) -> dict[str, Any]:
    base: dict[str, Any] = {
        "company_id": "thin-ch-crux",
        "name": "Crux Product Design Ltd",
        "town": "Bristol",
        "postcode": "BS4",
        "sectors": "construction_green",
        "entry_routes": "apprenticeship",
        "website": "https://careers.cruxproductdesign.com",
        "source": "companies_house",
        "summary": "Companies House-listed employer. Nature of business (SIC): 71121.",
    }
    base.update(overrides)
    return base


def _vacancy_row(**overrides: Any) -> dict[str, Any]:
    base: dict[str, Any] = {
        "company_id": "thin-vac-1",
        "name": "Severn Digital Ltd",
        "town": "Gloucester",
        "postcode": "GL1 1AA",
        "sectors": "cyber_digital",
        "entry_routes": "apprenticeship",
        "website": "https://severndigital.example/careers",
        "source": "vacancies",
        "summary": "Software developer apprenticeship (may be closed).",
    }
    base.update(overrides)
    return base


def _seed_row(**overrides: Any) -> dict[str, Any]:
    base: dict[str, Any] = {
        "company_id": "seed-renishaw-test",
        "name": "Renishaw",
        "town": "Wotton-under-Edge",
        "postcode": "GL12",
        "sectors": "aerospace_manufacturing|cyber_digital",
        "entry_routes": "apprenticeship|graduate|higher_apprenticeship",
        "website": "https://www.renishaw.com/en/careers",
        "source": "seed",
        "summary": "Precision engineering and metrology employer in Gloucestershire.",
    }
    base.update(overrides)
    return base


def _pathway_titles(*sectors: str) -> list[str]:
    return [str(card["title"]) for card in pathways_for_sectors(list(sectors))]


def _forbid_openai(monkeypatch: pytest.MonkeyPatch) -> dict[str, int]:
    calls = {"openai": 0}

    class Boom:
        def __init__(self, *args: Any, **kwargs: Any) -> None:
            calls["openai"] += 1
            raise AssertionError("OpenAI must not be called for thin work records")

        @property
        def chat(self) -> Any:
            raise AssertionError("OpenAI must not be called for thin work records")

    monkeypatch.setenv("OPENAI_API_KEY", "sk-test-thin-record")
    monkeypatch.setitem(sys.modules, "openai", SimpleNamespace(OpenAI=Boom))
    return calls


def _mock_openai(monkeypatch: pytest.MonkeyPatch, reply: str) -> dict[str, Any]:
    calls: dict[str, Any] = {"n": 0, "messages": []}

    class Client:
        def __init__(self, *args: Any, **kwargs: Any) -> None:
            self.chat = SimpleNamespace(completions=SimpleNamespace(create=self._create))

        def _create(self, **kwargs: Any) -> Any:
            calls["n"] += 1
            calls["messages"] = list(kwargs.get("messages") or [])
            return SimpleNamespace(
                choices=[SimpleNamespace(message=SimpleNamespace(content=reply))]
            )

    monkeypatch.setenv("OPENAI_API_KEY", "sk-test-hybrid-build")
    monkeypatch.setitem(sys.modules, "openai", SimpleNamespace(OpenAI=Client))
    return calls


def _gcc_row(**overrides: Any) -> dict[str, Any]:
    return _seed_row(
        company_id="seed-gcc-test",
        name="Gloucestershire County Council",
        town="Gloucester",
        postcode="GL1",
        sectors="public_sector",
        website="https://www.gloucestershire.gov.uk/jobs",
        summary="Local authority employer.",
        **overrides,
    )


def _gcc_programmes() -> list[dict[str, Any]]:
    return [
        {
            "programme_id": "GCC001",
            "programme_title": "Social Worker Degree Apprenticeship",
            "programme_type": "apprenticeship",
            "level": "Level 6+",
            "summary": "Degree apprenticeship into social work.",
            "evidence_url": "https://www.gloucestershire.gov.uk/jobs",
        }
    ]


def _mixed_interest_leaver(**overrides: Any) -> dict[str, Any]:
    return _leaver(
        profile_text="school leaver interested in public service, healthcare, and aerospace",
        interests=[
            "Public service & community",
            "Healthcare & wellbeing",
            "Aerospace & advanced manufacturing",
        ],
        interest_sectors={"public_sector", "health_care", "aerospace_manufacturing"},
        target_sectors={"public_sector", "health_care", "aerospace_manufacturing"},
        qualification_level="GCSEs / Level 2",
        **overrides,
    )


def _assert_three_work_h2s(text: str) -> None:
    headings = [line for line in text.splitlines() if line.startswith("## ")]
    assert headings == _GROUNDED_H2
    assert "## Your first steps this month" not in text


def test_thin_companies_house_work_briefing_is_grounded(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls = _forbid_openai(monkeypatch)
    monkeypatch.setattr(
        "glos_recommender.briefing.programmes_for_company",
        lambda *args, **kwargs: [],
    )
    md, source = generate_briefing(
        _leaver(),
        _ch_row(),
        use_openai=True,
        mode="work",
    )
    assert calls["openai"] == 0
    _assert_grounded(md, source, pathway_titles=_pathway_titles("construction_green"))
    assert _REGISTER_SENTENCE in md
    assert "(Gatsby)" not in md
    assert md.rstrip().endswith("when you are ready.")
    why = md.split("## Why this company fits you", 1)[1].split("## ", 1)[0]
    assert why.strip().endswith("hiring.")
    assert "company register" in why
    assert "Crux Product Design Ltd is listed in Bristol (BS4)." in md


def test_thin_vacancy_work_briefing_is_grounded(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls = _forbid_openai(monkeypatch)
    monkeypatch.setattr(
        "glos_recommender.briefing.programmes_for_company",
        lambda *args, **kwargs: [],
    )
    md, source = generate_briefing(
        _leaver(
            interests=["Software / apps / web"],
            interest_sectors={"cyber_digital"},
            target_sectors={"cyber_digital"},
            proud_example="",
        ),
        _vacancy_row(),
        use_openai=True,
        mode="work",
    )
    assert calls["openai"] == 0
    _assert_grounded(md, source, pathway_titles=_pathway_titles("cyber_digital"))
    assert "company register" not in md.lower()
    why = md.split("## Why this company fits you", 1)[1].split("## ", 1)[0]
    assert "historical" in why.lower()
    assert why.strip().endswith("hiring.")
    assert "hiring you" not in why.lower()
    assert "https://severndigital.example/careers" in md


def test_thin_seed_without_programmes_skips_openai(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls = _forbid_openai(monkeypatch)
    monkeypatch.setattr(
        "glos_recommender.briefing.programmes_for_company",
        lambda *args, **kwargs: [],
    )
    md, source = generate_briefing(
        _leaver(
            interests=["Cybersecurity & digital defence"],
            interest_sectors={"cyber_digital"},
            target_sectors={"cyber_digital"},
            proud_example="I finished a small website for a family event.",
        ),
        _seed_row(
            company_id="GLC029",
            name="CGI",
            town="Gloucester / Cheltenham corridor",
            postcode="GL1",
            sectors="cyber_digital|business_professional",
            website="https://www.cgi.com/uk/en-gb/careers",
            summary="Global IT employer with digital graduate and apprenticeship pathways.",
        ),
        use_openai=True,
        mode="work",
    )
    assert calls["openai"] == 0
    _assert_grounded(
        md,
        source,
        pathway_titles=[
            "CompTIA Security+",
            "Cyber Security Apprenticeship (cluster SMEs)",
            "Electrician (installation / maintenance)",
        ],
    )
    assert "company register" not in md.lower()
    assert "have previously run" not in md.lower()
    assert "(Gatsby)" not in md
    assert "CGI is listed in Gloucester / Cheltenham corridor (GL1)." in md
    why = md.split("## Why this company fits you", 1)[1].split("## ", 1)[0]
    assert "hiring." not in why
    assert "https://www.cgi.com/uk/en-gb/careers" in md


def test_grounded_why_only_uses_overlapping_interests(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        "glos_recommender.briefing.programmes_for_company",
        lambda *args, **kwargs: [],
    )
    md, source = generate_briefing(
        _leaver(
            interests=[
                "Data & AI",
                "Finance / accounting",
                "Creative / design / events",
            ],
            interest_sectors={"cyber_digital", "business_professional", "creative_events"},
            target_sectors={"cyber_digital", "business_professional", "creative_events"},
        ),
        _seed_row(
            company_id="GLC024",
            name="New Brewery Arts",
            town="Cirencester",
            postcode="GL7",
            sectors="creative_events",
            website="https://www.newbreweryarts.org.uk/careers",
        ),
        use_openai=True,
        mode="work",
    )
    assert source == "grounded_template"
    why = md.split("## Why this company fits you", 1)[1].split("## ", 1)[0]
    assert "Creative / design / events" in why
    assert "Data & AI" not in why
    assert "Finance" not in why
    routes = md.split("## Training routes that fit your interests", 1)[1].split("## ", 1)[0]
    assert "data & ai" not in routes.lower()
    assert "finance" not in routes.lower()
    build = md.split("## What to build or develop next", 1)[1]
    assert "Creative / design / events" in build
    assert "Data & AI" not in build
    assert "Finance" not in build


def test_grounded_why_omits_non_overlapping_aerospace(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        "glos_recommender.briefing.programmes_for_company",
        lambda *args, **kwargs: [],
    )
    md, source = generate_briefing(
        _leaver(
            interests=[
                "Construction & built environment",
                "Aerospace & advanced manufacturing",
            ],
            interest_sectors={"construction_green", "aerospace_manufacturing"},
            target_sectors={"construction_green", "aerospace_manufacturing"},
        ),
        _ch_row(),
        use_openai=True,
        mode="work",
    )
    assert source == "grounded_template"
    why = md.split("## Why this company fits you", 1)[1].split("## ", 1)[0]
    assert "Construction & built environment" in why
    assert "Aerospace" not in why
    assert _REGISTER_SENTENCE in md


def test_employer_prompt_restricts_why_to_overlap(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        "glos_recommender.briefing.programmes_for_company",
        lambda *args, **kwargs: list(_MOCK_PROGRAMMES),
    )
    _system, user = build_employer_briefing_prompt(
        _leaver(
            interests=[
                "Healthcare & wellbeing",
                "Aerospace & advanced manufacturing",
            ],
            interest_sectors={"health_care", "aerospace_manufacturing"},
            target_sectors={"health_care", "aerospace_manufacturing"},
        ),
        _seed_row(),
    )
    assert "cite only overlapping interests" in user.lower()
    assert "Overlapping interests (cite only these in Why): Aerospace & advanced manufacturing" in user
    assert "Your interests: Healthcare" not in user
    assert "Do not invent culture" in user
    assert "only mention leaver interests that overlap" in _system.lower()



def test_seed_with_programmes_is_not_thin_template(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        "glos_recommender.briefing.programmes_for_company",
        lambda *args, **kwargs: list(_MOCK_PROGRAMMES),
    )
    md, source = generate_briefing(
        _renishaw_leaver(),
        _seed_row(),
        use_openai=False,
        retrieved_chunks=[],
        mode="work",
    )
    assert source == "offline"
    assert "Renishaw have previously run" in md



def test_employer_prompt_seed_with_programmes_uses_locked_voice(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        "glos_recommender.briefing.programmes_for_company",
        lambda *args, **kwargs: list(_MOCK_PROGRAMMES),
    )
    system, user = build_employer_briefing_prompt(
        _renishaw_leaver(),
        _seed_row(),
    )
    combined = f"{system}\n{user}"
    assert "have previously run" in combined.lower()
    assert "Engineering Apprenticeship" in user
    assert "Graduate Software / Engineering" in user
    _assert_three_work_h2s(system)
    assert "## Your first steps this month" not in combined
    assert "(Gatsby)" not in combined
    assert "they offer" not in combined.lower()
    for title in _pathway_titles("aerospace_manufacturing", "cyber_digital"):
        assert title not in combined
    assert "no formal qualifications" not in system.lower()
    tail = user.split("Write the briefing now", 1)[-1].lower()
    assert "no formal qualifications" not in tail
    assert "Your first steps this month" not in EMPLOYER_SYSTEM_PROMPT


def test_employer_prompt_seed_empty_programmes_does_not_invent(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        "glos_recommender.briefing.programmes_for_company",
        lambda *args, **kwargs: [],
    )
    system, user = build_employer_briefing_prompt(
        _renishaw_leaver(),
        _seed_row(),
    )
    _assert_three_work_h2s(system)
    assert "do not invent" in user.lower()
    assert "Engineering Apprenticeship" not in user
    assert "TRAINING PATHWAY CARDS" not in user
    assert "## Your first steps this month" not in f"{system}\n{user}"
    for title in _pathway_titles("aerospace_manufacturing", "cyber_digital"):
        assert title not in f"{system}\n{user}"


def test_retrieval_filter_drops_other_employer_opportunities() -> None:
    hits = [
        {
            "chunk": "STRATEGY: employer encounters | Do: arrange one visit",
            "source": "evidence:encounters",
        },
        {
            "chunk": (
                "Opportunity at GE Aerospace: Aerospace Manufacturing Apprentice "
                "(apprenticeship, Level 3-4). Hands-on aerospace manufacturing."
            ),
            "source": "opportunities.txt",
        },
        {
            "chunk": (
                "Opportunity at Crux Product Design Ltd: Product design technician "
                "(apprenticeship, Level 3)."
            ),
            "source": "opportunities.txt",
        },
        {
            "chunk": (
                "Company: Crux Product Design Ltd (Bristol). Sectors: construction_green. "
                "Source: Companies House registry facts."
            ),
            "source": "company_profiles.txt",
        },
        {
            "chunk": (
                "Company: GE Aerospace (Cheltenham). Sectors: aerospace_manufacturing. "
                "Source: Curated local employer profile."
            ),
            "source": "company_profiles.txt",
        },
    ]
    kept = filter_retrieved_hits_for_employer(hits, "Crux Product Design Ltd")
    texts = [str(hit["chunk"]) for hit in kept]
    assert any("STRATEGY:" in text for text in texts)
    assert not any("GE Aerospace" in text for text in texts)
    assert not any("Opportunity at" in text for text in texts)
    assert not any(text.startswith("Company:") for text in texts)


def test_match_reasons_does_not_say_they_offer() -> None:
    leaver = _leaver()
    seed_reasons = match_reasons(leaver, pd.Series(_seed_row(sectors="construction_green")))
    ch_reasons = match_reasons(
        leaver,
        pd.Series(_ch_row(entry_routes="apprenticeship|school_leaver|graduate")),
    )
    blob = " ".join(seed_reasons + ch_reasons).lower()
    assert "they offer" not in blob
    assert all("they offer" not in reason.lower() for reason in seed_reasons + ch_reasons)


def test_work_fallback_seed_with_programmes_uses_have_previously_run(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        "glos_recommender.briefing.programmes_for_company",
        lambda *args, **kwargs: list(_MOCK_PROGRAMMES),
    )
    md = fallback_briefing(
        _renishaw_leaver(),
        _seed_row(),
        retrieved_chunks=[],
        mode="work",
    )
    _assert_three_work_h2s(md)
    assert "Renishaw have previously run" in md
    assert "Engineering Apprenticeship" in md
    assert "aimed at degree-level entry" in md
    assert "no formal qualifications" not in md.lower()
    assert "they offer" not in md.lower()
    for title in _pathway_titles("aerospace_manufacturing", "cyber_digital"):
        assert title not in md


def test_work_fallback_seed_empty_programmes_is_three_section(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        "glos_recommender.briefing.programmes_for_company",
        lambda *args, **kwargs: [],
    )
    md = fallback_briefing(
        _leaver(),
        _seed_row(sectors="construction_green"),
        retrieved_chunks=[],
        mode="work",
    )
    _assert_three_work_h2s(md)
    assert "college or apprenticeship" in md.lower()
    assert "(Gatsby)" not in md
    assert "they offer" not in md.lower()
    for title in _pathway_titles("construction_green", "aerospace_manufacturing"):
        assert title not in md


def test_retrieval_query_omits_entry_routes() -> None:
    query = build_retrieval_query(_renishaw_leaver(), _seed_row())
    assert "entry routes:" not in query.lower()


def test_ch_facts_block_does_not_claim_stamped_routes() -> None:
    block = employer_facts_block(
        _ch_row(entry_routes="apprenticeship|school_leaver|graduate")
    )
    assert "matcher tags" in block
    assert "apprenticeship|school_leaver|graduate" not in block
    assert "Entry routes (matcher tags): unknown" in block


def _facts_without_lookup_urls(block: str) -> str:
    skip = ("findapprenticeship", "find an apprenticeship")
    return "\n".join(
        line
        for line in block.splitlines()
        if not any(token in line.lower() for token in skip)
    )


def test_seed_facts_block_omits_marketing_routes() -> None:
    row = _seed_row(
        name="CGI",
        town="Gloucester / Cheltenham corridor",
        postcode="GL1",
        sectors="cyber_digital|business_professional",
        entry_routes="apprenticeship|graduate|internship|higher_apprenticeship",
        summary=(
            "Global IT and business consulting employer with a significant "
            "Gloucestershire footprint and digital graduate and apprenticeship pathways."
        ),
    )
    block = employer_facts_block(row)
    body = _facts_without_lookup_urls(block)
    assert "digital graduate and apprenticeship pathways" not in body.lower()
    assert "apprenticeship|graduate" not in body
    assert "Entry routes (matcher tags): unknown" in block
    assert "Location and matcher sector tags only" in block
    assert "CGI is listed in Gloucester / Cheltenham corridor (GL1)." in block


def test_hybrid_work_briefing_keeps_code_why_and_training(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        "glos_recommender.briefing.programmes_for_company",
        lambda *args, **kwargs: _gcc_programmes(),
    )
    junk = "\n".join(
        [
            "# Your match — Gloucestershire County Council",
            "## Why this company fits you",
            "They work in Healthcare & wellbeing and Aerospace & advanced manufacturing.",
            "Culture and values put mechanical and electrical engineering first.",
            "## Training routes that fit your interests",
            "They offer an Engineering Apprenticeship and open graduate jobs.",
            "## What to build or develop next",
            "Start a short volunteering log you can talk about, then read one public-service briefing.",
        ]
    )
    calls = _mock_openai(monkeypatch, junk)
    md, source = generate_briefing(
        _mixed_interest_leaver(),
        _gcc_row(),
        use_openai=True,
        retrieved_chunks=[],
        mode="work",
    )
    assert source == "openai"
    assert calls["n"] == 1
    _assert_three_work_h2s(md)
    why = md.split("## Why this company fits you", 1)[1].split("## ", 1)[0]
    assert "Public service & community" in why
    assert "Healthcare" not in why
    assert "Aerospace" not in why
    assert "mechanical" not in why.lower()
    assert "culture" not in why.lower()
    routes = md.split("## Training routes that fit your interests", 1)[1].split("## ", 1)[0]
    assert "Gloucestershire County Council have previously run" in routes
    assert "Social Worker Degree Apprenticeship" in routes
    assert "Engineering Apprenticeship" not in routes
    assert "open graduate jobs" not in routes.lower()
    build = md.split("## What to build or develop next", 1)[1]
    assert "volunteering log" in build
    prompt_blob = " ".join(str(m.get("content") or "") for m in calls["messages"])
    assert "Social Worker Degree Apprenticeship" not in prompt_blob
    assert "VERIFIED EMPLOYER FACTS" not in prompt_blob
    assert "Engineering Apprenticeship" not in prompt_blob
    user = next(m["content"] for m in calls["messages"] if m["role"] == "user")
    assert "No markdown headings" in user
    assert "no Why section" in calls["messages"][0]["content"]
    assert "Public service & community" in user
    assert "Healthcare & wellbeing" not in user
    assert "Aerospace & advanced manufacturing" not in user


def test_hybrid_work_briefing_drops_build_next_that_names_a_scheme(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        "glos_recommender.briefing.programmes_for_company",
        lambda *args, **kwargs: _gcc_programmes(),
    )
    calls = _mock_openai(
        monkeypatch,
        "Enrol on the Social Worker Degree Apprenticeship this month.",
    )
    md, source = generate_briefing(
        _mixed_interest_leaver(),
        _gcc_row(),
        use_openai=True,
        retrieved_chunks=[],
        mode="work",
    )
    assert source == "openai"
    assert calls["n"] == 1
    build = md.split("## What to build or develop next", 1)[1]
    assert "Social Worker Degree Apprenticeship" not in build
    assert "Start one small project" in build
    assert "Public service & community" in build
    assert "Healthcare" not in build
    assert "Aerospace" not in build
    why = md.split("## Why this company fits you", 1)[1].split("## ", 1)[0]
    assert "Healthcare" not in why
    assert "Aerospace" not in why


def test_build_next_prompt_omits_employer_programmes(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        "glos_recommender.briefing.programmes_for_company",
        lambda *args, **kwargs: _gcc_programmes(),
    )
    system, user = build_work_build_next_prompt(
        _mixed_interest_leaver(),
        _gcc_row(),
        retrieved_chunks=[],
    )
    combined = f"{system}\n{user}"
    assert system == BUILD_NEXT_SYSTEM_PROMPT
    assert "Social Worker Degree Apprenticeship" not in combined
    assert "VERIFIED EMPLOYER FACTS" not in combined
    assert "Gloucestershire County Council" not in user
    assert "## Why this company fits you" not in combined
    assert "no why section" in system.lower()
    assert "Public service & community" in user
    assert "Healthcare & wellbeing" not in user
    assert "Aerospace & advanced manufacturing" not in user
    assert "Interests: Public service" not in user
    assert "overlapping interests" in user.lower()
    assert "only the overlapping interests" in system.lower()


def test_hybrid_work_briefing_drops_build_next_with_non_overlap_interest(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        "glos_recommender.briefing.programmes_for_company",
        lambda *args, **kwargs: _gcc_programmes(),
    )
    calls = _mock_openai(
        monkeypatch,
        "Build a cybersecurity checklist, then visit a healthcare facility.",
    )
    md, source = generate_briefing(
        _mixed_interest_leaver(),
        _gcc_row(),
        use_openai=True,
        retrieved_chunks=[],
        mode="work",
    )
    assert source == "openai"
    assert calls["n"] == 1
    build = md.split("## What to build or develop next", 1)[1]
    assert "cybersecurity" not in build.lower()
    assert "healthcare" not in build.lower()
    assert "Public service & community" in build


def test_employer_prompt_omits_entry_route_reasons(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        "glos_recommender.briefing.programmes_for_company",
        lambda *args, **kwargs: [],
    )
    _system, user = build_employer_briefing_prompt(
        _renishaw_leaver(),
        _seed_row(
            summary="Precision engineering with STEM apprenticeships and graduate routes."
        ),
    )
    facts, _rest = user.split("Match score", 1)
    body = _facts_without_lookup_urls(facts)
    assert "stem apprenticeships" not in body.lower()
    assert "Entry-route match tags" not in user
    assert "apprenticeship|graduate|higher_apprenticeship" not in user
