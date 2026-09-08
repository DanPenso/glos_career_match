"""Unit tests for shared catalogue scoring primitives."""

from __future__ import annotations

import math

import pandas as pd

from glos_recommender.scoring import (
    jaccard,
    rounded_score_dict,
    score_catalogue_components,
    split_pipe,
    token_overlap,
)


def test_split_pipe_handles_blank_and_nan() -> None:
    assert split_pipe("cyber_digital| health_care |") == {"cyber_digital", "health_care"}
    assert split_pipe(None) == set()
    assert split_pipe("") == set()
    assert split_pipe(float("nan")) == set()
    assert split_pipe(pd.NA) == set()


def test_jaccard_overlap_and_empty() -> None:
    assert jaccard({"a", "b"}, {"b", "c"}) == 1 / 3
    assert jaccard(set(), {"a"}) == 0.0
    assert jaccard({"a"}, set()) == 0.0
    assert jaccard({"a"}, {"a"}) == 1.0


def test_token_overlap_ignores_short_tokens() -> None:
    score = token_overlap(
        "I like software engineering apprenticeships",
        "software engineering roles",
    )
    assert score > 0
    assert token_overlap("to a of", "to a of") == 0.0
    assert token_overlap("engineering", "engineering") == 1.0


def test_score_catalogue_components_weights() -> None:
    leaver = {
        "target_sectors": {"cyber_digital"},
        "interest_sectors": {"cyber_digital"},
        "psych_sectors": {"cyber_digital"},
        "entry_routes": {"apprenticeship"},
        "profile_text": "software engineering apprenticeship",
        "psych": {"role_prefs": {"software_developer"}},
    }
    weights = {"sector": 0.4, "entry": 0.3, "text": 0.2, "psych": 0.1}
    scores = score_catalogue_components(
        leaver,
        item_sectors={"cyber_digital"},
        item_routes={"apprenticeship"},
        item_roles={"software_developer"},
        profile_text_b="software engineering apprenticeship",
        weights=weights,
    )
    assert set(scores) == {
        "final_score",
        "sector_score",
        "entry_score",
        "text_score",
        "psych_score",
    }
    assert scores["sector_score"] == 1.0
    assert scores["entry_score"] == 1.0
    assert scores["text_score"] == 1.0
    assert 0.0 <= scores["final_score"] <= 1.0
    assert math.isclose(
        scores["final_score"],
        weights["sector"] * scores["sector_score"]
        + weights["entry"] * scores["entry_score"]
        + weights["text"] * scores["text_score"]
        + weights["psych"] * scores["psych_score"],
        rel_tol=1e-9,
    )

    rounded = rounded_score_dict(scores)
    assert all(isinstance(v, float) for v in rounded.values())
    assert rounded["final_score"] == round(scores["final_score"], 4)


def test_score_catalogue_uses_default_entry_when_item_routes_empty() -> None:
    leaver = {
        "target_sectors": {"health_care"},
        "interest_sectors": {"health_care"},
        "psych_sectors": set(),
        "entry_routes": {"apprenticeship"},
        "profile_text": "",
        "psych": {"role_prefs": set()},
    }
    scores = score_catalogue_components(
        leaver,
        item_sectors={"health_care"},
        item_routes=set(),
        item_roles=set(),
        profile_text_b="",
        weights={"sector": 1.0, "entry": 0.0, "text": 0.0, "psych": 0.0},
        default_entry=0.42,
    )
    assert scores["entry_score"] == 0.42
