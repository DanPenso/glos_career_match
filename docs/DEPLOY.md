# Deploy guide (MatchKite)

Recommended split:

- **Frontend:** Vercel (free) — `web/` at **https://matchkite.com**
- **API:** small VPS or Fly.io — **https://api.matchkite.com**

GitHub repo slug is still `DanPenso/glos_career_match`; the product name is MatchKite.

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
git commit -m "Prepare MatchKite demo for deployment"
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
OPENAI_API_KEY=                 # optional (only for opt-in AI reports)
OPENAI_MODEL=gpt-4o-mini
FAA_DISPLAY_API_KEY=            # optional (Open opportunities flag)
REED_API_KEY=                   # optional (Open jobs flag)
CORS_ORIGINS=https://matchkite.com,https://www.matchkite.com
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
curl https://api.matchkite.com/health
```

## 3) Deploy frontend on Vercel

1. Import GitHub repo in Vercel
2. Set **Root Directory** = `web`
3. Environment variable:
   - `NEXT_PUBLIC_API_URL` = `https://api.matchkite.com`
4. Deploy

After first deploy, add `https://matchkite.com` (and `https://www.matchkite.com`) to API `CORS_ORIGINS` if needed and restart API:

```bash
docker compose up -d
```

## 3b) Point matchkite.com at Vercel

The domain is registered at Porkbun. It will stay on the Porkbun parking page until DNS is changed.

1. In Vercel: Project → Settings → Domains → add `matchkite.com` and `www.matchkite.com`.
2. Vercel will show the records it needs (usually A `10.0.1.2` for the apex, CNAME `cname.vercel-dns.com` for `www`).
3. In Porkbun → Domain Management → matchkite.com → DNS:
   - Turn **off** URL forwarding / parking / “coming soon”.
   - Delete the Porkbun parking A records and the `www` CNAME to `uixie.porkbun.com`.
   - Add the Vercel A / CNAME records exactly as shown.
4. Wait for DNS (often minutes, up to 48h). `https://matchkite.com` should then serve the Next.js app.
5. For the API, add `api.matchkite.com` as a CNAME to your Fly app (`glos-career-match-api.fly.dev`) or an A record to the VPS, then set `NEXT_PUBLIC_API_URL=https://api.matchkite.com` on Vercel.

Keep Porkbun nameservers (`*.ns.porkbun.com`) unless you deliberately move DNS to Vercel/Cloudflare.

## 4) Production smoke test

```bash
curl https://api.matchkite.com/health
curl https://api.matchkite.com/taxonomy
```

Browser:

- intake loads
- match returns top 3 + signal boxes
- AI reports only appear when checkbox is enabled
- `/privacy` page loads

## 5) Updating data later

On your machine:

```bash
.venv\Scripts\python scripts/02_build_company_masters.py
.venv\Scripts\python scripts/03_build_verified_programmes.py
.venv\Scripts\python scripts/04_export_rag_corpus.py
.venv\Scripts\python scripts/05_build_company_embeddings.py
.venv\Scripts\python scripts/06_build_catalogue_embeddings.py
.venv\Scripts\python scripts/07_build_faiss_corpus.py
.venv\Scripts\python scripts/08_build_persona_model.py
git add app/app_data data/seed/verified_programmes.csv data/corpus
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
| Domain (matchkite.com) | already registered at Porkbun |
| OpenAI (optional, opt-in only) | usage-based |
