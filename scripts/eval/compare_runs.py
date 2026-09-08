"""Paired before/after comparison of two 200-journey Haiku judge runs.

Joins metrics.csv on journey_id. Primary test: Wilcoxon signed-rank on
faithfulness. Secondary metrics use Holm-adjusted p-values. Bootstrap CI
on the mean paired difference.

  .venv\\Scripts\\python scripts/eval/compare_runs.py ^
      --before data/eval/runs/20260902T150328Z ^
      --after latest ^
      --docs-dir docs/eval
"""

from __future__ import annotations

import argparse
import csv
import json
import sys
from pathlib import Path
from typing import Any

import numpy as np

_SCRIPTS_EVAL = Path(__file__).resolve().parent
if str(_SCRIPTS_EVAL) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS_EVAL))

from common import ROOT, jsonable, resolve_run_dir  # noqa: E402

METRIC_KEYS = (
    "faithfulness",
    "answer_relevancy",
    "context_precision",
    "programmes_grounding",
    "provenance_cues",
)
METRIC_LABELS = {
    "faithfulness": "Faithfulness",
    "answer_relevancy": "Relevancy",
    "context_precision": "Context prec.",
    "programmes_grounding": "Programmes",
    "provenance_cues": "Provenance",
}
PRIMARY = "faithfulness"
BOOTSTRAP_N = 10_000
RNG_SEED = 42
EXPECTED_N = 200
DEFAULT_BEFORE = ROOT / "data" / "eval" / "runs" / "20260902T150328Z"


# Load a run's metrics.csv as journey_id -> row.
def load_metrics(run_dir: Path) -> dict[str, dict[str, str]]:
    path = run_dir / "metrics.csv"
    if not path.exists():
        raise SystemExit(f"Missing {path}")
    with path.open(encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    out: dict[str, dict[str, str]] = {}
    for row in rows:
        jid = str(row.get("journey_id") or "").strip()
        if jid:
            out[jid] = row
    return out


# Inner-join two runs on journey_id; fail if the pair count is wrong.
def pair_rows(
    before: dict[str, dict[str, str]],
    after: dict[str, dict[str, str]],
    *,
    expected_n: int = EXPECTED_N,
) -> list[tuple[dict[str, str], dict[str, str]]]:
    shared = sorted(set(before) & set(after))
    if expected_n and len(shared) != expected_n:
        raise SystemExit(
            f"Expected {expected_n} paired journey_ids, got {len(shared)} "
            f"(before={len(before)} after={len(after)})"
        )
    if not shared:
        raise SystemExit("No shared journey_ids between the two runs.")
    return [(before[jid], after[jid]) for jid in shared]


def _floats(pairs: list[tuple[dict[str, str], dict[str, str]]], metric: str) -> tuple[np.ndarray, np.ndarray]:
    a = np.array([float(b[metric]) for b, _ in pairs], dtype=float)
    b = np.array([float(aft[metric]) for _, aft in pairs], dtype=float)
    return a, b


# Holm step-down adjusted p-values (smaller is still more significant).
def holm_adjust(pvals: dict[str, float]) -> dict[str, float]:
    items = sorted(pvals.items(), key=lambda kv: kv[1])
    m = len(items)
    adj: dict[str, float] = {}
    running = 0.0
    for i, (key, p) in enumerate(items):
        value = min(1.0, (m - i) * p)
        value = max(value, running)
        adj[key] = value
        running = value
    return adj


# Matched-pairs rank-biserial: (n_pos - n_neg) / (n_pos + n_neg).
def rank_biserial(diff: np.ndarray) -> float:
    n_pos = int((diff > 0).sum())
    n_neg = int((diff < 0).sum())
    denom = n_pos + n_neg
    if denom == 0:
        return 0.0
    return (n_pos - n_neg) / denom


# Percentile bootstrap CI for the mean paired difference.
def bootstrap_mean_ci(
    diff: np.ndarray,
    *,
    n_boot: int = BOOTSTRAP_N,
    seed: int = RNG_SEED,
    alpha: float = 0.05,
) -> tuple[float, float]:
    rng = np.random.default_rng(seed)
    n = int(diff.size)
    if n == 0:
        return (0.0, 0.0)
    draws = rng.choice(diff, size=(n_boot, n), replace=True).mean(axis=1)
    lo = float(np.quantile(draws, alpha / 2))
    hi = float(np.quantile(draws, 1 - alpha / 2))
    return lo, hi


def _wilcoxon_p(diff: np.ndarray) -> tuple[float, float]:
    from scipy.stats import wilcoxon

    nonzero = diff[diff != 0]
    if nonzero.size == 0:
        return 0.0, 1.0
    if np.all(nonzero > 0) or np.all(nonzero < 0):
        # scipy can warn; still a valid extreme result
        result = wilcoxon(nonzero, zero_method="wilcox", alternative="two-sided", method="auto")
        return float(result.statistic), float(result.pvalue)
    result = wilcoxon(nonzero, zero_method="wilcox", alternative="two-sided", method="auto")
    return float(result.statistic), float(result.pvalue)


# Summarise one metric's paired before/after scores.
def compare_metric(before: np.ndarray, after: np.ndarray) -> dict[str, Any]:
    diff = after - before
    stat, p = _wilcoxon_p(diff)
    lo, hi = bootstrap_mean_ci(diff)
    return {
        "n": int(diff.size),
        "mean_before": round(float(before.mean()), 4),
        "mean_after": round(float(after.mean()), 4),
        "mean_delta": round(float(diff.mean()), 4),
        "median_delta": round(float(np.median(diff)), 4),
        "ci95_low": round(lo, 4),
        "ci95_high": round(hi, 4),
        "wilcoxon_stat": round(stat, 4),
        "p_value": float(p),
        "rank_biserial": round(rank_biserial(diff), 4),
        "n_improved": int((diff > 0).sum()),
        "n_worse": int((diff < 0).sum()),
        "n_tie": int((diff == 0).sum()),
    }


def compare_runs(
    pairs: list[tuple[dict[str, str], dict[str, str]]],
) -> dict[str, Any]:
    metrics: dict[str, Any] = {}
    for key in METRIC_KEYS:
        before, after = _floats(pairs, key)
        metrics[key] = compare_metric(before, after)

    secondary = {k: metrics[k]["p_value"] for k in METRIC_KEYS if k != PRIMARY}
    holm = holm_adjust(secondary)
    for key, adj in holm.items():
        metrics[key]["p_holm"] = float(adj)

    by_source: dict[str, Any] = {}
    for source in ("seed", "companies_house"):
        subset = [(b, a) for b, a in pairs if str(b.get("match_source") or "") == source]
        if len(subset) < 5:
            continue
        before, after = _floats(subset, PRIMARY)
        by_source[source] = compare_metric(before, after)
        by_source[source]["n_pairs"] = len(subset)

    primary = metrics[PRIMARY]
    return {
        "n": len(pairs),
        "primary": PRIMARY,
        "alpha": 0.05,
        "primary_significant": bool(primary["p_value"] < 0.05),
        "metrics": metrics,
        "faithfulness_by_source": by_source,
    }


def _style() -> None:
    import matplotlib.pyplot as plt

    plt.rcParams.update(
        {
            "figure.facecolor": "white",
            "axes.facecolor": "white",
            "axes.edgecolor": "#3d3d3d",
            "axes.labelcolor": "#1f1f1f",
            "xtick.color": "#1f1f1f",
            "ytick.color": "#1f1f1f",
            "text.color": "#1f1f1f",
            "font.size": 11,
            "axes.titlesize": 13,
            "axes.titleweight": "bold",
            "axes.labelsize": 11,
            "legend.frameon": False,
            "axes.spines.top": False,
            "axes.spines.right": False,
            "savefig.dpi": 160,
            "savefig.bbox": "tight",
        }
    )


def fig_metrics_before_after(summary: dict[str, Any], out: Path, caption: str) -> None:
    import matplotlib.pyplot as plt

    metrics = summary["metrics"]
    labels = [METRIC_LABELS[k] for k in METRIC_KEYS]
    before = [metrics[k]["mean_before"] for k in METRIC_KEYS]
    after = [metrics[k]["mean_after"] for k in METRIC_KEYS]
    x = np.arange(len(METRIC_KEYS))
    width = 0.36
    fig, ax = plt.subplots(figsize=(8.8, 4.6))
    ax.bar(x - width / 2, before, width, label="Sep 2026 baseline (n=200)", color="#8a8a8a")
    ax.bar(x + width / 2, after, width, label="After grounding work (n=200)", color="#2f6fed")
    ax.set_ylim(0, 1)
    ax.set_ylabel("Mean Haiku score (0–1)")
    ax.set_xticks(x)
    ax.set_xticklabels(labels)
    ax.set_title("Work briefings: judge scores before vs after")
    ax.legend(fontsize=9)
    fig.text(0.0, -0.02, caption, ha="left", va="top", fontsize=8, color="#5c5c5c")
    fig.savefig(out)
    plt.close(fig)


def fig_faith_by_source(summary: dict[str, Any], out: Path, caption: str) -> None:
    import matplotlib.pyplot as plt

    block = summary.get("faithfulness_by_source") or {}
    order = [k for k in ("seed", "companies_house") if k in block]
    if not order:
        return
    labels = {
        "seed": "Curated seed",
        "companies_house": "Companies House",
    }
    names = [f"{labels[k]}\n(n={block[k]['n']})" for k in order]
    before = [block[k]["mean_before"] for k in order]
    after = [block[k]["mean_after"] for k in order]
    x = np.arange(len(order))
    width = 0.36
    fig, ax = plt.subplots(figsize=(7.2, 4.6))
    ax.bar(x - width / 2, before, width, label="Sep 2026 baseline", color="#8a8a8a")
    ax.bar(x + width / 2, after, width, label="After grounding work", color="#2f6fed")
    ax.set_ylim(0, 1)
    ax.set_ylabel("Mean faithfulness (0–1)")
    ax.set_xticks(x)
    ax.set_xticklabels(names)
    ax.set_title("Faithfulness by top-match source")
    ax.legend(fontsize=9)
    fig.text(0.0, -0.02, caption, ha="left", va="top", fontsize=8, color="#5c5c5c")
    fig.savefig(out)
    plt.close(fig)


def _fmt_p(p: float) -> str:
    if p < 0.0001:
        return "<0.0001"
    if p < 0.001:
        return f"{p:.4f}"
    return f"{p:.3f}"


def write_compare_md(path: Path, summary: dict[str, Any], before_name: str, after_name: str) -> None:
    primary = summary["metrics"][PRIMARY]
    lines = [
        "# Paired 200-journey comparison",
        "",
        f"Before: `{before_name}`  ",
        f"After: `{after_name}`  ",
        f"n={summary['n']} paired journeys · primary metric **{PRIMARY}** · Wilcoxon signed-rank (two-sided).",
        "",
        f"- Mean faithfulness: {primary['mean_before']:.3f} -> {primary['mean_after']:.3f} "
        f"(delta {primary['mean_delta']:+.3f}, 95% bootstrap CI "
        f"{primary['ci95_low']:+.3f} to {primary['ci95_high']:+.3f})",
        f"- Wilcoxon p = {_fmt_p(primary['p_value'])} · rank-biserial r = {primary['rank_biserial']:.3f} · "
        f"{primary['n_improved']} improved / {primary['n_worse']} worse / {primary['n_tie']} ties",
        f"- Primary significant at α=0.05: **{'yes' if summary['primary_significant'] else 'no'}**",
        "",
        "| metric | before | after | delta | 95% CI | p (raw) | p (Holm) |",
        "| --- | --- | --- | --- | --- | --- | --- |",
    ]
    for key in METRIC_KEYS:
        row = summary["metrics"][key]
        holm = row.get("p_holm")
        holm_s = "—" if holm is None else _fmt_p(float(holm))
        lines.append(
            f"| {METRIC_LABELS[key]} | {row['mean_before']:.3f} | {row['mean_after']:.3f} | "
            f"{row['mean_delta']:+.3f} | {row['ci95_low']:+.3f}-{row['ci95_high']:+.3f} | "
            f"{_fmt_p(row['p_value'])} | {holm_s} |"
        )
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Paired Wilcoxon comparison of two journey eval runs.")
    parser.add_argument("--before", default=str(DEFAULT_BEFORE))
    parser.add_argument("--after", default="latest")
    parser.add_argument("--docs-dir", default="", help="If set, copy PNGs here for the README.")
    parser.add_argument("--expected-n", type=int, default=EXPECTED_N)
    args = parser.parse_args(argv)

    before_dir = resolve_run_dir(args.before)
    after_dir = resolve_run_dir(args.after)
    pairs = pair_rows(
        load_metrics(before_dir),
        load_metrics(after_dir),
        expected_n=max(0, int(args.expected_n)),
    )
    summary = compare_runs(pairs)
    payload = {
        "before": str(before_dir.relative_to(ROOT)),
        "after": str(after_dir.relative_to(ROOT)),
        **summary,
    }
    out_json = after_dir / "compare_summary.json"
    out_json.write_text(json.dumps(jsonable(payload), indent=2) + "\n", encoding="utf-8")
    write_compare_md(
        after_dir / "compare.md",
        summary,
        before_dir.name,
        after_dir.name,
    )

    _style()
    caption = (
        f"Source: same 200 WORK journeys · Haiku judge · paired Wilcoxon · "
        f"{before_dir.name} vs {after_dir.name}"
    )
    fig_dir = after_dir / "figures"
    fig_dir.mkdir(parents=True, exist_ok=True)
    metrics_png = fig_dir / "ai_safety_metrics_before_after.png"
    source_png = fig_dir / "ai_safety_faith_by_source.png"
    fig_metrics_before_after(summary, metrics_png, caption)
    fig_faith_by_source(summary, source_png, caption)

    docs = str(args.docs_dir or "").strip()
    if docs:
        docs_dir = Path(docs)
        if not docs_dir.is_absolute():
            docs_dir = ROOT / docs_dir
        docs_dir.mkdir(parents=True, exist_ok=True)
        import shutil

        shutil.copy2(metrics_png, docs_dir / metrics_png.name)
        if source_png.exists():
            shutil.copy2(source_png, docs_dir / source_png.name)
        (docs_dir / "compare_summary.json").write_text(
            json.dumps(jsonable(payload), indent=2) + "\n", encoding="utf-8"
        )

    print(f"Paired n={summary['n']}")
    p = summary["metrics"][PRIMARY]
    print(
        f"Faithfulness {p['mean_before']:.3f} -> {p['mean_after']:.3f} "
        f"delta={p['mean_delta']:+.3f} CI=[{p['ci95_low']:+.3f}, {p['ci95_high']:+.3f}] "
        f"p={_fmt_p(p['p_value'])}"
    )
    print(f"Wrote {out_json.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
