"""Unit tests for age-band helpers and the crisis keyword screen."""

from __future__ import annotations

import pytest

from glos_recommender.safeguarding import (
    AGE_BANDS,
    age_band_allowed_for_match,
    age_band_allows_ai,
    age_bands_for_taxonomy,
    is_youth_band,
    looks_like_safety_concern,
    normalise_age_band,
    safeguarding_chat_response,
    show_military_age_notice,
)


@pytest.mark.parametrize(
    "phrase",
    [
        "I want to kill myself",
        "I've been thinking about suicide",
        "I am self-harming",
        "I want to die",
        "don't want to live anymore",
        "someone is grooming me",
        "I am in danger",
    ],
)
def test_looks_like_safety_concern_positive(phrase: str) -> None:
    assert looks_like_safety_concern(phrase) is True


@pytest.mark.parametrize(
    "phrase",
    [
        "I want an engineering apprenticeship",
        "I want to live in Cheltenham after college",
        "I enjoy software engineering and cyber security",
        "",
    ],
)
def test_looks_like_safety_concern_negative(phrase: str) -> None:
    assert looks_like_safety_concern(phrase) is False


def test_looks_like_safety_concern_joins_multiple_texts() -> None:
    assert looks_like_safety_concern("careers chat", "I want to hang myself") is True
    assert looks_like_safety_concern(None, "") is False


def test_safeguarding_chat_is_fixed_not_model_generated() -> None:
    payload = safeguarding_chat_response()
    reply = payload["reply_markdown"]

    assert payload["source"] == "safeguarding"
    assert "999" in reply
    assert "Childline" in reply
    assert "Samaritans" in reply


def test_normalise_age_band_aliases() -> None:
    assert normalise_age_band("16-17") == "16_17"
    assert normalise_age_band("under16") == "under_16"
    assert normalise_age_band("25+") == "25_plus"
    assert normalise_age_band("prefer not") == "prefer_not"
    assert normalise_age_band("mystery") == ""


def test_age_band_gates() -> None:
    assert age_band_allowed_for_match("under_16") is False
    assert age_band_allowed_for_match("16_17") is True
    assert age_band_allows_ai("16_17") is True
    assert age_band_allows_ai("prefer_not") is False
    assert show_military_age_notice("16_17") is True
    assert show_military_age_notice("18_24") is False
    assert is_youth_band("prefer_not") is True
    assert is_youth_band("25_plus") is False


def test_age_bands_for_taxonomy_covers_all_ids() -> None:
    rows = age_bands_for_taxonomy()
    assert [row["id"] for row in rows] == list(AGE_BANDS)
    assert all(row["label"] for row in rows)
