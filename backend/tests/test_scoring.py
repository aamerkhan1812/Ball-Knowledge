from __future__ import annotations

from backend.services.scoring import MatchScorer


class FakeApi:
    def get_standings(  # noqa: ARG002
        self,
        league_id: int,
        season: int,
        allow_live_refresh: bool = True,
    ):
        return {
            "arsenal": {"rank": 1, "points": 80, "form": "WWWWW"},
            "chelsea": {"rank": 10, "points": 45, "form": "LDLWW"},
        }


def test_extract_features_uses_case_insensitive_standings_lookup() -> None:
    scorer = MatchScorer()
    match = {
        "league": {"id": 39, "season": 2023, "round": "Regular Season - 30"},
        "teams": {"home": {"name": "Arsenal"}, "away": {"name": "Chelsea"}},
    }

    features = scorer.extract_features(match, api=FakeApi())
    assert features["rank_diff"] == 9
    assert features["points_gap"] == 35
    assert features["home_form"] == 15
    assert features["away_form"] == 7
    assert features["is_late_season"] == 1
