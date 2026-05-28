# Daily Handoff

Last reviewed: 2026-05-28 11:18 JST

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

## Dirty Tree Summary

- `scripts/install_weekly_cc_update_launch_agent.py` and `scripts/run_weekly_cc_current_season_update.sh` are intentional local automation changes from the 2026-05-28 weekly CC LaunchAgent migration.

## Active Automations

- `websoccer-current-season-cc-weekly-update`
  - Weekly Sunday 02:00 JST via `~/Library/LaunchAgents/com.gigagigo.websoccer.cc-current-season-update.plist`.
  - Codex cron automation is paused; the active scheduler is macOS LaunchAgent.
  - Workdir for unattended runs: `/Users/gigagigo/work/coding/websoccer-player-search`.
  - Wrapper: `scripts/run_weekly_cc_current_season_update.sh`.
  - Expected logs: `~/Library/Logs/websoccer-player-search/weekly-cc-update.out.log` and `.err.log`.
  - Wrapper uses `--notify-pushover --reuse-valid-session`.

- `websoccer-updatefile-and-core-data-watch`
  - Local LaunchAgent: `~/Library/LaunchAgents/com.gigagigo.websoccer.updatefile-core-watch.plist`.
  - Runs hourly at minute `00`, excluding 04:00, 05:00, and 06:00 JST.
  - Workdir for unattended runs: `/Users/gigagigo/work/coding/websoccer-player-search`.
  - Data dir for unattended runs: `/Users/gigagigo/work/coding/wsc_data`.
  - Wrapper: `scripts/run_updatefile_and_core_data_watch.sh`.
  - Installer: `scripts/install_updatefile_and_core_data_launch_agent.py`.
  - Logs: `~/Library/Logs/websoccer-player-search/updatefile-core-watch.out.log` and `.err.log`.
  - The old Codex cron automation is paused because cron-launched threads were observed with `network_access=false`, causing DNS failures.

- `websoccer-daily-handoff-refresh`
  - Updates this file for new Codex chats.

## Important Commands

```bash
python3 scripts/run_cc_update_pipeline.py --season 0 --commit-push --quit-first --auto-navigate-websoccer --wait-sec 900 --notify-pushover --reuse-valid-session
python3 scripts/run_cc_update_pipeline.py --season 0 --quit-first --auto-navigate-websoccer --capture-only --wait-sec 180 --capture-warmup-sec 3
python3 scripts/watch_updatefile_and_refresh_site.py --commit-push
python3 scripts/fetch_update_core_data.py --auth-check
python3 scripts/fetch_update_core_data.py --ids 3210 --dry-run
python3 scripts/fetch_update_core_data.py --dry-run
```

## Recent Status

- CC:
  - `~/charles_sessions` contains fresh saved sessions through `2026-05-28 00:38 JST`.
  - Weekly CC LaunchAgent was reinstalled at `2026-05-28 11:18 JST` to use `/Users/gigagigo/work/coding/websoccer-player-search`.
  - No full weekly CC run was kicked off during the migration to avoid unintended data update/commit/push outside the Sunday 02:00 schedule.

- UpdateFile:
  - Latest local UpdateFile directory is `../wsc_data/UpdateFile_p40_325`.
  - Manual LaunchAgent kickstart at `2026-05-28 10:21 JST` succeeded from `/Users/gigagigo/work/coding/websoccer-player-search`.
  - Scheduled LaunchAgent run at `2026-05-28 11:00 JST` also succeeded.
  - Both runs reported `p326: missing HTTPError 403`, then `no new UpdateFile`.
  - Historical log context still includes the 2026-05-25 `p325` download and failed site rebuild caused by a missing CC DB path in the older `/Users/k.nishimura/...` environment.

- Update_core_data:
  - Latest saved snapshot remains `../wsc_data/update_core_data_3205_3210` from `2026-05-21 19:09 JST`.
  - Manual LaunchAgent kickstart at `2026-05-28 10:21 JST` and scheduled run at `2026-05-28 11:00 JST` extracted API auth, validated latest id `3210`, and probed `3211` through `3220`.
  - Probe result: HTTP 500 / no new core rows.

## Unresolved Issues

- Verify the WSM/site integration path the first time new `update_core_data` rows appear beyond `3210`.
- Confirm the next scheduled weekly CC LaunchAgent run succeeds on Sunday 02:00 JST.

## Stash And Scratch

- Stash still present: `stash@{0}: On main: pre-cc-update dirty workspace 2026-05-27`.
- No local scratch files were found under `app/prepared/local/`, `local/`, `tmp/`, or `artifacts/` during this refresh.
