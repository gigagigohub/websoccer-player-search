# CC Script Status

This file marks which CC update scripts are active and which are compatibility-only.
Keep it near the scripts so future cleanup does not require reconstructing old intent.

## Active Path

Use this entry point for normal CC updates:

```bash
python3 scripts/run_cc_update_pipeline.py --commit-push
```

Current active chain:

1. `run_cc_update_pipeline.py`
2. `fetch_cc_completed_season.py`
3. `update_wsm_cc_from_json.py`
4. `update_site_from_master_db.py`

`run_cc_update_pipeline.py` is responsible for Charles/WebSoccer capture, fresh key detection,
fetch, WSM update, site update, git commit/push, and closing Charles/WebSoccer.

`fetch_cc_completed_season.py` is the canonical CC fetch implementation for completed
group-league and tournament matches.

## Compatibility-Only Scripts

Do not use these for new automation unless there is a specific reason. They are kept temporarily
because older manual commands and chat history may still reference them.

- `fetch_cc_full_season_completed.py`
  - Former one-command wrapper that ran group and tournament fetch scripts separately.
  - Replaced in the active pipeline by `fetch_cc_completed_season.py`.
- `fetch_cc_group_league_completed.py`
  - Former group-league-only fetch implementation.
  - Logic is now folded into `fetch_cc_completed_season.py`.
- `fetch_cc_all_worlds_completed.py`
  - Former tournament fetch implementation.
  - Still provides shared helpers used by current scripts, so do not delete until those helpers are moved.
- `fetch_cc_full_season_with_key_refresh.py`
  - Older attempt at key-refresh orchestration.
  - Replaced by `run_cc_update_pipeline.py`.
- `fetch_cc_match_summaries.py`
  - Older bulk summary fetcher based on captured/list JSON.
  - Not part of the active update pipeline.

## Cleanup Criteria

These scripts can be removed or moved to an archive after all conditions are true:

1. `run_cc_update_pipeline.py --commit-push` has completed a real full CC update at least twice.
2. Fresh Charles/WebSoccer key capture works from a new chat using `docs/cc_update_runbook.md`.
3. WSM update reports complete CC coverage for the target season.
4. Site JSON generation and Top Teams verification pass.
5. No docs, scheduled commands, shell history snippets, or Codex runbooks still call the compatibility-only scripts.
6. Helpers currently imported from `fetch_cc_all_worlds_completed.py` have been moved into a neutral shared module, for example `scripts/cc_fetch_lib.py`.

Recommended cleanup sequence:

1. Move shared helpers out of `fetch_cc_all_worlds_completed.py`.
2. Update imports in `fetch_cc_completed_season.py`, `run_cc_update_pipeline.py`, and any remaining active scripts.
3. Delete or archive the compatibility-only scripts in one commit.
4. Run a dry-run fetch, a small real fetch to a temporary directory, WSM/site verification, then commit/push.

## Last Verified

Verified on 2026-05-27:

- `fetch_cc_completed_season.py` dry-run against saved Charles session worked.
- Small real fetch saved 21/21 JSON files with `code=000` for season `2626`, world `10`.
- WSM/site verification completed for season `2626`.
- Imported CC summary: `1323` matches, `21` worlds, `21` complete worlds.
