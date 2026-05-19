# Scripts

用途別の目録です。ファイル移動は既存の呼び出しパスを壊しやすいため、現状はこの分類で管理します。

## Site Update

- `update_site_from_master_db.py` - master DB から `app/data.json` などのサイトデータを生成する。
- `export_site_json_from_master_db.py` - master DB からサイト向け JSON を出力する。
- `prepare_formations_page_data.py` - フォーメーションページ用データを整形する。
- `prepare_collections_data.py` - Collections のユニフォーム・エンブレム表示データを生成する。
- `write_site_meta.py` - サイト更新日時などのメタ情報を書き出す。

## Master DB

- `build_websoccer_master_db.py` - WSM master DB を構築する。
- `collect_updatefile_inventory.py` - UpdateFile の中身を棚卸しする。
- `fetch_updatefiles.py` - UpdateFile を取得する。
- `link_challenge_history.py` - ChallengeMatch 系 plist を master DB に反映する。
- `link_scout_history.py` - Scout 系データを master DB に反映する。
- `migrate_player_person_identity.py` - player/person identity の移行補助。
- `refresh_coach_obtainable_from_rohm.py` - 監督取得可否情報を Rohm 由来で更新する。

## CC Data

- `fetch_cc_all_worlds_completed.py` - CC 全ワールドの完了済みデータ取得。
- `fetch_cc_full_season_completed.py` - CC シーズン単位の完了済みデータ取得。
- `fetch_cc_group_league_completed.py` - CC グループリーグ取得。
- `fetch_cc_match_summaries.py` - CC 試合サマリ取得。
- `ingest_cc_match_result_db.py` - CC 試合結果 JSON を DB 化する。
- `ingest_cc_pk_into_master_db.py` - PK 結果補正を master DB に反映する。
- `update_cc_site_data.py` - CC 由来のサイト表示データを更新する。
- `update_wsm_cc_from_json.py` - CC JSON から WSM を更新する。
- `build_cc_match_result_csv.py` - CC 試合結果 CSV を生成する。
- `build_cc_range_data.py` - CC 表示用の範囲データを生成する。

## TPI / Analysis

- `build_v4_slot_adjusted_team_power.py` - TPI/GDI 係数再推計と関連データ生成。
- `analyze_cc_team_power_logic.py` - チームパワー指標の分析。
- `analyze_cc_world_strength.py` - ワールド別強度分析。
- `build_rohm_slot_data.py` - Rohm slot ranking データの生成。

## Player Data

- `assign_categories_for_ios_data.py` - iOS データ由来の選手カテゴリ付与。
- `import_ios_dataset_to_site.py` - iOS データセットのサイト取り込み。
- `prepare_ios_source_data.py` - iOS ソースデータの整形。
- `reclassify_by_zero_lifecycle.py` - lifecycle 由来のカテゴリ再分類。

## Trade Data

- `fetch_trade_comments_for_top_demand.py` - トレード需要コメント取得。
- `fetch_trade_search_all_ids.py` - トレード検索データ取得。
