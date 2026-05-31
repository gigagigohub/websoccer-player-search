# WebSoccer Account Transfer Runbook

Use this runbook when moving iPhone-managed WebSoccer team accounts into the Mac app.

Current preferred workflow:

1. Prepare the Mac app fresh state.
2. Manually transfer one account in WebSoccer.
3. If another account must be transferred, save or discard the active transferred state intentionally, then prepare fresh state again.

Charles/API replay is not the default path for this work because account transfer is not expected to be a high-frequency workflow.

For the saved local team profile inventory and restore commands, see `docs/websoccer_local_profiles_inventory.md`.

## New Team Identity Defaults

Unless the user explicitly gives different names, new WebSoccer teams created from now on use:

- Team name: random alphabetic 5-10 character string
- Owner/manager name: random alphabetic 5-10 character string

Generate team and owner/manager names separately. They should not intentionally reuse the same
generated value.

Use this helper before manual or API-based team creation:

```bash
python3 scripts/generate_websoccer_new_team_identity.py
```

The names must stay random because WebSoccer rejects already-used names. If
`/creating_team/checkName.json` rejects generated names, generate fresh random values and retry.

For API-based creation plus tutorial completion, use the combined helper:

```bash
python3 scripts/complete_websoccer_tutorial.py --create-team --player-id <initial_player_id> --sync --backup --execute
```

This runs `/creating_team/checkName.json`, `/creating_team/informal.json`, updates the local
profile's team metadata from the informal response, then runs `/creating_team/formal.json` and
`/sync/all.json`. Defaults intentionally match the current policy:

- `team_name`: random alphabetic 5-10 characters, retried on `checkName` rejection unless explicitly supplied
- `owner_name`: random alphabetic 5-10 characters, retried on `checkName` rejection unless explicitly supplied
- `wanted_world_id`: `0`
- `player_id`: explicit only
- `headcoach_id`: random from active WSM coaches unless overridden
- `formation_ids`: 3 random WSM formations with at least one active available coach unless overridden

Run without `--execute` first to inspect the planned payloads.

Current transferred teams are managed as one canonical profile per team:

```text
/Users/gigagigo/Codex/WebSoccer/websoccer_local_backups/account_transfer/teams/<team_id>_<slug>/current
```

When switching ACTIVE from one stored team to another, use:

```bash
python3 scripts/restore_websoccer_current_profile.py --team-id <target_team_id>
```

The script quits WebSoccer, saves the current ACTIVE team's latest data back into its own
`current` profile, stores the previous `current`/ACTIVE copies under `safety_backups/`, restores
the target team's `current` profile, and kills `cfprefsd`. Do not treat `active_before_restore_*`
or `*_previous_current_*` safety backups as the source of truth.

Before moving active `Data` into storage, always inspect the active `Documents/Model/Model.sqlite`
for current team metadata. Team names are editable, so compare the current `ZTEAM_ID` and `ZNAME`
with `docs/websoccer_local_profiles_inventory.md`; if the same team id has a different name,
update the inventory and record the rename in the notes. After storage, run
`scripts/export_websoccer_local_profile_snapshot.py` for that stored profile so future chats can
see team season, world/league, funds, coach, and player list without launching the app. Then run
`scripts/build_websoccer_local_player_index.py` so cross-team player queries can be answered quickly.

Stored profiles can also be refreshed from `/sync/all.json` without launching WebSoccer by running
`scripts/sync_websoccer_local_profile_from_api.py --profile-data <stored-data> --backup`, then
regenerating the profile snapshot and player index.

## Safety Rules

- Do not print or commit transfer codes, Websoccer-gate-key values, Cookie values, User-Agent strings, or other secrets.
- Save Charles logs under `/Users/gigagigo/charles_sessions` or another local-only scratch location.
- Do not use an entirely empty WebSoccer `Data` directory as the final fresh-state setup. The app needs bundled local resources under `Documents/Resources`.
- Keep full container backups before changing the active app state.

## Paths

```text
Container:
~/Library/Containers/jp.novelapproach.WebSoccer

Active data:
~/Library/Containers/jp.novelapproach.WebSoccer/Data

Suggested backup root:
~/Codex/WebSoccer/websoccer_local_backups/account_transfer

Older local profile stash:
/Users/gigagigo/Codex/WebSoccer/websoccer_local_profiles
```

## Confirmed Fresh-State Isolation

This procedure produced a startable fresh app state on 2026-05-30.

1. Quit WebSoccer.
2. Move the current `Data` directory to a timestamped backup.
3. Create a fresh active `Data` directory.
4. Copy only these items back from the backup:
   - `Documents/Resources`
   - `StoreKit/receipt`
5. Do not restore `Documents/Model`.
6. Delete the `jp.novelapproach.WebSoccer` UserDefaults domain.
7. Kill `cfprefsd`.
8. Verify local-profile auth generation fails, because `Model.sqlite` should be absent.
9. Start WebSoccer and confirm the app can reach the new-start or transfer flow.

Example command shape:

```bash
APP_DOMAIN='jp.novelapproach.WebSoccer'
CONTAINER="$HOME/Library/Containers/$APP_DOMAIN"
DATA="$CONTAINER/Data"
STAMP="$(date +%Y%m%d_%H%M%S)"
BACKUP_ROOT="$HOME/Codex/WebSoccer/websoccer_local_backups/account_transfer"
BACKUP="$BACKUP_ROOT/WebSoccer_Data_before_transfer_${STAMP}"

osascript -e 'tell application "Webサッカー" to quit' >/dev/null 2>&1 || true
mkdir -p "$BACKUP_ROOT"
mv "$DATA" "$BACKUP"
mkdir -p "$DATA/Documents" "$DATA/Library" "$DATA/tmp"
cp -a "$BACKUP/Documents/Resources" "$DATA/Documents/Resources"
cp -a "$BACKUP/StoreKit" "$DATA/StoreKit"
defaults delete "$APP_DOMAIN" >/dev/null 2>&1 || true
killall cfprefsd >/dev/null 2>&1 || true
chmod 700 "$DATA"
```

Then check:

```bash
python3 scripts/fetch_update_core_data.py --auth-source local --auth-check
test ! -e "$HOME/Library/Containers/jp.novelapproach.WebSoccer/Data/Documents/Model/Model.sqlite"
```

The auth check should fail when the local profile has been isolated correctly.

## Charles Capture

This is optional investigation work, not the normal transfer workflow.

1. Start Charles Recording.
2. Clear the current Charles session if old traffic would make analysis noisy.
3. Launch WebSoccer.
4. From the fresh state, perform the account transfer manually.
5. Continue until the transferred team is visible in the app.
6. Save the session as `.chlz`.

Suggested filename:

```text
/Users/gigagigo/charles_sessions/websoccer_account_transfer_<team-or-purpose>_<yyyymmddhhmm>.chlz
```

Share only the `.chlz` path in chat, not secret values from the captured requests.

## Restore Previous Local State

To restore the prior Mac local team state, quit WebSoccer, move the active `Data` aside, then move the timestamped full backup back to:

```text
~/Library/Containers/jp.novelapproach.WebSoccer/Data
```

After restore, kill `cfprefsd` if the app appears to reuse stale preferences.

## Known Failed Intermediate Attempt

Moving the whole `Data` directory aside and leaving an empty `Data` directory was not sufficient. The app recreated some preferences/cache directories, but the resulting state could fail around app start or `START` because `Documents/Resources` was missing.
