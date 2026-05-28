# CC Update Runbook

This runbook is the handoff for a fresh Codex chat. Work in:

```bash
cd /Users/gigagigo/Documents/Codex/websoccer-player-search
```

## One Command

Use this for the normal previous-season CC update:

```bash
python3 scripts/run_cc_update_pipeline.py --commit-push
```

The script launches Charles and WebSoccer, waits for a newly saved Charles session containing
`Websoccer-gate-key`, fetches CC data, updates WSM, regenerates site JSON, then commits and pushes
the generated site changes. After the run finishes, it quits Charles and WebSoccer.

Use `--season 0` when the target is the current season instead of the previous season.

## Weekly Schedule

The installed launchd job runs every Sunday at 02:00 and fetches the current season.
Codex cron automation for this task is paused; launchd is the active scheduler.
Unattended runs use `/Users/gigagigo/work/coding/websoccer-player-search` as the working copy to
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
python3 scripts/run_cc_update_pipeline.py --season 0 --commit-push --quit-first --auto-navigate-websoccer --wait-sec 900 --notify-pushover --reuse-valid-session
```

Logs are written to:

```text
~/Library/Logs/websoccer-player-search/weekly-cc-update.out.log
~/Library/Logs/websoccer-player-search/weekly-cc-update.err.log
```

For fully unattended key capture, the Mac must be logged in with GUI automation available, and
Charles must be able to save the captured session automatically or via its Web Interface. Charles
supports headless mode and a Web Interface for recording/session control; it also has an Auto Save
tool for periodic session saving. If Auto Save is not enabled, the scheduled job may wait for a
saved session until `--wait-sec` expires.

Charles Auto Save is configured on this Mac as:

- Enable Auto Save: on
- Enable on startup: on
- Save interval: 1 minute
- Save to: `/Users/gigagigo/charles_sessions`
- Save type: Charles Session (`.chlz`)

Use this to test only the unattended capture path without fetching/updating data:

```bash
python3 scripts/run_cc_update_pipeline.py \
  --season 0 \
  --quit-first \
  --auto-navigate-websoccer \
  --capture-only \
  --wait-sec 180
```

Verified unattended capture on 2026-05-27 with:

- saved session: `/Users/gigagigo/charles_sessions/charles202605272256.chlz`
- `Websoccer-gate-key`: present
- current-season dry-run: world `10`, group `0`, round max `4`, completed group targets `6`

## Charles / WebSoccer Capture Steps

The key is treated as same-day/short-lived auth. Capture it fresh each time.

Persistent setup expected on this Mac:

- `/Applications/Charles.app`
- `/Applications/Webサッカー.app`
- Charles SSL Proxying includes `api.app.websoccer.jp`
- Charles Root Certificate is trusted in the login keychain
- Saved sessions go under `/Users/gigagigo/charles_sessions`

When the script prints `[ACTION]`, do this:

1. In Webサッカー, press `START`.
2. Close the notice with `OK`.
3. Open `チャンピオンズカップ`.
4. After the CC screen loads, stop Charles Recording.
5. Save the Charles session as `.chlz` under `/Users/gigagigo/charles_sessions`.

The script continues automatically after the saved file contains `Websoccer-gate-key`.

If Charles or WebSoccer is stuck, rerun with:

```bash
python3 scripts/run_cc_update_pipeline.py --quit-first --commit-push
```

If you want to inspect Charles after the run, keep the apps open:

```bash
python3 scripts/run_cc_update_pipeline.py --commit-push --keep-apps-open
```

## Useful Checks

Check only whether the latest saved session can be used:

```bash
python3 scripts/run_cc_update_pipeline.py \
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
~/.websoccer_pushover.env
```

```text
PUSHOVER_APP_TOKEN=...
PUSHOVER_USER_KEY=...
```

The weekly Codex automation passes `--notify-pushover --reuse-valid-session`. The pipeline first
checks whether the newest Charles session passes a lightweight CC API check. It launches
Charles/Webサッカー for fresh auth only when the existing session is missing or stale. If the
Pushover file or variables are missing, the CC update still runs and only the notification is
skipped.

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

`Update_core_data` is tracked separately because it requires fresh Websoccer-gate-key / Cookie /
User-Agent capture from Charles/Webサッカー. Local snapshots live under
`/Users/gigagigo/Documents/Codex/wsc_data/update_core_data_*`.

Use this to verify that a Charles session has API auth without printing the values:

```bash
python3 scripts/fetch_update_core_data.py --auth-check
```

Auth presence alone is not enough. Validate the existing latest local core id explicitly; if it
returns rows, the key is valid:

```bash
python3 scripts/fetch_update_core_data.py --ids <latest-local-core-id> --dry-run
```

Use this to probe from the latest local core player id + 1 after validation:

```bash
python3 scripts/fetch_update_core_data.py --dry-run
```

If no fresh auth exists, capture it first:

```bash
python3 scripts/run_cc_update_pipeline.py \
  --season 0 \
  --quit-first \
  --auto-navigate-websoccer \
  --capture-only \
  --wait-sec 180 \
  --capture-warmup-sec 3
```

Then rerun `fetch_update_core_data.py` without `--dry-run` if new rows were found.

For old CC scripts and future cleanup criteria, see `scripts/CC_LEGACY_README.md`.
