"""Paired Wilcoxon comparison helper (scripts/eval/compare_runs.py)."""

from __future__ import annotations

import csv
import sys
from pathlib import Path

import numpy as np

_EVAL = Path(__file__).resolve().parents[1] / "scripts" / "eval"
if str(_EVAL) not in sys.path:
    sys.path.insert(0, str(_EVAL))

from compare_runs import (  # noqa: E402
    compare_metric,
    compare_runs,
    holm_adjust,
    pair_rows,
)


def test_holm_adjust_monotone() -> None:
    adj = holm_adjust({"a": 0.04, "b": 0.01, "c": 0.20})
    assert adj["b"] <= adj["a"] <= adj["c"]
    assert adj["b"] == 0.03
    assert adj["a"] == 0.08
    assert adj["c"] == 0.20


def test_compare_metric_detects_paired_gain() -> None:
    before = np.array([0.2] * 20 + [0.3] * 20)
    after = before + 0.4
    row = compare_metric(before, after)
    assert row["mean_delta"] == 0.4
    assert row["p_value"] < 0.001
    assert row["n_improved"] == 40
    assert row["rank_biserial"] > 0.9
    assert row["ci95_low"] > 0.3


def test_pair_rows_and_compare_runs(tmp_path: Path) -> None:
    def _write(path: Path, faith: list[float]) -> None:
        with path.open("w", encoding="utf-8", newline="") as f:
            writer = csv.DictWriter(
                f,
                fieldnames=[
                    "journey_id",
                    "stratum",
                    "match_source",
                    "faithfulness",
                    "answer_relevancy",
                    "context_precision",
                    "programmes_grounding",
                    "provenance_cues",
                ],
            )
            writer.writeheader()
            for i, val in enumerate(faith):
                writer.writerow(
                    {
                        "journey_id": f"j_{i:03d}",
                        "stratum": "no_quals",
                        "match_source": "seed" if i < 6 else "companies_house",
                        "faithfulness": val,
                        "answer_relevancy": val,
                        "context_precision": val,
                        "programmes_grounding": val,
                        "provenance_cues": val,
                    }
                )

    before_csv = tmp_path / "before.csv"
    after_csv = tmp_path / "after.csv"
    _write(before_csv, [0.25] * 12)
    _write(after_csv, [0.70] * 12)

    def load(path: Path) -> dict[str, dict[str, str]]:
        with path.open(encoding="utf-8") as f:
            return {str(r["journey_id"]): r for r in csv.DictReader(f)}

    pairs = pair_rows(load(before_csv), load(after_csv), expected_n=12)
    summary = compare_runs(pairs)
    assert summary["n"] == 12
    assert summary["primary_significant"] is True
    assert summary["metrics"]["faithfulness"]["mean_before"] == 0.25
    assert summary["metrics"]["faithfulness"]["mean_after"] == 0.70
    assert "p_holm" in summary["metrics"]["answer_relevancy"]
    assert "seed" in summary["faithfulness_by_source"]
