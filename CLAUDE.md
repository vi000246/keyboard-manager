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
| `~/Projects/keyboard-map/spec.md` | Keyboard layout spec (what the `.vil` was designed to express) |
| `~/Projects/keyboard-map/hotkey-analysis.md` | 8-day, 137k-keystroke stats baseline (the data we want to visualize) |
| `~/Projects/keyboard-map/keystat_analyze.py` | The aggregation logic to port into the backend |
| `~/Projects/keyboard-map/mylayout.vil` | The actual Vial config — main parsing target |

## Project conventions

- **Backend**: Python 3.12+, FastAPI, vanilla SQLite (stdlib). No ORM.
- **Frontend**: vanilla HTML / CSS / JS. No framework, no build step.
- **Native helper**: Python + pynput first; revisit Swift CGEventTap if pynput's macOS permission UX is too brittle.
- **Stats math**: reuse `keystat_analyze.py` logic — `split_mods`, `is_modifier_combo`, `APP_BUCKETS`.
- **Tests**: pytest for backend; manual UI verification for frontend; e2e left informal until M5.
- **Lint**: ruff for Python.

## Milestones

| # | Name | What ships |
|---|---|---|
| 0 | Bootstrap | Repo, scaffold, docker-compose skeleton — **current** |
| 1 | Static Viewer | `.vil` parser + 6-layer grid |
| 2 | Stats baseline | SQLite schema + JSON importer + top-N reports |
| 3 | Heatmap | Stats overlay on layout grid |
| 4 | Native helper + Interactive | macOS capture + WS + live grid switching |
| 5 | Polish | docker compose 一鍵起、launchd plist、README polish |

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

# M2+: one-shot JSON import (CLI to be added)
python backend/scripts/import_keystat_json.py ~/keystat-counts.json
```

## Reading order for a fresh agent

1. `README.md`
2. `docs/PRD.md`
3. `docs/architecture.md`
4. The plan file referenced above
5. `~/Projects/keyboard-map/mylayout.vil` (just `head` enough to see the shape)
