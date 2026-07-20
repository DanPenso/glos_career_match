# Deploy guide (cheap public demo)

Recommended split:

- **Frontend:** Vercel (free) — `web/`
- **API:** small VPS (~$5–6/mo) — Docker from repo root

## 0) One-time local check

```bash
.venv\Scripts\uvicorn api.main:app --reload --port 8000
cd web && npm run dev
```

Open http://localhost:3000 and run one match.

## 1) Push to GitHub

```bash
git init
git add .
git commit -m "Prepare Gloucestershire Career Match demo for deployment"
git branch -M main
git remote add origin https://github.com/DanPenso/glos_career_match.git
git push -u origin main
```

Ensure these are committed (required at runtime):

- `app/app_data/` (masters, embeddings, FAISS, persona joblib)
- `data/taxonomy/`, `data/seed/`, `data/corpus/`
- `data/seed/verified_programmes.csv`

Do **not** commit `.env`, `data/raw/`, or `data/live/` events.

## 2) Deploy API on a VPS (Docker)

On Ubuntu 24.04:

```bash
sudo apt update
sudo apt install -y docker.io docker-compose-v2 git
sudo usermod -aG docker $USER
# log out/in once, then:
git clone https://github.com/DanPenso/glos_career_match.git
cd glos_career_match
cp .env.example .env
```

Edit `.env`:

```env
OPENAI_API_KEY=sk-...          # optional (only for opt-in AI reports)
OPENAI_MODEL=gpt-4o-mini
CORS_ORIGINS=https://your-app.vercel.app
LIVE_EVENTS_RETENTION_DAYS=180
```

Build and run:

```bash
docker compose up -d --build
curl http://127.0.0.1:8000/health
```

### HTTPS with Caddy

```bash
sudo apt install -y caddy
sudo cp deploy/Caddyfile.example /etc/caddy/Caddyfile
# edit domain, then:
sudo systemctl reload caddy
curl https://api.yourdomain.com/health
```

## 3) Deploy frontend on Vercel

1. Import GitHub repo in Vercel
2. Set **Root Directory** = `web`
3. Environment variable:
   - `NEXT_PUBLIC_API_URL` = `https://api.yourdomain.com`
4. Deploy

After first deploy, add your Vercel URL to API `CORS_ORIGINS` if needed and restart API:

```bash
docker compose up -d
```

## 4) Production smoke test

```bash
curl https://api.yourdomain.com/health
curl https://api.yourdomain.com/taxonomy
```

Browser:

- intake loads
- match returns top 3 + signal boxes
- AI reports only appear when checkbox is enabled
- `/privacy` page loads

## 5) Updating data later

On your machine:

```bash
.venv\Scripts\python scripts/build_company_masters.py
.venv\Scripts\python scripts/build_company_embeddings.py
.venv\Scripts\python scripts/build_faiss_corpus.py
.venv\Scripts\python scripts/build_persona_model.py
.venv\Scripts\python scripts/build_verified_programmes.py
git add app/app_data data/seed/verified_programmes.csv
git commit -m "Refresh runtime artefacts"
git push
```

On VPS:

```bash
git pull
docker compose up -d --build
```

## Cost snapshot

| Item | Typical cost |
|------|----------------|
| Vercel (Next.js) | $0 |
| VPS 2GB | ~$5–6/mo |
| Domain (optional) | ~$10/yr |
| OpenAI (optional, opt-in only) | usage-based |
