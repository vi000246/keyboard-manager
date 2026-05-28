"""Repository layer — stdlib sqlite3 abstractions over events / apps / snapshots.

Each repo opens its own short-lived connection per call. SQLite handles this
fine for our single-writer / few-readers usage; we don't need a connection pool.
"""
from __future__ import annotations

import sqlite3
from contextlib import contextmanager
from pathlib import Path

# Kind → SQL fragment selecting which rows count for top_n queries.
_KIND_SQL: dict[str, str] = {
    "single": "modifiers = ''",
    "mod":    "modifiers != ''",
    "all":    "1=1",
}


class _BaseRepo:
    def __init__(self, db_path: Path):
        self.db_path = Path(db_path)

    @contextmanager
    def _conn(self):
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        try:
            yield conn
            conn.commit()
        finally:
            conn.close()


class SnapshotRepo(_BaseRepo):
    """Snapshots record the start of an import or capture session."""

    def create(self, ts: int, source: str, notes: str | None = None) -> int:
        with self._conn() as c:
            cur = c.execute(
                "INSERT INTO snapshots(ts, source, notes) VALUES(?,?,?)",
                (ts, source, notes),
            )
            return cur.lastrowid

    def get(self, sid: int) -> dict | None:
        with self._conn() as c:
            row = c.execute(
                "SELECT * FROM snapshots WHERE id=?", (sid,)
            ).fetchone()
            return dict(row) if row else None


class AppsRepo(_BaseRepo):
    """App bundle ID → display name + bucket. Upsert-preserving."""

    def upsert(
        self,
        bundle_id: str,
        display_name: str | None,
        bucket: str | None,
        ts: int,
    ) -> None:
        with self._conn() as c:
            c.execute(
                """
                INSERT INTO apps(bundle_id, display_name, bucket, first_seen_ts, last_seen_ts)
                VALUES(?, ?, ?, ?, ?)
                ON CONFLICT(bundle_id) DO UPDATE SET
                  display_name = COALESCE(excluded.display_name, apps.display_name),
                  bucket       = COALESCE(excluded.bucket,       apps.bucket),
                  last_seen_ts = MAX(apps.last_seen_ts, excluded.last_seen_ts)
                """,
                (bundle_id, display_name, bucket, ts, ts),
            )

    def get(self, bundle_id: str) -> dict | None:
        with self._conn() as c:
            row = c.execute(
                "SELECT * FROM apps WHERE bundle_id=?", (bundle_id,)
            ).fetchone()
            return dict(row) if row else None

    def all(self) -> list[dict]:
        with self._conn() as c:
            rows = c.execute(
                "SELECT * FROM apps ORDER BY bundle_id"
            ).fetchall()
            return [dict(r) for r in rows]

    def all_with_counts(self) -> list[dict]:
        """Return every known app plus its total event count, sorted DESC by count.

        Used by the Stats dropdown to order by usage and to show a count badge.
        Apps with zero events still appear (after the counted ones) so newly
        seen bundles aren't hidden until they accumulate stats.
        """
        with self._conn() as c:
            rows = c.execute(
                """
                SELECT a.bundle_id,
                       a.display_name,
                       a.bucket,
                       a.first_seen_ts,
                       a.last_seen_ts,
                       COALESCE(e.total, 0) AS total_count
                FROM apps a
                LEFT JOIN (
                  SELECT app_bundle, SUM(count) AS total
                  FROM events
                  GROUP BY app_bundle
                ) e ON e.app_bundle = a.bundle_id
                ORDER BY total_count DESC, a.bundle_id ASC
                """
            ).fetchall()
            return [dict(r) for r in rows]


class StatsRepo(_BaseRepo):
    """Read-only aggregation queries over the events table."""

    def top_n(
        self,
        app: str | None,
        kind: str,
        n: int = 50,
    ) -> list[dict]:
        kind_clause = _KIND_SQL.get(kind, "1=1")
        params: list = []
        app_clause = ""
        if app:
            app_clause = "AND app_bundle = ?"
            params.append(app)
        params.append(n)
        with self._conn() as c:
            rows = c.execute(
                f"SELECT key, modifiers, SUM(count) AS total "
                f"FROM events WHERE {kind_clause} {app_clause} "
                f"GROUP BY key, modifiers ORDER BY total DESC LIMIT ?",
                params,
            ).fetchall()
            return [dict(r) for r in rows]

    def total_count(self, app: str | None = None) -> int:
        with self._conn() as c:
            if app:
                row = c.execute(
                    "SELECT COALESCE(SUM(count), 0) FROM events WHERE app_bundle=?",
                    (app,),
                ).fetchone()
            else:
                row = c.execute(
                    "SELECT COALESCE(SUM(count), 0) FROM events"
                ).fetchone()
            return row[0] or 0
