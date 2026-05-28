"""FastAPI entrypoint for keyboard-manager backend.

Scaffold only — endpoints below are placeholders for the M1+ milestones.
"""
from __future__ import annotations

import os
from pathlib import Path

from fastapi import FastAPI

app = FastAPI(title="keyboard-manager", version="0.0.1")

VIAL_PATH = Path(os.environ.get("VIAL_PATH", "/data/mylayout.vil"))
DB_PATH = Path(os.environ.get("DB_PATH", "/data/db/keystat.db"))


@app.get("/health")
def health() -> dict[str, object]:
    return {
        "status": "ok",
        "vial_path": str(VIAL_PATH),
        "vial_exists": VIAL_PATH.exists(),
        "db_path": str(DB_PATH),
        "db_exists": DB_PATH.exists(),
    }


# M1: GET /api/layout
# M2: GET /api/stats?app=<bundle_id>&top=<n>, POST /api/stats/import
# M3: GET /api/stats/heatmap?app=<bundle_id>
# M4: WS  /api/live  (proxies to native-helper ws://host:8765)
