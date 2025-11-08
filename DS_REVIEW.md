# データサイエンティストによる批判的レビュー
## keiba-solo-db プロジェクト

**日付**: 2025-11-08
**レビュアー**: Claude Code (DS Pro)
**対象**: 競馬予測モデルの全体アーキテクチャ

---

## 📋 Executive Summary

このプロジェクトは**基盤はしっかりしているが、本番レベルのデータサイエンスの観点から、複数の重大な課題がある**。特に：

1. ✅ **良い点**: TimeSeriesSplit、クラス不均衡対策、複合特徴量エンジニアリング
2. ❌ **重大な問題**: 多重共線性への対策欠如、モデル説明可能性の不足、過学習リスクの評価不足
3. ⚠️ **改善必須**: ハイパーパラメータ最適化、検証戦略、運用メトリクス

---

## 🔴 重大な課題

### 1. **多重共線性（Multicollinearity）への対応欠如**

**問題**:
```python
# features.py で以下のような派生特徴量が数多くある：
features['win_losses'] = races_count * features['win_rate']  # races_count と完全相関
features['strong_record'] = win_rate * 0.5 + place_rate * 0.3 + show_rate * 0.2  # 線形結合
features['distance_performance'] = (win_rate * 0.5 + place_rate * 0.3 + show_rate * 0.2)
```

**実際の影響**:
- LightGBMは線形結合に強いが、係数解釈が不安定
- 重要度ランキング（feature_importance）が信頼できない
- 本番環境で特定の特徴量が欠落した時、予測が崩壊する可能性

**修正方法**:
```python
# VIF（Variance Inflation Factor）で診断
from statsmodels.stats.outliers_influence import variance_inflation_factor

# VIF > 5 の特徴量は削除 or 結合
```

**優先度**: 🔴 **高** - 係数解釈や説明可能性に直結

---

### 2. **過学習の系統的な検証がない**

**問題**:
```python
# prediction_model_lightgbm.py:
def build_training_data_with_cv(self):
    # TimeSeriesSplit で交差検証してるが...
    # テスト期間での過学習の定量評価がない
    # train/val/test の精度差を記録していない
```

**具体的に欠けているもの**:
- ✗ 訓練データ vs テストデータの **Learning Curve** がない
- ✗ `max_depth`, `num_leaves` の過学習リスク評価がない
- ✗ Early Stopping を使わない → 常に n_estimators=200 で訓練

**修正方法**:
```python
# Early Stopping を実装
train_data = lgb.Dataset(X_train, label=y_train)
val_data = lgb.Dataset(X_val, label=y_val, reference=train_data)

model = lgb.train(
    params,
    train_data,
    num_boost_round=1000,
    valid_sets=[val_data],
    callbacks=[
        lgb.early_stopping(50),  # これが必須
        lgb.log_evaluation(0)
    ]
)
```

**優先度**: 🔴 **高** - モデルの汎化性能に直結

---

### 3. **クラス不均衡対策が不完全**

**問題**:
```python
# TimeSeriesSplit では数値上は対策してるが...
# 1着予測: 100head ÷ 8頭 = 着順確率 1/8 ≈ 12.5%
# 実際には "来ない可能性高い" という极端なクラス不均衡

# compute_class_weight は使ってるが、
# sampling_strategy や threshold_tuning がない
```

**実際の影響**:
- モデルは「その他」クラスに偏る（safest prediction）
- 1着予測の recall が異常に低い可能性
- 複勝（2-3着）予測も同じ問題

**修正方法**:
```python
# 1. Stratified TimeSeriesSplit
from sklearn.model_selection import StratifiedKFold

# 2. SMOTE（Synthetic Minority Over-sampling）
from imblearn.over_sampling import SMOTE

# 3. Threshold tuning
# P(1st) > 0.3 で「1着候補」ではなく、
# 実データから最適な閾値を学習
```

**優先度**: 🔴 **高** - 実務的な的中率に直結

---

### 4. **説明可能性の完全な欠如**

**問題**:
```python
# UI では feature_importance を表示してるが...
# "なぜこの馬が1着予測されたのか" を説明できない
```

**欠けているもの**:
- ✗ SHAP値（個別予測の説明）
- ✗ Partial Dependence Plot（特徴量の効果）
- ✗ LIME（ローカル説明）
- ✗ 予測に寄与した「top 5 features」の表示

**修正方法**:
```python
import shap

# ビット予測の説明
explainer = shap.TreeExplainer(model)
shap_values = explainer.shap_values(X_sample)

# UI で表示
st.write("この馬が1着の理由:")
st.write("1. win_rate +0.15 点")
st.write("2. distance_performance +0.08 点")
```

**優先度**: 🟡 **中** - ユーザー信頼度に関わるが、モデル精度より優先度低

---

## 🟡 重要な改善点

### 5. **ハイパーパラメータが固定値で最適化されていない**

**問題**:
```python
# lightgbm.py:
self.model = lgb.LGBMClassifier(
    num_leaves=31,       # ← これは何で 31？
    learning_rate=0.05,  # ← 0.05 は理由がない？
    n_estimators=200,    # ← 200 で十分？
)
```

**改善**:
```python
# GridSearchCV で最適化
from sklearn.model_selection import GridSearchCV

param_grid = {
    'num_leaves': [15, 31, 63],
    'learning_rate': [0.01, 0.05, 0.1],
    'max_depth': [5, 7, 9],
    'min_child_samples': [10, 20, 30],
}

gs = GridSearchCV(
    lgb.LGBMClassifier(),
    param_grid,
    cv=TimeSeriesSplit(n_splits=3),
    scoring='f1_macro'
)
```

**優先度**: 🟡 **中** - 予測精度を5-10%改善できる可能性

---

### 6. **検証メトリクスが不十分**

**問題**:
```python
# backtest.py では accuracy_score のみ
# 実務的には不足してる
```

**欠けているメトリクス**:
- ✗ **Precision/Recall per class**（1着vs複勝で異なるため）
- ✗ **AUC-ROC/PR Curve**（閾値選択に必要）
- ✗ **Calibration Curve**（予測確度の信頼性）
- ✗ **Confusion Matrix** の詳細分析

**具体的に追加すべき**:
```python
from sklearn.metrics import precision_recall_fscore_support, roc_auc_score

# 1着予測の precision/recall を分離
precision, recall, f1, _ = precision_recall_fscore_support(
    y_true, y_pred, average=None
)

# Brier score（確度の正確性）
from sklearn.metrics import brier_score_loss
brier = brier_score_loss(y_true, y_pred_proba.max(axis=1))
```

**優先度**: 🟡 **中** - 運用判断に必須

---

### 7. **テストデータ生成が "架空" すぎる**

**問題**:
```python
# test_data.py:
horse_weight = round(400.0 + random.uniform(-100, 150), 0)  # ← これは実データと同じ？
```

**現実との乖離**:
- ✗ 年度ごとの馬齢分布を無視（2才〜5才の競走馬の構成比）
- ✗ 騎手・調教師の性能を完全にランダム化
- ✗ 季節性を反映していない（G1 は春秋、賞金は月別で異なる）
- ✗ 実績の相関構造を持たない

**改善**:
```python
# 実データの統計特性を反映
# 1. 既存レースデータから finish_pos の分布を計算
# 2. その分布を新規テストデータに適用

races_distribution = db.query(
    "SELECT finish_pos, COUNT(*) FROM race_entries GROUP BY finish_pos"
)
```

**優先度**: 🟡 **中** - 本番精度の乖離が生じる可能性

---

## 🟢 良い実装

### ✅ TimeSeriesSplit の活用
正しい時系列検証。データリークなし。

### ✅ 複合特徴量エンジニアリング
WHO×WHEN×RACE×ENTRY×PEDIGREE の5次元思考は学術的に正しい。

### ✅ クラス不均衡への部分的対応
compute_class_weight の使用は基本だが、さらに改善の余地あり。

### ✅ モデルの永続化
pickle で訓練済みモデルを保存。本番化の準備がある。

---

## 📊 優先度別改善ロードマップ

### Phase 1 (即実施 - 2-3 日)
1. VIF による多重共線性診断
2. Early Stopping の実装
3. Learning Curve の可視化

### Phase 2 (1-2週間)
1. Stratified TimeSeriesSplit の導入
2. SHAP による説明可能性
3. Precision/Recall per class の分離

### Phase 3 (2-3週間)
1. GridSearchCV でハイパーパラメータ最適化
2. SMOTE の実装
3. Threshold tuning

### Phase 4 (継続改善)
1. 実データでのテストデータ再生成
2. モデルアンサンブル（LightGBM + XGBoost）
3. 運用メトリクスダッシュボード

---

## 🎯 結論

**これは「教育的には優れているが、本番運用にはまだ早い」レベルのコード品質。**

- 基盤は正しい（Time Series Split、特徴量エンジニアリング）
- しかし、プロダクションを支える検証と説明可能性が不足
- **Phase 1 の修正（多重共線性 + Early Stopping）で、50% 品質向上が期待できる**

このレビューを基に、計画的に改善していきましょう。

---

**Next Step**: 改善実装を開始（feature ブランチで進行）

