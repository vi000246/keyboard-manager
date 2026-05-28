#!/usr/bin/env bash
# Install the git-backup LaunchAgent. Idempotent.
set -euo pipefail

PLIST_NAME="com.keyboard-manager.git-backup.plist"
SRC="$(cd "$(dirname "$0")" && pwd)/${PLIST_NAME}"
DST="${HOME}/Library/LaunchAgents/${PLIST_NAME}"

mkdir -p "${HOME}/Library/LaunchAgents"

if launchctl list | grep -q com.keyboard-manager.git-backup; then
  launchctl unload "${DST}" 2>/dev/null || true
fi

cp "${SRC}" "${DST}"
launchctl load "${DST}"

echo "Installed and loaded: ${DST}"
echo
echo "Verify with:"
echo "  launchctl list | grep com.keyboard-manager.git-backup"
echo "  tail -f /tmp/keyboard-manager-git-backup.err.log"
echo
echo "Next run: tomorrow at 03:30 local. Run backup.sh manually to test now."
