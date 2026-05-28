# Data Preservation Contract

The native helper is the only writer of keystroke statistics now, and those
events are irreplaceable — no JSON source feeds them, and the only way to get
them back if lost is to wait days/weeks for new capture. This doc records the
guarantees, the threats, and the explicit safety nets.

## Where the data lives

```
~/Library/Application Support/keyboard-manager/
├── keystat.db            ← live SQLite database (helper writes here)
└── uploaded.vil          ← optional, set by the upload UI
```

The Docker compose backend mounts this path as `/data/db` with **read-write**;
the Vial config mount stays **read-only**. The DB **never lives inside a
Docker image or volume** — it's a plain host file. Container rebuilds, image
pulls, even `docker compose down -v` leave it untouched.

## What is safe

These operations are confirmed safe and tested:

| Operation                              | Why safe |
|---|---|
| `docker compose down` / `up`           | Bind mount survives container lifecycle |
| `docker compose up -d --build`         | Image rebuild doesn't touch host files |
| `docker compose down -v`               | `-v` only removes *named* volumes; we use a bind mount |
| `git pull` / branch switch in repo     | DB path is outside the repo |
| `ensure_schema()` re-running           | All CREATEs are guarded with `IF NOT EXISTS` |
| App restart (launchd respawn the helper) | New `INSERT` only — no DELETE on the existing rows |
| `.vil` upload via UI                   | Touches `uploaded.vil` only, not `keystat.db` |

## What would destroy data (and how it's prevented)

| Threat | Guard |
|---|---|
| Schema migration adds `DROP TABLE` / `DELETE FROM` | `test_migrations.py::test_schema_text_contains_no_destructive_statements` fails the build |
| Migration replaces `CREATE TABLE IF NOT EXISTS` with `CREATE TABLE` (clobbering on rerun) | `test_schema_uses_if_not_exists_for_every_create` |
| Container restart silently wipes events | `test_ensure_schema_on_populated_db_preserves_rows` seeds, restarts schema 3×, asserts every row survives |
| ~~JSON importer wipes `native_helper` rows~~ | Importer was removed entirely (see `docs/migration-from-hammerspoon.md`). Historical `hs_keystat_json` rows still in the DB, kept as read-only baseline |
| `rm -rf ~/Library/Application Support/keyboard-manager/` | The git-backup script (see below) keeps daily snapshots on a remote |

## Backup: git auto-commit + push

A separate **private** GitHub repo (e.g. `vi000246/keyboard-manager-data`)
holds daily SQLite snapshots. The live DB is never committed in place; a
script makes a hot-backup copy first.

> Setup steps and the actual backup script live in
> [`scripts/git-backup/`](../scripts/git-backup/) (see DP-1' commit).

## Adding a non-additive schema change in the future

Don't edit `SCHEMA` in `backend/db/migrations.py` to add `DROP` or any
destructive statement. The right pattern is:

1. Take a fresh backup: `~/scripts/git-backup/backup-once.sh`
2. Write a one-shot migration script (e.g. `backend/scripts/migrate_NNN_<name>.py`)
3. Document the change in `docs/spec/keyboard-manager.spec.md` Change History
4. Run the script once, verify, then optionally add the new shape to `SCHEMA`
   so fresh databases get it directly

## Restoring from backup

```bash
# Pick a backup from the git-backup repo
cp ~/path/to/keyboard-manager-data/keystat.db \
   "$HOME/Library/Application Support/keyboard-manager/keystat.db"

# Restart helper so it opens the restored file
launchctl unload ~/Library/LaunchAgents/com.keyboard-manager.helper.plist
launchctl load   ~/Library/LaunchAgents/com.keyboard-manager.helper.plist
```

## TL;DR

Future code changes to this repo can't accidentally destroy your stats. The
test suite enforces it. If you ever genuinely need to wipe or restructure
data, that has to happen via an explicit, named, backed-up procedure — not
as a side effect of a normal merge.
