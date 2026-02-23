from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from services.api_football import FootballAPI
from services.scoring import MatchScorer
import os
from typing import List, Dict

app = FastAPI(title="Match Recommender API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

api = FootballAPI()
scorer = MatchScorer()

@app.get("/api/matches/today")
async def get_todays_matches(date: str = None):
    # If no date is provided, FootballAPI will default to today
    fixtures = api.get_fixtures_by_date(date)
    
    if "errors" in fixtures and fixtures["errors"]:
        return {"error": "API Error", "details": fixtures["errors"]}
    
    matches = fixtures.get("response", [])
    
    # Process and score matches
    scored_matches = scorer.score_matches(matches)
    
    return {"status": "success", "total_matches_checked": len(matches), "matches": scored_matches}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
