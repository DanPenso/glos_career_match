# Evidence-backed RAG for briefings

Briefings pull short **strategy cards** paraphrased from public careers / youth-employment research, then (when `OPENAI_API_KEY` is set) ask the model to ground “What to build next” and “Your first steps this month” in those cards.

## Layout

| Path | Role |
|------|------|
| `data/corpus/evidence/strategies.yaml` | Source of truth (40 cards) |
| `data/corpus/evidence/SOURCES.md` | Citations / links |
| `data/corpus/evidence_strategies.txt` | Flat export for indexing |
| `data/corpus/howto/howto.yaml` | Practical how-to cards for plan breakdowns |
| `data/corpus/howto/SOURCES.md` | How-to citations / links |
| `data/corpus/howto_cards.txt` | Flat export for indexing |
| `src/glos_recommender/rag.py` | FAISS retrieve + keyword fallback (+ howto) |
| `scripts/build_faiss_corpus.py` | Rebuild index |

## Rebuild after editing cards

```powershell
.venv\Scripts\python scripts/build_faiss_corpus.py
```

Restart the API so it reloads the index (or use `--reload` and trigger a code touch).

## Runtime behaviour

1. `generate_briefing()` builds a query from leaver interests + company sectors.
2. `retrieve()` prefers `evidence:*` FAISS hits, fills with company/sector chunks.
3. If FAISS / MiniLM is unavailable, keyword matching over YAML still supplies strategy cards.
4. Offline briefings inject the cards’ **Do** lines into next-step sections.
5. OpenAI briefings receive STRATEGY blocks in `RETRIEVED CONTEXT` and must cite sources in plain language without inventing personal odds.

## Adding a card

Edit `strategies.yaml` with `id`, `strategy`, `source_id`, `source_label`, `strength`, `tags`, `claim`, `do`, `do_not_claim`. Re-run the build script.
