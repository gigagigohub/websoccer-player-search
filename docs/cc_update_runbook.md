# CC Update Runbook

This runbook is the handoff for a fresh Codex chat. Work in:

```bash
cd /Users/gigagigo/Codex/WebSoccer/websoccer-player-search
```

## One Command

Use this for the normal previous-season CC update:

```bash
python3 scripts/run_cc_update_pipeline.py --websoccer-container /Users/gigagigo/Codex/WebSoccer/websoccer_local_backups/account_transfer/teams/10527301_openai/current --commit-push
```

As of 2026-05-30, the normal CC/update_core_data/search auth source is fixed to the stored OpenAI
profile:

```text
/Users/gigagigo/Codex/WebSoccer/websoccer_local_backups/account_transfer/teams/10527301_openai/current
```

The pipeline generates `Websoccer-gate-key` locally from that saved OpenAI profile and validates it
with a lightweight CC API check, then fetches CC data, updates WSM, regenerates site JSON, and
optionally commits/pushes the generated site changes. The default `--auth-source` is `local` so it
does not silently fall back to another ACTIVE team. Use `--auth-source session` explicitly only for
manual Charles fallback investigation.

Use `--season 0` when the target is the current season instead of the previous season.

## Weekly Schedule

The installed launchd job runs every Sunday at 02:00 and fetches the current season.
Codex cron automations are paused; launchd is the active scheduler for weekly CC, UpdateFile/core-data, and daily handoff refresh.
Unattended runs use `/Users/gigagigo/Codex/WebSoccer/websoccer-player-search` as the working copy to
avoid macOS Documents permission prompts:

```bash
python3 scripts/install_weekly_cc_update_launch_agent.py
```

It runs:

```bash
scripts/run_weekly_cc_current_season_update.sh
```

That wrapper calls:

```bash
python3 scripts/run_cc_update_pipeline.py --websoccer-container /Users/gigagigo/Codex/WebSoccer/websoccer_local_backups/account_transfer/teams/10527301_openai/current --auth-source local --skip-capture --season 0 --commit-push --notify-pushover
```

The installed wrapper must pass the OpenAI profile explicitly and must use `--auth-source local
--skip-capture`. Scheduled CC updates are not allowed to launch Charles or Webサッカー. Manual
fallback investigation should be done outside this automation path.

If the Sunday 02:00 job is missed and you manually catch up after the Sunday 04:00 season rollover,
use `--season 1` instead of the scheduled `--season 0`.

```bash
python3 scripts/run_cc_update_pipeline.py \
  --websoccer-container /Users/gigagigo/Codex/WebSoccer/websoccer_local_backups/account_transfer/teams/10527301_openai/current \
  --auth-source local \
  --skip-capture \
  --season 1 \
  --commit-push \
  --notify-pushover
```

Logs are written to:

```text
~/Library/Logs/websoccer-player-search/weekly-cc-update.out.log
~/Library/Logs/websoccer-player-search/weekly-cc-update.err.log
```

Use this to test the scheduled local-auth path without updating WSM/site data:

```bash
python3 scripts/run_cc_update_pipeline.py \
  --websoccer-container /Users/gigagigo/Codex/WebSoccer/websoccer_local_backups/account_transfer/teams/10527301_openai/current \
  --auth-source local \
  --skip-capture \
  --season 0 \
  --worlds 10 \
  --groups 0 \
  --round-max 1 \
  --dry-run-fetch \
  --skip-wsm-update
```

## Charles / WebSoccer Capture

The CC/update_core_data automation no longer captures auth via Charles or Webサッカー. The pipeline
does not contain any app-launch capture path. If local OpenAI profile auth fails, fix the stored
profile/auth generator or investigate manually outside scheduled automation.

## Useful Checks

Check the local generated gate-key path without fetching summaries:

```bash
python3 scripts/run_cc_update_pipeline.py \
  --auth-source local \
  --season 0 \
  --worlds 10 \
  --groups 0 \
  --round-max 2 \
  --dry-run-fetch
```

Check only whether the latest saved session can be used:

```bash
python3 scripts/run_cc_update_pipeline.py \
  --auth-source session \
  --skip-capture \
  --session-dir /Users/gigagigo/charles_sessions \
  --worlds 10 \
  --groups 0 \
  --round-max 4 \
  --dry-run-fetch
```

Use a specific session file:

```bash
python3 scripts/run_cc_update_pipeline.py \
  --auth-source session \
  --skip-capture \
  --session-file /Users/gigagigo/charles_sessions/websoccer_cc_ssl_ok_20260527_2131.chlz \
  --worlds 10 \
  --groups 0 \
  --round-max 4 \
  --dry-run-fetch
```

## What The Pipeline Calls

1. `scripts/fetch_cc_completed_season.py`
   - This is the cleaner group-league + tournament fetch implementation used by the pipeline.
   - `scripts/fetch_cc_full_season_completed.py` remains as a compatibility wrapper for older manual runs.
2. `scripts/update_wsm_cc_from_json.py`
3. `git add` for tracked site JSON files only
4. `git commit`
5. `git push`

The script does not commit unrelated working-tree files.

## Pushover Notifications

The pipeline can notify an iPhone through Pushover after success or failure:

```bash
python3 scripts/run_cc_update_pipeline.py --season 0 --commit-push --notify-pushover --reuse-valid-session
```

Create this local secret file on the Mac. Do not commit the values:

```bash
~/.websoccer_ordinary_pushover.env
```

```text
PUSHOVER_APP_TOKEN=...
PUSHOVER_USER_KEY=...
```

Use the WSC Ordinary Pushover App Key for `PUSHOVER_APP_TOKEN`. The weekly LaunchAgent passes
`--auth-source local --skip-capture --notify-pushover`. It should use the stored OpenAI profile and
should fail rather than launching Charles/Webサッカー if local auth breaks. If the Pushover file or
variables are missing, the CC update still runs and only the notification is skipped.

## Git Hygiene

Before scheduled or manual CC updates, keep unrelated local analysis out of the working tree.
See `docs/git_hygiene.md` for what to commit and where to place scratch outputs.

## UpdateFile / Core Data Watch

Codex automation `websoccer-updatefile-and-core-data-watch` checks app update assets hourly.
Because WebSoccer maintenance runs from 04:00 to 07:00 JST, it skips the 04:00, 05:00, and
06:00 runs.
It runs the existing UpdateFile watcher first:

```bash
python3 scripts/watch_updatefile_and_refresh_site.py --commit-push
```

That watcher downloads new `UpdateFile/pXXX.zip` archives when available, copies site images,
rebuilds the WSM/site JSON, then commits and pushes intentional site changes.

`Update_core_data` is tracked separately from UpdateFile. It now uses the same OpenAI local generated
`Websoccer-gate-key` path by default. Local
snapshots live under
`/Users/gigagigo/Codex/WebSoccer/wsc_data/update_core_data_*`.

Use this to verify that local generated API auth is available without printing the values:

```bash
python3 scripts/fetch_update_core_data.py --websoccer-container /Users/gigagigo/Codex/WebSoccer/websoccer_local_backups/account_transfer/teams/10527301_openai/current --auth-check
```

Auth presence alone is not enough. Validate the existing latest local core id explicitly; if it
returns rows, the key is valid:

```bash
python3 scripts/fetch_update_core_data.py --websoccer-container /Users/gigagigo/Codex/WebSoccer/websoccer_local_backups/account_transfer/teams/10527301_openai/current --ids <latest-local-core-id> --dry-run
```

Use this to probe from the latest local core player id + 1 after validation:

```bash
python3 scripts/fetch_update_core_data.py --websoccer-container /Users/gigagigo/Codex/WebSoccer/websoccer_local_backups/account_transfer/teams/10527301_openai/current --dry-run
```

If local auth fails, do not use Charles/Webサッカー fallback from automation. Fix the OpenAI stored
profile auth path first. Then rerun `fetch_update_core_data.py` without `--dry-run` if new rows were
found.

For old CC scripts and future cleanup criteria, see `scripts/CC_LEGACY_README.md`.
