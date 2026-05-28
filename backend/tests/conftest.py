"""Shared pytest fixtures + sys.path setup."""
from __future__ import annotations

import sqlite3
import sys
import time
from pathlib import Path

# Add project root (the parent of `backend/`) to sys.path so `import backend`
# resolves to this package directory.
PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from backend.db.seed import bucket_for  # noqa: E402
from backend.parsers.keystat_keys import (  # noqa: E402
    is_modifier_combo,
    serialize_mods,
    split_mods,
)


def seed_events(
    db_path: Path,
    data: dict[str, dict[str, int]],
    source: str = "test_seed",
) -> int:
    """Insert (bundle_id, key, count) rows into events + apps for tests.

    `data` is the same shape the legacy JSON importer accepted:
        {bundle_id: {"j": 5892, "cmd+v": 3, ...}}

    Returns the snapshot_id used. Tests should prefer this over reaching into
    the live importer (now removed); it covers the same code path the helper
    will eventually use, just with deterministic input.
    """
    now = int(time.time())
    conn = sqlite3.connect(db_path)
    try:
        cur = conn.execute(
            "INSERT INTO snapshots(ts, source, notes) VALUES(?, ?, ?)",
            (now, source, "seeded by test"),
        )
        snapshot_id = cur.lastrowid

        events: list[tuple] = []
        for bundle_id, keys in data.items():
            for raw_key, count in keys.items():
                if is_modifier_combo(raw_key):
                    mods, base = split_mods(raw_key)
                    mods_str = serialize_mods(mods)
                else:
                    base, mods_str = raw_key, ""
                events.append(
                    (now, bundle_id, base, mods_str, count, snapshot_id, source)
                )
            conn.execute(
                """
                INSERT INTO apps(bundle_id, display_name, bucket, first_seen_ts, last_seen_ts)
                VALUES(?, NULL, ?, ?, ?)
                ON CONFLICT(bundle_id) DO UPDATE SET
                  bucket       = COALESCE(excluded.bucket, apps.bucket),
                  last_seen_ts = MAX(apps.last_seen_ts, excluded.last_seen_ts)
                """,
                (bundle_id, bucket_for(bundle_id), now, now),
            )
        if events:
            conn.executemany(
                "INSERT INTO events(ts, app_bundle, key, modifiers, count, snapshot_id, source) "
                "VALUES(?, ?, ?, ?, ?, ?, ?)",
                events,
            )
        conn.commit()
        return snapshot_id
    finally:
        conn.close()
