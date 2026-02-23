import os
import xgboost as xgb
import pandas as pd
from loguru import logger

class MatchScorer:
    def __init__(self):
        self.model = None
        self.model_path = os.path.join(os.path.dirname(__file__), "../../backend/ml_model_elite.json")
        try:
            if os.path.exists(self.model_path):
                self.model = xgb.XGBRegressor()
                self.model.load_model(self.model_path)
                logger.info("Loaded XGBoost Elite Ranking Model.")
            else:
                logger.warning(f"Model not found at {self.model_path}. Using pure heuristic fallback.")
        except Exception as e:
            logger.error(f"Failed to load XGBoost model: {e}")

    def extract_features(self, match):
        """Extracts features for a single match for both ML and heuristic usage."""
        league = match.get("league", {})
        teams = match.get("teams", {})
        
        league_id = league.get("id", 0)
        round_name = str(league.get("round", "")).lower()
        home_team = teams.get("home", {}).get("name", "Unknown")
        away_team = teams.get("away", {}).get("name", "Unknown")
        
        league_weight = 1.5 if league_id == 2 else 1.0
        is_knockout = 1 if any(x in round_name for x in ["knockout", "16", "quarter", "semi", "final"]) and "group" not in round_name else 0
        
        famous_derbies = [
            ("Real Madrid", "Barcelona"), ("Manchester City", "Manchester United"),
            ("Arsenal", "Tottenham"), ("Inter", "AC Milan"),
            ("Bayern Munich", "Borussia Dortmund"), ("Liverpool", "Manchester United")
        ]
        is_derby = 1 if any((t1 in home_team and t2 in away_team) or (t2 in home_team and t1 in away_team) for t1, t2 in famous_derbies) else 0
        
        # In a real production environment, you fetch the current standings immediately before this:
        # For inference without active standings API, we mock the dynamic values to evaluate the architecture flow:
        rank_diff = 5
        points_gap = 10
        home_form = 10 # roughly 3 wins, 1 draw
        away_form = 10
        is_relegation_battle = 0
        is_title_race = 0
        is_late_season = 0
        
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
            "is_late_season": is_late_season
        }

    def score_matches(self, matches):
        scored_matches = []
        for match in matches:
            features = self.extract_features(match)
            
            # 1. Rule-Based Score (Heuristic)
            rule_score = (features["is_derby"] * 25) + (features["is_knockout"] * 35) + \
                         (features["is_title_race"] * 30)
                         
            if rule_score == 0: 
                rule_score = 10 # Base for top leagues
                
            # 2. ML Predicted Score
            ml_score = 0
            if self.model:
                df_features = pd.DataFrame([features])
                # Ensure correct column order matching train_model.py exactly
                cols = ["league_weight", "is_knockout", "is_derby", "rank_diff", "points_gap", "home_form", "away_form", "is_relegation_battle", "is_title_race", "is_late_season"]
                ml_score = float(self.model.predict(df_features[cols])[0])
            else:
                ml_score = rule_score # Fallback
                
            # 3. Ensemble Prediction => 0.7 * ML + 0.3 * Heuristic
            final_score = int(np.clip(0.7 * ml_score + 0.3 * rule_score, 0, 100))

            
            # Reason generation
            reason = []
            if features["is_derby"]: reason.append("Historic Derby")
            if features["is_knockout"]: reason.append("Knockout Stage")
            if features["is_top4_clash"]: reason.append("Top 4 Clash")
            if not reason: reason.append("Premium League Game")
            
            match_data = {
                "id": match["fixture"]["id"],
                "home_team": match["teams"]["home"]["name"],
                "home_logo": match["teams"]["home"]["logo"],
                "away_team": match["teams"]["away"]["name"],
                "away_logo": match["teams"]["away"]["logo"],
                "kickoff": match["fixture"]["date"],
                "league": match["league"]["name"],
                "league_logo": match["league"]["logo"],
                "score": final_score,
                "reason": ", ".join(reason)
            }
            scored_matches.append(match_data)
            
        scored_matches.sort(key=lambda x: x["score"], reverse=True)
        return scored_matches
