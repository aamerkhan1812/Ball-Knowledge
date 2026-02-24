# Ball Knowledge

Production baseline for an AI football match recommender:

- `backend/` FastAPI service for fixture retrieval, scoring, and personalization
- `frontend/` Next.js dashboard
- `ml_pipeline/` data collection, training, and evaluation scripts

## 1) Backend Setup

```bash
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
copy backend\.env.example backend\.env
```

Set `API_SPORTS_KEY` in `backend/.env`.

Run backend:

```bash
python -m uvicorn backend.main:app --host 0.0.0.0 --port 8000
```

Health checks:

- `GET /healthz`
- `GET /readyz`

## 2) Frontend Setup

```bash
cd frontend
npm install
copy .env.example .env.local
npm run dev
```

## 3) ML Pipeline

Collect real data:

```bash
python ml_pipeline/collect_data.py
```

Train:

```bash
python ml_pipeline/train_model.py
```

Evaluate:

```bash
python ml_pipeline/evaluate_model.py
```

## 4) Production Notes

- Keep `backend/.env` out of version control.
- Use `CORS_ORIGINS` to restrict allowed frontend origins.
- Set `ENABLE_SHAP_EXPLANATIONS=false` for lower API latency.
- Persisted user preferences are stored in SQLite (`backend/data/preferences.db` by default).

## 5) Safe Mode

- Backend uses only `API_SPORTS_KEY` (single key).
- Upstream fixture API calls are restricted to **today only** (tomorrow is cache-only) and filtered to a rolling upcoming window (default 20h); historical upstream fetches are blocked.
- A hard local API budget (`MAX_DAILY_API_CALLS`, default `25`) is enforced and resets daily.
- Strict daily cache mode fetches each date at most once/day (`SINGLE_FETCH_PER_DATE_PER_DAY=true`).
- Request path is cache-only in production (`LIVE_FETCH_ON_REQUEST=false`) to prevent page refreshes from consuming API quota.
- Shared persistent cache uses Postgres when `CACHE_DATABASE_URL` is configured (recommended on Render); file JSON cache remains local fallback.
- Fixtures, standings, known logos, cache metadata, and API budget counters are persisted in the shared store.
- Request throttling is enabled via `MIN_REQUEST_INTERVAL_SECONDS` (default `1`).
- On upstream daily-limit detection, the local budget is locked for the rest of the day to prevent repeated retry bursts.

Daily warm cache:

```bash
python backend/warm_daily_cache.py  # warms today's fixtures cache + standings/logo cache
```

Recommended schedule: run twice daily in UTC (after rollover + midday).

## 6) Render Deployment (Backend + ML Inference)

This repo includes a Render blueprint at `render.yaml`.

1. Push the deployment branch:

```bash
git checkout render-deploy
git push -u origin render-deploy
```

2. In Render, create a new **Blueprint** service from this repo/branch.
3. Set `API_SPORTS_KEY` as a secret env var in Render.
4. Deploy.

Render build/runtime files:

- `render.yaml` (service definition + env vars)
- `requirements-render.txt` (production Python deps)
- `runtime.txt` (Python version)

Notes:

- Start command is `python -m uvicorn backend.main:app --host 0.0.0.0 --port $PORT`.
- Health check path is `/readyz`.
- Blueprint provisions a free Postgres cache DB and injects `CACHE_DATABASE_URL` into web + cron services.
- Two Render cron services run `python backend/warm_daily_cache.py` (`00:10 UTC` and `12:10 UTC`) to keep upcoming cache fresh without user-triggered API calls.
- If `backend/ml_model_elite.json` is missing, the API still runs with heuristic fallback scoring.

