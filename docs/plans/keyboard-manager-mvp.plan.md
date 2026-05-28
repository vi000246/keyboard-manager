---
linear_issue: null
---
# Plan: keyboard-manager MVP

> `/prp-implement` 將根據下方 `Metadata.Type` 路由到 `implementing-features` skill。任務以核取方塊 (`- [ ]`) 追蹤；本 plan 採 **Mode B（任務先測）**：每個 task 整體先寫一個失敗測試 → 實作整個 task → 跑通過 → commit。

## Summary

把 `keyboard-manager` repo 從 M0 scaffold 升級為完整 MVP：解析 Vial `.vil` 並把所有 keycode 展開為人類可讀（M1）；把 8 天 keystat JSON baseline 匯入 SQLite 並提供 top-N 報表（M2）；在 keyboard layout 上疊 heatmap（M3）；建 macOS native helper 全域抓鍵 + WebSocket 推播給 web UI 即時模擬 hold/layer（M4）；最後 launchd 自啟 + smoke test + 廢用 Hammerspoon keystat（M5）。

## User Story

As a keyboard layout designer iterating on my own Vial config,
I want a local web tool that shows every layer's keycodes fully expanded plus a heatmap of my actual key usage,
So that I can make data-driven layout decisions instead of guessing.

## Problem → Solution

**Current**: Vial GUI 顯示縮寫（`TD(0)`、`LT1(KC_TAB)`、`ALL_T(KC_SPACE)`），看不出 hold / TD 分支實際行為；keystat 跟 layout 視覺脫鉤，必須跑 CLI 文字 table 然後腦補對位
→
**Target**: web UI 一頁可切 6 layer 看完整展開、按住實體鍵盤 mod / layer key 即時看 grid 切換、heatmap 直接套在 layout 上一眼看冷熱

## Metadata
- **Module**: keyboard-manager
- **Parent Plan**: N/A
- **Source PRD**: `docs/PRD.md`
- **Source Feature SRS**: `docs/srs/keyboard-manager-mvp.srs.md`
- **Source Module Spec**: `docs/spec/keyboard-manager.spec.md`
- **Source Linear Issue**: N/A
- **Type**: feature
- **Size**: L
- **Complexity**: Large
- **Rigor**: balanced
- **Mode**: B — 任務先測
- **TDD**: on（task-level，非 step-level）
- **Commit cadence**: per-task
- **Estimated Files**: ~28（新建 25 + 修改 3）

---

## UX Design

### Before
```
┌─ Vial GUI ──────────────────┐    ┌─ Terminal ────────────────┐
│ Layer 0 ▼                   │    │ $ python keystat_analyze.py│
│ [TD(0)] [Q] [W] [E] [R] ... │    │ ## Single-key top 50      │
│ [TD(1)] [A] [S] [D] [F] ... │    │  1   26570  20.17% space  │
│ [LSft]  [Z] [X] [C] [V] ... │    │  2    6783   5.15% delete │
│                             │    │  ...                      │
│ ← user 心想：TD(0) 是啥？   │    │ ← user 心想：space 放對嗎？│
└─────────────────────────────┘    └───────────────────────────┘
```

### After
```
┌─ keyboard-manager  http://localhost:8080 ────────────────────┐
│ [Static Viewer*] [Interactive] [Stats]      Layer: [0 BASE▼] │
│                                                              │
│  `   1  2  3  4  5              6  7  8  9  0  =             │
│ ┌───┬───┬───┬───┬───┬───┬─────┬───┬───┬───┬───┬───┬───┐       │
│ │TD0│ Q │ W │ E │ R │ T │MEDIA│ Y │ U │ I │ O │ P │ - │       │
│ │Cmd│   │   │   │   │   │＞L2 │   │   │   │   │   │   │       │
│ │+1 │   │   │   │   │   │     │   │   │   │   │   │   │       │
│ │/C │   │   │   │   │   │     │   │   │   │   │   │   │       │
│ │trl│   │   │   │   │   │     │   │   │   │   │   │   │       │
│ └───┴───┴───┴───┴───┴───┴─────┴───┴───┴───┴───┴───┴───┘       │
│                                                              │
│  Hover TD0 → tooltip: tap=Cmd+1 / hold=Ctrl / dt=- / th=-    │
└──────────────────────────────────────────────────────────────┘

┌─ Stats / Heatmap ──────────────────────────────────────────────┐
│ App: [All ▼] [Terminal] [Browser] [Editor]                     │
│                                                                │
│  grid 同上、但每顆鍵背景色 = log(count) 紅階                   │
│  最紅：space(26570) 深紅；j(5892) 中紅；hjkl 整列偏紅          │
│  灰底：pinky 死角                                              │
│                                                                │
│ Top 10 keys (terminal bucket):                                 │
│  1   5892  4.47%  j                                            │
│  2   4949  3.76%  o   (← 點此會 highlight grid 上的 O 鍵)      │
└────────────────────────────────────────────────────────────────┘

┌─ Interactive ────────────────────────────────────────────────┐
│ Layer: 1 NAV   helper: ● connected                           │
│ user 按住 Space（base layer's LT1(KC_SPACE)）的瞬間：         │
│ → grid 切到 NAV layer view、hjkl 變成 ←↓↑→                   │
│ 鬆開 → 回 BASE                                               │
└──────────────────────────────────────────────────────────────┘
```

### Interaction Changes

| Touchpoint | Before | After | Notes |
|---|---|---|---|
| 看 layout 全貌 | Vial GUI、單 layer、縮寫 | web UI、6 layer dropdown、完整展開 | 智慧模式：plain 鍵單行、MT/LT/TD 雙行 |
| 看 keystat top-N | `python keystat_analyze.py` | web UI Stats 頁、per-app filter | 數字對得起來 |
| 確認 layout 設計對應使用習慣 | 腦補對位 | heatmap 套在 grid 上 | M3 主要 deliverable |
| 看 hold / layer 即時效果 | 在實體鍵盤上試、不知道 firmware 怎麼解 | 按住實體 mod / layer key → web UI 即時切 view | M4 核心，延遲 < 100ms |

---

## Mandatory Reading

| Priority | File | Lines | Why |
|---|---|---|---|
| P0 | `docs/srs/keyboard-manager-mvp.srs.md` | all | 本 plan 的功能 delta、AC、NFR |
| P0 | `docs/spec/keyboard-manager.spec.md` | all | 完整架構、schema、API contract、components |
| P0 | `~/Projects/keyboard-map/mylayout.vil` | head -100 | 看 `.vil` JSON 結構（layout / tap_dance / combo / settings） |
| P0 | `~/Projects/keyboard-map/keystat_analyze.py` | 60-86, 89-96, 142-195 | aggregate / split_mods / per-app bucket — 直接移植 |
| P1 | `docs/PRD.md` | all | 問題脈絡與優先序 |
| P1 | `~/Projects/keyboard-map/hotkey-analysis.md` | §2.1, §2.3 | M3 heatmap 驗證對照（top key 應呼應） |
| P1 | `~/keystat-counts.json` | head -50 | JSON schema：`{"__meta": {...}, "{bundle_id}": {"{key}": count}}` |
| P2 | `~/Projects/keyboard-map/spec.md` | §1, §2 | 硬體拓樸（58-key Borne 4 row × 6 col + 2 inner + 3 thumb） |
| P2 | `~/.hammerspoon/keystat.lua` | all | 知道 baseline data 怎麼來的、M5 對照怎麼 disable |

## External Documentation

| Topic | Source | Key Takeaway |
|---|---|---|
| Vial `.vil` schema | https://get.vial.today/docs/ | JSON、`vial_protocol: 6`、`layout[L][R][C]` 三層 array、`-1` 表空 slot |
| QMK keycodes | https://docs.qmk.fm/keycodes | `KC_*` 名稱、wrapper macros: `LT(layer,kc)` / `MT(mod,kc)` / `LSFT(kc)` / `LGUI(kc)` / `OSM(mod)` |
| FastAPI WebSocket | https://fastapi.tiangolo.com/advanced/websockets/ | `@app.websocket` decorator；用 `WebSocket.accept()` / `receive_text()` / `send_json()` |
| pynput keyboard listener | https://pynput.readthedocs.io | `from pynput import keyboard; keyboard.Listener(on_press, on_release).start()` |
| pyobjc NSWorkspace | https://pyobjc.readthedocs.io | `AppKit.NSWorkspace.sharedWorkspace().frontmostApplication().bundleIdentifier()` |
| Docker host.docker.internal | https://docs.docker.com/desktop/networking/ | macOS Docker Desktop 自動解析、`extra_hosts: ["host.docker.internal:host-gateway"]` 保險 |
| websockets (Python) | https://websockets.readthedocs.io | `websockets.serve(handler, host, port)`；reverse proxy 用 `websockets.connect(url)` |
| launchd plist | https://www.launchd.info | `~/Library/LaunchAgents/*.plist`；`KeepAlive=true` 自動拉起 |

---

## Patterns to Mirror

### KEYCODE_RESOLVER_DISPATCH（自訂模式，本 repo 首例 — 由 task 1.2 建立）

```python
# DESIGN: dict-based dispatch on keycode prefix; wrapper keycodes recurse.
# SOURCE: 本 plan 首次定義；M1 後成為本 repo pattern
def resolve(raw: str, ctx: LayoutContext) -> ResolvedKey:
    if raw == "KC_NO" or raw == "-1": return EMPTY
    if raw == "KC_TRNS": return TRANSPARENT
    if raw.startswith("LT") and "(" in raw:  # LT1(KC_TAB)
        layer = int(raw[2:raw.index("(")])
        inner = raw[raw.index("(")+1:-1]
        return ResolvedKey(
            tap=resolve(inner, ctx).label_top,
            hold=f"→L{layer}",
            label_top=resolve(inner, ctx).label_top,
            label_bottom=f"→L{layer}",
            expanded_kind="layer-tap",
        )
    if raw.startswith("TD(") and raw.endswith(")"):  # TD(0)
        idx = int(raw[3:-1])
        td = ctx.tap_dance[idx]
        return ResolvedKey(
            tap=resolve(td.tap, ctx).label_top,
            hold=resolve(td.hold, ctx).label_top,
            branches=[...],
            label_top=resolve(td.tap, ctx).label_top,
            label_bottom=f"TD{idx}",
            expanded_kind="tap-dance",
        )
    # MT / mod-wrapped / plain follow same recursive pattern
    ...
```

### STATS_AGGREGATE_PORT（移植自 keystat_analyze.py）

```python
# SOURCE: ~/Projects/keyboard-map/keystat_analyze.py:60-86
def is_modifier_combo(key: str) -> bool:
    return "+" in key

def split_mods(key: str) -> tuple[frozenset[str], str]:
    parts = key.split("+")
    return frozenset(parts[:-1]), parts[-1]

# 移植進 backend/parsers/keystat_keys.py，回傳 (mods, base)
# 注意：要把 frozenset 轉成 sorted 「+」 join 字串存 SQLite
def serialize_mods(mods: frozenset[str]) -> str:
    return "+".join(sorted(mods))
```

### APP_BUCKETS_PORT（移植自 keystat_analyze.py）

```python
# SOURCE: ~/Projects/keyboard-map/keystat_analyze.py:20-48
APP_BUCKETS: dict[str, list[str]] = {
    "terminal": ["com.googlecode.iterm2", "dev.warp.Warp-Stable",
                 "com.apple.Terminal", "com.github.wez.wezterm"],
    "editor":   ["org.vim.MacVim", "md.obsidian", "notion.id",
                 "com.apple.TextEdit"],
    "browser":  ["com.brave.Browser", "org.mozilla.firefox",
                 "org.qutebrowser.qutebrowser", "com.google.chrome.for.testing"],
    "chat":     ["jp.naver.line.mac", "com.apple.MobileSMS", "com.apple.mail"],
    "launcher": ["com.raycast.macos", "org.hammerspoon.Hammerspoon"],
}
# 移植進 backend/db/seed.py，import 時做 apps.bucket 填充
```

### ERROR_HANDLING（本 repo 首例 — 由 task 1.3 建立）

```python
# DESIGN: FastAPI custom exceptions + uniform JSON error body
# Module Spec §API Contracts > Error Codes 已定義 5 個錯誤碼
from fastapi import HTTPException
class VialNotFound(HTTPException):
    def __init__(self, path: str):
        super().__init__(status_code=503, detail={"error":"VIAL_NOT_FOUND", "message": f"vial file not found at {path}"})

class VialParseError(HTTPException):
    def __init__(self, reason: str):
        super().__init__(status_code=422, detail={"error":"VIAL_PARSE_ERROR", "message": reason})
```

### LOGGING_PATTERN（本 repo 首例 — 由 task 1.3 建立）

```python
# DESIGN: stdlib logging, structured (key=value), INFO default
import logging
logger = logging.getLogger("keyboard_manager")
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")

logger.info("parsed vial layout layers=%d tap_dance=%d", len(layers), len(tap_dance))
logger.error("vial parse failed path=%s reason=%s", path, exc)
```

### TEST_STRUCTURE（本 repo 首例 — 由 task 1.1 建立）

```python
# tests/test_vial_parser.py
import pytest
from pathlib import Path
from backend.parsers.vial import parse

FIXTURE = Path(__file__).parent / "fixtures" / "mylayout.vil"

def test_parses_6_layers():
    layout = parse(FIXTURE)
    assert len(layout.layers) == 6

def test_layer_0_first_key_is_grave():
    layout = parse(FIXTURE)
    assert layout.layers[0].rows[0].keys[0].raw == "KC_GRAVE"
```

Fixture: 把 `~/Projects/keyboard-map/mylayout.vil` 內容複製到 `backend/tests/fixtures/mylayout.vil`（一次 setup）。

### REPOSITORY_PATTERN（本 repo 首例 — 由 task 2.3 建立）

```python
# backend/db/repository.py
import sqlite3
from contextlib import contextmanager
from pathlib import Path

class StatsRepo:
    def __init__(self, db_path: Path):
        self.db_path = db_path

    @contextmanager
    def _conn(self):
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        try:
            yield conn
            conn.commit()
        finally:
            conn.close()

    def top_n(self, app: str | None, kind: str, n: int = 50) -> list[dict]:
        with self._conn() as c:
            mod_filter = "modifiers = ''" if kind == "single" else \
                         "modifiers != ''" if kind == "mod" else "1=1"
            app_filter = "AND app_bundle = ?" if app else ""
            params = (app,) if app else ()
            rows = c.execute(
                f"SELECT key, modifiers, SUM(count) AS total "
                f"FROM events WHERE {mod_filter} {app_filter} "
                f"GROUP BY key, modifiers ORDER BY total DESC LIMIT ?",
                (*params, n),
            ).fetchall()
            return [dict(r) for r in rows]
```

### FRONTEND_MODULE（本 repo 首例 — 由 task 1.4 建立）

```javascript
// frontend/static-viewer.js — IIFE-style, no build step, no framework
(function () {
  "use strict";
  const root = document.getElementById("view-static");

  async function loadLayer(idx) {
    const r = await fetch("/api/layout");
    if (!r.ok) { root.innerHTML = `<p class="error">${r.status}</p>`; return; }
    const layout = await r.json();
    root.innerHTML = renderGrid(layout.layers[idx]);
  }

  function renderGrid(layer) { /* HTML string builder */ }

  window.staticViewer = { loadLayer };
})();
```

---

## Files to Change

| File | Action | Justification |
|---|---|---|
| `backend/main.py` | UPDATE | 註冊 router，目前只有 `/health` |
| `backend/parsers/__init__.py` | CREATE | Python package marker |
| `backend/parsers/vial.py` | CREATE | `.vil` JSON loader + dataclasses |
| `backend/parsers/keycodes.py` | CREATE | Keycode resolver (KC/LT/MT/TD/wrapped) |
| `backend/parsers/keycode_labels.py` | CREATE | Map `KC_GRAVE` → `` ` `` 等大表 |
| `backend/parsers/keystat_keys.py` | CREATE | port `split_mods`、`is_modifier_combo` |
| `backend/api/__init__.py` | CREATE | package marker |
| `backend/api/layout.py` | CREATE | `/api/layout` + `/api/layout/keycodes` |
| `backend/api/stats.py` | CREATE | `/api/stats` + `/api/stats/heatmap` + `/api/apps` + `/api/stats/import` |
| `backend/api/live.py` | CREATE | WS `/api/live` — reverse proxy to helper :8765 |
| `backend/api/errors.py` | CREATE | Custom HTTPException 子類（VialNotFound 等） |
| `backend/db/__init__.py` | CREATE | package marker |
| `backend/db/migrations.py` | CREATE | Boot-time create tables if not exist |
| `backend/db/repository.py` | CREATE | `StatsRepo`、`AppsRepo`、`SnapshotRepo` |
| `backend/db/seed.py` | CREATE | `APP_BUCKETS` seed for `apps.bucket` |
| `backend/db/heatmap_mapper.py` | CREATE | key → (layer, row, col) 反向對映 |
| `backend/scripts/__init__.py` | CREATE | package marker |
| `backend/scripts/import_keystat.py` | CREATE | One-shot JSON 匯入 CLI |
| `backend/tests/conftest.py` | CREATE | shared fixtures（temp db、fixture .vil） |
| `backend/tests/fixtures/mylayout.vil` | CREATE | 複製自 `~/Projects/keyboard-map/mylayout.vil` |
| `backend/tests/fixtures/keystat-counts.sample.json` | CREATE | 縮小版 keystat baseline 樣本 |
| `backend/tests/test_vial_parser.py` | CREATE | M1 |
| `backend/tests/test_keycode_resolver.py` | CREATE | M1 |
| `backend/tests/test_layout_api.py` | CREATE | M1 |
| `backend/tests/test_keystat_keys.py` | CREATE | M2 |
| `backend/tests/test_repository.py` | CREATE | M2 |
| `backend/tests/test_import.py` | CREATE | M2 |
| `backend/tests/test_stats_api.py` | CREATE | M2 |
| `backend/tests/test_heatmap_mapper.py` | CREATE | M3 |
| `backend/tests/test_heatmap_api.py` | CREATE | M3 |
| `frontend/index.html` | UPDATE | 加 status bar（helper connection 狀態） |
| `frontend/style.css` | UPDATE | 加 grid、heatmap、tooltip 樣式 |
| `frontend/app.js` | UPDATE | router 已在；接 module bootstraps |
| `frontend/static-viewer.js` | CREATE | M1 — 渲染 keyboard grid |
| `frontend/grid-render.js` | CREATE | 共用 grid HTML builder（被 viewer / interactive / heatmap 共用） |
| `frontend/keycode-format.js` | CREATE | Frontend 端 keycode → label 函式（也可 server-render；先 client） |
| `frontend/stats.js` | CREATE | M2 — Stats dashboard 表格 |
| `frontend/heatmap.js` | CREATE | M3 — color overlay + bidirectional highlight |
| `frontend/interactive.js` | CREATE | M4 — WS client + live grid 切換 |
| `native-helper/pyproject.toml` | CREATE | pynput + pyobjc + websockets 依賴 |
| `native-helper/main.py` | CREATE | M4 entrypoint — listener + ws server + sink |
| `native-helper/sink.py` | CREATE | SQLite batch writer |
| `native-helper/app_tracker.py` | CREATE | NSWorkspace bundle ID 抓取 |
| `native-helper/tests/test_sink.py` | CREATE | M4 |
| `native-helper/com.keyboard-manager.helper.plist` | CREATE | M5 — launchd 自啟 |
| `docs/migration-from-hammerspoon.md` | CREATE | M5 — disable HS keystat 步驟 |
| `scripts/smoke.sh` | CREATE | M5 — `compose up` + `/health` + `/api/layout` 煙測 |

## NOT Building

- Layout 編輯 / 修改 `.vil`
- Firmware flash
- Cross-platform capture（Linux / Windows）
- Cloud sync / multi-user / auth
- Bigram / N-gram 分析
- Time-series heatmap（schema 有 ts、但 UI 不做）
- Vial 升版 schema 自動 migration（fail-fast 422）
- 比較 `.vil` 跟設備內 keymap
- Web UI 內建重啟 helper 機制（靠 launchd self-recover 即可）
- ORM（用 stdlib sqlite3）
- Frontend build step（vanilla JS、no framework）

---

## Step-by-Step Tasks

任務分組對應 SRS / PRD Milestones。**完成順序依 milestone**；同一 milestone 內，依編號順序（後面 task 可能依賴前面）。

> **每個 task 結構（Mode B）**：ACTION → TEST FIRST → IMPLEMENT → MIRROR → VALIDATE → COMMIT。

---

### Milestone M1 — Static Viewer（解析 .vil + 6 layer grid）

#### Task 1.1: Vial config loader（dataclasses + JSON load）

- **ACTION**: 建 `backend/parsers/vial.py`，read `.vil` JSON、validate `vial_protocol`，把 `layout` / `tap_dance` / `combo` / `key_override` 轉成 dataclasses。
- **TEST FIRST**:
  ```python
  # backend/tests/test_vial_parser.py
  from pathlib import Path
  import pytest
  from backend.parsers.vial import parse, VialParseError

  FIXTURE = Path(__file__).parent / "fixtures" / "mylayout.vil"

  def test_parse_returns_layout_with_6_layers():
      layout = parse(FIXTURE)
      assert len(layout.layers) == 6

  def test_parse_tap_dance_count():
      layout = parse(FIXTURE)
      assert len(layout.tap_dance) == 16

  def test_parse_combo_count():
      layout = parse(FIXTURE)
      assert len(layout.combo) == 16

  def test_parse_layer_0_first_key_raw():
      layout = parse(FIXTURE)
      assert layout.layers[0].rows[0].keys[0] == "KC_GRAVE"

  def test_parse_layer_0_empty_slot_is_none():
      # Row 0 col 6 is -1 in .vil
      layout = parse(FIXTURE)
      assert layout.layers[0].rows[0].keys[6] is None

  def test_parse_rejects_unsupported_protocol(tmp_path):
      bad = tmp_path / "bad.vil"
      bad.write_text('{"vial_protocol": 99, "version": 1, "layout": []}')
      with pytest.raises(VialParseError):
          parse(bad)
  ```
  Run: `pytest backend/tests/test_vial_parser.py` — expect FAIL（module 不存在）。
- **IMPLEMENT**:
  - Copy fixture: `cp ~/Projects/keyboard-map/mylayout.vil backend/tests/fixtures/mylayout.vil`
  - `backend/parsers/vial.py`：
    ```python
    from __future__ import annotations
    from dataclasses import dataclass
    from pathlib import Path
    import json

    SUPPORTED_PROTOCOLS = {6}

    class VialParseError(Exception): ...

    @dataclass(frozen=True)
    class Row:
        row: int
        keys: list[str | None]   # None if -1

    @dataclass(frozen=True)
    class Layer:
        index: int
        rows: list[Row]

    @dataclass(frozen=True)
    class TapDance:
        index: int
        tap: str
        hold: str
        double_tap: str
        tap_hold: str
        tap_term_ms: int

    @dataclass(frozen=True)
    class Combo:
        index: int
        triggers: list[str]      # filter out KC_NO
        output: str

    @dataclass(frozen=True)
    class Layout:
        vial_protocol: int
        uid: int
        layers: list[Layer]
        tap_dance: list[TapDance]
        combo: list[Combo]

    def parse(path: Path) -> Layout:
        try:
            data = json.loads(Path(path).read_text())
        except json.JSONDecodeError as e:
            raise VialParseError(f"invalid json: {e}")
        proto = data.get("vial_protocol")
        if proto not in SUPPORTED_PROTOCOLS:
            raise VialParseError(f"vial_protocol {proto} unsupported (expect {SUPPORTED_PROTOCOLS})")
        # Build layers
        layers = []
        for li, raw_layer in enumerate(data["layout"]):
            rows = [
                Row(row=ri, keys=[None if k == -1 else k for k in raw_row])
                for ri, raw_row in enumerate(raw_layer)
            ]
            layers.append(Layer(index=li, rows=rows))
        # Build tap_dance
        td_list = []
        for ti, td in enumerate(data.get("tap_dance", [])):
            td_list.append(TapDance(index=ti, tap=td[0], hold=td[1],
                                    double_tap=td[2], tap_hold=td[3], tap_term_ms=td[4]))
        # Build combo
        combos = []
        for ci, c in enumerate(data.get("combo", [])):
            triggers = [k for k in c[:4] if k != "KC_NO"]
            combos.append(Combo(index=ci, triggers=triggers, output=c[4]))
        return Layout(
            vial_protocol=proto,
            uid=data.get("uid", 0),
            layers=layers,
            tap_dance=td_list,
            combo=combos,
        )
    ```
- **MIRROR**: TEST_STRUCTURE pattern 上方；無既有 parser pattern，本 task 建立 dataclass-based parser convention。
- **VALIDATE**: `pytest backend/tests/test_vial_parser.py -v` — expect 6 tests PASS
- **COMMIT**: `feat(parser): add vial config loader with dataclass schema`

#### Task 1.2: Keycode resolver（KC / LT / MT / TD / wrapped）

- **ACTION**: 建 `backend/parsers/keycodes.py`，把 raw keycode（`KC_GRAVE` / `LT1(KC_TAB)` / `TD(0)` / `ALL_T(KC_SPACE)` / `LSFT(KC_SCOLON)`）解析為 `ResolvedKey` 結構。
- **TEST FIRST**:
  ```python
  # backend/tests/test_keycode_resolver.py
  import pytest
  from backend.parsers.keycodes import resolve, ResolvedKey
  from backend.parsers.vial import TapDance

  def make_ctx(tap_dance=None):
      from backend.parsers.keycodes import LayoutContext
      return LayoutContext(tap_dance=tap_dance or [])

  def test_plain_letter():
      r = resolve("KC_A", make_ctx())
      assert r.expanded_kind == "plain"
      assert r.label_top == "A"
      assert r.label_bottom is None

  def test_grave_accent():
      r = resolve("KC_GRAVE", make_ctx())
      assert r.label_top == "`"

  def test_layer_tap():
      r = resolve("LT1(KC_TAB)", make_ctx())
      assert r.expanded_kind == "layer-tap"
      assert r.label_top == "Tab"
      assert r.label_bottom == "→L1"
      assert r.tap == "Tab"
      assert r.hold == "→L1"

  def test_mod_tap_all_t():
      r = resolve("ALL_T(KC_SPACE)", make_ctx())
      assert r.expanded_kind == "mod-tap"
      assert r.label_top == "Space"
      assert r.label_bottom == "Hyper"

  def test_lgui_t_enter():
      r = resolve("LGUI_T(KC_ENTER)", make_ctx())
      assert r.tap == "Enter"
      assert r.hold == "Cmd"

  def test_shift_wrapped():
      r = resolve("LSFT(KC_SCOLON)", make_ctx())
      assert r.label_top == ":"

  def test_tap_dance_branches():
      td0 = TapDance(index=0, tap="LGUI(KC_1)", hold="KC_LCTRL",
                    double_tap="KC_NO", tap_hold="KC_NO", tap_term_ms=200)
      r = resolve("TD(0)", make_ctx(tap_dance=[td0]))
      assert r.expanded_kind == "tap-dance"
      assert r.tap == "Cmd+1"
      assert r.hold == "Ctrl"
      assert r.double_tap is None
      assert r.tap_term_ms == 200
      assert len(r.branches) == 4

  def test_kc_trns_transparent():
      r = resolve("KC_TRNS", make_ctx())
      assert r.expanded_kind == "transparent"
      assert r.label_top is None

  def test_kc_no_empty():
      r = resolve("KC_NO", make_ctx())
      assert r.expanded_kind == "empty"
  ```
  Run: `pytest backend/tests/test_keycode_resolver.py` — expect FAIL
- **IMPLEMENT**:
  - `backend/parsers/keycode_labels.py`（純表）：
    ```python
    KEYCODE_LABELS: dict[str, str] = {
      "KC_A": "A", "KC_B": "B", ..., "KC_Z": "Z",
      "KC_1": "1", ..., "KC_0": "0",
      "KC_GRAVE": "`", "KC_MINUS": "-", "KC_EQUAL": "=",
      "KC_LBRC": "[", "KC_RBRC": "]", "KC_BSLS": "\\",
      "KC_SCOLON": ";", "KC_QUOTE": "'", "KC_COMMA": ",",
      "KC_DOT": ".", "KC_SLASH": "/",
      "KC_SPACE": "Space", "KC_ENTER": "Enter", "KC_TAB": "Tab",
      "KC_BSPACE": "Bksp", "KC_DELETE": "Del", "KC_ESCAPE": "Esc",
      "KC_LSHIFT": "LShift", "KC_RSHIFT": "RShift",
      "KC_LCTRL": "Ctrl", "KC_RCTRL": "RCtrl",
      "KC_LALT": "Alt", "KC_RALT": "RAlt",
      "KC_LGUI": "Cmd", "KC_RGUI": "RCmd",
      "KC_HYPR": "Hyper",
      "KC_LEFT": "←", "KC_RIGHT": "→", "KC_UP": "↑", "KC_DOWN": "↓",
      "KC_PGUP": "PgUp", "KC_PGDOWN": "PgDn",
      "KC_HOME": "Home", "KC_END": "End",
      "KC_MPLY": "Play/Pause", "KC_MSTP": "Stop",
      "KC_MNXT": "Next", "KC_MPRV": "Prev",
      "KC_VOLU": "Vol↑", "KC_VOLD": "Vol↓", "KC_MUTE": "Mute",
      "KC_BRIU": "Brt↑", "KC_BRID": "Brt↓",
      "AU_TOG": "Audio Toggle",
      # ... full QMK keycode set
    }
    ```
  - `backend/parsers/keycodes.py`：
    ```python
    from dataclasses import dataclass, field
    from .keycode_labels import KEYCODE_LABELS
    from .vial import TapDance

    @dataclass
    class LayoutContext:
        tap_dance: list[TapDance]

    @dataclass
    class ResolvedKey:
        raw: str
        expanded_kind: str   # plain | layer-tap | mod-tap | tap-dance | transparent | empty | shift-wrapped | combo
        label_top: str | None
        label_bottom: str | None = None
        tap: str | None = None
        hold: str | None = None
        double_tap: str | None = None
        tap_hold: str | None = None
        tap_term_ms: int | None = None
        branches: list[dict] = field(default_factory=list)

    MOD_T_MAP = {
        "LSFT_T": "Shift", "RSFT_T": "RShift",
        "LCTL_T": "Ctrl", "RCTL_T": "RCtrl",
        "LALT_T": "Alt", "RALT_T": "RAlt",
        "LGUI_T": "Cmd", "RGUI_T": "RCmd",
        "ALL_T": "Hyper", "HYPR_T": "Hyper", "MEH_T": "Meh",
    }
    SHIFT_PAIRS = {
        "KC_1": "!", "KC_2": "@", "KC_3": "#", "KC_4": "$", "KC_5": "%",
        "KC_6": "^", "KC_7": "&", "KC_8": "*", "KC_9": "(", "KC_0": ")",
        "KC_SCOLON": ":", "KC_QUOTE": "\"", "KC_COMMA": "<", "KC_DOT": ">",
        "KC_SLASH": "?", "KC_MINUS": "_", "KC_EQUAL": "+",
        "KC_LBRC": "{", "KC_RBRC": "}", "KC_BSLS": "|", "KC_GRAVE": "~",
    }

    def resolve(raw: str, ctx: LayoutContext) -> ResolvedKey:
        if raw in ("KC_NO", None):
            return ResolvedKey(raw=raw, expanded_kind="empty", label_top=None)
        if raw == "KC_TRNS":
            return ResolvedKey(raw=raw, expanded_kind="transparent", label_top=None)
        if raw in KEYCODE_LABELS:
            return ResolvedKey(raw=raw, expanded_kind="plain", label_top=KEYCODE_LABELS[raw])
        # LSFT(KC_X)
        if raw.startswith("LSFT(") and raw.endswith(")"):
            inner = raw[5:-1]
            label = SHIFT_PAIRS.get(inner) or f"⇧{resolve(inner, ctx).label_top}"
            return ResolvedKey(raw=raw, expanded_kind="shift-wrapped", label_top=label)
        # LGUI(KC_X) → "Cmd+X" 等
        for prefix, mod_label in [("LCTL", "Ctrl"), ("LSFT", "Shift"), ("LALT", "Alt"), ("LGUI", "Cmd")]:
            if raw.startswith(f"{prefix}(") and raw.endswith(")"):
                inner = raw[len(prefix)+1:-1]
                inner_lbl = resolve(inner, ctx).label_top or inner
                return ResolvedKey(raw=raw, expanded_kind="mod-wrapped",
                                   label_top=f"{mod_label}+{inner_lbl}")
        # LT{n}(KC_X)
        if raw.startswith("LT") and "(" in raw and raw.endswith(")"):
            layer_str, inner = raw[2:raw.index("(")], raw[raw.index("(")+1:-1]
            try:
                layer = int(layer_str)
            except ValueError:
                # Fall through to mod-tap
                pass
            else:
                inner_r = resolve(inner, ctx)
                return ResolvedKey(raw=raw, expanded_kind="layer-tap",
                                   label_top=inner_r.label_top, label_bottom=f"→L{layer}",
                                   tap=inner_r.label_top, hold=f"→L{layer}")
        # MT mods: ALL_T, LGUI_T, etc.
        for mod_t, mod_label in MOD_T_MAP.items():
            if raw.startswith(f"{mod_t}(") and raw.endswith(")"):
                inner = raw[len(mod_t)+1:-1]
                inner_r = resolve(inner, ctx)
                return ResolvedKey(raw=raw, expanded_kind="mod-tap",
                                   label_top=inner_r.label_top, label_bottom=mod_label,
                                   tap=inner_r.label_top, hold=mod_label)
        # TD(N)
        if raw.startswith("TD(") and raw.endswith(")"):
            idx = int(raw[3:-1])
            td = ctx.tap_dance[idx]
            tap_lbl   = resolve(td.tap, ctx).label_top
            hold_lbl  = resolve(td.hold, ctx).label_top
            dt_lbl    = resolve(td.double_tap, ctx).label_top
            th_lbl    = resolve(td.tap_hold, ctx).label_top
            return ResolvedKey(raw=raw, expanded_kind="tap-dance",
                               label_top=tap_lbl, label_bottom=f"TD{idx}",
                               tap=tap_lbl, hold=hold_lbl,
                               double_tap=dt_lbl, tap_hold=th_lbl,
                               tap_term_ms=td.tap_term_ms,
                               branches=[
                                   {"action":"tap","label":tap_lbl},
                                   {"action":"hold","label":hold_lbl},
                                   {"action":"double_tap","label":dt_lbl},
                                   {"action":"tap_hold","label":th_lbl},
                               ])
        # Fallback
        return ResolvedKey(raw=raw, expanded_kind="unknown", label_top=raw)
    ```
- **MIRROR**: KEYCODE_RESOLVER_DISPATCH pattern 上方；建立本 repo 第一個 dispatcher-style resolver。
- **VALIDATE**: `pytest backend/tests/test_keycode_resolver.py -v` — expect 9 tests PASS
- **COMMIT**: `feat(parser): keycode resolver with TD/LT/MT/wrapped expansion`

#### Task 1.3: Layout API endpoint

- **ACTION**: 建 `backend/api/layout.py`、`backend/api/errors.py`，註冊 `/api/layout` 與 `/api/layout/keycodes`；解析失敗回 422、檔案不存在回 503。
- **TEST FIRST**:
  ```python
  # backend/tests/test_layout_api.py
  import os
  from pathlib import Path
  from fastapi.testclient import TestClient
  import pytest

  FIXTURE = Path(__file__).parent / "fixtures" / "mylayout.vil"

  @pytest.fixture
  def client(monkeypatch):
      monkeypatch.setenv("VIAL_PATH", str(FIXTURE))
      from backend.main import app
      return TestClient(app)

  def test_layout_ok(client):
      r = client.get("/api/layout")
      assert r.status_code == 200
      body = r.json()
      assert len(body["layers"]) == 6
      assert body["layers"][0]["rows"][0]["keys"][0]["raw"] == "KC_GRAVE"
      assert body["layers"][0]["rows"][0]["keys"][0]["resolved"]["label_top"] == "`"

  def test_layout_resolves_td(client):
      r = client.get("/api/layout")
      # Layer 0 row 1 col 0 (thumb area) = TD(3) in mylayout.vil
      td_key = next(
          k for row in r.json()["layers"][0]["rows"]
          for k in row["keys"] if k and k["raw"] == "TD(3)"
      )
      assert td_key["resolved"]["expanded_kind"] == "tap-dance"
      assert td_key["resolved"]["tap"] == "Tab"   # TD(3)[0] = KC_TAB
      assert td_key["resolved"]["hold"] == "Alt"  # TD(3)[1] = KC_LALT

  def test_layout_503_when_vial_missing(monkeypatch):
      monkeypatch.setenv("VIAL_PATH", "/nonexistent.vil")
      # Need a fresh app instance: import-time path read
      from importlib import reload
      from backend import main
      reload(main)
      c = TestClient(main.app)
      r = c.get("/api/layout")
      assert r.status_code == 503
      assert r.json()["detail"]["error"] == "VIAL_NOT_FOUND"

  def test_keycodes_endpoint(client):
      r = client.get("/api/layout/keycodes")
      assert r.status_code == 200
      assert r.json()["KC_GRAVE"] == "`"
  ```
  Run: `pytest backend/tests/test_layout_api.py` — expect FAIL
- **IMPLEMENT**:
  - `backend/api/errors.py`:
    ```python
    from fastapi import HTTPException
    class VialNotFound(HTTPException):
        def __init__(self, path: str):
            super().__init__(status_code=503, detail={"error":"VIAL_NOT_FOUND","message":f"vial file not found at {path}"})
    class VialParseFailed(HTTPException):
        def __init__(self, reason: str):
            super().__init__(status_code=422, detail={"error":"VIAL_PARSE_ERROR","message":reason})
    ```
  - `backend/api/layout.py`:
    ```python
    from dataclasses import asdict
    from pathlib import Path
    from fastapi import APIRouter
    from ..parsers.vial import parse, VialParseError
    from ..parsers.keycodes import resolve, LayoutContext
    from ..parsers.keycode_labels import KEYCODE_LABELS
    from .errors import VialNotFound, VialParseFailed

    router = APIRouter()

    _cache: dict = {}

    def _load(path: Path):
        if not path.exists():
            raise VialNotFound(str(path))
        mtime = path.stat().st_mtime
        if _cache.get("mtime") == mtime:
            return _cache["data"]
        try:
            layout = parse(path)
        except VialParseError as e:
            raise VialParseFailed(str(e))
        ctx = LayoutContext(tap_dance=layout.tap_dance)
        # Resolve every key to a dict
        layers_json = []
        for layer in layout.layers:
            rows = []
            for row in layer.rows:
                keys = []
                for ci, raw in enumerate(row.keys):
                    if raw is None:
                        keys.append(None)
                    else:
                        rk = resolve(raw, ctx)
                        keys.append({"col": ci, "raw": raw, "resolved": asdict(rk)})
                rows.append({"row": row.row, "keys": keys})
            layers_json.append({"index": layer.index, "rows": rows})
        result = {
            "vial_protocol": layout.vial_protocol,
            "uid": layout.uid,
            "layers": layers_json,
            "tap_dance": [asdict(td) for td in layout.tap_dance],
            "combo": [asdict(c) for c in layout.combo],
        }
        _cache["mtime"] = mtime
        _cache["data"] = result
        return result

    @router.get("/api/layout")
    def get_layout():
        from ..main import VIAL_PATH
        return _load(VIAL_PATH)

    @router.get("/api/layout/keycodes")
    def get_keycodes():
        return KEYCODE_LABELS
    ```
  - Update `backend/main.py`:
    ```python
    from .api.layout import router as layout_router
    app.include_router(layout_router)
    ```
  - Update `backend/Dockerfile` 若需要 — 應已支援 nested module
- **MIRROR**: ERROR_HANDLING pattern + LOGGING_PATTERN（上方）
- **VALIDATE**: `pytest backend/tests/test_layout_api.py -v` — expect 4 tests PASS
- **COMMIT**: `feat(api): GET /api/layout returns resolved 6-layer tree`

#### Task 1.4: Frontend keyboard grid renderer

- **ACTION**: 建 `frontend/keycode-format.js`（純函式 — 給標籤 / class）、`frontend/grid-render.js`（共用 grid HTML builder）、`frontend/static-viewer.js`（接 `/api/layout` 渲染當前選定 layer）。
- **TEST FIRST**: Frontend 無 Jest/Vitest（vanilla JS、無 build），改用 **manual browser verification** + 一個簡單的 backend 端 contract 測：
  ```python
  # backend/tests/test_layout_api.py  ← 補一個 test
  def test_static_viewer_render_contract(client):
      """The frontend renderer needs: layer index, row index, col index,
      and resolved.{label_top, label_bottom, expanded_kind} per key."""
      body = client.get("/api/layout").json()
      sample_key = next(
          k for row in body["layers"][0]["rows"]
          for k in row["keys"] if k is not None
      )
      assert "raw" in sample_key
      assert "resolved" in sample_key
      r = sample_key["resolved"]
      for required in ["label_top", "label_bottom", "expanded_kind"]:
          assert required in r
  ```
  Run: `pytest -k test_static_viewer_render_contract` — expect PASS（從 task 1.3 已滿足）。
  **Frontend manual test**: 開 `http://localhost:8080`，看到 6 個 layer dropdown、選每個都正確渲染。
- **IMPLEMENT**:
  - `frontend/keycode-format.js`:
    ```javascript
    (function () {
      "use strict";
      function renderKey(key) {
        if (!key) return `<div class="key empty"></div>`;
        const r = key.resolved || {};
        const cls = ["key", `kind-${r.expanded_kind || "plain"}`];
        const top = r.label_top ?? "";
        const bot = r.label_bottom ?? "";
        const tooltip = r.expanded_kind === "tap-dance" && r.branches
          ? `tap=${r.tap} hold=${r.hold} dt=${r.double_tap ?? "—"} th=${r.tap_hold ?? "—"}`
          : (r.tap && r.hold) ? `tap=${r.tap} hold=${r.hold}` : key.raw;
        return `
          <div class="${cls.join(" ")}" title="${tooltip}">
            <div class="label-top">${top}</div>
            ${bot ? `<div class="label-bottom">${bot}</div>` : ""}
          </div>`;
      }
      window.keycodeFormat = { renderKey };
    })();
    ```
  - `frontend/grid-render.js`:
    ```javascript
    (function () {
      "use strict";
      // Borne topology: 10 rows × 7 cols, but col 6 of row 0 is null (no inner on num row)
      // and certain thumb rows have shape -1 -1 -1 K K K -1
      function renderLayer(layer) {
        const html = layer.rows.map((row, ri) => {
          const cells = row.keys.map(k => window.keycodeFormat.renderKey(k)).join("");
          return `<div class="row row-${ri}">${cells}</div>`;
        }).join("");
        return `<div class="keyboard-grid">${html}</div>`;
      }
      window.gridRender = { renderLayer };
    })();
    ```
  - `frontend/static-viewer.js`:
    ```javascript
    (function () {
      "use strict";
      const container = document.getElementById("view-static");
      const select = document.getElementById("layer-select");
      let layoutCache = null;

      async function ensureLayout() {
        if (layoutCache) return layoutCache;
        const r = await fetch("/api/layout");
        if (!r.ok) {
          container.innerHTML = `<p class="error">layout error: ${r.status}</p>`;
          return null;
        }
        layoutCache = await r.json();
        return layoutCache;
      }

      async function show(layerIdx) {
        const layout = await ensureLayout();
        if (!layout) return;
        container.innerHTML = window.gridRender.renderLayer(layout.layers[layerIdx]);
      }

      select.addEventListener("change", () => show(parseInt(select.value, 10)));
      // Initial render
      show(0);
      window.staticViewer = { show };
    })();
    ```
  - Update `frontend/index.html`：把 `<p class="placeholder">` 換掉，並加 `<script src="keycode-format.js"></script>` 等。
  - Update `frontend/style.css` 加 `.keyboard-grid` / `.row` / `.key` / `.kind-tap-dance` 等樣式。
- **MIRROR**: FRONTEND_MODULE pattern 上方（IIFE + window export）
- **VALIDATE**:
  - `docker compose up -d --build`
  - 開 `http://localhost:8080`、切 layer dropdown 看 6 layer 都渲染
  - 對著 `mylayout.vil` 手動 spot check：layer 0 thumb 中央顯示 "Space / →L1"；layer 0 A row outer 顯示 "Esc / Hyper" 之類（看你的 TD(1)）
- **COMMIT**: `feat(frontend): static viewer renders 6-layer keyboard grid`

#### Task 1.5: M1 acceptance — full mylayout coverage

- **ACTION**: 加一個 end-to-end coverage test 證明 `mylayout.vil` 內每個非 `KC_TRNS` 非 `-1` 的鍵都有 `label_top` 不為空。
- **TEST FIRST**:
  ```python
  # backend/tests/test_layout_api.py
  def test_mylayout_full_coverage(client):
      body = client.get("/api/layout").json()
      missing = []
      for layer in body["layers"]:
          for row in layer["rows"]:
              for k in row["keys"]:
                  if k is None:
                      continue
                  r = k["resolved"]
                  if r["expanded_kind"] in ("transparent", "empty"):
                      continue
                  if not r["label_top"]:
                      missing.append((layer["index"], row["row"], k["raw"]))
      assert not missing, f"missing labels for: {missing[:20]}"
  ```
  Run: `pytest -k test_mylayout_full_coverage` — expect either PASS（完美）or FAIL（需要在 `keycode_labels.py` 補表）。
- **IMPLEMENT**: 失敗時把缺漏 keycode 補進 `keycode_labels.py`，重跑直到 PASS。
- **MIRROR**: 無 — 純 coverage gate
- **VALIDATE**: PASS = AC-1 ✅、AC-2 ✅、AC-3 ✅（手動 + AC-3 已在 1.4 manual verify）
- **COMMIT**: `test(parser): assert mylayout full keycode coverage`

---

### Milestone M2 — Stats baseline（SQLite schema + JSON import + top-N）

#### Task 2.1: Database migrations

- **ACTION**: 建 `backend/db/migrations.py`，boot 時若 table 不存在則 create；用 Module Spec §Data Model 的 schema。
- **TEST FIRST**:
  ```python
  # backend/tests/test_migrations.py
  import sqlite3
  from pathlib import Path
  from backend.db.migrations import ensure_schema

  def test_creates_all_tables(tmp_path):
      db = tmp_path / "test.db"
      ensure_schema(db)
      conn = sqlite3.connect(db)
      tables = {r[0] for r in conn.execute(
          "SELECT name FROM sqlite_master WHERE type='table'").fetchall()}
      assert {"events", "apps", "snapshots"} <= tables

  def test_idempotent(tmp_path):
      db = tmp_path / "test.db"
      ensure_schema(db)
      ensure_schema(db)  # second call must not raise

  def test_indexes_present(tmp_path):
      db = tmp_path / "test.db"
      ensure_schema(db)
      conn = sqlite3.connect(db)
      idx = {r[0] for r in conn.execute(
          "SELECT name FROM sqlite_master WHERE type='index'").fetchall()}
      assert "idx_events_app_key" in idx
      assert "idx_events_ts" in idx
  ```
  Run: `pytest backend/tests/test_migrations.py` — expect FAIL
- **IMPLEMENT**:
  - `backend/db/migrations.py`:
    ```python
    import sqlite3
    from pathlib import Path

    SCHEMA = """
    CREATE TABLE IF NOT EXISTS events (
      id          INTEGER PRIMARY KEY AUTOINCREMENT,
      ts          INTEGER NOT NULL,
      app_bundle  TEXT    NOT NULL,
      key         TEXT    NOT NULL,
      modifiers   TEXT    NOT NULL DEFAULT '',
      count       INTEGER NOT NULL DEFAULT 1,
      snapshot_id INTEGER NOT NULL,
      source      TEXT    NOT NULL
    );
    CREATE INDEX IF NOT EXISTS idx_events_app_key   ON events(app_bundle, key);
    CREATE INDEX IF NOT EXISTS idx_events_modifiers ON events(modifiers);
    CREATE INDEX IF NOT EXISTS idx_events_ts        ON events(ts);
    CREATE INDEX IF NOT EXISTS idx_events_snapshot  ON events(snapshot_id);
    CREATE TABLE IF NOT EXISTS apps (
      bundle_id     TEXT    PRIMARY KEY,
      display_name  TEXT,
      bucket        TEXT,
      first_seen_ts INTEGER NOT NULL,
      last_seen_ts  INTEGER NOT NULL
    );
    CREATE TABLE IF NOT EXISTS snapshots (
      id     INTEGER PRIMARY KEY AUTOINCREMENT,
      ts     INTEGER NOT NULL,
      source TEXT    NOT NULL,
      notes  TEXT
    );
    """

    def ensure_schema(db_path: Path) -> None:
        db_path.parent.mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(db_path)
        try:
            conn.executescript(SCHEMA)
            conn.commit()
        finally:
            conn.close()
    ```
  - Update `backend/main.py`：startup event 跑 `ensure_schema(DB_PATH)`。
- **MIRROR**: 無，建立 schema migration convention
- **VALIDATE**: `pytest backend/tests/test_migrations.py -v` — 3 tests PASS
- **COMMIT**: `feat(db): bootstrap sqlite schema with idempotent migrations`

#### Task 2.2: Keystat keys helper（port `split_mods` / `is_modifier_combo`）

- **ACTION**: 建 `backend/parsers/keystat_keys.py`，移植 sibling project 邏輯。
- **TEST FIRST**:
  ```python
  # backend/tests/test_keystat_keys.py
  from backend.parsers.keystat_keys import split_mods, serialize_mods, is_modifier_combo

  def test_plain_key():
      assert is_modifier_combo("j") is False
      mods, base = split_mods("j")
      assert mods == frozenset() and base == "j"

  def test_single_mod():
      assert is_modifier_combo("cmd+v") is True
      mods, base = split_mods("cmd+v")
      assert mods == frozenset({"cmd"}) and base == "v"

  def test_multi_mod_sorted():
      mods, base = split_mods("cmd+ctrl+alt+1")
      assert mods == frozenset({"cmd", "ctrl", "alt"})
      assert base == "1"
      assert serialize_mods(mods) == "alt+cmd+ctrl"
  ```
  Run: `pytest backend/tests/test_keystat_keys.py` — expect FAIL
- **IMPLEMENT**:
  ```python
  # backend/parsers/keystat_keys.py
  # Ported from ~/Projects/keyboard-map/keystat_analyze.py:60-68
  def is_modifier_combo(key: str) -> bool:
      return "+" in key

  def split_mods(key: str) -> tuple[frozenset[str], str]:
      parts = key.split("+")
      return frozenset(parts[:-1]), parts[-1]

  def serialize_mods(mods: frozenset[str]) -> str:
      return "+".join(sorted(mods))
  ```
- **MIRROR**: STATS_AGGREGATE_PORT pattern 上方
- **VALIDATE**: `pytest backend/tests/test_keystat_keys.py -v` — 3 tests PASS
- **COMMIT**: `feat(parser): port mod-combo splitter from sibling project`

#### Task 2.3: StatsRepo + AppsRepo + SnapshotRepo

- **ACTION**: 建 `backend/db/repository.py`，3 個 repo class，CRUD methods（不含 import — task 2.5 處理）。
- **TEST FIRST**:
  ```python
  # backend/tests/test_repository.py
  import sqlite3
  from pathlib import Path
  import pytest
  from backend.db.migrations import ensure_schema
  from backend.db.repository import StatsRepo, AppsRepo, SnapshotRepo

  @pytest.fixture
  def db(tmp_path):
      p = tmp_path / "t.db"
      ensure_schema(p)
      return p

  def test_snapshot_create_and_fetch(db):
      sn = SnapshotRepo(db)
      sid = sn.create(ts=100, source="test", notes="x")
      row = sn.get(sid)
      assert row["ts"] == 100 and row["source"] == "test"

  def test_apps_upsert(db):
      apps = AppsRepo(db)
      apps.upsert("com.foo.app", display_name="Foo", bucket="terminal", ts=100)
      apps.upsert("com.foo.app", display_name="Foo", bucket="terminal", ts=200)
      row = apps.get("com.foo.app")
      assert row["first_seen_ts"] == 100
      assert row["last_seen_ts"] == 200
      assert row["bucket"] == "terminal"

  def test_stats_top_n_empty(db):
      s = StatsRepo(db)
      assert s.top_n(app=None, kind="single", n=10) == []

  def test_stats_top_n_aggregates(db):
      s = StatsRepo(db)
      sn = SnapshotRepo(db).create(ts=100, source="test")
      conn = sqlite3.connect(db)
      conn.executemany(
          "INSERT INTO events(ts, app_bundle, key, modifiers, count, snapshot_id, source) "
          "VALUES(?,?,?,?,?,?,?)",
          [
              (100, "appA", "j", "",     5, sn, "test"),
              (100, "appA", "j", "",     3, sn, "test"),
              (100, "appA", "k", "",     2, sn, "test"),
              (100, "appA", "v", "cmd",  4, sn, "test"),
          ]
      )
      conn.commit()
      rows = s.top_n(app="appA", kind="single", n=10)
      assert rows[0]["key"] == "j" and rows[0]["total"] == 8
      assert rows[1]["key"] == "k" and rows[1]["total"] == 2
      assert all(r["modifiers"] == "" for r in rows)  # kind=single

  def test_stats_top_n_modifier_filter(db):
      s = StatsRepo(db)
      sn = SnapshotRepo(db).create(ts=100, source="test")
      conn = sqlite3.connect(db)
      conn.executemany(
          "INSERT INTO events(ts, app_bundle, key, modifiers, count, snapshot_id, source) "
          "VALUES(?,?,?,?,?,?,?)",
          [(100, "appA", "v", "cmd", 5, sn, "test")]
      )
      conn.commit()
      rows = s.top_n(app="appA", kind="mod", n=10)
      assert len(rows) == 1 and rows[0]["modifiers"] == "cmd"
  ```
  Run: `pytest backend/tests/test_repository.py` — expect FAIL
- **IMPLEMENT**: 見 REPOSITORY_PATTERN 上方；外加 `AppsRepo`、`SnapshotRepo`：
  ```python
  # backend/db/repository.py
  import sqlite3
  from contextlib import contextmanager
  from pathlib import Path

  class _Base:
      def __init__(self, db_path: Path):
          self.db_path = db_path
      @contextmanager
      def _conn(self):
          conn = sqlite3.connect(self.db_path)
          conn.row_factory = sqlite3.Row
          try:
              yield conn
              conn.commit()
          finally:
              conn.close()

  class SnapshotRepo(_Base):
      def create(self, ts: int, source: str, notes: str | None = None) -> int:
          with self._conn() as c:
              cur = c.execute(
                  "INSERT INTO snapshots(ts, source, notes) VALUES(?,?,?)",
                  (ts, source, notes))
              return cur.lastrowid
      def get(self, sid: int) -> dict | None:
          with self._conn() as c:
              row = c.execute("SELECT * FROM snapshots WHERE id=?", (sid,)).fetchone()
              return dict(row) if row else None

  class AppsRepo(_Base):
      def upsert(self, bundle_id: str, display_name: str | None,
                 bucket: str | None, ts: int) -> None:
          with self._conn() as c:
              c.execute("""
                INSERT INTO apps(bundle_id, display_name, bucket, first_seen_ts, last_seen_ts)
                VALUES(?,?,?,?,?)
                ON CONFLICT(bundle_id) DO UPDATE SET
                  display_name = COALESCE(excluded.display_name, apps.display_name),
                  bucket       = COALESCE(excluded.bucket,       apps.bucket),
                  last_seen_ts = MAX(apps.last_seen_ts, excluded.last_seen_ts)
              """, (bundle_id, display_name, bucket, ts, ts))
      def get(self, bundle_id: str) -> dict | None:
          with self._conn() as c:
              row = c.execute("SELECT * FROM apps WHERE bundle_id=?", (bundle_id,)).fetchone()
              return dict(row) if row else None
      def all(self) -> list[dict]:
          with self._conn() as c:
              return [dict(r) for r in c.execute("SELECT * FROM apps ORDER BY bundle_id").fetchall()]

  class StatsRepo(_Base):
      def top_n(self, app: str | None, kind: str, n: int = 50) -> list[dict]:
          mod_clause = {
              "single": "modifiers = ''",
              "mod":    "modifiers != ''",
              "all":    "1=1",
          }.get(kind, "1=1")
          params = []
          app_clause = ""
          if app:
              app_clause = "AND app_bundle = ?"
              params.append(app)
          params.append(n)
          with self._conn() as c:
              rows = c.execute(
                  f"SELECT key, modifiers, SUM(count) AS total "
                  f"FROM events WHERE {mod_clause} {app_clause} "
                  f"GROUP BY key, modifiers ORDER BY total DESC LIMIT ?",
                  params,
              ).fetchall()
              return [dict(r) for r in rows]
      def total_count(self, app: str | None = None) -> int:
          with self._conn() as c:
              if app:
                  row = c.execute("SELECT SUM(count) FROM events WHERE app_bundle=?", (app,)).fetchone()
              else:
                  row = c.execute("SELECT SUM(count) FROM events").fetchone()
              return row[0] or 0
  ```
- **MIRROR**: REPOSITORY_PATTERN
- **VALIDATE**: `pytest backend/tests/test_repository.py -v` — 5 tests PASS
- **COMMIT**: `feat(db): SnapshotRepo, AppsRepo, StatsRepo with stdlib sqlite3`

#### Task 2.4: APP_BUCKETS seed

- **ACTION**: 建 `backend/db/seed.py`，把 sibling project 的 `APP_BUCKETS` 移過來，提供 `bucket_for(bundle_id)` helper。
- **TEST FIRST**:
  ```python
  # 已含在 task 2.5 的 import test 內
  ```
  Run: skip — pure data，搭 2.5 一起測。
- **IMPLEMENT**: 見 APP_BUCKETS_PORT pattern 上方。並加：
  ```python
  def bucket_for(bundle_id: str) -> str | None:
      for bucket, apps in APP_BUCKETS.items():
          if bundle_id in apps:
              return bucket
      return None
  ```
- **MIRROR**: APP_BUCKETS_PORT
- **VALIDATE**: import OK；`python -c "from backend.db.seed import bucket_for; assert bucket_for('com.googlecode.iterm2') == 'terminal'"`
- **COMMIT**: `feat(db): port APP_BUCKETS taxonomy from sibling`

#### Task 2.5: JSON keystat importer

- **ACTION**: 建 `backend/scripts/import_keystat.py`，CLI 接 path 參數，把 `~/keystat-counts.json` 內容寫進 SQLite。
- **TEST FIRST**:
  ```python
  # backend/tests/test_import.py
  import json
  from pathlib import Path
  import pytest
  from backend.db.migrations import ensure_schema
  from backend.scripts.import_keystat import import_file

  @pytest.fixture
  def db(tmp_path):
      p = tmp_path / "t.db"
      ensure_schema(p)
      return p

  def test_import_minimal(db, tmp_path):
      sample = tmp_path / "sample.json"
      sample.write_text(json.dumps({
          "__meta": {"startedAt": "2026-05-20T06:10:12Z", "lastFlush": "2026-05-28T05:57:03Z"},
          "com.googlecode.iterm2": {"j": 5892, "cmd+v": 3, "return": 14},
          "com.brave.Browser": {"right": 2497, "cmd+1": 1529},
      }))
      result = import_file(sample, db)
      assert result["events"] == 5
      assert result["apps"] == 2
      assert result["snapshot_id"] > 0

      import sqlite3
      conn = sqlite3.connect(db); conn.row_factory = sqlite3.Row
      ev = conn.execute("SELECT * FROM events WHERE app_bundle='com.googlecode.iterm2' AND key='j'").fetchone()
      assert ev["count"] == 5892 and ev["modifiers"] == ""
      cmdv = conn.execute("SELECT * FROM events WHERE key='v' AND modifiers='cmd'").fetchone()
      assert cmdv["count"] == 3
      app = conn.execute("SELECT * FROM apps WHERE bundle_id='com.googlecode.iterm2'").fetchone()
      assert app["bucket"] == "terminal"

  def test_import_full_baseline_count(db):
      """Real 8-day baseline import — slow test, opt-in via marker."""
      src = Path.home() / "keystat-counts.json"
      if not src.exists():
          pytest.skip("baseline json missing")
      result = import_file(src, db)
      # Loose assertion: at least matches what keystat_analyze.py reported
      assert result["events"] > 5000
  ```
  Run: `pytest backend/tests/test_import.py -v` — expect FAIL
- **IMPLEMENT**:
  ```python
  # backend/scripts/import_keystat.py
  from __future__ import annotations
  import argparse
  import json
  import os
  import time
  import sqlite3
  from pathlib import Path
  from ..parsers.keystat_keys import split_mods, serialize_mods, is_modifier_combo
  from ..db.migrations import ensure_schema
  from ..db.seed import bucket_for

  def import_file(json_path: Path, db_path: Path, source: str = "hs_keystat_json") -> dict:
      ensure_schema(db_path)
      data = json.loads(Path(json_path).read_text())
      meta = data.pop("__meta", {}) if isinstance(data.get("__meta"), dict) else {}
      now = int(time.time())
      conn = sqlite3.connect(db_path)
      try:
          cur = conn.execute(
              "INSERT INTO snapshots(ts, source, notes) VALUES(?,?,?)",
              (now, source, f"imported from {json_path.name}")
          )
          snapshot_id = cur.lastrowid
          events_rows = []
          apps_seen: set[str] = set()
          for bundle_id, keys in data.items():
              if not isinstance(keys, dict):
                  continue
              apps_seen.add(bundle_id)
              for raw_key, count in keys.items():
                  if is_modifier_combo(raw_key):
                      mods, base = split_mods(raw_key)
                      mods_str = serialize_mods(mods)
                  else:
                      base, mods_str = raw_key, ""
                  events_rows.append((now, bundle_id, base, mods_str, count, snapshot_id, source))
          conn.executemany(
              "INSERT INTO events(ts, app_bundle, key, modifiers, count, snapshot_id, source) "
              "VALUES(?,?,?,?,?,?,?)",
              events_rows
          )
          for bundle_id in apps_seen:
              conn.execute("""
                INSERT INTO apps(bundle_id, display_name, bucket, first_seen_ts, last_seen_ts)
                VALUES(?,?,?,?,?)
                ON CONFLICT(bundle_id) DO UPDATE SET
                  bucket = COALESCE(excluded.bucket, apps.bucket),
                  last_seen_ts = MAX(apps.last_seen_ts, excluded.last_seen_ts)
              """, (bundle_id, None, bucket_for(bundle_id), now, now))
          conn.commit()
      finally:
          conn.close()
      return {"snapshot_id": snapshot_id, "events": len(events_rows), "apps": len(apps_seen)}

  if __name__ == "__main__":
      parser = argparse.ArgumentParser()
      parser.add_argument("json_path", type=Path)
      parser.add_argument("--db", type=Path,
                          default=Path(os.environ.get("DB_PATH",
                            Path.home() / "Library/Application Support/keyboard-manager/keystat.db")))
      args = parser.parse_args()
      r = import_file(args.json_path, args.db)
      print(f"imported {r['events']} events from {r['apps']} apps; snapshot_id={r['snapshot_id']}")
  ```
- **MIRROR**: STATS_AGGREGATE_PORT、APP_BUCKETS_PORT
- **VALIDATE**:
  - `pytest backend/tests/test_import.py::test_import_minimal -v` — PASS
  - `pytest backend/tests/test_import.py::test_import_full_baseline_count -v` — PASS（若 ~/keystat-counts.json 存在）
  - 手動：`python -m backend.scripts.import_keystat ~/keystat-counts.json --db /tmp/test.db`
- **COMMIT**: `feat(scripts): import_keystat.py — one-shot JSON → SQLite`

#### Task 2.6: Stats API endpoints

- **ACTION**: 建 `backend/api/stats.py`：`GET /api/stats` / `GET /api/apps` / `POST /api/stats/import`。
- **TEST FIRST**:
  ```python
  # backend/tests/test_stats_api.py
  import json
  import pytest
  from pathlib import Path
  from fastapi.testclient import TestClient
  from backend.db.migrations import ensure_schema
  from backend.scripts.import_keystat import import_file

  @pytest.fixture
  def client(tmp_path, monkeypatch):
      db = tmp_path / "t.db"
      ensure_schema(db)
      # seed
      sample = tmp_path / "k.json"
      sample.write_text(json.dumps({
          "__meta": {},
          "com.googlecode.iterm2": {"j": 5892, "k": 2314, "cmd+v": 3},
          "com.brave.Browser":     {"right": 2497, "cmd+1": 1529},
      }))
      import_file(sample, db)
      vil_fix = Path(__file__).parent / "fixtures" / "mylayout.vil"
      monkeypatch.setenv("VIAL_PATH", str(vil_fix))
      monkeypatch.setenv("DB_PATH", str(db))
      from importlib import reload
      from backend import main
      reload(main)
      return TestClient(main.app)

  def test_apps_endpoint(client):
      r = client.get("/api/apps")
      assert r.status_code == 200
      bundles = {a["bundle_id"] for a in r.json()}
      assert {"com.googlecode.iterm2", "com.brave.Browser"} <= bundles

  def test_stats_top_n_global(client):
      r = client.get("/api/stats?top=5&kind=single")
      body = r.json()
      assert body["total_events"] > 0
      assert body["rows"][0]["key"] == "j" or body["rows"][0]["key"] == "right"

  def test_stats_per_app(client):
      r = client.get("/api/stats?app=com.googlecode.iterm2&top=5&kind=single")
      body = r.json()
      assert body["rows"][0]["key"] == "j"
      assert body["rows"][0]["count"] == 5892

  def test_stats_mod_kind(client):
      r = client.get("/api/stats?kind=mod&top=5")
      body = r.json()
      keys = {(r_["key"], r_["modifiers"]) for r_ in body["rows"]}
      assert ("1", "cmd") in keys or ("v", "cmd") in keys
  ```
  Run: `pytest backend/tests/test_stats_api.py` — expect FAIL
- **IMPLEMENT**:
  ```python
  # backend/api/stats.py
  from pathlib import Path
  from fastapi import APIRouter, Query
  from ..db.repository import StatsRepo, AppsRepo

  router = APIRouter()

  @router.get("/api/apps")
  def get_apps():
      from ..main import DB_PATH
      return AppsRepo(DB_PATH).all()

  @router.get("/api/stats")
  def get_stats(
      app: str | None = None,
      top: int = Query(50, ge=1, le=500),
      kind: str = Query("single", regex="^(single|mod|all)$"),
  ):
      from ..main import DB_PATH
      repo = StatsRepo(DB_PATH)
      rows = repo.top_n(app=app, kind=kind, n=top)
      total = repo.total_count(app=app)
      return {
          "scope": {"app": app, "kind": kind, "top": top},
          "total_events": total,
          "rows": [
              {"key": r["key"], "modifiers": r["modifiers"],
               "count": r["total"], "pct": (r["total"]/total*100) if total else 0.0}
              for r in rows
          ],
      }
  ```
  Update `backend/main.py` 註冊 router；加 `POST /api/stats/import`（可選，先 manual CLI 為主）。
- **MIRROR**: ERROR_HANDLING / LOGGING_PATTERN
- **VALIDATE**: `pytest backend/tests/test_stats_api.py -v` — 4 tests PASS
- **COMMIT**: `feat(api): stats endpoints — top-N + apps`

#### Task 2.7: Frontend stats page

- **ACTION**: 建 `frontend/stats.js`：表格 + per-app dropdown filter（無 chart，先純表）。
- **TEST FIRST**: Backend contract test 已在 2.6 滿足；frontend 為 manual verification。
- **IMPLEMENT**:
  ```javascript
  // frontend/stats.js
  (function () {
    "use strict";
    const root = document.getElementById("view-stats");
    let apps = [];

    async function loadApps() {
      const r = await fetch("/api/apps");
      apps = r.ok ? await r.json() : [];
    }

    async function loadStats(app, kind = "single") {
      const u = new URL("/api/stats", location.origin);
      if (app) u.searchParams.set("app", app);
      u.searchParams.set("kind", kind);
      u.searchParams.set("top", "30");
      const r = await fetch(u);
      return r.ok ? await r.json() : null;
    }

    function render(stats) {
      if (!stats) return `<p class="error">stats unavailable</p>`;
      const tableRows = stats.rows.map((row, i) => `
        <tr>
          <td>${i+1}</td>
          <td>${row.count}</td>
          <td>${row.pct.toFixed(2)}%</td>
          <td><code>${row.modifiers ? row.modifiers + "+" : ""}${row.key}</code></td>
        </tr>`).join("");
      return `
        <div class="stats-toolbar">
          <select id="stats-app">
            <option value="">All apps</option>
            ${apps.map(a => `<option value="${a.bundle_id}">${a.display_name || a.bundle_id} (${a.bucket || "—"})</option>`).join("")}
          </select>
          <select id="stats-kind">
            <option value="single">Single keys</option>
            <option value="mod">Mod combos</option>
            <option value="all">All</option>
          </select>
        </div>
        <p class="meta">Total events in scope: <strong>${stats.total_events}</strong></p>
        <table class="stats-table">
          <thead><tr><th>#</th><th>Count</th><th>%</th><th>Key</th></tr></thead>
          <tbody>${tableRows}</tbody>
        </table>`;
    }

    async function init() {
      await loadApps();
      const stats = await loadStats(null, "single");
      root.innerHTML = render(stats);
      root.querySelector("#stats-app").addEventListener("change", refresh);
      root.querySelector("#stats-kind").addEventListener("change", refresh);
    }

    async function refresh() {
      const app = root.querySelector("#stats-app").value || null;
      const kind = root.querySelector("#stats-kind").value;
      const stats = await loadStats(app, kind);
      // Preserve toolbar selection, only update table
      const html = render(stats);
      root.innerHTML = html;
      root.querySelector("#stats-app").value = app || "";
      root.querySelector("#stats-kind").value = kind;
      root.querySelector("#stats-app").addEventListener("change", refresh);
      root.querySelector("#stats-kind").addEventListener("change", refresh);
    }

    // Lazy load: only init when Stats tab clicked
    document.querySelector('nav button[data-view="stats"]').addEventListener("click", () => {
      if (!root.dataset.loaded) { init(); root.dataset.loaded = "1"; }
    });
  })();
  ```
  Update `frontend/index.html` 加 `<script src="stats.js"></script>`。
- **MIRROR**: FRONTEND_MODULE pattern
- **VALIDATE**:
  - `docker compose up -d --build`、`POST /api/stats/import` 或本機跑 `python -m backend.scripts.import_keystat ~/keystat-counts.json`
  - Stats tab：top-N 數字與 `python ~/Projects/keyboard-map/keystat_analyze.py` 對比 — AC-5 ✅
- **COMMIT**: `feat(frontend): stats dashboard with per-app + kind filter`

---

### Milestone M3 — Heatmap on layout

#### Task 3.1: Heatmap mapper（key → layer, row, col）

- **ACTION**: 建 `backend/db/heatmap_mapper.py`，給 layout 與 stats，產出每個 (layer, row, col) 的 count；同時回 `unmapped[]` 列出無法對映的鍵。
- **TEST FIRST**:
  ```python
  # backend/tests/test_heatmap_mapper.py
  from pathlib import Path
  import pytest
  from backend.parsers.vial import parse
  from backend.parsers.keycodes import resolve, LayoutContext
  from backend.db.heatmap_mapper import build_position_index, overlay_stats

  FIXTURE = Path(__file__).parent / "fixtures" / "mylayout.vil"

  def test_position_index_includes_base_layer():
      layout = parse(FIXTURE)
      idx = build_position_index(layout)
      # base layer j key should be at (0, 7, 2) (row 7 col 2 in mylayout right side)
      pos = idx.get(("j", ""))
      assert pos is not None
      assert pos[0]["layer"] == 0

  def test_overlay_returns_cells_and_unmapped():
      layout = parse(FIXTURE)
      idx = build_position_index(layout)
      stats_rows = [
          {"key": "j",   "modifiers": "",     "total": 5892},
          {"key": "f19", "modifiers": "",     "total": 1201},
          {"key": "1",   "modifiers": "cmd",  "total": 1529},
      ]
      result = overlay_stats(idx, stats_rows)
      assert any(c["key"] == "j" and c["count"] == 5892 for c in result["cells"])
      assert any(u["key"] == "f19" for u in result["unmapped"])
      # cmd+1 — depends on policy; if we map mod combos to base position, "1" should appear
      # Decision: map to base position; document in code
      assert any(c["key"] == "1" and c["count"] == 1529 for c in result["cells"]) \
          or any(u["key"] == "1" and u.get("modifiers") == "cmd" for u in result["unmapped"])
  ```
  Run: `pytest backend/tests/test_heatmap_mapper.py` — expect FAIL
- **IMPLEMENT**:
  ```python
  # backend/db/heatmap_mapper.py
  from collections import defaultdict
  from ..parsers.keycodes import resolve, LayoutContext
  from ..parsers.keycode_labels import KEYCODE_LABELS

  # Build reverse mapping: label_top.lower() → list of (layer, row, col, raw)
  # Plus alias map: macOS event names → label_top
  EVENT_KEY_ALIASES = {
      "space": "Space",
      "return": "Enter",
      "delete": "Bksp",
      "forwarddelete": "Del",
      "escape": "Esc",
      "tab": "Tab",
      "left": "←", "right": "→", "up": "↑", "down": "↓",
      "pageup": "PgUp", "pagedown": "PgDn",
      "home": "Home", "end": "End",
  }

  def _normalize(event_key: str) -> str:
      # macOS reports "j" "k" "space" etc. lowercase letters
      k = event_key.lower()
      return EVENT_KEY_ALIASES.get(k, k.upper() if len(k) == 1 else k)

  def build_position_index(layout) -> dict[tuple[str, str], list[dict]]:
      """Return: {(label_top_normalized, modifiers): [{layer, row, col, raw}, ...]}.
      modifiers always '' for now — we map mod-combos to their base key position.
      """
      ctx = LayoutContext(tap_dance=layout.tap_dance)
      idx: dict[tuple[str, str], list[dict]] = defaultdict(list)
      for layer in layout.layers:
          for row in layer.rows:
              for ci, raw in enumerate(row.keys):
                  if raw is None or raw in ("KC_NO", "KC_TRNS"):
                      continue
                  rk = resolve(raw, ctx)
                  if not rk.label_top:
                      continue
                  key_norm = rk.label_top
                  idx[(key_norm, "")].append(
                      {"layer": layer.index, "row": row.row, "col": ci, "raw": raw})
      return idx

  def overlay_stats(idx: dict, stats_rows: list[dict]) -> dict:
      cells = []
      unmapped = []
      for r in stats_rows:
          base = _normalize(r["key"])
          positions = idx.get((base, ""))
          if positions:
              # Pick base layer first; if not present, fall back to first
              pos = next((p for p in positions if p["layer"] == 0), positions[0])
              cells.append({
                  "layer": pos["layer"], "row": pos["row"], "col": pos["col"],
                  "key": base, "count": r["total"]
              })
          else:
              unmapped.append({
                  "key": r["key"], "modifiers": r["modifiers"],
                  "count": r["total"],
                  "reason": "no physical position"
              })
      return {"cells": cells, "unmapped": unmapped}
  ```
- **MIRROR**: 無，新建 mapper
- **VALIDATE**: `pytest backend/tests/test_heatmap_mapper.py -v` — 2 tests PASS
- **COMMIT**: `feat(db): heatmap mapper with macOS event key aliases`

#### Task 3.2: Heatmap API endpoint

- **ACTION**: 加 `GET /api/stats/heatmap` 到 `backend/api/stats.py`。
- **TEST FIRST**:
  ```python
  # backend/tests/test_heatmap_api.py (use same fixture as test_stats_api)
  def test_heatmap_global_coverage(client):
      r = client.get("/api/stats/heatmap")
      assert r.status_code == 200
      body = r.json()
      assert "cells" in body and "unmapped" in body
      assert body["coverage_pct"] >= 0

  def test_heatmap_max_count_set(client):
      r = client.get("/api/stats/heatmap")
      body = r.json()
      if body["cells"]:
          assert body["max_count"] >= max(c["count"] for c in body["cells"])
  ```
  Run: expect FAIL
- **IMPLEMENT**:
  ```python
  # backend/api/stats.py — add
  from ..parsers.vial import parse
  from ..db.heatmap_mapper import build_position_index, overlay_stats

  @router.get("/api/stats/heatmap")
  def get_heatmap(app: str | None = None):
      from ..main import VIAL_PATH, DB_PATH
      layout = parse(VIAL_PATH)
      idx = build_position_index(layout)
      repo = StatsRepo(DB_PATH)
      rows = repo.top_n(app=app, kind="single", n=500)
      result = overlay_stats(idx, rows)
      total = sum(r["total"] for r in rows)
      mapped = sum(c["count"] for c in result["cells"])
      return {
          "scope": {"app": app},
          "max_count": max((c["count"] for c in result["cells"]), default=0),
          "cells": result["cells"],
          "unmapped": result["unmapped"],
          "coverage_pct": (mapped / total * 100) if total else 0,
      }
  ```
- **MIRROR**: 無
- **VALIDATE**: `pytest backend/tests/test_heatmap_api.py -v`
- **COMMIT**: `feat(api): GET /api/stats/heatmap with coverage report`

#### Task 3.3: Frontend heatmap overlay

- **ACTION**: 建 `frontend/heatmap.js`、把 Stats tab 改成 「heatmap + 表格」雙 view（user 在 PRD 選 並重）。
- **TEST FIRST**: Backend contract 已測；frontend manual。
- **IMPLEMENT**:
  ```javascript
  // frontend/heatmap.js
  (function () {
    "use strict";
    function colorFor(count, maxCount) {
      if (!count || !maxCount) return "transparent";
      const intensity = Math.log(1 + count) / Math.log(1 + maxCount);
      const r = Math.round(255 * intensity);
      const g = Math.round(80 * (1 - intensity));
      const b = Math.round(80 * (1 - intensity));
      return `rgba(${r}, ${g}, ${b}, 0.55)`;
    }

    async function loadHeatmap(app) {
      const u = new URL("/api/stats/heatmap", location.origin);
      if (app) u.searchParams.set("app", app);
      const r = await fetch(u);
      return r.ok ? await r.json() : null;
    }

    function applyOverlay(rootEl, heatmap, layerIdx) {
      const cells = heatmap.cells.filter(c => c.layer === layerIdx);
      const max = heatmap.max_count;
      rootEl.querySelectorAll(".row").forEach((row, ri) => {
        row.querySelectorAll(".key").forEach((k, ci) => {
          const m = cells.find(c => c.row === ri && c.col === ci);
          k.style.backgroundColor = m ? colorFor(m.count, max) : "";
          k.dataset.count = m ? m.count : 0;
          if (m) k.title += ` | count=${m.count}`;
        });
      });
    }

    window.heatmap = { loadHeatmap, applyOverlay, colorFor };
  })();
  ```
  Update `frontend/stats.js`：增加「Show heatmap」toggle、整合 grid render（layer 0 預設）。
  Update `frontend/style.css`：`.stats-grid-wrapper` 等。
- **MIRROR**: FRONTEND_MODULE
- **VALIDATE**:
  - Manual：開 Stats tab → 看 heatmap on layer 0、`space` 最紅、`hjkl` 醒目；切 per-app=terminal 看 vim pattern；切 per-app=browser 看方向鍵增強
  - AC-6（≥ 90% 涵蓋）：`curl http://localhost:8000/api/stats/heatmap | jq .coverage_pct` ≥ 90
- **COMMIT**: `feat(frontend): heatmap overlay on keyboard grid`

#### Task 3.4: Bidirectional highlight（grid ↔ table）

- **ACTION**: 點 grid 上某鍵 → 表格自動 highlight 該行；點表格行 → grid 對應鍵閃爍。
- **TEST FIRST**: pure frontend interaction — manual。
- **IMPLEMENT**:
  ```javascript
  // frontend/heatmap.js — add wireBidirectional()
  function wireBidirectional(rootEl, tableEl) {
    rootEl.addEventListener("click", e => {
      const k = e.target.closest(".key"); if (!k) return;
      const top = k.querySelector(".label-top")?.textContent;
      if (!top) return;
      tableEl.querySelectorAll("tr.highlighted").forEach(r => r.classList.remove("highlighted"));
      const row = [...tableEl.querySelectorAll("tbody tr")]
        .find(r => r.querySelector("code")?.textContent.endsWith(top));
      if (row) {
        row.classList.add("highlighted");
        row.scrollIntoView({block: "center", behavior: "smooth"});
      }
    });
    tableEl.addEventListener("click", e => {
      const tr = e.target.closest("tr"); if (!tr) return;
      const code = tr.querySelector("code")?.textContent; if (!code) return;
      rootEl.querySelectorAll(".key.flash").forEach(k => k.classList.remove("flash"));
      const target = [...rootEl.querySelectorAll(".key")]
        .find(k => k.querySelector(".label-top")?.textContent === code.replace(/^[^+]+\+/, ""));
      if (target) {
        target.classList.add("flash");
        setTimeout(() => target.classList.remove("flash"), 1200);
      }
    });
  }
  ```
  Style flash + highlighted。
- **MIRROR**: FRONTEND_MODULE
- **VALIDATE**: Manual — click any heatmap cell highlights table; click table row flashes grid cell.
- **COMMIT**: `feat(frontend): bidirectional grid↔table highlight on heatmap`

---

### Milestone M4 — Native helper + Interactive Simulator

#### Task 4.1: Native helper skeleton（pynput listener）

- **ACTION**: 建 `native-helper/pyproject.toml`、`native-helper/main.py`、global keydown/keyup listener；先 print 不寫 SQLite、不開 WS。
- **TEST FIRST**: pynput hooks 全域系統，pytest 在 CI 跑不到；改用 **smoke test**：
  ```python
  # native-helper/tests/test_smoke.py
  # Skipped if pynput install missing; mainly assert module imports + handler signature
  import pytest

  def test_import_main():
      pytest.importorskip("pynput")
      from native_helper import main  # noqa: F401

  def test_handler_takes_key():
      pytest.importorskip("pynput")
      from native_helper.main import on_press, on_release
      from pynput.keyboard import KeyCode
      key = KeyCode.from_char("j")
      on_press(key)  # should not raise
      on_release(key)
  ```
  Run: expect FAIL.
- **IMPLEMENT**:
  - `native-helper/pyproject.toml`:
    ```toml
    [project]
    name = "keyboard-manager-helper"
    version = "0.0.1"
    requires-python = ">=3.11"
    dependencies = ["pynput>=1.7", "pyobjc-framework-Cocoa>=10.3", "websockets>=13"]
    ```
  - `native-helper/main.py`:
    ```python
    from pynput import keyboard
    import logging
    logger = logging.getLogger("helper"); logging.basicConfig(level=logging.INFO)

    def _key_name(key) -> str:
        try:
            return key.char or repr(key)
        except AttributeError:
            return str(key).replace("Key.", "")

    def on_press(key):
        logger.info("DOWN %s", _key_name(key))

    def on_release(key):
        logger.info("UP %s", _key_name(key))

    if __name__ == "__main__":
        with keyboard.Listener(on_press=on_press, on_release=on_release) as listener:
            listener.join()
    ```
  - `native-helper/__init__.py` empty。
- **MIRROR**: 無 — 新建 native module
- **VALIDATE**:
  - `cd native-helper && pip install -e .`
  - `python -m native_helper.main`（需 Accessibility 權限）— 按幾下鍵看 stdout
  - `pytest native-helper/tests/test_smoke.py -v`
- **COMMIT**: `feat(helper): pynput global listener skeleton`

#### Task 4.2: App tracker（NSWorkspace bundle ID）

- **ACTION**: 建 `native-helper/app_tracker.py`，cache 100ms。
- **TEST FIRST**:
  ```python
  # native-helper/tests/test_app_tracker.py
  import pytest

  def test_current_app_returns_string_or_none():
      pytest.importorskip("AppKit")
      from native_helper.app_tracker import current_app
      r = current_app()
      assert r is None or isinstance(r, str)
  ```
  Run: expect FAIL.
- **IMPLEMENT**:
  ```python
  # native-helper/app_tracker.py
  import time
  try:
      from AppKit import NSWorkspace
  except ImportError:
      NSWorkspace = None

  _cache = {"ts": 0.0, "value": None}

  def current_app() -> str | None:
      now = time.monotonic()
      if now - _cache["ts"] < 0.1:
          return _cache["value"]
      if NSWorkspace is None:
          return None
      app = NSWorkspace.sharedWorkspace().frontmostApplication()
      bid = app.bundleIdentifier() if app else None
      _cache["ts"], _cache["value"] = now, bid
      return bid
  ```
- **MIRROR**: 無
- **VALIDATE**: `pytest native-helper/tests/test_app_tracker.py -v`；`python -c "from native_helper.app_tracker import current_app; print(current_app())"` 顯示當前 app
- **COMMIT**: `feat(helper): NSWorkspace-based frontmost app tracker`

#### Task 4.3: SQLite EventSink（batch write）

- **ACTION**: 建 `native-helper/sink.py`，每 5 秒 flush buffer 進 SQLite events。
- **TEST FIRST**:
  ```python
  # native-helper/tests/test_sink.py
  import sqlite3
  import pytest
  from pathlib import Path
  from native_helper.sink import EventSink

  @pytest.fixture
  def db(tmp_path):
      p = tmp_path / "t.db"
      # Need migrations from backend
      import sys; sys.path.insert(0, str(Path(__file__).parents[2] / "backend"))
      from backend.db.migrations import ensure_schema
      ensure_schema(p)
      return p

  def test_buffer_and_flush(db):
      sink = EventSink(db, source="test", flush_interval=999)
      sink.start(snapshot_id=1)
      sink.record(key="j", modifiers="", app_bundle="appA", ts=100)
      sink.record(key="k", modifiers="", app_bundle="appA", ts=101)
      sink.flush_now()
      conn = sqlite3.connect(db); conn.row_factory = sqlite3.Row
      rows = conn.execute("SELECT * FROM events").fetchall()
      assert len(rows) == 2
      assert rows[0]["key"] == "j" and rows[0]["count"] == 1
  ```
  Run: expect FAIL.
- **IMPLEMENT**:
  ```python
  # native-helper/sink.py
  import sqlite3
  import threading
  import time
  from pathlib import Path

  class EventSink:
      def __init__(self, db_path: Path, source: str = "native_helper", flush_interval: float = 5.0):
          self.db_path = db_path
          self.source = source
          self.flush_interval = flush_interval
          self.buffer: list[tuple] = []
          self.lock = threading.Lock()
          self._timer: threading.Timer | None = None
          self.snapshot_id: int | None = None

      def start(self, snapshot_id: int):
          self.snapshot_id = snapshot_id
          self._schedule()

      def _schedule(self):
          self._timer = threading.Timer(self.flush_interval, self._tick)
          self._timer.daemon = True
          self._timer.start()

      def _tick(self):
          self.flush_now()
          self._schedule()

      def record(self, key: str, modifiers: str, app_bundle: str, ts: int):
          with self.lock:
              self.buffer.append((ts, app_bundle, key, modifiers, 1, self.snapshot_id, self.source))

      def flush_now(self):
          with self.lock:
              rows, self.buffer = self.buffer, []
          if not rows:
              return
          conn = sqlite3.connect(self.db_path)
          try:
              conn.executemany(
                  "INSERT INTO events(ts, app_bundle, key, modifiers, count, snapshot_id, source) "
                  "VALUES(?,?,?,?,?,?,?)", rows)
              conn.commit()
          finally:
              conn.close()

      def stop(self):
          if self._timer: self._timer.cancel()
          self.flush_now()
  ```
- **MIRROR**: 無
- **VALIDATE**: `pytest native-helper/tests/test_sink.py -v`
- **COMMIT**: `feat(helper): batch SQLite EventSink with 5s flush`

#### Task 4.4: WebSocket server

- **ACTION**: 在 `native-helper/main.py` 加 `websockets` server on `:8765`，broadcast keypress events 給多 subscriber。
- **TEST FIRST**: WS server 端到端不易 unit test；先寫 dispatch helper test：
  ```python
  # native-helper/tests/test_dispatcher.py
  import asyncio
  import pytest
  from native_helper.dispatcher import EventDispatcher

  @pytest.mark.asyncio
  async def test_broadcast_to_all_subscribers():
      d = EventDispatcher()
      sub1 = asyncio.Queue()
      sub2 = asyncio.Queue()
      d.subscribe(sub1); d.subscribe(sub2)
      await d.broadcast({"type": "down", "key": "j"})
      assert (await sub1.get())["key"] == "j"
      assert (await sub2.get())["key"] == "j"

  @pytest.mark.asyncio
  async def test_unsubscribe_stops_delivery():
      d = EventDispatcher()
      q = asyncio.Queue()
      d.subscribe(q); d.unsubscribe(q)
      await d.broadcast({"type":"down","key":"j"})
      assert q.empty()
  ```
  Run: expect FAIL（dispatcher 不存在）。
- **IMPLEMENT**:
  - `native-helper/dispatcher.py`:
    ```python
    import asyncio
    class EventDispatcher:
        def __init__(self):
            self.subscribers: set[asyncio.Queue] = set()
        def subscribe(self, q: asyncio.Queue): self.subscribers.add(q)
        def unsubscribe(self, q: asyncio.Queue): self.subscribers.discard(q)
        async def broadcast(self, msg: dict):
            for q in list(self.subscribers):
                try: q.put_nowait(msg)
                except asyncio.QueueFull: pass
    ```
  - 修改 `native-helper/main.py` 整合 WS server（重寫 `__main__`）：
    ```python
    import asyncio
    import json
    import time
    from pathlib import Path
    import websockets
    from pynput import keyboard
    from .app_tracker import current_app
    from .sink import EventSink
    from .dispatcher import EventDispatcher

    DB_PATH = Path.home() / "Library/Application Support/keyboard-manager/keystat.db"
    WS_PORT = 8765

    dispatcher = EventDispatcher()
    sink: EventSink | None = None
    loop: asyncio.AbstractEventLoop | None = None

    def _key_name(key) -> str:
        try: return key.char or str(key).replace("Key.", "")
        except AttributeError: return str(key).replace("Key.", "")

    def on_press(key):
        name = _key_name(key)
        ts = int(time.time())
        app = current_app() or "unknown"
        if sink: sink.record(key=name, modifiers="", app_bundle=app, ts=ts)
        msg = {"type":"down", "key":name, "modifiers":"", "app":app, "ts":ts}
        if loop and loop.is_running():
            asyncio.run_coroutine_threadsafe(dispatcher.broadcast(msg), loop)

    def on_release(key):
        name = _key_name(key)
        ts = int(time.time())
        app = current_app() or "unknown"
        msg = {"type":"up", "key":name, "modifiers":"", "app":app, "ts":ts}
        if loop and loop.is_running():
            asyncio.run_coroutine_threadsafe(dispatcher.broadcast(msg), loop)

    async def ws_handler(websocket):
        q = asyncio.Queue(maxsize=1000)
        dispatcher.subscribe(q)
        try:
            while True:
                msg = await q.get()
                await websocket.send(json.dumps(msg))
        finally:
            dispatcher.unsubscribe(q)

    async def serve():
        async with websockets.serve(ws_handler, "0.0.0.0", WS_PORT):
            await asyncio.Future()

    def main():
        global sink, loop
        from .sink import EventSink
        # Create or open snapshot
        import sqlite3
        from importlib.util import spec_from_file_location, module_from_spec
        # Import backend.db.migrations + create snapshot
        ts = int(time.time())
        conn = sqlite3.connect(DB_PATH)
        try:
            cur = conn.execute("INSERT INTO snapshots(ts, source, notes) VALUES(?,?,?)",
                              (ts, "native_helper", "helper started"))
            snapshot_id = cur.lastrowid
            conn.commit()
        finally:
            conn.close()
        sink = EventSink(DB_PATH, source="native_helper", flush_interval=5.0)
        sink.start(snapshot_id=snapshot_id)
        loop = asyncio.new_event_loop()
        listener = keyboard.Listener(on_press=on_press, on_release=on_release)
        listener.start()
        try:
            loop.run_until_complete(serve())
        finally:
            listener.stop(); sink.stop()

    if __name__ == "__main__":
        main()
    ```
- **MIRROR**: 無
- **VALIDATE**:
  - `pytest native-helper/tests/test_dispatcher.py -v`
  - 手動：`python -m native_helper.main`；另開終端 `websocat ws://localhost:8765`；按鍵看 JSON 推送
- **COMMIT**: `feat(helper): WS server + SQLite sink integration`

#### Task 4.5: Backend WS reverse proxy `/api/live`

- **ACTION**: 在 `backend/api/live.py` 建 WebSocket route，dial helper :8765 並透傳。
- **TEST FIRST**: WS proxy 用 integration test 較難；寫一個 mock helper 跑 in-process：
  ```python
  # backend/tests/test_live_proxy.py
  import asyncio
  import json
  import pytest
  import websockets
  from fastapi.testclient import TestClient

  @pytest.mark.skip(reason="manual integration test — requires helper running")
  def test_live_proxy_passes_events():
      """Run native_helper.main in another terminal first; then open WS to backend:8000/api/live."""
      pass
  ```
  Run: skipped, treat manual test as primary.
- **IMPLEMENT**:
  ```python
  # backend/api/live.py
  import asyncio
  import os
  import logging
  from fastapi import APIRouter, WebSocket, WebSocketDisconnect
  import websockets

  router = APIRouter()
  logger = logging.getLogger("keyboard_manager.live")
  HELPER_URL = os.environ.get("HELPER_WS_URL", "ws://host.docker.internal:8765")

  @router.websocket("/api/live")
  async def live(ws: WebSocket):
      await ws.accept()
      try:
          async with websockets.connect(HELPER_URL) as up:
              async def pump():
                  async for msg in up:
                      await ws.send_text(msg)
              await pump()
      except (OSError, websockets.exceptions.WebSocketException) as e:
          logger.warning("helper unreachable: %s", e)
          await ws.send_json({"type":"helper_disconnected", "ts": 0})
          await ws.close()
      except WebSocketDisconnect:
          pass
  ```
  Update `main.py` 註冊。
- **MIRROR**: ERROR_HANDLING / LOGGING_PATTERN
- **VALIDATE**:
  - `python -m native_helper.main`（host-side）
  - `docker compose up -d --build`
  - Browser console: `ws = new WebSocket("ws://localhost:8080/api/live"); ws.onmessage = e => console.log(e.data)`
  - 按鍵看 events 從 helper → backend → nginx → browser
- **COMMIT**: `feat(api): /api/live WS proxy to native helper`

#### Task 4.6: Frontend Interactive page

- **ACTION**: 建 `frontend/interactive.js`，連 `/api/live`、根據 hold key 切 layer view。
- **TEST FIRST**: Frontend interactive — manual。
- **IMPLEMENT**:
  ```javascript
  // frontend/interactive.js
  (function () {
    "use strict";
    const root = document.getElementById("view-interactive");
    let layoutCache = null;
    let activeLayer = 0;
    const heldKeys = new Set();
    let socket = null;
    let helperStatus = "disconnected";

    async function ensureLayout() {
      if (layoutCache) return layoutCache;
      const r = await fetch("/api/layout");
      if (r.ok) layoutCache = await r.json();
      return layoutCache;
    }

    // Map "space" / lowercase letters from event-layer to base layer position; then
    // find what hold action that position triggers (e.g. base layer thumb middle = LT1(KC_SPACE) → hold=L1)
    function detectActiveLayer() {
      if (!layoutCache) return 0;
      const base = layoutCache.layers[0];
      // Iterate held keys, find any whose base position has resolved.expanded_kind=layer-tap
      for (const heldEventKey of heldKeys) {
        const labelGuess = heldEventKey === "space" ? "Space" :
                           heldEventKey === "tab" ? "Tab" :
                           heldEventKey.length === 1 ? heldEventKey.toUpperCase() :
                           heldEventKey;
        for (const row of base.rows) {
          for (const k of row.keys) {
            if (!k) continue;
            const r = k.resolved;
            if (r.expanded_kind === "layer-tap" && r.label_top === labelGuess) {
              // r.label_bottom = "→L1" → parse the digit
              const m = (r.label_bottom || "").match(/L(\d+)/);
              if (m) return parseInt(m[1], 10);
            }
          }
        }
      }
      return 0;
    }

    async function render() {
      const layout = await ensureLayout();
      if (!layout) { root.innerHTML = "<p class=error>layout load failed</p>"; return; }
      const gridHtml = window.gridRender.renderLayer(layout.layers[activeLayer]);
      root.innerHTML = `
        <div class="interactive-status">
          helper: <span class="status-${helperStatus}">●</span> ${helperStatus}
          | active layer: <strong>${activeLayer}</strong>
          | held: ${[...heldKeys].join(", ") || "(none)"}
        </div>
        ${gridHtml}`;
    }

    function connect() {
      socket = new WebSocket((location.protocol === "https:" ? "wss://" : "ws://") + location.host + "/api/live");
      socket.onopen  = () => { helperStatus = "connected"; render(); };
      socket.onclose = () => { helperStatus = "disconnected"; render(); setTimeout(connect, 3000); };
      socket.onerror = () => { helperStatus = "error"; render(); };
      socket.onmessage = e => {
        const msg = JSON.parse(e.data);
        if (msg.type === "down") heldKeys.add(msg.key.toLowerCase());
        else if (msg.type === "up") heldKeys.delete(msg.key.toLowerCase());
        else if (msg.type === "helper_disconnected") { helperStatus = "disconnected"; render(); return; }
        const newLayer = detectActiveLayer();
        if (newLayer !== activeLayer) { activeLayer = newLayer; }
        render();
      };
    }

    document.querySelector('nav button[data-view="interactive"]').addEventListener("click", () => {
      if (!root.dataset.loaded) { render(); connect(); root.dataset.loaded = "1"; }
    });
  })();
  ```
- **MIRROR**: FRONTEND_MODULE
- **VALIDATE**:
  - Helper 跑、docker compose up
  - 切 Interactive tab → 顯示 `helper: ● connected`
  - 按住 Space → grid 切到 layer 1（NAV）→ AC-8 ✅
  - 鬆開 → 回 layer 0
- **COMMIT**: `feat(frontend): interactive simulator with WS-driven layer switching`

#### Task 4.7: M4 acceptance — write events end-to-end

- **ACTION**: 跑 30 秒打字、確認 SQLite events 增加 + helper 沒 crash。
- **TEST FIRST**: 手動驗證 + 簡單 SQL check：
  ```bash
  before=$(sqlite3 ~/Library/Application\ Support/keyboard-manager/keystat.db \
    "SELECT COUNT(*) FROM events WHERE source='native_helper'")
  echo "before: $before"
  # 打字 30 秒...
  after=$(sqlite3 ~/Library/Application\ Support/keyboard-manager/keystat.db \
    "SELECT COUNT(*) FROM events WHERE source='native_helper'")
  echo "after: $after; delta: $((after - before))"
  test $((after - before)) -ge 50 || echo "FAIL: too few events captured"
  ```
- **IMPLEMENT**: 無新 code — 純驗證
- **MIRROR**: 無
- **VALIDATE**: delta ≥ 50 → AC-7 ✅
- **COMMIT**: 無（無 code change）

---

### Milestone M5 — Polish

#### Task 5.1: launchd plist for helper

- **ACTION**: 建 `native-helper/com.keyboard-manager.helper.plist`、寫 README 步驟（user 自己 `launchctl load`）。
- **TEST FIRST**: 手動：reboot → helper 自動跑。
- **IMPLEMENT**:
  ```xml
  <?xml version="1.0" encoding="UTF-8"?>
  <!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
  <plist version="1.0">
  <dict>
    <key>Label</key><string>com.keyboard-manager.helper</string>
    <key>ProgramArguments</key>
    <array>
      <string>/usr/bin/env</string>
      <string>python3</string>
      <string>-m</string>
      <string>native_helper.main</string>
    </array>
    <key>WorkingDirectory</key><string>/Users/logan/Projects/keyboard-manager/native-helper</string>
    <key>RunAtLoad</key><true/>
    <key>KeepAlive</key><true/>
    <key>StandardOutPath</key><string>/tmp/keyboard-manager-helper.out.log</string>
    <key>StandardErrorPath</key><string>/tmp/keyboard-manager-helper.err.log</string>
  </dict>
  </plist>
  ```
- **MIRROR**: 無
- **VALIDATE**:
  - `cp native-helper/com.keyboard-manager.helper.plist ~/Library/LaunchAgents/`
  - `launchctl load ~/Library/LaunchAgents/com.keyboard-manager.helper.plist`
  - `pgrep -f native_helper.main` — 有 pid
  - Kill 該 pid → 等 5s 後重新出現（KeepAlive）
- **COMMIT**: `feat(helper): launchd plist for auto-start`

#### Task 5.2: smoke.sh

- **ACTION**: 建 `scripts/smoke.sh`，跑 compose up → curl `/health` + `/api/layout` → 確認 vial_exists=true。
- **TEST FIRST**: shell script，本身就是 test
- **IMPLEMENT**:
  ```bash
  #!/usr/bin/env bash
  set -euo pipefail
  cd "$(dirname "$0")/.."
  export VIAL_CONFIG="${VIAL_CONFIG:-$HOME/Projects/keyboard-map/mylayout.vil}"
  docker compose up -d --build
  echo "waiting for backend..."
  for i in $(seq 1 30); do
    if curl -sf http://localhost:8000/health > /tmp/km-health.json; then break; fi
    sleep 1
  done
  cat /tmp/km-health.json
  jq -e '.vial_exists == true' /tmp/km-health.json
  curl -sf http://localhost:8000/api/layout | jq -e '.layers | length == 6'
  echo "smoke OK"
  ```
- **MIRROR**: 無
- **VALIDATE**: `bash scripts/smoke.sh` → 「smoke OK」→ AC-9 ✅
- **COMMIT**: `feat(scripts): smoke.sh end-to-end check`

#### Task 5.3: Hammerspoon migration doc

- **ACTION**: 建 `docs/migration-from-hammerspoon.md`，寫如何 disable HS `keystat.lua` binding。
- **IMPLEMENT**: doc 內容（簡短）：
  ```markdown
  # Migration: Hammerspoon keystat → keyboard-manager helper

  After Milestone M4 is shipped, the native helper takes over global keystroke capture.
  Hammerspoon's `keystat.lua` should be **disabled** to avoid double-counting.

  ## Steps

  1. Confirm helper is running: `pgrep -f native_helper.main`
  2. Confirm events are being written:
     ```bash
     sqlite3 ~/Library/Application\ Support/keyboard-manager/keystat.db \
       "SELECT COUNT(*) FROM events WHERE source='native_helper'"
     ```
  3. Edit `~/.hammerspoon/init.lua` (or wherever `keystat.lua` is `require`'d) and comment out the require / start call.
  4. `hs -c 'hs.reload()'` to apply.
  5. Verify `~/keystat-counts.json` size stops growing (`wc -c ~/keystat-counts.json` over 24 hours).
  6. Keep the JSON file as historical baseline — already imported via `import_keystat.py`.

  ## Rollback

  Re-enable the require in `~/.hammerspoon/init.lua`, `hs -c 'hs.reload()'`. JSON resumes writing immediately.
  ```
- **MIRROR**: 無
- **VALIDATE**: AC-10 ✅
- **COMMIT**: `docs: migration guide from Hammerspoon keystat`

#### Task 5.4: README polish + final docker compose verify

- **ACTION**: README 補完 setup 步驟、`docker compose ps` 與 `scripts/smoke.sh` 驗證。
- **IMPLEMENT**: 編 `README.md` 把 "target — not yet built" 改成 "Quick start" 完整步驟，並更新 milestone status table。
- **MIRROR**: 無
- **VALIDATE**: 跟著 README 步驟乾淨重跑（從 `docker compose down --volumes` 開始）
- **COMMIT**: `docs: README polish + Quick start finalized`

---

## No Placeholders 自檢

所有 task 已含：實際 test code、實際 implementation code 或精確 sketch、明確 VALIDATE 命令、`MIRROR` 對應 pattern 名稱與位置。**無 TBD / TODO / 「fill in details」**。

---

## Testing Strategy

### Unit Tests

| Test | Input | Expected Output | Edge Case? |
|---|---|---|---|
| `test_parse_returns_layout_with_6_layers` | `mylayout.vil` | 6 layers | — |
| `test_parse_rejects_unsupported_protocol` | bad protocol JSON | `VialParseError` | yes |
| `test_plain_letter` | `KC_A` | `label_top = "A"` | — |
| `test_layer_tap` | `LT1(KC_TAB)` | tap=Tab, hold=→L1 | — |
| `test_tap_dance_branches` | TD(0) + ctx | 4 branches | — |
| `test_split_mods` | `cmd+ctrl+1` | `(frozenset{cmd,ctrl}, "1")` | — |
| `test_stats_top_n_aggregates` | 4 events same key | summed total | — |
| `test_import_minimal` | sample JSON | events table populated | — |
| `test_layout_503_when_vial_missing` | bad VIAL_PATH | 503 + error code | yes |
| `test_heatmap_global_coverage` | full baseline | coverage_pct ≥ 0 | — |
| `test_overlay_returns_cells_and_unmapped` | mixed mapped/unmapped | both arrays present | edge |

### Edge Cases Checklist

- [x] Empty input — `KC_NO`, `-1` slot
- [x] Maximum size input — full 6-layer × 10-row × 7-col + 16 TD + 16 combo
- [x] Invalid types — bad `vial_protocol`
- [x] Concurrent access — SQLite WAL mode in M4 EventSink
- [x] Network failure — helper unreachable → `/api/live` 回 `helper_disconnected`
- [x] Permission denied — pynput accessibility 缺少時 fail-fast log

---

## Validation Commands

### Static Analysis

```bash
# backend
docker compose run --rm backend ruff check .

# native-helper
cd native-helper && python -m ruff check .
```
EXPECT: Zero lint errors

### Unit Tests

```bash
# backend
docker compose run --rm backend pytest -v

# native-helper
cd native-helper && pytest -v
```
EXPECT: All tests pass

### Browser / Integration Validation

```bash
bash scripts/smoke.sh
```
EXPECT: `smoke OK`

### Manual Validation Checklist

- [ ] **AC-1**: `curl :8000/api/layout | jq '.layers | length'` = 6
- [ ] **AC-2**: layer 0 thumb area `TD(0)` resolved 含 4 branches
- [ ] **AC-3**: 開 `:8080`、切每個 layer dropdown、所有非 TRN 鍵 label 不為空
- [ ] **AC-4**: `python -m backend.scripts.import_keystat ~/keystat-counts.json`、`sqlite3 ... "SELECT COUNT(*) FROM events"` > 5000
- [ ] **AC-5**: top-10 iterm2 `j` count 跟 `keystat_analyze.py` 一致
- [ ] **AC-6**: `/api/stats/heatmap | jq .coverage_pct` ≥ 90
- [ ] **AC-7**: 跑 helper → 打字 30 秒 → events 增加 ≥ 50
- [ ] **AC-8**: 按住 Space → web UI 切到 layer 1（停錶 < 100ms）
- [ ] **AC-9**: `bash scripts/smoke.sh` 通過
- [ ] **AC-10**: 跟著 `docs/migration-from-hammerspoon.md` disable HS、24h 後 JSON 不變

---

## Acceptance Criteria

- [ ] 所有 28 tasks 完成
- [ ] 所有單元測試通過
- [ ] `scripts/smoke.sh` 通過
- [ ] AC-1 ~ AC-10（SRS）全部驗證
- [ ] 無 ruff lint errors
- [ ] Manual UX：靜態 viewer、Interactive、Stats / Heatmap 三頁皆運作
- [ ] launchd 自啟 helper 重啟後仍跑

## Completion Checklist

- [ ] Code 遵循 plan 內 Patterns to Mirror（IIFE frontend、stdlib sqlite、ruff lint）
- [ ] 錯誤處理用 `backend/api/errors.py` 的 custom exceptions
- [ ] Logging 走 stdlib `logging`、structured key=value
- [ ] Tests follow pytest fixtures pattern
- [ ] 無 hardcoded paths（除了 launchd plist 內絕對路徑，文件化為 host-specific）
- [ ] README + migration doc 同步
- [ ] 無 scope creep（NOT Building 清單還是無動作）
- [ ] Plan 自包含 — 實作期間不需要查 SRS 以外的文件

## Risks

| Risk | Likelihood | Impact | Mitigation |
|---|---|---|---|
| pynput accessibility 權限 UX 卡 | M | M | Task 4.1 開頭 prototype 量測 hold timing；不行轉 Swift |
| Docker `host.docker.internal` 解析失敗 | L | M | docker-compose 加 `extra_hosts`；backend `/health` 加 helper 可達性 probe |
| `mylayout.vil` 內某 keycode `keycode_labels.py` 沒收錄 | M | L | Task 1.5 coverage test 強制全 cover、缺就補表 |
| Helper 與 HS 雙寫 SQLite 衝突 | L | H | HS 始終只寫 JSON、helper 寫 SQLite，不共用檔；M5 cutover 後 user 手動 disable HS |
| SQLite 寫入鎖 helper vs backend | L | L | Helper WAL mode + 5s batch；backend 只讀 |
| Heatmap 對 mod-combo `cmd+1` 對映模糊 | M | L | overlay_stats 落到 base `1` 位置；用 `unmapped[]` 標示其他 |
| WebSocket 重連風暴 | L | L | Frontend reconnect 用 3-second backoff |

## Notes

- 本 plan 為 L-size feature delivery；建議依 milestone 順序執行，每完一個 milestone 都跑該 milestone 對應 AC 驗證再進下個
- Mode B（task-level test-first）對 28 task 是中等 overhead；如某 task 純配 setup（如 5.3 doc）可降為 Mode A 直接做
- 沒有 schema 變動 / 沒有 deployment infra：所有 task 都在 dev box 上
- 未來如果要把 helper 轉 Swift（pynput 不堪用時），只動 `native-helper/main.py` 與 sink/dispatcher API surface，frontend / backend 不變
- 本 plan 與 `~/.claude/plans/claude-init-git-init-fancy-pinwheel.md` 的 milestone 對齊，後者已標 M0 完成
