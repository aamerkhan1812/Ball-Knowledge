from __future__ import annotations

import pytest

from backend.services.scoring import MatchScorer, _detect_derby, _detect_knockout


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

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


def _make_match(
    home: str,
    away: str,
    league_id: int = 39,
    round_name: str = "Regular Season - 26",
) -> dict:
    return {
        "league": {"id": league_id, "season": 2024, "round": round_name},
        "teams": {"home": {"name": home}, "away": {"name": away}},
    }


# ---------------------------------------------------------------------------
# Original test (unchanged)
# ---------------------------------------------------------------------------

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


# ---------------------------------------------------------------------------
# Derby detection — exact matching
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("home,away,expected_label_fragment", [
    # El Clasico
    ("Real Madrid", "Barcelona", "Clásico"),
    ("Barcelona", "Real Madrid", "Clásico"),
    # Der Klassiker
    ("Bayern Munich", "Borussia Dortmund", "Klassiker"),
    # Manchester Derby
    ("Manchester City", "Manchester United", "Manchester Derby"),
    # North London Derby
    ("Arsenal", "Tottenham", "North London"),
    # Milan Derby
    ("Inter", "AC Milan", "Madonnina"),
    # Internazionale full name variant
    ("FC Internazionale", "AC Milan", "Madonnina"),
    # Madrid Derby
    ("Real Madrid", "Atletico Madrid", "Madrid Derby"),
    # Old Firm
    ("Celtic", "Rangers", "Old Firm"),
])
def test_detect_derby_known_rivalries(home: str, away: str, expected_label_fragment: str) -> None:
    is_derby, label = _detect_derby(home, away)
    assert is_derby, f"Expected derby for {home} vs {away}"
    assert expected_label_fragment.lower() in label.lower(), (
        f"Expected '{expected_label_fragment}' in '{label}'"
    )


@pytest.mark.parametrize("home,away", [
    # "Inter Miami" must NOT trigger the Milan derby
    ("Inter Miami", "AC Milan"),
    ("AC Milan", "Inter Miami"),
    # Generic club names
    ("FC United", "City FC"),
    ("Real Betis", "Barcelona"),   # not a classic derby entry
])
def test_detect_derby_no_false_positives(home: str, away: str) -> None:
    is_derby, _ = _detect_derby(home, away)
    assert not is_derby, f"Expected NO derby for {home} vs {away}"


# ---------------------------------------------------------------------------
# Knockout round detection — UCL and domestic
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("round_name,league_id,expected_label_fragment", [
    ("Round of 16 - Leg 1", 2, "UCL"),
    ("Quarter-Finals", 2, "UCL Quarter-Final"),
    ("Semi-Finals", 2, "UCL Semi-Final"),
    ("Final", 2, "UCL Final"),
    ("Knockout Round Play-offs", 2, "UCL"),
    # Domestic cup
    ("Semi-Final", 39, "Semi-Final"),
    ("Final", 140, "Final"),
    ("Quarter-Final", 78, "Quarter-Final"),
])
def test_detect_knockout_known_stages(
    round_name: str, league_id: int, expected_label_fragment: str
) -> None:
    is_ko, label = _detect_knockout(round_name, league_id)
    assert is_ko, f"Expected knockout for round='{round_name}' league={league_id}"
    assert expected_label_fragment.lower() in label.lower(), (
        f"Expected '{expected_label_fragment}' in '{label}'"
    )


@pytest.mark.parametrize("round_name,league_id", [
    ("Regular Season - 26", 39),
    ("Group Stage - 3", 2),
    ("League Stage", 2),
    ("Regular Season - 1", 140),
])
def test_detect_knockout_non_knockout_rounds(round_name: str, league_id: int) -> None:
    is_ko, label = _detect_knockout(round_name, league_id)
    assert not is_ko, f"Expected non-knockout for round='{round_name}'"
    assert label == "", f"Expected empty label, got '{label}'"


# ---------------------------------------------------------------------------
# Scoring integration — must_watch_tier bonus
# ---------------------------------------------------------------------------

def test_ucl_knockout_scores_higher_than_regular_league_match() -> None:
    scorer = MatchScorer()

    ucl_ko = {
        "fixture": {"id": 1001, "date": "2025-03-12T20:00:00+00:00"},
        "league": {"id": 2, "name": "UEFA Champions League", "season": 2024,
                   "round": "Round of 16 - Leg 1", "logo": None},
        "teams": {
            "home": {"name": "Real Madrid", "logo": None, "id": 541},
            "away": {"name": "Manchester City", "logo": None, "id": 50},
        },
    }

    pl_regular = {
        "fixture": {"id": 1002, "date": "2025-03-12T15:00:00+00:00"},
        "league": {"id": 39, "name": "Premier League", "season": 2024,
                   "round": "Regular Season - 28", "logo": None},
        "teams": {
            "home": {"name": "Brentford", "logo": None, "id": 55},
            "away": {"name": "Wolverhampton", "logo": None, "id": 39},
        },
    }

    results = scorer.score_matches([ucl_ko, pl_regular])
    assert len(results) == 2
    ucl_result = next(r for r in results if r["id"] == 1001)
    pl_result = next(r for r in results if r["id"] == 1002)
    assert ucl_result["score"] > pl_result["score"], (
        f"UCL KO ({ucl_result['score']}) should outscore PL regular ({pl_result['score']})"
    )


def test_el_clasico_scores_higher_than_mid_table_match() -> None:
    scorer = MatchScorer()

    el_clasico = {
        "fixture": {"id": 2001, "date": "2025-03-23T19:00:00+00:00"},
        "league": {"id": 140, "name": "La Liga", "season": 2024,
                   "round": "Regular Season - 29", "logo": None},
        "teams": {
            "home": {"name": "Real Madrid", "logo": None, "id": 541},
            "away": {"name": "Barcelona", "logo": None, "id": 529},
        },
    }

    mid_table = {
        "fixture": {"id": 2002, "date": "2025-03-23T17:00:00+00:00"},
        "league": {"id": 140, "name": "La Liga", "season": 2024,
                   "round": "Regular Season - 29", "logo": None},
        "teams": {
            "home": {"name": "Celta Vigo", "logo": None, "id": 558},
            "away": {"name": "Getafe", "logo": None, "id": 546},
        },
    }

    results = scorer.score_matches([el_clasico, mid_table])
    clasico_result = next(r for r in results if r["id"] == 2001)
    mid_result = next(r for r in results if r["id"] == 2002)
    assert clasico_result["score"] > mid_result["score"], (
        f"El Clasico ({clasico_result['score']}) should outscore mid-table ({mid_result['score']})"
    )


def test_inter_miami_does_not_trigger_milan_derby_bonus() -> None:
    scorer = MatchScorer()

    miami_game = {
        "fixture": {"id": 3001, "date": "2025-05-10T23:00:00+00:00"},
        "league": {"id": 39, "name": "Premier League", "season": 2024,
                   "round": "Regular Season - 36", "logo": None},
        "teams": {
            "home": {"name": "Inter Miami", "logo": None, "id": 9999},
            "away": {"name": "AC Milan", "logo": None, "id": 489},
        },
    }

    results = scorer.score_matches([miami_game])
    assert len(results) == 1
    result = results[0]
    # The reason should NOT contain "Derby" or "Madonnina"
    reason_lower = result["reason"].lower()
    assert "madonnina" not in reason_lower, "Inter Miami should not trigger Milan derby"
    assert "derby della" not in reason_lower


def test_reason_field_shows_up_to_three_labels() -> None:
    scorer = MatchScorer()
    match = {
        "fixture": {"id": 4001, "date": "2025-04-08T19:00:00+00:00"},
        "league": {"id": 2, "name": "UEFA Champions League", "season": 2024,
                   "round": "Quarter-Finals", "logo": None},
        "teams": {
            "home": {"name": "Real Madrid", "logo": None, "id": 541},
            "away": {"name": "Barcelona", "logo": None, "id": 529},
        },
    }
    results = scorer.score_matches([match])
    assert len(results) == 1
    reason_parts = [p.strip() for p in results[0]["reason"].split(",") if p.strip()]
    assert 1 <= len(reason_parts) <= 3, f"Reason should have 1-3 parts, got: {results[0]['reason']}"
