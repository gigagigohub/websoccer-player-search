# Daily Handoff

Last reviewed: 2026-05-28 11:40 JST

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
- Unattended LaunchAgent runs use `/Users/gigagigo/work/coding/websoccer-player-search`.

## Dirty Tree Summary

```text
(clean)
```

## Active Schedulers

- Codex cron:
  - `websoccer-daily-handoff-refresh`: PAUSED
  - `websoccer-current-season-cc-weekly-update`: PAUSED
  - `websoccer-updatefile-and-core-data-watch`: PAUSED
- LaunchAgent `com.gigagigo.websoccer.daily-handoff-refresh`
  - Schedule: daily 05:00 JST
  - Workdir: /Users/gigagigo/work/coding/websoccer-player-search
  - Logs: `~/Library/Logs/websoccer-player-search/daily-handoff-refresh.out.log` and `.err.log`
  - Pushover: failure-only via `~/.handoff_pushover.env`
- LaunchAgent `com.gigagigo.websoccer.cc-current-season-update`
  - Schedule: Sunday 02:00 JST
  - Workdir: /Users/gigagigo/work/coding/websoccer-player-search
  - Logs: `~/Library/Logs/websoccer-player-search/weekly-cc-update.out.log` and `.err.log`
- LaunchAgent `com.gigagigo.websoccer.updatefile-core-watch`
  - Schedule: hourly at minute `00`, excluding 04:00, 05:00, and 06:00 JST
  - Workdir: /Users/gigagigo/work/coding/websoccer-player-search
  - Logs: `~/Library/Logs/websoccer-player-search/updatefile-core-watch.out.log` and `.err.log`

## Important Commands

```bash
python3 scripts/run_cc_update_pipeline.py --season 0 --commit-push --quit-first --auto-navigate-websoccer --wait-sec 900 --notify-pushover --reuse-valid-session
python3 scripts/run_cc_update_pipeline.py --season 0 --quit-first --auto-navigate-websoccer --capture-only --wait-sec 180 --capture-warmup-sec 3
python3 scripts/watch_updatefile_and_refresh_site.py --commit-push
python3 scripts/fetch_update_core_data.py --auth-check
python3 scripts/fetch_update_core_data.py --dry-run
python3 scripts/install_daily_handoff_refresh_launch_agent.py
python3 scripts/install_weekly_cc_update_launch_agent.py
python3 scripts/install_updatefile_and_core_data_launch_agent.py
```

## Recent Status

- CC:
  - Latest weekly log signals:
```text
log not found
```
- UpdateFile:
  - Latest local UpdateFile directory: `/Users/gigagigo/Documents/Codex/wsc_data/UpdateFile_p40_325`.
  - Latest watcher log signals:
```text
[2026-05-28 10:21:17] updatefile/core-data watch done
[2026-05-28 11:00:05] updatefile/core-data watch start
[2026-05-28 11:00:05+0900] p326: missing HTTPError 403
[2026-05-28 11:00:05+0900] no new UpdateFile
[2026-05-28 11:00:05] validating latest local core-data id: 3210
[FOUND] 3210: players=1 players_param=16
[2026-05-28 11:00:06] no new core-data rows found
[2026-05-28 11:00:06] updatefile/core-data watch done
```
- Update_core_data:
  - Latest local snapshot: `/Users/gigagigo/Documents/Codex/wsc_data/update_core_data_3205_3210`.
  - New ids should be treated as absent when the latest known id validates and the next ids return HTTP 500.

## Unresolved Issues

- Confirm the next scheduled daily handoff LaunchAgent run succeeds at 05:00 JST.
- Confirm the next scheduled weekly CC LaunchAgent run succeeds on Sunday 02:00 JST.
- Verify the WSM/site integration path the first time new `update_core_data` rows appear beyond the latest local snapshot.

## Stash And Scratch

```text
stash@{0}: On main: pre-cc-update dirty workspace 2026-05-27
```
