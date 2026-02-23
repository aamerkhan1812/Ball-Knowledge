import os
import requests
import datetime
from dotenv import load_dotenv

load_dotenv()

class FootballAPI:
    def __init__(self):
        self.api_key = os.getenv("API_SPORTS_KEY")
        self.base_url = "https://v3.football.api-sports.io"
        self.headers = {
            "x-rapidapi-host": "v3.football.api-sports.io",
            "x-rapidapi-key": self.api_key
        }
        
        # High priority leagues mapping (League ID)
        self.target_leagues = [
            2,    # UEFA Champions League
            39,   # Premier League
            140,  # La Liga
            78,   # Bundesliga
            135,  # Serie A
            1,    # World Cup
            4,    # Euro Championship
            9,    # Copa America
        ]
        
        self.standings_cache = {}

    def get_standings(self, league_id: int, season: int):
        """Fetch and cache standings for a given league and season to prevent rate limits."""
        cache_key = f"{league_id}_{season}"
        if cache_key in self.standings_cache:
            return self.standings_cache[cache_key]
            
        url = f"{self.base_url}/standings"
        querystring = {"league": league_id, "season": season}
        
        try:
            response = requests.get(url, headers=self.headers, params=querystring)
            response.raise_for_status()
            data = response.json()
            
            team_stats = {}
            if "response" in data and len(data["response"]) > 0:
                standings = data["response"][0]["league"]["standings"][0]
                for s in standings:
                    team_name = s["team"]["name"]
                    team_stats[team_name] = {
                        "rank": s["rank"],
                        "points": s["points"],
                        "form": s.get("form", "") or ""
                    }
                    
            self.standings_cache[cache_key] = team_stats
            return team_stats
        except Exception as e:
            return {}
            
    def get_fixtures_by_date(self, date: str = None):
        """Fetch fixtures for a given date (YYYY-MM-DD). Defaults to today."""
        if not date:
            date = datetime.datetime.now().strftime("%Y-%m-%d")
            
        url = f"{self.base_url}/fixtures"
        querystring = {"date": date}
        
        try:
            response = requests.get(url, headers=self.headers, params=querystring)
            response.raise_for_status()
            data = response.json()
            
            # Filter matches by our target leagues to save processing
            if "response" in data:
                filtered_matches = [
                    match for match in data["response"] 
                    if match["league"]["id"] in self.target_leagues
                ]
                data["response"] = filtered_matches
                
            return data
        except requests.exceptions.RequestException as e:
            return {"errors": str(e), "response": []}
