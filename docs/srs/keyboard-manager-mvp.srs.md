---
linear_issue: null
---
# SRS: keyboard-manager MVP

## Metadata
- **Module**: `keyboard-manager`
- **Module Spec**: `docs/spec/keyboard-manager.spec.md`
- **Source PRD**: `docs/PRD.md`
- **Source Linear Issue**: N/A — standalone personal project
- **Created**: 2026-05-28
- **Grill level**: 2 (light)
- **Implementation Plans**:
  - `docs/plans/keyboard-manager-mvp.plan.md` — 28 tasks (M1–M5), Mode B (task-level test-first), Size=L, Rigor=balanced

## Feature Summary

MVP v1 為 `keyboard-manager` 模組的 **foundational delivery** — 同時建立整個系統的初始架構。涵蓋 Vial `.vil` 解析、SQLite 統計儲存、heatmap 視覺化、macOS 全域按鍵 helper、WebSocket live 推播。這不是「在既有模組上加 feature」，而是「把模組從零做出來」。

## Delta from Current Module State

> Module 目前只有 scaffold（FastAPI `/health` endpoint、nginx 空殼、helper README placeholder）。此 SRS 描述「scaffold → MVP」這段 delta。完整目標架構見 `docs/spec/keyboard-manager.spec.md`。

### New / Changed API Endpoints

| Method | Path | Milestone | Purpose | Auth |
|---|---|---|---|---|
| GET | `/health` | M0 ✅ | Liveness probe（已實作） | none |
| GET | `/api/layout` | M1 | 回傳解析後 `.vil` 樹（6 layers + tap dance + combos） | none (localhost) |
| GET | `/api/layout/keycodes` | M1 | 列出所有 keycode 的人類可讀翻譯字典 | none |
| POST | `/api/stats/import` | M2 | 一次性匯入 `~/keystat-counts.json` 至 SQLite | none |
| GET | `/api/apps` | M2 | 回傳已知 app bundle + bucket 分類 | none |
| GET | `/api/stats` | M2 | Top-N 鍵與 mod-combo（query: `app`, `top`, `kind=single\|mod`） | none |
| GET | `/api/stats/heatmap` | M3 | 每 `(layer, row, col)` 的擊鍵 count | none |
| WS | `/api/live` | M4 | 反向代理 native-helper events 給瀏覽器 | none |

### New / Changed Data Models

新建（前無此模組，全部都是新增）：

- **SQLite `events` table** — 一筆=一次擊鍵；JSON baseline import 用 aggregated rows（`count > 1`），live capture 用 per-event rows（`count = 1`）
- **SQLite `apps` table** — bundle ID 對 bucket（terminal/browser/editor/chat/launcher）映射
- **SQLite `snapshots` table** — 記每次 import / capture session 起點，用於溯源
- **In-memory `Layout` 樹** — `.vil` 解析後常駐記憶體，watch file mtime hot-reload

完整 schema 見 Module Spec §Data Model。

### Changed Business Logic

無「改動」— 是「新建」。所有邏輯遵循 Module Spec §Components 定義：

- **Vial Parser** — 讀 JSON `.vil`，把 `LT1(KC_TAB)` / `TD(0)` / `LGUI_T(KC_ENTER)` 等 wrapper 展開成 `{tap, hold, branches}` 結構
- **Keycode Resolver** — 把 QMK keycode（`KC_GRAVE`, `LSFT(KC_SCOLON)`）翻成人類字串（`` ` ``、`:`）
- **Stats Aggregator** — 移植自 `~/Projects/keyboard-map/keystat_analyze.py` 的 `split_mods` / `is_modifier_combo` / `APP_BUCKETS` 邏輯
- **Heatmap Mapper** — 把 keystat 的 key name（如 `space`, `j`, `cmd+1`）對映到 `(layer, row, col)` 位置；無法對映的鍵（例如 keystat 是 macOS event 層，但 firmware 上是 `MO(1)`）走 fallback bucket
- **Native Capture** — pynput 監聽全域 `on_press` / `on_release`，搭配 `NSWorkspace.frontmostApplication` 取 bundle ID

### Explicitly Out of Scope

- **Layout 編輯** — Vial 已做，本 module 一律 read-only
- **跨平台 capture** — macOS-only；Linux/Windows 不寫 fallback
- **bigram / n-gram 分析** — Module Spec §Open Questions 列為 future
- **Time-series heatmap** — schema 有 timestamp，UI 暫不做
- **Cloud sync / multi-user** — personal tool，無 auth、無遠端
- **Vial → firmware diff** — 不比較 .vil 跟 device 內 keymap

## Functional Requirements

- [ ] FR-1 解析 `mylayout.vil` 6 layers 全部 keycode，TRN 之外全部展開為人類可讀
- [ ] FR-2 Static Viewer：layer dropdown 切換、每顆鍵智慧模式（plain=1 行；MT/LT/TD=2 行）、TD branch hover 看細節
- [ ] FR-3 JSON importer：一次性把 `~/keystat-counts.json` 8 天 137k 擊鍵讀進 SQLite，行數與 JSON 內非 `__meta` 鍵值對應
- [ ] FR-4 Stats API：top-N 單鍵與 mod-combo，支援 per-app filter，結果與 `keystat_analyze.py` 對得起來
- [ ] FR-5 Heatmap overlay：global view + per-app dropdown，覆蓋 ≥ 90% 擊鍵
- [ ] FR-6 Native helper：pynput 全域 capture，寫 SQLite events 表，附 timestamp + bundle ID
- [ ] FR-7 WebSocket live：hold modifier / layer key → web UI grid 即時切換 view，延遲 < 100ms
- [ ] FR-8 Helper crash recovery：launchd 自動拉起、helper 死掉 web UI 顯示「disconnected」狀態
- [ ] FR-9 Hammerspoon keystat 廢用：M4 ship 後給出步驟讓 user 自己 disable HS binding（不自動改 HS）

## Non-Functional Requirements

| Category | Target | How Achieved |
|---|---|---|
| **Interactive latency** | < 100ms (helper → grid re-render) | WebSocket 推播、frontend 不做網路 round-trip |
| **Stats query latency** | < 200ms p95 (top-N for 1M rows) | SQLite indexes on `(app_bundle, key)` 與 `ts` |
| **Capture overhead** | < 1% CPU idle, < 5MB RAM | pynput async listener、batch SQLite write 每 5 秒 flush |
| **Disk durability** | SSD friendly | events table batch insert（避免每鍵 fsync） |
| **Startup time** | docker compose up < 10 秒到 healthy | slim image、無 ORM、stdlib sqlite |
| **Availability** | Best-effort（personal tool） | 無 SLA；helper 死掉走 launchd 重啟 |

## Architecture Notes

完整架構見 `docs/spec/keyboard-manager.spec.md`。本 SRS 只 highlight 跟 PRD 痛點直接對應的關鍵：

1. **Native helper 為何不在 Docker** — Docker Desktop on macOS 跑 hypervisor，無 accessibility API；強制 host-side。詳見 spec §System Context > External Dependencies。
2. **WebSocket 路由**：browser → nginx :8080 → backend :8000 → helper :8765。nginx 統一入口，CORS 不用設定。
3. **Vial 解析快取**：`.vil` parse 結果常駐 process memory，檔案 mtime 變才重 parse。
4. **Heatmap 對映 fallback**：keystat 抓 macOS event-layer keycode（已經被 firmware 翻譯過），所以 firmware 上的 `LT1(KC_TAB)` hold 結果是「進 NAV」event-layer 看不到、只看到具體 NAV 內的 key。Heatmap 只能對應「base layer 位置」，這是 PRD 接受的限制（M3 Out of scope: time-series & bigram）。

## Acceptance Criteria

### AC-1: `.vil` 解析正確覆蓋所有 keycode
- **Given**: `/data/mylayout.vil` 是合法 Vial v1 JSON，含 6 layers、16 tap dance 槽、16 combo 槽
- **When**: 呼叫 `GET /api/layout`
- **Then**: response 含 `layers[0..5]`、每個 layer `rows[0..9].keys[0..6]` 對映 raw `.vil` 內容；每個非 `-1` 也非 `KC_TRNS` 的 key 都有 `resolved.label_top`（非空字串）；KC_TRNS 標記為 `transparent: true`
- **Test**: `backend/tests/test_layout_api.py::test_mylayout_full_coverage`

### AC-2: Tap-dance / Mod-tap / Layer-tap 完整展開
- **Given**: `tap_dance[0] = ["LGUI(KC_1)", "KC_LCTRL", "KC_NO", "KC_NO", 200]` 在 `.vil` 內
- **When**: layer 0 第 4 列拇指鍵 raw 為 `"TD(0)"`
- **Then**: response 的 resolved 物件含 `tap: "Cmd+1"`、`hold: "Ctrl"`、`double_tap: null`、`tap_hold: null`、`tap_term_ms: 200`、`expanded_kind: "tap-dance"`、`branches[].label`
- **Test**: `backend/tests/test_keycode_resolver.py::test_td_full_branches`

### AC-3: Static Viewer 正確渲染 6 layer
- **Given**: backend 已啟動、`/api/layout` 回應正常
- **When**: 開 `http://localhost:8080`、點 navigation 「Static Viewer」、layer dropdown 切到「Layer 4 — MEDIA」
- **Then**: keyboard grid 顯示 58 顆鍵的標籤；MEDIA layer 的 `KC_BRIU` / `KC_VOLU` 等鍵顯示為 `Brightness↑` / `Volume↑`；TRN 鍵顯示為灰色 fall-through 樣式
- **Test**: 手動驗證 + screenshot

### AC-4: JSON keystat 一次性匯入
- **Given**: `~/keystat-counts.json` 含 `__meta`、137k 擊鍵分散 42 app、startedAt 2026-05-20、lastFlush 2026-05-28
- **When**: 跑 `python backend/scripts/import_keystat.py ~/keystat-counts.json`
- **Then**: `events` 表行數 = JSON 內所有非 `__meta` key 數量（每個 (app, key) 一行，`count` 等於 JSON 的 value、`ts` 為 import 時刻、`modifiers` 從 key 字串拆解）；`apps` 表填入該 42 app；`snapshots` 表新增 1 行 `source = "hs_keystat_json"`
- **Test**: `backend/tests/test_import.py::test_full_import_8_day_baseline`

### AC-5: Stats API 與 `keystat_analyze.py` 對得起來
- **Given**: SQLite 已 import baseline
- **When**: 呼叫 `GET /api/stats?app=com.googlecode.iterm2&top=10&kind=single`
- **Then**: response 為 top-10 純單鍵（無 modifier）配 count，與 `python ~/Projects/keyboard-map/keystat_analyze.py | grep iterm2` 同樣 10 顆鍵、同樣 count
- **Test**: `backend/tests/test_stats_api.py::test_top_n_matches_legacy_analyzer`

### AC-6: Heatmap 涵蓋 ≥ 90% 擊鍵
- **Given**: SQLite 有 baseline + 至少 1 天 live capture
- **When**: `GET /api/stats/heatmap`（無 app filter）
- **Then**: `sum(response.cells[].count)` / `sum(events.count)` ≥ 0.90；無法對映的鍵（如 f19、cmd+1 這種 mod-combo 對映到 base 位置但 base 是字母）走 `unmapped[]` 列表並回報數量
- **Test**: `backend/tests/test_heatmap.py::test_coverage_90_percent`

### AC-7: Native helper 寫入 SQLite
- **Given**: helper 已啟動、accessibility 權限 grant、browser 連線 WebSocket
- **When**: user 在任意 app 連續打 30 秒「the quick brown fox」並有切 app
- **Then**: `events` 表新增筆數 ≥ 100；`app_bundle` 為非空字串、`ts` 為當下 epoch 秒、`modifiers` 在 shift+letter 等情境為 `"shift"`
- **Test**: `native-helper/tests/test_capture.py::test_writes_events_with_correct_app`

### AC-8: WebSocket hold-to-layer 延遲 < 100ms
- **Given**: helper 跑、browser 連 Interactive 頁
- **When**: user 按住左拇指中央（base 為 `LT1(KC_SPACE)`，hold 進 NAV）
- **Then**: 在 100ms 內 keyboard grid 重 render 為 NAV layer view；放開後重 render 回 base
- **Test**: 手動 stopwatch + Performance API console log

### AC-9: docker compose 一鍵起
- **Given**: 乾淨 clone 的 repo、`VIAL_CONFIG` env 指向真實 `.vil`
- **When**: `docker compose up -d`
- **Then**: 10 秒內 backend `/health` 200 OK 且 `vial_exists: true`；frontend `:8080` 回 index.html
- **Test**: `scripts/smoke.sh`（M5）

### AC-10: Hammerspoon cutover 文件化
- **Given**: M4 完成、helper 跑得起來
- **When**: user 跟著 `docs/migration-from-hammerspoon.md` 步驟
- **Then**: 能 disable HS keystat binding、不再雙寫；之前的 `~/keystat-counts.json` 不刪、留作歷史 baseline
- **Test**: 手動驗證 + diff `~/keystat-counts.json` 在 24 小時後 size 沒變

## Open Questions

- [ ] pynput vs Swift CGEventTap：pynput 在 macOS 15+ 對 accessibility 權限的 prompt UX 是否會吃掉 hold timing 精度？需 prototype 量測（M4 開頭）
- [ ] Helper 寫 SQLite 的 batching：每鍵 commit vs 每 5 秒 batch — 後者磁碟壽命友善但 crash 失 5 秒資料。可否接受？
- [ ] Heatmap 對 mod-combo（如 `cmd+1`）的處理：算在 `1` 位上、還是另開「mod-combo 列表」獨立 view？
- [ ] Vial `.vil` hot-reload：watch mtime 還是 user 在 UI 手動 reload？personal use 兩者都行
- [ ] App bucket 表的維護：硬編在 backend 還是 SQLite seed 後可由 UI 改？暫硬編
