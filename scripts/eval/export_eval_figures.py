"""Slide-ready figures for a MatchKite journey eval run.

  .venv\\Scripts\\python scripts/eval/export_eval_figures.py --run-dir latest
"""

from __future__ import annotations

import argparse
import csv
import sys
from pathlib import Path

import numpy as np

_SCRIPTS_EVAL = Path(__file__).resolve().parent
if str(_SCRIPTS_EVAL) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS_EVAL))

from common import (  # noqa: E402
    ROOT,
    STRATA,
    ensure_src_path,
    read_jsonl,
    resolve_run_dir,
)

ensure_src_path()

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
STRATUM_LABELS = {
    "no_quals": "No quals",
    "school_leaver": "School leaver",
    "fe_leaver": "FE leaver",
    "graduate": "Graduate",
}


def _mean(xs: list[float]) -> float:
    return sum(xs) / len(xs) if xs else 0.0


def _load_metrics(run_dir: Path) -> list[dict[str, str]]:
    path = run_dir / "metrics.csv"
    if not path.exists():
        raise SystemExit(f"Missing {path}")
    with path.open(encoding="utf-8") as f:
        return list(csv.DictReader(f))


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


def _caption(fig, text: str) -> None:
    fig.text(0.0, -0.02, text, ha="left", va="top", fontsize=8, color="#5c5c5c")


def fig_metrics_by_stratum(rows: list[dict[str, str]], out: Path) -> None:
    import matplotlib.pyplot as plt

    metrics = list(METRIC_KEYS)
    x = np.arange(len(metrics))
    width = 0.18
    palette = ["#2f6fed", "#c45c26", "#2a9d6e", "#7a3ea8"]
    fig, ax = plt.subplots(figsize=(9.2, 4.6))
    for i, stratum in enumerate(STRATA):
        vals = [_mean([float(r[m]) for r in rows if r["stratum"] == stratum]) for m in metrics]
        ax.bar(x + (i - 1.5) * width, vals, width, label=f"{STRATUM_LABELS[stratum]} (n=50)", color=palette[i])
    ax.set_ylim(0, 1)
    ax.set_ylabel("Mean Haiku score (0–1)")
    ax.set_xticks(x)
    ax.set_xticklabels([METRIC_LABELS[m] for m in metrics])
    ax.set_title("Mean judge scores by leaver stratum")
    ax.legend(ncols=2, fontsize=9)
    _caption(fig, "Source: 200 WORK briefings · Haiku judge · 2 Sep 2026 · n=50 per stratum")
    fig.savefig(out)
    plt.close(fig)


def fig_seed_vs_ch(rows: list[dict[str, str]], out: Path) -> None:
    import matplotlib.pyplot as plt

    keys = ["faithfulness", "programmes_grounding", "provenance_cues"]
    labels = ["Faithfulness", "Programmes grounding", "Provenance cues"]
    seed = [r for r in rows if r["match_source"] == "seed"]
    ch = [r for r in rows if r["match_source"] == "companies_house"]
    seed_n, ch_n = len(seed), len(ch)
    x = np.arange(len(keys))
    width = 0.34
    fig, ax = plt.subplots(figsize=(8.2, 4.6))
    ax.bar(
        x - width / 2,
        [_mean([float(r[k]) for r in seed]) for k in keys],
        width,
        label=f"Curated seed (n={seed_n})",
        color="#2f6fed",
    )
    ax.bar(
        x + width / 2,
        [_mean([float(r[k]) for r in ch]) for k in keys],
        width,
        label=f"Companies House (n={ch_n})",
        color="#c0392b",
    )
    ax.set_ylim(0, 1)
    ax.set_ylabel("Mean Haiku score (0–1)")
    ax.set_xticks(x)
    ax.set_xticklabels(labels)
    ax.set_title("Grounding is a source problem, not a stratum problem")
    ax.legend(fontsize=9)
    _caption(fig, "Source: 200 WORK briefings · top-1 match provenance · Haiku judge · 2 Sep 2026")
    fig.savefig(out)
    plt.close(fig)


def fig_faithfulness_hist(rows: list[dict[str, str]], out: Path) -> None:
    import matplotlib.pyplot as plt

    edges = np.arange(0.1, 0.81, 0.1)
    labels = [f"{a:.1f}–{b:.1f}" for a, b in zip(edges[:-1], edges[1:])]
    seed = np.array([float(r["faithfulness"]) for r in rows if r["match_source"] == "seed"])
    ch = np.array([float(r["faithfulness"]) for r in rows if r["match_source"] == "companies_house"])
    seed_c, _ = np.histogram(seed, bins=edges)
    ch_c, _ = np.histogram(ch, bins=edges)
    x = np.arange(len(labels))
    width = 0.38
    fig, ax = plt.subplots(figsize=(8.6, 4.6))
    ax.bar(x - width / 2, seed_c, width, label=f"Curated seed (n={len(seed)})", color="#2f6fed")
    ax.bar(x + width / 2, ch_c, width, label=f"Companies House (n={len(ch)})", color="#c0392b")
    ax.set_xticks(x)
    ax.set_xticklabels(labels)
    ax.set_xlabel("Faithfulness bin (0–1)")
    ax.set_ylabel("Number of journeys")
    ax.set_title("Faithfulness distribution by top-1 match source")
    ax.legend(fontsize=9)
    n15 = int((ch <= 0.15).sum())
    _caption(
        fig,
        f"Source: 200 WORK briefings · Haiku judge · 2 Sep 2026 · {n15} of {len(ch)} CH rows score 0.15; 0 seed rows do",
    )
    fig.savefig(out)
    plt.close(fig)


def fig_drift_bars(run_dir: Path, out: Path) -> None:
    import json
    import matplotlib.pyplot as plt

    summary = json.loads((run_dir / "cluster_summary.json").read_text(encoding="utf-8"))
    fig, ax = plt.subplots(figsize=(7.2, 4.4))
    cats = ["ARI vs stratum", "Cluster purity"]
    x = np.arange(len(cats))
    width = 0.34
    ax.bar(x - width / 2, [summary["input_ari"], summary["input_purity"]], width, label="Inputs (intake)", color="#2f6fed")
    ax.bar(
        x + width / 2,
        [summary["output_ari"], summary["output_purity"]],
        width,
        label="Outputs (briefings)",
        color="#c45c26",
    )
    ax.axhline(0, color="#8a8a8a", linewidth=0.8)
    ax.set_xticks(x)
    ax.set_xticklabels(cats)
    ax.set_ylabel("Score")
    ax.set_ylim(-0.08, 0.55)
    ax.set_title("Outputs are less separable by stratum than inputs")
    ax.legend(fontsize=9)
    _caption(fig, "Source: MiniLM embeddings + K-Means k=4 · n=200 · 2 Sep 2026 · $0 Anthropic")
    fig.savefig(out)
    plt.close(fig)


def fig_pca_pair(run_dir: Path, out: Path) -> None:
    import matplotlib.pyplot as plt
    from sklearn.decomposition import PCA

    from glos_recommender.embeddings import embed_texts

    records = read_jsonl(run_dir / "raw_journeys.jsonl")
    strata = [str(r.get("stratum") or "") for r in records]
    inputs = [str(r.get("user_input") or "") for r in records]
    answers = [str(r.get("answer") or r.get("briefing_markdown") or "") for r in records]
    print("Embedding inputs and outputs for PCA pair plot…")
    x_in = embed_texts(inputs)
    x_out = embed_texts(answers)
    xy_in = PCA(n_components=2, random_state=42).fit_transform(x_in)
    xy_out = PCA(n_components=2, random_state=42).fit_transform(x_out)
    colours = {
        "no_quals": "#2f6fed",
        "school_leaver": "#c45c26",
        "fe_leaver": "#2a9d6e",
        "graduate": "#7a3ea8",
    }
    fig, axes = plt.subplots(1, 2, figsize=(10.4, 4.8))
    for ax, xy, title in (
        (axes[0], xy_in, "Inputs by stratum (PCA)"),
        (axes[1], xy_out, "Outputs by stratum (PCA)"),
    ):
        for stratum in STRATA:
            mask = np.array([s == stratum for s in strata])
            ax.scatter(
                xy[mask, 0],
                xy[mask, 1],
                s=22,
                alpha=0.75,
                c=colours[stratum],
                label=STRATUM_LABELS[stratum],
                edgecolors="none",
            )
        ax.set_title(title)
        ax.set_xlabel("PC1")
        ax.set_ylabel("PC2")
        ax.set_xticks([])
        ax.set_yticks([])
    axes[0].legend(fontsize=8, loc="best")
    fig.suptitle("Coach-voice drift: colours mix in both panels; outputs mix more", fontsize=13, fontweight="bold")
    fig.tight_layout()
    _caption(fig, "Source: local MiniLM · PCA 2D of 200 intakes vs 200 briefings · 2 Sep 2026")
    fig.savefig(out)
    plt.close(fig)


def fig_nn_lollipop(run_dir: Path, out: Path) -> None:
    import matplotlib.pyplot as plt

    report = (run_dir / "cluster_report.md").read_text(encoding="utf-8")
    pairs: list[tuple[str, float]] = []
    for line in report.splitlines():
        if not line.startswith("| j_"):
            continue
        cells = [c.strip() for c in line.strip("|").split("|")]
        if len(cells) < 5:
            continue
        try:
            cosine = float(cells[4])
        except ValueError:
            continue
        label = f"{cells[0]} ({cells[1]})  vs  {cells[2]} ({cells[3]})"
        pairs.append((label, cosine))
    if not pairs:
        return
    pairs = list(reversed(pairs))
    fig, ax = plt.subplots(figsize=(9.4, 4.8))
    y = np.arange(len(pairs))
    vals = [p[1] for p in pairs]
    ax.hlines(y, 0.93, vals, color="#c45c26", linewidth=2)
    ax.plot(vals, y, "o", color="#c45c26", markersize=7)
    ax.set_yticks(y)
    ax.set_yticklabels([p[0] for p in pairs], fontsize=8)
    ax.set_xlabel("Cosine similarity of briefing embeddings")
    ax.set_xlim(0.93, 0.98)
    ax.set_title("Nearest briefing often belongs to a different stratum")
    _caption(fig, "Source: MiniLM cosine on briefing+top-3 text · cross-stratum nearest neighbours · n=200")
    fig.savefig(out)
    plt.close(fig)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Export presentation figures for a journey eval run.")
    parser.add_argument("--run-dir", default="latest")
    args = parser.parse_args(argv)
    run_dir = resolve_run_dir(args.run_dir)
    out_dir = run_dir / "figures"
    out_dir.mkdir(parents=True, exist_ok=True)
    rows = _load_metrics(run_dir)
    _style()
    fig_metrics_by_stratum(rows, out_dir / "presentation_metrics_by_stratum.png")
    fig_seed_vs_ch(rows, out_dir / "presentation_seed_vs_ch.png")
    fig_faithfulness_hist(rows, out_dir / "presentation_faithfulness_hist.png")
    fig_drift_bars(run_dir, out_dir / "presentation_drift_ari.png")
    fig_nn_lollipop(run_dir, out_dir / "presentation_cross_stratum_nn.png")
    fig_pca_pair(run_dir, out_dir / "presentation_drift_pca_pair.png")
    print(f"Wrote presentation figures under {out_dir.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
