"""確率キャリブレーション（evaluation/calibration）のテスト

すべて合成データで、手計算できる期待値と比較する。
"""

import numpy as np
import pytest

from evaluation import calibration


class TestBrierAndLogLoss:
    def test_brier_known_value(self):
        # (0.9-1)^2 と (0.1-0)^2 の平均 = 0.01
        assert calibration.brier_score([0.9, 0.1], [1, 0]) == pytest.approx(0.01)

    def test_binary_log_loss_known_value(self):
        assert calibration.binary_log_loss([0.9, 0.1], [1, 0]) == pytest.approx(
            -np.log(0.9)
        )

    def test_perfect_prediction_scores_zero(self):
        assert calibration.brier_score([1.0, 0.0], [1, 0]) == pytest.approx(0.0)
        assert calibration.binary_log_loss([1.0, 0.0], [1, 0]) == pytest.approx(
            0.0, abs=1e-12
        )


class TestFitCalibrator:
    def test_unknown_method_raises(self):
        with pytest.raises(ValueError):
            calibration.fit_calibrator([0.5, 0.5], [1, 0], method="unknown")

    def test_single_class_falls_back_to_identity(self):
        calibrator = calibration.fit_calibrator([0.3, 0.4], [1, 1], method="platt")
        assert calibrator.is_identity
        assert calibrator.predict([0.3]) == pytest.approx([0.3])

    @pytest.mark.parametrize("method", ["platt", "isotonic"])
    def test_output_is_valid_probability(self, method):
        rng = np.random.default_rng(0)
        probs = rng.uniform(0.01, 0.99, size=200)
        outcomes = (rng.uniform(size=200) < probs).astype(float)
        calibrator = calibration.fit_calibrator(probs, outcomes, method=method)
        calibrated = calibrator.predict([0.05, 0.5, 0.95])
        assert np.all((calibrated > 0) & (calibrated < 1))
        # 単調性: 入力が大きいほど較正後も小さくならない
        assert calibrated[0] <= calibrated[1] <= calibrated[2]

    @pytest.mark.parametrize("method", ["platt", "isotonic"])
    def test_overconfident_probs_are_pulled_toward_base_rate(self, method):
        """過信した確率（常に0.9と言うが実績は半分）を持つ較正セットでは、
        較正後の確率が実績勝率側へ引き戻されること"""
        rng = np.random.default_rng(1)
        probs = np.full(400, 0.9)
        outcomes = (rng.uniform(size=400) < 0.5).astype(float)
        calibrator = calibration.fit_calibrator(probs, outcomes, method=method)
        calibrated = calibrator.predict([0.9])[0]
        assert calibrated < 0.75  # 0.9 のままではない
        assert calibrated > 0.25  # 実績（約0.5）の近傍にある


class TestReliabilityTable:
    def test_known_bins(self):
        probs = [0.05, 0.15, 0.85, 0.95]
        outcomes = [0, 1, 1, 1]
        table = calibration.reliability_table(probs, outcomes, n_bins=10)
        assert table["n"].sum() == 4
        low = table[table["mean_pred"] < 0.2]
        assert low["n"].sum() == 2
        assert low["win_rate"].mean() == pytest.approx(0.5)
        high = table[table["mean_pred"] > 0.8]
        assert high["win_rate"].mean() == pytest.approx(1.0)


class TestCompareCalibration:
    def test_compare_returns_all_keys(self):
        result = calibration.compare_calibration(
            [0.9, 0.1, 0.8], [0.7, 0.3, 0.6], [1, 0, 1]
        )
        assert set(result) == {
            "log_loss_raw",
            "log_loss_calibrated",
            "brier_raw",
            "brier_calibrated",
        }
        # この例では較正後の方が確率が真値から遠いので Brier は悪化する
        assert result["brier_calibrated"] > result["brier_raw"]
