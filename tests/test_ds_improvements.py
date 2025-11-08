"""
Data Scientist 改善の統合テスト

Feature Diagnostics と Model Training Enhanced の
機能を統合的にテストします。

実行方法:
    python test_ds_improvements.py
"""

import sys
from pathlib import Path
import numpy as np

# パス設定
sys.path.insert(0, str(Path(__file__).parent))

from app import features as feat_module
from app.feature_diagnostics import FeatureDiagnostics, diagnose_features_simple
from app.test_data import generate_test_horses, generate_test_entries, generate_test_races
from app import queries, db as app_db
from app.model_training_enhanced import ModelTrainingEnhanced


def test_feature_diagnostics():
    """特徴量診断のテスト"""
    print("=" * 80)
    print("🧪 テスト 1: 特徴量診断 (VIF, 相関, 分散)")
    print("=" * 80)

    # テストデータ生成
    print("\n📊 テストデータを生成中...")
    conn = app_db.get_connection()
    races = generate_test_races(years=1)
    for race in races[:100]:  # 最初の100レース
        conn.execute("""
            INSERT OR IGNORE INTO races
            (race_id, race_date, course, race_no, distance_m, surface, going, grade, title)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            f"{race['race_date'].replace('-', '')}{str(races.index(race)).zfill(4)}",
            race['race_date'], race['course'], race['race_no'],
            race['distance_m'], race['surface'], race.get('going'), race.get('grade'), race['title']
        ))
    conn.commit()

    # 馬と出走データを生成
    horses = generate_test_horses(count=50)
    for horse in horses:
        conn.execute("""
            INSERT OR IGNORE INTO horses (horse_id, raw_name, sex, birth_year)
            VALUES (?, ?, ?, ?)
        """, (horse['horse_id'], horse['raw_name'], horse['sex'], horse['birth_year']))
    conn.commit()

    # 特徴量を抽出
    print("\n🔧 特徴量を抽出中...")
    X_list = []
    for horse in horses[:30]:
        try:
            features = feat_module.extract_features_for_horse(horse)
            X_list.append(list(features.values()))
        except Exception as e:
            print(f"  特徴量抽出エラー: {e}")

    if not X_list:
        print("❌ 特徴量を抽出できませんでした")
        return

    X = np.array(X_list)
    feature_names = feat_module.get_feature_names()

    print(f"✅ {len(X)} サンプル × {X.shape[1]} 特徴量を抽出")

    # VIF 分析
    print("\n📈 VIF分析を実行中...")
    diag = FeatureDiagnostics()
    vif_results = diag.calculate_vif(X, feature_names)
    print("\n🔴 VIF が高い特徴量（VIF > 5）:")
    high_vif = vif_results[vif_results['VIF'] > 5]
    if len(high_vif) > 0:
        for _, row in high_vif.iterrows():
            print(f"  - {row['Feature']}: {row['VIF']:.2f}")
    else:
        print("  なし（良好）")

    # 相関分析
    print("\n🔗 相関分析を実行中...")
    corr_pairs = diag.find_highly_correlated_pairs(X, feature_names, threshold=0.8)
    if corr_pairs:
        print(f"  高相関ペア（r > 0.8）: {len(corr_pairs)} 件")
        for pair in corr_pairs[:5]:
            print(f"  - {pair['Feature 1']} ↔ {pair['Feature 2']}: {pair['Correlation']:.3f}")
    else:
        print("  なし（良好）")

    # 分散分析
    print("\n📊 分散分析を実行中...")
    variance_results = diag.check_feature_variance(X, feature_names)
    print("  分散が極端に小さい特徴量:")
    low_var = variance_results[variance_results['Variance'] < 0.01]
    if len(low_var) > 0:
        for _, row in low_var.iterrows():
            print(f"  - {row['Feature']}: var={row['Variance']:.6f}")
    else:
        print("  なし（良好）")

    print("\n✅ 特徴量診断完了")
    return X, feature_names


def test_learning_curve_diagnostics():
    """Learning Curve と過学習診断のテスト"""
    print("\n" + "=" * 80)
    print("🧪 テスト 2: Learning Curve と過学習診断")
    print("=" * 80)

    # ダミーの損失データを生成（訓練と検証）
    print("\n📊 ダミー訓練履歴を生成中...")
    num_rounds = 100

    # 正常な学習曲線
    train_losses = [0.9 - 0.008 * i + np.random.normal(0, 0.01) for i in range(num_rounds)]
    val_losses = [0.9 - 0.007 * i + np.random.normal(0, 0.015) for i in range(num_rounds)]

    print(f"✅ {num_rounds} ラウンドの訓練履歴を生成")

    # 過学習診断
    print("\n🔍 Learning Curve 分析を実行中...")
    diagnosis = ModelTrainingEnhanced.analyze_learning_curve(train_losses, val_losses)

    print(f"\n結果:")
    print(f"  最終訓練損失: {diagnosis['final_train_loss']:.4f}")
    print(f"  最終検証損失: {diagnosis['final_val_loss']:.4f}")
    print(f"  汎化ギャップ: {diagnosis['generalization_gap']:.4f}")
    print(f"  状態: {diagnosis['status']}")
    print(f"  推奨: {diagnosis['recommendation']}")

    print("\n✅ Learning Curve 分析完了")


def test_fold_metrics():
    """Fold ごとのメトリクス計算テスト"""
    print("\n" + "=" * 80)
    print("🧪 テスト 3: Fold ごとのメトリクス計算")
    print("=" * 80)

    # ダミーのテスト結果を生成
    print("\n📊 ダミーテスト結果を生成中...")
    n_folds = 5
    y_true_list = []
    y_pred_list = []
    y_pred_proba_list = []

    for fold_idx in range(n_folds):
        n_samples = 100
        y_true = np.random.randint(0, 3, n_samples)
        y_pred = np.where(
            np.random.random(n_samples) > 0.3,
            y_true,
            np.random.randint(0, 3, n_samples)
        )
        y_proba = np.random.dirichlet([1, 1, 1], n_samples)

        y_true_list.append(y_true)
        y_pred_list.append(y_pred)
        y_pred_proba_list.append(y_proba)

    print(f"✅ {n_folds} Fold のテスト結果を生成")

    # メトリクス計算
    print("\n📈 メトリクスを計算中...")
    metrics = ModelTrainingEnhanced.compute_fold_wise_metrics(
        y_true_list, y_pred_list, y_pred_proba_list
    )

    print(f"\n結果:")
    print(f"  平均精度: {metrics['mean_accuracy']:.4f} ± {metrics['std_accuracy']:.4f}")
    print(f"  平均 F1: {metrics['mean_f1_macro']:.4f} ± {metrics['std_f1_macro']:.4f}")
    print(f"  平均 AUC: {metrics.get('mean_auc', np.nan):.4f}")

    print("\nFold 詳細:")
    print(metrics['fold_metrics'].to_string(index=False))

    print("\n✅ Fold メトリクス計算完了")


def main():
    """メインテスト実行"""
    print("\n" + "🚀" * 40)
    print("データサイエンティスト改善の統合テスト")
    print("🚀" * 40)

    try:
        # テスト 1: 特徴量診断
        test_feature_diagnostics()

        # テスト 2: Learning Curve 診断
        test_learning_curve_diagnostics()

        # テスト 3: Fold メトリクス
        test_fold_metrics()

        print("\n" + "=" * 80)
        print("✅ すべてのテストが完了しました")
        print("=" * 80)

    except Exception as e:
        print(f"\n❌ エラーが発生しました: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()
