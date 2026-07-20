# Gloucestershire Career Match

Matches school, college, and university leavers to **top 3 Gloucestershire employers**, with career-group clustering, training routes, and personalised RAG briefings.

**Status:** non-commercial **live demo** (open-source). Not an official careers service.  
**Licence:** [MIT](LICENSE) · **Data attribution:** [DATA.md](DATA.md) (includes DfE / OGL notice).  
**Product UI:** Next.js [`web/`](web/) + FastAPI [`api/`](api/).

**Deploy:** see [docs/DEPLOY.md](docs/DEPLOY.md) (Vercel frontend + Docker API on a small VPS).

## Quick start (product)

```bash
.venv\Scripts\activate
pip install -r requirements.txt

# Terminal 1 — API
.venv\Scripts\uvicorn api.main:app --reload --port 8000

# Terminal 2 — web
cd web
copy .env.local.example .env.local
npm run dev
```

Open http://localhost:3000. Optional LLM briefings: copy `.env.example` → `.env` and set `OPENAI_API_KEY`.

Rebuild FAISS / personas after data changes:

```bash
.venv\Scripts\python scripts/build_faiss_corpus.py
.venv\Scripts\python scripts/build_persona_model.py
```

## Offline research notebooks

Notebooks under `notebooks/` support exploration and ETL. **Canonical product rebuilds use `scripts/`.**

| Notebook | Role |
|----------|------|
| `00_environment_setup` | Deps + MiniLM provision |
| `01_data_consolidation` | EDA; prefer `scripts/build_company_masters.py` for masters |
| `02_feature_engineering` | Research notebook; **live embeddings via** `scripts/build_company_embeddings.py` |
| `03_clustering` | Exploratory; prefer `scripts/build_persona_model.py` |
| `04_recommender_system` | Research notebook; cosine blend now lives in `matching.py` |
| `05_rag_briefing` | Samples; prefer `scripts/build_faiss_corpus.py` |

| Script | Purpose |
|--------|---------|
| `scripts/build_verified_programmes.py` | Curated verified employer programmes for briefings |
| `scripts/build_company_masters.py` | Seed + vacancies → `app/app_data/` masters |
| `scripts/build_company_embeddings.py` | MiniLM company vectors for live match blend |
| `scripts/build_faiss_corpus.py` | Evidence FAISS index |
| `scripts/build_persona_model.py` | K-Means personas joblib |
| `scripts/curate_leaver_dataset.py` | Curated + live leavers train set |
| `scripts/merge_live_into_curated.py` | Merge anonymous web match events |
| `scripts/fetch_companies_house_employers.py` | GL employer refresh |
| `scripts/fetch_external_clustering_data.py` | JobCannon / O*NET for curation |

## Project structure

```
HigherED_ML_app/
├── web/                       # Next.js product UI
├── api/                       # FastAPI matcher + briefings + live learning
├── app/app_data/              # Runtime CSVs, persona joblib, FAISS
├── src/glos_recommender/      # Matching, personas, briefing, RAG
├── data/taxonomy/             # Intake + pathways + persona priors
├── data/seed/                 # Curated employers
├── data/curated/              # Clustering train/holdout
├── data/live/                 # Anonymous match events (gitignored)
├── scripts/                   # Canonical rebuilds
├── notebooks/                 # Research / EDA (02 & 04 parked)
├── archive/                   # Old Streamlit prototype
└── docs/
```

Archived Streamlit UI: [`archive/streamlit_app.py`](archive/streamlit_app.py) (optional; not the product path).

## Employer data sources

1. **Seed** (`data/seed/`) — curated Gloucestershire priority employers (`priority_employer=1`), plus public-sector anchors (GCHQ, CGI, …).
2. **Companies House** — free BasicCompanyData snapshot; top GL registered-office employers by accounts-category size proxy (`scripts/fetch_companies_house_employers.py`).
3. **Find an Apprenticeship** — DfE underlying vacancies file from Explore Education Statistics (OGL). `scripts/build_company_masters.py` filters `GL*` postcodes, aggregates by employer, and merges (seed wins on name clash). The zip is stored under `data/raw/` (gitignored).

Full attribution → **[DATA.md](DATA.md)**.

> Contains public sector information licensed under the [Open Government Licence v3.0](https://www.nationalarchives.gov.uk/doc/open-government-licence/version/3/).  
> Source: Department for Education — Apprenticeships / Explore Education Statistics (underlying vacancies).  
> Companies House free company data product also used under OGL terms.

```bash
.venv\Scripts\python scripts/fetch_companies_house_employers.py --top 100 --rebuild
.venv\Scripts\python scripts/build_company_masters.py
.venv\Scripts\python scripts/build_company_embeddings.py
.venv\Scripts\python scripts/build_faiss_corpus.py
.venv\Scripts\python scripts/build_persona_model.py
```

Restart the API after rebuilding so it reloads masters / embeddings / FAISS / persona model.

## Matching score (live API)

```
hybrid =
  0.35 * sector_overlap
+ 0.20 * entry_route_fit
+ 0.20 * text_overlap
+ 0.15 * psych_role_fit
+ 0.10 * hiring_signal

# when app/app_data/company_embeddings.npz exists:
final_score = 0.7 * hybrid + 0.3 * cosine_sim(MiniLM)
```

Build embeddings after refreshing company masters:

```bash
.venv\Scripts\python scripts/build_company_embeddings.py
```

Restart the API so it reloads the matrix. Without the `.npz` file, matching falls back to hybrid-only.
