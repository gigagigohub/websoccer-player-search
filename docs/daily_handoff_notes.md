# Daily Handoff Notes

Use this file for durable context learned during chats. `scripts/refresh_daily_handoff.py` includes this content in `docs/daily_handoff.md` on every automatic refresh.

## Operating Notes

- When a chat establishes a durable workflow, unresolved issue, investigation result, or manual decision, add it here instead of editing only `docs/daily_handoff.md`.
- Prefer `python3 scripts/append_daily_handoff_note.py --section "<section>" --note "<note>"` for single-note additions during a chat.
- Do not include Websoccer-gate-key, Cookie, User-Agent, Pushover token, Pushover user key, or other secret values.
- Keep transient command output and scratch analysis out of this file unless it changes future operations.

## Team Creation / League Assignment

- 2026-05-29: For API-only team creation, keep wanted_world_id=0 to match real-device behavior. Generate headcoach_id randomly from existing coach ids. Generate formation_ids randomly from WSM formation ids after excluding formations that have no available coach. Keep player_id explicitly specified until the real-device player list selection logic is understood.
- 2026-05-29: Local CoreData detail: ZMOTEAMDATA.ZLEAGUE is a relationship to ZMOLEAGUE.Z_PK, not the WebSoccer league id. When building or repairing a local profile, set ZLEAGUE to the ZMOLEAGUE.Z_PK row whose ZID equals the server/informal league_id.
- 2026-05-29: Team006 verification: created API-only with selected player_id 1693; server /sync/all returned world=16, season=2627, name=Team006, league=751. Local profile maps ZLEAGUE Z_PK=752 to ZMOLEAGUE.ZID=751, ZCLASS_ID=0, ZGROUP_ID=0, ZGROUP_NAME=エントリーリーグ, and the app displayed エントリーリーグB.
- 2026-05-29: API-only team creation: do not subtract 1 from the league_id returned by /creating_team/informal.json when calling /creating_team/formal.json. Team003-Team005 were affected by the earlier -1 submission; Team006 was created with formal.league_id equal to the informal league_id and is the post-fix control case.
- 2026-05-28: The new-team creation client-side wrong-league submission issue was fixed. Treat Team003-Team005 as pre-fix affected teams.
- 2026-05-28 Team003 evidence: `/sync/all.json` returned `world=9`, `season=2627`, `name=Team003`, `league=400`; `league=400` maps to the previous world's main-league row in local `ZMOLEAGUE`, while world 9 entry league rows are `Z_PK=402` / `ZID=401` and `Z_PK=403` / `ZID=402`.
- User observed Team003-Team005 are displayed as main league A from team detail, but team search, ranking, and actual matches treat them as entry league teams. No fix was observed after the 2026-05-29 morning maintenance. Recheck after the Sunday early-morning promotion/relegation maintenance.
- Team006 is the post-fix control case and is considered correctly created: local `ZMOTEAMDATA` has `Team006`, `world=16`, `league Z_PK=752`, mapping to `ZMOLEAGUE.ZID=751`, `ZCLASS_ID=0`, `ZGROUP_ID=0`, `ZGROUP_NAME=エントリーリーグ`.
- API-only team creation was established in another chat, but the exact reusable runbook is not yet committed here. Known endpoint flow from Charles evidence: `/creating_team/initHP.json`, `/creating_team/checkName.json`, `/creating_team/informal.json`, `/creating_team/status/{uuid}.json`, `/creating_team/formal.json`, then login/sync endpoints. Create a dedicated runbook when that chat's details are available.

## Handoff Operation

- 2026-05-29: Keep the 05:00 automatic daily_handoff refresh for now. Closing prompts should update daily_handoff_notes.md only, without manually rerunning refresh_daily_handoff.py by default; reconsider if missed closing prompts make manual refresh reruns frequent.
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

## API Auth

- 2026-05-29: Local WebSoccer profile can now generate Websoccer-gate-key without launching Webサッカー or Charles. Normal Update_core_data checks and lightweight CC auth validation should prefer local generated auth; Charles/Webサッカー capture is now fallback-only when local auth or reusable sessions fail.

## WSM / Master DB

- 2026-05-29: WSM updates must always create a new copied DB and must not overwrite or mutate prior dated WSM files. Keep past wsm_*.sqlite3 files as backups. Continue using the dated naming convention wsm_yymmddhhss / current 10-digit wsm_YYMMDDHHMM-style filenames; if a timestamp collision occurs, add seconds rather than overwriting.
