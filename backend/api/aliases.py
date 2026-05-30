"""Key alias API — user-defined names for keycodes / actions.

GET    /api/aliases          → { raw: name, ... }
POST   /api/aliases          → upsert one {raw, name}; blank name deletes
DELETE /api/aliases/{raw}    → remove one (raw is query-safe via body too)

Names are keyed by the raw keycode string exactly as it appears in
/api/layout (e.g. "LALT(KC_F)", "TD(4)", or a combo output), so a single
name surfaces everywhere that action shows up — across layers and combos.
"""
from __future__ import annotations

import logging

from fastapi import APIRouter
from pydantic import BaseModel

from ..db.repository import AliasRepo

logger = logging.getLogger("keyboard_manager.api.aliases")

router = APIRouter()


class AliasIn(BaseModel):
    raw: str
    name: str = ""


def _repo() -> AliasRepo:
    from ..main import DB_PATH

    return AliasRepo(DB_PATH)


@router.get("/api/aliases")
def get_aliases() -> dict[str, str]:
    return _repo().all()


@router.post("/api/aliases")
def set_alias(body: AliasIn) -> dict[str, object]:
    raw = body.raw.strip()
    if not raw:
        return {"ok": False, "error": "empty raw"}
    _repo().set(raw, body.name)
    name = body.name.strip()
    logger.info("alias set raw=%s name=%r", raw, name)
    return {"ok": True, "raw": raw, "name": name, "deleted": not name}
