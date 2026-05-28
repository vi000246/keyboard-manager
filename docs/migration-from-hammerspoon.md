# Migration: Hammerspoon `keystat.lua` → `native-helper`

> **Update 2026-05-28 (later same day)**: the JSON importer
> (`backend/scripts/import_keystat.py`) has been **removed**. The 8-day
> baseline imported under `source='hs_keystat_json'` remains in SQLite
> indefinitely as historical data. Going forward, the native helper writes
> directly to SQLite under `source='native_helper'` — no more JSON in the
> pipeline. The "rollback" section below is now informational only; restoring
> Hammerspoon would resume writing the JSON but the repo no longer has tooling
> to import it back.

Originally a Hammerspoon `keystat.lua` module fed `~/keystat-counts.json` with
cumulative per-(app, key) counts. Starting 2026-05-28 the `keyboard-manager`
native helper owns global keystroke capture and writes events into SQLite
directly. This doc records the cutover so future-you can reverse it if needed
and so the old JSON's role is clear.

## What changed

| Concern | Before | After |
|---|---|---|
| Source of new keystrokes | `~/.hammerspoon/keystat.lua` | `native-helper` (launchd-managed) |
| Data store | `~/keystat-counts.json` (cumulative counts) | `~/Library/Application Support/keyboard-manager/keystat.db` (per-event rows, `source` column) |
| Capture lifecycle | tied to Hammerspoon process | own launchd LaunchAgent, auto-starts at login, KeepAlive |
| Timestamp granularity | none (single counter) | per-event epoch seconds in the `ts` column |

## Steps performed

1. **Native helper deployed** (`native-helper/install-launchd.sh`). Listens
   for global key events via pynput, batched 5 s to SQLite, broadcast via
   WebSocket on `:8766`. Requires macOS Accessibility — see
   [`docs/macos-accessibility.md`](./macos-accessibility.md).

2. **Hammerspoon keystat disabled.** In `~/.hammerspoon/init.lua` we commented
   out the `pcall(require, 'keystat')` line and ran `hs.reload()`. The
   `keystat.lua` file is left on disk; only the `require` is gone. Confirm
   with:

   ```bash
   hs -c "return tostring(package.loaded.keystat ~= nil)"   # → false
   ```

3. **Final JSON import.** Ran the importer one last time so any keystrokes
   captured between the first import (during MVP M2) and the cutover are
   preserved as baseline:

   ```bash
   cd ~/Projects/keyboard-manager
   backend/.venv/bin/python -m backend.scripts.import_keystat \
     /Users/logan/keystat-counts.json \
     --db "$HOME/Library/Application Support/keyboard-manager/keystat.db"
   ```

   The importer defaults to `replace_existing_source=True` so re-imports
   refresh the `hs_keystat_json` source rows in place rather than
   accumulating duplicates. The `native_helper` source rows are not touched.

4. **JSON file kept as a backup.** `~/keystat-counts.json` is no longer
   updated but stays on disk; it documents the 8-day historical baseline that
   bootstrapped the heatmap.

## Source labels in SQLite

```sql
SELECT source, COUNT(*) AS events, SUM(count) AS total_count
FROM events
GROUP BY source;
-- hs_keystat_json | 1378 | 146547   ← historical JSON baseline (8 days)
-- native_helper   |  134 |    134   ← live capture from cutover onwards
```

Stats / heatmap queries do not filter by `source` — both contribute to the
same aggregate, which is what we want (the JSON baseline gives heatmap depth
on day one, the helper extends it).

## Rolling back

If the native helper proves unreliable on a future macOS update:

1. Uninstall the LaunchAgent: `native-helper/uninstall-launchd.sh`
2. Re-enable Hammerspoon keystat: uncomment `pcall(require, 'keystat')` in
   `~/.hammerspoon/init.lua`, then `hs -c "hs.reload()"`.
3. The `~/keystat-counts.json` writes will resume from where Hammerspoon last
   left it. Re-import any time with the same command in step 3 above.

`native_helper` events already in SQLite stay. Nothing destructive happens to
the existing data.

## Verifying the new pipeline

```bash
DB="$HOME/Library/Application Support/keyboard-manager/keystat.db"
before=$(sqlite3 "$DB" "SELECT COUNT(*) FROM events WHERE source='native_helper'")
sleep 30    # type normally
after=$(sqlite3 "$DB" "SELECT COUNT(*) FROM events WHERE source='native_helper'")
echo "captured $((after - before)) events in 30 s"
```

> Typical desk-typing: ≥ 20 events / 30 s. If you get 0, the most likely
> cause is the Accessibility grant being on the wrong binary — see
> [`docs/macos-accessibility.md`](./macos-accessibility.md).
