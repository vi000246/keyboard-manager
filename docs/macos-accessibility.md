# macOS Accessibility Permission for the Native Helper

`native-helper` uses `pynput` to read global keyboard events. macOS sandboxes this — the helper needs **Accessibility** permission before its `pynput.keyboard.Listener` can see anything. Without it the helper boots, the WebSocket starts, but no events flow and you'll see this in the log:

```
WARNING pynput.keyboard.Listener This process is not trusted! Input event
monitoring will not be possible until it is added to accessibility clients.
```

## The gotcha: grant the Python.app bundle, not the symlink

`native-helper/.venv/bin/python` is a symlink, e.g.

```
.venv/bin/python → /opt/homebrew/opt/python@3.12/bin/python3.12
                 → /opt/homebrew/Cellar/python@3.12/X.Y.Z/.../bin/python3.12
```

But pynput's CGEventTap actually runs through the **Framework Python.app bundle**:

```
/opt/homebrew/Cellar/python@3.12/<version>/Frameworks/Python.framework/Versions/3.12/Resources/Python.app
```

macOS Accessibility identifies processes by code signature + bundle, **not** by the path you launched. So you must grant the `.app` bundle, not the `bin/python` binary. Granting the binary alone will leave the warning in place even though the process appears in the list.

## One-time setup

1. Find the correct `Python.app` path for your installed Python:
   ```bash
   readlink -f /Users/logan/Projects/keyboard-manager/native-helper/.venv/bin/python
   # → /opt/homebrew/Cellar/python@3.12/X.Y.Z/Frameworks/Python.framework/Versions/3.12/bin/python3.12
   ```
   The `Python.app` lives two levels up at `Resources/Python.app`, e.g.
   ```
   /opt/homebrew/Cellar/python@3.12/X.Y.Z/Frameworks/Python.framework/Versions/3.12/Resources/Python.app
   ```

2. Open **System Settings → Privacy & Security → Accessibility**.

3. Click `+`, then `⌘⇧G` (Go to Folder), paste the `Python.app` path above, hit Enter.

4. Tick the checkbox for the added `Python.app` entry.

5. Reload the launchd helper so the listener re-attaches with the new grant:
   ```bash
   launchctl unload ~/Library/LaunchAgents/com.keyboard-manager.helper.plist
   launchctl load   ~/Library/LaunchAgents/com.keyboard-manager.helper.plist
   ```

6. Verify capture is working:
   ```bash
   DB="$HOME/Library/Application Support/keyboard-manager/keystat.db"
   before=$(sqlite3 "$DB" "SELECT COUNT(*) FROM events WHERE source='native_helper'")
   sleep 30   # type normally during this window
   after=$(sqlite3 "$DB" "SELECT COUNT(*) FROM events WHERE source='native_helper'")
   echo "delta: $((after - before))"   # should be > 0
   ```

## Common pitfalls

| Symptom | Cause | Fix |
|---|---|---|
| `not trusted` warning persists after grant | Granted the symlink/bin not the `.app` bundle | Remove the entry, re-add the `Python.app` bundle |
| `not trusted` persists despite `.app` grant | Stale daemon (launchd holds an old PID) | `launchctl unload` then `load` the plist |
| Helper running but no events in DB | Foreground app is in System Settings (some panes block global event taps) | Switch focus to any other app and type there |
| After macOS update, capture stops | The OS sometimes revokes permissions on system updates | Re-tick the `Python.app` entry; if still failing, remove + re-add |
| Python version upgraded via brew | The `.app` bundle path now includes a new version | Re-grant against the new path (and prune the old one) |

## Why not Swift / native binary?

A purpose-built signed binary (Swift + CGEventTap, or a hardened Python launcher) would avoid the "Framework Python.app" surprise. We chose `pynput` for v1 because it keeps the helper in the same Python stack as the backend and ships in 15 lines. If macOS Accessibility breaks again post-update or pynput's permission UX gets worse, this is the obvious follow-up — see `docs/srs/keyboard-manager-mvp.srs.md` Open Questions.

## Uninstalling

```bash
~/Projects/keyboard-manager/native-helper/uninstall-launchd.sh
```

This unloads + removes the LaunchAgent. The Accessibility grant can be revoked in System Settings (untick the box, or `-` the entry).
