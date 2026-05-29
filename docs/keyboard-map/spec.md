# Keyboard Layout Spec

> 為 58-key 4-row Corne-class 分體鍵盤（**YMDK Borne**：Corne 4×6 layout + 2 旋鈕）量身設計的 vim/tmux 取向 layout。
> 起草於 2026-05-28，將在這個檔案上持續迭代。
> 相關深度研究：`~/Documents/Corne_Vim_Tmux_Layouts_Research_20260527/`

## ⚠️ 重要：v0.2 設計文件同步

**v0.2 完整設計文件存在 Obsidian vault，不在本 repo 內。** 任何要改 layout 的工作開始前，**必須先讀取**：

```
~/Projects/Obsidian/Obsidian/MainRepo/500 Programing/IDE、終端機、檔案總管/鍵盤 Layout v0.2 — NAV + MEDIA + Obsidian 全鍵盤化.md
```

該文件包含：
- v0.2 完整 5 層架構（BASE / NAV / MEDIA / FN / ADJ，已砍 SYM）
- 每層左右側獨立鍵位圖（防 Obsidian 跑版）
- Inner Column 4 顆完整分配（Q+A 行，Z 行無 inner）
- 與既有 `mylayout.vil` 的 diff 表
- Obsidian 全鍵盤化的 vimrc 補完清單

**雙向同步原則**：
- 本 `spec.md` 改任何決策 → 同步更新 Obsidian 文件
- Obsidian 文件改任何決策 → 同步更新 `spec.md`
- `mylayout.vil` 由 user 自己在 Vial GUI 編輯，不由 Claude 動

---

## 1. 硬體規格

| 項目 | 規格 |
|---|---|
| 鍵數 | **58 鍵**（單邊 29 鍵 × 2） |
| 列數 | **4 row**（最上面一列是**實體數字鍵**） |
| 字母欄數 | **6 主欄 + 2 inner column**（index finger 內側） |
| Thumb cluster | **單邊 3 thumb keys**，共 6 顆 |
| 等價拓撲 | 接近「4-row Corne 變體 + inner column」；視覺上與 Lily58/Sofle 的 4-row 規格相似（但 thumb 數量為 3 而非 4） |

**硬體優勢**（相對標準 3-row 42-key Corne）：
- 多 12 顆實體數字鍵 → 不需要 number layer
- 多 4 顆 inner column 鍵（每邊 2 顆）→ 可放 vim 高頻符號 / leader / hyper
- 合計多 16 顆鍵可用

---

## 2. 使用情境（必須優先支援的工作流）

| 排序 | 工作流 | 高頻按鍵 |
|---|---|---|
| **P0** | **vim** / neovim | Esc、hjkl、`:`、`;`、`/`、`[ ]`、`{ }`、`( )`、`<` `>`、leader key、Ctrl-w / Ctrl-d / Ctrl-u / Ctrl-r |
| **P0** | **tmux** | Ctrl-prefix（`Ctrl-b` 或 `Ctrl-a`）+ letter（c / n / p / d / `%` / `"` / 數字） |
| **P1** | shell / zsh | Ctrl-c / Ctrl-z / Ctrl-r / Ctrl-l / Ctrl-w / Tab、`|` |
| **P1** | git CLI | 平常輸入 + git alias |
| **P2** | 一般打字（中英文混用，base 仍為 QWERTY） | 字母 + 標點 |
| **P2** | macOS 系統熱鍵 | Cmd-C/V/X/A/Z（不在 layout 設計範圍，但不能被破壞） |

**Base layer = QWERTY**（不換 Colemak/Dvorak）。

---

## 3. 編輯器與韌體

- **使用編輯器**：**Vial**（GUI、即改即用、不用編譯）
- **底層韌體**：vial-qmk（Vial 是 QMK 的 fork）
- **不使用**：原生 QMK 編譯流程、ZMK
- **韌體前置需求**：keyboard 必須先 flash Vial-enabled firmware；後續所有 keymap 設計都在 Vial GUI 操作

### Vial 可用功能（已驗證可用於本設計）
- 多層（看 firmware 配置，通常 8 層以上）
- Mod-Tap（`MT(mod, kc)`）
- Layer-Tap（`LT(layer, kc)`）
- One-Shot Mod（`OSM(mod)`）
- One-Shot Layer（`OSL(layer)`）
- Combos（J+K → Esc 等）
- Tap Dance（`;` tap = `;`、double-tap = `:`）
- Key Override
- Macros
- QMK Settings 調 timing（TAPPING_TERM、PERMISSIVE_HOLD、CHORDAL_HOLD、QUICK_TAP_TERM）

### Vial 不能或要繞道的功能
- **Callum-style「整層 oneshot」**：Vial 沒有原生「整個 layer 上全部 OSM」的概念，要用 `OSL + OSM` 組合模擬
- **Achordion**（已被 Chordal Hold 取代，視 firmware 版本而定）
- 進階自訂 C macro（要改 vial-qmk 源碼重編）

---

## 4. 已 commit 的設計原則

來源：基於 deep-research 報告的跨派系 9 條共識 + 對 vim/tmux 情境的特化。

1. **強指承擔高頻**——Space / Enter / Backspace 不放 pinky，放 thumb
2. **layer 按用途正交切分**——sym / nav / fn 不混層
3. **layer 用 hold 而非 toggle**——避免和 vim modal 衝突
4. **opposite-hand layer activation**——layer key 在對側拇指，避免 race condition（Miryoku 原則）
5. **mod-tap 是 vim/tmux 的脆弱點**——預設啟用 Chordal Hold；不行就走 one-shot mods
6. **symbol bigram 用 inward roll**——`!=`、`<=`、`->` 在 home row 上向內滾（Getreuer）
7. **F-key 對齊數字列**——位置 1=F1、2=F2 同構好記
8. **不要在同一 thumb 上堆超過 2 個功能**——拇指強但不無敵（Getreuer thumb-ergo 警告）
9. **base layer 動最少**——維持 QWERTY，改的是 layer 結構與 modifier 策略

---

## 5. 已決定的具體配置

### 5.1 Layer 結構（5 層）

| Layer | 名稱 | 觸發 | 用途 |
|---|---|---|---|
| 0 | **BASE** | 預設 | QWERTY + 實體數字列 + 基本符號 |
| 1 | **NAV** | hold 左拇指中央（暫定 Space） | 方向鍵（hjkl 對應）、Home/End/PgUp/PgDn、word jump、tmux/vim 快捷 |
| 2 | **SYM** | hold 右拇指中央（暫定 Bksp 或 Enter） | 程式符號 + 括號對 + 比較運算子（inward rolls） |
| 3 | **FN** | hold 第三 thumb 或同按組合 | F1–F12（對齊數字列）+ media + 系統熱鍵 |
| 4 | **ADJ** | 同按兩個 layer key | layer-lock / reset / RGB / 罕用 |

**砍掉 NUM layer**——你有實體數字列，不需要。

### 5.2 Esc 設計

**Caps Lock 位置設為「tap = Esc / hold = Hyper」**
- Vial 操作：選 Caps 鍵 → Quantum 分頁 → `ALL_T (kc)`（第 4 列最右）→ 對話框選 `KC_ESC`
- 對應 QMK 寫法：`ALL_T(KC_ESC)` 也寫作 `HYPR_T(KC_ESC)`
- Hyper = Ctrl + Shift + Alt + GUI 四個 modifier 同時送
- **P0 用途：視窗管理第二入口**（與既有 `cmd+1~5` 並存）— Hammerspoon 把 Hyper+N 雙綁到 cmd+N 的同一函式，或用 Karabiner manipulator 轉發 `Hyper+key → cmd+key`。**這條導致 §8.0 那條「WezTerm Cmd→Alt 全面戒命令鍵」被否決**：cmd+1 是 1529 次/8 天的冠軍 mod-combo，保留既有 muscle memory；Hyper 是平行新入口，不取代 cmd

**加裝 J+K combo → Esc**（向 markstos 借的設計）
- Vial 操作：Combos 分頁 → 新增 → 兩鍵選 `KC_J` 和 `KC_K` → 動作選 `KC_ESC`
- 用途：在 normal mode 內快速回 Esc，不必移到 Caps Lock；雙保險

### 5.3 hjkl 處理

- **Base layer hjkl 不動**（QWERTY 原位）——vim 自己會把 h 解釋成左移
- **NAV layer 同位置改為方向鍵**：H→Left、J→Down、K→Up、L→Right
- NAV layer **預設 hold-to-activate**，**不全域 toggle**（避免和 vim modal 衝突）
- **但 NAV 內保留一顆 `QK_LLCK`（Layer Lock）**，給長時間 PTT / 瀏覽器導覽用：先 hold 進 NAV → 點 lock → 鬆 hold → NAV 持續生效，**完全零 hold 單手操作**；再點 lock 解鎖。`QK_LLCK` 只在 NAV 內生效，BASE 同位仍是字母 — 不會誤觸。詳見 Obsidian 文件 §3 三段入口設計

### 5.4 thumb cluster 暫定（**未定，需迭代**）

| 位置 | 暫定鍵 | 備註 |
|---|---|---|
| 左外（最遠） | Esc / OSM Shift | 較少用 |
| 左中 | **`LT(NAV, KC_SPC)`**（tap=Space / hold=NAV） | 高頻 Space + NAV 切換 |
| 左內（最近） | Tab / OSM Ctrl / FN layer | 待定 |
| 右內（最近） | **`LT(SYM, KC_ENT)`**（tap=Enter / hold=SYM） | 高頻 Enter + SYM 切換 |
| 右中 | **`LT(FN, KC_BSPC)`** 或單獨 Bksp | 待定 |
| 右外 | Delete / OSM Shift | 較少用 |

**已決定**：Space 與 Enter 各自帶一個 layer-tap，分別在對側手；NAV 在左、SYM 在右。
**未決定**：另外 4 顆（左外、左內、右中、右外）的具體分配。

### 5.5 Inner column 4 顆（**未定**）

候選方案：

| 方案 | 左 inner col 2 顆 | 右 inner col 2 顆 |
|---|---|---|
| A: 括號優先 | Tab / Esc | `[` / `]` |
| B: leader 優先 | Tab / **Leader** | **Hyper** / `]` |
| C: 全 hyper 派 | Tab / `Hyper(KC_NO)` | `Hyper(KC_NO)` / `]` |

**傾向方案 B**——leader + hyper 給 Karabiner / Hammerspoon 接全域熱鍵用，跟 tmux/vim 既有 modifier 不衝突。

### 5.6 Modifier 策略

**三條路線、最終要二選一**：

| 路線 | 做法 | 何時用 | 風險 |
|---|---|---|---|
| **保守路線** | 所有 modifier 在外側 pinky 直行 / thumb；不用 HRM | 第一週 flash 就能用 | 沒風險，但 modifier 觸達較遠 |
| **中間路線**（**目前傾向**） | HRM GACS + **Chordal Hold** 開啟 + Ctrl 不放 home row（移到 thumb 或外側） | flash 2–4 週後可試 | tmux Ctrl-prefix 仍有低機率 timing 誤觸 |
| **激進路線** | 完整 HRM GACS + Chordal Hold + 細調 per-key tapping term | 中間路線穩定後 | 學習曲線長 |
| **救援路線** | 完全捨棄 HRM，改 Callum-style oneshot（在 Vial 用 OSL + OSM 組合） | 中間/激進路線失敗時 | 多一次擊鍵，但永遠不誤觸 |

**第一版採保守路線**——快速可用，下一輪迭代再進中間路線。

### 5.7 timing settings（QMK Settings 面板）

| 參數 | 第一版設定 | 備註 |
|---|---|---|
| `TAPPING_TERM` | 200ms | 第一週後可往 180 / 220 微調 |
| `PERMISSIVE_HOLD` | **on** | fast typist 友善 |
| `HOLD_ON_OTHER_KEY_PRESS` | **off** | 對 HRM 必須 off，否則 typing roll 誤觸 |
| `CHORDAL_HOLD` | **on**（若 firmware 支援） | QMK 2025-02 內建；如沒這選項表示你的 vial-qmk fork 太舊 |
| `QUICK_TAP_TERM` | 120ms | 連按 letter 時避免誤判 hold |

---

## 6. 待決定的事項（下次討論的議題）

1. **thumb cluster 另外 4 顆**的具體分配（5.4 表中標「待定」的部分）
2. **inner column** 選 A / B / C（5.5）
3. **modifier 策略**第一版要不要直接跳中間路線（5.6）
4. **第 6 欄字母列**：你硬體比 Miryoku 派多一欄字母，這欄左右要放什麼？選項：(a) 維持 QWERTY 的 `B` / `Y` 在這欄，(b) 用作 inner-column 進階符號
5. **數字列上的 shift 字符**：`!@#$%^&*()` 該保留 shift-modified 還是放到 SYM layer 的 home row？
6. **leader key 觸發後的二級序列**：要不要設計一套 vim-style leader 序列（`<leader>t` 開 tmux session、`<leader>f` 開 file 等）？這跟 Vial 的 Macros + Combos 怎麼搭？
7. **OS-specific 鍵的處理**：Cmd (Gui) 在 layout 上要放哪？是否要保留方便用 macOS 系統熱鍵？
8. **media / mouse layer 是否需要**：對 vim/tmux 工作流而言這層 ROI 低，但 Vial 有 mouse layer 模板

---

## 7. 已排除的方案與原因

| 排除方案 | 原因 |
|---|---|
| **fork markstos 的 keymap.c 直接用** | markstos 是 36-key minimalist，跟 58-key 差太多；用其設計理念但不用 keymap |
| **fork justinmklam 的 layout 直接用** | 標準 42-key Corne，少 16 顆；用其 layer 結構（4-layer）為骨架但要擴成 5 層 |
| **直接套用「Miryoku-with-pinky-modifier」圖** | 設計理念契合，但拓撲不符（其修飾鍵在 outer pinky 直行，你的硬體沒這直行） |
| **NUM layer** | 你有實體數字列，重複設計 |
| **Colemak / Dvorak base** | 學習曲線 + 既有 vim 肌肉記憶成本太高 |
| **完整 Callum oneshot 第一版** | Vial 不直接支援整層 oneshot，要繞道；保留為救援路線 |
| **mod-tap 不開 Chordal Hold** | tmux Ctrl-prefix 工作流會持續誤觸（已在 deep-research Finding 4 驗證） |

---

## 8. 參考資料

### 8.0 本機 Hotkey 使用實測報告 ⭐
- **[hotkey-analysis.md](./hotkey-analysis.md)** — 基於 `~/keystat-counts.json`（8 天、137k 擊鍵）+ `keystat_analyze.py` + MyConfig 各設定檔交叉比對的實測報告。**這是把猜測換成事實的關鍵文件。**
  - 涵蓋：整體統計、Top 鍵位排行、各 app（WezTerm / tmux / vim / Hammerspoon / Browser-BBS）工作流分析、給 layout 設計的具體訊號、跟 spec 已決事項的驗證對照
  - **要點**：
    - Space 佔 20.17%、Backspace 5.15%、hjkl 合計 ~10%（合計絕對不能動 base 位置）
    - tmux prefix Ctrl-Space 8 天 224 次（唯一頻繁的 Ctrl-combo）
    - Hammerspoon `mash`（Cmd+Ctrl）8 天 179 次——可以全部平移到 Hyper
    - WezTerm 的 Cmd 綁定 8 天 ~1,200 次（cmd+1 1529 為主）——可以全改 Alt 安全戒掉
    - macOS 系統 Cmd+C/V/A/Z 8 天 ~1,100 次——不建議戒
  - **新增建議**（已可直接放進 spec 的決策）：
    1. `;` 用 Tap Dance（tap=`;` / 雙 tap=`:`）
    2. NAV layer 必須含 PageUp/PageDown（BBS 工作流）
    3. ~~WezTerm Cmd 綁定全改 Alt~~ — **已否決**（2026-05-28）：`cmd+1` 是 1529 次/8 天的冠軍 mod-combo，戒掉 muscle memory 成本太高；改採「cmd+1 保留 + Hyper 並存」雙入口策略，見 §5.2
    4. Hammerspoon mash 平移到真 Hyper（Caps Lock ALL_T 一條鞭）— **保留**且升等 P0

### 8.1 主研究報告
- `~/Documents/Corne_Vim_Tmux_Layouts_Research_20260527/report.md` — 8 個 finding + synthesis + recommendations
- `~/Documents/Corne_Vim_Tmux_Layouts_Research_20260527/followups.md` — markstos vs justinmklam 比較

### 8.2 起手值得借鏡的 keymap repo
- [rafaelromao/keyboards](https://github.com/rafaelromao/keyboards) — ZMK、明確 vim 取向、用 ZMK Leader Key module
- [precompute/keyboard-keymap-QMK](https://github.com/precompute/keyboard-keymap-QMK) — QMK、有獨立 vim layer、Colemak Mod-DH（Colemak 派參考）
- [Elil50/crkbd_QMK](https://github.com/Elil50/crkbd_QMK) — 4-row Corne V3/V4 完整 9-layer
- [PiXeL16/Lily58_PiXeL16](https://github.com/PiXeL16/Lily58_PiXeL16) — Lily58 模組化標竿
- [niqodea/crkbd](https://github.com/niqodea/crkbd) — 顯式 vim mnemonics

### 8.3 設計理念來源（必讀）
- [Miryoku — Manna Harbour](https://github.com/manna-harbour/miryoku) — orthogonal layer 概念
- [Designing a Symbol Layer — Pascal Getreuer](https://getreuer.info/posts/keyboards/symbol-layer/index.html) — bigram-driven 符號擺位
- [Achordion / Chordal Hold — Getreuer](https://getreuer.info/posts/keyboards/achordion/index.html) — mod-tap 救星
- [Thumb Keys — Matt Gemmell](https://mattgemmell.scot/thumb-keys/) — thumb cluster 強指原則
- [How to Vim: Proper Ways to Escape — Batsov](https://batsov.com/articles/2025/06/03/how-to-vim-proper-ways-to-escape/) — Esc 設計
- [Combo mods — jasoncarloscox](https://jasoncarloscox.com/writing/combo-mods/) — 放棄 HRM 後的替代方案

### 8.4 Vial 操作參考
- Vial 官網：https://get.vial.today/
- Vial 文件：https://get.vial.today/docs/
- vial-qmk firmware repo：https://github.com/vial-kb/vial-qmk

---

## 9. Roadmap

| 階段 | 內容 | 預期時間 |
|---|---|---|
| **v0.1**（draft） | 完成本 spec | 已完成 |
| **v0.2**（first keymap） | 把 5.1–5.7 全部 commit 完成，產出第一版 keymap 視覺圖 + Vial 設定步驟 | 下次討論 |
| **v0.3**（flash & 試用） | flash 到鍵盤、用 1 週 | flash 後 +1 週 |
| **v0.4**（迭代 1） | 根據手感調整 thumb / inner column / timing | +2 週 |
| **v0.5**（modifier 升級） | 從保守路線升中間路線（加 HRM + Chordal Hold） | +1 月 |
| **v1.0**（穩定） | 不再大改、進入 micro-tuning | +2 月 |

---

## 10. 變更紀錄

| 日期 | 版本 | 內容 |
|---|---|---|
| 2026-05-28 | v0.1 | 初版：硬體規格、5 層結構、Caps→Esc/Hyper、J+K combo Esc、第一版 timing 設定 |
| 2026-05-28 | v0.1.1 | 加入 hotkey-analysis.md 引用（§8.0），補入 4 條資料驅動的建議決策（Tap Dance `:`、NAV 含 PgUp/PgDn、WezTerm Cmd→Alt、mash→Hyper） |
| 2026-05-28 | v0.1.2 | NAV 加 `QK_LLCK` 鎖層做零 hold 單手操作（§5.3）；確認 Hyper P0 視窗管理用途（§5.2）；否決「WezTerm Cmd→Alt」、保留 cmd+1~5（§8.0） |
