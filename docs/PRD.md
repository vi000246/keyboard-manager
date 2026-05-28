# Product Requirements Document — keyboard-manager

> Generated 2026-05-28. Mirror of the PRD section in `~/.claude/plans/claude-init-git-init-fancy-pinwheel.md`. Keep in sync if the canonical plan is updated.

## Problem Statement

User 自己設計鍵盤 layout 時，要不斷在 Vial GUI 切換 layer / 點 keycode 才能看清楚當前設定。看到 `LT1(KC_TAB)` 或 `TD(2)` 必須回去 cross-reference 才能確認該鍵實際行為。與此同時，自己已有的擊鍵統計與 layout 是脫鉤的——無法在鍵盤位置圖上看「這顆鍵每天按 1500 次但放在 pinky 死角」這種訊號。

## Evidence

- Vial 顯示 `TD(0)` 不直接寫「tap=Cmd+1, hold=Ctrl」（要去 tap_dance 區查 index 0）
- `mylayout.vil` 有 6 個 layer × 10 row × 7 col + tap dance + combo + key override，單一頁面看不完整
- 既有 `keystat_analyze.py` 輸出純文字 table，無視覺化、無跟鍵盤位置對位
- 8 天累積 keystat 資料（137k 擊鍵）證明願意持續產生使用統計

## Proposed Solution

本地 Docker web tool，兩個主要頁面 + native 抓鍵 helper：

1. **Static Viewer** — 6 個 layer 用 Vial 拓樸畫成 keyboard grid，每顆鍵用「智慧模式」展開
2. **Interactive Simulator** — 滑鼠點 hold/layer 鍵能即時切換 view；WebSocket 接 native helper 的真實按鍵事件
3. **Stats Reports** — keystat 進 SQLite，提供 heatmap on keyboard layout + 表格/bar chart top-N

## Key Hypothesis

我們相信展開所有 keycode + 即時 hold 預覽 + heatmap 套位能讓 user 在 60 秒內看出「哪顆鍵浪費了」「哪個 layer 的某顆鍵設計錯了」，比 Vial GUI 加上跑 `keystat_analyze.py` 快至少 5×。

我們會知道我們做對了當 **user 在改 `mylayout.vil` 之前先看 keyboard-manager 的 heatmap、且每月至少使用一次來輔助 layout 決策**。

## What We're NOT Building

- Layout 編輯（Vial 已做好）
- Firmware flash（Vial 做）
- 跨平台（macOS only）
- 多 user / cloud sync（personal tool）
- 跟其他 keyboard 韌體相容（只認 Vial `.vil`）

## Success Metrics

| Metric | Target | How Measured |
|---|---|---|
| 顯示 `mylayout.vil` 全部 6 layer 的展開圖 | 100% keycode 正確翻譯 | 比對 `.vil` 與 web UI |
| Hold key 後 grid view 切換延遲 | < 100ms | helper → web UI re-render |
| Heatmap 涵蓋 keystat 90% 擊鍵 | per-app + 全域兩個 view 都 work | SQLite 行數 vs heatmap 涵蓋筆數 |
| MVP 1 個月內 ship 完所有 milestone | M1–M5 全綠 | git log + 自己驗收 |

## MoSCoW

| Priority | Capability |
|---|---|
| Must | `.vil` parser, Static Viewer, Interactive Simulator, SQLite stats, Heatmap, Native helper, JSON importer |
| Should | Top-N tables, docker compose 一鍵起 |
| Could | Time-series heatmap, bigram analysis |
| Won't | Layout editing, firmware flash, multi-user, cross-platform |

## Milestones

| # | Milestone | User-Visible Value |
|---|---|---|
| 0 | Bootstrap | Repo / claude init / Docker scaffold |
| 1 | Static Viewer | 開 web 看到 `.vil` 6 個 layer 完整展開 |
| 2 | Stats baseline | JSON 一次匯入 SQLite + 表格報表 |
| 3 | Heatmap on layout | 統計疊在 keyboard grid 上 |
| 4 | Native helper + Interactive | 真實按鍵 → web UI 即時反應 + 取代 HS keystat |
| 5 | Polish | docker compose 一鍵起、README、launchd plist |

See the canonical plan for detailed milestone breakdowns and verification.
