"""Stats API — top-N rankings and app metadata.

GET /api/stats        — top-N keys aggregated from events table
GET /api/apps         — known app bundle IDs and their bucket
"""
from __future__ import annotations

import logging
from typing import Literal

from fastapi import APIRouter, Query

from ..db.app_names import friendly_name
from ..db.heatmap_mapper import (
    build_combo_position_index,
    build_modifier_position_index,
    build_position_index,
    filter_typing_singles,
    overlay_stats,
)
from ..db.repository import AppsRepo, StatsRepo
from ..parsers.vial import parse

logger = logging.getLogger("keyboard_manager.api.stats")

router = APIRouter()


@router.get("/api/apps")
def get_apps():
    """List known apps sorted by total event count (DESC), with friendly names.

    `display_name` is the macOS-friendly name when known (e.g. "Obsidian" for
    `md.obsidian`); falls back to the last reverse-DNS segment for unknown
    bundles. The frontend dropdown sorts by `total_count` for fast access to
    the most-used apps.
    """
    from ..main import DB_PATH

    rows = AppsRepo(DB_PATH).all_with_counts()
    # Prefer a stored display_name if the helper / importer ever sets one;
    # otherwise fall back to the static mapping.
    for r in rows:
        r["display_name"] = r.get("display_name") or friendly_name(r["bundle_id"])
    return rows


@router.get("/api/stats/heatmap")
def get_heatmap(app: str | None = None):
    """Return per-position counts for the keyboard heatmap overlay.

    The heatmap is the "shortcut surface" view: every combo (`modifiers != ''`)
    is included plus any non-typing single keys (arrows, F-keys, navigation,
    etc.). Plain-typing singles — letters, digits, space/enter/bksp, common
    punctuation — are filtered out so the heatmap reflects deliberate hotkey
    usage rather than how much English the user types.

    For combo rows, the modifier portion is also credited to the physical
    modifier key(s) on the active layout (cmd → LGUI_T positions, ctrl → TD
    branches holding LCTL, etc.). Multi-mod sources like ALL_T are skipped
    because we can't tell which modifier the user actually wanted.

    `coverage_pct` is computed over included events (post-filter) so it reflects
    "how much of what we're surfacing is mapped to a physical key".
    """
    from ..main import DB_PATH, VIAL_PATH

    layout = parse(VIAL_PATH)
    base_idx = build_position_index(layout)
    mod_idx = build_modifier_position_index(layout)
    combo_idx = build_combo_position_index(layout)
    repo = StatsRepo(DB_PATH)
    # Pull both kinds so we can show combos plus the functional singles
    # (arrows / F-keys / Esc / Tab) that survive the typing filter.
    rows = filter_typing_singles(
        repo.top_n(app=app, kind="all", n=1000)
    )
    result = overlay_stats(
        base_idx, rows, modifier_index=mod_idx, combo_index=combo_idx
    )

    # Coverage measured against raw included events (before modifier derivation
    # inflates cell totals), so the % matches what's in `rows`.
    included_total = sum(r["total"] for r in rows)
    unmapped_total = sum(u["count"] for u in result["unmapped"])
    mapped_total = included_total - unmapped_total

    return {
        "scope": {"app": app},
        "max_count": result["max_count"],
        "cells": result["cells"],
        "unmapped": result["unmapped"],
        "coverage_pct": (mapped_total / included_total * 100) if included_total else 0.0,
    }


@router.get("/api/stats/nameable")
def get_nameable_keys():
    """Distinct combos + non-typing singles across ALL apps, for the Key Name Map.

    The Key Name Map's layout-derived list can't cover shortcuts you press that
    aren't keys on the .vil (e.g. `alt+r`, a media play/pause). Those live only
    in the recorded `events` table, so we surface every distinct (key, modifiers)
    here — minus plain-typing singles (letters/digits/space/etc.) so the list
    stays a "shortcut surface". Each entry's `display` matches the Stats table
    rendering so an alias keyed by it (`stat:<display>`) lines up on both pages.
    """
    from ..main import DB_PATH

    rows = filter_typing_singles(
        StatsRepo(DB_PATH).top_n(app=None, kind="all", n=10000)
    )
    out = []
    for r in rows:
        mods = r["modifiers"] or ""
        display = (f"{mods}+" if mods else "") + r["key"]
        out.append(
            {
                "key": r["key"],
                "modifiers": mods,
                "total": r["total"],
                "display": display,
            }
        )
    out.sort(key=lambda e: e["total"], reverse=True)
    return out


@router.get("/api/stats")
def get_stats(
    app: str | None = None,
    top: int = Query(50, ge=1, le=500),
    kind: Literal["single", "mod", "all"] = "single",
    key: str | None = None,
):
    from ..main import DB_PATH

    repo = StatsRepo(DB_PATH)
    # When the key filter is active, surface ALL matching combos — even rare
    # ones (count=1) — by ignoring the `top` cap. The user is explicitly
    # narrowing the result set; truncating to top-N would hide the long tail
    # of one-off combos they're often hunting for. 10000 is a hard safety
    # cap to keep the response bounded if someone passes an empty-ish filter
    # against a huge events table.
    effective_n = 10000 if key else top
    # Bare letter presses (a-z, no modifier) are pure typing noise on the
    # single-key list — exclude them so it surfaces functional keys. Combos
    # (Cmd+A etc.) are unaffected since they carry modifiers.
    rows = repo.top_n(
        app=app, kind=kind, n=effective_n, key_filter=key,
        exclude_single_letters=True,
    )

    # Total within the same scope (kind+app+key filter) drives the % column.
    # Applying the key filter here too means pct represents "share of the
    # filtered scope" — e.g. with key="cmd", Cmd+C's pct is its share of
    # all Cmd combos, not of all events overall (which would be unhelpfully
    # small numbers that don't add to anything meaningful).
    # Exclude bare letters from the denominator too, matching the rows above,
    # so percentages are a share of what's actually listed.
    no_letters = "NOT (modifiers = '' AND key GLOB '[a-z]')"
    if kind == "single":
        where = f"modifiers = '' AND {no_letters}"
    elif kind == "mod":
        where = "modifiers != ''"
    else:
        where = no_letters
    scope_total = _scoped_total(DB_PATH, app=app, where=where, key=key)

    return {
        "scope": {"app": app, "kind": kind, "top": top, "key": key},
        "total_events": scope_total,
        "rows": [
            {
                "key": r["key"],
                "modifiers": r["modifiers"],
                "count": r["total"],
                "pct": (r["total"] / scope_total * 100) if scope_total else 0.0,
            }
            for r in rows
        ],
    }


def _scoped_total(
    db_path, app: str | None, where: str, key: str | None = None
) -> int:
    """Sum of count over events matching {where} (+ optional app/key filter)."""
    import sqlite3

    params: list = []
    app_clause = ""
    if app:
        app_clause = "AND app_bundle = ?"
        params.append(app)
    key_clause = ""
    if key:
        key_clause = "AND (LOWER(key) LIKE ? OR LOWER(modifiers) LIKE ?)"
        like = f"%{key.lower()}%"
        params.extend([like, like])
    conn = sqlite3.connect(db_path)
    try:
        row = conn.execute(
            f"SELECT COALESCE(SUM(count), 0) "
            f"FROM events WHERE {where} {app_clause} {key_clause}",
            params,
        ).fetchone()
        return row[0] or 0
    finally:
        conn.close()
