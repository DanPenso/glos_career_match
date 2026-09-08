"""Claude Haiku RAGAS-style scores for work briefing journeys.

Judge is Anthropic (ANTHROPIC_API_KEY / ANTHROPIC_MODEL). Never OpenAI.
Temperature 0. Results are cached so clustering can re-run without re-paying.

  .venv\\Scripts\\python scripts/eval/score_ragas.py --run-dir latest
  .venv\\Scripts\\python scripts/eval/score_ragas.py --run-dir data/eval/runs/<ts>
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

_SCRIPTS_EVAL = Path(__file__).resolve().parent
if str(_SCRIPTS_EVAL) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS_EVAL))

from common import (  # noqa: E402
    JUDGE_MODEL_DEFAULT,
    METRIC_VERSION,
    ROOT,
    STRATA,
    contexts_as_strings,
    jsonable,
    load_dotenv_root,
    read_jsonl,
    resolve_run_dir,
)

load_dotenv_root()

METRIC_KEYS = (
    "faithfulness",
    "answer_relevancy",
    "context_precision",
    "programmes_grounding",
    "provenance_cues",
)

JUDGE_SYSTEM = """You are a strict evaluator for MatchKite, a Gloucestershire careers-guidance demo.
Score only from the supplied user intake, retrieved contexts, and the answer.
Do not reward warmth or coaching tone if claims are ungrounded.
Return JSON only. Temperature-equivalent: be deterministic and conservative.
"""

JUDGE_USER = """Score this work-mode employer briefing.

SCORING (floats 0.0–1.0):
- faithfulness: every employer/programme/vacancy claim in the answer is supported by CONTEXTS.
  Invented open roles, salaries, culture, or scheme names → low.
- answer_relevancy: the answer addresses THIS leaver (interests, quals, routes, location), not a generic pep talk.
- context_precision: retrieved STRATEGY/catalogue/facts that appear in CONTEXTS are on-topic for this intake/match.
- programmes_grounding: named programmes or current openings only if present in verified_programmes context;
  otherwise the answer must not invent them (pointing to Find an apprenticeship / official site is fine).
- provenance_cues: if the top match source is vacancies or companies_house, the answer must caution that
  listings may be historical/closed and/or that registry facts are not careers copy, and must tell the
  reader to verify on the official site. For curated/seed matches, a verify-official cue is still expected.

USER_INPUT (serialised intake):
{user_input}

CONTEXTS:
{contexts}

ANSWER (briefing + top-3 match list):
{answer}

TOP MATCH SOURCE: {source_kind} ({source_label})

Respond with JSON only:
{{
  "faithfulness": 0.0,
  "answer_relevancy": 0.0,
  "context_precision": 0.0,
  "programmes_grounding": 0.0,
  "provenance_cues": 0.0,
  "notes": "one short sentence"
}}
"""


def _judge_model() -> str:
    return os.getenv("ANTHROPIC_MODEL", JUDGE_MODEL_DEFAULT).strip() or JUDGE_MODEL_DEFAULT


def _cache_key(record: dict[str, Any], model: str) -> str:
    payload = {
        "journey_id": record.get("journey_id"),
        "answer": record.get("answer") or record.get("briefing_markdown"),
        "contexts": record.get("contexts") or [],
        "user_input": record.get("user_input") or "",
        "model": model,
        "metric_version": METRIC_VERSION,
    }
    blob = json.dumps(jsonable(payload), ensure_ascii=False, sort_keys=True)
    return hashlib.sha256(blob.encode("utf-8")).hexdigest()


def _load_cache(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {}
    return data if isinstance(data, dict) else {}


def _save_cache(path: Path, cache: dict[str, Any]) -> None:
    path.write_text(json.dumps(cache, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def _clip(value: Any) -> float:
    try:
        n = float(value)
    except (TypeError, ValueError):
        return 0.0
    if n < 0:
        return 0.0
    if n > 1:
        return 1.0
    return n


def _parse_json_object(text: str) -> dict[str, Any]:
    raw = (text or "").strip()
    if raw.startswith("```"):
        raw = raw.strip("`")
        if raw.lower().startswith("json"):
            raw = raw[4:]
        raw = raw.strip()
    try:
        data = json.loads(raw)
        if isinstance(data, dict):
            return data
    except json.JSONDecodeError:
        pass
    start = raw.find("{")
    end = raw.rfind("}")
    if start >= 0 and end > start:
        data = json.loads(raw[start : end + 1])
        if isinstance(data, dict):
            return data
    raise ValueError("judge did not return a JSON object")


def _anthropic_judge(record: dict[str, Any], *, model: str) -> dict[str, Any]:
    api_key = os.getenv("ANTHROPIC_API_KEY", "").strip()
    if not api_key:
        raise SystemExit("ANTHROPIC_API_KEY is not set. Refusing to use OpenAI as judge.")

    top = (record.get("top3") or [{}])[0] if record.get("top3") else {}
    source_kind = str(top.get("source") or "unknown")
    source_label = str(top.get("source_label") or source_kind)
    ctx_blob = "\n\n".join(contexts_as_strings(record.get("contexts") or [])) or "(none)"
    user = JUDGE_USER.format(
        user_input=record.get("user_input") or serialise_fallback(record),
        contexts=ctx_blob[:24_000],
        answer=(record.get("answer") or record.get("briefing_markdown") or "")[:12_000],
        source_kind=source_kind,
        source_label=source_label,
    )

    import time

    import anthropic

    client = anthropic.Anthropic(api_key=api_key)
    last_err: Exception | None = None
    resp = None
    for attempt in range(1, 5):
        try:
            # anthropic>=1.3 dropped temperature= from Messages.create; keep T=0 via extra_body.
            resp = client.messages.create(
                model=model,
                max_tokens=400,
                system=JUDGE_SYSTEM,
                messages=[{"role": "user", "content": user}],
                extra_body={"temperature": 0},
            )
            break
        except anthropic.APIConnectionError as exc:
            last_err = exc
            time.sleep(min(20, 2 ** attempt))
    if resp is None:
        raise SystemExit(f"Anthropic connection failed after retries: {last_err}")
    text_parts: list[str] = []
    for block in resp.content:
        if getattr(block, "type", "") == "text":
            text_parts.append(getattr(block, "text", "") or "")
    parsed = _parse_json_object("\n".join(text_parts))
    scores = {k: _clip(parsed.get(k)) for k in METRIC_KEYS}
    usage = getattr(resp, "usage", None)
    return {
        **scores,
        "notes": str(parsed.get("notes") or "").strip(),
        "judge_model": model,
        "metric_version": METRIC_VERSION,
        "input_tokens": int(getattr(usage, "input_tokens", 0) or 0),
        "output_tokens": int(getattr(usage, "output_tokens", 0) or 0),
    }


def serialise_fallback(record: dict[str, Any]) -> str:
    from common import serialise_intake

    return str(record.get("user_input") or serialise_intake(record.get("intake") or {}))


def _mean(values: list[float]) -> float:
    return sum(values) / len(values) if values else 0.0


def _write_metrics_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    import csv

    fields = [
        "journey_id",
        "stratum",
        "persona",
        "briefing_source",
        "match_source",
        *METRIC_KEYS,
        "notes",
        "cached",
        "input_tokens",
        "output_tokens",
    ]
    with path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()
        for row in rows:
            writer.writerow({k: row.get(k, "") for k in fields})


def _md_table(headers: list[str], rows: list[list[str]]) -> str:
    line = "| " + " | ".join(headers) + " |"
    sep = "| " + " | ".join("---" for _ in headers) + " |"
    body = ["| " + " | ".join(r) + " |" for r in rows]
    return "\n".join([line, sep, *body])


def _write_stratum_md(path: Path, rows: list[dict[str, Any]]) -> None:
    lines = [
        "# Metrics by stratum",
        "",
        f"Judge: Anthropic `{rows[0].get('judge_model') if rows else _judge_model()}` · "
        f"metric_version `{METRIC_VERSION}` · n={len(rows)}",
        "",
        "OpenAI was not used as judge.",
        "",
    ]
    headers = ["stratum", "n", *METRIC_KEYS]
    table_rows: list[list[str]] = []
    for stratum in STRATA:
        subset = [r for r in rows if r.get("stratum") == stratum]
        if not subset:
            table_rows.append([stratum, "0", *["—" for _ in METRIC_KEYS]])
            continue
        cells = [stratum, str(len(subset))]
        for key in METRIC_KEYS:
            cells.append(f"{_mean([float(r[key]) for r in subset]):.3f}")
        table_rows.append(cells)
    overall = ["all", str(len(rows))]
    for key in METRIC_KEYS:
        overall.append(f"{_mean([float(r[key]) for r in rows]):.3f}")
    table_rows.append(overall)
    lines.append(_md_table(headers, table_rows))
    lines.append("")
    by_src: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        by_src[str(row.get("match_source") or "unknown")].append(row)
    if by_src:
        lines.append("## By top-match source")
        lines.append("")
        src_headers = ["source", "n", "faithfulness", "provenance_cues", "programmes_grounding"]
        src_rows = []
        for src, subset in sorted(by_src.items(), key=lambda kv: -len(kv[1])):
            src_rows.append(
                [
                    src,
                    str(len(subset)),
                    f"{_mean([float(r['faithfulness']) for r in subset]):.3f}",
                    f"{_mean([float(r['provenance_cues']) for r in subset]):.3f}",
                    f"{_mean([float(r['programmes_grounding']) for r in subset]):.3f}",
                ]
            )
        lines.append(_md_table(src_headers, src_rows))
        lines.append("")
    path.write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")


def _write_worst(path: Path, rows: list[dict[str, Any]], *, n: int = 20) -> None:
    lines = ["# Spot-check: worst faithfulness / answer relevancy", "", f"Top {n} by each metric.", ""]
    for metric, title in (
        ("faithfulness", "Lowest faithfulness"),
        ("answer_relevancy", "Lowest answer relevancy"),
    ):
        ordered = sorted(rows, key=lambda r: float(r.get(metric) or 0.0))[:n]
        lines.append(f"## {title}")
        lines.append("")
        headers = ["journey_id", "stratum", "match_source", metric, "notes"]
        table = []
        for row in ordered:
            table.append(
                [
                    str(row.get("journey_id") or ""),
                    str(row.get("stratum") or ""),
                    str(row.get("match_source") or ""),
                    f"{float(row.get(metric) or 0):.3f}",
                    str(row.get("notes") or "").replace("|", "/")[:80],
                ]
            )
        lines.append(_md_table(headers, table) if table else "_none_")
        lines.append("")
    path.write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Score journey briefings with Claude Haiku (not OpenAI).")
    parser.add_argument("--run-dir", default="latest")
    parser.add_argument("--limit", type=int, default=None)
    parser.add_argument("--force", action="store_true", help="Ignore judge cache.")
    args = parser.parse_args(argv)

    if os.getenv("EVAL_JUDGE_PROVIDER", "").strip().lower() == "openai":
        raise SystemExit("OpenAI must not be used as the judge.")

    run_dir = resolve_run_dir(args.run_dir)
    raw_path = run_dir / "raw_journeys.jsonl"
    if not raw_path.exists():
        raise SystemExit(f"Missing {raw_path}")

    records = read_jsonl(raw_path)
    if args.limit:
        records = records[: max(1, args.limit)]
    if not records:
        raise SystemExit("raw_journeys.jsonl is empty")

    model = _judge_model()
    cache_path = run_dir / "judge_cache.json"
    cache = {} if args.force else _load_cache(cache_path)

    print(f"Scoring {len(records)} journeys with {model} ({METRIC_VERSION})")
    print("Judge provider: Anthropic. OpenAI is not used as judge.")

    rows: list[dict[str, Any]] = []
    in_tok = 0
    out_tok = 0
    n_cached = 0
    for i, rec in enumerate(records, start=1):
        key = _cache_key(rec, model)
        cached = (not args.force) and key in cache
        if cached:
            judged = dict(cache[key])
            n_cached += 1
        else:
            judged = _anthropic_judge(rec, model=model)
            judged["cache_key"] = key
            cache[key] = judged
            _save_cache(cache_path, cache)
        top = (rec.get("top3") or [{}])[0] if rec.get("top3") else {}
        row = {
            "journey_id": rec.get("journey_id"),
            "stratum": rec.get("stratum"),
            "persona": rec.get("persona"),
            "briefing_source": (rec.get("models") or {}).get("briefing_source"),
            "match_source": top.get("source"),
            "judge_model": judged.get("judge_model") or model,
            "cached": cached,
            "notes": judged.get("notes") or "",
            "input_tokens": judged.get("input_tokens") or 0,
            "output_tokens": judged.get("output_tokens") or 0,
        }
        for metric in METRIC_KEYS:
            row[metric] = _clip(judged.get(metric))
        rows.append(row)
        in_tok += int(row["input_tokens"] or 0)
        out_tok += int(row["output_tokens"] or 0)
        print(
            f"  [{i}/{len(records)}] {row['journey_id']}  "
            f"faith={row['faithfulness']:.2f} rel={row['answer_relevancy']:.2f}"
            f"{'  [cache]' if cached else ''}"
        )

    _write_metrics_csv(run_dir / "metrics.csv", rows)
    _write_stratum_md(run_dir / "metrics_by_stratum.md", rows)
    _write_worst(run_dir / "worst_cases.md", rows)
    summary = {
        "generated_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "n": len(rows),
        "n_cached": n_cached,
        "judge_model": model,
        "metric_version": METRIC_VERSION,
        "judge_provider": "anthropic",
        "input_tokens": in_tok,
        "output_tokens": out_tok,
        "means": {k: round(_mean([float(r[k]) for r in rows]), 4) for k in METRIC_KEYS},
    }
    (run_dir / "score_summary.json").write_text(
        json.dumps(summary, indent=2) + "\n", encoding="utf-8"
    )
    print(f"Wrote {(run_dir / 'metrics.csv').relative_to(ROOT)}")
    print(f"Wrote {(run_dir / 'metrics_by_stratum.md').relative_to(ROOT)}")
    print(f"Wrote {(run_dir / 'worst_cases.md').relative_to(ROOT)}")
    print(f"Cache hits: {n_cached}/{len(rows)} · tokens in={in_tok} out={out_tok}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
