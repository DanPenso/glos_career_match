# MatchKite

Live demo: **[matchkite.com](https://matchkite.com)** · API: `https://glos-career-match-api.fly.dev`

Matches school, college, and university leavers to **top 3 Gloucestershire and Bristol employers**, plus education and military pathways. Hybrid ranking, career-group personas, and opt-in RAG briefings that stay locked to verified facts.

**Status:** non-commercial live demo. Not an official careers service.  
**Licence:** [MIT](LICENSE) · **Data attribution:** [DATA.md](DATA.md) (DfE / OGL).  
**UI:** Next.js [`web/`](web/) · **API:** FastAPI [`api/`](api/).  
**Deploy:** [docs/DEPLOY.md](docs/DEPLOY.md).

## RAGAS before vs after

This is the main AI-safety result. We ran a **paired RAGAS-style assessment** on the same 200 work-mode journeys, before and after locking briefings to verified facts.

| | Protocol |
| --- | --- |
| What was scored | Work-mode employer briefing + top-3 match list |
| Design | **Paired before / after** — identical intakes, identical judge |
| n | 200 synthetic leavers (50 each: no quals, school leaver, FE, graduate) |
| Metrics | RAGAS core: **faithfulness**, **answer relevancy**, **context precision**. Domain extras: **programmes grounding**, **provenance cues** |
| Judge | Claude Haiku (`scripts/eval/score_ragas.py`). Temperature 0. **OpenAI is never the judge.** |
| Test | Wilcoxon signed-rank on paired scores; 95% bootstrap CI on the mean delta |

**Headline:** mean **faithfulness 0.34 → 0.69** (Δ **+0.35**, 95% CI 0.33–0.38; *p* < 0.0001; 188 improved, 3 worse, 9 ties).

<p align="center">
  <img src="./docs/eval/ai_safety_metrics_before_after.png" alt="RAGAS before vs after: work briefing judge scores, n=200" width="900">
</p>

*Source: same 200 WORK journeys · Haiku judge · paired Wilcoxon · run `20260902T150328Z` (baseline) vs `20260904T101453Z` (grounded pipeline).*

| Metric | Before | After | Mean Δ (95% CI) |
| --- | ---: | ---: | --- |
| Faithfulness (RAGAS) | 0.34 | 0.69 | +0.35 (0.33–0.38) |
| Answer relevancy (RAGAS) | 0.56 | 0.65 | +0.09 (0.08–0.11) |
| Context precision (RAGAS) | 0.52 | 0.74 | +0.22 (0.21–0.24) |
| Programmes grounding | 0.31 | 0.80 | +0.50 (0.46–0.53) |
| Provenance cues | 0.31 | 0.69 | +0.38 (0.35–0.40) |

**How to read it.** Faithfulness is the safety metric: did the briefing invent roles, schemes, or culture that were not in the retrieved contexts? The grey bars are the free-form LLM briefing. The blue bars are the grounded path: **Why** and **Training routes** filled in code; OpenAI may only write **What to build**; thin Companies House rows skip the model.

The original hole was **Companies House** matches (faithfulness 0.23 vs 0.38 on curated seed). After grounding, CH is 0.77 and seed is 0.65:

<p align="center">
  <img src="./docs/eval/ai_safety_faith_by_source.png" alt="RAGAS faithfulness by match source, seed vs Companies House" width="900">
</p>

This is careers guidance, not a jobs board. The judge can still dock packed top-3 employer names that never appeared in the retrieved contexts. Numbers: [`docs/eval/compare_summary.json`](docs/eval/compare_summary.json). Re-run notes are at the bottom of this README.

## Try a match (60 seconds)

1. Open [matchkite.com](https://matchkite.com) (or local, below).
2. Pick age **18–24**, a location, and a few “what you enjoy” / work-or-study tiles.
3. **Find my work matches**.
4. Optional: tick live apprenticeships and/or live jobs on reed.co.uk, then match again.

## How matching works

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

Live **Find an apprenticeship** and **Reed** listings decorate matches (pink / blue pills) and can filter the directory. They do **not** replace the ranker. Apprenticeship-titled Reed rows are dropped so FAA remains the source for those.

## How briefings stay grounded

That RAGAS lift came from product constraints, not a better prompt:

- **Why** and **Training routes** are filled in code (one overlapping interest + verified programmes only).
- OpenAI may write **What to build** only, and only when the user opts in.
- Thin Companies House / vacancy rows skip the model and use a template.
- Under-16s cannot match. Crisis-like free text is not sent to third-party models.

## Quick start

Python 3.11+, Node 20+. Copy `.env.example` → `.env` only if you want opt-in LLM reports.

**Windows (PowerShell)**

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt

# Terminal 1 — API
.\.venv\Scripts\uvicorn api.main:app --reload --port 8000

# Terminal 2 — web
cd web
copy .env.local.example .env.local
npm install
npm run dev
```

**macOS / Linux**

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

# Terminal 1 — API
uvicorn api.main:app --reload --port 8000

# Terminal 2 — web
cd web
cp .env.local.example .env.local
npm install
npm run dev
```

Open http://localhost:3000. Tests: `pip install -r requirements-dev.txt` then `pytest`.

## Project structure

```
MatchKite/
├── web/                       # Next.js product UI
├── api/                       # FastAPI matcher + briefings + live learning
├── app/app_data/              # Runtime CSVs, persona joblib, FAISS
├── src/glos_recommender/      # Matching, personas, briefing, RAG, plans
├── data/taxonomy/             # Intake + pathways + persona priors
├── data/seed/                 # Curated employers
├── data/eval/gold_set.json    # Small offline gold set
├── docs/eval/                 # Published AI-safety figures
├── scripts/                   # Canonical rebuilds
├── notebooks/                 # Research / EDA
└── archive/                   # Old Streamlit prototype
```

Do not commit `.env` or `data/live/` caches. Rebuild FAISS / personas after data changes:

```bash
python scripts/07_build_faiss_corpus.py
python scripts/08_build_persona_model.py
```

## Employer data sources

1. **Seed** (`data/seed/`) — curated Gloucestershire priority employers, plus public-sector anchors (GCHQ, CGI, …).
2. **Companies House** — free BasicCompanyData snapshot; top GL registered-office employers by accounts-category size proxy (`scripts/01_fetch_companies_house_employers.py`).
3. **Find an apprenticeship** — DfE underlying vacancies from Explore Education Statistics (OGL). Live adverts use the Display Advert API (keyed).
4. **Reed Jobseeker API** — live jobs in a Gloucester / Bristol radius (keyed; decorate + optional filter).

Full attribution → **[DATA.md](DATA.md)**.

> Contains public sector information licensed under the [Open Government Licence v3.0](https://www.nationalarchives.gov.uk/doc/open-government-licence/version/3/).  
> Source: Department for Education — Apprenticeships / Explore Education Statistics (underlying vacancies).  
> Companies House free company data product also used under OGL terms.

## Rebuild masters (optional)

Canonical product rebuilds use `scripts/` (01–08), not the notebooks.

| # | Script | Purpose |
|---|--------|---------|
| 01 | `scripts/01_fetch_companies_house_employers.py` | GL employer refresh from Companies House |
| 02 | `scripts/02_build_company_masters.py` | Seed + vacancies → `app/app_data/` masters |
| 03 | `scripts/03_build_verified_programmes.py` | Curated verified employer programmes for briefings |
| 04 | `scripts/04_export_rag_corpus.py` | Company / opportunity corpus |
| 05 | `scripts/05_build_company_embeddings.py` | MiniLM company vectors for live match blend |
| 06 | `scripts/06_build_catalogue_embeddings.py` | MiniLM course / military catalogue vectors |
| 07 | `scripts/07_build_faiss_corpus.py` | Evidence FAISS index |
| 08 | `scripts/08_build_persona_model.py` | K-Means personas joblib |

Optional when that data changes: website hygiene **2.1–2.4**, NCS course seed **6.1**, persona mix **8.1–8.3**, live FAA cache **09**, Reed jobs cache **10**.

Notebooks under `notebooks/` are research only.

## Re-run the RAGAS assessment

Not the 10-case gold set in `scripts/run_ai_eval.py`. Needs `ANTHROPIC_API_KEY`.

```bash
python scripts/eval/run_journeys.py
python scripts/eval/score_ragas.py --run-dir latest
python scripts/eval/compare_runs.py --before data/eval/runs/20260902T150328Z --after latest --docs-dir docs/eval
```
