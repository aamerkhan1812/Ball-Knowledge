from __future__ import annotations

from pathlib import Path

from backend.services.preferences_store import UserPreferenceStore


def test_preference_store_upsert_and_read(tmp_path: Path) -> None:
    db_path = tmp_path / "prefs.db"
    store = UserPreferenceStore(str(db_path))

    profile_1 = store.upsert_profile(
        user_id="user-a",
        favorite_team="Arsenal",
        prefers_goals=True,
        prefers_tactical=False,
        increment_interactions=True,
    )
    assert profile_1["favorite_team"] == "Arsenal"
    assert profile_1["prefers_goals"] is True
    assert profile_1["prefers_tactical"] is False
    assert profile_1["interaction_count"] == 1

    profile_2 = store.upsert_profile(
        user_id="user-a",
        favorite_team=None,
        prefers_goals=None,
        prefers_tactical=True,
        increment_interactions=True,
    )
    assert profile_2["favorite_team"] == "Arsenal"
    assert profile_2["prefers_goals"] is True
    assert profile_2["prefers_tactical"] is True
    assert profile_2["interaction_count"] == 2

    loaded = store.get_profile("user-a")
    assert loaded == profile_2
