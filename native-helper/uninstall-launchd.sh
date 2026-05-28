#!/usr/bin/env bash
# Remove the keyboard-manager launchd LaunchAgent. Idempotent.
set -euo pipefail

PLIST_NAME="com.keyboard-manager.helper.plist"
DST="${HOME}/Library/LaunchAgents/${PLIST_NAME}"

if launchctl list | grep -q com.keyboard-manager.helper; then
  echo "Unloading helper..."
  launchctl unload "${DST}" 2>/dev/null || true
fi

if [[ -f "${DST}" ]]; then
  rm -f "${DST}"
  echo "Removed: ${DST}"
else
  echo "(no plist at ${DST})"
fi

echo
echo "Helper is no longer managed by launchd."
echo "Existing keystat events in SQLite are preserved."
