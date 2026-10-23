"""Data Scientist 改善機能のテスト（pytest形式）

旧版は結果を print するだけで assert が無く、しかも本番DBへ直接テストデータを
書き込んでいた。ここでは合成データに対する既知の出力を検証する。
"""

import numpy as np
import pytest

from app import features as feat_module
from app.feature_diagnostics import FeatureDiagnostics
from app.model_training_enhanced import ModelTrainingEnhanced


@pytest.fixture()
def synthetic_matrix():
    """a と完全相関する列・定数列を含む合成特徴量行列"""
    rng = np.random.default_rng(42)
    a = rng.normal(size=200)
    X = np.column_stack(
        [
            a,
            a * 2 + 1,  # a と完全相関
            rng.normal(size=200),  # 独立なノイズ
            np.full(200, 3.14),  # 定数列
        ]
    )
    names = ["a", "a_dup", "noise", "const"]
    return X, names


class TestFeatureDiagnostics:
    def test_vif_detects_duplicate_columns(self, synthetic_matrix):
        X, names = synthetic_matrix
        vif = FeatureDiagnostics.calculate_vif(X, names)
        by_feature = dict(zip(vif["Feature"], vif["VIF"]))

        # 完全相関のペアは VIF が極端に大きくなる
        assert by_feature["a"] > 10
        assert by_feature["a_dup"] > 10
        # 独立な列は VIF が小さい
        assert by_feature["noise"] < 2

    def test_correlated_pairs(self, synthetic_matrix):
        X, names = synthetic_matrix
        pairs = FeatureDiagnostics.find_highly_correlated_pairs(X, names, threshold=0.8)

        assert len(pairs) == 1
        assert {pairs[0]["Feature 1"], pairs[0]["Feature 2"]} == {"a", "a_dup"}
        assert pairs[0]["Correlation"] == pytest.approx(1.0)

    def test_variance_detects_constant_column(self, synthetic_matrix):
        X, names = synthetic_matrix
        variance = FeatureDiagnostics.check_feature_variance(X, names)
        by_feature = dict(zip(variance["Feature"], variance["Variance"]))

        assert by_feature["const"] == pytest.approx(0.0, abs=1e-20)
        assert by_feature["noise"] > 0.5

    def test_correlation_matrix_shape(self, synthetic_matrix):
        X, names = synthetic_matrix
        corr = FeatureDiagnostics.calculate_correlation_matrix(X, names)
        assert corr.shape == (4, 4)
        assert corr.loc["a", "a_dup"] == pytest.approx(1.0)
        assert corr.loc["a", "a"] == pytest.approx(1.0)


class TestFeatureExtraction:
    def test_extract_features_known_values(self):
        horse = {
            "races_count": 10,
            "win_rate": 0.2,
            "place_rate": 0.4,
            "show_rate": 0.5,
            "recent_score": 3.0,
            "distance_pref": '{"win_rate": 0.3, "place_rate": 0.5, "show_rate": 0.6}',
            "surface_pref": "{}",
        }
        features = feat_module.extract_features_for_horse(horse)

        assert features["races_count"] == 10.0
        assert features["log_races_count"] == pytest.approx(np.log(11))
        assert features["is_experienced"] == 1.0
        assert features["is_veteran"] == 0.0
        # 複合指標: win 0.2*0.5 + place 0.4*0.3 + show 0.5*0.2 = 0.32
        assert features["strong_record"] == pytest.approx(0.32)
        # 距離別成績が JSON から読まれる
        assert features["distance_win_rate"] == pytest.approx(0.3)
        assert features["has_distance_data"] == 1.0

    def test_feature_vector_matches_feature_names(self):
        # レース情報・出走情報まで渡すと、正規の特徴量名（41個）と過不足なく一致する
        horse = {"races_count": 0}
        features = feat_module.extract_features_for_horse(
            horse,
            race_info={"distance_m": 1600, "surface": "芝"},
            entry_info={
                "horse_weight": 480,
                "weight_carried": 57.0,
                "days_since_last_race": 21,
                "is_steeplechase": 0,
                "age": 4,
            },
        )
        vector, names = feat_module.create_feature_vector(features)

        assert len(vector) == len(names) == len(feat_module.get_feature_names())
        assert set(names) == set(features.keys())
        assert np.all(np.isfinite(vector))


class TestModelTrainingEnhanced:
    def test_learning_curve_normal(self):
        # 訓練・検証とも単調に下がる損失 → 汎化ギャップ小
        train = [0.90 - 0.008 * i for i in range(100)]
        val = [0.905 - 0.0079 * i for i in range(100)]
        diagnosis = ModelTrainingEnhanced.analyze_learning_curve(train, val)

        # window_size = max(5, 100 // 10) = 10 の平均が最終損失になる
        assert diagnosis["final_train_loss"] == pytest.approx(np.mean(train[-10:]))
        assert diagnosis["generalization_gap"] == pytest.approx(
            diagnosis["final_val_loss"] - diagnosis["final_train_loss"]
        )
        assert diagnosis["status"] == "✅ 正常"

    def test_learning_curve_insufficient_data(self):
        diagnosis = ModelTrainingEnhanced.analyze_learning_curve([0.5] * 5, [0.5] * 5)
        assert "サンプル不足" in diagnosis["status"]

    def test_fold_metrics_perfect_prediction(self):
        y_true = [np.array([0, 1, 2, 0, 1, 2])]
        y_pred = [np.array([0, 1, 2, 0, 1, 2])]
        y_proba = [
            np.array(
                [
                    [1.0, 0.0, 0.0],
                    [0.0, 1.0, 0.0],
                    [0.0, 0.0, 1.0],
                    [1.0, 0.0, 0.0],
                    [0.0, 1.0, 0.0],
                    [0.0, 0.0, 1.0],
                ]
            )
        ]
        metrics = ModelTrainingEnhanced.compute_fold_wise_metrics(y_true, y_pred, y_proba)

        assert metrics["mean_accuracy"] == pytest.approx(1.0)
        assert metrics["mean_f1_macro"] == pytest.approx(1.0)
        assert len(metrics["fold_metrics"]) == 1
