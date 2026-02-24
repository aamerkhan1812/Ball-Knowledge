from __future__ import annotations

import datetime as dt
import os
import sqlite3
import threading
from typing import Any


class UserPreferenceStore:
    def __init__(self, db_path: str) -> None:
        self.db_path = db_path
        self._lock = threading.Lock()
        self._ensure_schema()

    def _connect(self) -> sqlite3.Connection:
        return sqlite3.connect(self.db_path, check_same_thread=False)

    def _ensure_schema(self) -> None:
        db_dir = os.path.dirname(self.db_path)
        if db_dir:
            os.makedirs(db_dir, exist_ok=True)

        conn = self._connect()
        try:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS user_preferences (
                    user_id TEXT PRIMARY KEY,
                    favorite_team TEXT NOT NULL DEFAULT '',
                    prefers_goals INTEGER NOT NULL DEFAULT 0,
                    prefers_tactical INTEGER NOT NULL DEFAULT 0,
                    interaction_count INTEGER NOT NULL DEFAULT 0,
                    updated_at TEXT NOT NULL
                )
                """
            )
            conn.commit()
        finally:
            conn.close()

    def get_profile(self, user_id: str) -> dict[str, Any]:
        with self._lock:
            conn = self._connect()
            try:
                row = conn.execute(
                    """
                    SELECT favorite_team, prefers_goals, prefers_tactical, interaction_count
                    FROM user_preferences
                    WHERE user_id = ?
                    """,
                    (user_id,),
                ).fetchone()
            finally:
                conn.close()

        if not row:
            return {
                "favorite_team": "",
                "prefers_goals": False,
                "prefers_tactical": False,
                "interaction_count": 0,
            }

        return {
            "favorite_team": row[0],
            "prefers_goals": bool(row[1]),
            "prefers_tactical": bool(row[2]),
            "interaction_count": int(row[3]),
        }

    def upsert_profile(
        self,
        user_id: str,
        favorite_team: str | None = None,
        prefers_goals: bool | None = None,
        prefers_tactical: bool | None = None,
        increment_interactions: bool = True,
    ) -> dict[str, Any]:
        current = self.get_profile(user_id)

        if favorite_team is not None:
            current["favorite_team"] = favorite_team.strip()
        if prefers_goals is not None:
            current["prefers_goals"] = bool(prefers_goals)
        if prefers_tactical is not None:
            current["prefers_tactical"] = bool(prefers_tactical)
        if increment_interactions:
            current["interaction_count"] += 1

        updated_at = dt.datetime.now(dt.UTC).isoformat()
        with self._lock:
            conn = self._connect()
            try:
                conn.execute(
                    """
                    INSERT INTO user_preferences (
                        user_id, favorite_team, prefers_goals, prefers_tactical, interaction_count, updated_at
                    ) VALUES (?, ?, ?, ?, ?, ?)
                    ON CONFLICT(user_id) DO UPDATE SET
                        favorite_team=excluded.favorite_team,
                        prefers_goals=excluded.prefers_goals,
                        prefers_tactical=excluded.prefers_tactical,
                        interaction_count=excluded.interaction_count,
                        updated_at=excluded.updated_at
                    """,
                    (
                        user_id,
                        current["favorite_team"],
                        int(current["prefers_goals"]),
                        int(current["prefers_tactical"]),
                        int(current["interaction_count"]),
                        updated_at,
                    ),
                )
                conn.commit()
            finally:
                conn.close()

        return current
