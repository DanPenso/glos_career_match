# MatchKite (web)

Next.js + TypeScript UI for 16–24. Talks to the FastAPI matcher in `../api`.

## Run (two terminals)

From project root:

```bash
# Terminal 1 — API (Windows: .venv\Scripts\uvicorn …)
uvicorn api.main:app --reload --port 8000

# Terminal 2 — web
cd web
cp .env.local.example .env.local   # Windows: copy .env.local.example .env.local
npm run dev
```

Open http://localhost:3000

## Stack

- Next.js App Router + TypeScript + Tailwind
- Match / taxonomy / offline briefings via `POST /match` and `GET /taxonomy`
