# Live clustering events

Anonymous match events are appended to `leavers_events.jsonl` when someone
completes a match via the Next.js app → FastAPI `/match` endpoint.

**Stored:** interest sectors, RIASEC signals, assigned persona, optional thumbs feedback.  
**Not stored:** name, email, IP, free-text identity.

## Retrain loop

```bash
# 8.3 after enough matches (e.g. 50+)
.venv\Scripts\python scripts/08_3_merge_live_into_curated.py
# or 8.2 rebuild the full mix (includes live automatically):
.venv\Scripts\python scripts/08_2_curate_leaver_dataset.py

# 08 refit
.venv\Scripts\python scripts/08_build_persona_model.py
```

Restart the API so it loads the new `app/app_data/persona_kmeans.joblib`.

## Open apprenticeship cache

`open_apprenticeships.json` is a cache of **currently listed** Find an apprenticeship adverts (GL/BS) from the Display Advert API. It is used for the Open opportunities flag — not for clustering.

```bash
.venv\Scripts\python scripts/09_fetch_open_apprenticeships.py
```

Requires `FAA_DISPLAY_API_KEY` in `.env`. Do not commit the JSON file.
