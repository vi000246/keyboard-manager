# Hotkey 使用分析報告

> 來源：`~/keystat-counts.json` + `keystat_analyze.py` + MyConfig 各設定檔交叉比對。
> 起草於 2026-05-28，資料窗口：**2026-05-20 → 2026-05-28（8 天）**。
> 用途：把實際打字數據翻成 keyboard layout 設計訊號，把猜測換成事實。

---

## 0. TL;DR — 給 layout 設計的 9 個結論

1. **Space 必須在最強指**——20.17% 的擊鍵都是 Space，相當於每打 5 鍵就有 1 顆 Space。**已 commit 給左 thumb 中央 `LT(NAV, Space)` 是對的。**
2. **Backspace（delete）排第 2（5.15%）**——確認放右 thumb 是對的，不要還留在右 pinky 角落。
3. **Cmd 是你最頻繁的 modifier（2627 次，佔 mod-combo 49%）**——比 Ctrl(643) + Shift(1432) 還多。**如果你要「戒 Command」，請先決定要不要保留 macOS 系統熱鍵這層**（Cmd+C/V/X/A/Z 等）。
4. **`cmd+1` 是冠軍 mod-combo（1529 次，28.49%）**——這是你 Hammerspoon 的 `mash+1`（左上窗格 snap）。**Hammerspoon 工作流是你 cmd+ctrl 用得這麼重的根源。**
5. **Hjkl 在 base layer 已經有大量純按用量**（j 5892 / l 3787 / h 1946 / k 2314）——**hjkl 不能移走 base 位置**（這驗證 Finding 3.2 的決定）。
6. **Ctrl+hjkl 才是 tmux/vim navigator 的真實用量**（總計 56 次/8 天，**比想像中少**）。**這暗示 Ctrl 不一定要在 home row**——tmux pane 切換並不是真的高頻到非得手指不離家。
7. **Shift+letter（capitals）在 vim 模式佔大量**（shift+t / shift+; / shift+a 各 50+ 次）——**Shift 在 thumb 比在 pinky 好**，可以連發大寫指令不卡。
8. **方向鍵的單按頻率不算低**（right 2785 / down 1650 / up 955 / left 852）——主要在瀏覽器（BBS 操作習慣帶來）；**NAV layer 的 hjkl→方向鍵設計必要**。
9. **Esc 單按 617 次 + jj 也常用**（vim insert→normal）——**Caps→Esc/Hyper 設計 +  J+K combo 雙保險，得到驗證**。

---

## 1. 整體統計

| 指標 | 數值 |
|---|---|
| 時間窗口 | 2026-05-20T06:10 → 2026-05-28T00:38（**8 天**） |
| 紀錄 app 數 | 42 個 |
| 不重複單鍵 | 81 個 |
| 不重複 mod-combo | 167 個 |
| **總擊鍵數** | **137,087**（每天平均約 17,000） |
| 純單鍵 | 131,720（96.1%） |
| Mod-combo | 5,367（3.9%） |

**讀法**：你**絕大多數時間是在打字（單鍵），用 modifier 的時間只有 4%**——這對 layout 設計的意涵是：**modifier 觸達效率 < base layer 觸達效率重要 5 倍**。換句話說，**不要為了 home row mods 犧牲打字準確度**。

### 1.1 各 app bucket 擊鍵量

| Bucket | 擊鍵數 | 佔比 | 主要 app |
|---|---|---|---|
| **terminal** | **92,324** | **70%** | iTerm2 / WezTerm / Warp（tmux + vim 主場） |
| **browser** | 28,179 | 20% | Brave / Firefox / qutebrowser |
| **editor**（GUI） | < 5,000 | 4% | MacVim / Obsidian / Notion |
| **chat** | 2,832 | 2% | LINE / iMessage / Mail |
| **launcher** | 77 | <0.1% | Raycast / Hammerspoon prompt |

**啟示**：你 **70% 的擊鍵在終端機**——這份 layout 必須**徹底為終端機優化**，瀏覽器排第二，GUI editor 反而不是優先（你的 vim 主要在終端機跑）。

---

## 2. Top 鍵位排行

### 2.1 純單鍵 Top 20（與 layout 直接相關）

| Rank | Count | % | Key | 為什麼這麼多 |
|---|---|---|---|---|
| 1 | **26,570** | **20.17%** | **Space** | 打字最頻繁的鍵；tmux prefix 是 Ctrl-Space 也算（但被算進 mod-combo） |
| 2 | 6,783 | 5.15% | **delete** (Backspace) | 改錯字、vim normal 的 X |
| 3 | 5,892 | 4.47% | **j** | vim 下移；對話/編輯打字 |
| 4 | 5,410 | 4.11% | i | vim 進 insert mode + 一般字母 |
| 5 | 4,949 | 3.76% | o | vim 開新行 + 一般字母 |
| 6 | 4,948 | 3.76% | n | vim 跳下一個搜尋 + 一般字母 |
| 7 | 4,222 | 3.21% | e | vim word end + 字母 |
| 8 | 4,184 | 3.18% | d | vim delete + 字母 |
| 9 | 4,166 | 3.16% | a | vim insert after + 字母 |
| 10 | 3,787 | 2.88% | l | vim 右移 + 字母 |
| 11 | 3,702 | 2.81% | p | vim paste + 字母 |
| 12 | 3,583 | 2.72% | **return** (Enter) | 換行；BBS 進入 |
| 13 | 3,337 | 2.53% | r | vim replace + 字母 |
| 14 | 2,982 | 2.26% | x | vim 刪字元 |
| 15 | 2,936 | 2.23% | t | vim till + 字母 |
| 16 | **2,785** | **2.11%** | **right (→)** | BBS / 瀏覽器主要導覽鍵 |
| 17 | 2,738 | 2.08% | f | vim find + 字母 |
| 18 | 2,627 | 1.99% | c | vim change + 字母 |
| 19 | 2,595 | 1.97% | u | vim undo + 字母 |
| 20 | 2,565 | 1.95% | b | vim back word + 字母 |

**對 layout 的訊息**：
- **Space + Enter + Backspace 三巨頭佔 28%**——三個都應該在 thumb 或近 thumb 位置
- **j / i / o / e / d / a 是 home row 級高頻**——base layer **絕對不能動這幾顆**
- **right 方向鍵 2,785 次** 是個 surprise——你在瀏覽器/BBS 用方向鍵的量很大；NAV layer 的方向鍵設計很重要

### 2.2 方向 / 編輯鍵單獨統計

| Key | Count | 主要場景 |
|---|---|---|
| right | 2,785 | 瀏覽器/BBS（佔 89%） |
| down | 1,650 | 同上 |
| up | 955 | 同上 |
| pagedown | 895 | BBS 翻頁 |
| left | 852 | 瀏覽器/BBS |
| pageup | 602 | BBS 翻頁 |
| escape | 617 | vim 退出 insert mode（高得驚人，jj 對應的） |
| tab | 118 | 切 split / completion |
| end / home | 145 / 少 | 行末/行首 |

**訊息**：你的方向鍵主要在瀏覽器和 BBS——不是 vim（vim 都用 hjkl）。這表示 NAV layer 必須涵蓋方向鍵但**也必須涵蓋 PageUp/PageDown**，否則 BBS 翻頁會卡。

### 2.3 Mod-combo Top 30

| Rank | Count | % | Combo | 來源（依 config 比對） |
|---|---|---|---|---|
| 1 | **1,529** | **28.49%** | **cmd+1** | Hammerspoon mash+1 = 左上角窗格 snap |
| 2 | 511 | 9.52% | cmd+v | macOS 貼上 |
| 3 | 327 | 6.09% | alt+space | Raycast 主熱鍵 |
| 4 | 272 | 5.07% | cmd+c | macOS 複製 |
| 5 | **224** | **4.17%** | **ctrl+space** | **tmux prefix** ⭐ |
| 6 | 133 | 2.48% | shift+t | vim Top of screen + 一般 |
| 7 | 114 | 2.12% | shift+; | vim `:`（進 command-line） |
| 8 | 102 | 1.90% | cmd+t | 新 tab |
| 9 | 83 | 1.55% | ctrl+f | vim Forward page / 搜尋 |
| 10 | 73 | 1.36% | shift+= | `+` |
| 11 | 73 | 1.36% | shift+a | vim Append end-of-line + 一般 |
| 12 | 67 | 1.25% | shift+s | vim Substitute |
| 13 | 66 | 1.23% | shift+n | vim 反向搜尋 |
| 14 | 62 | 1.16% | cmd+a | 全選 |
| 15 | 60 | 1.12% | shift+i | vim Insert at line start |
| 16 | 58 | 1.08% | shift+r | vim Replace mode |
| 17 | 56 | 1.04% | ctrl+v | vim visual block / 終端機貼上 |
| 18 | 50 | 0.93% | shift+h | vim High of screen / 行首 |
| 19 | 49 | 0.91% | shift+c | vim Change to EOL |
| 20 | 47 | 0.88% | shift+p | vim Paste before |
| 21 | 46 | 0.86% | shift+/ | `?` 反向搜尋 |
| 22 | 44 | 0.82% | shift+b | vim Big word back |
| 23 | 43 | 0.80% | shift+f | vim Find back |
| 24 | **42** | **0.78%** | **ctrl+b** | tmux 舊 prefix（你已改 Ctrl-Space，但有殘留） |
| 25 | 41 | 0.76% | shift+e | vim end Big word |
| 26 | 40 | 0.75% | shift+tab | 反向切換 |
| 27 | 39 | 0.73% | shift+m | vim Middle of screen |
| 28 | 38 | 0.71% | cmd+ctrl+space | window hints (Hammerspoon mash+space) |
| 29 | 34 | 0.63% | ctrl+e | vim 捲下一行 |
| 30 | 34 | 0.63% | ctrl+x | vim insert mode completion / close split |

### 2.4 Modifier 使用分佈（你真正在按住的是哪個 mod）

| Modifier 集合 | 次數 | 佔比 |
|---|---|---|
| **cmd**（單獨） | **2,627** | **49.0%** |
| shift（單獨） | 1,432 | 26.7% |
| ctrl（單獨） | 643 | 12.0% |
| alt（單獨） | 385 | 7.2% |
| cmd+ctrl（Hammerspoon mash） | 179 | 3.3% |
| alt+cmd+ctrl（mashAlt） | 47 | 0.9% |
| 其他組合 | 54 | 1.0% |

**訊息**：
- **Cmd 是你最常按的 modifier**，幾乎一半的 mod-combo 都包含它——主要是 macOS 系統熱鍵 + WezTerm 切 tab/pane + Hammerspoon
- **Shift 第二**——主要是 vim 大寫指令
- **Ctrl 只佔 12%**——比 Shift 還少；這意味著「Ctrl 一定要在 home row」的論點**對你而言力道沒那麼強**
- **cmd+ctrl (Hammerspoon mash) 用量也不少**（179）——這是你的 Hyper 替代品

### 2.5 callout: tmux/vim navigator 真實用量

| 場景 | 鍵 | 次數 |
|---|---|---|
| Ctrl+hjkl（tmux/vim 切 split & pane） | ctrl+k=31, ctrl+h=9, ctrl+j=7, ctrl+l=4 | **51 / 8 天** |
| Cmd+Ctrl+hjkl（Hammerspoon snap） | 19+16+2+2 | **39 / 8 天** |
| Cmd+Ctrl+Alt+hjkl（移螢幕） | 18+14 | **32 / 8 天** |

**訊息**：你的 Ctrl+hjkl 用量**遠低於想像**——平均每天才 6 次，不到打字總量的 0.04%。**這代表「Ctrl 一定要好按」不是死命題**——你可以把 Ctrl 放 thumb，每天多 6 次伸拇指完全可接受。

---

## 3. 各 App 工作流分析

### 3.1 Terminal（70% — 主場）

**主要 app**：WezTerm + iTerm2 + Warp，內跑 tmux + vim/neovim

**頂層 hotkey 環境**（從外層到內層）：
```
WezTerm (Cmd-based) → tmux (Ctrl-Space prefix) → vim (`,` leader + normal mode)
```

**WezTerm 熱鍵設定**（`dot_wezterm.lua` line 40-83）：
- `Cmd+D` / `Cmd+Shift+D` — split horizontal / vertical
- `Cmd+W` — close pane
- `Cmd+方向鍵` — pane navigation
- `Cmd+Shift+方向鍵` — pane resize
- `Cmd+T` — new tab
- `Cmd+Shift+[/]` — prev/next tab
- `Cmd+1~5` — 直接跳 tab N
- `Cmd+Shift+Enter` — zoom pane toggle
- `Ctrl+Space` 在 WezTerm 內被 SendString '\x00'（給 tmux prefix 用）

**tmux 熱鍵設定**（`dot_tmux.conf`）：
- **Prefix = `Ctrl+Space`**（已改，避免和 shell C-a 衝突）
- `Ctrl+h/j/k/l`（**無 prefix**）— vim-tmux-navigator 整合，邊緣自動跨到 tmux pane
- `prefix + r` — reload
- `prefix + |` / `prefix + -` — split
- `prefix + H/J/K/L` (大寫) — resize
- `prefix + Tab` — last pane
- `prefix + X` — kill all other panes
- `Alt+1~5`（**無 prefix**）— 切 window
- `prefix + j/k` — prev/next window
- `prefix + v` — copy-mode
- copy-mode 內：vim 鍵位 (`hjkl`, `w/b/e`, `H/L`, `gg/G`, `f/F`, `/`, `n/N`)
- `prefix + ,` — easy-motion 入口（對齊 vim leader）
  - `prefix + ,m` — 1-char 雙向跳
  - `prefix + ,s` — 2-char 雙向跳 ⭐
  - `prefix + ,w` — word 開頭跳
  - `prefix + ,h` — 跳行首

**vim 熱鍵**（`dot_vimrc`）：
- Leader = `,`
- 大量 `,X` 序列（,gf / ,gb / ,gt / ,lf / ,mp 等）
- `jj` 退出 insert mode
- `H/L` 行首/行尾
- `J/K` 切換 buffer（注意：大寫 J/K，會和插入內容衝突）
- `Ctrl-h/j/k/l` 透過 vim-tmux-navigator 跨 split + tmux pane
- `gn`/`gN` 找游標當前字
- `gc` 註解
- `,mp` markdown preview toggle

**對 layout 的訊息**：
1. **tmux prefix Ctrl-Space 是你最頻繁的真實 mod-combo（除去 Hammerspoon 的 cmd+1）**——Ctrl 必須**可靠、無誤觸**。home row mods 在這上面失敗就完蛋。
2. **`,` 是 vim + tmux 共用 leader**——必須在 base layer，且要好按。它是排名 22 的單鍵（2,340 次/8 天）。
3. **vim 的 `:` (shift+;) 113 次** + `?` (shift+/) 46 次 + `*` (shift+8) 等——SYM layer 設計時注意 shift+數字的可達性。
4. **vim normal-mode capitals（shift+T/A/S/N/I/R/H/C/P/F/E/M/G/D/U/B/L/J/K/V/Y/X/O）總計約 800 次**——Shift 必須容易連發。

### 3.2 Browser（20%）

**主要 app**：Brave / Firefox / qutebrowser

**主要 hotkey 模式**：
- 方向鍵（right 2497、down 541、up 489、left 472）— **這部分是 BBS-style 操作**：右鍵=進入、左鍵=返回上一層
- PageDown/PageUp（838/265）— 翻頁
- `Cmd+1`（295）— Hammerspoon 接到的 snap
- `Cmd+C/V/T/A` — 標準系統熱鍵
- `Alt+Space`（132）— Raycast
- `Cmd+T`（96）— 新 tab
- `Ctrl+F`（53）— 頁內搜尋
- `Shift+;` `Shift+H`（在 qutebrowser 內是 vim-style）

**Browser-leaning（瀏覽器明顯比終端機多）的鍵**：
```
right (2497) > pagedown (838) > up (489) > left (472)
> down (541) > pageup (265) > f19 (390) > cmd+c (216)
> cmd+v (215) > end (137) > 0 (127)
```

**對 layout 的訊息**：
1. **方向鍵和 PgUp/PgDn 是瀏覽器 + BBS 的命脈**——NAV layer 必須把這 6 顆鍵設成 home row 級易達
2. **`Cmd+C` / `Cmd+V` / `Cmd+A` 不可動**——這些是 macOS 系統熱鍵，layout 不能干擾
3. **`Alt+Space`（Raycast）不可動**——你開 app/搜尋的入口
4. **`f19` 出現 1201 次**——這是 Karabiner 把某顆鍵 remap 出來的（可能是切換輸入法的中間鍵），不在 layout 範圍

### 3.3 Vim / GUI Editor（MacVim 1,567 次，少）

**注意**：你的 MacVim 用量很少（1,567 次/8 天）——絕大部分 vim 工作在終端機（被計入 terminal bucket）。

**MacVim 內 top 鍵**：
```
j (321) > , (143) > space (103) > escape (57) > return (56) > k (52)
> delete (49) > n (41) > o (41) > f19 (40)
```

**Leader (`,`) 在 MacVim 佔 9.13%**——遠高於其他 app（Obsidian 1.19%、qutebrowser 0%）。確認 `,` 是 vim 真正的入口鍵。

### 3.4 Hammerspoon（cmd+ctrl 系列）

**`mash = {cmd, ctrl}`** 與 **`mashAlt = {cmd, ctrl, alt}`** 是你的 Hyper 替代品。

| 熱鍵 | 動作 | 用量（8 天） |
|---|---|---|
| `mash+space` | window hints | 38 |
| `mash+escape` | focus pop previous | 23（推估） |
| `mash+g` | layout picker | 17 |
| `mash+t` | terminal picker | 16 |
| `mash+y` | （未看到） | — |
| `mash+h` | snap 左半 | 19 |
| `mash+l` | snap 右半 | 16 |
| `mash+k` | snap 上半 | 2 |
| `mash+j` | snap 下半 | 2 |
| `mash+f` | toggle maximize | 30（推估） |
| `mash+1~4` | 四象限 snap | 0（但 cmd+1 達 1529 — 主要是這個 alias） |
| `mashAlt+h/l` | 移到上/下螢幕 | 18 / 14 |

**訊息**：`mash`（Cmd+Ctrl）是你「Hyper-like」的真正使用者。**這意味著你已經在用一種準 Hyper key 模式**——只是用 Cmd+Ctrl 而不是真正的 Hyper。在 keyboard layout 上，**把 Caps Lock 設成「tap=Esc / hold=Hyper」之後，Hammerspoon 的 mash bindings 可以直接平移成 Hyper bindings**，省一個指頭。

### 3.5 BBS（推斷）

從你的瀏覽器擊鍵特徵（方向鍵 + Space + Return + PgUp/PgDn 佔極大比例），可以推斷你**在瀏覽器用 PCMan 之類的 BBS 連線**（不太可能用獨立 BBS client，因為 keystat 沒抓到 BBS 專用 app bundle ID）。

**BBS 熱鍵需求**：
- 方向鍵（上下左右）— 選單 + 文章導覽
- Space — 往下一頁
- Enter — 進入
- ← Backspace — 返回
- PgUp/PgDn — 翻頁
- Q — 離開 / 結束
- /, A, 1-9 — 搜尋 / 文章編號

**對 layout 的訊息**：BBS 跟你的 vim/tmux 工作流**很少衝突**——它主要用方向鍵 + space + enter，這些都已經是 layout 必備鍵；但要注意 **NAV layer 不能設計成「按了 hold 就完全進 nav 模式」**，因為 BBS 的方向鍵連發很頻繁，hold 要穩定。

---

## 4. 給 Layout 設計的具體訊號

### 4.1 Base layer 的 hot keys（絕對不能動）

按 base layer 觸達優先順序（從必須最易達到較容易）：

| 區位 | 鍵 | 為什麼 |
|---|---|---|
| **最強指（thumb）** | Space, Backspace, Enter | 三者合計 28% |
| **home row** | a, s, d, f / j, k, l, ; | vim hjkl + 字母高頻 |
| **home row 鄰位** | i, o, n, e, r, t | 高頻字母 |
| **next-to-home** | c, p, m, b, u, h, v, g, y | 中頻字母 + vim 指令字母 |

**所有英文字母都必須在 base layer 上**——不能搬到 layer。

### 4.2 必須好按的 modifier

排序：
1. **Cmd**（49% mod 用量）— 但你在問「能不能戒掉」，所以先保留外側 pinky
2. **Shift**（27%）— **應該在 thumb**（次於 Space/Enter/Bksp）或 home row pinky
3. **Ctrl**（12%）— 真實用量沒想像高，可以在 thumb 或外側 pinky
4. **Alt**（7%）— 偶爾用，遠側可以

### 4.3 應該移到 layer 的鍵

從 base layer 移走、進 layer 沒問題的低頻單鍵：

| 鍵 | base 次數 | 移到哪 |
|---|---|---|
| Escape (617) | base 617 但有 J+K combo 雙保險 | Caps Lock (ALL_T) + J+K combo |
| Tab (118) | 低 | thumb 或 inner column |
| End/Home (145/少) | 低 | NAV layer |
| PgUp/PgDn (602/895) | 中 | **NAV layer**（BBS 需要） |
| F19 (1201) | Karabiner-generated, 不在 layout 範圍 | — |

### 4.4 SYM layer 設計優先順序（依 shift+數字 用量）

shift+數字組（=symbol）用量：
- `shift+=` (=`+`) 73 次
- `shift+;` (=`:`) 114 次 ⭐
- `shift+/` (=`?`) 46 次
- `shift+1` (=`!`) 20 次
- `shift+2` (=`@`) 14 次
- `shift+5` (=`%`) 18 次（部分混進 cmd+shift+5）

**對 SYM layer 的訊息**：
- **`:` 是 vim command-line 入口**（114 次）—— 在 SYM layer 上要極易達；建議放右手 home row index 位
- **`+` `=` 是程式運算**（73 次）—— 右手 home row 中段
- **`?` `/`** 雙向搜尋—— 也是 home row 級
- **brackets `[]{}()<>` 沒抓到單獨統計**，但程式設計師日常頻率高，inner column 直接放是好選擇

### 4.5 NAV layer 設計優先順序

從 BBS 與瀏覽器需求：
- **方向鍵**（左右下上）→ hjkl 位置
- **PgUp/PgDn / Home/End** → home row 旁邊
- **Backspace / Delete** → 已在 thumb
- **Word-jump (Ctrl+→ / Ctrl+←)** → 進階

### 4.6 「戒 Command」這件事的真實成本

從資料看，你「動到 Cmd」的真實場景：

| 場景 | Cmd 用量 | 能不能戒 |
|---|---|---|
| macOS 系統熱鍵（C/V/X/A/Z） | ~1,100（cmd+v 511 + cmd+c 272 + cmd+a 62 + ...） | **不建議戒**——成本太高，全系統 muscle memory |
| WezTerm tab/pane（Cmd+1~5、Cmd+D、Cmd+T 等） | ~1,200（cmd+1 主要） | ✅ **可以戒**——改成 Alt 或 leader key 即可 |
| Hammerspoon mash（Cmd+Ctrl） | 179 | ✅ **建議改成真 Hyper**——layout 內建 |
| 其他 | 少 | 視情況 |

**結論**：你能戒的是 **WezTerm 的 Cmd 綁定 + Hammerspoon 的 mash**——這部分大約佔你 Cmd 用量的 **50%**。剩下 50% 是 macOS 系統熱鍵和標準 Cmd+C/V/A/Z，**戒掉不划算**。

---

## 5. 跟 spec.md 已決定事項的對照

| spec.md 決策 | 資料驗證 | 結論 |
|---|---|---|
| Space 在左 thumb 中央 LT(NAV, KC_SPC) | Space 佔 20.17% | ✅ **強驗證** |
| Backspace 在右 thumb | Backspace 佔 5.15%（第 2 名） | ✅ **強驗證** |
| Caps→Esc/Hyper (ALL_T) | Esc 單按 617 次 + mash 179 次 | ✅ **驗證** —— 兩者合起來 800 次/8 天，Hyper 槽位有用 |
| J+K combo → Esc | （combo 沒被計入；但 vim normal-mode jk 排第 3、第 23） | ✅ **可行**—— J+K 不會跟 base 衝突 |
| hjkl 在 base 不動 | h/j/k/l 合計 13,939 次/8 天 | ✅ **絕對不能動** |
| 5 layer（NAV/SYM/FN/ADJ/Base） | 對 | ✅ |
| 砍 NUM layer | 你硬體有實體數字列 | ✅ |
| Modifier 第一版採保守路線（pinky/thumb，不 HRM） | Ctrl 只佔 mod 用量 12%，沒必要扛 HRM 風險 | ✅ **強驗證**—— Ctrl 不用在 home row |

### 5.1 資料反過來建議要改 spec 的地方

1. **`,` (leader) 必須在 base layer 易達位置**——目前 spec.md 沒明確指定。資料顯示 `,` 是 2,340 次/8 天的 base layer 鍵。**建議：仍放 QWERTY 原位（右手 home row 下方），這是最佳位置**。
2. **`;` 跟 `:` 處理**：`shift+;` 用量 114 次（vim `:`）—— **強烈建議用 Tap Dance**（單 tap=`;`、雙 tap=`:`），省一次 shift。spec.md 5.2 已有提及但未列為 v0.2 必做，**建議升等為必做**。
3. **NAV layer 要含 PageUp/PageDown**——spec.md 5.1 沒明列 PgUp/PgDn，但你 BBS 工作流真的需要。**建議補進 NAV layer 規格**。
4. **WezTerm 的 Cmd 綁定可以全部改 Alt**——你資料顯示 Alt 還大量空缺（只佔 7%），WezTerm 把 Cmd+D/W/T/1~5 全改成 Alt+D/W/T/1~5 完全可行，且不會跟 macOS 系統熱鍵衝突。**這是「戒 Command」最低風險的具體計畫**。

### 5.2 新增的 spec 候選決策

1. **Hammerspoon mash 全部平移到 Hyper**——Caps Lock 設好 ALL_T 之後，Hammerspoon 的 `cmd+ctrl` 改成 `cmd+ctrl+alt+shift`（也就是 Hyper），這樣全鍵盤只剩一個 Hyper 入口、不用記 mash vs mashAlt。**會多需要 Karabiner 一個 manipulator 來轉換** `Hyper+key → mash+key` 或直接改 Hammerspoon 註冊。
2. **inner column 左 1 顆建議：`,`（leader 備援）**——因為 `,` 在 base 用太頻繁，inner column 多一個入口在 vim leader 場景可以雙手分擔。
3. **Shift 候選位置升等**——目前 spec.md 5.4 把 Shift 列為左外/右外的可選；資料顯示 Shift 佔 mod 用量 27%，**應該升等到 thumb 之一**或者用 OSM 模式（按一下 sticky）。

---

## 6. 局限與下一步

### 局限
- **無 8 天 baseline 之外的長期數據**——可能本週 vim/tmux 偏重，下週可能在做別的（例如 PowerPoint 之類），分布會跳
- **資料無記錄按鍵序列**——`,mp` `,gf` 之類 leader 序列無法量化，只能間接從「app 內 top 鍵」推
- **combo / tap dance / mod-tap 都沒被計入**——這些 firmware 層的鍵不會出現在 macOS 事件層
- **f19 1201 次但不知道映射到什麼**——Karabiner 有條 manipulator 把某鍵 → F18 / F19 / F20，要去 `private_karabiner.json` 對

### 下一步建議
1. **跑 1 個月的 keystat 再 re-analyze**——看看 v0.1 spec flash 後實際用量變化
2. **加入 BBS-specific 抽樣**——如果你有用 BBS app（非瀏覽器），可以加進 APP_BUCKETS
3. **追蹤 leader 序列**——keystat 改成記錄相鄰兩鍵時序，可以還原 `,X` 用量
4. **Hammerspoon 改 hook 自己記錄**——`mash+key` 用了幾次直接從 Hammerspoon log 出來，比從 macOS 事件層猜準

---

## 變更紀錄

| 日期 | 版本 | 內容 |
|---|---|---|
| 2026-05-28 | v0.1 | 初版：8 天 137k 擊鍵基礎分析、tmux/wezterm/vim/Hammerspoon hotkey 對照、給 spec 的具體 8 點建議 |
