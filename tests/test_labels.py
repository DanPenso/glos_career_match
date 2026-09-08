"""Unit tests for presentation labels and employer website hygiene."""

from __future__ import annotations

import pytest

from glos_recommender.labels import (
    clean_company_summary,
    fit_label,
    hiring_label,
    is_registry_website,
    overall_label,
    public_employer_website,
    sic_activity,
)


@pytest.mark.parametrize(
    "url, expected",
    [
        ("https://find-and-update.company-information.service.gov.uk/company/012", True),
        ("https://company-information.service.gov.uk/company/012", True),
        ("https://find-and-update.company-information.service.gov.uk", True),
        ("http://companieshouse.gov.uk/search", True),
        ("https://acme.example/careers", False),
        ("", False),
        (None, False),
    ],
)
def test_is_registry_website(url: str | None, expected: bool) -> None:
    assert is_registry_website(url) is expected


def test_public_employer_website_keeps_http_homepages_only() -> None:
    assert public_employer_website("https://acme.example") == "https://acme.example"
    assert public_employer_website("http://acme.example") == "http://acme.example"
    assert public_employer_website("acme.example") == ""
    assert (
        public_employer_website(
            "https://find-and-update.company-information.service.gov.uk/company/1"
        )
        == ""
    )
    assert public_employer_website("") == ""
    assert public_employer_website(None) == ""


def test_sic_activity_strips_code_prefix() -> None:
    assert (
        sic_activity("62012 - Business and domestic software development")
        == "Business and domestic software development"
    )
    assert sic_activity("Hospitality.") == "Hospitality"


@pytest.mark.parametrize(
    "score, label",
    [
        (0.55, "Strong"),
        (0.90, "Strong"),
        (0.30, "Good"),
        (0.54, "Good"),
        (0.29, "Worth exploring"),
        (0.0, "Worth exploring"),
    ],
)
def test_fit_label_thresholds(score: float, label: str) -> None:
    assert fit_label(score) == label


def test_hiring_label_does_not_claim_live_hiring() -> None:
    assert hiring_label({"hiring_signal": "high"}) == "Check current openings"
    assert hiring_label({"hiring_score": 0.85}) == "Check current openings"
    assert hiring_label({"hiring_signal": "medium"}) == "Check current openings"
    assert hiring_label({"hiring_score": 0.5}) == "Check current openings"
    assert hiring_label({"hiring_signal": "low", "hiring_score": 0.2}) == "Check current openings"


def test_overall_label_by_rank() -> None:
    assert overall_label(0) == "Your strongest match"
    assert overall_label(1) == "A strong option"
    assert overall_label(2) == "Also worth a look"


def test_clean_company_summary_passthrough_and_boilerplate() -> None:
    plain = "Cheltenham software studio taking school leavers."
    assert clean_company_summary(plain) == plain

    boilerplate = (
        "Companies House-listed employer. Registered office in Cheltenham. "
        "Nature of business (SIC): 62012 - Business and domestic software development. "
        "Leaver routes include apprenticeships."
    )
    cleaned = clean_company_summary(boilerplate)
    assert "companies house" not in cleaned.lower()
    assert "cheltenham" in cleaned.lower()
    assert "software" in cleaned.lower()


def test_display_summary_seed_omits_marketing_pathways() -> None:
    from glos_recommender.provenance import display_summary

    cgi = display_summary(
        {
            "name": "CGI",
            "town": "Gloucester / Cheltenham corridor",
            "postcode": "GL1",
            "source": "seed",
            "summary": (
                "Global IT and business consulting employer with a significant "
                "Gloucestershire footprint and digital graduate and apprenticeship pathways."
            ),
        }
    )
    assert "CGI is listed in Gloucester / Cheltenham corridor (GL1)." in cgi
    assert "apprenticeship" not in cgi.lower()
    assert "graduate" not in cgi.lower()

    aviva = display_summary(
        {
            "name": "Aviva PLC",
            "town": "Local Area",
            "postcode": "BS34",
            "source": "seed",
            "summary": (
                "Bristol employer (Local Area) with apprenticeship vacancies on "
                "Find an Apprenticeship. Recent roles include: Claims Apprentice; "
                "Risk and Compliance Apprentice; Business Analyst Apprentice."
            ),
        }
    )
    assert "Aviva PLC is listed in Local Area (BS34)." in aviva
    assert "Claims Apprentice" not in aviva
    assert "Business Analyst" not in aviva


def test_display_summary_vacancy_omits_role_titles() -> None:
    from glos_recommender.provenance import display_summary

    text = display_summary(
        {
            "name": "AVIVA PLC",
            "town": "Local Area",
            "postcode": "BS34",
            "source": "vacancies",
            "summary": (
                "Recent roles include: Claims Apprentice; Risk and Compliance "
                "Apprentice; Business Analyst Apprentice."
            ),
        }
    )
    assert "Claims Apprentice" not in text
    assert "Find an apprenticeship" in text
    assert "historical" in text.lower()
