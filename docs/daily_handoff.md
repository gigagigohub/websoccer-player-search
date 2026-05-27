# Daily Handoff

Last reviewed: 2026-05-28 00:00 JST

## Start Here

Use `docs/new_chat_prompt.md` when opening a fresh Codex chat.

Always start in:

```bash
cd /Users/gigagigo/Documents/Codex/websoccer-player-search
git status --short
```

## Current Operating Notes

- Do not print Websoccer-gate-key, Cookie, User-Agent, Pushover token, or Pushover user key values.
- Avoid `git add .`; stage only intentional files.
- Existing local scratch should go under `app/prepared/local/`, `local/`, `tmp/`, or `artifacts/`.
- Follow `docs/git_hygiene.md` when deciding whether to commit or keep local.

## Automations

- `websoccer-current-season-cc-weekly-update`
  - Weekly Sunday 02:00 JST.
  - Runs current-season CC update.
  - Uses `--reuse-valid-session`; captures a fresh key only when the existing session fails a CC API check.
  - Sends Pushover success/failure notifications.

- `websoccer-updatefile-and-core-data-watch`
  - Hourly.
  - Runs `scripts/watch_updatefile_and_refresh_site.py --commit-push`.
  - Checks Update_core_data with `scripts/fetch_update_core_data.py`.
  - Validates an existing latest core id before deciding whether a fresh key is needed.

## Useful Commands

```bash
python3 scripts/run_cc_update_pipeline.py --season 0 --commit-push --quit-first --auto-navigate-websoccer --wait-sec 900 --notify-pushover --reuse-valid-session
python3 scripts/watch_updatefile_and_refresh_site.py --commit-push
python3 scripts/fetch_update_core_data.py --auth-check
python3 scripts/fetch_update_core_data.py --dry-run
```

## Recent State

- Pushover notification test succeeded.
- CC fresh capture succeeded with Charles Auto Save.
- CC dry-run reused a valid existing Charles session successfully.
- Update_core_data fresh-key validation succeeded for existing id `3205`.
- Update_core_data next id `3211` returned HTTP 500 while existing id worked; treat as no new core data unless future evidence changes.
- UpdateFile dry-run checked `p326` and found no new archive.

## Open Threads

- Commit the intentional automation/support changes when ready.
- The old stash `pre-cc-update dirty workspace 2026-05-27` still exists for earlier mixed dirty work.
- Update_core_data saving works at the JSON fetch layer, but the exact WSM/site integration path for newly saved core rows should be verified when new core rows first appear.
