"""One-shot keystat JSON → SQLite importer.

Loads ~/keystat-counts.json (or any file with the same schema) into the
events / apps / snapshots tables. Used both as a CLI and as a function
called by the (future) POST /api/stats/import endpoint.

JSON schema (produced by ~/.hammerspoon/keystat.lua):

    {
      "__meta": { "startedAt": "...", "lastFlush": "..." },
      "<bundle_id>": { "<event_key>": <count>, ... },
      ...
    }

Where `<event_key>` is either a single key name ("j", "space") or a
modifier combo ("cmd+v", "cmd+ctrl+1"). Each (bundle_id, event_key) pair
becomes one row in the events table with `count` carrying the aggregated
value. Modifiers are normalized to the canonical alphabetical form.
"""
from __future__ import annotations

import argparse
import json
import os
import sqlite3
import time
from pathlib import Path

from ..db.migrations import ensure_schema
from ..db.seed import bucket_for
from ..parsers.keystat_keys import is_modifier_combo, serialize_mods, split_mods

DEFAULT_DB = Path(
    os.environ.get(
        "DB_PATH",
        str(Path.home() / "Library/Application Support/keyboard-manager/keystat.db"),
    )
)


def import_file(
    json_path: Path,
    db_path: Path,
    source: str = "hs_keystat_json",
    *,
    replace_existing_source: bool = True,
) -> dict:
    """Import a keystat JSON file into SQLite. Returns counts dict.

    Hammerspoon's keystat.lua writes cumulative counts since `startedAt`, so
    re-importing the same JSON after the file grew would double-count every
    (app, key) pair already on disk. To prevent that, by default we treat each
    JSON re-import as a snapshot REPLACEMENT for the given `source`: delete
    all existing events (and snapshots) with that source label, then insert
    fresh.

    Pass ``replace_existing_source=False`` to append additively — only useful
    when the JSON is known to be disjoint from prior imports.
    """
    json_path = Path(json_path)
    db_path = Path(db_path)
    ensure_schema(db_path)

    data = json.loads(json_path.read_text())
    # `__meta` is informational — drop it before iterating
    data.pop("__meta", None)

    now = int(time.time())
    conn = sqlite3.connect(db_path)
    try:
        if replace_existing_source:
            # Wipe prior rows + snapshots so the new import isn't summed on
            # top of the previous one. apps rows survive (their first_seen_ts
            # is meaningful).
            conn.execute("DELETE FROM events WHERE source = ?", (source,))
            conn.execute("DELETE FROM snapshots WHERE source = ?", (source,))

        cur = conn.execute(
            "INSERT INTO snapshots(ts, source, notes) VALUES(?, ?, ?)",
            (now, source, f"imported from {json_path.name}"),
        )
        snapshot_id = cur.lastrowid

        events_rows: list[tuple] = []
        apps_seen: set[str] = set()

        for bundle_id, keys in data.items():
            if not isinstance(keys, dict):
                continue
            apps_seen.add(bundle_id)
            for raw_key, count in keys.items():
                if is_modifier_combo(raw_key):
                    mods, base = split_mods(raw_key)
                    mods_str = serialize_mods(mods)
                else:
                    base, mods_str = raw_key, ""
                events_rows.append(
                    (now, bundle_id, base, mods_str, count, snapshot_id, source)
                )

        if events_rows:
            conn.executemany(
                "INSERT INTO events(ts, app_bundle, key, modifiers, count, snapshot_id, source) "
                "VALUES(?, ?, ?, ?, ?, ?, ?)",
                events_rows,
            )

        for bundle_id in apps_seen:
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

        conn.commit()
    finally:
        conn.close()

    return {
        "snapshot_id": snapshot_id,
        "events": len(events_rows),
        "apps": len(apps_seen),
    }


def _cli() -> int:
    parser = argparse.ArgumentParser(
        description="Import a keystat JSON snapshot into the SQLite stats db."
    )
    parser.add_argument("json_path", type=Path, help="path to keystat-counts.json")
    parser.add_argument(
        "--db",
        type=Path,
        default=DEFAULT_DB,
        help=f"sqlite db path (default {DEFAULT_DB})",
    )
    parser.add_argument(
        "--source",
        default="hs_keystat_json",
        help="snapshot source label",
    )
    parser.add_argument(
        "--append",
        action="store_true",
        help="append instead of replacing existing rows for this source",
    )
    args = parser.parse_args()
    r = import_file(
        args.json_path,
        args.db,
        source=args.source,
        replace_existing_source=not args.append,
    )
    mode = "appended" if args.append else "replaced"
    print(
        f"{mode} {r['events']} events from {r['apps']} apps; "
        f"snapshot_id={r['snapshot_id']}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(_cli())
