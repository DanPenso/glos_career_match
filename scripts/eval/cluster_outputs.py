"""MiniLM drift clustering for work briefing journeys.

Embeds answers AND inputs with models/local_minilm_model ($0 Anthropic).
PCA (or UMAP if installed) + K-Means k=4. Reports ARI/purity vs stratum.

  .venv\\Scripts\\python scripts/eval/cluster_outputs.py --run-dir latest
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

from common import (  # noqa: E402
    RANDOM_SEED,
    ROOT,
    STRATA,
    ensure_src_path,
    load_dotenv_root,
    read_jsonl,
    resolve_run_dir,
)

ensure_src_path()
load_dotenv_root()

from glos_recommender.embeddings import embed_texts  # noqa: E402


def _label_index(values: list[str]) -> tuple[np.ndarray, list[str]]:
    uniq = list(dict.fromkeys(values))
    idx = {name: i for i, name in enumerate(uniq)}
    return np.array([idx[v] for v in values], dtype=int), uniq


def _purity(y_true: np.ndarray, y_pred: np.ndarray) -> float:
    if len(y_true) == 0:
        return 0.0
    total = 0
    for cluster in np.unique(y_pred):
        mask = y_pred == cluster
        if not np.any(mask):
            continue
        counts = np.bincount(y_true[mask], minlength=int(y_true.max()) + 1)
        total += int(counts.max())
    return total / len(y_true)


def _centroids(X: np.ndarray, labels: np.ndarray) -> dict[int, np.ndarray]:
    out: dict[int, np.ndarray] = {}
    for lab in np.unique(labels):
        out[int(lab)] = X[labels == lab].mean(axis=0)
    return out


def _pairwise_distances(centroids: dict[int, np.ndarray], names: list[str]) -> list[tuple[str, str, float]]:
    rows: list[tuple[str, str, float]] = []
    keys = sorted(centroids)
    for i, a in enumerate(keys):
        for b in keys[i + 1 :]:
            va, vb = centroids[a], centroids[b]
            dist = float(np.linalg.norm(va - vb))
            na = names[a] if a < len(names) else str(a)
            nb = names[b] if b < len(names) else str(b)
            rows.append((na, nb, dist))
    return rows


def _within_variance(X: np.ndarray, labels: np.ndarray, names: list[str]) -> dict[str, float]:
    out: dict[str, float] = {}
    for lab, name in enumerate(names):
        mask = labels == lab
        if not np.any(mask):
            out[name] = 0.0
            continue
        subset = X[mask]
        centre = subset.mean(axis=0)
        out[name] = float(((subset - centre) ** 2).sum(axis=1).mean())
    return out


def _cross_stratum_nn(
    X: np.ndarray,
    ids: list[str],
    strata: list[str],
    *,
    top_n: int = 8,
) -> list[dict[str, Any]]:
    sims = X @ X.T
    np.fill_diagonal(sims, -np.inf)
    pairs: list[dict[str, Any]] = []
    n = len(ids)
    for i in range(n):
        j = int(np.argmax(sims[i]))
        if strata[i] == strata[j]:
            continue
        pairs.append(
            {
                "a": ids[i],
                "a_stratum": strata[i],
                "b": ids[j],
                "b_stratum": strata[j],
                "cosine": float(sims[i, j]),
            }
        )
    pairs.sort(key=lambda p: -p["cosine"])
    seen: set[tuple[str, str]] = set()
    unique: list[dict[str, Any]] = []
    for p in pairs:
        key = tuple(sorted((p["a"], p["b"])))
        if key in seen:
            continue
        seen.add(key)
        unique.append(p)
        if len(unique) >= top_n:
            break
    return unique


def _reduce_2d(X: np.ndarray) -> tuple[np.ndarray, str]:
    try:
        import umap

        reducer = umap.UMAP(n_components=2, random_state=RANDOM_SEED, n_neighbors=min(15, max(2, len(X) - 1)))
        return np.asarray(reducer.fit_transform(X), dtype="float64"), "umap"
    except Exception:
        from sklearn.decomposition import PCA

        n_comp = 2 if X.shape[0] > 2 else 1
        reducer = PCA(n_components=n_comp, random_state=RANDOM_SEED)
        xy = np.asarray(reducer.fit_transform(X), dtype="float64")
        if xy.shape[1] == 1:
            xy = np.column_stack([xy[:, 0], np.zeros(len(xy))])
        return xy, "pca"


def _plot(
    path: Path,
    xy: np.ndarray,
    colour_labels: list[str],
    title: str,
) -> None:
    try:
        import matplotlib.pyplot as plt
    except ImportError:
        return
    fig, ax = plt.subplots(figsize=(7.2, 5.4))
    uniq = list(dict.fromkeys(colour_labels))
    cmap = plt.get_cmap("tab10")
    for i, name in enumerate(uniq):
        mask = np.array([c == name for c in colour_labels])
        ax.scatter(xy[mask, 0], xy[mask, 1], s=36, alpha=0.85, label=name, color=cmap(i % 10))
    ax.set_title(title)
    ax.legend(frameon=False, fontsize=8)
    ax.set_xticks([])
    ax.set_yticks([])
    fig.tight_layout()
    path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(path, dpi=140)
    plt.close(fig)


def _kmeans(X: np.ndarray, k: int) -> np.ndarray:
    from sklearn.cluster import KMeans

    k = max(1, min(k, len(X)))
    model = KMeans(n_clusters=k, random_state=RANDOM_SEED, n_init=10)
    return model.fit_predict(X)


def _cluster_block(
    name: str,
    X: np.ndarray,
    ids: list[str],
    strata: list[str],
    *,
    k: int,
) -> dict[str, Any]:
    from sklearn.metrics import adjusted_rand_score

    y_true, true_names = _label_index(strata)
    pred = _kmeans(X, k)
    ari = float(adjusted_rand_score(y_true, pred)) if len(set(strata)) > 1 and len(X) > k else 0.0
    pur = float(_purity(y_true, pred))
    true_cent = _centroids(X, y_true)
    dist_rows = _pairwise_distances(true_cent, true_names)
    within = _within_variance(X, y_true, true_names)
    nn = _cross_stratum_nn(X, ids, strata)
    xy, reducer = _reduce_2d(X)
    return {
        "name": name,
        "n": int(len(X)),
        "k": int(k),
        "ari_vs_stratum": ari,
        "purity_vs_stratum": pur,
        "reducer": reducer,
        "xy": xy,
        "pred": pred,
        "centroid_distances": dist_rows,
        "within_stratum_variance": within,
        "cross_stratum_nn": nn,
        "true_names": true_names,
    }


def _fmt_dist(rows: list[tuple[str, str, float]]) -> str:
    if not rows:
        return "_none_"
    lines = ["| a | b | euclidean |", "| --- | --- | --- |"]
    for a, b, d in sorted(rows, key=lambda r: r[2]):
        lines.append(f"| {a} | {b} | {d:.3f} |")
    return "\n".join(lines)


def _write_report(
    path: Path,
    inputs: dict[str, Any],
    outputs: dict[str, Any],
) -> None:
    in_ari = inputs["ari_vs_stratum"]
    out_ari = outputs["ari_vs_stratum"]
    if out_ari + 0.02 < in_ari:
        drift = (
            "Outputs are **less separable** than inputs (ARI drop). "
            "That is the generic coach-voice drift signal: strata stay distinct in intake "
            "but briefings collapse toward a shared careers-coach register."
        )
    elif out_ari > in_ari + 0.02:
        drift = (
            "Outputs are **more separable** than inputs. Briefing language is still carrying "
            "stratum-specific content (routes, quals, match provenance) rather than a single template."
        )
    else:
        drift = (
            "Output and input separability are similar. Little extra collapse beyond the "
            "variation already present in the fixture set."
        )
    lines = [
        "# Cluster / semantic-drift report",
        "",
        "Embeddings: local MiniLM (`models/local_minilm_model`). Anthropic cost: **$0**.",
        "Clustering: K-Means k=4 on the embedding vectors. 2D plot: UMAP if installed, else PCA.",
        "",
        "## Summary",
        "",
        f"- Input ARI vs stratum: **{in_ari:.3f}** (purity {inputs['purity_vs_stratum']:.3f})",
        f"- Output ARI vs stratum: **{out_ari:.3f}** (purity {outputs['purity_vs_stratum']:.3f})",
        f"- 2D reducer: inputs `{inputs['reducer']}`, outputs `{outputs['reducer']}`",
        "",
        "### Drift note",
        "",
        drift,
        "",
        "## Input (serialised intake) within-stratum variance",
        "",
        *[f"- {k}: {v:.4f}" for k, v in inputs["within_stratum_variance"].items()],
        "",
        "## Output (briefing + top-3) within-stratum variance",
        "",
        *[f"- {k}: {v:.4f}" for k, v in outputs["within_stratum_variance"].items()],
        "",
        "## Input centroid distances",
        "",
        _fmt_dist(inputs["centroid_distances"]),
        "",
        "## Output centroid distances",
        "",
        _fmt_dist(outputs["centroid_distances"]),
        "",
        "## Cross-stratum nearest neighbours (outputs)",
        "",
    ]
    if outputs["cross_stratum_nn"]:
        lines += [
            "| a | a_stratum | b | b_stratum | cosine |",
            "| --- | --- | --- | --- | --- |",
        ]
        for p in outputs["cross_stratum_nn"]:
            lines.append(
                f"| {p['a']} | {p['a_stratum']} | {p['b']} | {p['b_stratum']} | {p['cosine']:.3f} |"
            )
    else:
        lines.append("_No cross-stratum nearest neighbours (small n or perfect separation)._")
    lines += ["", "No Gemini/plan text was included in these embeddings.", ""]
    path.write_text("\n".join(lines), encoding="utf-8")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="MiniLM cluster drift report for journey runs.")
    parser.add_argument("--run-dir", default="latest")
    parser.add_argument("--k", type=int, default=4)
    args = parser.parse_args(argv)

    run_dir = resolve_run_dir(args.run_dir)
    raw_path = run_dir / "raw_journeys.jsonl"
    if not raw_path.exists():
        raise SystemExit(f"Missing {raw_path}")
    records = read_jsonl(raw_path)
    if len(records) < 2:
        raise SystemExit("Need at least 2 journeys to cluster.")

    ids = [str(r.get("journey_id") or i) for i, r in enumerate(records)]
    strata = [str(r.get("stratum") or "unknown") for r in records]
    inputs = [str(r.get("user_input") or "") for r in records]
    answers = [str(r.get("answer") or r.get("briefing_markdown") or "") for r in records]

    print(f"Embedding {len(records)} inputs + outputs with local MiniLM…")
    X_in = embed_texts(inputs)
    X_out = embed_texts(answers)

    in_block = _cluster_block("inputs", X_in, ids, strata, k=int(args.k))
    out_block = _cluster_block("outputs", X_out, ids, strata, k=int(args.k))

    fig_dir = run_dir / "figures"
    _plot(fig_dir / "inputs_by_stratum.png", in_block["xy"], strata, "Inputs by stratum")
    _plot(
        fig_dir / "outputs_by_stratum.png",
        out_block["xy"],
        strata,
        "Outputs (briefings) by stratum",
    )
    out_cluster_names = [f"cluster_{int(c)}" for c in out_block["pred"]]
    _plot(
        fig_dir / "outputs_by_kmeans.png",
        out_block["xy"],
        out_cluster_names,
        f"Outputs K-Means k={args.k}",
    )

    assign_path = run_dir / "cluster_assignments.csv"
    with assign_path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(
            f,
            fieldnames=["journey_id", "stratum", "input_cluster", "output_cluster"],
        )
        writer.writeheader()
        for i, jid in enumerate(ids):
            writer.writerow(
                {
                    "journey_id": jid,
                    "stratum": strata[i],
                    "input_cluster": int(in_block["pred"][i]),
                    "output_cluster": int(out_block["pred"][i]),
                }
            )

    _write_report(run_dir / "cluster_report.md", in_block, out_block)
    summary = {
        "n": len(records),
        "k": int(args.k),
        "input_ari": in_block["ari_vs_stratum"],
        "output_ari": out_block["ari_vs_stratum"],
        "input_purity": in_block["purity_vs_stratum"],
        "output_purity": out_block["purity_vs_stratum"],
        "input_reducer": in_block["reducer"],
        "output_reducer": out_block["reducer"],
        "strata": {s: strata.count(s) for s in STRATA},
    }
    (run_dir / "cluster_summary.json").write_text(
        json.dumps(summary, indent=2) + "\n", encoding="utf-8"
    )
    print(f"Input  ARI={in_block['ari_vs_stratum']:.3f}  purity={in_block['purity_vs_stratum']:.3f}")
    print(f"Output ARI={out_block['ari_vs_stratum']:.3f}  purity={out_block['purity_vs_stratum']:.3f}")
    print(f"Wrote {(run_dir / 'cluster_report.md').relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
