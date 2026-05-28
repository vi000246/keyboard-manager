# keyboard-manager

Vial config visualizer + keystat heatmap — a local Docker web tool to inspect your keyboard layout and where your fingers actually go.

## Why this exists

[Vial](https://get.vial.today/) is great for editing keymaps, but the built-in viewer leaves you decoding cryptic abbreviations: `TD(0)`, `LT1(KC_TAB)`, `ALL_T(KC_SPACE)`. You can't see at a glance what a key becomes when you hold it, or what each tap-dance branch does, or whether the rarely-used `pinky` slot is actually being hammered 1500 times a day.

`keyboard-manager` reads your `.vil` file and your existing keystroke statistics (e.g. from a Hammerspoon capture script) and stitches them into:

1. **Static Viewer** — every layer drawn with all keycodes expanded into human-readable form
2. **Interactive Simulator** — hold a key on the physical keyboard, see the live grid switch to that layer
3. **Stats Dashboard** — usage heatmap overlaid on the keyboard layout, plus per-app and global breakdowns

It's read-only on the layout (editing stays in Vial GUI) and stores stats in SQLite.

## Project status

Scaffolding only. See [`docs/PRD.md`](docs/PRD.md) and [`docs/architecture.md`](docs/architecture.md) for the design.

## Layout

```
keyboard-manager/
├── backend/        FastAPI service — parses .vil, serves layout + stats API
├── frontend/       Static HTML/JS — three pages (static / interactive / stats)
├── native-helper/  macOS host process — global keystroke capture + WebSocket push
├── docs/           PRD, architecture, decisions
└── docker-compose.yml
```

`backend/` and `frontend/` run in Docker. `native-helper/` must run on the macOS host (Docker on macOS has no access to host accessibility / keyboard events).

## Setup (target — not yet built)

```bash
# 1. Clone
git clone https://github.com/vi000246/keyboard-manager.git
cd keyboard-manager

# 2. Point at your .vil
export VIAL_CONFIG=$HOME/Projects/keyboard-map/mylayout.vil

# 3. Start backend + frontend
docker compose up -d

# 4. Start native helper (host-side)
cd native-helper && python main.py

# 5. Open browser
open http://localhost:8080
```

## Acknowledgements

- [Vial](https://get.vial.today/) for the keymap editor and the `.vil` format
- [keymap-drawer](https://github.com/caksoylar/keymap-drawer) for inspiration on static rendering
- The original `keystat_analyze.py` in `~/Projects/keyboard-map/` for the analysis logic this project extends

## License

MIT — see [`LICENSE`](LICENSE).
