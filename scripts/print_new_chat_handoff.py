#!/usr/bin/env python3
"""Print a copy-paste handoff prompt for a fresh Codex chat."""

from __future__ import annotations

from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]


HANDOFF = f"""作業対象:
 {REPO_ROOT}

前提:
 - Codexの新規作業ディレクトリは空のことがあるので、必ず上記リポジトリへ移動して作業してください
 - Charles継続方針
 - Macには /Applications/Webサッカー.app と /Applications/Charles.app がある
 - Charles保存先は /Users/gigagigo/charles_sessions
 - Charles SSL Proxying には api.app.websoccer.jp を設定済み
 - Charles Auto Save は有効化済み、.chlz を /Users/gigagigo/charles_sessions に保存する設定
 - Websoccer-gate-key / Cookie / User-Agent は短命なので、その日の作業ごとにCharlesで取り直す
 - キーやCookieの実値は表示しないでください
 - 作業ツリーには過去作業の未コミット変更が残っていることがあるので、依頼対象外の変更は触らず、git add は対象ファイルだけにしてください

CCデータ更新の標準フロー:
 1. Charles と Webサッカーを起動
 2. Webサッカーで START → OK/close → チャンピオンズカップ を開く
 3. Charles の .chlz から Websoccer-gate-key / Cookie / User-Agent を抽出
 4. CCデータ取得
 5. WSM更新
 6. サイトJSON更新
 7. git commit / push
 8. 最後に Charles と Webサッカーを終了

通常実行:
 python3 scripts/run_cc_update_pipeline.py --commit-push

今シーズンを取得する場合:
 python3 scripts/run_cc_update_pipeline.py --season 0 --commit-push

キー取得だけ確認する場合:
 python3 scripts/run_cc_update_pipeline.py --season 0 --quit-first --auto-navigate-websoccer --capture-only --wait-sec 180 --capture-warmup-sec 3

週次自動実行:
 - Codex cron は停止し、launchd で毎週日曜 02:00 に現在シーズンを取得する設定
 - LaunchAgent: /Users/gigagigo/Library/LaunchAgents/com.gigagigo.websoccer.cc-current-season-update.plist
 - 作業場所: /Users/gigagigo/work/coding/websoccer-player-search
 - 実体: scripts/run_weekly_cc_current_season_update.sh
 - ログ:
   ~/Library/Logs/websoccer-player-search/weekly-cc-update.out.log
   ~/Library/Logs/websoccer-player-search/weekly-cc-update.err.log

引き継ぎファイル自動更新:
 - Codex cron は停止し、launchd で毎日 05:00 に docs/daily_handoff.md を更新する設定
 - LaunchAgent: /Users/gigagigo/Library/LaunchAgents/com.gigagigo.websoccer.daily-handoff-refresh.plist
 - 作業場所: /Users/gigagigo/work/coding/websoccer-player-search
 - 実体: scripts/run_daily_handoff_refresh.sh
 - ログ:
   ~/Library/Logs/websoccer-player-search/daily-handoff-refresh.out.log
   ~/Library/Logs/websoccer-player-search/daily-handoff-refresh.err.log

主要スクリプト:
 - scripts/run_cc_update_pipeline.py
   Charles/Webサッカー起動、キー取得待ち、CC取得、WSM更新、サイト更新、commit/push、アプリ終了までの統合パイプライン
 - scripts/fetch_cc_completed_season.py
   現行の整理済みCC取得スクリプト
 - scripts/fetch_cc_full_season_completed.py
   互換用ラッパー/旧運用由来
 - scripts/CC_LEGACY_README.md
   古いCC系スクリプトの扱いと削除候補の説明
 - docs/cc_update_runbook.md
   詳細runbook

直近で確認済みのこと:
 - Webサッカー自動操作は START → close → CCクリックまで通る
 - Charles Auto Save の .chlz から api.app.websoccer.jp の Websoccer-gate-key を検出できる
 - capture-only は成功済み
 - パイプラインは完了後に Charles と Webサッカーを終了する

まずやること:
 cd {REPO_ROOT}
 git status --short
 sed -n '1,220p' docs/cc_update_runbook.md
"""


def main() -> int:
    print(HANDOFF)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
