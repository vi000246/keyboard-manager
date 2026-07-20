# CLAUDE.md

Guidance for Claude Code sessions working in this repo.

## What this project is

`keyboard-manager` — a local Docker web tool that:

1. Parses a Vial `.vil` keyboard config and renders all 6 layers with **fully expanded keycodes** (no `TD(0)` / `LT1(...)` abbreviations)
2. Provides an interactive simulator that reacts to real keystrokes via a host-side native helper + WebSocket
3. Stores keystroke statistics in SQLite and overlays them as a heatmap on the keyboard layout

Personal tool, macOS only. Editing the layout stays in Vial GUI — this project is **read-only on layout** and write-only on stats.

## Layout of the repo

```
keyboard-manager/
├── backend/        FastAPI service (runs in Docker)
├── frontend/       static HTML/JS served by nginx (runs in Docker)
├── native-helper/  macOS host process — keystroke capture + WS push (NOT in Docker)
├── docs/           PRD + architecture
└── docker-compose.yml
```

`native-helper/` cannot run inside Docker because Docker Desktop on macOS has no access to host accessibility events.

## Key files to read first

| File | Purpose |
|---|---|
| `docs/PRD.md` | Product intent — problem, hypothesis, milestones |
| `docs/architecture.md` | Component map, data shape, endpoints |
| `~/.claude/plans/claude-init-git-init-fancy-pinwheel.md` | The canonical bootstrap + design plan |
| `docs/keyboard-map/spec.md` | Keyboard layout spec (what the `.vil` was designed to express) |
| `docs/keyboard-map/hotkey-analysis.md` | 8-day, 137k-keystroke stats baseline (the data we want to visualize) |
| `docs/keyboard-map/keystat_analyze.py` | The aggregation logic that was ported into the backend |
| `sample/beekeeb-36key.vil` | The **default** Vial config — current board, main parsing target (override with `VIAL_CONFIG`) |
| `sample/mylayout.vil` | Previous board (borne, 10×7). Kept as a second-topology regression fixture |
| `backend/parsers/topology.py` | Per-keyboard physical geometry — registry by `uid` + inference fallback |
| `docs/macos-accessibility.md` | One-time Accessibility permission setup for the native helper (the `Python.app` gotcha) |

## Project conventions

- **Backend**: Python 3.12+, FastAPI, vanilla SQLite (stdlib). No ORM.
- **Frontend**: vanilla HTML / CSS / JS. No framework, no build step.
- **Native helper**: Python + pynput first; revisit Swift CGEventTap if pynput's macOS permission UX is too brittle.
- **Stats math**: reuse `keystat_analyze.py` logic — `split_mods`, `is_modifier_combo`, `APP_BUCKETS`.
- **Tests**: pytest for backend; manual UI verification for frontend; e2e left informal until M5.
- **Lint**: ruff for Python.
- **Keyboard geometry**: never hardcode row/column counts or the split point in
  the frontend. Board shape is resolved server-side in `backend/parsers/topology.py`
  and shipped on `/api/layout` as `topology`. To support a new board, add a
  `PROFILES` entry keyed by its `.vil` `uid`; without one it still renders
  correctly via inference, just flat (no column stagger).

## Milestones

| # | Name | Status |
|---|---|---|
| 0 | Bootstrap | ✅ done |
| 1 | Static Viewer | ✅ done |
| 2 | Stats baseline | ✅ done |
| 3 | Heatmap | ✅ done |
| 4 | Native helper + Interactive | ✅ done (pynput + WS + launchd) |
| 5 | Polish | partial — launchd done (M5.1); `scripts/smoke.sh` + README finalize TODO |

## Operational notes

- Helper is launchd-managed: `~/Library/LaunchAgents/com.keyboard-manager.helper.plist`
- Install/uninstall via `native-helper/install-launchd.sh` / `uninstall-launchd.sh`
- macOS Accessibility setup: see `docs/macos-accessibility.md` (must grant the `Python.app` framework bundle, **not** the `.venv/bin/python` symlink)
- Hammerspoon `keystat.lua` is deprecated; SQLite at `~/Library/Application Support/keyboard-manager/keystat.db` is the source of truth. The legacy JSON importer (`backend/scripts/import_keystat.py`) has been removed — the native helper writes directly to SQLite
- Default ports: backend `:8001`, frontend `:8081`, helper WS `:8766` (8765 collides with Hammerspoon's `hs.httpserver` on some setups)

## Things NOT to do

- Don't add layout editing (Vial owns it)
- Don't add firmware flash (Vial owns it)
- Don't expand to non-macOS (cap of v1)
- Don't commit `*.db`, `keystat-counts.json`, or any personal stats data
- Don't introduce a frontend framework without explicit go-ahead — vanilla JS is the chosen constraint

## Run commands (target — built up over milestones)

```bash
# M0+: scaffold sanity
docker compose config

# M1+: bring up backend + frontend
docker compose up -d

# M4+: start native helper (host-side)
cd native-helper && python main.py
# or run the LaunchAgent (preferred)
./native-helper/install-launchd.sh
```

## Reading order for a fresh agent

1. `README.md`
2. `docs/PRD.md`
3. `docs/architecture.md`
4. The plan file referenced above
5. `sample/beekeeb-36key.vil` (just `head` enough to see the shape)
