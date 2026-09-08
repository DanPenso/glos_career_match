"""Live-learning events must stay anonymous and write only to a tmp JSONL."""

from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from glos_recommender.live_learning import (
    append_live_event,
    build_match_event,
    events_to_training_rows,
    live_event_count,
    load_live_events,
    log_match_event,
    prune_live_events,
    record_persona_feedback,
)

_PII_KEYS = {"name", "email", "about_me", "about me", "about"}
_FREE_TEXT_SNIPPETS = (
    "Ada Lovelace",
    "ada@example.com",
    "I love robotics and live at 12 High Street",
)


def _leaver_with_pii() -> dict:
    return {
        "name": "Ada Lovelace",
        "email": "ada@example.com",
        "about_me": "I love robotics and live at 12 High Street",
        "about me": "secret diary text",
        "profile_text": "I love robotics and live at 12 High Street",
        "proud_example": "I love robotics and live at 12 High Street",
        "goal_sentence": "I love robotics and live at 12 High Street",
        "interest_sectors": ["cyber_digital"],
        "target_sectors": ["cyber_digital"],
        "leaver_type": "School leaver (Year 11 / 13)",
        "psych": {
            "dominant_riasec": ["Investigative"],
            "riasec_scores": {"Investigative": 3.0, "Realistic": 1.0},
        },
        "persona": "Digital makers",
    }


def _assert_no_pii(event: dict) -> None:
    keys_lower = {str(k).lower() for k in event}
    assert keys_lower.isdisjoint({k.lower() for k in _PII_KEYS})
    blob = json.dumps(event, ensure_ascii=False)
    for snippet in _FREE_TEXT_SNIPPETS:
        assert snippet not in blob
    assert "12 High Street" not in blob
    assert "secret diary" not in blob


def test_build_match_event_omits_name_email_and_about_me() -> None:
    event = build_match_event(
        _leaver_with_pii(),
        {
            "persona": "Digital makers",
            "runner_up": "Analysts",
            "cluster_id": 2,
            "method": "kmeans",
            "persona_fit": [
                {
                    "persona": "Digital makers",
                    "closeness": 0.8,
                    "is_primary": True,
                    "is_runner_up": False,
                }
            ],
        },
        channel="web:jobs",
    )
    _assert_no_pii(event)
    assert event["interest_sectors"] == ["cyber_digital"]
    assert event["dominant_riasec"] == ["Investigative"]
    assert event["channel"] == "web:jobs"
    assert event["source"] == "live_intake"
    assert event["persona_assigned"] == "Digital makers"
    assert event["persona_helpful"] is None


def test_append_and_load_roundtrip_on_tmp_path(tmp_path: Path) -> None:
    path = tmp_path / "leavers_events.jsonl"
    event = build_match_event(_leaver_with_pii())
    append_live_event(event, path)

    loaded = load_live_events(path)
    assert len(loaded) == 1
    _assert_no_pii(loaded[0])
    assert live_event_count(path) == 1
    assert path.read_text(encoding="utf-8").count("\n") == 1


def test_log_match_event_writes_tmp_jsonl_and_skips_empty(tmp_path: Path) -> None:
    path = tmp_path / "leavers_events.jsonl"
    written = log_match_event(_leaver_with_pii(), path=path)
    assert written is not None
    _assert_no_pii(written)
    assert live_event_count(path) == 1

    skipped = log_match_event({"interest_sectors": [], "psych": {}}, path=path)
    assert skipped is None
    assert live_event_count(path) == 1


def test_record_persona_feedback_on_tmp_path(tmp_path: Path) -> None:
    path = tmp_path / "leavers_events.jsonl"
    event = log_match_event(_leaver_with_pii(), path=path)
    assert event is not None
    assert record_persona_feedback(event["event_id"], True, path=path) is True
    loaded = load_live_events(path)[0]
    assert loaded["persona_helpful"] is True
    assert "feedback_at" in loaded
    _assert_no_pii(loaded)
    assert record_persona_feedback("missing", False, path=path) is False


def test_prune_live_events_keeps_recent_only(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("LIVE_EVENTS_RETENTION_DAYS", "10")
    path = tmp_path / "leavers_events.jsonl"
    now = datetime(2026, 9, 2, tzinfo=timezone.utc)
    old = build_match_event(_leaver_with_pii())
    old["created_at"] = (now - timedelta(days=40)).isoformat()
    recent = build_match_event(_leaver_with_pii())
    recent["created_at"] = now.isoformat()
    path.write_text(
        json.dumps(old, ensure_ascii=False)
        + "\n"
        + json.dumps(recent, ensure_ascii=False)
        + "\n",
        encoding="utf-8",
    )

    removed = prune_live_events(path, now=now)
    assert removed == 1
    kept = load_live_events(path)
    assert len(kept) == 1
    assert kept[0]["event_id"] == recent["event_id"]


def test_events_to_training_rows_excludes_unhelpful_and_pii() -> None:
    helpful = build_match_event(_leaver_with_pii())
    helpful["persona_helpful"] = True
    unhelpful = build_match_event(_leaver_with_pii())
    unhelpful["persona_helpful"] = False
    no_sectors = build_match_event({"psych": {"dominant_riasec": ["Investigative"]}})

    rows = events_to_training_rows(
        [helpful, unhelpful, no_sectors],
        exclude_unhelpful=True,
    )
    assert len(rows) == 1
    row = rows[0]
    assert row["interest_sectors"] == ["cyber_digital"]
    assert row["source"] == "live_intake"
    blob = json.dumps(row)
    for snippet in _FREE_TEXT_SNIPPETS:
        assert snippet not in blob
    assert "name" not in row
    assert "email" not in row
    assert "about_me" not in row
