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
- Upstream fixture API calls are restricted to **today + tomorrow** (configurable via `SNAPSHOT_INCLUDE_TOMORROW_LIVE`) and filtered to a rolling upcoming window (default 20h); historical upstream fetches are blocked.
- A hard local API budget (`MAX_DAILY_API_CALLS`, default `40`) is enforced and resets daily.
- Strict daily cache mode fetches each date at most once/day (`SINGLE_FETCH_PER_DATE_PER_DAY=true`).
- Shared persistent cache uses Postgres when `CACHE_DATABASE_URL` is configured (recommended on Render); file JSON cache remains local fallback.
- Fixtures, standings, known logos, cache metadata, and API budget counters are persisted in the shared store.
- Snapshot flow is request-driven: if snapshot is missing or expired, backend refreshes once; otherwise it serves cached snapshot.
- Request throttling is enabled via `MIN_REQUEST_INTERVAL_SECONDS` (default `1`).
- On upstream daily-limit detection, the local budget is locked for the rest of the day to prevent repeated retry bursts.
- Configure snapshot freshness via `AUTO_SNAPSHOT_REFRESH=true`, `SNAPSHOT_TTL_MINUTES`, `SNAPSHOT_ERROR_RETRY_MINUTES`, and `SNAPSHOT_INCLUDE_TOMORROW_LIVE=true`.

Manual warm (optional):

```bash
python backend/warm_daily_cache.py  # warms today's fixtures cache + standings/logo cache
```

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
- No Render cron service is required in the default architecture.
- Set `CACHE_DATABASE_URL` in web service env vars when using Postgres shared cache.
- If `backend/ml_model_elite.json` is missing, the API still runs with heuristic fallback scoring.

