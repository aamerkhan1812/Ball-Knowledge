from __future__ import annotations

import datetime as dt
import json
from pathlib import Path

from backend.services.api_football import FootballAPI


class FakeResponse:
    def __init__(self, payload: dict, status_code: int = 200) -> None:
        self._payload = payload
        self.status_code = status_code

    def raise_for_status(self) -> None:
        if self.status_code >= 400:
            raise RuntimeError(f"http status {self.status_code}")

    def json(self) -> dict:
        return self._payload


def _fixture(league_id: int) -> dict:
    return {
        "fixture": {"id": 800000 + league_id, "date": "2026-02-24T20:00:00+00:00"},
        "league": {
            "id": league_id,
            "name": f"League {league_id}",
            "season": 2025,
            "round": "Regular Season - 26",
        },
        "teams": {
            "home": {"name": f"Home {league_id}", "logo": None},
            "away": {"name": f"Away {league_id}", "logo": None},
        },
    }


def test_today_cache_is_used_without_upstream_calls(tmp_path: Path, monkeypatch) -> None:
    today = dt.date.today().isoformat()
    seed_payload = {today: [_fixture(39)]}

    seed_path = tmp_path / "seed.json"
    cache_path = tmp_path / "fixtures_cache.json"
    meta_path = tmp_path / "fixtures_meta.json"
    standings_path = tmp_path / "standings_cache.json"
    budget_path = tmp_path / "api_budget.json"

    seed_path.write_text(json.dumps(seed_payload), encoding="utf-8")
    meta_path.write_text("{}", encoding="utf-8")

    monkeypatch.setenv("API_SPORTS_KEY", "demo-key")
    monkeypatch.setenv("FIXTURES_SEED_PATH", str(seed_path))
    monkeypatch.setenv("FIXTURES_CACHE_PATH", str(cache_path))
    monkeypatch.setenv("FIXTURES_META_PATH", str(meta_path))
    monkeypatch.setenv("STANDINGS_CACHE_PATH", str(standings_path))
    monkeypatch.setenv("API_BUDGET_PATH", str(budget_path))

    api = FootballAPI()

    # Directly patch the refresh-needed decision to False: this is the cleanest
    # way to test "when a refresh is not needed, the cache is returned without
    # any upstream HTTP calls" — regardless of meta file state.
    monkeypatch.setattr(
        api,
        "_should_attempt_live_refresh",
        lambda date, date_value, has_cache: False,
    )

    def should_not_call(*args, **kwargs):  # noqa: ANN002, ANN003
        raise AssertionError("Upstream should not be called when today cache exists")

    monkeypatch.setattr(api.session, "get", should_not_call)

    payload = api.get_fixtures_by_date(today)
    assert payload["errors"] == {}
    assert payload.get("cached") is True
    assert len(payload["response"]) == 1




def test_historical_fetch_is_blocked_and_cache_only(tmp_path: Path, monkeypatch) -> None:
    seed_path = tmp_path / "seed.json"
    cache_path = tmp_path / "fixtures_cache.json"
    standings_path = tmp_path / "standings_cache.json"
    budget_path = tmp_path / "api_budget.json"
    seed_path.write_text("{}", encoding="utf-8")

    monkeypatch.setenv("API_SPORTS_KEY", "demo-key")
    monkeypatch.setenv("FIXTURES_SEED_PATH", str(seed_path))
    monkeypatch.setenv("FIXTURES_CACHE_PATH", str(cache_path))
    monkeypatch.setenv("STANDINGS_CACHE_PATH", str(standings_path))
    monkeypatch.setenv("API_BUDGET_PATH", str(budget_path))

    api = FootballAPI()

    def should_not_call(*args, **kwargs):  # noqa: ANN002, ANN003
        raise AssertionError("Historical upstream fetch should be blocked")

    monkeypatch.setattr(api.session, "get", should_not_call)

    payload = api.get_fixtures_by_date("2025-02-24")
    assert payload["response"] == []
    assert payload["errors"]


def test_standings_fetches_once_per_league_and_caches(tmp_path: Path, monkeypatch) -> None:
    seed_path = tmp_path / "seed.json"
    cache_path = tmp_path / "fixtures_cache.json"
    standings_path = tmp_path / "standings_cache.json"
    budget_path = tmp_path / "api_budget.json"
    seed_path.write_text("{}", encoding="utf-8")

    monkeypatch.setenv("API_SPORTS_KEY", "demo-key")
    monkeypatch.setenv("FIXTURES_SEED_PATH", str(seed_path))
    monkeypatch.setenv("FIXTURES_CACHE_PATH", str(cache_path))
    monkeypatch.setenv("STANDINGS_CACHE_PATH", str(standings_path))
    monkeypatch.setenv("API_BUDGET_PATH", str(budget_path))

    api = FootballAPI()
    call_count = {"value": 0}

    def fake_get(url, params, timeout):  # noqa: ANN001, ARG001
        call_count["value"] += 1
        return FakeResponse(
            {
                "errors": {},
                "response": [
                    {
                        "league": {
                            "standings": [
                                [
                                    {
                                        "rank": 1,
                                        "points": 80,
                                        "form": "WWWWW",
                                        "team": {"name": "Arsenal"},
                                    }
                                ]
                            ]
                        }
                    }
                ],
            }
        )

    monkeypatch.setattr(api.session, "get", fake_get)

    first = api.get_standings(39, 2025)
    second = api.get_standings(39, 2025)

    assert call_count["value"] == 1
    assert first == second
    assert "arsenal" in first


def test_window_filters_by_real_kickoff_datetime(tmp_path: Path, monkeypatch) -> None:
    seed_path = tmp_path / "seed.json"
    cache_path = tmp_path / "fixtures_cache.json"
    standings_path = tmp_path / "standings_cache.json"
    seed_path.write_text("{}", encoding="utf-8")

    monkeypatch.setenv("API_SPORTS_KEY", "demo-key")
    monkeypatch.setenv("FIXTURES_SEED_PATH", str(seed_path))
    monkeypatch.setenv("FIXTURES_CACHE_PATH", str(cache_path))
    monkeypatch.setenv("STANDINGS_CACHE_PATH", str(standings_path))

    api = FootballAPI()

    now_utc = dt.datetime.now(dt.UTC)
    in_window = {
        "fixture": {"id": 9001, "date": (now_utc + dt.timedelta(hours=2)).isoformat()},
        "league": {"id": 2, "name": "UEFA Champions League", "season": 2025},
        "teams": {
            "home": {"name": "Team A", "logo": None},
            "away": {"name": "Team B", "logo": None},
        },
    }
    out_of_window = {
        "fixture": {"id": 9002, "date": (now_utc + dt.timedelta(hours=30)).isoformat()},
        "league": {"id": 2, "name": "UEFA Champions League", "season": 2025},
        "teams": {
            "home": {"name": "Team C", "logo": None},
            "away": {"name": "Team D", "logo": None},
        },
    }

    today = dt.date.today().isoformat()
    tomorrow = (dt.date.today() + dt.timedelta(days=1)).isoformat()

    def fake_by_date(
        date: str | None = None,
        allow_live_refresh: bool = True,  # noqa: ARG001
    ):
        if date == today:
            return {"errors": {}, "response": [in_window], "source": "cache_today"}
        if date == tomorrow:
            return {"errors": {}, "response": [out_of_window], "source": "cache"}
        return {"errors": {}, "response": [], "source": "cache"}

    monkeypatch.setattr(api, "get_fixtures_by_date", fake_by_date)

    payload = api.get_fixtures_in_window(window_hours=24)

    assert payload["errors"] == {}
    assert payload["window_hours"] == 24
    assert len(payload["response"]) == 1
    assert payload["response"][0]["fixture"]["id"] == 9001
