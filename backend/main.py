"""FastAPI entrypoint for keyboard-manager backend."""
from __future__ import annotations

import logging
import os
from pathlib import Path

from fastapi import FastAPI

from .api.layout import router as layout_router
from .api.live import router as live_router
from .api.stats import router as stats_router
from .db.migrations import ensure_schema

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s %(message)s",
)

app = FastAPI(title="keyboard-manager", version="0.0.1")

VIAL_PATH = Path(os.environ.get("VIAL_PATH", "/data/mylayout.vil"))
DB_PATH = Path(os.environ.get("DB_PATH", "/data/db/keystat.db"))

# Ensure tables exist before any request lands. Idempotent.
ensure_schema(DB_PATH)

app.include_router(layout_router)
app.include_router(stats_router)
app.include_router(live_router)


@app.get("/health")
def health() -> dict[str, object]:
    return {
        "status": "ok",
        "vial_path": str(VIAL_PATH),
        "vial_exists": VIAL_PATH.exists(),
        "db_path": str(DB_PATH),
        "db_exists": DB_PATH.exists(),
    }
