"""FastAPI tests with masters and LLM calls mocked out."""

from __future__ import annotations

from typing import Any

import pandas as pd
import pytest
from fastapi.testclient import TestClient

from glos_recommender.safeguarding import UNDER_16_DETAIL


def _fake_leaver(form: dict[str, Any] | None = None) -> dict[str, Any]:
    form = form or {}
    return {
        "leaver_type": form.get("leaver_type") or "School leaver (Year 11 / 13)",
        "location": form.get("location") or "Cheltenham",
        "age_band": form.get("age_band") or "18_24",
        "interests": form.get("interests") or ["Software / apps / web"],
        "courses": form.get("courses") or [],
        "interest_sectors": {"cyber_digital"},
        "target_sectors": {"cyber_digital"},
        "psych_sectors": set(),
        "entry_routes": {"apprenticeship"},
        "psych": {},
        "profile_text": "software apprenticeship",
    }


def _fake_ranked_companies() -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "company_id": "mock1",
                "name": "Mock Employer",
                "town": "Cheltenham",
                "postcode": "GL50 1AA",
                "sectors": "cyber_digital",
                "entry_routes": "apprenticeship",
                "summary": "A mock digital employer",
                "website": "https://mock.example",
                "hiring_signal": "high",
                "priority_employer": 0,
                "final_score": 0.9,
                "sector_score": 0.8,
                "entry_score": 0.7,
                "hiring_score": 1.0,
                "hybrid_score": 0.9,
                "cosine_sim": 0.0,
                "source": "seed",
            }
        ]
    )


@pytest.fixture
def client(monkeypatch: pytest.MonkeyPatch) -> TestClient:
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)

    monkeypatch.setattr("api.main.load_companies", lambda: pd.DataFrame())
    monkeypatch.setattr("api.main.load_courses", lambda: pd.DataFrame())
    monkeypatch.setattr(
        "api.main.match_companies",
        lambda form, companies=None, top_n=3: (_fake_leaver(form), _fake_ranked_companies()),
    )
    monkeypatch.setattr(
        "api.main.generate_briefing",
        lambda *args, **kwargs: ("mocked briefing", "openai"),
    )
    monkeypatch.setattr(
        "api.main.generate_plan",
        lambda **kwargs: {"steps": [{"id": "s1", "title": "Mock step"}], "source": "mock"},
    )
    monkeypatch.setattr(
        "api.main.chat_about_step",
        lambda **kwargs: (_ for _ in ()).throw(AssertionError("LLM chat must not be called")),
    )
    monkeypatch.setattr(
        "api.main.persona_bundle",
        lambda *args, **kwargs: {
            "persona": "Digital makers",
            "cluster_id": None,
            "runner_up": None,
            "persona_blurb": "",
            "persona_disclaimer": "",
            "persona_fit": [],
            "persona_map_2d": None,
            "training_routes": [],
        },
    )
    monkeypatch.setattr(
        "api.main.match_online_courses",
        lambda **kwargs: ([], ""),
    )
    monkeypatch.setattr("api.main.pathways_for_sectors", lambda sectors: [])
    monkeypatch.setattr("api.main.log_match_event", lambda *args, **kwargs: None)
    monkeypatch.setattr("api.main.gemini_configured", lambda: False)

    from api.main import app

    return TestClient(app)


def _match_body(**overrides: Any) -> dict[str, Any]:
    body: dict[str, Any] = {
        "leaver_type": "School leaver (Year 11 / 13)",
        "location": "Cheltenham",
        "age_band": "18_24",
        "interests": ["Software / apps / web"],
        "courses": ["Computer Science / IT"],
        "allow_anonymous_logging": False,
        "use_openai_briefing": False,
        "use_gemini_plan": False,
        "mode": "work",
    }
    body.update(overrides)
    return body


def test_health_ok(client: TestClient) -> None:
    response = client.get("/health")
    assert response.status_code == 200
    payload = response.json()
    assert payload["ok"] is True
    assert payload["companies"] == 0
    assert payload["courses"] == 0


def test_under_16_cannot_get_matches(client: TestClient) -> None:
    response = client.post("/match", json=_match_body(age_band="under_16"))
    assert response.status_code == 403
    assert response.json()["detail"] == UNDER_16_DETAIL


def test_plan_chat_crisis_returns_safeguarding(client: TestClient) -> None:
    response = client.post(
        "/plan/chat",
        json={
            "mode": "work",
            "leaver": {"age_band": "18_24"},
            "match": {"name": "Mock Employer", "company_id": "mock1"},
            "step": {"id": "s1", "title": "Check the website"},
            "message": "I want to kill myself",
            "use_gemini_plan": True,
        },
    )
    assert response.status_code == 200
    payload = response.json()
    reply = payload["reply_markdown"]
    assert payload["source"] == "safeguarding"
    assert "999" in reply
    assert "Childline" in reply
    assert "Samaritans" in reply


def test_match_uses_mocked_companies(client: TestClient) -> None:
    response = client.post("/match", json=_match_body())
    assert response.status_code == 200
    payload = response.json()
    assert payload["matches"][0]["name"] == "Mock Employer"
    assert payload["matches"][0]["kind"] == "employer"
    assert payload["matches"][0]["hiring_label"] == "Check current openings"
    assert payload["matches"][0]["open_now"] is False
    summary = payload["matches"][0]["summary"] or ""
    assert "matcher sector tags" not in summary.lower()
    assert "listed in Cheltenham" not in summary
    assert "apprenticeship" not in summary.lower()


def test_match_keeps_grounded_template_briefing(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(
        "api.main.generate_briefing",
        lambda *args, **kwargs: (
            "# Your match — Mock Employer\n\n## Why this company fits you\nGrounded.",
            "grounded_template",
        ),
    )
    response = client.post("/match", json=_match_body(use_openai_briefing=True))
    assert response.status_code == 200
    match = response.json()["matches"][0]
    assert match["briefing_markdown"]
    assert "Grounded." in match["briefing_markdown"]
    assert match["briefing_source"] == "grounded_template"


def test_plan_generate_uses_mock(client: TestClient) -> None:
    response = client.post(
        "/plan/generate",
        json={
            "mode": "work",
            "leaver": {"age_band": "18_24"},
            "match": {"name": "Mock Employer", "company_id": "mock1"},
            "use_gemini_plan": True,
        },
    )
    assert response.status_code == 200
    assert response.json()["source"] == "mock"


def test_match_rejects_live_filter_for_military(client: TestClient) -> None:
    response = client.post(
        "/match",
        json=_match_body(mode="military", live_apprenticeships_only=True),
    )
    assert response.status_code == 400
    assert "official live-opportunities list" in response.json()["detail"]

    response = client.post(
        "/match",
        json=_match_body(mode="military", live_jobs_only=True),
    )
    assert response.status_code == 400


def test_match_attaches_open_opportunities_flag(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(
        "api.main.load_open_apprenticeships",
        lambda **kwargs: {"fetched_at": "2026-09-08T12:00:00+00:00", "vacancies": []},
    )
    monkeypatch.setattr("api.main.open_apprenticeship_index", lambda doc: {})
    monkeypatch.setattr(
        "api.main.open_fields_for_employer",
        lambda name, index=None: {
            "open_now": True,
            "open_label": "Open opportunities",
            "open_url": "https://www.findapprenticeship.service.gov.uk/apprenticeship/1",
            "open_count": 1,
            "open_as_of": "2026-09-08T12:00:00+00:00",
            "open_source": "faa_display_advert",
            "open_titles": ["Dental nurse"],
        },
    )
    response = client.post("/match", json=_match_body())
    assert response.status_code == 200
    match = response.json()["matches"][0]
    assert match["open_now"] is True
    assert match["open_label"] == "Open opportunities"
    assert "findapprenticeship.service.gov.uk/apprenticeship/1" in match["open_url"]


def test_match_attaches_open_jobs_flag(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(
        "api.main.load_open_apprenticeships",
        lambda **kwargs: {"fetched_at": None, "vacancies": []},
    )
    monkeypatch.setattr("api.main.open_apprenticeship_index", lambda doc: {})
    monkeypatch.setattr(
        "api.main.open_fields_for_employer",
        lambda name, index=None: {
            "open_now": False,
            "open_label": "",
            "open_url": "",
            "open_count": 0,
            "open_as_of": None,
            "open_source": "",
            "open_titles": [],
        },
    )
    monkeypatch.setattr(
        "api.main.load_reed_jobs",
        lambda **kwargs: {"fetched_at": "2026-09-11T12:00:00+00:00", "jobs": []},
    )
    monkeypatch.setattr("api.main.open_jobs_index", lambda doc: {})
    monkeypatch.setattr(
        "api.main.open_fields_for_employer_jobs",
        lambda name, index=None: {
            "jobs_open_now": True,
            "jobs_open_label": "Open jobs",
            "jobs_open_url": "https://www.reed.co.uk/jobs/40126680",
            "jobs_open_count": 2,
            "jobs_open_as_of": "2026-09-11T12:00:00+00:00",
            "jobs_open_source": "reed_jobseeker",
            "jobs_open_titles": ["Graduate software engineer", "Analyst"],
        },
    )
    response = client.post("/match", json=_match_body())
    assert response.status_code == 200
    match = response.json()["matches"][0]
    assert match["open_now"] is False
    assert match["jobs_open_now"] is True
    assert match["jobs_open_label"] == "Open jobs"
    assert match["jobs_open_count"] == 2
    assert "reed.co.uk/jobs/40126680" in match["jobs_open_url"]


def test_match_live_filter_work_without_cache(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(
        "api.main.load_open_apprenticeships",
        lambda **kwargs: {"fetched_at": None, "vacancies": []},
    )
    monkeypatch.setattr("api.main.open_apprenticeship_index", lambda doc: {})
    monkeypatch.setattr(
        "api.main.filter_employers_with_open",
        lambda companies, index=None: companies.iloc[0:0],
    )
    response = client.post("/match", json=_match_body(live_apprenticeships_only=True))
    assert response.status_code == 400
    detail = response.json()["detail"].lower()
    assert "apprenticeship" in detail


def test_match_live_jobs_filter_without_cache(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(
        "api.main.load_open_apprenticeships",
        lambda **kwargs: {"fetched_at": None, "vacancies": []},
    )
    monkeypatch.setattr("api.main.open_apprenticeship_index", lambda doc: {})
    monkeypatch.setattr(
        "api.main.load_reed_jobs",
        lambda **kwargs: {"fetched_at": None, "jobs": []},
    )
    monkeypatch.setattr("api.main.open_jobs_index", lambda doc: {})
    monkeypatch.setattr(
        "api.main.filter_employers_with_open_jobs",
        lambda companies, index=None: companies.iloc[0:0],
    )
    response = client.post("/match", json=_match_body(live_jobs_only=True))
    assert response.status_code == 400
    detail = response.json()["detail"].lower()
    assert "reed" in detail or "job" in detail


def test_match_live_filters_or_keeps_either_source(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    companies = _fake_ranked_companies()
    monkeypatch.setattr("api.main.load_companies", lambda: companies)
    monkeypatch.setattr(
        "api.main.load_open_apprenticeships",
        lambda **kwargs: {"fetched_at": None, "vacancies": []},
    )
    monkeypatch.setattr("api.main.open_apprenticeship_index", lambda doc: {})
    monkeypatch.setattr(
        "api.main.filter_employers_with_open",
        lambda frame, index=None: frame.iloc[0:0],
    )
    monkeypatch.setattr(
        "api.main.load_reed_jobs",
        lambda **kwargs: {"fetched_at": "2026-09-11T12:00:00+00:00", "jobs": []},
    )
    monkeypatch.setattr("api.main.open_jobs_index", lambda doc: {"mock employer": []})
    monkeypatch.setattr(
        "api.main.filter_employers_with_open_jobs",
        lambda frame, index=None: frame,
    )
    response = client.post(
        "/match",
        json=_match_body(live_apprenticeships_only=True, live_jobs_only=True),
    )
    assert response.status_code == 200
    assert response.json()["matches"][0]["name"] == "Mock Employer"
