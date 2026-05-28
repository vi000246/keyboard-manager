#!/usr/bin/env bash
# Install the keyboard-manager native helper as a launchd LaunchAgent.
# Idempotent — safe to re-run after edits to the plist or helper code.
set -euo pipefail

PLIST_NAME="com.keyboard-manager.helper.plist"
SRC="$(cd "$(dirname "$0")" && pwd)/${PLIST_NAME}"
DST="${HOME}/Library/LaunchAgents/${PLIST_NAME}"

if [[ ! -f "${SRC}" ]]; then
  echo "ERROR: ${SRC} not found" >&2
  exit 1
fi

mkdir -p "${HOME}/Library/LaunchAgents"

# Unload any previous version cleanly (ignore "not loaded" errors)
if launchctl list | grep -q com.keyboard-manager.helper; then
  echo "Unloading previous helper..."
  launchctl unload "${DST}" 2>/dev/null || true
fi

# Copy fresh plist (cp instead of symlink so launchd doesn't follow into the repo)
cp "${SRC}" "${DST}"
echo "Installed: ${DST}"

# Load and bootstrap
launchctl load "${DST}"
echo "Loaded into launchd."
echo
echo "Verify with:"
echo "  launchctl list | grep com.keyboard-manager.helper"
echo "  pgrep -fl native_helper.main"
echo "  tail -f /tmp/keyboard-manager-helper.err.log"
echo
echo "If 'pynput: This process is not trusted!' appears in the log, grant"
echo "Accessibility permission to the Python interpreter:"
echo "  System Settings → Privacy & Security → Accessibility → +"
echo "  add /Users/logan/Projects/keyboard-manager/native-helper/.venv/bin/python"
echo "After granting, restart the helper:"
echo "  launchctl unload \"${DST}\" && launchctl load \"${DST}\""
