# Webサカ 選手能力検索

`caselli.websoccer.info` の選手データを1回スクレイピングし、スマホ向けに能力条件検索できる静的Webアプリです。

## 機能

- 選手名の部分一致検索
- 能力値の複合条件検索（`=` / `>=` / `<=` / 範囲）
- 条件結合の切替（`AND` / `OR`）
- 条件判定は「全期のどこかで満たせば一致」
- 対象能力値: `スピ テク パワ スタ ラフ 個性 人気 PK FK CK CP 知性 感性 個人 組織`
- 並び替え:
  - 名前順
  - 総合値（`スピ + テク + パワ`）昇順/降順
  - 各能力値の昇順/降順

## セットアップ

```bash
cd websoccer-player-search
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

## データ作成（初回のみ）

```bash
python scraper.py --output app/data.json
```

テスト用に件数を減らす場合:

```bash
python scraper.py --output app/data.json --max-pages 2
```

## ローカル起動

`app` ディレクトリを静的配信します。

```bash
cd app
python3 -m http.server 8080
```

ブラウザで `http://localhost:8080` を開いてください。

## GitHub Pages 公開

このリポジトリには `.github/workflows/deploy-pages.yml` を入れてあります。
`main` にpushすると `app/` の中身がGitHub Pagesへ自動デプロイされます。

### 手順

1. GitHubで空のリポジトリを作成（例: `websoccer-player-search`）
2. ローカルで以下を実行

```bash
git init
git branch -M main
git add .
git commit -m "Initial commit"
git remote add origin <あなたのGitHubリポジトリURL>
git push -u origin main
```

3. GitHubのリポジトリ設定で `Settings > Pages` を開く
4. `Build and deployment` の `Source` を `GitHub Actions` にする
5. `Actions` タブで `Deploy to GitHub Pages` が成功したら公開URLが表示される

公開URLは通常次の形式です。
`https://<ユーザー名>.github.io/<リポジトリ名>/`
