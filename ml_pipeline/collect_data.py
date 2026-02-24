from __future__ import annotations

import os
import re
import time
from datetime import timedelta

import pandas as pd
import requests
from dotenv import load_dotenv
from loguru import logger
from pytrends.request import TrendReq

load_dotenv("backend/.env")

API_KEY = os.getenv("API_SPORTS_KEY", "").strip()
REQUEST_TIMEOUT_SECONDS = float(os.getenv("REQUEST_TIMEOUT_SECONDS", "15"))

HEADERS = {
    "x-rapidapi-host": "v3.football.api-sports.io",
    "x-apisports-key": API_KEY,
}

TARGET_LEAGUES = {
    2: "UEFA Champions League",
    39: "Premier League",
    140: "La Liga",
    78: "Bundesliga",
    135: "Serie A",
}
SEASONS = [2021, 2022, 2023]

pytrends = TrendReq(hl="en-US", tz=360)


def fetch_historical_fixtures() -> list[dict]:
    if not API_KEY:
        raise RuntimeError("API_SPORTS_KEY is required to collect historical fixtures.")

    all_matches: list[dict] = []
    for league_id, league_name in TARGET_LEAGUES.items():
        for season in SEASONS:
            logger.info(f"Fetching {league_name} fixtures for {season}")
            try:
                response = requests.get(
                    "https://v3.football.api-sports.io/fixtures",
                    headers=HEADERS,
                    params={"league": league_id, "season": season},
                    timeout=REQUEST_TIMEOUT_SECONDS,
                )
                response.raise_for_status()
                payload = response.json()
                rows = payload.get("response", [])
                if isinstance(rows, list):
                    all_matches.extend(rows)
            except requests.exceptions.RequestException as exc:
                logger.error(
                    f"Fixture fetch failed for league_id={league_id} season={season}: {exc}"
                )
            time.sleep(1)
    return all_matches


def fetch_standings(league_id: int, season: int) -> dict[str, dict]:
    try:
        response = requests.get(
            "https://v3.football.api-sports.io/standings",
            headers=HEADERS,
            params={"league": league_id, "season": season},
            timeout=REQUEST_TIMEOUT_SECONDS,
        )
        response.raise_for_status()
        payload = response.json()
        standings = payload["response"][0]["league"]["standings"][0]
    except (requests.exceptions.RequestException, ValueError, KeyError, IndexError) as exc:
        logger.error(f"Standings fetch failed for league_id={league_id} season={season}: {exc}")
        return {}

    team_stats: dict[str, dict] = {}
    for row in standings:
        team_name = str(row.get("team", {}).get("name", "")).strip().lower()
        if not team_name:
            continue
        team_stats[team_name] = {
            "rank": int(row.get("rank", 10)),
            "points": int(row.get("points", 40)),
            "form": str(row.get("form", "") or "WLLDW"),
        }
    return team_stats


def _is_late_season(round_name: str) -> int:
    round_name = round_name.lower()
    matchday_match = re.search(r"regular season - (\d+)", round_name)
    if matchday_match:
        return int(int(matchday_match.group(1)) >= 30)
    return int(any(x in round_name for x in ["quarter", "semi", "final"]))


def _form_to_points(form_str: str) -> int:
    score = 0
    for char in str(form_str)[-5:].upper():
        if char == "W":
            score += 3
        elif char == "D":
            score += 1
    return score


def extract_competitive_features(match_list: list[dict]) -> pd.DataFrame:
    rows: list[dict] = []

    standings_cache: dict[tuple[int, int], dict[str, dict]] = {}
    for league_id in TARGET_LEAGUES:
        for season in SEASONS:
            standings_cache[(league_id, season)] = fetch_standings(league_id, season)
            time.sleep(1)

    for match in match_list:
        try:
            league_id = int(match["league"]["id"])
            season = int(match["league"]["season"])
            round_name = str(match["league"]["round"])
            match_date = str(match["fixture"]["date"])[:10]
            home_team = str(match["teams"]["home"]["name"])
            away_team = str(match["teams"]["away"]["name"])

            is_knockout = int(
                any(x in round_name.lower() for x in ["knockout", "16", "quarter", "semi", "final"])
                and "group" not in round_name.lower()
            )
            league_weight = 1.5 if league_id == 2 else 1.0
            is_late_season = _is_late_season(round_name)

            famous_derbies = [
                ("Real Madrid", "Barcelona"),
                ("Manchester City", "Manchester United"),
                ("Arsenal", "Tottenham"),
                ("Inter", "AC Milan"),
                ("Bayern Munich", "Borussia Dortmund"),
                ("Liverpool", "Manchester United"),
            ]
            is_derby = int(
                any(
                    (t1 in home_team and t2 in away_team)
                    or (t2 in home_team and t1 in away_team)
                    for t1, t2 in famous_derbies
                )
            )

            standings = standings_cache.get((league_id, season), {})
            home_stats = standings.get(home_team.strip().lower(), {"rank": 10, "points": 40, "form": "WLLDW"})
            away_stats = standings.get(away_team.strip().lower(), {"rank": 10, "points": 40, "form": "WLLDW"})

            home_rank = int(home_stats["rank"])
            away_rank = int(away_stats["rank"])
            rank_diff = abs(home_rank - away_rank)
            points_gap = abs(int(home_stats["points"]) - int(away_stats["points"]))
            home_form = _form_to_points(home_stats["form"])
            away_form = _form_to_points(away_stats["form"])

            is_relegation_battle = int(home_rank >= 15 and away_rank >= 15 and is_late_season == 1)
            is_title_race = int(home_rank <= 3 and away_rank <= 3 and is_late_season == 1)

            rows.append(
                {
                    "match_id": int(match["fixture"]["id"]),
                    "date": match_date,
                    "season": season,
                    "league_id": league_id,
                    "home_team": home_team,
                    "away_team": away_team,
                    "league_weight": league_weight,
                    "is_knockout": is_knockout,
                    "is_derby": is_derby,
                    "rank_diff": rank_diff,
                    "points_gap": points_gap,
                    "home_form": home_form,
                    "away_form": away_form,
                    "is_relegation_battle": is_relegation_battle,
                    "is_title_race": is_title_race,
                    "is_late_season": is_late_season,
                    "search_term": f"{home_team} vs {away_team}",
                }
            )
        except (KeyError, TypeError, ValueError) as exc:
            logger.warning(f"Skipping malformed match row: {exc}")

    return pd.DataFrame(rows)


def fetch_google_trends_batched(df: pd.DataFrame) -> pd.DataFrame:
    if df.empty:
        logger.error("DataFrame is empty. No matches available for trends scoring.")
        return df

    df = df.copy()
    df["date"] = pd.to_datetime(df["date"])
    df = df.sort_values(by="date")

    # Keep this bounded to avoid API bans during one-shot runs.
    df_subset = df.head(100).copy()
    hype_scores: list[float] = []

    anchor_term = "Football"
    batch_size = 4

    for i in range(0, len(df_subset), batch_size):
        batch = df_subset.iloc[i : i + batch_size]
        terms = batch["search_term"].tolist()
        query_list = [anchor_term] + terms

        min_date = batch["date"].min() - timedelta(days=3)
        max_date = batch["date"].max() + timedelta(days=3)
        timeframe = f"{min_date.strftime('%Y-%m-%d')} {max_date.strftime('%Y-%m-%d')}"
        logger.info(f"Querying Trends for {terms} in timeframe {timeframe}")

        try:
            pytrends.build_payload(query_list, cat=0, timeframe=timeframe, geo="")
            trends_df = pytrends.interest_over_time()
            if trends_df.empty:
                hype_scores.extend([0.0] * len(terms))
            else:
                anchor_peak = float(trends_df[anchor_term].max()) or 1.0
                for term in terms:
                    if term in trends_df.columns:
                        term_peak = float(trends_df[term].max())
                        hype_scores.append((term_peak / anchor_peak) * 100)
                    else:
                        hype_scores.append(0.0)
            time.sleep(5)
        except Exception as exc:
            logger.warning(f"Trends API error for batch {terms}: {exc}")
            hype_scores.extend([0.0] * len(terms))
            time.sleep(15)

    df_subset["target_hype"] = hype_scores
    return df_subset


if __name__ == "__main__":
    logger.info("Starting historical data collection.")
    raw_matches = fetch_historical_fixtures()
    logger.info(f"Fetched {len(raw_matches)} matches.")

    df_features = extract_competitive_features(raw_matches)
    logger.info(f"Extracted features for {len(df_features)} matches.")

    df_scored = fetch_google_trends_batched(df_features)
    os.makedirs("data", exist_ok=True)
    df_scored.to_csv("data/historical_matches_elite.csv", index=False)
    logger.info("Saved dataset to data/historical_matches_elite.csv")
