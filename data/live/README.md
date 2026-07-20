# Live clustering events

Anonymous match events are appended to `leavers_events.jsonl` when someone
completes a match via the Next.js app → FastAPI `/match` endpoint.

**Stored:** interest sectors, RIASEC signals, assigned persona, optional thumbs feedback.  
**Not stored:** name, email, IP, free-text identity.

## Retrain loop

```bash
# After enough matches (e.g. 50+)
.venv\Scripts\python scripts/merge_live_into_curated.py
# or rebuild the full mix (includes live automatically):
.venv\Scripts\python scripts/curate_leaver_dataset.py

.venv\Scripts\python scripts/build_persona_model.py
```

Restart the API so it loads the new `app/app_data/persona_kmeans.joblib`.
