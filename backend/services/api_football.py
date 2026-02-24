from __future__ import annotations

import datetime as dt
import os
import time
from typing import Any

import requests
from dotenv import load_dotenv
from loguru import logger
try:
    from backend.services.persistent_store import PersistentStore
except ModuleNotFoundError:
    from services.persistent_store import PersistentStore

env_path = os.path.join(os.path.dirname(__file__), "..", ".env")
load_dotenv(env_path)


def _env_flag(name: str, default: bool = False) -> bool:
    raw = os.getenv(name, str(default)).strip().lower()
    return raw in {"1", "true", "yes", "on"}


def _env_int(name: str, default: int, minimum: int, maximum: int) -> int:
    raw = os.getenv(name, str(default)).strip()
    try:
        value = int(raw)
    except ValueError:
        value = default
    return max(minimum, min(maximum, value))


def _local_now() -> dt.datetime:
    return dt.datetime.now().astimezone()


def _local_today_iso() -> str:
    return _local_now().date().isoformat()


def _dedupe_text(items: list[str]) -> list[str]:
    deduped: list[str] = []
    seen: set[str] = set()
    for item in items:
        value = str(item).strip()
        if not value or value in seen:
            continue
        seen.add(value)
        deduped.append(value)
    return deduped


def _norm_key(value: Any) -> str:
    return str(value or "").strip().lower()


def _clean_logo(value: Any) -> str:
    text = str(value or "").strip()
    if not text:
        return ""
    if text.lower().startswith(("http://", "https://")):
        return text
    return ""


def _summarize_live_error(raw_error: str) -> str:
    text = str(raw_error or "").strip()
    if not text:
        return "Upstream live refresh failed."

    lowered = text.lower()
    reasons: list[str] = []

    if "request limit" in lowered or "reached the request limit" in lowered:
        reasons.append("API daily request limit reached")

    if "daily api call budget reached" in lowered:
        reasons.append("Local daily API safety budget reached")

    if "free plans do not have access to this date" in lowered:
        reasons.append("Free-plan date window blocked")

    if "historical api fetch is disabled" in lowered:
        reasons.append("Historical fetch blocked by policy")

    if "future api fetch beyond tomorrow is disabled" in lowered:
        reasons.append("Future fetch beyond tomorrow blocked by policy")

    if not reasons:
        return "Upstream live refresh failed."

    return f"{', '.join(_dedupe_text(reasons))}."


def _is_daily_limit_error_text(raw_error: str) -> bool:
    text = str(raw_error or "").strip().lower()
    if not text:
        return False
    return (
        "request limit" in text
        or "daily api call budget reached" in text
        or "429" in text
        or "too many requests" in text
    )


class FootballAPI:
    def __init__(self) -> None:
        self.api_key = os.getenv("API_SPORTS_KEY", "").strip()
        # Safe-mode policy: only one key is used.
        self.api_keys = [self.api_key] if self.api_key else []

        self.timeout_seconds = float(os.getenv("REQUEST_TIMEOUT_SECONDS", "10"))
        self.min_request_interval_seconds = float(os.getenv("MIN_REQUEST_INTERVAL_SECONDS", "1"))
        self.default_window_hours = _env_int("UPCOMING_WINDOW_HOURS", default=20, minimum=1, maximum=48)
        self.auto_snapshot_refresh = _env_flag("AUTO_SNAPSHOT_REFRESH", default=True)
        self.snapshot_ttl_minutes = _env_int(
            "SNAPSHOT_TTL_MINUTES", default=1440, minimum=5, maximum=1440
        )
        self.snapshot_error_retry_minutes = _env_int(
            "SNAPSHOT_ERROR_RETRY_MINUTES", default=60, minimum=1, maximum=240
        )
        self.snapshot_align_to_utc_day = _env_flag(
            "SNAPSHOT_ALIGN_TO_UTC_DAY", default=True
        )
        self.snapshot_include_tomorrow_live = _env_flag(
            "SNAPSHOT_INCLUDE_TOMORROW_LIVE", default=True
        )
        self.min_window_matches = _env_int("MIN_WINDOW_MATCHES", default=4, minimum=1, maximum=20)
        self.window_extension_hours = _env_int("WINDOW_EXTENSION_HOURS", default=4, minimum=0, maximum=24)
        self.single_fetch_per_date_per_day = _env_flag(
            "SINGLE_FETCH_PER_DATE_PER_DAY", default=True
        )
        self.max_daily_api_calls = _env_int("MAX_DAILY_API_CALLS", default=40, minimum=1, maximum=500)
        self.fixture_cache_refresh_minutes = _env_int(
            "FIXTURE_CACHE_REFRESH_MINUTES", default=90, minimum=5, maximum=720
        )
        self.fixture_error_retry_minutes = _env_int(
            "FIXTURE_ERROR_RETRY_MINUTES", default=30, minimum=5, maximum=240
        )
        self.filter_target_leagues = _env_flag("FILTER_TARGET_LEAGUES", default=True)

        self.fixtures_cache_path = os.path.normpath(
            os.getenv(
                "FIXTURES_CACHE_PATH",
                os.path.join(os.path.dirname(__file__), "..", "data", "fixtures_cache.json"),
            )
        )
        self.fixtures_seed_path = os.path.normpath(
            os.getenv(
                "FIXTURES_SEED_PATH",
                os.path.join(os.path.dirname(__file__), "..", "data", "fixtures_seed.json"),
            )
        )
        self.fixtures_meta_path = os.path.normpath(
            os.getenv(
                "FIXTURES_META_PATH",
                os.path.join(os.path.dirname(__file__), "..", "data", "fixtures_cache_meta.json"),
            )
        )
        self.standings_cache_path = os.path.normpath(
            os.getenv(
                "STANDINGS_CACHE_PATH",
                os.path.join(os.path.dirname(__file__), "..", "data", "standings_cache.json"),
            )
        )
        self.logo_cache_path = os.path.normpath(
            os.getenv(
                "LOGO_CACHE_PATH",
                os.path.join(os.path.dirname(__file__), "..", "data", "logo_cache.json"),
            )
        )
        self.api_budget_path = os.path.normpath(
            os.getenv(
                "API_BUDGET_PATH",
                os.path.join(os.path.dirname(__file__), "..", "data", "api_budget.json"),
            )
        )
        self.cache_database_url = os.getenv(
            "CACHE_DATABASE_URL",
            os.getenv("DATABASE_URL", ""),
        ).strip()
        self.store = PersistentStore(self.cache_database_url)

        self.base_url = "https://v3.football.api-sports.io"
        self.session = requests.Session()
        session_headers = {"x-rapidapi-host": "v3.football.api-sports.io"}
        if self.api_key:
            session_headers["x-apisports-key"] = self.api_key
        self.session.headers.update(session_headers)

        self.target_leagues = [
            2,  # UEFA Champions League
            39,  # Premier League
            140,  # La Liga
            78,  # Bundesliga
            135,  # Serie A
        ]
        self.league_names = {
            2: "UEFA Champions League",
            39: "Premier League",
            140: "La Liga",
            78: "Bundesliga",
            135: "Serie A",
        }

        self._last_request_monotonic = 0.0
        self.standings_cache: dict[str, dict[str, dict[str, Any]]] = {}
        self.standings_cache_date = ""
        self.fixtures_cache: dict[str, list[dict[str, Any]]] = {}
        self.fixtures_meta: dict[str, dict[str, Any]] = {}
        self.logo_cache: dict[str, dict[str, str]] = {
            "leagues_by_id": {},
            "leagues_by_name": {},
            "teams_by_id": {},
            "teams_by_name": {},
        }
        self.api_budget_date = _local_today_iso()
        self.api_call_count = 0
        self.force_refresh_dates: set[str] = set()
        self.needs_daily_standings_warm = True
        self.snapshot_meta_key = "__window_snapshot__"

        self._load_fixtures_cache()
        self._load_fixtures_meta()
        self._load_standings_cache()
        self._load_logo_cache()
        self._load_api_budget()
        self.needs_daily_standings_warm = not self._has_full_target_standings_for_today()

        if self.store.use_postgres:
            logger.info("Using Postgres shared cache backend.")

    def _throttle(self) -> None:
        if self.min_request_interval_seconds <= 0:
            return

        now = time.monotonic()
        elapsed = now - self._last_request_monotonic
        wait_for = self.min_request_interval_seconds - elapsed
        if wait_for > 0:
            time.sleep(wait_for)

        self._last_request_monotonic = time.monotonic()

    @staticmethod
    def _has_upstream_errors(upstream_errors: Any) -> bool:
        if isinstance(upstream_errors, dict):
            return any(bool(value) for value in upstream_errors.values())
        return bool(upstream_errors)

    @staticmethod
    def _format_upstream_errors(upstream_errors: Any) -> str:
        if isinstance(upstream_errors, dict):
            non_empty = {key: value for key, value in upstream_errors.items() if value}
            return str(non_empty)
        return str(upstream_errors)

    @staticmethod
    def _parse_iso_datetime(value: Any) -> dt.datetime | None:
        text = str(value or "").strip()
        if not text:
            return None

        iso_text = text.replace("Z", "+00:00")
        try:
            parsed = dt.datetime.fromisoformat(iso_text)
        except ValueError:
            return None

        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=dt.UTC)
        return parsed.astimezone(dt.UTC)

    def _request_json_once(
        self, path: str, params: dict[str, Any]
    ) -> tuple[dict[str, Any] | None, str | None]:
        if not self.api_key:
            return None, "API_SPORTS_KEY is not configured"

        if not self._consume_api_budget():
            return (
                None,
                f"Daily API call budget reached ({self.api_call_count}/{self.max_daily_api_calls})",
            )

        self._throttle()

        try:
            response = self.session.get(
                f"{self.base_url}/{path}",
                params=params,
                timeout=self.timeout_seconds,
            )
            response.raise_for_status()
            payload = response.json()
        except (requests.exceptions.RequestException, ValueError) as exc:
            error_text = str(exc)
            if _is_daily_limit_error_text(error_text):
                self._lock_api_budget_for_today()
            return None, error_text

        upstream_errors = payload.get("errors")
        if self._has_upstream_errors(upstream_errors):
            formatted_error = self._format_upstream_errors(upstream_errors)
            if _is_daily_limit_error_text(formatted_error):
                self._lock_api_budget_for_today()
            return None, formatted_error

        return payload, None

    def _load_fixtures_cache(self, silent: bool = False) -> None:
        try:
            data = self.store.load_map(
                "fixtures_cache",
                file_paths=[self.fixtures_seed_path, self.fixtures_cache_path],
            )
        except Exception as exc:
            logger.warning(f"Failed to load fixtures cache from persistent store: {exc}")
            return

        loaded_dates = 0
        cache: dict[str, list[dict[str, Any]]] = {}
        if isinstance(data, dict):
            for key, value in data.items():
                if isinstance(value, list):
                    cache[str(key)] = value
                    loaded_dates += 1

        self.fixtures_cache = cache
        if loaded_dates > 0 and not silent:
            logger.info(f"Loaded fixture cache entries for {loaded_dates} date keys.")

    def _save_fixtures_cache(self) -> None:
        try:
            self.store.save_map(
                "fixtures_cache",
                self.fixtures_cache,
                file_path=self.fixtures_cache_path,
            )
        except Exception as exc:
            logger.warning(f"Failed to persist fixtures cache: {exc}")

    def _load_fixtures_meta(self, silent: bool = False) -> None:
        try:
            data = self.store.load_map(
                "fixtures_meta",
                file_paths=[self.fixtures_meta_path],
            )
        except Exception as exc:
            logger.warning(f"Failed to load fixtures meta from persistent store: {exc}")
            return

        meta_map: dict[str, dict[str, Any]] = {}
        if isinstance(data, dict):
            for date_key, meta in data.items():
                if isinstance(meta, dict):
                    meta_map[str(date_key)] = meta
        self.fixtures_meta = meta_map

        if self.fixtures_meta and not silent:
            logger.info(f"Loaded fixtures meta entries for {len(self.fixtures_meta)} date keys.")

    def _save_fixtures_meta(self) -> None:
        try:
            self.store.save_map(
                "fixtures_meta",
                self.fixtures_meta,
                file_path=self.fixtures_meta_path,
            )
        except Exception as exc:
            logger.warning(f"Failed to persist fixtures meta: {exc}")

    def _load_logo_cache(self, silent: bool = False) -> None:
        try:
            data = self.store.load_map(
                "logo_cache",
                file_paths=[self.logo_cache_path],
            )
        except Exception as exc:
            logger.warning(f"Failed to load logo cache from persistent store: {exc}")
            return

        if not isinstance(data, dict):
            return

        loaded_logo_cache: dict[str, dict[str, str]] = {
            "leagues_by_id": {},
            "leagues_by_name": {},
            "teams_by_id": {},
            "teams_by_name": {},
        }
        for key in ["leagues_by_id", "leagues_by_name", "teams_by_id", "teams_by_name"]:
            bucket = data.get(key)
            if isinstance(bucket, dict):
                loaded_logo_cache[key] = {
                    str(k): str(v)
                    for k, v in bucket.items()
                    if str(k).strip() and _clean_logo(v)
                }

        self.logo_cache = loaded_logo_cache
        total_logo_keys = sum(len(bucket) for bucket in self.logo_cache.values())
        if total_logo_keys > 0 and not silent:
            logger.info(f"Loaded logo cache entries: {total_logo_keys}.")

    def _save_logo_cache(self) -> None:
        try:
            self.store.save_map(
                "logo_cache",
                self.logo_cache,
                file_path=self.logo_cache_path,
            )
        except Exception as exc:
            logger.warning(f"Failed to persist logo cache: {exc}")

    def _load_api_budget(self) -> None:
        payload = self.store.load_budget_payload(self.api_budget_path)
        if not isinstance(payload, dict):
            self._mark_rollover_refresh_targets()
            self.api_budget_date = _local_today_iso()
            self.api_call_count = 0
            self._save_api_budget()
            return

        date_text = str(payload.get("date", "")).strip()
        count_raw = payload.get("count", 0)
        try:
            count = int(count_raw)
        except (TypeError, ValueError):
            count = 0

        today = _local_today_iso()
        if date_text == today:
            self.api_budget_date = today
            self.api_call_count = self._sanitize_budget_count(count)
            # Persist corrected count if file contained an out-of-range value.
            if self.api_call_count != count:
                self._save_api_budget()
            return

        self.api_budget_date = today
        self.api_call_count = 0
        self._mark_rollover_refresh_targets()
        self._save_api_budget()

    def _sanitize_budget_count(self, count: int) -> int:
        return max(0, min(self.max_daily_api_calls, int(count)))

    def _mark_rollover_refresh_targets(self) -> None:
        local_today = _local_now().date()
        local_tomorrow = local_today + dt.timedelta(days=1)
        self.force_refresh_dates.update(
            {local_today.isoformat(), local_tomorrow.isoformat()}
        )
        self.needs_daily_standings_warm = True

    def _sync_api_budget_from_disk(self) -> None:
        if self.store.use_postgres:
            count = self.store.get_budget_count_for_date(
                self.api_budget_date,
                self.api_budget_path,
            )
            safe_shared_count = self._sanitize_budget_count(count)
            safe_local_count = self._sanitize_budget_count(self.api_call_count)
            self.api_call_count = max(safe_local_count, safe_shared_count)
            return

        payload = self.store.load_budget_payload(self.api_budget_path)
        if not isinstance(payload, dict):
            return

        date_text = str(payload.get("date", "")).strip()
        count_raw = payload.get("count", 0)
        try:
            count = int(count_raw)
        except (TypeError, ValueError):
            return

        if date_text == self.api_budget_date:
            safe_disk_count = self._sanitize_budget_count(count)
            safe_local_count = self._sanitize_budget_count(self.api_call_count)
            self.api_call_count = max(safe_local_count, safe_disk_count)

    def _save_api_budget(self) -> None:
        self.api_call_count = self._sanitize_budget_count(self.api_call_count)
        payload = {
            "date": self.api_budget_date,
            "count": self.api_call_count,
            "max_daily_api_calls": self.max_daily_api_calls,
        }
        self.store.save_budget_payload(payload, self.api_budget_path)

    def _lock_api_budget_for_today(self) -> None:
        self._refresh_api_budget_if_needed()
        locked_count = self.store.lock_budget(
            self.api_budget_date,
            self.max_daily_api_calls,
            self.api_budget_path,
        )
        self.api_call_count = self._sanitize_budget_count(locked_count)

    def _refresh_api_budget_if_needed(self) -> None:
        today = _local_today_iso()
        if self.api_budget_date == today:
            return
        self.api_budget_date = today
        self.api_call_count = self._sanitize_budget_count(
            self.store.get_budget_count_for_date(today, self.api_budget_path)
        )
        self.standings_cache.clear()
        self.standings_cache_date = ""
        self._mark_rollover_refresh_targets()
        if not self.store.use_postgres:
            self._save_api_budget()

    def _consume_api_budget(self) -> bool:
        self._refresh_api_budget_if_needed()
        self._sync_api_budget_from_disk()
        allowed, count = self.store.consume_budget(
            self.api_budget_date,
            self.max_daily_api_calls,
            self.api_budget_path,
        )
        self.api_call_count = self._sanitize_budget_count(count)
        return bool(allowed)

    def budget_status(self) -> dict[str, Any]:
        self._refresh_api_budget_if_needed()
        self._sync_api_budget_from_disk()
        self.api_call_count = self._sanitize_budget_count(self.api_call_count)
        remaining = max(0, self.max_daily_api_calls - self.api_call_count)
        return {
            "date": self.api_budget_date,
            "used": self.api_call_count,
            "limit": self.max_daily_api_calls,
            "remaining": remaining,
        }

    def _remaining_api_budget(self) -> int:
        status = self.budget_status()
        return int(status.get("remaining", 0) or 0)

    def _target_standings_cache_key(self, league_id: int) -> str:
        season = self._season_for_date(_local_now().date())
        return f"{league_id}_{season}"

    def _has_full_target_standings_for_today(self) -> bool:
        today_iso = _local_today_iso()
        if self.standings_cache_date != today_iso:
            return False

        for league_id in self.target_leagues:
            cache_key = self._target_standings_cache_key(league_id)
            if cache_key not in self.standings_cache:
                return False
        return True

    def _warm_target_standings_once(self) -> None:
        if not self.needs_daily_standings_warm:
            return

        if self._remaining_api_budget() < len(self.target_leagues):
            return

        season = self._season_for_date(_local_now().date())
        for league_id in self.target_leagues:
            cache_key = f"{league_id}_{season}"
            if self.standings_cache_date == _local_today_iso() and cache_key in self.standings_cache:
                continue
            self.get_standings(league_id, season, allow_live_refresh=True)

        self.needs_daily_standings_warm = not self._has_full_target_standings_for_today()

    def _enrich_cached_dates_with_logo_cache(self, dates: list[str]) -> None:
        changed = False
        for date in dates:
            rows = self.fixtures_cache.get(date)
            if not isinstance(rows, list) or not rows:
                continue
            if self._enrich_fixture_rows_with_logo_cache(rows):
                changed = True

        if changed:
            self._save_fixtures_cache()

    def _refresh_shared_cache_state(self) -> None:
        if not self.store.use_postgres:
            return

        self._load_fixtures_cache(silent=True)
        self._load_fixtures_meta(silent=True)
        self._load_standings_cache(silent=True)
        self._load_logo_cache(silent=True)
        today = _local_today_iso()
        self.api_budget_date = today
        self.api_call_count = self._sanitize_budget_count(
            self.store.get_budget_count_for_date(today, self.api_budget_path)
        )

    def _load_standings_cache(self, silent: bool = False) -> None:
        try:
            data = self.store.load_map(
                "standings_cache",
                file_paths=[self.standings_cache_path],
            )
        except Exception as exc:
            logger.warning(f"Failed to load standings cache from persistent store: {exc}")
            return

        if not isinstance(data, dict):
            return

        cache_date = str(data.get("_cache_date", "")).strip()
        leagues = data.get("leagues", {})
        if cache_date != _local_today_iso() or not isinstance(leagues, dict):
            self.standings_cache.clear()
            self.standings_cache_date = ""
            return

        loaded = 0
        cache: dict[str, dict[str, Any]] = {}
        for cache_key, team_rows in leagues.items():
            if isinstance(team_rows, dict):
                cache[str(cache_key)] = team_rows
                loaded += 1

        self.standings_cache = cache
        if loaded > 0:
            self.standings_cache_date = cache_date
            if not silent:
                logger.info(f"Loaded standings cache entries for {loaded} league keys.")

    def _save_standings_cache(self) -> None:
        payload = {
            "_cache_date": self.standings_cache_date,
            "leagues": self.standings_cache,
        }
        try:
            self.store.save_map(
                "standings_cache",
                payload,
                file_path=self.standings_cache_path,
            )
        except Exception as exc:
            logger.warning(f"Failed to persist standings cache: {exc}")

    def _index_logo(
        self,
        bucket: str,
        key: str,
        logo: str,
    ) -> bool:
        if not key or not logo:
            return False

        current = self.logo_cache.get(bucket, {})
        if not isinstance(current, dict):
            current = {}
            self.logo_cache[bucket] = current

        if current.get(key) == logo:
            return False
        current[key] = logo
        return True

    def _update_logo_cache_from_rows(self, response_rows: list[dict[str, Any]]) -> bool:
        changed = False
        for match in response_rows:
            league = match.get("league", {})
            league_id = str(league.get("id", "")).strip()
            league_name = _norm_key(league.get("name"))
            league_logo = _clean_logo(league.get("logo"))
            if league_logo:
                changed = self._index_logo("leagues_by_id", league_id, league_logo) or changed
                changed = self._index_logo("leagues_by_name", league_name, league_logo) or changed

            teams = match.get("teams", {})
            for side in ["home", "away"]:
                team = teams.get(side, {})
                team_id = str(team.get("id", "")).strip()
                team_name = _norm_key(team.get("name"))
                team_logo = _clean_logo(team.get("logo"))
                if not team_logo:
                    continue
                changed = self._index_logo("teams_by_id", team_id, team_logo) or changed
                changed = self._index_logo("teams_by_name", team_name, team_logo) or changed

        if changed:
            self._save_logo_cache()
        return changed

    def _enrich_fixture_rows_with_logo_cache(self, response_rows: list[dict[str, Any]]) -> bool:
        changed = False
        leagues_by_id = self.logo_cache.get("leagues_by_id", {})
        leagues_by_name = self.logo_cache.get("leagues_by_name", {})
        teams_by_id = self.logo_cache.get("teams_by_id", {})
        teams_by_name = self.logo_cache.get("teams_by_name", {})

        for match in response_rows:
            league = match.get("league", {})
            league_logo = _clean_logo(league.get("logo"))
            if not league_logo:
                league_id_key = str(league.get("id", "")).strip()
                league_name_key = _norm_key(league.get("name"))
                replacement = str(
                    leagues_by_id.get(league_id_key) or leagues_by_name.get(league_name_key) or ""
                ).strip()
                if replacement:
                    league["logo"] = replacement
                    changed = True

            teams = match.get("teams", {})
            for side in ["home", "away"]:
                team = teams.get(side, {})
                team_logo = _clean_logo(team.get("logo"))
                if team_logo:
                    continue
                team_id_key = str(team.get("id", "")).strip()
                team_name_key = _norm_key(team.get("name"))
                replacement = str(teams_by_id.get(team_id_key) or teams_by_name.get(team_name_key) or "").strip()
                if replacement:
                    team["logo"] = replacement
                    changed = True

        return changed

    def _filter_response_rows(self, response_rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
        if not self.filter_target_leagues:
            return response_rows
        return [
            match
            for match in response_rows
            if match.get("league", {}).get("id") in self.target_leagues
        ]

    def _dedupe_fixtures(self, response_rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
        deduped: dict[str, dict[str, Any]] = {}
        for match in response_rows:
            fixture = match.get("fixture", {})
            fixture_id = fixture.get("id")

            if fixture_id is not None:
                key = str(fixture_id)
            else:
                league_id = str(match.get("league", {}).get("id", "0"))
                teams = match.get("teams", {})
                home_name = str(teams.get("home", {}).get("name", "")).strip().lower()
                away_name = str(teams.get("away", {}).get("name", "")).strip().lower()
                kickoff = str(fixture.get("date", "")).strip()
                key = f"{league_id}:{home_name}:{away_name}:{kickoff}"

            deduped[key] = match

        return list(deduped.values())

    def _parse_fixture_kickoff_utc(self, match: dict[str, Any]) -> dt.datetime | None:
        raw_kickoff = str(match.get("fixture", {}).get("date", "")).strip()
        if not raw_kickoff:
            return None

        parsed = self._parse_iso_datetime(raw_kickoff)
        if parsed is None:
            return None
        return parsed.astimezone(dt.UTC)

    def _filter_matches_in_window(
        self,
        matches: list[dict[str, Any]],
        start_utc: dt.datetime,
        end_utc: dt.datetime,
    ) -> list[dict[str, Any]]:
        filtered: list[dict[str, Any]] = []
        for match in matches:
            kickoff_utc = self._parse_fixture_kickoff_utc(match)
            if kickoff_utc is None:
                continue
            if start_utc <= kickoff_utc <= end_utc:
                filtered.append(match)
        return filtered

    def _collect_cached_matches_between(
        self,
        start_utc: dt.datetime,
        end_utc: dt.datetime,
    ) -> list[dict[str, Any]]:
        merged_rows: list[dict[str, Any]] = []
        for rows in self.fixtures_cache.values():
            if isinstance(rows, list):
                merged_rows.extend(rows)

        self._enrich_fixture_rows_with_logo_cache(merged_rows)
        filtered = self._filter_response_rows(merged_rows)
        deduped = self._dedupe_fixtures(filtered)
        return self._filter_matches_in_window(deduped, start_utc, end_utc)

    def _cache_source_for_date(self, date: str) -> str:
        return "cache_today" if date == _local_today_iso() else "cache"

    def _meta_age_minutes(self, date: str) -> float | None:
        meta = self.fixtures_meta.get(date)
        if not isinstance(meta, dict):
            return None

        last_attempt = self._parse_iso_datetime(meta.get("last_attempt_at"))
        if last_attempt is None:
            return None

        age = dt.datetime.now(dt.UTC) - last_attempt
        return max(0.0, age.total_seconds() / 60.0)

    def _date_attempted_today(self, date: str) -> bool:
        meta = self.fixtures_meta.get(date)
        if not isinstance(meta, dict):
            return False

        last_attempt = self._parse_iso_datetime(
            meta.get("last_attempt_at") or meta.get("updated_at")
        )
        if last_attempt is None:
            return False

        return last_attempt.date() == dt.datetime.now(dt.UTC).date()

    def _update_fixtures_meta(
        self,
        date: str,
        status: str,
        source: str,
        match_count: int,
        last_error: str | None = None,
    ) -> None:
        now_iso = dt.datetime.now(dt.UTC).isoformat()
        meta = self.fixtures_meta.get(date, {})
        if not isinstance(meta, dict):
            meta = {}

        meta["status"] = status
        meta["source"] = source
        meta["match_count"] = int(match_count)
        meta["updated_at"] = now_iso
        meta["last_attempt_at"] = now_iso

        if last_error:
            meta["last_error"] = last_error
        else:
            meta.pop("last_error", None)

        self.fixtures_meta[date] = meta
        self._save_fixtures_meta()

    def _window_snapshot_has_cache(self, today_iso: str, tomorrow_iso: str) -> bool:
        today_cached = (
            today_iso in self.fixtures_cache
            and isinstance(self.fixtures_cache.get(today_iso), list)
        )
        tomorrow_cached = (
            tomorrow_iso in self.fixtures_cache
            and isinstance(self.fixtures_cache.get(tomorrow_iso), list)
        )
        return bool(today_cached or tomorrow_cached)

    def _window_snapshot_is_stale(
        self,
        now_utc: dt.datetime,
        today_iso: str,
        tomorrow_iso: str,
    ) -> bool:
        if not self._window_snapshot_has_cache(today_iso, tomorrow_iso):
            return True

        meta = self.fixtures_meta.get(self.snapshot_meta_key)
        if not isinstance(meta, dict):
            return True

        expires_at = self._parse_iso_datetime(meta.get("expires_at") or meta.get("updated_at"))
        if expires_at is None:
            return True
        return now_utc >= expires_at

    def _set_window_snapshot_meta(self, status: str, last_error: str | None = None) -> None:
        now_utc = dt.datetime.now(dt.UTC)
        if status == "success" and self.snapshot_align_to_utc_day:
            expires_at = dt.datetime.combine(
                now_utc.date() + dt.timedelta(days=1),
                dt.time(hour=0, minute=0, second=0),
                tzinfo=dt.UTC,
            )
        else:
            ttl_minutes = (
                self.snapshot_ttl_minutes
                if status == "success"
                else self.snapshot_error_retry_minutes
            )
            expires_at = now_utc + dt.timedelta(minutes=ttl_minutes)

        meta: dict[str, Any] = {
            "status": status,
            "updated_at": now_utc.isoformat(),
            "expires_at": expires_at.isoformat(),
        }
        if last_error:
            meta["last_error"] = last_error

        self.fixtures_meta[self.snapshot_meta_key] = meta
        self._save_fixtures_meta()

    def _ensure_window_snapshot(self) -> None:
        if not self.auto_snapshot_refresh:
            return

        self._refresh_api_budget_if_needed()
        self._refresh_shared_cache_state()

        now_local = _local_now()
        now_utc = now_local.astimezone(dt.UTC)
        today_iso = now_local.date().isoformat()
        tomorrow_iso = (now_local.date() + dt.timedelta(days=1)).isoformat()

        if not self._window_snapshot_is_stale(now_utc, today_iso, tomorrow_iso):
            return

        if not self.api_key:
            self._set_window_snapshot_meta(
                "error",
                "API_SPORTS_KEY is not configured",
            )
            return

        refresh_errors: list[str] = []

        today_payload = self.get_fixtures_by_date(today_iso, allow_live_refresh=True)
        today_errors = today_payload.get("errors")
        if today_errors:
            refresh_errors.append(str(today_errors))
        today_issues = today_payload.get("upstream_issues")
        if isinstance(today_issues, list):
            refresh_errors.extend([str(item) for item in today_issues if str(item).strip()])

        if (
            self.snapshot_include_tomorrow_live
            and self._remaining_api_budget() >= len(self.target_leagues)
        ):
            tomorrow_payload = self.get_fixtures_by_date(tomorrow_iso, allow_live_refresh=True)
            tomorrow_errors = tomorrow_payload.get("errors")
            if tomorrow_errors:
                refresh_errors.append(str(tomorrow_errors))
            tomorrow_issues = tomorrow_payload.get("upstream_issues")
            if isinstance(tomorrow_issues, list):
                refresh_errors.extend(
                    [str(item) for item in tomorrow_issues if str(item).strip()]
                )
        else:
            self.get_fixtures_by_date(tomorrow_iso, allow_live_refresh=False)

        self._warm_target_standings_once()
        self._refresh_shared_cache_state()

        deduped_errors = _dedupe_text(refresh_errors)
        if self._window_snapshot_has_cache(today_iso, tomorrow_iso):
            self._set_window_snapshot_meta(
                "success",
                "; ".join(deduped_errors) if deduped_errors else None,
            )
        else:
            self._set_window_snapshot_meta(
                "error",
                "; ".join(deduped_errors) if deduped_errors else "Snapshot refresh failed",
            )

    def _is_allowed_fixture_date(self, date_value: dt.date) -> tuple[bool, str | None]:
        today = _local_now().date()
        if date_value < today:
            return False, "Historical API fetch is disabled by policy"
        if date_value > (today + dt.timedelta(days=1)):
            return False, "Future API fetch beyond tomorrow is disabled by policy"
        return True, None

    def _should_attempt_live_refresh(self, date: str, date_value: dt.date, has_cache: bool) -> bool:
        self._refresh_api_budget_if_needed()

        allowed, _ = self._is_allowed_fixture_date(date_value)
        if not allowed:
            return False

        if not self.api_key:
            return False

        if date in self.force_refresh_dates:
            self.force_refresh_dates.discard(date)
            return True

        # Strict cache mode: only one live fetch attempt per date per day.
        if self.single_fetch_per_date_per_day and self._date_attempted_today(date):
            return False

        if has_cache and self._remaining_api_budget() < len(self.target_leagues):
            return False

        meta = self.fixtures_meta.get(date)
        if not isinstance(meta, dict):
            return True

        age_minutes = self._meta_age_minutes(date)
        if age_minutes is None:
            return True

        status = str(meta.get("status", "")).strip().lower()
        if status == "error":
            return age_minutes >= float(self.fixture_error_retry_minutes)

        if has_cache:
            return age_minutes >= float(self.fixture_cache_refresh_minutes)

        return True

    def _build_cached_payload(
        self,
        date: str,
        cache_reason: str,
        extra_warnings: list[str] | None = None,
    ) -> dict[str, Any]:
        cached_exists = date in self.fixtures_cache and isinstance(self.fixtures_cache.get(date), list)
        cached_rows = self.fixtures_cache.get(date, []) if cached_exists else []
        cache_changed = False
        if cached_exists and cached_rows:
            cache_changed = self._enrich_fixture_rows_with_logo_cache(cached_rows)
            if cache_changed:
                self.fixtures_cache[date] = cached_rows
                self._save_fixtures_cache()

        warnings: list[str] = []
        if cached_exists:
            if cached_rows:
                warnings.append(f"Loaded cached fixtures for {date}.")
                if cache_changed:
                    warnings.append("Applied cached logo enrichment.")
            else:
                warnings.append(f"Loaded cached empty fixture set for {date}.")

            meta = self.fixtures_meta.get(date)
            if isinstance(meta, dict):
                last_error = str(meta.get("last_error", "")).strip()
                if last_error:
                    warnings.append(
                        f"Latest live refresh failed: {_summarize_live_error(last_error)}"
                    )

            if extra_warnings:
                warnings.extend(extra_warnings)

            return {
                "errors": {},
                "response": cached_rows,
                "cached": True,
                "cache_reason": cache_reason,
                "source": self._cache_source_for_date(date),
                "warnings": _dedupe_text(warnings),
            }

        warnings.append(f"No cached fixtures available for {date}.")
        warnings.append(_summarize_live_error(cache_reason))
        if extra_warnings:
            warnings.extend(extra_warnings)

        return {
            "errors": cache_reason,
            "response": [],
            "source": "none",
            "warnings": _dedupe_text(warnings),
        }

    def _fetch_live_fixtures_for_date(
        self, date: str
    ) -> tuple[list[dict[str, Any]], list[str]]:
        upstream_issues: list[str] = []
        merged_rows: list[dict[str, Any]] = []
        budget_error: str | None = None

        for league_id in self.target_leagues:
            league_label = self.league_names.get(league_id, f"League {league_id}")
            payload, error_message = self._request_json_once(
                "fixtures", {"date": date, "league": league_id}
            )
            if payload is None:
                if error_message and _is_daily_limit_error_text(error_message):
                    budget_error = error_message
                    upstream_issues.append(f"{league_label}: {error_message}")
                    break
                if error_message and "Daily API call budget reached" in error_message:
                    budget_error = error_message
                    break
                upstream_issues.append(f"{league_label}: {error_message}")
                continue

            response_rows = payload.get("response", [])
            if not isinstance(response_rows, list):
                upstream_issues.append(f"{league_label}: malformed fixtures response payload")
                continue

            merged_rows.extend(response_rows)

        if budget_error:
            upstream_issues.append(budget_error)

        filtered_rows = self._filter_response_rows(merged_rows)
        deduped_rows = self._dedupe_fixtures(filtered_rows)
        if deduped_rows:
            self._update_logo_cache_from_rows(deduped_rows)
            self._enrich_fixture_rows_with_logo_cache(deduped_rows)
        return deduped_rows, upstream_issues

    @staticmethod
    def _season_for_date(date_value: dt.date) -> int:
        return date_value.year if date_value.month >= 7 else date_value.year - 1

    def get_standings(
        self,
        league_id: int,
        season: int,
        allow_live_refresh: bool = True,
    ) -> dict[str, dict[str, Any]]:
        cache_key = f"{league_id}_{season}"
        today_iso = _local_today_iso()

        if self.standings_cache_date and self.standings_cache_date != today_iso:
            self.standings_cache.clear()
            self.standings_cache_date = today_iso

        if cache_key in self.standings_cache:
            return self.standings_cache[cache_key]

        # For long-tail leagues we avoid upstream calls and use stable fallback stats.
        if league_id not in self.target_leagues:
            fallback = self._generate_fallback_standings()
            self.standings_cache[cache_key] = fallback
            return fallback

        if not allow_live_refresh:
            fallback = self._generate_fallback_standings()
            self.standings_cache[cache_key] = fallback
            self.standings_cache_date = today_iso
            self._save_standings_cache()
            return fallback

        if not self.api_key:
            logger.warning("API_SPORTS_KEY is not configured. Using standings fallback.")
            fallback = self._generate_fallback_standings()
            self.standings_cache[cache_key] = fallback
            return fallback

        payload, error_message = self._request_json_once(
            "standings", {"league": league_id, "season": season}
        )
        if payload is None:
            logger.warning(
                "Standings fetch failed for league={} season={}: {}",
                league_id,
                season,
                error_message,
            )
            fallback = self._generate_fallback_standings()
            self.standings_cache[cache_key] = fallback
            return fallback

        try:
            rows = payload["response"][0]["league"]["standings"][0]
        except (KeyError, IndexError, TypeError) as exc:
            logger.warning(
                f"Standings payload malformed for league={league_id} season={season}: {exc}"
            )
            fallback = self._generate_fallback_standings()
            self.standings_cache[cache_key] = fallback
            return fallback

        standings_logo_changed = False
        for row in rows:
            team = row.get("team", {})
            team_logo = _clean_logo(team.get("logo"))
            if not team_logo:
                continue
            team_id = str(team.get("id", "")).strip()
            team_name = _norm_key(team.get("name"))
            standings_logo_changed = (
                self._index_logo("teams_by_id", team_id, team_logo) or standings_logo_changed
            )
            standings_logo_changed = (
                self._index_logo("teams_by_name", team_name, team_logo) or standings_logo_changed
            )
        if standings_logo_changed:
            self._save_logo_cache()

        team_stats: dict[str, dict[str, Any]] = {}
        for row in rows:
            team_name = str(row.get("team", {}).get("name", "")).strip().lower()
            if not team_name:
                continue
            team_stats[team_name] = {
                "rank": int(row.get("rank", 10)),
                "points": int(row.get("points", 40)),
                "form": str(row.get("form", "") or ""),
            }

        if not team_stats:
            team_stats = self._generate_fallback_standings()

        self.standings_cache[cache_key] = team_stats
        self.standings_cache_date = today_iso
        self._save_standings_cache()
        return team_stats

    def _generate_fallback_standings(self) -> dict[str, dict[str, Any]]:
        return {
            "real madrid": {"rank": 1, "points": 82, "form": "WWWWW"},
            "barcelona": {"rank": 2, "points": 79, "form": "WWDWW"},
            "manchester city": {"rank": 1, "points": 84, "form": "WWWWW"},
            "liverpool": {"rank": 2, "points": 80, "form": "WWDWW"},
            "arsenal": {"rank": 3, "points": 78, "form": "WDWWW"},
            "inter": {"rank": 1, "points": 83, "form": "WWWWW"},
            "juventus": {"rank": 3, "points": 72, "form": "WDWLW"},
            "bayern munich": {"rank": 2, "points": 76, "form": "WWLWW"},
            "bayer leverkusen": {"rank": 1, "points": 81, "form": "WWDWW"},
        }

    def get_fixtures_by_date(
        self, date: str | None = None, allow_live_refresh: bool = True
    ) -> dict[str, Any]:
        self._refresh_shared_cache_state()

        if not date:
            date_value = _local_now().date()
            date = date_value.isoformat()
        else:
            try:
                date_value = dt.date.fromisoformat(date)
            except ValueError:
                return {
                    "errors": "date must be in YYYY-MM-DD format",
                    "response": [],
                    "source": "none",
                    "warnings": ["Invalid date format."],
                }

        has_cache = date in self.fixtures_cache and isinstance(self.fixtures_cache.get(date), list)
        should_refresh = self._should_attempt_live_refresh(date, date_value, has_cache)

        if has_cache and not should_refresh:
            return self._build_cached_payload(
                date,
                cache_reason="Using cached result within refresh interval",
            )

        if not allow_live_refresh:
            return self._build_cached_payload(
                date,
                cache_reason="Live refresh disabled for request path",
            )

        allowed, reason = self._is_allowed_fixture_date(date_value)
        if not allowed:
            return self._build_cached_payload(date, cache_reason=str(reason))

        if not self.api_key:
            return self._build_cached_payload(date, cache_reason="API_SPORTS_KEY is not configured")

        live_rows, upstream_issues = self._fetch_live_fixtures_for_date(date)

        if live_rows:
            self.fixtures_cache[date] = live_rows
            self._save_fixtures_cache()

            status = "success_partial" if upstream_issues else "success"
            self._update_fixtures_meta(
                date=date,
                status=status,
                source="live",
                match_count=len(live_rows),
                last_error="; ".join(upstream_issues) if upstream_issues else None,
            )

            result: dict[str, Any] = {
                "errors": {},
                "response": live_rows,
                "source": "live" if not upstream_issues else "live_partial",
            }
            if upstream_issues:
                result["warnings"] = [
                    f"Loaded partial fixtures for {date}: {len(upstream_issues)} league request(s) failed."
                ]
                result["upstream_issues"] = upstream_issues
            return result

        if not upstream_issues:
            # Valid empty day. Cache it and refresh later based on interval.
            self.fixtures_cache[date] = []
            self._save_fixtures_cache()
            self._update_fixtures_meta(
                date=date,
                status="empty_success",
                source="live",
                match_count=0,
                last_error=None,
            )
            return {
                "errors": {},
                "response": [],
                "source": "live",
                "warnings": [f"No fixtures found for {date} in configured leagues."],
            }

        error_text = "; ".join(upstream_issues)
        self._update_fixtures_meta(
            date=date,
            status="error",
            source="live_error",
            match_count=len(self.fixtures_cache.get(date, []) if has_cache else []),
            last_error=error_text,
        )

        if has_cache:
            payload = self._build_cached_payload(
                date,
                cache_reason=error_text,
                extra_warnings=[f"Using cached fixtures for {date} because live refresh failed."],
            )
            payload["upstream_issues"] = upstream_issues
            return payload

        return {
            "errors": error_text,
            "response": [],
            "source": "none",
            "warnings": [
                f"Unable to load fixtures for {date} from API and no cache is available."
            ],
            "upstream_issues": upstream_issues,
        }

    def get_fixtures_in_window(
        self, window_hours: int | None = None, allow_live_refresh: bool = True
    ) -> dict[str, Any]:
        self._refresh_shared_cache_state()
        self._ensure_window_snapshot()

        hours = self.default_window_hours if window_hours is None else int(window_hours)
        hours = max(1, min(48, hours))

        now_local = _local_now()
        base_end_local = now_local + dt.timedelta(hours=hours)
        end_local = base_end_local
        now_utc = now_local.astimezone(dt.UTC)
        end_utc = base_end_local.astimezone(dt.UTC)

        today = now_local.date()
        tomorrow = today + dt.timedelta(days=1)

        payloads = [
            self.get_fixtures_by_date(today.isoformat(), allow_live_refresh=False),
            self.get_fixtures_by_date(tomorrow.isoformat(), allow_live_refresh=False),
        ]
        date_keys = [today.isoformat(), tomorrow.isoformat()]

        self._enrich_cached_dates_with_logo_cache(date_keys)

        merged_rows: list[dict[str, Any]] = []
        warnings: list[str] = []
        upstream_issues: list[str] = []
        sources: list[str] = []

        for payload in payloads:
            rows = payload.get("response", [])
            if isinstance(rows, list):
                merged_rows.extend(rows)

            sources.append(str(payload.get("source", "unknown")))

            payload_warnings = payload.get("warnings")
            if isinstance(payload_warnings, list):
                warnings.extend([str(item) for item in payload_warnings])
            elif isinstance(payload_warnings, str):
                warnings.append(payload_warnings)

            payload_issues = payload.get("upstream_issues")
            if isinstance(payload_issues, list):
                upstream_issues.extend([str(item) for item in payload_issues])

            raw_error = payload.get("errors")
            if raw_error:
                upstream_issues.append(str(raw_error))

        self._enrich_fixture_rows_with_logo_cache(merged_rows)
        filtered = self._filter_response_rows(merged_rows)
        deduped = self._dedupe_fixtures(filtered)
        window_matches = self._filter_matches_in_window(deduped, now_utc, end_utc)
        cached_window_matches = self._collect_cached_matches_between(now_utc, end_utc)
        if cached_window_matches:
            window_matches = self._dedupe_fixtures(window_matches + cached_window_matches)
            window_matches = self._filter_matches_in_window(window_matches, now_utc, end_utc)

        if (
            len(window_matches) < self.min_window_matches
            and self.window_extension_hours > 0
        ):
            extended_total_hours = min(48, hours + self.window_extension_hours)
            if extended_total_hours > hours:
                extended_end_local = now_local + dt.timedelta(hours=extended_total_hours)
                extended_end_utc = extended_end_local.astimezone(dt.UTC)
                extended_matches = self._filter_matches_in_window(deduped, now_utc, extended_end_utc)
                cached_extended_matches = self._collect_cached_matches_between(
                    now_utc, extended_end_utc
                )
                if cached_extended_matches:
                    extended_matches = self._dedupe_fixtures(
                        extended_matches + cached_extended_matches
                    )
                    extended_matches = self._filter_matches_in_window(
                        extended_matches, now_utc, extended_end_utc
                    )
                if len(extended_matches) > len(window_matches):
                    window_matches = extended_matches
                    end_local = extended_end_local
                    end_utc = extended_end_utc
                    warnings.append(
                        f"Auto-extended window to {extended_total_hours}h due limited upcoming fixtures."
                    )

        if not window_matches:
            tomorrow_end_local = dt.datetime.combine(
                tomorrow,
                dt.time(hour=23, minute=59, second=59),
                tzinfo=now_local.tzinfo,
            )
            tomorrow_end_utc = tomorrow_end_local.astimezone(dt.UTC)
            fallback_matches = self._collect_cached_matches_between(now_utc, tomorrow_end_utc)
            if fallback_matches:
                window_matches = fallback_matches
                end_local = tomorrow_end_local
                end_utc = tomorrow_end_utc
                warnings.append("Using cached upcoming matches through end of tomorrow.")
            else:
                warnings.append(f"No fixtures found in the next {hours} hours.")

        has_live = any(source.startswith("live") for source in sources)
        has_cache = any(source.startswith("cache") for source in sources)

        if has_live and has_cache:
            source = "window_partial"
        elif has_live:
            source = "window_live"
        elif has_cache:
            source = "window_cache"
        else:
            source = "window_none"

        result: dict[str, Any] = {
            "errors": {},
            "response": window_matches,
            "source": source,
            "warnings": _dedupe_text(warnings),
            "window_start": now_local.isoformat(),
            "window_end": end_local.isoformat(),
            "window_hours": hours,
        }

        deduped_issues = _dedupe_text(upstream_issues)
        if deduped_issues:
            result["upstream_issues"] = deduped_issues

        return result
