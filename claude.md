# Claude Code ガイドライン - keiba-solo-db プロジェクト

このドキュメントは、このプロジェクトの開発を通じて学んだ教訓、ルール、失敗事例をまとめたものです。

## 📋 ブランチ管理ルール

### ❌ **やってはいけないこと**
1. **feature ブランチで開発完了後、勝手に main へマージしない**
   - 失敗例：`feature/improve-prediction-model` を自動でマージ
   - 理由：ユーザー様の確認と承認を得ていない
   - **ルール**：feature ブランチへの push のみ止める、main のマージは明示的な指示を待つ

2. **main への勝手な push をしない**
   - 失敗例：マージ後に自動で `git push origin main`
   - 理由：ユーザー様の意図に反する可能性がある
   - **ルール**：main へのマージは ユーザー様の指示後

### ✅ **推奨される対応**
1. feature ブランチでの開発完了
2. ブランチへ push: `git push -u origin feature/xxx`
3. ユーザー様に報告して指示を待つ
4. 「OK、main にマージして」などの指示があったら実行

---

## 🚀 Streamlit 環境の移行教訓

### ❌ **失敗例：ローカルとクラウドで異なる動作**

#### 問題1：ModuleNotFoundError: No module named 'app.lib'
```python
# ❌ ローカルでは動くが、Streamlit Cloud では動かない
from app.lib import db
```

**原因**：
- ローカル：`app/lib/` が Python パッケージとして認識される
- Streamlit Cloud：異なる実行コンテキスト

**解決策**：
- `app/lib/` から `app/` 直下に全モジュールを移動
- `from app.lib import db` → `import db`（app/ が sys.path に追加されている場合）
- sys.path の設定順序を正しくする（Home.py のような early binding）

#### 問題2：パス参照エラー
```python
# ❌ ローカルでは動くが、構造変更後に壊れる
Path(__file__).parent.parent.parent  # 3階層上
```

**原因**：
- ファイルの移動に伴い、階層レベルが変わった
- `app/lib/db.py` → `app/db.py`（1階層上移動）

**解決策**：
- ファイル構造変更後は、すべてのパス参照を確認
- 相対的なパス計算ではなく、プロジェクトルートを基準にする

**ベストプラクティス**：
```python
# ✅ 推奨される方法
sys.path.insert(0, str(Path(__file__).parent.parent))  # 最初に実行
import db  # app/ が sys.path に含まれている
```

---

## 🔍 UI/UX 改善の教訓

### ❌ **失敗例：Race.py の selectbox が機能しない**

```python
# ❌ インデント エラー（行96）
if selected_horse_name:
# 選択された馬の情報を取得  ← この行のインデントが不足
selected_entry = next(...)
```

**問題**：
- `if selected_horse_name:` の直下のコードが正しくインデントされていない
- ユーザー様から「馬が選択されません」という報告

**教訓**：
1. Streamlit の selectbox や radio など UI 要素の処理は、適切なインデント（4スペース）が必須
2. `if` 文の直下のコード全体が正しくネストされていることを確認
3. エラーメッセージなしで動作しないコードもある（デバッグが必要）

**解決策**：
- すべてのコードをインデント4倍にして修正
- Streamlit ページの構造を視覚的に確認

---

## 📊 機械学習モデルの教訓

### ❌ **失敗しやすいポイント**

#### 1. **未来情報リーク（Data Leakage）**
```python
# ❌ 時系列データで危険
from sklearn.model_selection import train_test_split
train_test_split(X, y, test_size=0.2)  # ランダムに分割
```

**問題**：
- 競馬データは時系列
- 未来のレース結果を過去のデータで学習すると、現実性がない

**解決策**：
```python
# ✅ 推奨される方法
from sklearn.model_selection import TimeSeriesSplit
tscv = TimeSeriesSplit(n_splits=3)
for train_idx, test_idx in tscv.split(X):
    X_train, X_test = X[train_idx], X[test_idx]
```

#### 2. **特徴量エンジニアリングの重要性**
- 論文から学んだ：特徴量エンジニアリングが **モデル選択より重要**
- 実装：11個 → 60+個の特徴量へ拡張
- **ルール**：WHO（馬）× WHEN（距離/馬場）× RACE × ENTRY × PEDIGREE の5次元思考

#### 3. **複数モデルの提供**
```python
# ✅ ユーザー様の選択肢を提供
model_choice = st.radio("モデルを選択", options=["LightGBM（推奨）", "ランダムフォレスト"])
```

- LightGBM：カテゴリ変数・欠損値に強い
- ランダムフォレスト：シンプルで安定

---

## 📈 テストデータ生成の注意点

### ✅ **実装したベストプラクティス**

1. **現実的なデータ分布**
   ```python
   # ✅ 体重：実際の競走馬の体重範囲（350-550kg）
   horse_weight = round(400.0 + random.uniform(-100, 150), 0)

   # ✅ 経過日数：加重分布（7日が最頻値）
   days_since_last_race = random.choices(
       [7, 14, 21, 28, 35],
       weights=[30, 35, 20, 10, 5]  # リアル
   )[0]
   ```

2. **スケール感の理解**
   - 3年分のデータ：約800レース
   - 5年分のデータ：約1,300レース
   - 出走馬：各レース8-14頭

---

## 🔧 データベーススキーマの教訓

### ✅ **スキーマ設計時の注意点**

1. **拡張性を考慮する**
   ```sql
   -- ✅ 後で拡張可能な設計
   CREATE TABLE IF NOT EXISTS race_entries (
       ...
       horse_weight REAL,           -- 後から追加
       days_since_last_race INTEGER,
       is_steeplechase INTEGER DEFAULT 0
   );
   ```

2. **関連テーブルの分離**
   ```sql
   -- ✅ 1対多の関係は別テーブル化
   CREATE TABLE horse_pedigree (...)
   CREATE TABLE horse_weight_history (...)
   ```

3. **NULL許容の設計**
   - 初期データでは NULL になる可能性を許容
   - `DEFAULT` 値を適切に設定

---

## 📝 コード品質の教訓

### ✅ **実装パターン**

1. **Streamlit のキャッシング**
   ```python
   # ✅ 推奨：毎回の初期化を避ける
   @st.cache_resource
   def get_model():
       return PredictionModel()
   ```

2. **エラーハンドリング**
   ```python
   # ✅ Streamlit での try-except
   try:
       model.train()
   except Exception as e:
       st.error(f"エラー: {e}")
       import traceback
       st.code(traceback.format_exc())  # デバッグ用
   ```

3. **進捗表示**
   ```python
   # ✅ 長時間処理の可視化
   with st.status("処理中...", expanded=True) as status:
       st.write("ステップ1...")
       st.write("ステップ2...")
       status.update(label="✅ 完了!", state="complete")
   ```

---

## 🎯 次のプロジェクトへの教訓

### ✅ **計画段階**
1. ローカル環境とクラウド環境の違いを事前に考慮
2. ファイル構造を最初に決定（後の移動は高リスク）
3. パス参照は統一ルールで

### ✅ **開発段階**
1. feature ブランチで開発、ユーザー様の指示を待つ
2. UI 要素のインデント確認（Streamlit 特有）
3. 機械学習は TimeSeriesSplit を検討

### ✅ **リリース段階**
1. main へのマージは明示的な指示を待つ
2. ブランチ削除は確認後に

---

## 📚 参考資料

### 競馬予測に関する論文・記事
- **PyCon JP 2018**：「データサイエンスで競馬の結果を予測する」（貫井駿）
- **2023-2025 最新研究**：LightGBM、TimeSeriesSplit、特徴量エンジニアリング
- **Zenn 記事**：「データ収集から機械学習まで全て行って競馬の予測をしてみた」

### キー概念
1. **特徴量エンジニアリング**：1,500個の特徴量組み合わせ（WHO×WHEN×RACE×ENTRY×PEDIGREE）
2. **TimeSeriesSplit**：時系列データの未来情報リーク防止
3. **複勝予測**：単なる勝率より複勝予測が実用的

---

## 🏁 このプロジェクトの成果

✅ 基本的な競馬データベース（SQLite）
✅ Streamlit web アプリケーション
✅ テストデータ生成システム
✅ 2つの機械学習モデル（Random Forest + LightGBM）
✅ 60+個の複合特徴量
✅ TimeSeriesSplit による時系列検証

---

**最後に**：このドキュメントは定期的に更新してください。新しい教訓が得られたら追記することで、プロジェクトの知識資産になります。
