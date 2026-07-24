# Data sources & attribution

This project is a **non-commercial live demo** for careers guidance exploration in Gloucestershire. It is not an official careers service and does not sell recommendations.

## 1. DfE Find an Apprenticeship / Explore Education Statistics

**What we use:** Underlying apprenticeship **vacancies** supporting files published with DfE Apprenticeships statistics on [Explore Education Statistics](https://explore-education-statistics.service.gov.uk/) (Find an Apprenticeship / RAAv2 content). We filter vacancies with `GL*` postcodes, aggregate by employer, and merge into company/opportunity masters.

**Licence:** Released under the [Open Government Licence v3.0](https://www.nationalarchives.gov.uk/doc/open-government-licence/version/3/) (OGL), as stated in the EES underlying-data guidance for Apprenticeships releases.

**Attribution (required by OGL):**

> Contains public sector information licensed under the Open Government Licence v3.0.  
> Source: Department for Education — Apprenticeships statistics / Explore Education Statistics (underlying vacancies data).

**How we use it:** Historical and current vacancy adverts are summarised into employer profiles and example opportunities. Many rows are **Archived** or **Closed**. They must **not** be shown as guaranteed live vacancies. Always check [Find an apprenticeship](https://www.findapprenticeship.service.gov.uk/) for current openings.

**Local storage:** Large downloads live under `data/raw/` (gitignored). Rebuild with `scripts/build_company_masters.py` or notebook `01_data_consolidation.ipynb`.

## 2. Companies House (free company data product)

**What we use:** Monthly [BasicCompanyData](http://download.companieshouse.gov.uk/en_output.html) snapshot. We keep **Active** companies whose registered-office postcode starts with `GL`, rank a top list by **accounts category** as a size proxy (GROUP/FULL/MEDIUM ahead of SMALL/MICRO — exact headcount is not in the free file), and upsert missing names into `data/seed/companies_seed.csv`.

**Script:** `scripts/fetch_companies_house_employers.py`  
**Audit output:** `data/seed/companies_house_top100.csv`  
**Raw zip:** `data/raw/companies_house_basic.zip` (gitignored)

**Licence:** Companies House free data product / Open Government Licence — attribute Companies House when redistributing derived lists.

**Limits:** Registered office ≠ all jobs in the county; national groups may be under- or over-represented; public bodies such as GCHQ often need the manual anchors file below.

## 3. Curated seed employers & opportunities

**What we use:** Hand-maintained CSVs in `data/seed/` (priority employers, example programmes), `public_sector_anchors.csv` (GCHQ, CGI, constabulary, etc.), and taxonomy YAML in `data/taxonomy/` (intake options, psych questions, pathway cards).

**Licence:** Part of this repository under the project MIT License, unless a specific file says otherwise.

**Note:** Employer names are used factually for local careers context. Inclusion does **not** imply endorsement by those organisations.

## 4. Pathway cards & sector guides

**What we use:** Editorial pathway text (`data/taxonomy/pathways.yaml`) and corpus snippets under `data/corpus/` (built/extended in notebook 05).

**Licence:** Project MIT License for original text we author. Do not paste long copyrighted careers-page copy into the corpus without permission.

## 5. Machine learning models & libraries

| Component | Role | Typical licence |
|-----------|------|-----------------|
| `sentence-transformers` / MiniLM | Local embeddings | Model card / Apache-2.0 family (see Hugging Face model card) |
| scikit-learn, pandas, numpy, FAISS, PyTorch | Runtime | Their respective OSS licences (see package metadata) |
| OpenAI API (`gpt-4o-mini` etc.) | Optional briefings | Commercial API terms — **not** open-source model weights |

Keep API keys in `.env` (never commit). Optional LLM calls send the leaver profile and company context to OpenAI when the user opts in.

## 6. Persona clustering training mix

**What we use:** A curated leaver table for K-Means personas (`data/curated/`), built by:

- Glos `persona_priors.yaml` synthetic seeds  
- Occupation → sector bridge (`data/curated/occupation_to_sector.csv`)  
- Optional [JobCannon Psychometric Response Dataset](https://github.com/PeterKolomiets/jobcannon-psychometric-dataset) RIASEC files (CC-BY-4.0) under `data/external/jobcannon/`

**Scripts:** `scripts/fetch_external_clustering_data.py` → `scripts/curate_leaver_dataset.py` → `scripts/build_persona_model.py`  
**Live loop:** anonymous match events in `data/live/` → `scripts/merge_live_into_curated.py` → rebuild persona model  
**Docs:** [docs/curated_leavers.md](docs/curated_leavers.md)

**Attribution (JobCannon):** JobCannon Psychometric Response Dataset, CC-BY-4.0 — https://jobcannon.io  

Curated rows are **not** a Gloucestershire population sample. Product copy must keep the model disclaimer.

**Live logging:** interests, work-style (RIASEC) signals, and assigned career group only — no names or contact details.
Users can opt out of anonymous logging in the intake form.

**Retention:** live-learning events are pruned automatically after a retention window
(default `180` days, configurable via `LIVE_EVENTS_RETENTION_DAYS`).

**OpenAI briefings:** optional and opt-in on intake. When enabled, leaver profile context
and matched company context are sent to OpenAI to generate briefing text.

## 7. National Careers Service course directory (education + micro-credentials)

**What we use:** Monthly [National Careers Service: course directory](https://www.gov.uk/government/publications/national-careers-service-course-directory) CSVs (live courses + providers). We filter to Gloucestershire and Bristol locations and build:

- `data/seed/courses_seed.csv` — FE/HE course matches  
- `data/seed/military_microcreds_seed.csv` — Level 3+ / short courses for PD exploration  

**Script:** `scripts/build_courses_seed_from_ncs.py`  
**Raw downloads:** `data/raw/ncs_*.csv` (gitignored)

**Licence:** [Open Government Licence v3.0](https://www.nationalarchives.gov.uk/doc/open-government-licence/version/3/)

**Attribution:**

> Contains public sector information licensed under the Open Government Licence v3.0.  
> Source: Department for Education — National Careers Service course directory.

**Limits:** Course catalogues change monthly. Rows are **not** confirmed live enrolments. For Enhanced Learning Credits (ELC), eligibility must be checked on [ELCAS](https://www.enhancedlearningcredits.com/) and with Education Staff — this demo never asserts ELC approval.

## 8. Military pathways (curated guidance)

**What we use:** Hand-maintained `data/seed/military_pathways_seed.csv` with high-level role families and links to official Armed Forces / defence careers pages.

**Licence:** Original pathway blurbs under the project MIT License. Official site content remains Crown copyright; we link out rather than republishing long recruitment copy.

**Limits:** Guidance only — **not** official recruitment advice and not an offer of employment.

## 9. What this demo is not

- Not a live vacancy board  
- Not official advice from DfE, MOD, employers, or local authorities  
- Not a guarantee of interview, apprenticeship, course place, or job outcomes  
- Not a commercial product (no referral tracking or monetised lead gen)

For licence of the **software**, see [LICENSE](LICENSE).
