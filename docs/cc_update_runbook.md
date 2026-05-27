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
