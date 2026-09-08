"""Matching tests using in-memory company rows only (no companies_master.csv)."""

from __future__ import annotations

import pandas as pd
import pytest

from glos_recommender.matching import (
    build_leaver_profile,
    drop_vacancy_duplicates_of_seed,
    match_companies,
    match_reasons,
    score_company,
)


@pytest.fixture
def no_embeddings(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "glos_recommender.matching.load_company_embeddings",
        lambda path=None: None,
    )


def _leaver(**overrides: object) -> dict:
    base = {
        "interest_sectors": {"cyber_digital"},
        "target_sectors": {"cyber_digital"},
        "psych_sectors": set(),
        "entry_routes": {"apprenticeship"},
        "profile_text": "software engineering apprenticeship",
        "interests": ["Software / apps / web"],
        "psych": {
            "role_prefs": {"software_developer"},
            "dominant_riasec": ["Investigative"],
        },
    }
    base.update(overrides)
    return base


def _company_row(**overrides: object) -> pd.Series:
    data = {
        "company_id": "c1",
        "name": "Acme Digital",
        "sectors": "cyber_digital",
        "entry_routes": "apprenticeship",
        "role_families": "software_developer",
        "profile_text": "software engineering apprenticeship",
        "hiring_signal": "high",
        "priority_employer": 0,
        "source": "seed",
        "website": "https://acme.example",
    }
    data.update(overrides)
    return pd.Series(data)


def test_score_company_perfect_overlap_beats_mismatch() -> None:
    leaver = _leaver()
    aligned = score_company(leaver, _company_row())
    other = score_company(
        leaver,
        _company_row(
            company_id="c2",
            sectors="hospitality_tourism",
            entry_routes="graduate",
            role_families="chef",
            profile_text="hotel kitchen",
            hiring_signal="low",
        ),
    )
    assert aligned["final_score"] > other["final_score"]
    assert aligned["sector_score"] == 0.75
    assert aligned["entry_score"] == 1.0


def test_score_company_soft_rejects_when_no_shared_route() -> None:
    leaver = _leaver()
    shared = score_company(leaver, _company_row(hiring_signal="low"))
    no_route = score_company(
        leaver,
        _company_row(entry_routes="graduate", hiring_signal="low"),
    )
    assert no_route["final_score"] < shared["final_score"]


def test_build_leaver_profile_maps_interests_to_sectors() -> None:
    profile = build_leaver_profile(
        {
            "leaver_type": "School leaver (Year 11 / 13)",
            "age_band": "16_17",
            "location": "Cheltenham",
            "courses": ["Computer Science / IT"],
            "interests": ["Software / apps / web"],
            "passions": ["Solving puzzles / problems"],
            "work_experience": ["Coding / personal projects"],
            "qualification_level": "GCSEs / Level 2",
            "psych_answers": {},
        }
    )
    assert "cyber_digital" in profile["interest_sectors"]
    assert "apprenticeship" in profile["entry_routes"]
    assert "Software / apps / web" in profile["profile_text"]
    assert profile["age_band"] == "16_17"


def test_build_leaver_profile_maps_youth_interests() -> None:
    profile = build_leaver_profile(
        {
            "leaver_type": "School leaver (Year 11 / 13)",
            "age_band": "18_24",
            "location": "Gloucester",
            "courses": [],
            "interests": [
                "Gaming",
                "Team sports / fitness",
                "Social media / content / marketing",
                "Building apps",
                "Campaigning",
            ],
            "passions": [],
            "work_experience": [],
            "qualification_level": "GCSEs / Level 2",
            "psych_answers": {},
        }
    )
    assert "cyber_digital" in profile["interest_sectors"]
    assert "creative_events" in profile["interest_sectors"]
    assert "health_care" in profile["interest_sectors"]
    assert "business_professional" in profile["interest_sectors"]
    assert "public_sector" in profile["interest_sectors"]


def test_match_companies_ranks_in_memory_rows(no_embeddings: None) -> None:
    companies = pd.DataFrame(
        [
            {
                "company_id": "fit",
                "name": "Fit Digital",
                "sectors": "cyber_digital",
                "entry_routes": "apprenticeship|school_leaver",
                "role_families": "software_developer",
                "profile_text": "software engineering apprenticeship",
                "hiring_signal": "high",
                "priority_employer": 1,
                "source": "seed",
                "website": "https://fit.example",
            },
            {
                "company_id": "miss",
                "name": "Miss Hotel",
                "sectors": "hospitality_tourism",
                "entry_routes": "graduate",
                "role_families": "chef",
                "profile_text": "hotel restaurant kitchen",
                "hiring_signal": "low",
                "priority_employer": 0,
                "source": "vacancies",
                "website": "https://hotel.example",
            },
            {
                "company_id": "registry",
                "name": "Registry Only Ltd",
                "sectors": "cyber_digital",
                "entry_routes": "apprenticeship",
                "role_families": "software_developer",
                "profile_text": "software",
                "hiring_signal": "high",
                "priority_employer": 0,
                "source": "seed",
                "website": "https://find-and-update.company-information.service.gov.uk/company/1",
            },
            {
                "company_id": "nosite",
                "name": "No Website Ltd",
                "sectors": "cyber_digital",
                "entry_routes": "apprenticeship",
                "role_families": "software_developer",
                "profile_text": "software",
                "hiring_signal": "high",
                "priority_employer": 0,
                "source": "seed",
                "website": "",
            },
        ]
    )
    form = {
        "leaver_type": "School leaver (Year 11 / 13)",
        "age_band": "16_17",
        "location": "Cheltenham",
        "courses": ["Computer Science / IT"],
        "interests": ["Software / apps / web"],
        "passions": [],
        "work_experience": [],
        "qualification_level": "GCSEs / Level 2",
        "psych_answers": {},
    }
    leaver, ranked = match_companies(form, companies, top_n=3)

    assert leaver["matching_mode"] == "hybrid_only"
    ids = ranked["company_id"].tolist()
    assert "fit" in ids
    assert ids[0] == "fit"
    assert "registry" not in ids
    assert "nosite" not in ids
    assert all(str(url).startswith("http") for url in ranked["website"])


def test_match_reasons_include_shared_sector() -> None:
    leaver = _leaver()
    reasons = match_reasons(leaver, _company_row())
    assert any("cyber_digital" in reason for reason in reasons)
    assert any("apprenticeship" in reason for reason in reasons)
    assert all("they offer" not in reason.lower() for reason in reasons)


def test_drop_vacancy_duplicates_prefers_aviva_seed() -> None:
    companies = pd.DataFrame(
        [
            {
                "company_id": "GLC191",
                "name": "Aviva PLC",
                "source": "seed",
                "website": "https://careers.aviva.com",
                "sectors": "business_professional",
            },
            {
                "company_id": "VAC6E81C21A",
                "name": "AVIVA PLC",
                "source": "vacancies",
                "website": "https://careers.aviva.com",
                "sectors": "business_professional",
            },
            {
                "company_id": "VAC-OTHER",
                "name": "Other Vacancy Ltd",
                "source": "vacancies",
                "website": "https://othervac.example",
                "sectors": "business_professional",
            },
        ]
    )
    kept = drop_vacancy_duplicates_of_seed(companies)
    ids = kept["company_id"].tolist()
    assert "GLC191" in ids
    assert "VAC6E81C21A" not in ids
    assert "VAC-OTHER" in ids


def test_match_companies_hides_vacancy_when_seed_exists(
    no_embeddings: None,
) -> None:
    companies = pd.DataFrame(
        [
            {
                "company_id": "GLC191",
                "name": "Aviva PLC",
                "sectors": "business_professional|cyber_digital",
                "entry_routes": "apprenticeship",
                "role_families": "admin|finance",
                "profile_text": "insurance finance apprenticeship",
                "hiring_signal": "medium",
                "priority_employer": 0,
                "source": "seed",
                "website": "https://careers.aviva.com",
            },
            {
                "company_id": "VAC6E81C21A",
                "name": "AVIVA PLC",
                "sectors": "business_professional|cyber_digital",
                "entry_routes": "apprenticeship",
                "role_families": "admin|finance",
                "profile_text": "claims apprentice risk compliance",
                "hiring_signal": "medium",
                "priority_employer": 0,
                "source": "vacancies",
                "website": "https://careers.aviva.com",
            },
        ]
    )
    form = {
        "leaver_type": "College / FE leaver",
        "age_band": "18_24",
        "location": "Bristol",
        "courses": ["Business / Economics"],
        "interests": ["Finance / accounting"],
        "passions": [],
        "work_experience": [],
        "qualification_level": "A-levels / Level 3",
        "psych_answers": {},
    }
    _leaver_out, ranked = match_companies(form, companies, top_n=3)
    ids = ranked["company_id"].tolist()
    assert ids == ["GLC191"]
