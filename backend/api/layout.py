"""Layout API — exposes parsed Vial config to the frontend.

GET /api/layout            → full resolved 6-layer tree
GET /api/layout/keycodes   → keycode → label dictionary
"""
from __future__ import annotations

import logging
from dataclasses import asdict
from pathlib import Path

from fastapi import APIRouter

from ..parsers.keycode_labels import KEYCODE_LABELS
from ..parsers.keycodes import LayoutContext, resolve
from ..parsers.vial import VialParseError, parse
from .errors import VialNotFound, VialParseFailed

logger = logging.getLogger("keyboard_manager.api.layout")

router = APIRouter()

# Module-level cache keyed by file mtime — re-parse only when .vil changes on disk.
_cache: dict = {}


def _load(path: Path) -> dict:
    if not path.exists():
        raise VialNotFound(str(path))

    mtime = path.stat().st_mtime
    if _cache.get("mtime") == mtime:
        return _cache["data"]

    try:
        layout = parse(path)
    except VialParseError as e:
        logger.error("vial parse failed path=%s reason=%s", path, e)
        raise VialParseFailed(str(e)) from e

    ctx = LayoutContext(tap_dance=list(layout.tap_dance))
    layers_json: list[dict] = []
    for layer in layout.layers:
        rows: list[dict] = []
        for row in layer.rows:
            keys: list[dict | None] = []
            for ci, raw in enumerate(row.keys):
                if raw is None:
                    keys.append(None)
                else:
                    rk = resolve(raw, ctx)
                    keys.append({"col": ci, "raw": raw, "resolved": asdict(rk)})
            rows.append({"row": row.row, "keys": keys})
        layers_json.append({"index": layer.index, "rows": rows})

    result = {
        "vial_protocol": layout.vial_protocol,
        "uid": layout.uid,
        "layers": layers_json,
        "tap_dance": [asdict(td) for td in layout.tap_dance],
        "combo": [asdict(c) for c in layout.combo],
    }

    _cache["mtime"] = mtime
    _cache["data"] = result
    logger.info(
        "parsed vial layout layers=%d tap_dance=%d combo=%d",
        len(layers_json), len(layout.tap_dance), len(layout.combo),
    )
    return result


@router.get("/api/layout")
def get_layout():
    from ..main import VIAL_PATH

    return _load(VIAL_PATH)


@router.get("/api/layout/keycodes")
def get_keycodes():
    return KEYCODE_LABELS
