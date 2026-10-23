"""確率キャリブレーション（Phase 2）

モデルの生の予測確率は、そのままでは「真の勝率」とずれていることが多い。
EV 判定や Kelly 基準は確率の絶対値に依存するため、買い方ポリシーに使う前に
独立した較正セットで確率を較正する（KEIBA-PLAN Phase 2）。

較正セットの作り方（リーク防止）:
- 較正セットは学習期間の「後段」を時系列で切り分けたものを使う
  （evaluation.model の train_predict_fn がこの方式）。
- 検証期間のデータで較正してはいけない（それは未来情報の使用になる）。

対応手法:
- platt: ロジット変換した確率へのロジスティック回帰（Platt scaling）
- isotonic: アイソトニック回帰（単調変換、較正セットが大きい場合に有効）
"""

from typing import Optional

import numpy as np
import pandas as pd
from sklearn.isotonic import IsotonicRegression
from sklearn.linear_model import LogisticRegression

_EPS = 1e-15

SUPPORTED_METHODS = ("platt", "isotonic")


class ProbabilityCalibrator:
    """学習済みキャリブレータ

    method="identity" は較正を適用しない恒等変換（較正セットが使えない
    場合のフォールバック。呼び出し側は is_identity で判定できる）。
    """

    def __init__(self, method: str):
        self.method = method
        self._platt: Optional[LogisticRegression] = None
        self._isotonic: Optional[IsotonicRegression] = None

    @property
    def is_identity(self) -> bool:
        return self.method == "identity"

    def predict(self, probs) -> np.ndarray:
        """生の予測確率を較正済み確率に変換する"""
        p = np.clip(np.asarray(probs, dtype=float), _EPS, 1 - _EPS)
        if self.method == "identity":
            return p
        if self.method == "platt":
            assert self._platt is not None
            logit = np.log(p / (1 - p)).reshape(-1, 1)
            return np.clip(self._platt.predict_proba(logit)[:, 1], _EPS, 1 - _EPS)
        if self.method == "isotonic":
            assert self._isotonic is not None
            return np.clip(self._isotonic.predict(p), _EPS, 1 - _EPS)
        raise ValueError(f"未知のキャリブレーション手法です: {self.method}")


def fit_calibrator(probs, outcomes, method: str = "platt") -> ProbabilityCalibrator:
    """較正セットでキャリブレータを学習する

    Args:
        probs: モデルの生の予測確率（較正セットに対する予測）
        outcomes: 実際の勝敗（1=勝ち, 0=負け）
        method: "platt" または "isotonic"

    Returns:
        学習済み ProbabilityCalibrator。較正セットに勝ち・負けの両方が
        含まれない場合は較正が定義できないため identity を返す。
    """
    if method not in SUPPORTED_METHODS:
        raise ValueError(f"未対応のキャリブレーション手法です: {method}")

    p = np.clip(np.asarray(probs, dtype=float), _EPS, 1 - _EPS)
    y = np.asarray(outcomes, dtype=float)
    if len(p) == 0 or len(np.unique(y)) < 2:
        return ProbabilityCalibrator("identity")

    calibrator = ProbabilityCalibrator(method)
    if method == "platt":
        logit = np.log(p / (1 - p)).reshape(-1, 1)
        model = LogisticRegression(C=1.0, solver="lbfgs")
        model.fit(logit, y)
        calibrator._platt = model
    else:  # isotonic
        iso = IsotonicRegression(out_of_bounds="clip")
        iso.fit(p, y)
        calibrator._isotonic = iso
    return calibrator


def binary_log_loss(probs, outcomes) -> float:
    """二値 LogLoss（勝ち=1 の確率に対する損失）"""
    p = np.clip(np.asarray(probs, dtype=float), _EPS, 1 - _EPS)
    y = np.asarray(outcomes, dtype=float)
    if len(p) == 0:
        return float("nan")
    return float(-(y * np.log(p) + (1 - y) * np.log(1 - p)).mean())


def brier_score(probs, outcomes) -> float:
    """Brier スコア（確率予測の平均二乗誤差。小さいほど良い）"""
    p = np.asarray(probs, dtype=float)
    y = np.asarray(outcomes, dtype=float)
    if len(p) == 0:
        return float("nan")
    return float(np.mean((p - y) ** 2))


def reliability_table(probs, outcomes, n_bins: int = 10) -> pd.DataFrame:
    """信頼性テーブル: 予測確率帯ごとの「平均予測」と「実績勝率」

    較正が効いていれば mean_pred と win_rate が近づく。
    戻り値の列: bin, n, mean_pred, win_rate
    """
    p = np.asarray(probs, dtype=float)
    y = np.asarray(outcomes, dtype=float)
    frame = pd.DataFrame({"prob": p, "won": y})
    frame["bin"] = pd.cut(
        frame["prob"],
        bins=np.linspace(0.0, 1.0, n_bins + 1),
        include_lowest=True,
    )
    grouped = frame.groupby("bin", observed=True).agg(
        n=("won", "size"), mean_pred=("prob", "mean"), win_rate=("won", "mean")
    )
    return grouped.reset_index()


def compare_calibration(raw_probs, calibrated_probs, outcomes) -> dict:
    """キャリブレーション前後の指標を比較する

    Returns:
        {"log_loss_raw", "log_loss_calibrated", "brier_raw", "brier_calibrated"}
    """
    return {
        "log_loss_raw": binary_log_loss(raw_probs, outcomes),
        "log_loss_calibrated": binary_log_loss(calibrated_probs, outcomes),
        "brier_raw": brier_score(raw_probs, outcomes),
        "brier_calibrated": brier_score(calibrated_probs, outcomes),
    }
