#!/usr/bin/env bash
# Remove the git-backup LaunchAgent. The GitHub repo + local checkout are
# left in place so the historical snapshots are preserved.
set -euo pipefail

PLIST_NAME="com.keyboard-manager.git-backup.plist"
DST="${HOME}/Library/LaunchAgents/${PLIST_NAME}"

if launchctl list | grep -q com.keyboard-manager.git-backup; then
  launchctl unload "${DST}" 2>/dev/null || true
fi

rm -f "${DST}"
echo "LaunchAgent removed."
echo
echo "Snapshots remain on GitHub and at:"
echo "  ${KM_BACKUP_REPO:-$HOME/Library/Application Support/keyboard-manager/git-backup}"
echo
echo "Delete those manually if you want to wipe the history too."
