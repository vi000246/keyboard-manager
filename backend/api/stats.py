"""Stats API — top-N rankings and app metadata.

GET /api/stats        — top-N keys aggregated from events table
GET /api/apps         — known app bundle IDs and their bucket
"""
from __future__ import annotations

import logging
from typing import Literal

from fastapi import APIRouter, Query

from ..db.app_names import friendly_name
from ..db.heatmap_mapper import build_position_index, overlay_stats
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

    Pulls a generous top-500 single-key rows (covers >99% of keystrokes in
    practice), projects each onto its physical position via the keymap, and
    returns mapped cells + unmapped keys + coverage_pct.
    """
    from ..main import DB_PATH, VIAL_PATH

    layout = parse(VIAL_PATH)
    idx = build_position_index(layout)
    repo = StatsRepo(DB_PATH)
    rows = repo.top_n(app=app, kind="single", n=500)
    result = overlay_stats(idx, rows)

    mapped = sum(c["count"] for c in result["cells"])
    unmapped = sum(u["count"] for u in result["unmapped"])
    total = mapped + unmapped

    return {
        "scope": {"app": app},
        "max_count": result["max_count"],
        "cells": result["cells"],
        "unmapped": result["unmapped"],
        "coverage_pct": (mapped / total * 100) if total else 0.0,
    }


@router.get("/api/stats")
def get_stats(
    app: str | None = None,
    top: int = Query(50, ge=1, le=500),
    kind: Literal["single", "mod", "all"] = "single",
):
    from ..main import DB_PATH

    repo = StatsRepo(DB_PATH)
    rows = repo.top_n(app=app, kind=kind, n=top)

    # Total within the same scope (kind+app filter) drives the % column.
    # Use raw events filtered by the same predicate so percentages add up to ~100.
    if kind == "single":
        # Only count rows where modifiers='' for the denominator
        scope_total = _scoped_total(DB_PATH, app=app, where="modifiers = ''")
    elif kind == "mod":
        scope_total = _scoped_total(DB_PATH, app=app, where="modifiers != ''")
    else:
        scope_total = _scoped_total(DB_PATH, app=app, where="1=1")

    return {
        "scope": {"app": app, "kind": kind, "top": top},
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


def _scoped_total(db_path, app: str | None, where: str) -> int:
    """Sum of count over events matching {where} (+ optional app filter)."""
    import sqlite3

    params: list = []
    app_clause = ""
    if app:
        app_clause = "AND app_bundle = ?"
        params.append(app)
    conn = sqlite3.connect(db_path)
    try:
        row = conn.execute(
            f"SELECT COALESCE(SUM(count), 0) FROM events WHERE {where} {app_clause}",
            params,
        ).fetchone()
        return row[0] or 0
    finally:
        conn.close()
