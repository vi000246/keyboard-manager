#!/usr/bin/env bash
# Daily snapshot of keystat.db → private git remote.
# Idempotent: no-op if there are no changes since the last commit.
set -euo pipefail

LIVE_DB="${KEYSTAT_DB:-$HOME/Library/Application Support/keyboard-manager/keystat.db}"
BACKUP_REPO="${KM_BACKUP_REPO:-$HOME/Library/Application Support/keyboard-manager/git-backup}"
BACKUP_FILE="$BACKUP_REPO/keystat.db"

log() { printf '%s %s\n' "$(date '+%Y-%m-%dT%H:%M:%S%z')" "$*"; }

if [[ ! -f "$LIVE_DB" ]]; then
  log "ERROR: live db not found at $LIVE_DB"
  exit 1
fi

if [[ ! -d "$BACKUP_REPO/.git" ]]; then
  log "ERROR: $BACKUP_REPO is not a git checkout. Run setup.sh first."
  exit 1
fi

# Online backup — safe to run while the helper is writing.
sqlite3 "$LIVE_DB" ".backup '$BACKUP_FILE'"

cd "$BACKUP_REPO"

# Stage first so the diff check covers both "new file" and "modified".
git add keystat.db

# Bail out cleanly if nothing changed (no events since last backup).
if git diff --cached --quiet --exit-code keystat.db; then
  log "no changes since last backup — skipping commit"
  exit 0
fi

# Capture row counts in the commit message so `git log` is a usable timeline.
totals="$(sqlite3 "$BACKUP_FILE" \
  "SELECT source || '=' || COUNT(*) || '/' || COALESCE(SUM(count), 0) \
   FROM events GROUP BY source" | tr '\n' ' ')"
size_bytes="$(stat -f %z "$BACKUP_FILE")"

git add keystat.db
git commit -m "snapshot $(date '+%Y-%m-%dT%H:%M') — ${totals} bytes=${size_bytes}"

if ! git push origin HEAD 2>&1; then
  log "WARNING: push failed; commit is local only. Will retry next run."
  exit 0
fi

log "snapshot committed and pushed: ${totals}"
