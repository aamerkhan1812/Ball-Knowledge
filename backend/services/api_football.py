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
