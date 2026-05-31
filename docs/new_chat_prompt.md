# New Chat Startup

This file is the startup instruction for a fresh Codex chat.

## Repository

Work in:

```bash
cd /Users/gigagigo/Codex/WebSoccer/websoccer-player-search
```

Start by running:

```bash
git status --short
sed -n '1,220p' docs/daily_handoff.md
sed -n '1,220p' docs/daily_handoff_notes.md
sed -n '1,260p' docs/cc_update_runbook.md
```

## Operating Rules

- Do not print actual Websoccer-gate-key, Cookie, User-Agent, Pushover token, or Pushover user key values.
- Do not touch dirty changes unrelated to the user's current request.
- Do not use `git add .`; stage only intentional files.
- Put one-off analysis HTML/CSV/notebook outputs under `app/prepared/local/`, `local/`, `tmp/`, or `artifacts/`.
- Use `docs/git_hygiene.md` when deciding whether an artifact should be committed or kept local.
- `docs/daily_handoff.md` is auto-generated. Add durable chat findings, workflow decisions, and unresolved investigations to `docs/daily_handoff_notes.md`; the daily refresh includes that file.
- During each chat, append durable findings to `docs/daily_handoff_notes.md` as soon as they become clear. Prefer `python3 scripts/append_daily_handoff_note.py --section "<section>" --note "<note>"` for single-note additions.
- Quit Charles and Webサッカー after workflows that launched them, unless debugging requires leaving them open.
- For WebSoccer account-transfer or local fresh-state work, use `docs/account_transfer_runbook.md`; append-only handoff notes are not enough for this risky recurring procedure.
- For restoring or locating saved local WebSoccer team profiles, use `docs/websoccer_local_profiles_inventory.md`.
- For switching between managed transferred teams, prefer `python3 scripts/restore_websoccer_current_profile.py --team-id <target_team_id>` so the outgoing ACTIVE team is saved back to its canonical `teams/<team>/current` profile before restore.

## Standard Commands

Current-season CC update:

```bash
python3 scripts/run_cc_update_pipeline.py --websoccer-container /Users/gigagigo/Codex/WebSoccer/websoccer_local_backups/account_transfer/teams/10527301_openai/current --season 0 --commit-push --notify-pushover
```

CC local-auth dry-run check:

```bash
python3 scripts/run_cc_update_pipeline.py --websoccer-container /Users/gigagigo/Codex/WebSoccer/websoccer_local_backups/account_transfer/teams/10527301_openai/current --auth-source local --skip-capture --season 0 --worlds 10 --groups 0 --round-max 1 --dry-run-fetch --skip-wsm-update
```

UpdateFile watch:

```bash
python3 scripts/watch_updatefile_and_refresh_site.py --commit-push
```

Update_core_data checks:

```bash
python3 scripts/fetch_update_core_data.py --websoccer-container /Users/gigagigo/Codex/WebSoccer/websoccer_local_backups/account_transfer/teams/10527301_openai/current --auth-check
python3 scripts/fetch_update_core_data.py --websoccer-container /Users/gigagigo/Codex/WebSoccer/websoccer_local_backups/account_transfer/teams/10527301_openai/current --dry-run
```

## Automations

- Codex cron active: none
- Codex cron paused: `websoccer-daily-handoff-refresh`, `websoccer-current-season-cc-weekly-update`, `websoccer-updatefile-and-core-data-watch`
- LaunchAgents active: `com.gigagigo.websoccer.daily-handoff-refresh`, `com.gigagigo.websoccer.cc-current-season-update`, `com.gigagigo.websoccer.updatefile-core-watch`

After reading this file, use `docs/daily_handoff.md` as the source of truth for the latest state.
