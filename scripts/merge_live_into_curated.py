"""Merge anonymous live match events into curated leavers train/holdout.

Run after you have some matches in data/live/leavers_events.jsonl:

  .venv\\Scripts\\python scripts/merge_live_into_curated.py
  .venv\\Scripts\\python scripts/build_persona_model.py

Live rows get high sample_weight so they influence K-Means more than JobCannon.
"""

from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from glos_recommender.live_learning import (  # noqa: E402
    EVENTS_PATH,
    events_to_training_rows,
    live_event_count,
)
from glos_recommender.personas import RIASEC  # noqa: E402

CURATED = ROOT / "data" / "curated"
TRAIN_PATH = CURATED / "leavers_train.csv"
HOLD_PATH = CURATED / "leavers_holdout.csv"
HOLDOUT_FRAC = 0.15
RANDOM_SEED = 42


def _rows_to_frame(rows: list[dict]) -> pd.DataFrame:
    out = []
    for r in rows:
        scores = r.get("riasec_scores") or {}
        arr = np.array([float(scores.get(n, 0.0)) for n in RIASEC], dtype="float64")
        total = float(arr.sum())
        if total > 1e-9:
            arr = arr / total
        elif r.get("dominant_riasec"):
            arr = np.zeros(6, dtype="float64")
            for name in r["dominant_riasec"]:
                if name in RIASEC:
                    arr[RIASEC.index(name)] = 1.0
            if arr.sum() > 0:
                arr = arr / arr.sum()
        sectors = r.get("interest_sectors") or []
        if isinstance(sectors, str):
            sec_str = sectors
        else:
            sec_str = "|".join(sorted(set(sectors)))
        dom = r.get("dominant_riasec") or []
        if isinstance(dom, str):
            dom_str = dom
        else:
            dom_str = "|".join(dom)
        out.append(
            {
                "leaver_id": r["leaver_id"],
                "interest_sectors": sec_str,
                "target_sectors": sec_str,
                "dominant_riasec": dom_str,
                "r": round(float(arr[0]), 4),
                "i": round(float(arr[1]), 4),
                "a": round(float(arr[2]), 4),
                "s": round(float(arr[3]), 4),
                "e": round(float(arr[4]), 4),
                "c": round(float(arr[5]), 4),
                "source": r.get("source") or "live_intake",
                "cohort": r.get("cohort") or "live_glos",
                "sample_weight": float(r.get("sample_weight") or 4.0),
                "persona_seed": r.get("persona_seed") or "",
            }
        )
    return pd.DataFrame(out)


def main() -> None:
    n_events = live_event_count()
    print(f"Live events: {n_events} ({EVENTS_PATH})")
    live_rows = events_to_training_rows()
    if not live_rows:
        print("No usable live rows (need interest sectors). Nothing merged.")
        return

    live_df = _rows_to_frame(live_rows)
    if TRAIN_PATH.exists():
        base = pd.read_csv(TRAIN_PATH)
        # Drop previous live rows so re-merge is idempotent
        base = base[base["source"] != "live_intake"]
        train = pd.concat([base, live_df], ignore_index=True)
    else:
        train = live_df

    train = train.drop_duplicates(subset=["leaver_id"], keep="last")

    # Light holdout slice from live only
    rng = np.random.default_rng(RANDOM_SEED)
    live_idx = train.index[train["source"] == "live_intake"].to_numpy()
    hold_live = []
    if len(live_idx) >= 8:
        n_hold = max(1, int(round(len(live_idx) * HOLDOUT_FRAC)))
        hold_live = list(rng.choice(live_idx, size=n_hold, replace=False))

    hold_extra = train.loc[hold_live].copy() if hold_live else pd.DataFrame()
    train = train.drop(index=hold_live) if hold_live else train

    if HOLD_PATH.exists():
        hold = pd.read_csv(HOLD_PATH)
        hold = hold[hold["source"] != "live_intake"]
        if len(hold_extra):
            hold = pd.concat([hold, hold_extra], ignore_index=True)
    else:
        hold = hold_extra

    CURATED.mkdir(parents=True, exist_ok=True)
    train.to_csv(TRAIN_PATH, index=False)
    hold.to_csv(HOLD_PATH, index=False)

    manifest_path = CURATED / "CURATED_MANIFEST.json"
    manifest = {}
    if manifest_path.exists():
        try:
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            manifest = {}
    manifest.update(
        {
            "live_merged_utc": datetime.now(timezone.utc).isoformat(),
            "n_live_events": n_events,
            "n_live_train_rows": int((train["source"] == "live_intake").sum()),
            "n_train": int(len(train)),
            "n_holdout": int(len(hold)),
            "sources": train["source"].value_counts().to_dict(),
        }
    )
    manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")

    print(f"Merged {len(live_df)} live rows into {TRAIN_PATH}")
    print(f"Train n={len(train)}  Holdout n={len(hold)}")
    print(train["source"].value_counts().to_string())
    print("Next: .venv\\Scripts\\python scripts/build_persona_model.py")


if __name__ == "__main__":
    main()
