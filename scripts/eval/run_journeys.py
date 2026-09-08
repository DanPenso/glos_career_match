"""In-process WORK match + briefing runner for journeys_200.jsonl.

Does not call production HTTP. Uses repo-root masters / FAISS / corpus only.
Does not crawl commercial websites.

  .venv\\Scripts\\python scripts/eval/run_journeys.py --smoke --offline
  .venv\\Scripts\\python scripts/eval/run_journeys.py --offline --limit 8
  .venv\\Scripts\\python scripts/eval/run_journeys.py   # full 200, OpenAI briefings
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

_SCRIPTS_EVAL = Path(__file__).resolve().parent
if str(_SCRIPTS_EVAL) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS_EVAL))

from common import (  # noqa: E402
    JOURNEYS_PATH,
    JUDGE_MODEL_DEFAULT,
    ROOT,
    STRATA,
    ensure_src_path,
    jsonable,
    load_dotenv_root,
    new_run_dir,
    pack_answer,
    read_jsonl,
    serialise_intake,
    smoke_ids,
    write_jsonl,
)

ensure_src_path()
load_dotenv_root()

from glos_recommender.briefing import generate_briefing  # noqa: E402
from glos_recommender.matching import load_companies, match_companies  # noqa: E402
from glos_recommender.programmes import (  # noqa: E402
    format_programmes_for_prompt,
    programmes_for_company,
)
from glos_recommender.provenance import (  # noqa: E402
    classify_employer_source,
    employer_facts_block,
    provenance_payload,
)
from glos_recommender.rag import (  # noqa: E402
    build_retrieval_query,
    filter_retrieved_hits_for_employer,
    retrieve,
)


MATCH_FLAGS = (
    "use_openai_briefing",
    "use_gemini_plan",
    "allow_anonymous_logging",
    "top_n",
    "mode",
)


def _form_for_match(question: dict[str, Any]) -> dict[str, Any]:
    form = dict(question)
    for key in MATCH_FLAGS:
        form.pop(key, None)
    form["mode"] = "work"
    return form


def _row_to_match_meta(row: Any) -> dict[str, Any]:
    data = row.to_dict() if hasattr(row, "to_dict") else dict(row)
    clean: dict[str, Any] = {}
    for key, value in data.items():
        if str(key).endswith("_list"):
            continue
        if isinstance(value, (list, tuple, set, dict)):
            continue
        clean[str(key)] = jsonable(value)
    kind = classify_employer_source(clean)
    prov = provenance_payload(clean, mode="work")
    return {
        "company_id": str(clean.get("company_id") or ""),
        "name": str(clean.get("name") or ""),
        "town": str(clean.get("town") or ""),
        "postcode": str(clean.get("postcode") or ""),
        "sectors": str(clean.get("sectors") or ""),
        "entry_routes": str(clean.get("entry_routes") or ""),
        "website": str(clean.get("website") or ""),
        "source": prov.get("source") or kind,
        "source_label": prov.get("source_label") or "",
        "source_note": prov.get("source_note") or "",
        "final_score": clean.get("final_score"),
        "hiring_signal": str(clean.get("hiring_signal") or ""),
    }


def _chunk_record(hit: dict[str, Any]) -> dict[str, Any]:
    return {
        "kind": "rag_chunk",
        "source": str(hit.get("source") or ""),
        "source_label": str(hit.get("source_label") or ""),
        "score": jsonable(hit.get("score")),
        "text": str(hit.get("chunk") or hit.get("text") or ""),
    }


def _pack_contexts(
    company: dict[str, Any],
    programmes: list[dict[str, Any]],
    rag_hits: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    contexts: list[dict[str, Any]] = [
        {
            "kind": "employer_facts",
            "source": str(company.get("source") or classify_employer_source(company)),
            "text": employer_facts_block(company),
        }
    ]
    if programmes:
        contexts.append(
            {
                "kind": "verified_programmes",
                "source": str(company.get("company_id") or ""),
                "text": format_programmes_for_prompt(programmes),
            }
        )
    else:
        contexts.append(
            {
                "kind": "verified_programmes",
                "source": str(company.get("company_id") or ""),
                "text": (
                    "No curated verified programmes on file for this employer. "
                    "Do not invent programme or job titles."
                ),
            }
        )
    for hit in rag_hits:
        rec = _chunk_record(hit)
        if rec["text"].strip():
            contexts.append(rec)
    return contexts


def _select_journeys(
    journeys: list[dict[str, Any]],
    *,
    smoke: bool,
    limit: int | None,
    ids: list[str],
) -> list[dict[str, Any]]:
    if ids:
        wanted = set(ids)
        picked = [j for j in journeys if j.get("journey_id") in wanted]
        missing = wanted - {j.get("journey_id") for j in picked}
        if missing:
            raise SystemExit(f"Unknown journey ids: {sorted(missing)}")
        return picked
    if smoke:
        keep = set(smoke_ids(journeys, n_per_stratum=2))
        return [j for j in journeys if j.get("journey_id") in keep]
    if limit is not None and limit > 0:
        return journeys[:limit]
    return journeys


def run_one(
    journey: dict[str, Any],
    companies: Any,
    *,
    use_openai: bool,
    rag_top_k: int,
) -> dict[str, Any]:
    question = dict(journey.get("question") or {})
    question["mode"] = "work"
    question["use_gemini_plan"] = False
    form = _form_for_match(question)
    top_n = int(question.get("top_n") or 3)

    t0 = time.perf_counter()
    leaver, ranked = match_companies(form, companies, top_n=top_n)
    match_ms = (time.perf_counter() - t0) * 1000

    matches = [_row_to_match_meta(ranked.iloc[i]) for i in range(len(ranked))]
    briefing_md = ""
    briefing_source = "none"
    rag_hits: list[dict[str, Any]] = []
    programmes: list[dict[str, Any]] = []
    briefing_ms = 0.0
    openai_model = ""

    if matches:
        top = ranked.iloc[0]
        company_dict = top.to_dict() if hasattr(top, "to_dict") else dict(top)
        programmes = programmes_for_company(str(company_dict.get("company_id") or ""))
        query = build_retrieval_query(leaver, company_dict)
        employer_name = str(company_dict.get("name") or "")
        try:
            rag_hits = retrieve(
                query,
                top_k=rag_top_k,
                prefer_evidence=True,
                employer_name=employer_name,
            )
            rag_hits = filter_retrieved_hits_for_employer(rag_hits, employer_name)
        except Exception:
            rag_hits = []
        t1 = time.perf_counter()
        briefing_md, briefing_source = generate_briefing(
            leaver,
            top,
            use_openai=use_openai,
            retrieved_chunks=rag_hits,
            mode="work",
        )
        briefing_ms = (time.perf_counter() - t1) * 1000
        if briefing_source == "openai":
            import os

            openai_model = os.getenv("OPENAI_MODEL", "gpt-4o-mini").strip() or "gpt-4o-mini"
        # grounded_template is delivered copy, not an OpenAI billed call.

    contexts = _pack_contexts(matches[0] if matches else {}, programmes, rag_hits)
    answer = pack_answer(briefing_md, matches)
    total_ms = match_ms + briefing_ms

    return {
        "journey_id": journey.get("journey_id"),
        "stratum": journey.get("stratum"),
        "seed": journey.get("seed"),
        "persona": journey.get("persona"),
        "intake": question,
        "user_input": serialise_intake(question),
        "top3": matches,
        "briefing_markdown": briefing_md,
        "answer": answer,
        "contexts": contexts,
        "programmes": jsonable(programmes),
        "models": {
            "briefing": openai_model or briefing_source,
            "briefing_source": briefing_source,
            "matching": leaver.get("matching_mode") or "hybrid_only",
            "judge": JUDGE_MODEL_DEFAULT,
        },
        "latency_ms": {
            "match": round(match_ms, 1),
            "briefing": round(briefing_ms, 1),
            "total": round(total_ms, 1),
        },
        "flags": {
            "BRIEFINGS": 1 if use_openai and briefing_source == "openai" else 0,
            "PLANS": 0,
            "JUDGE": "claude-haiku",
            "MODE": "work",
        },
        "n_matches": len(matches),
        "n_contexts": len(contexts),
        "n_rag_chunks": len(rag_hits),
        "n_programmes": len(programmes),
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="In-process WORK briefing journeys (no live HTTP).")
    parser.add_argument("--journeys", type=Path, default=JOURNEYS_PATH)
    parser.add_argument("--out-dir", type=Path, default=None)
    parser.add_argument("--offline", action="store_true", help="Deterministic offline briefings (no OpenAI).")
    parser.add_argument("--smoke", action="store_true", help="2 journeys per stratum (8 total).")
    parser.add_argument("--limit", type=int, default=None)
    parser.add_argument("--ids", nargs="*", default=None)
    parser.add_argument("--rag-top-k", type=int, default=6)
    args = parser.parse_args(argv)

    journeys_path = args.journeys if args.journeys.is_absolute() else ROOT / args.journeys
    journeys = read_jsonl(journeys_path)
    selected = _select_journeys(
        journeys,
        smoke=bool(args.smoke),
        limit=args.limit,
        ids=list(args.ids or []),
    )
    if not selected:
        raise SystemExit("No journeys selected.")

    use_openai = not bool(args.offline)
    out_dir = args.out_dir
    if out_dir is None:
        out_dir = new_run_dir()
    else:
        out_dir = out_dir if out_dir.is_absolute() else ROOT / out_dir
        out_dir.mkdir(parents=True, exist_ok=True)
        (out_dir / "figures").mkdir(exist_ok=True)

    print(f"Loaded {len(journeys)} journeys from {journeys_path.relative_to(ROOT)}")
    print(
        f"Running {len(selected)} | offline={args.offline} | "
        f"BRIEFINGS={'0' if args.offline else '1'} PLANS=0 JUDGE=claude-haiku MODE=work"
    )
    print(f"Output: {out_dir.relative_to(ROOT)}")

    companies = load_companies()
    raw_path = out_dir / "raw_journeys.jsonl"
    raw_path.write_text("", encoding="utf-8")
    records: list[dict[str, Any]] = []
    for i, journey in enumerate(selected, start=1):
        rec = run_one(
            journey,
            companies,
            use_openai=use_openai,
            rag_top_k=max(1, int(args.rag_top_k)),
        )
        records.append(rec)
        with raw_path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(jsonable(rec), ensure_ascii=False) + "\n")
            f.flush()
        src = rec["models"]["briefing_source"]
        print(
            f"  [{i}/{len(selected)}] {rec['journey_id']}  "
            f"stratum={rec['stratum']}  matches={rec['n_matches']}  "
            f"briefing={src}  {rec['latency_ms']['total']:.0f}ms",
            flush=True,
        )
    meta = {
        "generated_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "n": len(records),
        "smoke": bool(args.smoke),
        "offline": bool(args.offline),
        "journeys_path": str(journeys_path.relative_to(ROOT)),
        "strata": {s: sum(1 for r in records if r.get("stratum") == s) for s in STRATA},
        "flags": {
            "BRIEFINGS": 0 if args.offline else 1,
            "PLANS": 0,
            "JUDGE": "claude-haiku",
            "MODE": "work",
        },
        "briefing_sources": {
            src: sum(1 for r in records if r["models"]["briefing_source"] == src)
            for src in sorted({r["models"]["briefing_source"] for r in records})
        },
    }
    (out_dir / "run_meta.json").write_text(
        json.dumps(meta, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    print(f"Wrote {raw_path.relative_to(ROOT)}")
    print(f"Wrote {(out_dir / 'run_meta.json').relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
