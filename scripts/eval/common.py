"""Shared paths and helpers for the 200-journey MatchKite work-briefing eval.

This is NOT the 10-case offline gold set in scripts/run_ai_eval.py.
"""

from __future__ import annotations

import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

RANDOM_SEED = 42
STRATA = ("no_quals", "school_leaver", "fe_leaver", "graduate")
N_PER_STRATUM = 50
MODE = "work"
JUDGE_MODEL_DEFAULT = "claude-haiku-4-5"
METRIC_VERSION = "v1-haiku-json-5"

ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "src"
EVAL_DIR = ROOT / "data" / "eval"
JOURNEYS_PATH = EVAL_DIR / "journeys_200.jsonl"
RUNS_DIR = EVAL_DIR / "runs"


def ensure_src_path() -> None:
    root_s = str(ROOT)
    src_s = str(SRC)
    if src_s not in sys.path:
        sys.path.insert(0, src_s)
    if root_s not in sys.path:
        sys.path.insert(0, root_s)


def load_dotenv_root() -> None:
    try:
        from dotenv import load_dotenv

        load_dotenv(ROOT / ".env")
    except Exception:
        pass


def jsonable(value: Any) -> Any:
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    if isinstance(value, dict):
        return {str(k): jsonable(v) for k, v in value.items()}
    if isinstance(value, set):
        return [jsonable(v) for v in sorted(value, key=str)]
    if isinstance(value, (list, tuple)):
        return [jsonable(v) for v in value]
    try:
        import numpy as np

        if isinstance(value, np.generic):
            return value.item()
        if isinstance(value, np.ndarray):
            return value.tolist()
    except Exception:
        pass
    try:
        import pandas as pd

        if isinstance(value, pd.Timestamp):
            return value.isoformat()
        try:
            if pd.isna(value):
                return None
        except (TypeError, ValueError):
            pass
    except Exception:
        pass
    return str(value)


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    with path.open(encoding="utf-8") as f:
        for line_no, line in enumerate(f, start=1):
            text = line.strip()
            if not text:
                continue
            rec = json.loads(text)
            if not isinstance(rec, dict):
                raise SystemExit(f"{path}:{line_no} is not a JSON object")
            rows.append(rec)
    return rows


def write_jsonl(path: Path, rows: Iterable[dict[str, Any]]) -> int:
    path.parent.mkdir(parents=True, exist_ok=True)
    n = 0
    with path.open("w", encoding="utf-8") as f:
        for row in rows:
            f.write(json.dumps(jsonable(row), ensure_ascii=False) + "\n")
            n += 1
    return n


def serialise_intake(question: dict[str, Any]) -> str:
    payload = jsonable(question)
    return json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True)


def pack_answer(briefing_markdown: str, matches: list[dict[str, Any]]) -> str:
    lines = [str(briefing_markdown or "").strip(), "", "## Top matches", ""]
    for i, match in enumerate(matches, start=1):
        name = str(match.get("name") or match.get("company_id") or "unknown")
        label = str(match.get("source_label") or match.get("source") or "").strip()
        cid = str(match.get("company_id") or "").strip()
        extra = " · ".join(x for x in (label, cid) if x)
        lines.append(f"{i}. {name}" + (f" ({extra})" if extra else ""))
    return "\n".join(lines).strip() + "\n"


def contexts_as_strings(contexts: list[dict[str, Any]] | None) -> list[str]:
    out: list[str] = []
    for item in contexts or []:
        if isinstance(item, str):
            text = item.strip()
        else:
            kind = str(item.get("kind") or "context").strip()
            src = str(item.get("source") or "").strip()
            body = str(item.get("text") or item.get("chunk") or "").strip()
            head = f"[{kind}" + (f" | {src}" if src else "") + "]"
            text = f"{head}\n{body}".strip() if body else ""
        if text:
            out.append(text)
    return out


def smoke_ids(journeys: list[dict[str, Any]], *, n_per_stratum: int = 2) -> list[str]:
    picked: list[str] = []
    for stratum in STRATA:
        subset = [j for j in journeys if j.get("stratum") == stratum]
        for row in subset[:n_per_stratum]:
            jid = str(row.get("journey_id") or "").strip()
            if jid:
                picked.append(jid)
    return picked


def new_run_dir(now: datetime | None = None) -> Path:
    stamp = (now or datetime.now(timezone.utc)).strftime("%Y%m%dT%H%M%SZ")
    path = RUNS_DIR / stamp
    path.mkdir(parents=True, exist_ok=True)
    (path / "figures").mkdir(exist_ok=True)
    return path


def latest_run_dir() -> Path | None:
    if not RUNS_DIR.exists():
        return None
    dirs = [p for p in RUNS_DIR.iterdir() if p.is_dir() and p.name != ".gitkeep"]
    if not dirs:
        return None
    return max(dirs, key=lambda p: p.name)


def resolve_run_dir(raw: str | Path | None) -> Path:
    if raw in (None, "", "latest"):
        found = latest_run_dir()
        if found is None:
            raise SystemExit("No eval run directories under data/eval/runs/")
        return found
    path = Path(raw)
    if not path.is_absolute():
        path = ROOT / path
    if not path.is_dir():
        raise SystemExit(f"Run directory not found: {path}")
    return path


def env_flag(name: str, default: str = "") -> str:
    return os.getenv(name, default).strip()
