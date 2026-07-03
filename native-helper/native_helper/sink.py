"""Batched SQLite writer for live keystroke events.

We buffer events in memory and flush every ``flush_interval`` seconds (default
5s). This trades a small data-loss window on crash for:
  - lower wal/journal churn vs. per-keystroke fsync (SSD-friendly)
  - no contention with the backend's read queries

The sink is thread-safe — the pynput listener pushes from its background
thread, the timer thread drains the buffer.
"""
from __future__ import annotations

import sqlite3
import threading
import time
from pathlib import Path

# Row shape: (ts, app_bundle, key, modifiers, count, snapshot_id, source)
_INSERT_SQL = (
    "INSERT INTO events(ts, app_bundle, key, modifiers, count, snapshot_id, source) "
    "VALUES(?, ?, ?, ?, ?, ?, ?)"
)


class EventSink:
    def __init__(
        self,
        db_path: Path,
        source: str = "native_helper",
        flush_interval: float = 5.0,
    ):
        self.db_path = Path(db_path)
        self.source = source
        self.flush_interval = flush_interval
        self._buffer: list[tuple] = []
        self._lock = threading.Lock()
        self._timer: threading.Timer | None = None
        self._stopped = False
        self.snapshot_id: int | None = None

    # ── lifecycle ─────────────────────────────────────────────────────

    def start(self, snapshot_id: int) -> None:
        self.snapshot_id = snapshot_id
        self._stopped = False
        self._schedule()

    def stop(self) -> None:
        self._stopped = True
        if self._timer is not None:
            self._timer.cancel()
            self._timer = None
        self.flush_now()

    # ── ingestion ─────────────────────────────────────────────────────

    def record(self, *, key: str, modifiers: str, app_bundle: str, ts: int) -> None:
        if self.snapshot_id is None:
            raise RuntimeError("EventSink.start(snapshot_id) must be called first")
        with self._lock:
            self._buffer.append(
                (ts, app_bundle, key, modifiers, 1, self.snapshot_id, self.source)
            )

    # ── flushing ──────────────────────────────────────────────────────

    def flush_now(self) -> int:
        """Drain the buffer to SQLite in one transaction. Returns rows written.

        Rows identical up to the second — same (ts, app, key, modifiers) —
        are merged into one row with a summed count before insert. Fast
        typing / key repeat produces many such duplicates; merging costs no
        information (ts already has second granularity) and shrinks both the
        write batch and the events table.
        """
        with self._lock:
            rows = self._buffer
            self._buffer = []
        if not rows:
            return 0
        merged: dict[tuple, list] = {}
        for r in rows:
            ts, app_bundle, key, modifiers, count, snapshot_id, source = r
            k = (ts, app_bundle, key, modifiers, snapshot_id, source)
            slot = merged.get(k)
            if slot is None:
                merged[k] = [ts, app_bundle, key, modifiers, count, snapshot_id, source]
            else:
                slot[4] += count
        out = [tuple(v) for v in merged.values()]
        conn = sqlite3.connect(self.db_path)
        try:
            conn.executemany(_INSERT_SQL, out)
            conn.commit()
        finally:
            conn.close()
        return len(out)

    def _schedule(self) -> None:
        if self._stopped:
            return
        self._timer = threading.Timer(self.flush_interval, self._tick)
        self._timer.daemon = True
        self._timer.start()

    def _tick(self) -> None:
        try:
            self.flush_now()
        except Exception:  # noqa: BLE001 — log via stderr but never kill the timer
            import traceback

            traceback.print_exc()
        finally:
            self._schedule()


def open_snapshot(db_path: Path, source: str, notes: str | None = None) -> int:
    """Insert a fresh snapshot row and return its id.

    Helper for the entrypoint — keeps SQL out of the listener glue code.
    """
    conn = sqlite3.connect(db_path)
    try:
        cur = conn.execute(
            "INSERT INTO snapshots(ts, source, notes) VALUES(?, ?, ?)",
            (int(time.time()), source, notes),
        )
        conn.commit()
        return cur.lastrowid
    finally:
        conn.close()
