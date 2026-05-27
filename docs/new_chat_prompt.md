# New Chat Startup

This file is the startup instruction for a fresh Codex chat.

## Repository

Work in:

```bash
cd /Users/gigagigo/Documents/Codex/websoccer-player-search
```

Start by running:

```bash
git status --short
sed -n '1,220p' docs/daily_handoff.md
sed -n '1,260p' docs/cc_update_runbook.md
```

## Operating Rules

- Do not print actual Websoccer-gate-key, Cookie, User-Agent, Pushover token, or Pushover user key values.
- Do not touch dirty changes unrelated to the user's current request.
- Do not use `git add .`; stage only intentional files.
- Put one-off analysis HTML/CSV/notebook outputs under `app/prepared/local/`, `local/`, `tmp/`, or `artifacts/`.
- Use `docs/git_hygiene.md` when deciding whether an artifact should be committed or kept local.
- Quit Charles and Webサッカー after workflows that launched them, unless debugging requires leaving them open.

## Standard Commands

Current-season CC update:

```bash
python3 scripts/run_cc_update_pipeline.py --season 0 --commit-push --quit-first --auto-navigate-websoccer --wait-sec 900 --notify-pushover --reuse-valid-session
```

CC capture-only:

```bash
python3 scripts/run_cc_update_pipeline.py --season 0 --quit-first --auto-navigate-websoccer --capture-only --wait-sec 180 --capture-warmup-sec 3
```

UpdateFile watch:

```bash
python3 scripts/watch_updatefile_and_refresh_site.py --commit-push
```

Update_core_data checks:

```bash
python3 scripts/fetch_update_core_data.py --auth-check
python3 scripts/fetch_update_core_data.py --dry-run
```

## Automations

- `websoccer-current-season-cc-weekly-update`
- `websoccer-updatefile-and-core-data-watch`
- `websoccer-daily-handoff-refresh`

After reading this file, use `docs/daily_handoff.md` as the source of truth for the latest state.
