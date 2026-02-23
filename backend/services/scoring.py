import os
import xgboost as xgb
import pandas as pd
import numpy as np
import shap
from loguru import logger
import datetime

class MatchScorer:
    def __init__(self):
        self.model = None
        self.model_path = os.path.join(os.path.dirname(__file__), "../../backend/ml_model_elite.json")
        self.explainer = None
        try:
            if os.path.exists(self.model_path):
                self.model = xgb.XGBRegressor()
                self.model.load_model(self.model_path)
                self.explainer = shap.TreeExplainer(self.model)
                logger.info("Loaded XGBoost Elite Ranking Model and SHAP Explainer.")
            else:
                logger.warning(f"Model not found at {self.model_path}. Using pure heuristic fallback.")
        except Exception as e:
            logger.error(f"Failed to load XGBoost model: {e}")

    def extract_features(self, match, api=None):
        """Extracts features for a single match dynamically using the Football API."""
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
        
        # Fetch real standings to compute dynamic features
        home_rank = 10
        away_rank = 10
        home_points = 0
        away_points = 0
        home_form_scorer = 0
        away_form_scorer = 0
        
        if api:
            season = league.get("season", 2023)
            standings = api.get_standings(league_id, season)
            if home_team in standings:
                home_rank = standings[home_team]["rank"]
                home_points = standings[home_team]["points"]
                h_form_str = standings[home_team]["form"]
                home_form_scorer = sum([3 if c == 'W' else 1 if c == 'D' else 0 for c in h_form_str[-5:]])
            if away_team in standings:
                away_rank = standings[away_team]["rank"]
                away_points = standings[away_team]["points"]
                a_form_str = standings[away_team]["form"]
                away_form_scorer = sum([3 if c == 'W' else 1 if c == 'D' else 0 for c in a_form_str[-5:]])
            
        rank_diff = abs(home_rank - away_rank)
        points_gap = abs(home_points - away_points)
        home_form = home_form_scorer
        away_form = away_form_scorer
        
        # is_late_season approx: Matchday > 28
        is_late_season = 1 if "regular season - 3" in round_name or "regular season - 29" in round_name or "final" in round_name else 0
        
        is_relegation_battle = 1 if (home_rank >= 15 and away_rank >= 15 and is_late_season) else 0
        is_title_race = 1 if (home_rank <= 3 and away_rank <= 3 and is_late_season) else 0
        
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

    def score_matches(self, matches, api=None, prefs=None):
        if prefs is None: prefs = {}
        fav_team = str(prefs.get("favorite_team", "")).lower()
        prefers_goals = prefs.get("prefers_goals", False)
        prefers_tactical = prefs.get("prefers_tactical", False)
        
        scored_matches = []
        for match in matches:
            features = self.extract_features(match, api)
            
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
                
            # 3. Ensemble Prediction => 0.85 * ML + 0.15 * Heuristic
            base_score = 0.85 * ml_score + 0.15 * rule_score
            
            # 4. Personalization Layer
            personalization_bonus = 0
            is_fav_team = False
            
            home_name_lower = match['teams']['home']['name'].lower()
            away_name_lower = match['teams']['away']['name'].lower()
            
            if fav_team and (fav_team in home_name_lower or fav_team in away_name_lower):
                personalization_bonus += 40
                is_fav_team = True
                
            if prefers_goals and (features["home_form"] >= 10 and features["away_form"] >= 10):
                personalization_bonus += 15
                
            if prefers_tactical and (features["rank_diff"] <= 3 and features["points_gap"] <= 5):
                personalization_bonus += 15
                
            final_score = int(np.clip(base_score + personalization_bonus, 0, 100))

            # Debug Logs
            print(f"--- MATCH: {match['teams']['home']['name']} vs {match['teams']['away']['name']} ---")
            print(f"Features: {features}")
            print(f"ML Score: {ml_score:.2f} | Heuristic Score: {rule_score} | Bonus: {personalization_bonus} | Final: {final_score}")
            print("-" * 50)

            # 5. Reason generation (SHAP Explainability Layer)
            reason = []
            
            # Personalization override for driving reason
            if is_fav_team:
                reason.append("⭐ Your Favorite Team")
                
            if self.explainer:
                shap_values = self.explainer.shap_values(df_features[cols])
                # Find top 2 indices with the highest absolute shap value contribution
                top_indices = np.argsort(-np.abs(shap_values[0]))[:2]
                
                # Human-readable mapping of features
                feature_descriptions = {
                    "is_derby": "Historic Rivalry Derby",
                    "is_knockout": "High-Stakes Knockout Stage",
                    "is_title_race": "Late-Season Title Clash",
                    "rank_diff": "Close Bracket Proximity",
                    "points_gap": "Tight Points Differential",
                    "home_form": "Elite Home Form",
                    "away_form": "Elite Away Form",
                    "league_weight": "Premium European Fixture",
                    "is_relegation_battle": "Relegation Survival Battle",
                    "is_late_season": "Late Season Decider"
                }
                
                for idx in top_indices:
                    feat_name = cols[idx]
                    contribution = shap_values[0][idx]
                    # Only add if it's a positive driver of hype, or just list the driving factors
                    if contribution > 0:
                        reason.append(feature_descriptions.get(feat_name, feat_name))
            
            # Fallback if SHAP didn't find positive drivers
            if not reason:
                if features["is_derby"]: reason.append("Historic Derby")
                elif features["is_knockout"]: reason.append("Knockout Stage")
                elif features.get("is_title_race", 0): reason.append("Title Race")
                else: reason.append("Premium League Game")
            
            # Deduplicate reasons
            reason = list(set(reason))
            
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
                "reason": ", ".join(reason[:2]) # Max 2 reasons
            }
            scored_matches.append(match_data)
            
        scored_matches.sort(key=lambda x: x["score"], reverse=True)
        
        # 5. Drift Monitoring Logging
        try:
            if scored_matches:
                scores = [m["score"] for m in scored_matches]
                mean_score = np.mean(scores)
                std_score = np.std(scores)
                log_dir = os.path.join(os.path.dirname(__file__), "../../backend/logs")
                os.makedirs(log_dir, exist_ok=True)
                log_file = os.path.join(log_dir, "drift_monitor.log")
                with open(log_file, "a") as f:
                    date_str = datetime.datetime.now().strftime("%Y-%m-%d")
                    f.write(f"{date_str} - Count: {len(scores)}, Mean: {mean_score:.2f}, Std/Variance: {std_score:.2f}\n")
        except Exception as e:
            logger.error(f"Failed to log drift monitoring: {e}")
            
        return scored_matches
