import os
import requests
import pandas as pd
import time
from datetime import datetime, timedelta
from pytrends.request import TrendReq
from dotenv import load_dotenv
from loguru import logger

load_dotenv("backend/.env")
API_KEY = os.getenv("API_SPORTS_KEY")
HEADERS = {
    "x-rapidapi-host": "v3.football.api-sports.io",
    "x-rapidapi-key": API_KEY
}

TARGET_LEAGUES = {
    2: "UEFA Champions League",
    39: "Premier League",
    140: "La Liga",
    78: "Bundesliga",
    135: "Serie A"
}
SEASONS = [2021, 2022, 2023]

pytrends = TrendReq(hl='en-US', tz=360)

def fetch_historical_fixtures():
    all_matches = []
    for league_id in TARGET_LEAGUES.keys():
        for season in SEASONS:
            logger.info(f"Fetching {TARGET_LEAGUES[league_id]} fixtures for {season}")
            url = f"https://v3.football.api-sports.io/fixtures"
            params = {"league": league_id, "season": season}
            try:
                response = requests.get(url, headers=HEADERS, params=params)
                data = response.json()
                if "response" in data:
                    all_matches.extend(data["response"])
                time.sleep(1) 
            except Exception as e:
                logger.error(f"Error fetching matches: {e}")
    return all_matches

def fetch_standings(league_id, season):
    """Fetch final standings for a league to approximate team strength for the season."""
    url = f"https://v3.football.api-sports.io/standings"
    params = {"league": league_id, "season": season}
    try:
        response = requests.get(url, headers=HEADERS, params=params)
        data = response.json()
        if "response" in data and len(data["response"]) > 0:
            standings = data["response"][0]["league"]["standings"][0]
            # Map team string to their rank and points
            team_stats = {}
            for s in standings:
                team_name = s["team"]["name"]
                team_stats[team_name] = {
                    "rank": s["rank"],
                    "points": s["points"],
                    "form": s.get("form", "?????") # Last 5 form string
                }
            return team_stats
    except Exception as e:
        logger.error(f"Error fetching standings: {e}")
    return {}

def extract_competitive_features(match_list):
    """Extracts genuine competitive intensity features."""
    df_data = []
    
    # Cache standings to avoid hitting API repeatedly
    standings_cache = {}
    for league_id in TARGET_LEAGUES.keys():
        for season in SEASONS:
            standings_cache[(league_id, season)] = fetch_standings(league_id, season)
            time.sleep(1)
            
    for match in match_list:
        try:
            league_id = match["league"]["id"]
            season = match["league"]["season"]
            round_name = str(match["league"]["round"]).lower()
            date = match["fixture"]["date"]
            
            home_team = match["teams"]["home"]["name"]
            away_team = match["teams"]["away"]["name"]
            
            # Base Features
            is_knockout = 1 if any(x in round_name for x in ["knockout", "16", "quarter", "semi", "final"]) and "group" not in round_name else 0
            league_weight = 1.5 if league_id == 2 else 1.0
            
            # Late season flag (Matchday > 28 usually)
            is_late_season = 1 if "regular season - 3" in round_name or "final" in round_name else 0
            
            famous_derbies = [
                ("Real Madrid", "Barcelona"), ("Manchester City", "Manchester United"),
                ("Arsenal", "Tottenham"), ("Inter", "AC Milan"),
                ("Bayern Munich", "Borussia Dortmund"), ("Liverpool", "Manchester United")
            ]
            is_derby = 1 if any((t1 in home_team and t2 in away_team) or (t2 in home_team and t1 in away_team) for t1, t2 in famous_derbies) else 0
            
            # Competitive Features (Using end of season standings as an approximation for the historical match's competitive intensity)
            s_data = standings_cache.get((league_id, season), {})
            h_stats = s_data.get(home_team, {"rank": 10, "points": 40, "form": "WLLDW"})
            a_stats = s_data.get(away_team, {"rank": 10, "points": 40, "form": "WLLDW"})
            
            h_rank = h_stats["rank"]
            a_rank = a_stats["rank"]
            rank_diff = abs(h_rank - a_rank)
            points_gap = abs(h_stats["points"] - a_stats["points"])
            
            # Form translation (W=3, D=1, L=0)
            def calc_form(form_str):
                score = 0
                for char in form_str[-5:]:
                    if char == 'W': score += 3
                    elif char == 'D': score += 1
                return score
                
            h_form = calc_form(h_stats["form"])
            a_form = calc_form(a_stats["form"])
            
            is_relegation_battle = 1 if (h_rank >= 15 and a_rank >= 15 and is_late_season) else 0
            is_title_race = 1 if (h_rank <= 3 and a_rank <= 3 and is_late_season) else 0
            
            df_data.append({
                "match_id": match["fixture"]["id"],
                "date": date[:10],
                "season": season,
                "league_id": league_id,
                "home_team": home_team,
                "away_team": away_team,
                "league_weight": league_weight,
                "is_knockout": is_knockout,
                "is_derby": is_derby,
                "rank_diff": rank_diff,
                "points_gap": points_gap,
                "home_form": h_form,
                "away_form": a_form,
                "is_relegation_battle": is_relegation_battle,
                "is_title_race": is_title_race,
                "is_late_season": is_late_season,
                "search_term": f"{home_team} vs {away_team}"
            })
        except Exception as e:
            continue
            
    return pd.DataFrame(df_data)

def fetch_google_trends_batched(df):
    """
    Batches matches by week and queries Google Trends with 5 terms at a time.
    Uses 'El Clasico' or 'Messi' as a constant anchor term to normalize scores across different batches.
    """
    if df.empty:
        logger.error("DataFrame is empty! No matches were fetched to process for trends.")
        return df
        
    df["date"] = pd.to_datetime(df["date"])
    # Sort by date so we query matches happening in the same week together
    df = df.sort_values(by="date")
    
    # We will just process the first 100 matches in this script as a proof-of-concept
    # In production, you would run this over a few days for the entire dataset
    df_subset = df.head(100).copy()
    hype_scores = []
    
    ANCHOR_TERM = "Football"
    
    # Batch into groups of 4 (leaving 1 slot for our anchor term)
    batch_size = 4
    for i in range(0, len(df_subset), batch_size):
        batch = df_subset.iloc[i:i+batch_size]
        terms = batch["search_term"].tolist()
        
        query_list = [ANCHOR_TERM] + terms
        # Use a wide timeframe covering the matches in this batch
        min_date = batch["date"].min() - timedelta(days=3)
        max_date = batch["date"].max() + timedelta(days=3)
        timeframe = f"{min_date.strftime('%Y-%m-%d')} {max_date.strftime('%Y-%m-%d')}"
        
        logger.info(f"Querying Trends for: {terms} | Timeframe: {timeframe}")
        
        try:
            pytrends.build_payload(query_list, cat=0, timeframe=timeframe, geo='')
            trends_df = pytrends.interest_over_time()
            
            if not trends_df.empty:
                # Find the peak interest for the anchor and normalize
                anchor_peak = trends_df[ANCHOR_TERM].max()
                if anchor_peak == 0: anchor_peak = 1 # Prevent division by zero
                
                for term in terms:
                    if term in trends_df.columns:
                        term_peak = trends_df[term].max()
                        normalized_score = (term_peak / anchor_peak) * 100
                        hype_scores.append(normalized_score)
                    else:
                        hype_scores.append(0)
            else:
                hype_scores.extend([0]*len(terms))
                
            time.sleep(5) # Crucial sleep to prevent IP bans
            
        except Exception as e:
            logger.warning(f"Trends API Error: {e}")
            hype_scores.extend([0]*len(terms))
            time.sleep(15) # Longer backoff
            
    df_subset["target_hype"] = hype_scores
    return df_subset

if __name__ == "__main__":
    logger.info("Starting ADVANCED historical data collection...")
    # Step 1: Fetch Matches
    raw_matches = fetch_historical_fixtures()
    logger.info(f"Fetched {len(raw_matches)} matches.")
    
    # Step 2: Extract REAL Competitive Features (Fetching standings)
    df = extract_competitive_features(raw_matches)
    logger.info(f"Extracted competitive features for {len(df)} matches.")
    
    # Step 3: Batched Google Trends Extraction
    logger.info("Starting Batched Google Trends extraction (Proof of Concept, first 100 matches)...")
    df_scored = fetch_google_trends_batched(df)
    
    os.makedirs("data", exist_ok=True)
    df_scored.to_csv("data/historical_matches_elite.csv", index=False)
    logger.info("Saved true elite dataset to data/historical_matches_elite.csv")
