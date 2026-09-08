"""Offline AI-eval harness for later RAGAS scoring.

Default path is fully local: keyword evidence retrieval + deterministic
offline briefings. No FAISS, no companies_master.csv, no network.

  python scripts/run_ai_eval.py
  python scripts/run_ai_eval.py --skip-llm
  python scripts/run_ai_eval.py --ragas
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from glos_recommender.briefing import generate_briefing  # noqa: E402
from glos_recommender.rag import retrieve_evidence_keyword  # noqa: E402

GOLD_PATH = ROOT / "data" / "eval" / "gold_set.json"
LAST_RUN_PATH = ROOT / "data" / "eval" / "last_run.json"


# Coerce JSON lists/strings into a set of tags.
def _as_set(value: Any) -> set[str]:
    if isinstance(value, set):
        return {str(v).strip() for v in value if str(v).strip()}
    if isinstance(value, str):
        return {p.strip() for p in value.replace("|", ",").split(",") if p.strip()}
    if isinstance(value, (list, tuple)):
        return {str(v).strip() for v in value if str(v).strip()}
    return set()


# Shape a gold-set leaver so briefing/match_reasons can run offline.
def _prepare_leaver(raw: dict[str, Any]) -> dict[str, Any]:
    leaver = dict(raw)
    sectors = _as_set(leaver.get("target_sectors") or leaver.get("interest_sectors"))
    leaver["target_sectors"] = sectors
    leaver["interest_sectors"] = _as_set(leaver.get("interest_sectors")) or set(sectors)
    leaver["entry_routes"] = _as_set(leaver.get("entry_routes"))
    if not isinstance(leaver.get("psych"), dict):
        leaver["psych"] = {}
    interests = leaver.get("interests") or []
    if not leaver.get("profile_text"):
        leaver["profile_text"] = " ".join(str(x) for x in interests)
    return leaver


# One-line claim from an evidence card (RAGAS ground_truth fallback).
def _claim_line(card: dict[str, Any] | None) -> str:
    if not card:
        return ""
    claim = " ".join(str(card.get("claim") or "").split())
    if not claim:
        return ""
    first = claim.split(".")[0].strip()
    return f"{first}." if first else ""


# Keyword-retrieve + offline briefing for one gold case.
def _run_case(case: dict[str, Any], *, top_k: int, use_openai: bool = False) -> dict[str, Any]:
    question = str(case.get("question") or "").strip()
    leaver = _prepare_leaver(dict(case.get("leaver") or {}))
    company = dict(case.get("company") or {})

    hits = retrieve_evidence_keyword(question, top_k=top_k)
    contexts = [str(h.get("chunk") or "") for h in hits if str(h.get("chunk") or "").strip()]
    answer, source = generate_briefing(
        leaver,
        company,
        use_openai=use_openai,
        retrieved_chunks=hits,
    )

    ground_truth = " ".join(str(case.get("ground_truth") or "").split())
    if not ground_truth:
        top_card = hits[0].get("card") if hits else None
        ground_truth = _claim_line(top_card if isinstance(top_card, dict) else None)

    return {
        "retrieved_contexts": contexts,
        "answer": answer,
        "source": source or "offline",
        "ground_truth": ground_truth,
    }


# Write RAGAS-shaped rows for later evaluate().
def _last_run_records(cases: list[dict[str, Any]]) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    for case in cases:
        record: dict[str, Any] = {
            "question": case.get("question", ""),
            "contexts": list(case.get("retrieved_contexts") or []),
            "answer": case.get("answer", ""),
        }
        gt = str(case.get("ground_truth") or "").strip()
        if gt:
            record["ground_truth"] = gt
        records.append(record)
    return records


# Optional RAGAS pass (network + OpenAI). Skip cleanly if deps/key missing.
def _try_ragas(records: list[dict[str, Any]]) -> int:
    try:
        import ragas  # noqa: F401
    except ImportError:
        print(
            "Skipping RAGAS: package 'ragas' is not installed. "
            "Install eval-only deps with: pip install -r requirements-eval.txt"
        )
        return 0

    if not os.getenv("OPENAI_API_KEY", "").strip():
        print("Skipping RAGAS: OPENAI_API_KEY is not set.")
        return 0

    try:
        from ragas import evaluate
    except ImportError:
        print("Skipping RAGAS: ragas.evaluate could not be imported.")
        return 0

    dataset: Any = None
    try:
        from ragas import EvaluationDataset, SingleTurnSample

        samples = [
            SingleTurnSample(
                user_input=r["question"],
                retrieved_contexts=list(r.get("contexts") or []),
                response=r.get("answer") or "",
                reference=r.get("ground_truth") or "",
            )
            for r in records
        ]
        dataset = EvaluationDataset(samples=samples)
    except Exception:
        try:
            from datasets import Dataset

            dataset = Dataset.from_dict(
                {
                    "question": [r["question"] for r in records],
                    "contexts": [list(r.get("contexts") or []) for r in records],
                    "answer": [r.get("answer") or "" for r in records],
                    "ground_truth": [r.get("ground_truth") or "" for r in records],
                }
            )
        except Exception as exc:
            print(f"Skipping RAGAS: could not build an evaluation dataset ({exc}).")
            return 0

    try:
        result = evaluate(dataset)
    except Exception as exc:
        print(f"RAGAS evaluation failed: {exc}")
        return 1

    print(result)
    scores_path = LAST_RUN_PATH.with_name("last_ragas_scores.json")
    try:
        payload: Any
        if hasattr(result, "to_pandas"):
            payload = result.to_pandas().to_dict(orient="records")
        elif isinstance(result, dict):
            payload = result
        else:
            payload = {"result": str(result)}
        scores_path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        print(f"Wrote {scores_path.relative_to(ROOT)}")
    except Exception:
        pass
    return 0


# CLI: offline gold run, optional RAGAS.
def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Offline AI-eval harness (keyword RAG + offline briefing).")
    parser.add_argument(
        "--skip-llm",
        action="store_true",
        default=True,
        help="Use generate_briefing(..., use_openai=False). Default: on.",
    )
    parser.add_argument(
        "--ragas",
        action="store_true",
        help="After the offline run, import ragas and evaluate (needs OPENAI_API_KEY).",
    )
    parser.add_argument("--gold", type=Path, default=GOLD_PATH, help="Gold set JSON path.")
    parser.add_argument("--out", type=Path, default=LAST_RUN_PATH, help="last_run.json output path.")
    parser.add_argument("--top-k", type=int, default=4, help="Keyword retrieval depth.")
    args = parser.parse_args(argv)

    gold_path: Path = args.gold if args.gold.is_absolute() else ROOT / args.gold
    out_path: Path = args.out if args.out.is_absolute() else ROOT / args.out

    cases = json.loads(gold_path.read_text(encoding="utf-8"))
    if not isinstance(cases, list) or not cases:
        raise SystemExit(f"Gold set must be a non-empty JSON list: {gold_path}")

    use_openai = not bool(args.skip_llm)
    print(f"Loaded {len(cases)} gold cases from {gold_path.relative_to(ROOT)}")
    print(
        "Retrieval: retrieve_evidence_keyword (FAISS disabled). "
        f"Briefings: use_openai={use_openai}."
    )

    updated: list[dict[str, Any]] = []
    for case in cases:
        if not isinstance(case, dict):
            raise SystemExit("Each gold case must be an object.")
        generated = _run_case(
            case,
            top_k=max(1, int(args.top_k)),
            use_openai=use_openai,
        )
        merged = dict(case)
        merged["retrieved_contexts"] = generated["retrieved_contexts"]
        merged["answer"] = generated["answer"]
        merged["source"] = generated["source"]
        if generated["ground_truth"] and not str(merged.get("ground_truth") or "").strip():
            merged["ground_truth"] = generated["ground_truth"]
        n_ctx = len(merged["retrieved_contexts"])
        print(f"  {merged.get('id', '?')}: {n_ctx} contexts, source={merged['source']}")
        updated.append(merged)

    gold_path.parent.mkdir(parents=True, exist_ok=True)
    gold_path.write_text(json.dumps(updated, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"Wrote {gold_path.relative_to(ROOT)}")

    records = _last_run_records(updated)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "generated_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "skip_llm": bool(args.skip_llm),
        "n": len(records),
        "records": records,
    }
    out_path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"Wrote {out_path.relative_to(ROOT)}")

    if args.ragas:
        try:
            from dotenv import load_dotenv

            load_dotenv(ROOT / ".env")
        except Exception:
            pass
        return _try_ragas(records)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
