from __future__ import annotations

import datetime as dt
import json

try:
    from backend.services.api_football import FootballAPI
except ModuleNotFoundError:
    from services.api_football import FootballAPI


def _dedupe_text(values: list[str]) -> list[str]:
    deduped: list[str] = []
    seen: set[str] = set()
    for value in values:
        item = str(value).strip()
        if not item or item in seen:
            continue
        seen.add(item)
        deduped.append(item)
    return deduped


def main() -> None:
    api = FootballAPI()
    today = dt.date.today()
    tomorrow = today + dt.timedelta(days=1)
    requested_dates = [today.isoformat(), tomorrow.isoformat()]

    fixtures_loaded = 0
    warnings: list[str] = []
    source_by_date: dict[str, str] = {}
    leagues: set[tuple[int, int]] = set()

    for date_text in requested_dates:
        payload = api.get_fixtures_by_date(date_text)
        source_by_date[date_text] = str(payload.get("source", "unknown"))

        payload_warnings = payload.get("warnings")
        if isinstance(payload_warnings, list):
            warnings.extend([str(item) for item in payload_warnings])
        elif isinstance(payload_warnings, str):
            warnings.append(payload_warnings)

        fixtures = payload.get("response", [])
        if not isinstance(fixtures, list):
            continue

        fixtures_loaded += len(fixtures)
        for match in fixtures:
            league = match.get("league", {})
            league_id = int(league.get("id", 0) or 0)
            season = int(league.get("season", dt.date.today().year) or dt.date.today().year)
            if league_id > 0:
                leagues.add((league_id, season))

    warmed = 0
    for league_id, season in sorted(leagues):
        api.get_standings(league_id, season)
        warmed += 1

    print(
        json.dumps(
            {
                "requested_dates": requested_dates,
                "fixtures_loaded": fixtures_loaded,
                "standings_leagues_warmed": warmed,
                "source_by_date": source_by_date,
                "warnings": _dedupe_text(warnings),
                "api_budget": api.budget_status(),
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
