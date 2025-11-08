# 競馬データベース 🐴

JRA（日本中央競馬会）サイトから競馬データをスクレイピングし、SQLiteに蓄積して、Streamlitで可視化するシステムです。

## 機能

- **データ取得**: JRAサイトから過去データと将来のレース情報をスクレイピング
- **データ蓄積**: SQLiteデータベースに自動的に蓄積・管理
- **指標計算**: 馬の勝率、連対率、複勝率、近走指数などを自動計算
- **可視化**: Streamlitでインタラクティブにデータを閲覧
- **機械学習予測**: Random Forest + LightGBMで競馬の勝馬を予測
- **ベッティング最適化**: Kelly Criterionで最適な賭け金を計算

## システム構成

```
keiba-solo-db/
  app/                           # Streamlitアプリケーション
    Home.py                      # ホームページ
    pages/
      1_Race.py                  # レース詳細ページ
      2_FutureRaces.py           # 将来レース＆予測
      3_Horse.py                 # 馬詳細ページ
      4_ModelTraining.py         # モデル訓練
      5_Prediction.py            # 予測実行
      6_Betting.py               # ベッティング最適化
    db.py                        # DB接続・クエリ
    queries.py                   # キャッシュ付きクエリ
    charts.py                    # グラフ生成
    features.py                  # 特徴量エンジニアリング
    prediction_model.py          # Random Forest モデル
    prediction_model_lightgbm.py # LightGBM モデル
    betting_optimizer.py         # Kelly Criterion 計算

  scraper/                       # スクレイピング機能
    selectors.py                 # HTML選択子管理
    rate_limit.py                # レート制限・再試行
    fetch_calendar.py            # レースカレンダー取得
    fetch_card.py                # 出馬表取得
    fetch_result.py              # 結果取得
    fetch_future_races.py        # 将来レース取得

  etl/                           # ETL処理
    base.py                      # 基本クラス
    upsert_master.py             # マスタデータ管理
    upsert_race.py               # レース情報管理
    upsert_entry.py              # 出走情報管理
    apply_alias.py               # 名称ゆれ補正

  metrics/                       # 指標計算
    build_horse_metrics.py       # 馬の指標計算

  tests/                         # テストスイート
    test_pipeline.py             # パイプライン統合テスト
    test_csv_export.py           # CSV出力テスト
    test_prediction_page.py      # 予測ページテスト
    test_betting_optimizer.py    # ベッティング最適化テスト
    test_ds_improvements.py      # データサイエンス検証

  docs/                          # ドキュメント
    INDEX.md                     # ドキュメントインデックス
    ARCHITECTURE.md              # システム設計書
    API.md                       # API リファレンス
    DEVELOPMENT.md               # 開発ガイド
    TESTING.md                   # テストガイド
    CLAUDE.md                    # AI開発ガイドライン
    CRITICAL_IMPROVEMENTS_IMPLEMENTED.md
    DS_CRITICAL_IMPROVEMENTS.md
    BETTING_OPTIMIZATION_GUIDE.md
    STREAMLIT_CACHE_FIX.md

  data/
    keiba.db                     # SQLiteデータベース
    logs/                        # スクレイピングログ

  requirements.txt               # Python依存関係
  pyproject.toml                 # Black, isort, pytest設定
  mypy.ini                       # 型チェック設定
  .flake8                        # スタイル設定
  lint.bat / lint.sh             # コード品質チェックスクリプト
```

## インストール

### 前提条件

- Python 3.9以上
- Git
- pip または conda

### セットアップ

```bash
# リポジトリをクローン
git clone <repo-url>
cd keiba-solo-db

# 仮想環境を作成（推奨）
python -m venv venv
source venv/bin/activate  # macOS/Linux
# または
venv\Scripts\activate  # Windows

# 依存関係をインストール
pip install -r requirements.txt

# データベーススキーマを初期化
python -c "from app.db import init_schema; init_schema()"

# Streamlitアプリを起動
streamlit run app/Home.py
```

## 使い方

### 1. ローカルでデータ取得（手動）

初回データの一括取得:

```bash
# レースカレンダーを取得
python -m scraper.fetch_calendar --start 2019 --end 2024

# 出馬表を取得
python -m scraper.fetch_card --years 2019 2020 2021 2022 2023 2024

# レース結果を取得
python -m scraper.fetch_result --years 2019 2020 2021 2022 2023 2024

# ETL処理を実行
python -m etl.upsert_master
python -m etl.upsert_race
python -m etl.upsert_entry
python -m etl.apply_alias

# 指標を計算
python -m metrics.build_horse_metrics
```

### 2. Streamlitアプリで利用

```bash
streamlit run app/Home.py
```

ブラウザが開き、http://localhost:8501 でアプリが表示されます。

**ページ構成**:
- **Home** - 全体概要とデータ統計
- **Race** - レース詳細情報とエントリー表示
- **FutureRaces** - 将来のレース予測と自動データ蓄積
- **Horse** - 馬の成績分析
- **ModelTraining** - 機械学習モデルの訓練
- **Prediction** - レースの勝馬予測
- **Betting** - ベッティング最適化（Kelly Criterion）

### 3. 将来レースの自動蓄積

**2_FutureRaces** ページから:
- 本日以降のレース日付を選択
- 「データベースに保存」ボタンでスクレイピング
- データは自動的にデータベースに蓄積

**注**: GitHub Actions自動実行は削除されています。ローカルで手動実行してください。

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
python -c "from app.db import init_schema; init_schema()"
```

### Streamlit起動エラー

```bash
# キャッシュをクリア
streamlit cache clear

# 依存関係を確認
pip install -r requirements.txt --upgrade
```

### import エラー（app.lib が見つからない）

古い import パスの問題です:

```python
# ❌ 古い形式
from app.lib import db

# ✅ 新しい形式
from app.db import init_schema
```

プロジェクト構造の変更により、`app/lib/` フォルダは削除され、
モジュールは `app/` 直下に移動しました。

## 開発ガイド

詳細な開発ガイドは `docs/` フォルダを参照してください:

- **[docs/DEVELOPMENT.md](docs/DEVELOPMENT.md)** - セットアップと開発基準
- **[docs/TESTING.md](docs/TESTING.md)** - テスト戦略と実行方法
- **[docs/ARCHITECTURE.md](docs/ARCHITECTURE.md)** - システム設計書
- **[docs/API.md](docs/API.md)** - API リファレンス

### クイックスタート

#### コード品質管理

**Windows:**
```bash
lint.bat
```

**macOS/Linux:**
```bash
bash lint.sh
```

実行内容:
- **Black**: コード自動整形（PEP 8準拠、行長100文字）
- **Flake8**: スタイルチェック（PEP 8, import順序, 複雑度）
- **mypy**: 型チェック（型安全性の検証）

#### テスト実行

```bash
# 全テスト実行
pytest tests/ -v

# カバレッジ付きで実行
pytest tests/ --cov=app --cov=etl --cov=scraper --cov=metrics
```

#### 新機能追加フロー

1. Feature ブランチを作成: `git checkout -b feature/your-feature`
2. コードを実装（type hints, docstrings必須）
3. `lint.bat` or `bash lint.sh` でコード品質確認
4. テストを追加・実行
5. Commit & Push
6. GitHub で Pull Request 作成

### コード品質基準

- **行長**: 100文字以下
- **型ヒント**: 全新規関数に必須
- **docstring**: Google形式で記述
- **テスト**: 新機能ごとにテストを追加
- **カバレッジ**: 80%以上を目指す

## ドキュメント

プロジェクトの詳細情報は `docs/` フォルダに集約されています:

| ドキュメント | 説明 |
|-------------|------|
| [docs/INDEX.md](docs/INDEX.md) | ドキュメント索引・ナビゲーション |
| [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) | システム設計・データフロー・DB設計 |
| [docs/API.md](docs/API.md) | TypedDict型定義・関数リファレンス |
| [docs/DEVELOPMENT.md](docs/DEVELOPMENT.md) | 開発環境セットアップ・コード基準 |
| [docs/TESTING.md](docs/TESTING.md) | テスト戦略・pytest実行方法 |
| [docs/CLAUDE.md](docs/CLAUDE.md) | AI開発ガイドライン・設計原則 |

## ライセンス

MIT License

## 更新履歴

- **2025-11** (最新): プロフェッショナル構造化
  - テスト・ドキュメントの集約（tests/, docs/）
  - 包括的なドキュメント作成
  - Black/Flake8/mypy等のコード品質ツール導入
  - 60+特徴量の機械学習モデル実装
  - Kelly Criterionベッティング最適化機能追加

- **2024-11**: 初版実装完了
  - スクレイパー実装
  - ETL処理実装
  - Streamlitアプリ実装
  - GitHub Actions自動化（現在は削除）

## サポート

### 問題がある場合

1. `docs/DEVELOPMENT.md` の**トラブルシューティング**を確認
2. `data/logs/` のエラーログを確認
3. GitHub Issues で報告

### 技術的な質問

1. `docs/INDEX.md` でロール別ナビゲーション確認
2. 関連するドキュメント（ARCHITECTURE.md, API.md等）を参照
3. `docs/DEVELOPMENT.md` の**コード品質**セクション確認

---

**お断り**: JRAのデータ利用にあたり、利用規約への準拠をご確認ください。
