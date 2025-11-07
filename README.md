# 競馬データベース 🐴

JRA（日本中央競馬会）サイトから競馬データをスクレイピングし、SQLiteに蓄積して、Streamlitで可視化するシステムです。

## 機能

- **データ取得**: JRAサイトのレース情報をスクレイピング
- **データ蓄積**: SQLiteデータベースに効率的に保存
- **指標計算**: 馬の勝率、連対率、複勝率、近走指数などを自動計算
- **可視化**: Streamlitでインタラクティブにデータを閲覧
- **自動更新**: GitHub Actionsで週次更新を自動実行

## システム構成

```
repo/
  app/                           # Streamlitアプリケーション
    Home.py                      # ホームページ
    pages/
      Race.py                    # レース詳細ページ
      Horse.py                   # 馬詳細ページ
    lib/
      db.py                      # DB接続・クエリ
      queries.py                 # キャッシュ付きクエリ
      charts.py                  # グラフ生成

  scraper/                       # スクレイピング機能
    selectors.py                 # HTML選択子管理
    rate_limit.py                # レート制限・再試行
    fetch_calendar.py            # レースカレンダー取得
    fetch_card.py                # 出馬表取得
    fetch_result.py              # 結果取得

  etl/                           # ETL処理
    base.py                      # 基本クラス
    upsert_master.py             # マスタデータ管理
    upsert_race.py               # レース情報管理
    upsert_entry.py              # 出走情報管理
    apply_alias.py               # 名称ゆれ補正

  metrics/                       # 指標計算
    build_horse_metrics.py       # 馬の指標計算

  sql/
    schema.sql                   # SQLスキーマ

  data/
    keiba.db                     # SQLiteデータベース
    logs/                        # スクレイピングログ

  .github/workflows/
    backfill.yml                 # 初回一括取得ワークフロー
    weekly_cards.yml             # 週次出馬表取得
    weekly_results.yml           # 週次結果取得＋指標計算
```

## インストール

### 前提条件

- Python 3.11以上
- Git

### セットアップ

```bash
# リポジトリをクローン
git clone <repo-url>
cd keiba-solo-db

# 依存関係をインストール
pip install -r requirements.txt

# データベーススキーマを初期化
python -c "from app.lib import db; db.init_schema()"
```

## 使い方

### 1. 初回データ取得（一括）

GitHub Actionsで手動実行:

1. GitHubのリポジトリを開く
2. **Actions** → **backfill** ワークフローを選択
3. **Run workflow** をクリック
4. 開始年度と終了年度を入力（例: 2019-2024）
5. **Run workflow** を実行

または、ローカルで実行:

```bash
python -m scraper.fetch_calendar --start 2019 --end 2024
python -m scraper.fetch_card --years 2019 2020 2021 2022 2023 2024
python -m scraper.fetch_result --years 2019 2020 2021 2022 2023 2024
python -m etl.upsert_master
python -m etl.upsert_race
python -m etl.upsert_entry
python -m etl.apply_alias
python -m metrics.build_horse_metrics
```

### 2. Streamlitアプリを起動

```bash
streamlit run app/Home.py
```

ブラウザが開き、http://localhost:8501 でアプリが表示されます。

### 3. 週次自動更新

GitHub Actionsで以下のスケジュールで自動実行:

- **出馬表**: 土曜朝6:00 JST
- **結果**: 日曜23:30, 月曜6:00 JST

データベースとコミットは自動的に更新されます。

## データベース設計

### テーブル構成

#### マスタデータ
- `horses` - 馬情報（名前、性別、生年）
- `jockeys` - 騎手情報
- `trainers` - 調教師情報
- `alias_horse`, `alias_jockey`, `alias_trainer` - 名称ゆれ補正用

#### トランザクションデータ
- `races` - レース情報（日付、開催場、距離、馬場など）
- `race_entries` - 出走情報（枠番、馬番、騎手、結果など）

#### 指標データ
- `horse_metrics` - 馬の成績指標（勝率、連対率、近走指数など）

## 指標の定義

### 基本指標

- **勝率**: 1着数 / 総出走数
- **連対率**: (1着数 + 2着数) / 総出走数
- **複勝率**: (1着数 + 2着数 + 3着数) / 総出走数

### 近走指数

直近5走を対象に、着順と人気から計算:

```
近走指数 = Σ(着順点 × 古さの重み × 人気係数)

着順点: 1着=5点, 2着=3点, 3着=2点, 着外=0点
古さの重み: 新しいレースほど1.0に近い
人気係数: 人気が高いほど0.75-1.0の範囲
```

### 距離別・馬場別成績

各距離・馬場での出走数、勝利数、連対数をJSON形式で保存。

## 注意事項

### 法的・運用上の注意

- **利用規約確認**: JRAの利用規約とrobots.txtを確認してからご利用ください
- **可否が不明な場合**: スクレイピング前に必ず確認してください
- **禁止の場合**: 処理を中止できるよう実装分岐を用意しています

### パフォーマンス

- **レート制限**: JRA側への負荷軽減のため、リクエスト間に自動待機を挿入
- **キャッシング**: Streamlitのキャッシュで読み込み性能を向上
- **VACUUM**: データベース断片化を定期的に最適化

## トラブルシューティング

### HTMLパースが失敗する

JRAサイトの構造が変わった可能性があります:

1. `scraper/selectors.py` のセレクタを確認・修正
2. `data/logs/` に保存されたエラーログを確認
3. ブラウザでJRAサイトの実際のHTML構造を確認

### データベースエラー

```bash
# スキーマ検証
sqlite3 data/keiba.db ".schema"

# スキーマをリセット（注意: データが削除されます）
rm data/keiba.db
python -c "from app.lib import db; db.init_schema()"
```

### Streamlit起動エラー

```bash
# キャッシュをクリア
streamlit cache clear

# 依存関係を確認
pip install -r requirements.txt --upgrade
```

## 開発ガイド

### 新機能を追加する

1. **新しいクエリ**: `app/lib/queries.py` に追加
2. **新しいグラフ**: `app/lib/charts.py` に追加
3. **新しいページ**: `app/pages/` に新規ファイルを作成
4. **スクレイパー変更**: `scraper/selectors.py` でセレクタを集約管理

### テストと確認

```bash
# ローカルでワークフローをシミュレート
python -m etl.upsert_master
python -m etl.upsert_race
python -m etl.upsert_entry
python -m metrics.build_horse_metrics

# Streamlitで動作確認
streamlit run app/Home.py
```

## ライセンス

MIT License

## 更新履歴

- **2024-11**: 初版実装完了
  - スクレイパー実装
  - ETL処理実装
  - Streamlitアプリ実装
  - GitHub Actions自動化

## サポート

問題や質問がある場合:

1. `data/logs/` のエラーログを確認
2. GitHub Issues で報告
3. Discussionsで質問

---

**お断り**: JRAのデータ利用にあたり、利用規約への準拠をご確認ください。
