# WebSoccer Ordinary / websoccer-player-search

WebSoccer 向けの **静的データ閲覧アプリ**と、配信用 JSON を生成する **データ更新スクリプト群**をまとめたリポジトリです。  
フロントエンドは `app/` 配下の素の HTML/CSS/JavaScript で構成されています。

---

## できること

### 1) Players ページ（`app/index.html`）
- 選手名 / モデル選手 / タイプの検索
- ポジション（GK/DF/MF/FW）フィルタ
- 適正エリア（=7 / >=6）フィルタ
- カテゴリ別フィルタ（NR/CC/SS/CM、引退選手の含有切替）
- 複数パラメータ条件検索（ID・主要能力・適正値）
- TeamID ログイン連携でスタメン/後継登録導線

### 2) Coaches ページ（`app/coaches.html`）
- 監督名検索
- タイプ（超攻撃型〜超守備型）フィルタ
- 使用可能フォーメーション / 理解フォーメーション絞り込み

### 3) Formations ページ（`app/formations.html`）
- フォーメーション名検索
- ソートキー切替
- 対応監督（使用可能/理解）での絞り込み
- スロット詳細や相性表示モーダル

### 4) My Team ページ（`app/myteam.html`）
- TeamID 単位での編成管理
- スタメン / リザーブ / 監督 / フォーメーション編集
- シーズン進行（+1 / -1）を含む Cycle Management 導線

---

## ディレクトリ構成（主要）

```text
app/                # 静的サイト本体（HTML/CSS/JS + 生成済みJSON + 画像）
data/               # 補助CSV（オーバーライド定義など）
scripts/            # データ生成・更新・分析スクリプト
requirements.txt    # Python依存
```

補足:
- `app/data.json` / `app/coaches_data.json` / `app/formations_data.json` などをフロントエンドが直接読み込みます。
- `app/site_meta.json` は更新日時などのメタ情報です。

---

## セットアップ

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

---

## ローカル起動

```bash
cd app
python3 -m http.server 8080
```

ブラウザで `http://localhost:8080` を開いてください。

---

## データ更新フロー（現在の主経路）

現在の標準は、マスタ DB からサイト用 JSON を再生成するフローです。

```bash
python3 scripts/update_site_from_master_db.py \
  --master-db /path/to/wsm_xxxxxxxxxx.sqlite3 \
  --out-app-dir ./app
```

`update_site_from_master_db.py` は主に以下を実行します。
1. `scripts/export_site_json_from_master_db.py`（選手/監督系JSONの生成）
2. `scripts/prepare_formations_page_data.py`（フォーメーションページ用JSONの生成）
3. `scripts/write_site_meta.py`（メタ情報更新）

`--master-db` を省略した場合は、`--wsm-dir` から最新 `wsm_*.sqlite3` を探索して使用します。

---

## 旧フロー（互換）

必要に応じて legacy 更新フローも呼び出せます。

```bash
python3 scripts/update_site_from_master_db.py --fallback-legacy
```

---

## 注意事項

- 本リポジトリは画像アセットを多数含むため、クローン/差分取得が大きくなります。
- 生成済み JSON をコミット運用する想定のため、データ更新時は `app/*.json` の差分が発生します。
- フロントはビルドレス運用（Node.js 必須ではありません）。

---

## ライセンス

必要に応じて追記してください（現状は明示ライセンスファイル未同梱）。
