from __future__ import annotations

import datetime as dt
import json
import os
from typing import Any

from loguru import logger

try:
    import psycopg
except Exception:  # pragma: no cover - optional dependency fallback
    psycopg = None


def _normalize_database_url(url: str) -> str:
    value = str(url or "").strip()
    if value.startswith("postgres://"):
        return "postgresql://" + value[len("postgres://") :]
    return value


class PersistentStore:
    """Shared cache/budget persistence for file or Postgres backends."""

    def __init__(self, database_url: str | None = None) -> None:
        self.database_url = _normalize_database_url(database_url or "")
        self.use_postgres = bool(self.database_url) and psycopg is not None
        self.snapshots_table = "app_cache_snapshots"
        self.budget_table = "app_api_budget"

        if self.database_url and psycopg is None:
            logger.warning(
                "CACHE_DATABASE_URL is set but psycopg is unavailable. Falling back to file cache."
            )

        if self.use_postgres:
            self._ensure_postgres_schema()

    def _ensure_postgres_schema(self) -> None:
        try:
            with psycopg.connect(self.database_url, autocommit=True) as conn:  # type: ignore[arg-type]
                with conn.cursor() as cur:
                    cur.execute(
                        f"""
                        CREATE TABLE IF NOT EXISTS {self.snapshots_table} (
                            namespace TEXT PRIMARY KEY,
                            payload JSONB NOT NULL,
                            updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
                        )
                        """
                    )
                    cur.execute(
                        f"""
                        CREATE TABLE IF NOT EXISTS {self.budget_table} (
                            budget_date DATE PRIMARY KEY,
                            count INTEGER NOT NULL,
                            limit_value INTEGER NOT NULL,
                            updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
                        )
                        """
                    )
        except Exception as exc:
            logger.error(f"Failed to initialize Postgres cache schema: {exc}")
            self.use_postgres = False

    @staticmethod
    def _read_json_file(path: str) -> dict[str, Any] | None:
        if not path or not os.path.exists(path):
            return None
        try:
            with open(path, "r", encoding="utf-8") as handle:
                payload = json.load(handle)
        except (OSError, json.JSONDecodeError):
            return None
        if not isinstance(payload, dict):
            return None
        return payload

    @staticmethod
    def _write_json_file(path: str, payload: dict[str, Any]) -> None:
        if not path:
            return
        parent = os.path.dirname(path)
        if parent:
            os.makedirs(parent, exist_ok=True)
        with open(path, "w", encoding="utf-8") as handle:
            json.dump(payload, handle, ensure_ascii=False, indent=2)

    def load_map(self, namespace: str, file_paths: list[str] | None = None) -> dict[str, Any]:
        if self.use_postgres:
            payload = self._read_snapshot(namespace)
            if isinstance(payload, dict):
                return payload

        merged: dict[str, Any] = {}
        for path in file_paths or []:
            data = self._read_json_file(path)
            if isinstance(data, dict):
                merged.update(data)

        if self.use_postgres and merged:
            self.save_map(namespace, merged)

        return merged

    def save_map(
        self,
        namespace: str,
        payload: dict[str, Any],
        file_path: str | None = None,
    ) -> None:
        if self.use_postgres:
            self._write_snapshot(namespace, payload)
            return
        if file_path:
            self._write_json_file(file_path, payload)

    def _read_snapshot(self, namespace: str) -> dict[str, Any] | None:
        try:
            with psycopg.connect(self.database_url, autocommit=True) as conn:  # type: ignore[arg-type]
                with conn.cursor() as cur:
                    cur.execute(
                        f"SELECT payload FROM {self.snapshots_table} WHERE namespace = %s",
                        (namespace,),
                    )
                    row = cur.fetchone()
        except Exception as exc:
            logger.warning(f"Failed reading snapshot namespace={namespace}: {exc}")
            return None

        if not row:
            return None

        payload = row[0]
        if isinstance(payload, dict):
            return payload
        return None

    def _write_snapshot(self, namespace: str, payload: dict[str, Any]) -> None:
        try:
            with psycopg.connect(self.database_url, autocommit=True) as conn:  # type: ignore[arg-type]
                with conn.cursor() as cur:
                    cur.execute(
                        f"""
                        INSERT INTO {self.snapshots_table} (namespace, payload, updated_at)
                        VALUES (%s, %s::jsonb, NOW())
                        ON CONFLICT (namespace)
                        DO UPDATE SET payload = EXCLUDED.payload, updated_at = NOW()
                        """,
                        (namespace, json.dumps(payload, ensure_ascii=False)),
                    )
        except Exception as exc:
            logger.warning(f"Failed writing snapshot namespace={namespace}: {exc}")

    def load_budget_payload(self, file_path: str) -> dict[str, Any] | None:
        if self.use_postgres:
            try:
                with psycopg.connect(self.database_url, autocommit=True) as conn:  # type: ignore[arg-type]
                    with conn.cursor() as cur:
                        cur.execute(
                            f"""
                            SELECT budget_date, count, limit_value
                            FROM {self.budget_table}
                            ORDER BY budget_date DESC
                            LIMIT 1
                            """
                        )
                        row = cur.fetchone()
            except Exception as exc:
                logger.warning(f"Failed reading API budget from Postgres: {exc}")
                return None

            if not row:
                return None

            budget_date, count, limit_value = row
            return {
                "date": str(budget_date),
                "count": int(count),
                "max_daily_api_calls": int(limit_value),
            }

        return self._read_json_file(file_path)

    def save_budget_payload(self, payload: dict[str, Any], file_path: str) -> None:
        date_text = str(payload.get("date", "")).strip()
        count = int(payload.get("count", 0) or 0)
        limit_value = int(payload.get("max_daily_api_calls", 0) or 0)

        if self.use_postgres:
            if not date_text:
                return
            try:
                budget_date = dt.date.fromisoformat(date_text)
            except ValueError:
                return

            try:
                with psycopg.connect(self.database_url, autocommit=True) as conn:  # type: ignore[arg-type]
                    with conn.cursor() as cur:
                        cur.execute(
                            f"""
                            INSERT INTO {self.budget_table} (budget_date, count, limit_value, updated_at)
                            VALUES (%s, %s, %s, NOW())
                            ON CONFLICT (budget_date)
                            DO UPDATE SET
                                count = EXCLUDED.count,
                                limit_value = EXCLUDED.limit_value,
                                updated_at = NOW()
                            """,
                            (budget_date, count, limit_value),
                        )
            except Exception as exc:
                logger.warning(f"Failed writing API budget to Postgres: {exc}")
            return

        self._write_json_file(file_path, payload)

    def get_budget_count_for_date(
        self,
        date_text: str,
        file_path: str,
    ) -> int:
        if self.use_postgres:
            try:
                budget_date = dt.date.fromisoformat(date_text)
            except ValueError:
                return 0

            try:
                with psycopg.connect(self.database_url, autocommit=True) as conn:  # type: ignore[arg-type]
                    with conn.cursor() as cur:
                        cur.execute(
                            f"SELECT count FROM {self.budget_table} WHERE budget_date = %s",
                            (budget_date,),
                        )
                        row = cur.fetchone()
            except Exception as exc:
                logger.warning(f"Failed reading current-day budget count: {exc}")
                return 0

            if not row:
                return 0
            return int(row[0] or 0)

        payload = self._read_json_file(file_path)
        if not isinstance(payload, dict):
            return 0
        if str(payload.get("date", "")).strip() != date_text:
            return 0
        return int(payload.get("count", 0) or 0)

    def consume_budget(
        self,
        date_text: str,
        max_daily_api_calls: int,
        file_path: str,
    ) -> tuple[bool, int]:
        if self.use_postgres:
            return self._consume_budget_postgres(date_text, max_daily_api_calls)
        return self._consume_budget_file(date_text, max_daily_api_calls, file_path)

    def lock_budget(
        self,
        date_text: str,
        max_daily_api_calls: int,
        file_path: str,
    ) -> int:
        if self.use_postgres:
            return self._lock_budget_postgres(date_text, max_daily_api_calls)

        payload = self._read_json_file(file_path) or {}
        payload["date"] = date_text
        payload["count"] = int(max_daily_api_calls)
        payload["max_daily_api_calls"] = int(max_daily_api_calls)
        self._write_json_file(file_path, payload)
        return int(max_daily_api_calls)

    def _consume_budget_postgres(
        self,
        date_text: str,
        max_daily_api_calls: int,
    ) -> tuple[bool, int]:
        try:
            budget_date = dt.date.fromisoformat(date_text)
        except ValueError:
            return False, int(max_daily_api_calls)

        try:
            with psycopg.connect(self.database_url, autocommit=False) as conn:  # type: ignore[arg-type]
                with conn.cursor() as cur:
                    cur.execute(
                        f"DELETE FROM {self.budget_table} WHERE budget_date < (%s::date - INTERVAL '30 days')",
                        (budget_date,),
                    )
                    cur.execute(
                        f"""
                        SELECT count
                        FROM {self.budget_table}
                        WHERE budget_date = %s
                        FOR UPDATE
                        """,
                        (budget_date,),
                    )
                    row = cur.fetchone()

                    if not row:
                        cur.execute(
                            f"""
                            INSERT INTO {self.budget_table} (budget_date, count, limit_value, updated_at)
                            VALUES (%s, %s, %s, NOW())
                            """,
                            (budget_date, 1, max_daily_api_calls),
                        )
                        conn.commit()
                        return True, 1

                    current_count = max(0, int(row[0] or 0))
                    current_count = min(current_count, int(max_daily_api_calls))
                    if current_count >= int(max_daily_api_calls):
                        cur.execute(
                            f"""
                            UPDATE {self.budget_table}
                            SET count = %s, limit_value = %s, updated_at = NOW()
                            WHERE budget_date = %s
                            """,
                            (current_count, max_daily_api_calls, budget_date),
                        )
                        conn.commit()
                        return False, current_count

                    next_count = current_count + 1
                    cur.execute(
                        f"""
                        UPDATE {self.budget_table}
                        SET count = %s, limit_value = %s, updated_at = NOW()
                        WHERE budget_date = %s
                        """,
                        (next_count, max_daily_api_calls, budget_date),
                    )
                    conn.commit()
                    return True, next_count
        except Exception as exc:
            logger.warning(f"Failed consuming API budget in Postgres: {exc}")
            # Fail closed.
            return False, int(max_daily_api_calls)

    @staticmethod
    def _consume_budget_file(
        date_text: str,
        max_daily_api_calls: int,
        file_path: str,
    ) -> tuple[bool, int]:
        payload: dict[str, Any] = {}
        if os.path.exists(file_path):
            try:
                with open(file_path, "r", encoding="utf-8") as handle:
                    loaded = json.load(handle)
                if isinstance(loaded, dict):
                    payload = loaded
            except (OSError, json.JSONDecodeError):
                payload = {}

        if str(payload.get("date", "")).strip() != date_text:
            payload = {
                "date": date_text,
                "count": 0,
                "max_daily_api_calls": int(max_daily_api_calls),
            }

        count = max(0, int(payload.get("count", 0) or 0))
        if count >= int(max_daily_api_calls):
            payload["count"] = int(max_daily_api_calls)
            payload["max_daily_api_calls"] = int(max_daily_api_calls)
            PersistentStore._write_json_file(file_path, payload)
            return False, int(max_daily_api_calls)

        count += 1
        payload["count"] = count
        payload["max_daily_api_calls"] = int(max_daily_api_calls)
        PersistentStore._write_json_file(file_path, payload)
        return True, count

    def _lock_budget_postgres(self, date_text: str, max_daily_api_calls: int) -> int:
        try:
            budget_date = dt.date.fromisoformat(date_text)
        except ValueError:
            return int(max_daily_api_calls)

        try:
            with psycopg.connect(self.database_url, autocommit=False) as conn:  # type: ignore[arg-type]
                with conn.cursor() as cur:
                    cur.execute(
                        f"""
                        INSERT INTO {self.budget_table} (budget_date, count, limit_value, updated_at)
                        VALUES (%s, %s, %s, NOW())
                        ON CONFLICT (budget_date)
                        DO UPDATE SET
                            count = GREATEST({self.budget_table}.count, EXCLUDED.count),
                            limit_value = EXCLUDED.limit_value,
                            updated_at = NOW()
                        RETURNING count
                        """,
                        (budget_date, max_daily_api_calls, max_daily_api_calls),
                    )
                    row = cur.fetchone()
                conn.commit()
        except Exception as exc:
            logger.warning(f"Failed locking API budget in Postgres: {exc}")
            return int(max_daily_api_calls)

        return int(row[0] if row else max_daily_api_calls)
