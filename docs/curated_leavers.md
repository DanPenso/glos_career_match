# Curated leaver clustering dataset

Training data for K-Means career personas (`scripts/build_persona_model.py`).
Feature space matches `glos_recommender.personas.leaver_feature_vector`
(11 sector one-hots + 6 RIASEC one-hots).

## Layout

```text
data/
  external/                 # raw third-party downloads (often gitignored)
    SOURCES.md
    jobcannon/              # riasec.csv, career_match.csv (CC-BY-4.0)
    onet/                   # optional Interests.txt, Occupation Data.txt
  curated/
    occupation_to_sector.csv
    sector_bridge_notes.md
    leavers_train.csv       # built artefact
    leavers_holdout.csv
    CURATED_MANIFEST.json
```

## Schema (`leavers_*.csv`)

| column | type | meaning |
|--------|------|---------|
| `leaver_id` | str | stable id (`src_…`) |
| `interest_sectors` | str | pipe-separated tags from `SECTORS` |
| `target_sectors` | str | usually same as interest |
| `dominant_riasec` | str | pipe-separated top 1–2 Holland codes |
| `r`…`c` | float | optional continuous RIASEC (0–1) |
| `source` | str | `glos_priors` \| `jobcannon` \| `onet_bridge` \| … |
| `cohort` | str | `synthetic_glos` \| `adult_online` \| … |
| `sample_weight` | float | training weight |
| `persona_seed` | str | optional prior label for cluster naming |
| `split` | str | `train` \| `holdout` |

## Personas (K)

`data/taxonomy/persona_priors.yaml` defines **four** Glos personas:

1. Technical Specialist  
2. Hands-on Maker  
3. People & Care  
4. Creative / Commercial  

`build_persona_model.py` sets `k` from the number of prior names when the train set is large enough.

## Live feedback loop

Each completed match from the TypeScript web app (FastAPI `/match`) appends an
anonymous event to `data/live/leavers_events.jsonl` (sectors + RIASEC + assigned
persona). Optional UI feedback updates `persona_helpful`.

```bash
# Merge live rows into curated train (high sample_weight), then refit
.venv\Scripts\python scripts/merge_live_into_curated.py
.venv\Scripts\python scripts/build_persona_model.py
```

`curate_leaver_dataset.py` also pulls in live events when present.

## Rebuild

```bash
# Optional: download JobCannon (and try O*NET)
.venv\Scripts\python scripts/fetch_external_clustering_data.py

# Build train/holdout (works offline with priors + occupation bridge + live)
.venv\Scripts\python scripts/curate_leaver_dataset.py

# Fit live persona model (prefers curated train set)
.venv\Scripts\python scripts/build_persona_model.py
```

## Licence notes

- **JobCannon:** CC-BY-4.0 — attribute JobCannon; do not claim their microdata as Glos leavers.
- **O*NET:** US DOL / CC-BY for Interest Profiler materials — attribute when redistributing derived lists.
- **Curated bridge + Glos priors:** project MIT unless a row cites another source.
- Prefer shipping the fitted `persona_kmeans.joblib`, not redistributing raw external CSVs, if unsure.

Product copy remains: similar profiles in our model — not national labour statistics.
