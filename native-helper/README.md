# native-helper

macOS host-side process that:

1. Captures global `keydown` / `keyup` events with the foreground app's bundle ID
2. Pushes events over WebSocket (`ws://localhost:8765`) for the web UI's Interactive Simulator
3. Writes events to SQLite (`~/Library/Application Support/keyboard-manager/keystat.db`)

## Why this can't run inside Docker

Docker Desktop on macOS runs the Linux VM in a hypervisor that has **no access to host accessibility events or HID input**. The helper therefore must run as a native process on the host.

## Status

Scaffold only. Implementation arrives in M4 (see `docs/PRD.md` Milestones).

## Planned stack

- Python 3.12+
- [`pynput`](https://github.com/moses-palmer/pynput) for the global keyboard listener (cross-evaluate against Swift CGEventTap if pynput's permission UX is too brittle)
- `pyobjc-framework-Cocoa` for `NSWorkspace.frontmostApplication` to grab bundle IDs
- `websockets` for the WS server
- `sqlite3` (stdlib) for the events table

## macOS permissions required

The helper needs **Accessibility** permission (System Settings → Privacy & Security → Accessibility). Grant it once to the Python interpreter (or to the compiled launcher) you use to run the helper.

## launchd plist (M5)

A `com.keyboard-manager.helper.plist` will live here and be installed to `~/Library/LaunchAgents/` for auto-start.

## Relationship to existing `~/.hammerspoon/keystat.lua`

Once this helper is operational (M4 complete), the Hammerspoon `keystat.lua` binding will be disabled to avoid double-counting. The 8 days of historical JSON data already produced by `keystat.lua` will be imported once as a baseline (M2).
