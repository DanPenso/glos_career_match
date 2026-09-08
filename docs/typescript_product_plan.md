# TypeScript web product plan (16–24)

Historical plan to evolve the Streamlit prototype into the MatchKite Next.js app for school and university leavers (roughly **16–24**).

**Status of this doc:** shipped. The live product is MatchKite (`web/` + `api/`). Keep this file for the original product decisions; do not treat it as a backlog.  
**Current product:** Next.js [`web/`](../web/) + FastAPI [`api/`](../api/) · MIT · see [DATA.md](../DATA.md), [LICENSE](../LICENSE).

---

## 1. Product north star

A **mobile-first careers companion**:

> Tell us a bit about you → get **3 local options** + **clear next steps**.

Not a corporate dashboard. Tone: peer coach, not school noticeboard.

**Always true**
- Options, not verdicts  
- Qualitative fit labels (not scary low %)  
- Verify live vacancies on Find an Apprenticeship / employer sites  
- Encourage talking to a real careers adviser  
- Non-commercial / open demo ethos unless product model changes later  

---

## 2. Phase 0 — Positioning & language (1–2 weeks)

### Positioning
- One promise: *Find your next step in Gloucestershire* (apprenticeship / college / uni / job).
- Audience modes (same app, different default copy):
  - Year 11–13 school leaver  
  - College / FE  
  - Uni / recent grad  
  - Early career changer (under ~25)  

### Language system (style guide)

| Do | Don’t |
|----|--------|
| “Here’s a strong option for you” | “Candidate ranked #1 (0.47)” |
| “Worth exploring” / “Often hiring” | “Low probability of hire” |
| Short sentences, second person (“you”) | Jargon (RIASEC, Jaccard, SIC) |
| Concrete verbs: apply, visit, ask, build | Vague: leverage, optimise |
| Inclusive **route** language | Identity-coded phrases (“people like you”) |

**Voice length:** closer to social captions than LinkedIn. Pathway cards: headline + max 3 bullets on mobile.

**Artefact to create:** `content/en-GB/` copy deck (JSON) so UI strings are not hard-coded in components.

---

## 3. Phase 1 — TypeScript architecture

### Recommended stack
| Layer | Choice | Why |
|-------|--------|-----|
| App | **Next.js (App Router) + TypeScript + React** | SSR/SSG, API routes, hireable stack |
| Styling | Tailwind + CSS variables (custom brand tokens) | Mobile-first; avoid generic “AI purple” defaults |
| Matcher v1 | **Python FastAPI** wrapping `glos_recommender.matching` | Fastest path; logic already proven |
| Matcher v2 | Port scoring to TypeScript | When rules stabilise |
| Data store | Postgres (e.g. Neon/Supabase) later; JSON/CSV CDN for M1 | Start simple |
| Auth | None in M1; Clerk/Auth.js later | Reduce friction for demos |
| LLM | Optional OpenAI via `/api/brief`; default offline template | Cost + privacy |

### System sketch

```
[Next.js UI 16–24]
       │
       ├─ POST /api/match  ──► [FastAPI: match_companies]
       ├─ POST /api/brief  ──► [OpenAI opt-in | offline template]
       └─ GET  /api/companies ► [DB or static export of masters]

[Offline ETL: notebooks + scripts]
  seed + public anchors + Companies House + DfE vacancies
       │
       ▼
  companies_master / opportunities_master / pathways.yaml
```

### Port order
1. Taxonomy + intake (YAML → typed JSON)  
2. Match API + 3 result cards  
3. Pathways + “How to use this advice”  
4. Offline briefing; then OpenAI opt-in  
5. Explore / search employers (not a raw spreadsheet)  

---

## 4. Phase 2 — UX for 16–24

### First viewport (landing)
- Brand / product name at hero level  
- One supporting sentence  
- One CTA: **Find my matches**  
- Full-bleed local visual (real Glos context — campus, workshop, high street)  
- No score dashboard, stats strip, or card grid in the hero  

### Core flow (mobile-first)
1. **You** — leaver type, location, interest chips (max ~5), optional work-style cards (not 6 dense radio stacks)  
2. **Matches** — 3 cards; labels only (*Strong / Good / Worth exploring*; hiring as *Often / Sometimes / Check openings*)  
3. **Deep dive** — pathway + briefing + “this month” checklist  
4. **Share / next** — screenshot-friendly summary; link to Careers Hub / Find an Apprenticeship  

### Interaction patterns
- Chip multi-select, step progress (“2 of 4”)  
- Skeleton → cards after submit  
- 2–3 purposeful motions (card enter, checklist tick)  
- Large tap targets; WCAG AA  

### Accessibility & inclusion
- Readable body type + distinctive display font (avoid default Inter-only look if brand allows)  
- Review outputs for stereotyping (who gets steered where)  
- Keep “How to use this advice” panel near results  

---

## 5. Phase 3 — Content productisation

- All user-facing strings in `content/en-GB/*.json`  
- Pathway YAML remains source of truth for routes; youth-edit summaries in content layer  
- Briefing structure stays (why / routes / opportunities / what to build / first steps) with **phone-length** caps  
- **QA loop:** Careers Hub or school adviser review + 5–8 young people sessions (“Would this make you apply or give up?”)  

---

## 6. Phase 4 — Data & trust

| Topic | Approach |
|-------|----------|
| Vacancies | Badge: past / example apprenticeships — always verify live |
| Employers | Priority curated + anchors (GCHQ, CGI, …) first; CH/vacancy long-tail in search |
| OpenAI | Opt-in; rate-limit; privacy one-liner |
| Analytics | Funnel only (start → match → open pathway → external click); no raw psych dumps |
| Licence | MIT code; OGL attribution for DfE / CH ([DATA.md](../DATA.md)) |

---

## 7. Milestones

| Milestone | Outcome |
|-----------|---------|
| **M1 Prototype** | Next.js intake + match via API; 3 cards; no auth |
| **M2 Beta** | Pathways, how-to panel, offline briefing, mobile polish |
| **M3 Pilot** | 1–2 schools / Careers Hub; feedback; copy rewrite |
| **M4 v1** | Saved journeys, share link, simple admin for seed employers |
| **M5** | Optional accounts, adviser “view as”, richer LMI |

**Rough effort:** M1–M2 in ~4–8 weeks for a solo/full-stack engineer if the matcher is wrapped (not rewritten).

---

## 8. Design decisions to lock early

1. **Python matcher behind API first** — port to TS later.  
2. **Never show discouraging absolute %** as “chance of getting a job.”  
3. **OpenAI opt-in** for school/demo contexts.  
4. **Brand direction** — Glos/youth, not generic gov SaaS or purple-glow AI.  
5. **Open-source core + hosted demo** — keep MIT; production needs hosting, monitoring, privacy notice.  

---

## 9. Success metrics (youth-appropriate)

- Intake completion rate  
- % who open at least one pathway  
- % who click an external apply / careers URL  
- Qualitative: “I know what to do this week”  

---

## 10. Mapping from today’s codebase

| Today | Future TS product |
|-------|-------------------|
| `app/app.py` Streamlit UI | Next.js App Router UI |
| `src/glos_recommender/matching.py` | FastAPI `/match` → later TS port |
| `src/glos_recommender/briefing.py` | `/api/brief` + offline template |
| `data/taxonomy/*.yaml` | Typed JSON + content deck |
| `data/seed/` + masters | ETL → DB or static snapshots |
| Encouraging labels in UI | Keep as product rule |
| `docs/glos_company_recommender.md` | Domain background; this doc = web roadmap |

---

## 11. Implementation status

**Done (M1 scaffold)**
1. `web/` — Next.js + TypeScript + Tailwind (Fraunces + DM Sans, teal/stone brand)  
2. `api/` — FastAPI `GET /health`, `GET /taxonomy`, `POST /match`  
3. Intake chips + results (encouraging labels, pathways, offline briefing)  

**Next**
4. OpenAI opt-in on `/api/brief`  
5. Psych work-style cards  
6. Shareable result card / PWA polish  
7. Pilot copy review with 16–24 + careers staff  

```bash
.venv\Scripts\uvicorn api.main:app --reload --port 8000
cd web && npm run dev
```

Streamlit demo remains available:

```bash
.venv\Scripts\streamlit run app/app.py
```
