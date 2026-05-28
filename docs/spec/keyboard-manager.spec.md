# Spec: keyboard-manager

## Metadata
- **Module**: keyboard-manager
- **Parent Module**: N/A
- **Sub-modules**: N/A — single-module project
- **Source PRDs**:
  - `docs/PRD.md` — initial creation
- **Source Linear Issue**: N/A
- **Owner**: vi000246 (solo)
- **Status**: ACTIVE — living document
- **Created**: 2026-05-28
- **Last Updated**: 2026-05-28

## Change History

| Date | Source PRD | Feature SRS | Plan | Summary |
|------|------------|-------------|------|---------|
| 2026-05-28 | `docs/PRD.md` | `docs/srs/keyboard-manager-mvp.srs.md` | `docs/plans/keyboard-manager-mvp.plan.md` | Created — local Docker tool that parses Vial `.vil` for layout viz + ingests keystrokes from a macOS native helper for heatmap & live simulator |

## Summary

`keyboard-manager` 是 macOS-only 個人工具，把 Vial 鍵盤的 `.vil` 設定檔解析後做完整 keycode 視覺化（含 tap-dance / mod-tap / layer-tap 展開），並把全域擊鍵統計累進 SQLite，疊在鍵盤位置圖上呈現 heatmap。系統採 3-process 架構：macOS host 上跑 native-helper（accessibility-aware keystroke capture + WebSocket），Docker 內跑 FastAPI backend + nginx 靜態前端。

---

## Domain Model

### Bounded Context
- **Context Name**: KeyboardManager（單一 bounded context — 整個 module）
- **Domain Layer**: Supporting Subdomain（personal tooling，非 core business）
- **Parent Module**: N/A

### Ubiquitous Language

| Term | Definition |
|------|-----------|
| **Vial config** / `.vil` | Vial 鍵盤編輯器產出的 JSON 設定檔，含 layout / tap_dance / combo / key_override / settings |
| **Keycode** | QMK 鍵碼字串，如 `KC_A`、`LSFT(KC_SCOLON)`、`LT1(KC_TAB)`；本系統的核心解析目標 |
| **Layer** | Vial 的層，本 user 設定 6 層（BASE / NAV / 未命名 / 未命名 / MEDIA / 未命名） |
| **Tap-dance（TD）** | QMK 機制：一顆鍵根據 tap / hold / double-tap / tap-hold 四種動作送出不同 keycode |
| **Layer-tap（LT）** | tap 送字母、hold 進入指定 layer |
| **Mod-tap（MT）** | tap 送字母、hold 當作 modifier；`ALL_T(...)` = hold 送 Hyper |
| **Resolved key** | Keycode 經 resolver 翻譯後的人類可讀結構：`{tap, hold, branches, label_top, label_bottom, expanded_kind}` |
| **Smart mode (rendering)** | 純字母鍵單行顯示、MT/LT/TD 鍵雙行堆疊顯示的 frontend 渲染策略 |
| **Keystat event** | 一次擊鍵紀錄，含 `(ts, app_bundle, key, modifiers, count)` |
| **App bundle ID** | macOS 應用唯一識別字串，例如 `com.googlecode.iterm2` |
| **Bucket** | App 分類（terminal/browser/editor/chat/launcher），用於 per-app stats 報表分組 |
| **Heatmap cell** | 一個 `(layer, row, col)` 位置加總的擊鍵 count，用於 keyboard grid overlay |
| **Snapshot** | 一次 import 或 capture session 的元資料（時間、來源、備註），用於溯源 |
| **Native helper** | host-side Python process，跑 pynput + WebSocket + SQLite writer |

### Domain Events
本 module 是封閉系統，不對外發 domain event。內部唯一「事件」是 WebSocket 推給 frontend 的 keypress notification，那是 UI 訊號、非 domain event。

---

## System Context

### Scope & Boundaries
- **In scope**:
  - 解析 Vial `.vil` 檔案結構
  - 把 QMK keycode 翻成人類字串
  - 全域 macOS 擊鍵 capture（host-side helper）
  - SQLite 統計儲存 + 查詢
  - Web UI：static viewer / interactive simulator / stats dashboard
  - JSON keystat baseline 一次性匯入
- **Out of scope**:
  - 編輯 / 修改 `.vil`（Vial GUI 負責）
  - Firmware flash（Vial 負責）
  - 跨平台 capture（Linux / Windows）
  - Cloud sync / multi-user / auth
  - 比較 `.vil` 與設備內 keymap（沒這 use case）

### Actors

| Actor | Type | Interaction |
|---|---|---|
| User（vi000246） | Human | 開瀏覽器 `:8080`、看 layout / heatmap / 即時模擬 |
| macOS HID layer | System | 全域 keyboard events 送進 native helper（透過 accessibility / CGEventTap） |
| Vial GUI | External tool | 改完 `.vil` 後存檔；本系統 watch mtime 重 parse（read-only） |
| Hammerspoon `keystat.lua` | Deprecated | M4 後手動 disable；歷史 JSON 留作 baseline |

### External Dependencies

| Dependency | Purpose | Failure Mode |
|---|---|---|
| **macOS Accessibility API** | Native helper 監聽全域 keystroke | 權限被撤銷 → helper 失敗、web UI 顯示「helper disconnected」、stats 不更新但既有資料仍可查 |
| **Vial config file (`.vil`)** | Layout 主要資料來源 | 檔案不存在 / 解析失敗 → backend `/api/layout` 回 503、UI 顯示錯誤訊息 |
| **Docker Desktop (macOS)** | Backend + frontend container 化 | Docker 停 → web UI 不可用；helper 仍持續寫 SQLite（host-side） |
| **Python pynput** | Helper 全域 listener | 套件壞 / macOS 升級不相容 → fallback 評估 Swift CGEventTap |
| **SQLite** | Stats 持久化 | DB 損毀 → 從最近 snapshot import 重建；JSON baseline 永遠可重 import |

---

## Architecture

### High-Level Diagram

```
┌──────────────────────────────────────────────────────────────────┐
│  macOS host                                                      │
│                                                                  │
│  ~/Library/Application Support/keyboard-manager/keystat.db       │
│  ▲                                                               │
│  │                                                               │
│  ┌────────────────────────────────────────────────────────────┐  │
│  │  native-helper/   (Python, launchd-managed)                │  │
│  │   ┌──────────────┐   ┌──────────────┐   ┌──────────────┐  │  │
│  │   │ pynput       │   │ AppTracker   │   │ EventSink    │  │  │
│  │   │ (Listener)   │──▶│ (NSWorkspace)│──▶│ ┬─SQLite     │  │  │
│  │   └──────────────┘   └──────────────┘   │ └─WS broadcast│ │  │
│  │                                          └──────┬───────┘  │  │
│  │                                                 │ :8765    │  │
│  └─────────────────────────────────────────────────┼──────────┘  │
│                                                    │             │
│  ┌─────────────────────────────────────────────────┼──────────┐  │
│  │  Docker network (bridge)                        │          │  │
│  │  ┌─────────────────────────────────┐            │          │  │
│  │  │ backend  (FastAPI, :8000)       │◀───────────┘          │  │
│  │  │  ┌───────────┐ ┌──────────────┐ │ host.docker.internal  │  │
│  │  │  │ VialParser│ │ StatsRepo    │ │                       │  │
│  │  │  └─────┬─────┘ └──────┬───────┘ │                       │  │
│  │  │        │              │         │                       │  │
│  │  │        ▼              ▼         │                       │  │
│  │  │  ┌──────────────────────────┐  │                       │  │
│  │  │  │ HTTP /api/* + WS /api/live│ │                       │  │
│  │  │  └──────────┬───────────────┘  │                       │  │
│  │  └─────────────┼──────────────────┘                       │  │
│  │                │                                          │  │
│  │  ┌─────────────▼─────────────┐                            │  │
│  │  │ frontend  (nginx, :80)    │                            │  │
│  │  │  ┌─────────────────────┐  │                            │  │
│  │  │  │ index.html / app.js │  │                            │  │
│  │  │  │  - StaticViewer     │  │                            │  │
│  │  │  │  - Interactive      │  │                            │  │
│  │  │  │  - StatsDashboard   │  │                            │  │
│  │  │  └─────────────────────┘  │                            │  │
│  │  └─────────────┬─────────────┘                            │  │
│  └────────────────┼──────────────────────────────────────────┘  │
│                   │ :8080 → host                                │
│  ┌────────────────▼──────────────────────────────────────────┐  │
│  │  Browser (http://localhost:8080)                          │  │
│  └────────────────────────────────────────────────────────────┘ │
└──────────────────────────────────────────────────────────────────┘

           Mount paths (read-only / read-write):
           ~/Projects/keyboard-map/mylayout.vil → /data/mylayout.vil:ro
           ~/Library/.../keystat.db             → /data/db/keystat.db:rw
```

### Components

| Component | Responsibility | Interface |
|---|---|---|
| **VialParser** | 讀 `.vil` JSON、把 layout/tap_dance/combo/key_override 解析成記憶體模型 | Python function `parse(path) → Layout` |
| **KeycodeResolver** | 把 raw keycode（`LT1(KC_TAB)`、`KC_LSFT` 等）翻成 `{tap, hold, branches, label_top, label_bottom, expanded_kind}` | `resolve(raw: str, ctx: LayoutContext) → ResolvedKey` |
| **LayoutAPI** | HTTP endpoint，回 parsed layout 給 frontend；快取 + mtime watch | FastAPI router |
| **StatsRepo** | SQLite CRUD 抽象（events / apps / snapshots）；提供 top-N、heatmap aggregation | Python class with methods `top_n()`, `heatmap()`, `import_json()` |
| **StatsAPI** | HTTP endpoint，回 stats / heatmap | FastAPI router |
| **JSONImporter** | 把 `~/keystat-counts.json` 讀進 SQLite，做一次 baseline aggregation | CLI script `backend/scripts/import_keystat.py` |
| **LiveBridge** | Backend WS endpoint，dial 進 helper :8765、把 events 轉發給瀏覽器 | FastAPI WS route + `websockets` client |
| **NativeHelper.Listener** | pynput global key listener，產生 `KeyEvent(ts, key, modifiers, action)` | Python thread |
| **NativeHelper.AppTracker** | 用 `NSWorkspace.frontmostApplication()` 取當前 bundle ID，cache 100ms | Python helper |
| **NativeHelper.EventSink** | 把 KeyEvent 同時寫 SQLite（batch 5s）+ WebSocket broadcast | Python async coroutine |
| **NativeHelper.WSServer** | WebSocket server on :8765，多 subscriber 容忍 | `websockets.serve` |
| **Frontend.StaticViewer** | 渲染 6 layer keyboard grid SVG + 智慧模式 keycode 展開 | DOM module |
| **Frontend.Interactive** | 訂閱 `/api/live`、依即時 keypress 切換 grid view | DOM module + WebSocket client |
| **Frontend.StatsDashboard** | Heatmap overlay + top-N 表格 + per-app filter | DOM module + Canvas |

### Data Flow

**靜態查詢路徑**：
1. Browser → `GET http://localhost:8080/api/layout`
2. nginx proxy → backend :8000
3. backend VialParser.parse(`/data/mylayout.vil`) → 解析（首次）或從 memory cache 取
4. 回傳 JSON 樹

**Live capture 路徑**：
1. User 在實體鍵盤按鍵
2. macOS HID → pynput on_press handler
3. NativeHelper.Listener → 取 modifier state + 從 AppTracker 取 bundle ID
4. EventSink 同時做兩件事：
   - 加進 SQLite write buffer（每 5 秒 flush）
   - 透過 WSServer broadcast 給訂閱者
5. backend LiveBridge 收 WS event → 轉發給 browser
6. Frontend.Interactive 收到 → 更新 view state、re-render grid

**Heatmap 查詢路徑**：
1. Browser → `GET /api/stats/heatmap?app=com.googlecode.iterm2`
2. backend StatsRepo 跑 aggregation SQL（`GROUP BY key`）
3. HeatmapMapper 對映每個 key 到 `(layer, row, col)`（使用 VialParser cache 找位置）
4. 回傳 cells[] + unmapped[]

### Sequence Diagrams

**Interactive hold 預覽（M4 P0 場景）**：

```
User    Keyboard    Helper                       Backend                Frontend
 │         │          │                            │                       │
 │ press   │          │                            │                       │
 │ Space ──▶ HID ───▶ on_press("space")            │                       │
 │         │          │                            │                       │
 │         │          ├─ App = "iterm2"            │                       │
 │         │          ├─ Buffer.append(...)        │                       │
 │         │          └─ WS.broadcast(             │                       │
 │         │              {type:"down",key:"space",│                       │
 │         │               app:"iterm2", ts:...})  │                       │
 │         │                  │                    │                       │
 │         │                  │ WS event           │                       │
 │         │                  └──────────────────▶│                       │
 │         │                                       │ /api/live (proxy)     │
 │         │                                       └──────────────────────▶│
 │         │                                                               │
 │         │                                                               ├─ state.held.add("space")
 │         │                                                               ├─ if mapsTo MO(layer) → activeLayer = N
 │         │                                                               └─ re-render grid
 │         │                                                               │
 │         │                                                       (< 100ms target)
```

**JSON import（M2 一次性）**：

```
User CLI                JSONImporter          StatsRepo          SQLite
  │                         │                    │                  │
  │ python import.py        │                    │                  │
  ├────────────────────────▶│                    │                  │
  │                         ├─ load json         │                  │
  │                         ├─ snapshot_id =      │                  │
  │                         │   create_snapshot  │                  │
  │                         ├─────────────────────▶                 │
  │                         │                    ├─ INSERT snapshot │
  │                         │                    ├─────────────────▶│
  │                         │ for (app, key, count):                │
  │                         │   split_mods(key) → (mods, base)      │
  │                         │   upsert_app(bundle)                  │
  │                         │   insert_event(snapshot_id, app,      │
  │                         │                base, mods, count, ts) │
  │                         ├─────────────────────▶                 │
  │                         │                    ├─ batch INSERT    │
  │                         │                    ├─────────────────▶│
  │                         │                    │                  │
  │ "imported 5367 mod      │                    │                  │
  │  + 131720 single rows"  │                    │                  │
  │◀────────────────────────┤                    │                  │
```

---

## Data Model

### Entities

| Entity | Owner | Lifecycle |
|---|---|---|
| **Event** | NativeHelper.EventSink (writer) / StatsRepo (reader) | Created on每次 keypress（live）或 JSON import；不刪除（hard archive only） |
| **App** | StatsRepo | Upsert 在 import 或 live capture 第一次見到該 bundle；可手動編輯 bucket |
| **Snapshot** | StatsRepo | 每次 JSON import / helper session 開頭 create；不刪除 |
| **Layout（memory only）** | VialParser | App boot 時 parse；mtime change 時 re-parse；無持久化 |

### Schema

```sql
-- events: 一筆 = 一次擊鍵記錄
CREATE TABLE events (
  id           INTEGER PRIMARY KEY AUTOINCREMENT,
  ts           INTEGER NOT NULL,                   -- epoch seconds (UTC)
  app_bundle   TEXT    NOT NULL,                   -- e.g. "com.googlecode.iterm2"
  key          TEXT    NOT NULL,                   -- base key, e.g. "j", "space", "return"
  modifiers    TEXT    NOT NULL DEFAULT '',        -- "cmd+shift" sorted alphabetically; "" if none
  count        INTEGER NOT NULL DEFAULT 1,         -- 1 for live event; > 1 for aggregated JSON-import row
  snapshot_id  INTEGER NOT NULL REFERENCES snapshots(id),
  source       TEXT    NOT NULL                    -- "native_helper" | "hs_keystat_json"
);

CREATE INDEX idx_events_app_key    ON events(app_bundle, key);
CREATE INDEX idx_events_modifiers  ON events(modifiers);
CREATE INDEX idx_events_ts         ON events(ts);
CREATE INDEX idx_events_snapshot   ON events(snapshot_id);

-- apps: bundle ID 到顯示名稱與 bucket 的映射
CREATE TABLE apps (
  bundle_id     TEXT    PRIMARY KEY,
  display_name  TEXT,
  bucket        TEXT,                              -- "terminal"|"browser"|"editor"|"chat"|"launcher"|NULL
  first_seen_ts INTEGER NOT NULL,
  last_seen_ts  INTEGER NOT NULL
);

-- snapshots: 紀錄每次 import / capture session 的起點
CREATE TABLE snapshots (
  id     INTEGER PRIMARY KEY AUTOINCREMENT,
  ts     INTEGER NOT NULL,                         -- session start epoch sec
  source TEXT    NOT NULL,                         -- "hs_keystat_json" | "native_helper"
  notes  TEXT                                      -- optional, e.g. "M0 baseline import 8 days"
);
```

### Migration Strategy

- **Forward**：MVP v1 用單一 SQL 檔 `backend/migrations/001_initial.sql`；boot 時若 table 不存在自動建立
- **Backward**：drop database file → 從 JSON 重 import baseline；helper restart 後新事件繼續寫
- **Backfill**：JSON import 是 one-shot；無漸進 backfill 需求
- **Coexistence**：M2–M3 期間 Hammerspoon `keystat.lua` 仍寫 `~/keystat-counts.json`、helper 寫 SQLite，**不雙寫至 SQLite**；M4 結束後手動 disable HS

---

## API Contracts

### Endpoints

| Method | Path | Purpose | Auth |
|---|---|---|---|
| GET | `/health` | Liveness + path existence probe | none |
| GET | `/api/layout` | Parsed `.vil` 樹（含 layers / tap_dance / combos / key_overrides） | none |
| GET | `/api/layout/keycodes` | 全部 keycode → 人類字串字典 | none |
| GET | `/api/apps` | 已知 apps + bucket | none |
| GET | `/api/stats` | Top-N 鍵；params: `app`、`top` (default 50)、`kind` (`single`/`mod`/`all`) | none |
| POST | `/api/stats/import` | 觸發 JSON import；body `{path, source}` | none |
| GET | `/api/stats/heatmap` | 每 `(layer, row, col)` count；params: `app`、`include_modifiers` | none |
| WS | `/api/live` | 訂閱 helper events；proxies `ws://host.docker.internal:8765` | none |

### Request / Response Shape

```jsonc
// GET /api/health
{
  "status": "ok",
  "vial_path": "/data/mylayout.vil",
  "vial_exists": true,
  "db_path": "/data/db/keystat.db",
  "db_exists": true,
  "helper_reachable": true       // dial to host.docker.internal:8765 succeeded recently
}

// GET /api/layout
{
  "vial_version": 1,
  "uid": 5010774632021243529,
  "layers": [
    {
      "index": 0,
      "name": "BASE",
      "rows": [
        {
          "row": 0,
          "keys": [
            { "col": 0, "raw": "KC_GRAVE", "resolved": {
                "expanded_kind": "plain",
                "label_top": "`",
                "label_bottom": null,
                "tap": "`",
                "hold": null
            }},
            // ... or null for -1 slot
          ]
        }
        // ... 10 rows
      ]
    }
    // ... 6 layers
  ],
  "tap_dance": [
    {
      "index": 0,
      "tap": "Cmd+1",
      "hold": "Ctrl",
      "double_tap": null,
      "tap_hold": null,
      "tap_term_ms": 200
    }
    // ... 16 entries
  ],
  "combos": [
    { "index": 0, "trigger": ["KC_J", "KC_K"], "output_label": "Esc" }
    // ...
  ],
  "key_overrides": [],
  "encoder_layout": [ /* ... */ ]
}

// GET /api/stats?app=com.googlecode.iterm2&top=10&kind=single
{
  "scope": { "app": "com.googlecode.iterm2", "kind": "single", "top": 10 },
  "total_events": 92324,
  "rows": [
    { "key": "j", "modifiers": "", "count": 5892, "pct": 4.47 },
    // ...
  ]
}

// GET /api/stats/heatmap?app=com.googlecode.iterm2
{
  "scope": { "app": "com.googlecode.iterm2" },
  "max_count": 5892,
  "cells": [
    { "layer": 0, "row": 7, "col": 1, "key": "h", "count": 1946 },
    { "layer": 0, "row": 7, "col": 2, "key": "j", "count": 5892 }
    // ...
  ],
  "unmapped": [
    { "key": "f19", "count": 1201, "reason": "no physical position" }
  ],
  "coverage_pct": 92.3
}

// WS /api/live — server → client frames
{ "type": "down", "key": "space", "modifiers": "", "app": "com.apple.Terminal", "ts": 1748401234 }
{ "type": "up",   "key": "space", "modifiers": "", "app": "com.apple.Terminal", "ts": 1748401234 }
{ "type": "helper_disconnected", "ts": 1748401300 }
```

### Error Codes

| Code | HTTP | Meaning | Caller Action |
|---|---|---|---|
| `VIAL_NOT_FOUND` | 503 | `/data/mylayout.vil` 不存在 | 檢查 docker-compose volume mount |
| `VIAL_PARSE_ERROR` | 422 | JSON 格式錯 / schema 不符 | 用 Vial GUI 重存 |
| `DB_NOT_INITIALIZED` | 503 | SQLite 還沒建表 | 等 startup migration 完成 |
| `HELPER_UNREACHABLE` | 503 (WS upgrade fail) | dial helper :8765 失敗 | 確認 helper 啟動 + accessibility 權限 |
| `INVALID_QUERY` | 400 | top > 500 / 不認識的 kind | 修 query params |

### Versioning Strategy

- 個人 tool、單一 client（自己的 browser），不做版本化
- API path 不加 `/v1`，未來如有 breaking change 直接改
- 若 schema 變動：drop & re-import JSON baseline，可接受

---

## Non-Functional Requirements

| Category | Target | Measurement | How Achieved |
|---|---|---|---|
| **Interactive latency** | p99 < 100ms（hold → grid re-render） | Browser Performance API + 手動 stopwatch | WebSocket push、frontend 不做 fetch、grid render 純 DOM 切換 |
| **Stats query latency** | p95 < 200ms（top-N over 1M rows） | uvicorn access log | Composite indexes `idx_events_app_key`、`idx_events_modifiers`、SQLite in-process（無網路） |
| **Capture overhead** | < 1% CPU idle, < 5MB RAM | macOS Activity Monitor | pynput async listener、SQLite WAL mode、batch 5-second commit |
| **Disk durability** | 預期 SSD 壽命無影響 | events table 寫入頻率（< 0.05 commit/sec avg） | batch insert、無 per-key fsync |
| **Startup time** | docker compose up → healthy < 10 秒 | `time docker compose up -d --wait` | slim Python image、無 ORM、stdlib sqlite |
| **Availability** | Best-effort（personal tool） | n/a | helper 死 → launchd 重啟；docker 死 → user 手動 |
| **Data integrity** | 0 lost JSON-baseline records | 比對 JSON 內非 `__meta` key 數量 = events.count | import script 用 SQLite transaction、失敗 rollback |
| **Helper recovery** | < 5 秒從 crash 回復 | launchd `KeepAlive=true` | launchd plist |

---

## Technology Choices

| Concern | Choice | Alternatives | Rationale |
|---|---|---|---|
| **Backend lang** | Python 3.12 | Node/TypeScript, Go | 復用 `keystat_analyze.py` 邏輯零成本 |
| **Backend framework** | FastAPI | Flask, Starlette raw | WebSocket + REST 同框、type hint 自動驗證 |
| **DB** | SQLite (stdlib) | DuckDB, Postgres | Single-user local；Python stdlib 內建、無外部依賴 |
| **Migration** | 手寫 SQL + boot-time check | Alembic | Schema 簡單、不值得 ORM |
| **Native capture** | pynput | Swift CGEventTap, Karabiner-DriverKit | Python 同 stack、prototype 速度；fallback 留為 Open Question |
| **App tracking** | pyobjc `NSWorkspace.frontmostApplication` | parsing `ps -A` | 官方 API、即時 |
| **Frontend framework** | None (vanilla HTML/JS) | React, Vue, Svelte | UI 簡單、零 build step、Docker image 更小 |
| **Frontend serving** | nginx | Caddy, FastAPI static | nginx 內建 WS proxy、業界標準 |
| **WebSocket** | `websockets` (Python) + browser WebSocket API | Socket.IO | 標準 protocol、無 polling fallback 需求 |
| **Charting** | TBD: chart.js or vanilla Canvas | D3.js | 等 M3 開做時再選；heatmap 簡單，Canvas 也夠 |
| **Container** | Docker compose | Podman, raw containers | macOS Docker Desktop 通用、user 已有 |
| **Process supervision (helper)** | launchd plist | brew services, pm2 | macOS 原生、KeepAlive 直接 |
| **Linting** | ruff | flake8 + black + isort | 一個 tool 全包 |
| **Testing** | pytest | unittest | 業界預設 |

---

## Integration Points

| Touchpoint | Type | Contract | Backwards Compat |
|---|---|---|---|
| **Vial `.vil` file** | File system (read-only) | Vial v1 JSON schema | Yes — Vial v1 schema 已穩定多年 |
| **Hammerspoon `keystat.lua`** | None (deprecated) | n/a | Yes — JSON 留作 historical baseline |
| **macOS Accessibility API** | OS API (read) | `CGEventTap` / `pynput` | Best-effort — macOS 升級可能改 permission UX |
| **`~/keystat-counts.json`** | File system (read, one-shot) | Hammerspoon-defined schema：`{__meta, [bundle_id]: {[key]: count}}` | Yes — 不再產生新版本 |
| **Browser** | HTTP + WS via nginx | Frontend code 即 contract | n/a — same-origin |

### Rollout Strategy

- **No feature flags**：personal tool、單一 user、不需要漸進 rollout
- **No A/B**：n/a
- **Kill switch**：`docker compose down` 立刻停所有 web 功能；helper `launchctl unload` 停 capture
- **Rollback**：
  - Bad layout parse → fix code 或 git revert
  - Bad SQLite migration → 刪 `.db` 從 JSON 重 import
  - Helper 不穩 → `launchctl unload com.keyboard-manager.helper.plist`，回歸 Hammerspoon

---

## Codebase Patterns to Follow

> 參考 `~/Projects/keyboard-map/` 既有資源（**這個 keyboard-manager repo 是 greenfield，所以下表參考的是 sibling project 的 pattern，不是 in-repo pattern**）。

| Pattern | Where to Find | Why Follow |
|---|---|---|
| **Stats aggregation** | `~/Projects/keyboard-map/keystat_analyze.py:71-86` (`aggregate()`) | 已被 8-day baseline 驗證過 |
| **Mod-combo split** | `~/Projects/keyboard-map/keystat_analyze.py:60-68` (`split_mods`) | API 跟 SQLite `modifiers` 欄位都需要 |
| **App bucket mapping** | `~/Projects/keyboard-map/keystat_analyze.py:20-48` (`APP_BUCKETS`) | 移植進 `apps` table seed |
| **Vial `.vil` schema** | `~/Projects/keyboard-map/mylayout.vil` (entire file) | Ground truth |
| **Layout spec context** | `~/Projects/keyboard-map/spec.md`、`hotkey-analysis.md` | 設計動機 + 驗證對照 |

> 本 module 的 in-repo patterns 在 implementation milestones 才會出現；M1+ 才開始累積。

---

## Risks & Trade-offs

| Risk | Likelihood | Impact | Mitigation |
|---|---|---|---|
| **pynput macOS 權限 UX 不穩** | M | M | M4 開頭做 1-day prototype；不行 → Swift CGEventTap fallback |
| **Helper hold timing 精度不足（mod-tap 內部 timing 看不到）** | H | L | PRD 已接受：keystat 看的是 macOS event 層、不是 firmware 內部；本系統不嘗試還原 firmware timing |
| **Docker `host.docker.internal` 解析失敗** | L | M | docker-compose 加 `extra_hosts: ["host.docker.internal:host-gateway"]`、liveness probe 偵測 |
| **HS keystat 與 helper 雙寫 SQLite 衝突** | L | H | Spec 明確：M4 ship 前 HS 只寫 JSON、不碰 SQLite；M4 後 user 手動 disable HS |
| **`.vil` schema 變化（Vial 升版）** | L | M | Parser 用 `vial_protocol` 欄位 gate、不認得就 fail-fast 回 422 |
| **SQLite 寫入競爭** | L | L | helper 用 WAL mode + 5s batch；backend 只讀 |
| **macOS 升級破壞 Accessibility** | M | H | 文件化 reinstall 步驟、helper 啟動時 self-check 並回 helper_disconnected event |
| **Heatmap 對映 mod-combo 模糊** | M | L | `unmapped[]` 透明顯示、不嘗試硬塞到 base 位置 |

---

## Decisions Log

| Decision | Choice | Alternatives | Rationale |
|---|---|---|---|
| Process topology | 3-process（helper host + backend docker + frontend docker） | Monolith / Electron | macOS Docker 限制強迫拆分；3-process 已是 minimal |
| Helper lang | Python (pynput) | Swift CGEventTap, Karabiner DriverKit | 同 backend stack、快速 prototype；Swift 留作 follow-up |
| Backend lang | Python + FastAPI | Node/Next.js, Go | 復用 `keystat_analyze.py` |
| Frontend | Vanilla HTML/JS | React, Svelte | 零 build step、UI 簡單 |
| DB | SQLite (stdlib) | DuckDB, Postgres | Single-user local；無外部依賴 |
| Migration | 手寫 SQL + boot check | Alembic | Schema 小、不值得 ORM 化 |
| API versioning | 不版本化 | `/api/v1/*` | Personal、單 client、breaking change 直改 |
| WS routing | Backend proxy helper | Browser 直連 helper :8765 | nginx 統一入口、避免 CORS / 防火牆問題 |
| Capture stats overlap | M4 ship 後手動 disable HS | 自動接管 HS | HS 是 user 自己的 dotfiles、避免動 |
| JSON baseline 處理 | One-shot import | 持續 sync JSON ↔ SQLite | JSON 廢用後不會再變 |
| Smart-mode rendering | 雙模（plain 單行 / MT-LT-TD 雙行） | 全雙行 / hover-only | 平衡視覺密度與快速辨識（PRD 決定） |

---

## Open Questions

- [ ] pynput 在 macOS 15+ accessibility prompt UX 是否吃 hold timing 精度（M4 prototype 量測）
- [ ] Helper 寫 SQLite 用每鍵 commit / 每 5 秒 batch — 後者磁碟壽命友善但 crash 失 5 秒資料，可否接受
- [ ] Heatmap 對 mod-combo（如 `cmd+1`）— 算在 base `1` 位、或獨立 view
- [ ] `.vil` hot-reload — watch mtime / 手動 reload 哪個更實用
- [ ] Frontend chart 用 chart.js 還是純 Canvas（M3 開做時定）
- [ ] App bucket 表硬編還是 UI 可改（暫硬編）
- [ ] 是否內建 web UI 重啟 helper 的能力（helper self-recover 即可？）
