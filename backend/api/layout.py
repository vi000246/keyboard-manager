"""Layout API — exposes parsed Vial config to the frontend.

GET  /api/layout            → full resolved 6-layer tree
GET  /api/layout/keycodes   → keycode → label dictionary
POST /api/layout/upload     → replace the active `.vil` with the uploaded file
GET  /api/layout/source     → tells the UI which file path is currently active
"""
from __future__ import annotations

import logging
import shutil
from dataclasses import asdict
from pathlib import Path

from fastapi import APIRouter, UploadFile

from ..parsers.keycode_labels import KEYCODE_LABELS
from ..parsers.keycodes import LayoutContext, resolve
from ..parsers.vial import VialParseError, parse
from .errors import VialNotFound, VialParseFailed

logger = logging.getLogger("keyboard_manager.api.layout")

router = APIRouter()

# Module-level cache keyed by file mtime — re-parse only when .vil changes on disk.
_cache: dict = {}

# Soft cap on uploaded .vil size. Real .vil files are <50 KB; anything larger
# is almost certainly the wrong file and we want a clean 413 instead of OOM.
_MAX_UPLOAD_BYTES = 1 * 1024 * 1024  # 1 MiB


def _active_vial_path():
    """Return the path that /api/layout should parse.

    Precedence: uploaded `<DB_PATH parent>/uploaded.vil` (if it exists) wins
    over the boot-time VIAL_PATH. This lets the UI swap layouts without us
    needing a writable mount for the default file.
    """
    from ..main import DB_PATH, VIAL_PATH

    uploaded = DB_PATH.parent / "uploaded.vil"
    if uploaded.exists():
        return uploaded
    return VIAL_PATH


def _load(path: Path) -> dict:
    if not path.exists():
        raise VialNotFound(str(path))

    mtime = path.stat().st_mtime
    cache_key = (str(path), mtime)
    if _cache.get("key") == cache_key:
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

    # Combos store raw keycodes; the frontend tooltip wants resolved labels
    # (so "KC_J + KC_K → KC_ESCAPE" displays as "J + K → Esc"). Compute them
    # server-side using the same resolver the per-key serialization uses.
    def _label_of(raw: str) -> str:
        return resolve(raw, ctx).label_top or raw

    combo_json: list[dict] = []
    for c in layout.combo:
        d = asdict(c)
        d["trigger_labels"] = [_label_of(t) for t in c.triggers]
        d["output_label"] = _label_of(c.output)
        combo_json.append(d)

    # Only surface macros that actually have at least one action — empty
    # slots clutter the frontend's lookup table without adding information.
    # `raw` is the keycode that, when placed in a layer cell, fires this
    # macro (the frontend uses it to attach a "macro N" badge).
    macro_json: list[dict] = []
    for m in layout.macros:
        if not m.actions:
            continue
        macro_json.append({
            "index": m.index,
            "raw": f"MACRO{m.index}",
            "actions": m.actions,
        })

    result = {
        "vial_protocol": layout.vial_protocol,
        "uid": layout.uid,
        "layers": layers_json,
        "tap_dance": [asdict(td) for td in layout.tap_dance],
        "combo": combo_json,
        "macro": macro_json,
    }

    _cache["key"] = cache_key
    _cache["data"] = result
    logger.info(
        "parsed vial layout path=%s layers=%d tap_dance=%d combo=%d",
        path, len(layers_json), len(layout.tap_dance), len(layout.combo),
    )
    return result


@router.get("/api/layout")
def get_layout():
    return _load(_active_vial_path())


@router.get("/api/layout/keycodes")
def get_keycodes():
    return KEYCODE_LABELS


@router.get("/api/layout/source")
def get_source():
    """Where the currently-served layout comes from. Lets the UI show a hint
    when a custom upload is active and offer to revert."""
    from ..main import DB_PATH, VIAL_PATH

    uploaded = DB_PATH.parent / "uploaded.vil"
    active = _active_vial_path()
    return {
        "active_path": str(active),
        "is_uploaded": active == uploaded,
        "default_path": str(VIAL_PATH),
        "uploaded_path": str(uploaded),
    }


@router.post("/api/layout/upload")
async def upload_layout(file: UploadFile):
    """Receive a `.vil` file, validate it parses, and make it active.

    The file is written to `<DB_PATH parent>/uploaded.vil` — a path inside
    the writable volume mount. The default `VIAL_PATH` mount is read-only,
    so we keep uploaded layouts beside the SQLite db instead.
    """
    from ..main import DB_PATH

    body = await file.read(_MAX_UPLOAD_BYTES + 1)
    if len(body) > _MAX_UPLOAD_BYTES:
        raise VialParseFailed(
            f"upload too large: > {_MAX_UPLOAD_BYTES} bytes (real .vil files are <50 KB)"
        )

    target = DB_PATH.parent / "uploaded.vil"
    tmp = target.with_suffix(".vil.tmp")
    target.parent.mkdir(parents=True, exist_ok=True)
    tmp.write_bytes(body)

    # Validate by parsing before swapping the live file into place.
    try:
        parse(tmp)
    except VialParseError as e:
        tmp.unlink(missing_ok=True)
        raise VialParseFailed(f"uploaded file is not a valid .vil: {e}") from e

    shutil.move(str(tmp), str(target))
    _cache.clear()
    logger.info(
        "vial layout replaced via upload original=%s size=%d → %s",
        file.filename, len(body), target,
    )

    return {
        "ok": True,
        "filename": file.filename,
        "size_bytes": len(body),
        "active_path": str(target),
    }


@router.delete("/api/layout/upload")
def revert_uploaded_layout():
    """Remove the uploaded override so the default VIAL_PATH takes over again."""
    from ..main import DB_PATH

    uploaded = DB_PATH.parent / "uploaded.vil"
    if uploaded.exists():
        uploaded.unlink()
        _cache.clear()
        logger.info("reverted uploaded vial layout; back to default")
        return {"ok": True, "reverted": True}
    return {"ok": True, "reverted": False}
