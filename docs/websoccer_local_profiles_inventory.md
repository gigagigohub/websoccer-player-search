# WebSoccer Local Profiles Inventory

This file is the durable map for local WebSoccer Mac profiles that can be restored when the user wants to call up a specific team.

## Canonical Policy

- New profile backups for account transfer work should go under:

```text
/Users/gigagigo/Codex/WebSoccer/websoccer_local_backups/account_transfer
```

- Current iPhone-managed team profiles are now organized as one canonical current profile per
  team:

```text
/Users/gigagigo/Codex/WebSoccer/websoccer_local_backups/account_transfer/teams/<team_id>_<slug>/current
```

- Restore teams from `teams/<team_id>_<slug>/current`, not from timestamped safety backups.
- Before switching away from an active team, update that team's `current` profile from ACTIVE.
  Use `scripts/restore_websoccer_current_profile.py --team-id <target_team_id>` for normal
  switching; it saves ACTIVE into its team's `current` first, then restores the target team.
- Timestamped `active_before_restore_*` and `*_previous_current_*` directories are safety
  backups only. They live under:

```text
/Users/gigagigo/Codex/WebSoccer/websoccer_local_backups/account_transfer/safety_backups
```

- Safety backups can be pruned after the latest `current` profile has been verified, because
  they are not the source of truth.
- Older profiles are still valid and live under:

```text
/Users/gigagigo/Codex/WebSoccer/websoccer_local_profiles
```

- Do not move old profile directories casually. Some notes and prior chats refer to their current paths.
- Do not print or commit UUID, Websoccer-gate-key, Cookie, transfer codes, or other secrets.
- Team names are user-editable. Every time active `Data` is moved into storage, read the current `ZMOTEAMDATA.ZTEAM_ID`, `ZMOTEAMDATA.ZNAME`, `ZMOTEAMDATA.ZOWNER_NAME`, `ZMOTEAMDATA.ZSZN`, and `ZMOTEAMDATA.ZLEAGUE` from the active `Model.sqlite` before resetting the app. If the same team id already exists here with a different name, update this inventory and note the rename in the row notes.
- Every stored team profile should have a `profile_snapshot/` directory generated with `scripts/export_websoccer_local_profile_snapshot.py`. The snapshot includes safe metadata, current team season, world/league names, funds, coach, player list, and player acquired-season counts.
- After generating per-profile snapshots, run `scripts/build_websoccer_local_player_index.py` to refresh the cross-team player index. This supports later questions like "Which team has ラミレス, and what term is he in?" without launching WebSoccer.
- Run `scripts/build_websoccer_local_roster_report.py` after refreshing the player index to generate a small-image roster HTML for visual player/category checks. The report uses a local `app-images` symlink so player images load through the same localhost server, and it mirrors site category badges from `app/data.json`.

## Active App Paths

```text
Container:
/Users/gigagigo/Library/Containers/jp.novelapproach.WebSoccer

Active Data:
/Users/gigagigo/Library/Containers/jp.novelapproach.WebSoccer/Data

Active Model:
/Users/gigagigo/Library/Containers/jp.novelapproach.WebSoccer/Data/Documents/Model/Model.sqlite

Active Preferences:
/Users/gigagigo/Library/Containers/jp.novelapproach.WebSoccer/Data/Library/Preferences/jp.novelapproach.WebSoccer.plist
```

## Profile Layout Types

There are two observed backup layouts.

### Full Data Layout

The backup directory itself is a complete `Data` directory and contains paths such as:

```text
Documents/Model/Model.sqlite
Documents/Resources
Library/Preferences/jp.novelapproach.WebSoccer.plist
StoreKit/receipt
```

Restore by replacing the active `Data` directory with the backup directory.

### Compact Profile Layout

The backup directory contains only profile-specific files:

```text
Model/Model.sqlite
Preferences/jp.novelapproach.WebSoccer.plist
```

Restore by copying those into the active `Data` directory while preserving active `Documents/Resources`.

## Known Profiles

| Label | Team / Owner | Team ID | League Field | Layout | Path | Notes |
|---|---:|---:|---:|---|---|---|
| Current pre-transfer backup | Team006 / Owner006 | 10533601 | 752 | Full Data | `/Users/gigagigo/Codex/WebSoccer/websoccer_local_backups/account_transfer/WebSoccer_Data_before_transfer_20260530_092648` | Backup made before 2026-05-30 transfer work. |
| はたのっちFC 99 | はたのっちFC 99 / ギガギゴ. | 10052201 | 37 | Full Data current | `/Users/gigagigo/Codex/WebSoccer/websoccer_local_backups/account_transfer/teams/10052201_hatanocchi/current` | First manually transferred iPhone-managed team. Old `transferred_team_10052201_owner_gigagigo_20260530_095234` path is a compatibility symlink. |
| 中村サッカー倶楽部 | 中村サッカー倶楽部 / ナカムラマサト | 9725201 | 434 | Full Data current | `/Users/gigagigo/Codex/WebSoccer/websoccer_local_backups/account_transfer/teams/9725201_nakamura/current` | Manually transferred iPhone-managed team. Snapshot and player index generated. Old `transferred_team_9725201_nakamura_soccer_club_20260530_101600` path is a compatibility symlink. |
| エドリアーノ強くねか | エドリアーノ強くねか / オグエトシミツ | 9737901 | 532 | Full Data current | `/Users/gigagigo/Codex/WebSoccer/websoccer_local_backups/account_transfer/teams/9737901_edriano/current` | Manually transferred iPhone-managed team. Snapshot and player index generated. Old `transferred_team_9737901_edriano_20260530_102118` path is a compatibility symlink. |
| FC虹 | FC虹 / マルヤマダイチ | 9710901 | 888 | Full Data current | `/Users/gigagigo/Codex/WebSoccer/websoccer_local_backups/account_transfer/teams/9710901_fc_niji/current` | Manually transferred iPhone-managed team. Snapshot and player index generated. Old `transferred_team_9710901_fc_niji_20260530_102433` path is a compatibility symlink. |
| Failed empty attempt | Team006 prefs only | - | - | Partial/failed | `/Users/gigagigo/Codex/WebSoccer/websoccer_local_backups/account_transfer/WebSoccer_Data_failed_empty_attempt_20260530_092951` | Intermediate failed empty-Data attempt. Do not use as a team restore source. |
| OpenAI | OpenAI / Codex | 10527301 | 453 | Full Data current | `/Users/gigagigo/Codex/WebSoccer/websoccer_local_backups/account_transfer/teams/10527301_openai/current` | Migrated from old `websoccer_local_profiles/current_backup_20260528_193455`; canonical source for restores. |
| Team001 | Team001 / Owner001 | 10531801 | 452 | Full Data current | `/Users/gigagigo/Codex/WebSoccer/websoccer_local_backups/account_transfer/teams/10531801_team001/current` | Migrated from old `websoccer_local_profiles/team001_20260528_195600`; canonical source for restores. |
| Team002 | Team002 / Owner002 | 10532301 | 702 | Full Data current | `/Users/gigagigo/Codex/WebSoccer/websoccer_local_backups/account_transfer/teams/10532301_team002/current` | Migrated from old compact profile and normalized with Resources/StoreKit. |
| Team003 tutorial complete | Team003 / Owner003 | 10532501 | 401 | Full Data current | `/Users/gigagigo/Codex/WebSoccer/websoccer_local_backups/account_transfer/teams/10532501_team003/current` | Migrated from old `team003_tutorial_complete`; stale Team002 display prefs corrected. Old API-only zero-player profile is retained only as legacy evidence. |
| Team004 API | Team004 / Owner004 | 10532801 | 501 | Full Data current | `/Users/gigagigo/Codex/WebSoccer/websoccer_local_backups/account_transfer/teams/10532801_team004/current` | Migrated from old compact profile and stale Team002 display prefs corrected. |
| Team005 API | Team005 / Owner005 | 10533001 | 801 | Full Data current | `/Users/gigagigo/Codex/WebSoccer/websoccer_local_backups/account_transfer/teams/10533001_team005/current` | Migrated from old compact profile and stale Team002 display prefs corrected. |
| Team006 API fixed | Team006 / Owner006 | 10533601 | 752 | Full Data current | `/Users/gigagigo/Codex/WebSoccer/websoccer_local_backups/account_transfer/teams/10533601_team006/current` | Migrated from old compact profile; post-fix control profile and canonical source for restores. |
| 義務ジノラ API | 義務ジノラ / ムツヘケユカツ | 10551401 | 952 | Full Data current | `/Users/gigagigo/Codex/WebSoccer/websoccer_local_backups/account_transfer/teams/10551401_gimu_ginola/current` | Migrated from old `websoccer_local_profiles/gimu_ginola_10551401_20260530_185718`; canonical source for restores. |
| OpenAI stashed current | OpenAI / Codex | 10527301 | 452 | Full Data | `/Users/gigagigo/Codex/WebSoccer/websoccer_local_profiles/stashed_current_20260528_193455` | Older backup. |
| OpenAI cfprefsd test | OpenAI / Codex | 10527301 | 452 | Full Data | `/Users/gigagigo/Codex/WebSoccer/websoccer_local_profiles/stashed_cfprefsd_test_20260528_193701` | Used in cfprefsd/defaults testing. |
| Pre-Team002 backup | OpenAI / Codex | 10527301 | 452 | Compact | `/Users/gigagigo/Codex/WebSoccer/websoccer_local_profiles/pre_team002_backup_20260528_213115` | Older compact profile. |
| Incomplete attempt | OwnerName, team id 0 | 0 | - | Full Data | `/Users/gigagigo/Codex/WebSoccer/websoccer_local_profiles/incomplete_attempt_20260528_195154` | Incomplete/new-team attempt. |

## Restore A Full Data Profile

Use this when the inventory row says `Full Data`.

For the managed iPhone-transferred teams above, prefer:

```bash
python3 scripts/restore_websoccer_current_profile.py --team-id 9710901
```

This saves the currently active registered team into its own `teams/<team>/current` profile before
restoring the requested team. Use the manual restore below only for older profiles or one-off
recovery.

```bash
APP_DOMAIN='jp.novelapproach.WebSoccer'
CONTAINER="$HOME/Library/Containers/$APP_DOMAIN"
DATA="$CONTAINER/Data"
PROFILE='/absolute/path/to/full-data-profile'
STAMP="$(date +%Y%m%d_%H%M%S)"
SAVE="$HOME/Codex/WebSoccer/websoccer_local_backups/account_transfer/active_before_restore_${STAMP}"

osascript -e 'tell application "Webサッカー" to quit' >/dev/null 2>&1 || true
mkdir -p "$(dirname "$SAVE")"
mv "$DATA" "$SAVE"
cp -a "$PROFILE" "$DATA"
killall cfprefsd >/dev/null 2>&1 || true
```

Do not run `defaults delete "$APP_DOMAIN"` after restoring a full profile. That can remove the restored profile preferences, including the UUID needed for app-less API auth. Killing `cfprefsd` is enough.

## Restore A Compact Profile

Use this when the inventory row says `Compact`.

This keeps the currently active `Documents/Resources` and swaps only `Model` and app preferences.

```bash
APP_DOMAIN='jp.novelapproach.WebSoccer'
DATA="$HOME/Library/Containers/$APP_DOMAIN/Data"
PROFILE='/absolute/path/to/compact-profile'
STAMP="$(date +%Y%m%d_%H%M%S)"
SAVE="$HOME/Codex/WebSoccer/websoccer_local_backups/account_transfer/active_profile_bits_before_restore_${STAMP}"

osascript -e 'tell application "Webサッカー" to quit' >/dev/null 2>&1 || true
mkdir -p "$SAVE"
mkdir -p "$DATA/Documents" "$DATA/Library/Preferences"
if [ -d "$DATA/Documents/Model" ]; then
  mv "$DATA/Documents/Model" "$SAVE/Model"
fi
if [ -f "$DATA/Library/Preferences/jp.novelapproach.WebSoccer.plist" ]; then
  mkdir -p "$SAVE/Preferences"
  mv "$DATA/Library/Preferences/jp.novelapproach.WebSoccer.plist" "$SAVE/Preferences/"
fi
cp -a "$PROFILE/Model" "$DATA/Documents/Model"
cp -a "$PROFILE/Preferences/jp.novelapproach.WebSoccer.plist" "$DATA/Library/Preferences/jp.novelapproach.WebSoccer.plist"
defaults delete "$APP_DOMAIN" >/dev/null 2>&1 || true
killall cfprefsd >/dev/null 2>&1 || true
```

## Prepare Fresh State For Next Manual Transfer

Use `docs/account_transfer_runbook.md`. The key point is:

- Preserve or restore `Documents/Resources`.
- Preserve `StoreKit/receipt`.
- Remove `Documents/Model`.
- Delete the `jp.novelapproach.WebSoccer` UserDefaults domain.
- Kill `cfprefsd`.

Do not leave active `Data` completely empty as the final state.

## Export Profile Snapshot

Run this immediately after moving active `Data` into storage:

```bash
python3 scripts/export_websoccer_local_profile_snapshot.py --profile-data /absolute/path/to/stored-profile-data
```

The script writes:

```text
profile_snapshot/summary.json
profile_snapshot/players.csv
```

Then refresh the cross-team player index:

```bash
python3 scripts/build_websoccer_local_player_index.py
python3 scripts/build_websoccer_local_roster_report.py
```

The index is written to:

```text
/Users/gigagigo/Codex/WebSoccer/websoccer_local_backups/account_transfer/_index/players_index.json
/Users/gigagigo/Codex/WebSoccer/websoccer_local_backups/account_transfer/_index/players_index.csv
/Users/gigagigo/Codex/WebSoccer/websoccer_local_backups/account_transfer/_index/rosters.html
```

For one-click viewing in Codex, serve the index directory over localhost and open the HTTP URL:

```bash
cd /Users/gigagigo/Codex/WebSoccer/websoccer_local_backups/account_transfer/_index
python3 -m http.server 8765 --bind 127.0.0.1
```

Then open:

```text
http://127.0.0.1:8765/rosters.html
```

Do not rely on `file://` for the in-app browser; it may be blocked by browser policy.

## Refresh Stored Profile From API

For a stored profile that still has a valid UUID/team id in its local data, update it from
`/sync/all.json` without launching WebSoccer:

```bash
PROFILE=/absolute/path/to/stored-profile-data
python3 scripts/sync_websoccer_local_profile_from_api.py --profile-data "$PROFILE" --backup
python3 scripts/export_websoccer_local_profile_snapshot.py --profile-data "$PROFILE"
python3 scripts/build_websoccer_local_player_index.py
```

This currently updates the stored SQLite profile for:

- `ZMOTEAMDATA`
- `ZMOTEAMFUNDS`
- `ZMOTEAMSPLAYER`
- `ZMOTEAMSPLAYERRESULT`
- `ZMOTEAMSHEADCOACH`
- collection album tables for players, headcoaches, formations, emblems, uniforms, and stadiums

The script prints only safe response metadata and does not print generated auth values.
