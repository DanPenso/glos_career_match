"""Privacy-safe live intake logging for clustering retrain loops.

Each completed match appends one JSONL event under data/live/.
Events are anonymous feature vectors + model outputs — not PII.
"""

from __future__ import annotations

import json
import os
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from .personas import RIASEC, SECTORS

PROJECT_ROOT = Path(__file__).resolve().parents[2]
LIVE_DIR = PROJECT_ROOT / "data" / "live"
EVENTS_PATH = LIVE_DIR / "leavers_events.jsonl"

# Live Glos users outweigh open-data synthetic rows when merging
DEFAULT_LIVE_WEIGHT = 4.0
DEFAULT_RETENTION_DAYS = 180


def _as_list(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, set):
        return sorted(str(x) for x in value if x)
    if isinstance(value, (list, tuple)):
        return [str(x) for x in value if x]
    text = str(value).strip()
    if not text:
        return []
    if "|" in text:
        return [p.strip() for p in text.split("|") if p.strip()]
    return [text]


def _sectors_from_leaver(leaver: dict[str, Any]) -> list[str]:
    raw = set(_as_list(leaver.get("interest_sectors"))) | set(
        _as_list(leaver.get("target_sectors"))
    )
    return sorted(s for s in raw if s in SECTORS)


def _riasec_from_leaver(leaver: dict[str, Any]) -> tuple[list[str], dict[str, float]]:
    psych = leaver.get("psych") or {}
    dominant = [d for d in _as_list(psych.get("dominant_riasec")) if d in RIASEC]
    scores_raw = psych.get("riasec_scores") or {}
    scores: dict[str, float] = {}
    for name in RIASEC:
        if name in scores_raw:
            try:
                scores[name] = float(scores_raw[name])
            except (TypeError, ValueError):
                continue
    if not dominant and scores:
        dominant = [
            n
            for n, _ in sorted(scores.items(), key=lambda kv: kv[1], reverse=True)[:2]
        ]
    return dominant, scores


def build_match_event(
    leaver: dict[str, Any],
    persona_payload: dict[str, Any] | None = None,
    *,
    channel: str = "web",
) -> dict[str, Any]:
    """Build one anonymous clustering training event (no PII)."""
    persona_payload = persona_payload or {}
    sectors = _sectors_from_leaver(leaver)
    dominant, scores = _riasec_from_leaver(leaver)
    fit = persona_payload.get("persona_fit") or []
    fit_compact = [
        {
            "persona": row.get("persona"),
            "closeness": row.get("closeness"),
            "is_primary": bool(row.get("is_primary")),
            "is_runner_up": bool(row.get("is_runner_up")),
        }
        for row in fit
        if row.get("persona")
    ]
    return {
        "event_id": str(uuid.uuid4()),
        "created_at": datetime.now(timezone.utc).isoformat(),
        "channel": channel,
        "source": "live_intake",
        "cohort": "live_glos",
        "sample_weight": DEFAULT_LIVE_WEIGHT,
        "interest_sectors": sectors,
        "dominant_riasec": dominant,
        "riasec_scores": scores,
        "persona_assigned": persona_payload.get("persona") or leaver.get("persona"),
        "runner_up": persona_payload.get("runner_up"),
        "cluster_id": persona_payload.get("cluster_id"),
        "method": persona_payload.get("method"),
        "persona_fit": fit_compact,
        "leaver_type": str(leaver.get("leaver_type") or ""),
        # Feedback fields filled later via record_persona_feedback
        "persona_helpful": None,
    }


def append_live_event(event: dict[str, Any], path: Path | None = None) -> Path:
    """Append one JSON line. Creates data/live/ if needed."""
    out = path or EVENTS_PATH
    out.parent.mkdir(parents=True, exist_ok=True)
    with out.open("a", encoding="utf-8") as f:
        f.write(json.dumps(event, ensure_ascii=False) + "\n")
    prune_live_events(out)
    return out


def _retention_days() -> int:
    """Read retention policy from env, fallback to conservative default."""
    raw = os.getenv("LIVE_EVENTS_RETENTION_DAYS", str(DEFAULT_RETENTION_DAYS)).strip()
    try:
        days = int(raw)
    except ValueError:
        return DEFAULT_RETENTION_DAYS
    return max(1, days)


def _parse_iso8601(value: Any) -> datetime | None:
    text = str(value or "").strip()
    if not text:
        return None
    try:
        return datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError:
        return None


def prune_live_events(path: Path | None = None, *, now: datetime | None = None) -> int:
    """Delete expired live events and return number removed."""
    src = path or EVENTS_PATH
    events = load_live_events(src)
    if not events:
        return 0
    ref = now or datetime.now(timezone.utc)
    cutoff = ref - timedelta(days=_retention_days())
    kept: list[dict[str, Any]] = []
    removed = 0
    for ev in events:
        created = _parse_iso8601(ev.get("created_at"))
        if created is None:
            # Keep malformed rows so maintainers can inspect/fix manually.
            kept.append(ev)
            continue
        if created.tzinfo is None:
            created = created.replace(tzinfo=timezone.utc)
        if created < cutoff:
            removed += 1
            continue
        kept.append(ev)
    if removed == 0:
        return 0
    src.parent.mkdir(parents=True, exist_ok=True)
    with src.open("w", encoding="utf-8") as f:
        for ev in kept:
            f.write(json.dumps(ev, ensure_ascii=False) + "\n")
    return removed


def log_match_event(
    leaver: dict[str, Any],
    persona_payload: dict[str, Any] | None = None,
    *,
    channel: str = "web",
) -> dict[str, Any] | None:
    """Log a completed match. Returns the event, or None if nothing useful to store."""
    event = build_match_event(leaver, persona_payload, channel=channel)
    if not event["interest_sectors"] and not event["dominant_riasec"]:
        return None
    append_live_event(event)
    return event


def load_live_events(path: Path | None = None) -> list[dict[str, Any]]:
    src = path or EVENTS_PATH
    if not src.exists():
        return []
    rows: list[dict[str, Any]] = []
    with src.open(encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                rows.append(json.loads(line))
            except json.JSONDecodeError:
                continue
    return rows


def record_persona_feedback(
    event_id: str,
    helpful: bool,
    *,
    path: Path | None = None,
) -> bool:
    """Update persona_helpful on a prior event (rewrite file). Returns True if found."""
    src = path or EVENTS_PATH
    events = load_live_events(src)
    found = False
    for ev in events:
        if ev.get("event_id") == event_id:
            ev["persona_helpful"] = bool(helpful)
            ev["feedback_at"] = datetime.now(timezone.utc).isoformat()
            found = True
            break
    if not found:
        return False
    src.parent.mkdir(parents=True, exist_ok=True)
    with src.open("w", encoding="utf-8") as f:
        for ev in events:
            f.write(json.dumps(ev, ensure_ascii=False) + "\n")
    return True


def events_to_training_rows(
    events: list[dict[str, Any]] | None = None,
    *,
    min_weight: float = 1.0,
    exclude_unhelpful: bool = True,
) -> list[dict[str, Any]]:
    """Convert live events into curated-leaver-style row dicts for training."""
    events = events if events is not None else load_live_events()
    rows: list[dict[str, Any]] = []
    for ev in events:
        if exclude_unhelpful and ev.get("persona_helpful") is False:
            continue
        sectors = [s for s in _as_list(ev.get("interest_sectors")) if s in SECTORS]
        if not sectors:
            continue
        dominant = [d for d in _as_list(ev.get("dominant_riasec")) if d in RIASEC]
        scores = ev.get("riasec_scores") or {}
        weight = float(ev.get("sample_weight") or DEFAULT_LIVE_WEIGHT)
        if ev.get("persona_helpful") is True:
            weight = max(weight, DEFAULT_LIVE_WEIGHT) * 1.25
        weight = max(min_weight, weight)
        seed = str(ev.get("persona_assigned") or "")
        rows.append(
            {
                "leaver_id": f"live_{ev.get('event_id', uuid.uuid4())}",
                "interest_sectors": sectors,
                "target_sectors": sectors,
                "dominant_riasec": dominant,
                "riasec_scores": scores,
                "source": "live_intake",
                "cohort": "live_glos",
                "sample_weight": weight,
                "persona_seed": seed,
            }
        )
    return rows


def live_event_count(path: Path | None = None) -> int:
    return len(load_live_events(path))
