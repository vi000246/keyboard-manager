# Architecture — keyboard-manager

> Sketch only. Full SRS will be generated via `/prp-srs` at the start of M1.

## Why this layout

Three constraints drove the shape:

1. **macOS Docker can't read host keyboard events** — Docker Desktop runs in a hypervisor with no access to accessibility / HID. The keystroke-capturing process therefore lives outside Docker, on the host.
2. **Stats math is already in Python** — `~/Projects/keyboard-map/keystat_analyze.py` has the aggregation, mod-combo splitting, and per-app bucket logic. Backend in Python reuses it directly.
3. **Read-only** — editing stays in Vial GUI. No write paths needed for the layout file.

## Component map

```
┌──────────────────────────────────────────────┐
│  macOS host                                  │
│                                              │
│  ┌────────────────────────────────────────┐  │
│  │  native-helper/  (host process)        │  │
│  │  - global keydown/keyup capture        │  │
│  │  - WebSocket server on :8765           │  │
│  │  - writes SQLite events table          │  │
│  └────────┬──────────────────┬────────────┘  │
│           │ WS               │ SQLite        │
│           │                  │               │
│  ┌────────▼──────────────────▼────────────┐  │
│  │  Docker compose                        │  │
│  │  ┌──────────────────────────────────┐  │  │
│  │  │  backend  (FastAPI :8000)        │  │  │
│  │  │  - parses .vil (volume mount)    │  │  │
│  │  │  - queries SQLite (volume mount) │  │  │
│  │  │  - REST + WS proxy               │  │  │
│  │  └──────────────────────────────────┘  │  │
│  │  ┌──────────────────────────────────┐  │  │
│  │  │  frontend (nginx :80 → host :8080)│  │  │
│  │  │  - vanilla HTML / JS             │  │  │
│  │  │  - proxies /api/ to backend      │  │  │
│  │  └──────────────────────────────────┘  │  │
│  └────────────────────────────────────────┘  │
└──────────────────────────────────────────────┘
```

## Volume mounts

| Host path | Container path | Mode |
|---|---|---|
| `$HOME/Projects/keyboard-map/mylayout.vil` (override via `VIAL_CONFIG`) | `/data/mylayout.vil` | `ro` |
| `$HOME/Library/Application Support/keyboard-manager/` | `/data/db/` | `rw` |

## Ports

| Service | Host | Container |
|---|---|---|
| backend | 8000 | 8000 |
| frontend | 8080 | 80 |
| native-helper WS | 8765 | n/a (host process) |

Backend reaches the helper at `host.docker.internal:8765` (Docker Desktop alias).

## Data shape (preliminary)

`.vil` parsing produces a tree like:

```
Layout {
  layers: [Layer; 6]
  tap_dance: [TapDance; 16]
  combos: [Combo; 16]
  key_overrides: [KeyOverride; 16]
}

Layer {
  rows: [Row; 10]      # rows[0..4] left side, rows[5..9] right side
  index: 0..5
}

Row {
  keys: [Key | null; 7]  # -1 in source = null
}

Key {
  raw: "LT1(KC_TAB)"
  resolved: {
    tap: "KC_TAB"
    hold: "→layer 1"
    label_top: "Tab"
    label_bottom: "→L1"
    expanded_kind: "layer-tap"  # | "mod-tap" | "tap-dance" | "combo-target" | "plain"
  }
}
```

SQLite schema (M2, may evolve):

```sql
CREATE TABLE events (
  id          INTEGER PRIMARY KEY,
  ts          INTEGER NOT NULL,           -- epoch seconds
  app_bundle  TEXT    NOT NULL,
  key         TEXT    NOT NULL,
  modifiers   TEXT    NOT NULL DEFAULT '', -- "cmd+shift" sorted alphabetically
  count       INTEGER NOT NULL DEFAULT 1   -- > 1 only for JSON-imported baseline rows
);

CREATE INDEX idx_events_app_key ON events(app_bundle, key);
CREATE INDEX idx_events_ts     ON events(ts);

CREATE TABLE apps (
  bundle_id    TEXT PRIMARY KEY,
  display_name TEXT,
  bucket       TEXT   -- "terminal" | "browser" | "editor" | ...
);

CREATE TABLE snapshots (
  id     INTEGER PRIMARY KEY,
  ts     INTEGER NOT NULL,
  source TEXT NOT NULL,   -- "hs_keystat_json" | "native_helper" | ...
  notes  TEXT
);
```

## Endpoint sketch

| Method | Path | Milestone | Purpose |
|---|---|---|---|
| GET | `/health` | M0 | Liveness + path probes |
| GET | `/api/layout` | M1 | Parsed `.vil` tree |
| GET | `/api/stats` | M2 | Top-N keys (optional `?app=`, `?top=`) |
| POST | `/api/stats/import` | M2 | One-shot JSON ingest |
| GET | `/api/stats/heatmap` | M3 | Per-key counts keyed by (layer, row, col) |
| GET | `/api/apps` | M2 | App bundle ID + bucket list |
| WS | `/api/live` | M4 | Proxies native-helper events |

## Open architecture questions

- pynput vs Swift CGEventTap for the helper
- Whether to terminate the helper WS when no browser tab is open (save CPU) or keep it always-on
- Where the bucket-bundle-ID mapping table lives (config file? built into DB seed?)
