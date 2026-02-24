from __future__ import annotations

import datetime as dt
import os
import re
from typing import Any

import numpy as np
import pandas as pd
import scipy.stats
from loguru import logger

try:
    import xgboost as xgb
except Exception:  # pragma: no cover - fallback path for minimal deploys
    xgb = None

try:
    import shap
except Exception:  # pragma: no cover - optional dependency
    shap = None


FEATURE_COLUMNS = [
    "league_weight",
    "is_knockout",
    "is_derby",
    "rank_diff",
    "points_gap",
    "home_form",
    "away_form",
    "is_relegation_battle",
    "is_title_race",
    "is_late_season",
]

FAMOUS_DERBIES = [
    ("Real Madrid", "Barcelona"),
    ("Manchester City", "Manchester United"),
    ("Arsenal", "Tottenham"),
    ("Inter", "AC Milan"),
    ("Bayern Munich", "Borussia Dortmund"),
    ("Liverpool", "Manchester United"),
]


def _env_flag(name: str, default: bool = False) -> bool:
    raw = os.getenv(name, str(default)).strip().lower()
    return raw in {"1", "true", "yes", "on"}


def _fallback_team_stats(team_name: str) -> tuple[int, int, int]:
    pseudo_hash = sum(ord(c) for c in team_name)
    rank = (pseudo_hash % 20) + 1
    points = max(0, 85 - (rank * 3) + (pseudo_hash % 10))
    form = (pseudo_hash % 15) + 1
    return rank, points, form


class MatchScorer:
    def __init__(self) -> None:
        self.model: Any | None = None
        self.explainer = None
        self.enable_shap = _env_flag("ENABLE_SHAP_EXPLANATIONS", default=False)

        self.model_path = os.path.normpath(
            os.path.join(os.path.dirname(__file__), "..", "ml_model_elite.json")
        )

        if xgb is None:
            logger.warning("xgboost is unavailable. Using heuristic fallback scoring.")
            return

        if not os.path.exists(self.model_path):
            logger.warning(
                f"Model not found at {self.model_path}. Using heuristic fallback scoring."
            )
            return

        try:
            model = xgb.XGBRegressor()
            model.load_model(self.model_path)
            self.model = model
            logger.info(f"Loaded model from {self.model_path}")
        except Exception as exc:
            logger.error(f"Failed to load model at {self.model_path}: {exc}")
            return

        if self.enable_shap and shap is not None:
            try:
                self.explainer = shap.TreeExplainer(self.model)
                logger.info("SHAP explainer initialized.")
            except Exception as exc:
                logger.warning(f"SHAP unavailable; continuing without explanations: {exc}")
        elif self.enable_shap:
            logger.warning("ENABLE_SHAP_EXPLANATIONS=true but shap is not installed.")

    def extract_features(
        self,
        match: dict[str, Any],
        api: Any = None,
        standings: dict[str, dict[str, Any]] | None = None,
    ) -> dict[str, int | float]:
        league = match.get("league", {})
        teams = match.get("teams", {})

        league_id = league.get("id", 0)
        round_name = str(league.get("round", "")).lower()
        home_team = str(teams.get("home", {}).get("name", "Unknown"))
        away_team = str(teams.get("away", {}).get("name", "Unknown"))

        league_weight = 1.5 if league_id == 2 else 1.0
        is_knockout = int(
            any(x in round_name for x in ["knockout", "16", "quarter", "semi", "final"])
            and "group" not in round_name
        )

        is_derby = int(
            any(
                (t1 in home_team and t2 in away_team)
                or (t2 in home_team and t1 in away_team)
                for t1, t2 in FAMOUS_DERBIES
            )
        )

        home_rank = 10
        away_rank = 10
        home_points = 40
        away_points = 40
        home_form = 6
        away_form = 6

        team_standings = standings or {}
        if not team_standings and api:
            season = int(league.get("season", 2023))
            team_standings = api.get_standings(league_id, season)

        def get_team_stats(team_name: str) -> tuple[int, int, int]:
            key = team_name.strip().lower()
            if key and key in team_standings:
                row = team_standings[key]
                form_str = str(row.get("form", "") or "").upper()
                form_score = sum(3 if c == "W" else 1 if c == "D" else 0 for c in form_str[-5:])
                return int(row.get("rank", 10)), int(row.get("points", 40)), int(form_score)
            return _fallback_team_stats(team_name)

        home_rank, home_points, home_form = get_team_stats(home_team)
        away_rank, away_points, away_form = get_team_stats(away_team)

        rank_diff = abs(home_rank - away_rank)
        points_gap = abs(home_points - away_points)

        matchday_match = re.search(r"regular season - (\d+)", round_name)
        if matchday_match:
            matchday = int(matchday_match.group(1))
            is_late_season = int(matchday >= 30)
        else:
            is_late_season = int(any(x in round_name for x in ["final", "semi", "quarter"]))

        is_relegation_battle = int(home_rank >= 15 and away_rank >= 15 and is_late_season == 1)
        is_title_race = int(home_rank <= 3 and away_rank <= 3 and is_late_season == 1)

        return {
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
            "home_rank": home_rank,
            "away_rank": away_rank,
            "home_points": home_points,
            "away_points": away_points,
        }

    def _contextual_reasons(
        self,
        features: dict[str, int | float],
        home_name: str,
        away_name: str,
    ) -> list[str]:
        reasons: list[str] = []

        if features["is_derby"]:
            reasons.append("Historic rivalry matchup")
        if features["is_knockout"]:
            reasons.append("Knockout-stage pressure game")
        if features["is_title_race"]:
            reasons.append("Title-race implications")
        if features["is_relegation_battle"]:
            reasons.append("Relegation six-pointer")

        if features["rank_diff"] <= 3 and features["points_gap"] <= 6:
            reasons.append("Close table matchup")
        elif features["rank_diff"] <= 8 and features["points_gap"] <= 12:
            reasons.append("Mid-table positioning battle")

        if features["home_form"] >= 11 and features["away_form"] >= 11:
            reasons.append("Both teams in strong recent form")

        form_gap = int(abs(features["home_form"] - features["away_form"]))
        if form_gap >= 6:
            in_form_team = home_name if features["home_form"] > features["away_form"] else away_name
            reasons.append(f"{in_form_team} enters with a clear form edge")

        if features["rank_diff"] >= 8 and features["points_gap"] >= 15:
            reasons.append("Underdog upset narrative")

        if features["points_gap"] <= 12 and form_gap <= 4 and features["rank_diff"] <= 8:
            reasons.append("Likely decided by tactical details")

        if features["is_late_season"] and features["points_gap"] <= 10:
            reasons.append("Late-season points pressure")

        if features["league_weight"] > 1:
            reasons.append("Elite European competition")

        if not reasons:
            reasons.append("Balanced league fixture")

        return reasons

    def score_matches(
        self,
        matches: list[dict[str, Any]],
        api: Any = None,
        prefs: dict[str, Any] | None = None,
    ) -> list[dict[str, Any]]:
        prefs = prefs or {}
        fav_team = str(prefs.get("favorite_team", "")).strip().lower()
        prefers_goals = bool(prefs.get("prefers_goals", False))
        prefers_tactical = bool(prefs.get("prefers_tactical", False))

        standings_by_competition: dict[tuple[int, int], dict[str, dict[str, Any]]] = {}
        if api:
            for match in matches:
                league_meta = match.get("league", {})
                league_id = int(league_meta.get("id", 0) or 0)
                season = int(league_meta.get("season", 2023) or 2023)
                if league_id <= 0:
                    continue
                key = (league_id, season)
                if key in standings_by_competition:
                    continue
                standings_by_competition[key] = api.get_standings(league_id, season)

        scored_matches: list[dict[str, Any]] = []
        for match in matches:
            fixture = match.get("fixture", {})
            teams = match.get("teams", {})
            league = match.get("league", {})

            fixture_id = fixture.get("id")
            home_name = str(teams.get("home", {}).get("name", "Unknown"))
            away_name = str(teams.get("away", {}).get("name", "Unknown"))

            if fixture_id is None:
                logger.warning(f"Skipping fixture without id: {home_name} vs {away_name}")
                continue

            league_id = int(league.get("id", 0) or 0)
            season = int(league.get("season", 2023) or 2023)
            standings = standings_by_competition.get((league_id, season), {})
            features = self.extract_features(match, api=api, standings=standings)
            df_features = pd.DataFrame([features])

            rule_score = (
                (features["is_derby"] * 25)
                + (features["is_knockout"] * 35)
                + (features["is_title_race"] * 30)
            )
            if rule_score == 0:
                rule_score = 10

            ml_score = float(rule_score)
            if self.model is not None:
                try:
                    ml_score = float(self.model.predict(df_features[FEATURE_COLUMNS])[0])
                except Exception as exc:
                    logger.warning(f"Prediction failed for fixture_id={fixture_id}: {exc}")

            base_score = 0.85 * ml_score + 0.15 * rule_score

            personalization_bonus = 0
            is_fav_team = False
            is_tactical_bonus = False
            is_goals_bonus = False

            home_name_lower = home_name.lower()
            away_name_lower = away_name.lower()

            if fav_team and (fav_team in home_name_lower or fav_team in away_name_lower):
                personalization_bonus += 40
                is_fav_team = True

            if prefers_goals and features["home_form"] >= 8 and features["away_form"] >= 8:
                personalization_bonus += 15
                is_goals_bonus = True

            if prefers_tactical and features["rank_diff"] <= 5 and features["points_gap"] <= 10:
                personalization_bonus += 20
                is_tactical_bonus = True

            final_score = int(np.clip(base_score + personalization_bonus, 0, 100))
            reasons: list[str] = []

            if is_fav_team:
                reasons.append("Your Favorite Team")
            if is_goals_bonus:
                reasons.append("Heavy Goalscoring Form")
            if is_tactical_bonus:
                reasons.append("Tight Tactical Matchup")

            if self.explainer is not None:
                try:
                    shap_values = self.explainer.shap_values(df_features[FEATURE_COLUMNS])
                    row_values = shap_values[0] if np.ndim(shap_values) > 1 else shap_values
                    top_indices = np.argsort(-np.abs(row_values))[:2]
                    feature_labels = {
                        "is_derby": "Historic Rivalry Derby",
                        "is_knockout": "High-Stakes Knockout Stage",
                        "is_title_race": "Late-Season Title Clash",
                        "rank_diff": "Close Bracket Proximity",
                        "points_gap": "Tight Points Differential",
                        "home_form": "Elite Home Form",
                        "away_form": "Elite Away Form",
                        "league_weight": "Premium European Fixture",
                        "is_relegation_battle": "Relegation Survival Battle",
                        "is_late_season": "Late Season Decider",
                    }
                    for index in top_indices:
                        contribution = float(row_values[index])
                        if contribution <= 0:
                            continue
                        feature_name = FEATURE_COLUMNS[index]
                        reasons.append(
                            f"{feature_labels.get(feature_name, feature_name)} contributed +{contribution:.1f}"
                        )
                except Exception as exc:
                    logger.warning(f"SHAP explanation failed for fixture_id={fixture_id}: {exc}")

            reasons.extend(self._contextual_reasons(features, home_name, away_name))

            deduped_reasons: list[str] = []
            seen: set[str] = set()
            for reason in reasons:
                if reason in seen:
                    continue
                seen.add(reason)
                deduped_reasons.append(reason)

            scored_matches.append(
                {
                    "id": int(fixture_id),
                    "home_team": home_name,
                    "home_logo": teams.get("home", {}).get("logo"),
                    "away_team": away_name,
                    "away_logo": teams.get("away", {}).get("logo"),
                    "kickoff": str(fixture.get("date", "")),
                    "league": str(league.get("name", "Unknown League")),
                    "league_logo": league.get("logo"),
                    "score": final_score,
                    "probability": "",
                    "reason": ", ".join(deduped_reasons[:2]),
                }
            )

        scored_matches.sort(key=lambda item: item["score"], reverse=True)

        distribution = scipy.stats.norm(loc=26.8, scale=9.5)
        for match_data in scored_matches:
            percentile = int(distribution.cdf(match_data["score"]) * 100)
            percentile = min(99, max(1, percentile))
            if percentile % 10 == 1 and percentile != 11:
                suffix = "st"
            elif percentile % 10 == 2 and percentile != 12:
                suffix = "nd"
            elif percentile % 10 == 3 and percentile != 13:
                suffix = "rd"
            else:
                suffix = "th"
            match_data["probability"] = f"{percentile}{suffix} percentile"

        self._log_drift(scored_matches)
        return scored_matches

    def _log_drift(self, scored_matches: list[dict[str, Any]]) -> None:
        if not scored_matches:
            return

        try:
            scores = [match["score"] for match in scored_matches]
            mean_score = float(np.mean(scores))
            std_score = float(np.std(scores))
            variance = float(np.var(scores))

            log_dir = os.path.normpath(os.path.join(os.path.dirname(__file__), "..", "logs"))
            os.makedirs(log_dir, exist_ok=True)
            log_file = os.path.join(log_dir, "drift_monitor.log")

            with open(log_file, "a", encoding="utf-8") as handle:
                date_str = dt.datetime.now(dt.UTC).strftime("%Y-%m-%d")
                handle.write(
                    f"{date_str} - Count: {len(scores)}, Mean: {mean_score:.2f}, "
                    f"Std: {std_score:.2f}, Variance: {variance:.2f}\n"
                )
        except OSError as exc:
            logger.error(f"Failed to write drift log: {exc}")
