from __future__ import annotations

import datetime as dt
import os
from typing import Any

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

try:
    from backend.services.api_football import FootballAPI
    from backend.services.preferences_store import UserPreferenceStore
    from backend.services.scoring import MatchScorer
except ModuleNotFoundError:
    from services.api_football import FootballAPI
    from services.preferences_store import UserPreferenceStore
    from services.scoring import MatchScorer


def _parse_csv_env(name: str, default: str) -> list[str]:
    raw = os.getenv(name, default)
    values = [item.strip() for item in raw.split(",") if item.strip()]
    return values or [default]


def _normalize_warnings(raw: Any) -> list[str]:
    if isinstance(raw, list):
        return [str(item).strip() for item in raw if str(item).strip()]
    if isinstance(raw, str) and raw.strip():
        return [raw.strip()]
    return []


def _env_int(name: str, default: int, minimum: int, maximum: int) -> int:
    raw = os.getenv(name, str(default)).strip()
    try:
        value = int(raw)
    except ValueError:
        value = default
    return max(minimum, min(maximum, value))


def _env_flag(name: str, default: bool = False) -> bool:
    raw = os.getenv(name, str(default)).strip().lower()
    return raw in {"1", "true", "yes", "on"}


DEFAULT_WINDOW_HOURS = _env_int("UPCOMING_WINDOW_HOURS", default=20, minimum=1, maximum=48)
LIVE_FETCH_ON_REQUEST = _env_flag("LIVE_FETCH_ON_REQUEST", default=False)


class UserProfileResponse(BaseModel):
    favorite_team: str = ""
    prefers_goals: bool = False
    prefers_tactical: bool = False
    interaction_count: int = 0


class MatchResponse(BaseModel):
    id: int
    home_team: str
    home_logo: str | None = None
    away_team: str
    away_logo: str | None = None
    kickoff: str
    league: str
    league_logo: str | None = None
    score: int = Field(ge=0, le=100)
    probability: str
    reason: str


class MatchesResponse(BaseModel):
    status: str = "success"
    total_matches_checked: int
    user_profile: UserProfileResponse
    matches: list[MatchResponse]
    warnings: list[str] = Field(default_factory=list)
    source: str = "live"
    window_start: str | None = None
    window_end: str | None = None


app = FastAPI(
    title="Match Recommender API",
    version="1.0.0",
    description="Production baseline API for scoring top football fixtures.",
)

cors_origins = _parse_csv_env("CORS_ORIGINS", "http://localhost:3000")
allow_credentials = "*" not in cors_origins

app.add_middleware(
    CORSMiddleware,
    allow_origins=cors_origins,
    allow_credentials=allow_credentials,
    allow_methods=["GET", "OPTIONS"],
    allow_headers=["*"],
)

api = FootballAPI()
scorer = MatchScorer()
prefs_store = UserPreferenceStore(
    db_path=os.getenv("PREFERENCES_DB_PATH", "backend/data/preferences.db")
)


@app.get("/healthz")
async def healthz() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/readyz")
async def readyz() -> dict[str, Any]:
    budget = api.budget_status()
    return {
        "status": "ready",
        "model_loaded": scorer.model is not None,
        "api_key_configured": len(api.api_keys) > 0,
        "api_keys_configured": len(api.api_keys),
        "default_window_hours": api.default_window_hours,
        "api_daily_limit": budget["limit"],
        "api_daily_used": budget["used"],
        "api_daily_remaining": budget["remaining"],
        "api_budget_date": budget["date"],
        "live_fetch_on_request": LIVE_FETCH_ON_REQUEST,
        "auto_snapshot_refresh": api.auto_snapshot_refresh,
        "snapshot_ttl_minutes": api.snapshot_ttl_minutes,
        "snapshot_align_to_utc_day": api.snapshot_align_to_utc_day,
        "cache_backend": "postgres" if api.store.use_postgres else "file",
        "cache_database_configured": bool(api.cache_database_url),
    }


@app.get("/api/matches/today", response_model=MatchesResponse)
async def get_todays_matches(
    user_id: str = Query("default_user", min_length=1, max_length=128),
    date: str | None = Query(
        default=None, description="Fixture date in ISO format YYYY-MM-DD"
    ),
    window_hours: int = Query(
        default=DEFAULT_WINDOW_HOURS,
        ge=1,
        le=48,
        description="Rolling upcoming window in hours when date is omitted",
    ),
    favorite_team: str | None = Query(default=None, max_length=100),
    prefers_goals: bool | None = None,
    prefers_tactical: bool | None = None,
) -> MatchesResponse:
    # UI is team-search only; clear any stale persisted toggle preferences.
    if prefers_goals is None:
        prefers_goals = False
    if prefers_tactical is None:
        prefers_tactical = False

    if date:
        try:
            dt.date.fromisoformat(date)
        except ValueError as exc:
            raise HTTPException(
                status_code=400, detail="date must be in YYYY-MM-DD format"
            ) from exc

    fixtures = (
        api.get_fixtures_by_date(date, allow_live_refresh=LIVE_FETCH_ON_REQUEST)
        if date
        else api.get_fixtures_in_window(
            window_hours=window_hours,
            allow_live_refresh=LIVE_FETCH_ON_REQUEST,
        )
    )

    matches = fixtures.get("response", [])
    if not isinstance(matches, list):
        raise HTTPException(status_code=502, detail="Malformed fixtures payload")

    warnings = _normalize_warnings(fixtures.get("warnings"))
    raw_errors = fixtures.get("errors")
    if raw_errors and not matches:
        error_text = str(raw_errors)
        if "Historical API fetch is disabled" in error_text:
            warnings.append("Historical API fetch is disabled; using local cache only.")
        elif "Future API fetch beyond tomorrow is disabled" in error_text:
            warnings.append("Future API fetch beyond tomorrow is disabled; using local cache only.")
        else:
            warnings.append("Live fixture provider failed and no cached matches were available.")
    elif raw_errors:
        warnings.append("Live fixture provider failed for part of the data; fallback was used.")

    upstream_issues = fixtures.get("upstream_issues")
    if isinstance(upstream_issues, list) and upstream_issues:
        warnings.append(f"{len(upstream_issues)} league request(s) failed upstream.")

    deduped_warnings: list[str] = []
    seen_warnings: set[str] = set()
    for warning in warnings:
        if warning in seen_warnings:
            continue
        seen_warnings.add(warning)
        deduped_warnings.append(warning)

    user_profile = prefs_store.upsert_profile(
        user_id=user_id,
        favorite_team=favorite_team,
        prefers_goals=prefers_goals,
        prefers_tactical=prefers_tactical,
        increment_interactions=True,
    )

    scored_matches = scorer.score_matches(
        matches,
        api,
        prefs=user_profile,
        allow_live_refresh=LIVE_FETCH_ON_REQUEST,
    )
    response_status = "degraded" if not matches and deduped_warnings else "success"

    return MatchesResponse(
        status=response_status,
        total_matches_checked=len(matches),
        user_profile=UserProfileResponse(**user_profile),
        matches=[MatchResponse(**match) for match in scored_matches],
        warnings=deduped_warnings,
        source=str(fixtures.get("source", "live")),
        window_start=str(fixtures.get("window_start")) if fixtures.get("window_start") else None,
        window_end=str(fixtures.get("window_end")) if fixtures.get("window_end") else None,
    )


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("backend.main:app", host="0.0.0.0", port=8000, reload=True)

