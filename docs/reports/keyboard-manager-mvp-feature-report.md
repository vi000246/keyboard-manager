# Feature Implementation Report: keyboard-manager MVP (M1–M3)

## Summary

Implemented Milestones M1 (Static Viewer), M2 (Stats baseline), and M3 (Heatmap on layout) of the keyboard-manager MVP plan. M4 (native helper + Interactive simulator) and M5 (Polish) **deferred** to a separate session because they require macOS accessibility permissions and a long-running host process that isn't safe to dispatch unsupervised to subagents.

The web tool now reads `mylayout.vil`, renders every keycode fully expanded on a 58-key Borne grid across 6 layers, ingests the 8-day Hammerspoon keystat JSON baseline (1,369 events / 42 apps) into SQLite, and overlays a log-scaled heatmap on the keyboard with 96.15% coverage globally and 98.21% on the wezterm bucket.

## Strategy Used

- **Size**: L (28 tasks across 5 milestones; 16 done this session)
- **Concurrency cap**: unlimited per `implementing-features` Size=L rule
- **Subagent count**: 0 — most M1 tasks form a strict dependency chain (parser → resolver → API → grid) where subagent dispatch adds context-handoff overhead without parallelism gain; the M2 leaf tasks (2.1/2.2/2.4) were technically independent but small enough to batch in-session efficiently
- **Waves**: 1 wide wave executed sequentially (16 tasks)

> Deviation from skill default: skill suggested L → unlimited parallel subagents. With personal-tool scope and a tightly-chained DAG, the overhead of N subagents (each cold-starting context) exceeded the wall-clock saving. Recorded for next time.

## Tasks Completed

| #   | Task                                | Subagent? | Reviewer Findings | Status     |
|-----|-------------------------------------|-----------|-------------------|------------|
| 1.1 | Vial config loader                  | No        | n/a               | ✅ done    |
| 1.2 | Keycode resolver                    | No        | n/a               | ✅ done    |
| 1.3 | Layout API endpoint                 | No        | n/a               | ✅ done    |
| 1.4 | Frontend keyboard grid              | No        | n/a               | ✅ done    |
| 1.5 | M1 full coverage gate               | No        | n/a               | ✅ done (passed first-shot) |
| 2.1 | SQLite migrations                   | No        | n/a               | ✅ done    |
| 2.2 | Keystat keys helper                 | No        | n/a               | ✅ done    |
| 2.3 | Stats / Apps / Snapshot repos       | No        | n/a               | ✅ done    |
| 2.4 | APP_BUCKETS seed                    | No        | n/a               | ✅ done    |
| 2.5 | JSON keystat importer               | No        | n/a               | ✅ done    |
| 2.6 | Stats API endpoints                 | No        | n/a               | ✅ done    |
| 2.7 | Frontend stats dashboard            | No        | n/a               | ✅ done    |
| 3.1 | Heatmap mapper                      | No        | n/a               | ✅ done    |
| 3.2 | Heatmap API endpoint                | No        | n/a               | ✅ done    |
| 3.3 | Frontend heatmap overlay            | No        | n/a               | ✅ done    |
| 3.4 | Bidirectional highlight             | No        | n/a               | ✅ done    |
| 4.1–4.7 | M4 native helper + Interactive  | —         | —                 | **deferred** |
| 5.1–5.4 | M5 polish                       | —         | —                 | **deferred** |

## Integration Checks

| Check       | Status | Notes                                                              |
|-------------|--------|--------------------------------------------------------------------|
| Type-check  | n/a    | No type-checker configured (mypy in dev deps but no targets yet)   |
| Lint        | ✅ pass | `ruff check .` — All checks passed                                 |
| Unit tests  | ✅ pass | **84 tests** across 8 files                                        |
| Build       | ✅ pass | `docker compose up -d --build` both images build & start           |
| Smoke test  | ✅ pass | `/health` reports vial_exists+db_exists; `/api/stats/heatmap?app=wezterm` returns coverage=98.21%, max=19248; matches `hotkey-analysis.md` top keys (Space, Bksp, J, I, N) |

## AC Verification Map

| AC   | Description (from SRS)                          | Test                                                | Status |
|------|-------------------------------------------------|-----------------------------------------------------|--------|
| AC-1 | `.vil` parsing covers all keycodes              | `test_mylayout_full_keycode_coverage`               | ✅ Pass |
| AC-2 | TD / MT / LT full expansion                     | `test_tap_dance_branches`, `test_mod_tap_all_t`, `test_layer_tap` | ✅ Pass |
| AC-3 | Static Viewer renders 6 layers                  | Manual (UI verified end-to-end via docker compose) | ✅ Pass |
| AC-4 | JSON keystat imports into SQLite                | `test_import_minimal`, `test_import_full_baseline_count` | ✅ Pass |
| AC-5 | Stats API matches `keystat_analyze.py`          | `test_stats_top_n_per_app` + smoke: wezterm Space 22.7% mirrors hotkey-analysis §2.1 | ✅ Pass |
| AC-6 | Heatmap covers ≥ 90% of keystrokes              | Smoke: 96.15% global, 98.21% wezterm                | ✅ Pass |
| AC-7 | Native helper writes SQLite                     | —                                                   | ⏸ Deferred (M4) |
| AC-8 | WS hold-to-layer < 100ms                        | —                                                   | ⏸ Deferred (M4) |
| AC-9 | `docker compose up -d` brings up both services  | Manual + `scripts/smoke.sh` not yet written         | ⚠ Partial (works manually; smoke.sh is M5) |
| AC-10 | Hammerspoon cutover doc                        | —                                                   | ⏸ Deferred (M5) |

## Files Changed

| File                                                                | Action  | Lines |
|---------------------------------------------------------------------|---------|-------|
| `backend/__init__.py` + `parsers/`, `api/`, `db/`, `scripts/`, `tests/__init__.py` | CREATED | +0 each (markers) |
| `backend/parsers/vial.py`                                           | CREATED | +110  |
| `backend/parsers/keycodes.py`                                       | CREATED | +180  |
| `backend/parsers/keycode_labels.py`                                 | CREATED | +75   |
| `backend/parsers/keystat_keys.py`                                   | CREATED | +30   |
| `backend/db/migrations.py`                                          | CREATED | +50   |
| `backend/db/repository.py`                                          | CREATED | +120  |
| `backend/db/seed.py`                                                | CREATED | +50   |
| `backend/db/heatmap_mapper.py`                                      | CREATED | +95   |
| `backend/api/layout.py`                                             | CREATED | +85   |
| `backend/api/stats.py`                                              | CREATED | +95   |
| `backend/api/errors.py`                                             | CREATED | +25   |
| `backend/main.py`                                                   | UPDATED | +20 / -5 |
| `backend/scripts/import_keystat.py`                                 | CREATED | +110  |
| `backend/pyproject.toml`                                            | UPDATED | +6    |
| `backend/Dockerfile`                                                | UPDATED | +5 / -3 |
| `backend/tests/conftest.py`                                         | CREATED | +12   |
| `backend/tests/fixtures/mylayout.vil`                               | COPIED  | 1 file |
| `backend/tests/test_*.py` (8 files)                                 | CREATED | +650 total (84 tests) |
| `frontend/index.html`                                               | UPDATED | +15 / -3 |
| `frontend/style.css`                                                | UPDATED | +200 / -5 |
| `frontend/app.js`                                                   | UPDATED | rewritten ~25 |
| `frontend/static-viewer.js`                                         | CREATED | +50   |
| `frontend/grid-render.js`                                           | CREATED | +35   |
| `frontend/keycode-format.js`                                        | CREATED | +50   |
| `frontend/stats.js`                                                 | CREATED | +220  |
| `frontend/heatmap.js`                                               | CREATED | +75   |
| `frontend/Dockerfile`                                               | UPDATED | +2 / -4 |
| `docker-compose.yml`                                                | UPDATED | +5 / -3 (port overrides) |

## Deviations from Plan

1. **Subagent strategy**: plan implied dispatching independent tasks in parallel via subagents (Size=L). Executed sequentially in main session instead. Reason: most tasks formed a strict dependency chain; the few independent leaves were small enough that subagent dispatch overhead outweighed parallelism gain. Recorded for future L-sized features with wider dependency graphs.

2. **Docker port mapping**: plan assumed default ports 8000 / 8080. Local environment already has `wko5coach` on 8000 — switched to `KM_BACKEND_PORT=8001` and `KM_FRONTEND_PORT=8081` via env vars in `docker-compose.yml`. Smoke test commands and the README quick-start need updating accordingly (deferred to M5).

3. **Frontend Dockerfile**: original plan listed individual `COPY` per file. Changed to `COPY *.html *.css *.js` glob so future M4/M5 additions (interactive.js, etc.) don't need Dockerfile edits.

4. **M4 + M5 deferred**: see Summary. Plan scope was M1–M5; this session shipped M1–M3 (16/28 tasks) as the natural "web tool works without native capture" milestone. M4 requires macOS accessibility permissions and a long-running host helper; M5 polish builds on M4.

5. **`ensure_schema(DB_PATH)` at import time** caused a brief test regression after task 2.6 — fixed in the final commit by routing test DB_PATH through tmp_path.

## Issues Encountered

- **Backend container failed to start on first build** due to relative imports in `main.py`. Resolved by adjusting `backend/Dockerfile` to `COPY . ./backend` and `CMD uvicorn backend.main:app` so the backend stays a proper Python package inside the container.
- **Port 8000 conflict** with an unrelated container — resolved by introducing `KM_BACKEND_PORT` / `KM_FRONTEND_PORT` env-var overrides.
- **`uv pip install -e .` failed** because setuptools auto-discovery couldn't handle 5 top-level packages (parsers, api, db, scripts, tests). Switched to direct dep install (`uv pip install fastapi httpx ...`) rather than fight `[tool.setuptools.packages.find]` config.

## Tests Written

| Test File                                | Tests | Coverage                                                |
|------------------------------------------|-------|--------------------------------------------------------|
| `backend/tests/test_vial_parser.py`      | 9     | Vial JSON load, dataclass shape, schema validation     |
| `backend/tests/test_keycode_resolver.py` | 14    | KC_*, LT, MT, TD, LSFT/LGUI wrapped, TRN/NO/unknown    |
| `backend/tests/test_layout_api.py`       | 10    | `/api/layout` + `/api/layout/keycodes`, error codes, M1 coverage gate |
| `backend/tests/test_migrations.py`       | 5     | Idempotent schema creation, indexes, defaults          |
| `backend/tests/test_keystat_keys.py`     | 8     | `split_mods` / `serialize_mods` / `is_modifier_combo`  |
| `backend/tests/test_repository.py`       | 11    | StatsRepo / AppsRepo / SnapshotRepo CRUD + aggregation |
| `backend/tests/test_import.py`           | 6     | JSON → SQLite (incl. real 8-day baseline)              |
| `backend/tests/test_stats_api.py`        | 8     | `/api/stats` + `/api/apps`, kind filter, pct math      |
| `backend/tests/test_heatmap_mapper.py`   | 7     | Position index, event-key normalization, unmapped fallback |
| `backend/tests/test_heatmap_api.py`      | 6     | `/api/stats/heatmap`, coverage_pct, per-app filter     |
| **Total**                                | **84** |                                                       |

## Follow-ups

- [ ] **M4** — Native helper (pynput + WS + SQLite sink + Interactive UI). Requires macOS Accessibility permission setup and launchd plist; run in a separate session with manual permission grant.
- [ ] **M5** — `scripts/smoke.sh`, `docs/migration-from-hammerspoon.md`, README polish.
- [ ] **Port override docs**: update README quick-start to mention `KM_BACKEND_PORT` / `KM_FRONTEND_PORT` env vars.
- [ ] **Module Spec sync**: spec assumed default 8000/8080; update §System Context table to reflect the env-var override added in this session.
- [ ] **mypy targets**: dev deps include mypy but no type-checker pass exists yet; configure when M4 lands.
