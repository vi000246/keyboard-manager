# Git-backed SQLite backup

Daily snapshot of `keystat.db` to a private GitHub repo. Replaces a local-only
launchd backup so a stolen / wiped laptop doesn't take the stats with it.

## How it works

```
~/Library/Application Support/keyboard-manager/keystat.db       (live, helper writes here)
                       │
                       │  sqlite3 .backup
                       ▼
~/Library/Application Support/keyboard-manager/git-backup/keystat.db
                       │
                       │  git add + commit + push
                       ▼
github.com:<user>/keyboard-stats-backup (private repo)
```

The live DB is **never committed in place** — `sqlite3 .backup` creates a
consistent point-in-time copy even if the helper is mid-write.

## One-time setup

```bash
cd ~/Projects/keyboard-manager
./scripts/git-backup/setup.sh
```

This creates:
- a private GitHub repo `<your-gh-user>/keyboard-stats-backup`
- a local checkout at `~/Library/Application Support/keyboard-manager/git-backup/`
- a launchd plist at `~/Library/LaunchAgents/com.keyboard-manager.git-backup.plist`

The launchd job runs **once a day at 03:30 local** and on every system boot
(if a day was missed). Output goes to `/tmp/keyboard-manager-git-backup.{out,err}.log`.

## One-shot backup

If you want to back up immediately (e.g. before a risky change):

```bash
./scripts/git-backup/backup.sh
```

## Restoring from backup

```bash
cd ~/Library/Application Support/keyboard-manager/git-backup
git log --oneline                          # find the snapshot you want
git checkout <commit> keystat.db           # restore that file in place

# Copy back to the live path
cp keystat.db "$HOME/Library/Application Support/keyboard-manager/keystat.db"

# Restart helper so it opens the restored db
launchctl unload ~/Library/LaunchAgents/com.keyboard-manager.helper.plist
launchctl load   ~/Library/LaunchAgents/com.keyboard-manager.helper.plist
```

## Uninstalling

```bash
./scripts/git-backup/uninstall.sh
```

Removes the launchd job; leaves the GitHub repo and local checkout in place
so you can keep the historical snapshots.

## Why a separate repo

The main `keyboard-manager` repo is public; keystroke stats are personal usage
data and don't belong there. Keeping them in a separate **private** repo also
avoids polluting code-repo history with daily binary commits.
