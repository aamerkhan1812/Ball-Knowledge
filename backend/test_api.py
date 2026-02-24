import json
import os

import requests

base_url = os.getenv("MATCH_API_BASE_URL", "http://127.0.0.1:8000")

try:
    response = requests.get(f"{base_url}/api/matches/today", timeout=15)
    response.raise_for_status()
    print(json.dumps(response.json(), indent=2))
except requests.exceptions.RequestException as exc:
    print(f"Error: {exc}")
