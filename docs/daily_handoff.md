# Daily Handoff

Last reviewed: 2026-05-29 09:17 JST

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
 M docs/daily_handoff.md
 M docs/new_chat_prompt.md
 M scripts/refresh_daily_handoff.py
?? docs/daily_handoff_notes.md
?? scripts/analyze_cc_player_lineup_swaps.py
?? scripts/append_daily_handoff_note.py
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
[2026-05-29 08:00:07] updatefile/core-data watch done
[2026-05-29 09:00:05] updatefile/core-data watch start
[2026-05-29 09:00:05+0900] p326: missing HTTPError 403
[2026-05-29 09:00:05+0900] no new UpdateFile
[2026-05-29 09:00:05] validating latest local core-data id: 3210
[FOUND] 3210: players=1 players_param=16
[2026-05-29 09:00:06] no new core-data rows found
[2026-05-29 09:00:06] updatefile/core-data watch done
```
- Update_core_data:
  - Latest local snapshot: `/Users/gigagigo/Documents/Codex/wsc_data/update_core_data_3205_3210`.
  - New ids should be treated as absent when the latest known id validates and the next ids return HTTP 500.

## Persistent Chat Notes

These notes are maintained in `docs/daily_handoff_notes.md` and are preserved across automatic refreshes.

# Daily Handoff Notes

Use this file for durable context learned during chats. `scripts/refresh_daily_handoff.py` includes this content in `docs/daily_handoff.md` on every automatic refresh.

## Operating Notes

- When a chat establishes a durable workflow, unresolved issue, investigation result, or manual decision, add it here instead of editing only `docs/daily_handoff.md`.
- Prefer `python3 scripts/append_daily_handoff_note.py --section "<section>" --note "<note>"` for single-note additions during a chat.
- Do not include Websoccer-gate-key, Cookie, User-Agent, Pushover token, Pushover user key, or other secret values.
- Keep transient command output and scratch analysis out of this file unless it changes future operations.

## Team Creation / League Assignment

- 2026-05-29: Local CoreData detail: ZMOTEAMDATA.ZLEAGUE is a relationship to ZMOLEAGUE.Z_PK, not the WebSoccer league id. When building or repairing a local profile, set ZLEAGUE to the ZMOLEAGUE.Z_PK row whose ZID equals the server/informal league_id.
- 2026-05-29: Team006 verification: created API-only with selected player_id 1693; server /sync/all returned world=16, season=2627, name=Team006, league=751. Local profile maps ZLEAGUE Z_PK=752 to ZMOLEAGUE.ZID=751, ZCLASS_ID=0, ZGROUP_ID=0, ZGROUP_NAME=エントリーリーグ, and the app displayed エントリーリーグB.
- 2026-05-29: API-only team creation: do not subtract 1 from the league_id returned by /creating_team/informal.json when calling /creating_team/formal.json. Team003-Team005 were affected by the earlier -1 submission; Team006 was created with formal.league_id equal to the informal league_id and is the post-fix control case.
- 2026-05-28: The new-team creation client-side wrong-league submission issue was fixed. Treat Team003-Team005 as pre-fix affected teams.
- 2026-05-28 Team003 evidence: `/sync/all.json` returned `world=9`, `season=2627`, `name=Team003`, `league=400`; `league=400` maps to the previous world's main-league row in local `ZMOLEAGUE`, while world 9 entry league rows are `Z_PK=402` / `ZID=401` and `Z_PK=403` / `ZID=402`.
- User observed Team003-Team005 are displayed as main league A from team detail, but team search, ranking, and actual matches treat them as entry league teams. No fix was observed after the 2026-05-29 morning maintenance. Recheck after the Sunday early-morning promotion/relegation maintenance.
- Team006 is the post-fix control case and is considered correctly created: local `ZMOTEAMDATA` has `Team006`, `world=16`, `league Z_PK=752`, mapping to `ZMOLEAGUE.ZID=751`, `ZCLASS_ID=0`, `ZGROUP_ID=0`, `ZGROUP_NAME=エントリーリーグ`.
- API-only team creation was established in another chat, but the exact reusable runbook is not yet committed here. Known endpoint flow from Charles evidence: `/creating_team/initHP.json`, `/creating_team/checkName.json`, `/creating_team/informal.json`, `/creating_team/status/{uuid}.json`, `/creating_team/formal.json`, then login/sync endpoints. Create a dedicated runbook when that chat's details are available.

## Handoff Operation

- 2026-05-29: daily_handoff_notes.md is manually appended during chats when durable findings emerge; new_chat_prompt.md now instructs future chats to read it at startup and use append_daily_handoff_note.py for single-note additions.

## Automation / Power

- 2026-05-29: Codex automations depend on the Mac being awake and logged in for local file operations and GUI flows. A user LaunchAgent runs /usr/bin/caffeinate -s from ~/Library/LaunchAgents/com.gigagigo.keepawake.ac.plist to prevent AC-power system sleep without preventing display sleep. If automation unexpectedly stops, check launchctl status and pmset assertions before debugging scripts.

## UpdateFile / Core Data

- 2026-05-29: UpdateFile/core-data automation skips the 04:00, 05:00, and 06:00 JST runs because Webサッカー maintenance is 04:00-07:00. UpdateFile pXXX.zip checks are non-GUI, but Update_core_data may need fresh WebSoccer auth; validate an existing latest core id first before deciding to capture a new key.
- 2026-05-29: Update_core_data endpoint behavior: existing ids are fetched via /update_core_data/player/<ids>/.json and /update_core_data/players_param/<ids>/.json. A fresh valid session fetched existing id 3205 successfully, while next unissued id 3211 returned HTTP 500; treat HTTP 500 for only the next id as no-new-core-data when the latest existing id still returns rows.

## Notifications

- 2026-05-29: Pushover is configured through ~/.websoccer_pushover.env and must not be committed. Notification titles were standardized in English for CC/UpdateFile/core flows; message bodies may remain Japanese. Test notifications were delivered successfully.

## CC Update

- 2026-05-29: CC updates should use run_cc_update_pipeline.py with --reuse-valid-session. The pipeline first performs a lightweight CC API check against the newest/session-file Charles session and only launches Charles/Webサッカー for fresh auth if the existing session is missing or stale. Fresh key capture mutes macOS system output before launching Webサッカー to avoid unexpected sound.

## Unresolved Issues

- Confirm the next scheduled daily handoff LaunchAgent run succeeds at 05:00 JST.
- Confirm the next scheduled weekly CC LaunchAgent run succeeds on Sunday 02:00 JST.
- Verify the WSM/site integration path the first time new `update_core_data` rows appear beyond the latest local snapshot.

## Stash And Scratch

```text
stash@{0}: On main: pre-cc-update dirty workspace 2026-05-27
```
