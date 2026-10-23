"""評価用モデル（Phase 2）: LightGBM 二値分類（勝ち/負け）＋キャリブレーション

run_walk_forward の train_predict_fn として使うファクトリを提供する。

学習フォールド内の時系列の使い方:
- 学習期間を時系列で [サブ学習期間 | 較正期間] に分割する
  （較正期間 = 学習期間の後段 calib_fraction 分の日付）。
- ベースモデルはサブ学習期間だけで学習し、較正は較正期間の予測で fit する。
  これにより較正セットが「モデルの学習に使われていない期間」になり、
  較正の楽観バイアスを避ける（検証期間は一切使わない）。
- 特徴量の過去成績は学習・検証の全行を通して「対象日より前の結果」だけで
  計算する（evaluation.features）。検証期間内の過去レースを参照するのは
  発走時点で既知の情報なのでリークではない。
"""

from typing import Callable

import numpy as np
import pandas as pd

from evaluation import calibration, features

try:
    import lightgbm as lgb

    HAS_LIGHTGBM = True
except ImportError:  # pragma: no cover - lightgbm は必須依存に追加済み
    HAS_LIGHTGBM = False


def _fit_base_model(X: pd.DataFrame, y: pd.Series):
    model = lgb.LGBMClassifier(
        objective="binary",
        n_estimators=200,
        learning_rate=0.05,
        num_leaves=31,
        random_state=42,
        n_jobs=-1,
        verbose=-1,
    )
    model.fit(X, y)
    return model


def make_train_predict_fn(
    method: str = "platt",
    calibrate: bool = True,
    calib_fraction: float = 0.3,
) -> Callable[[pd.DataFrame, pd.DataFrame], pd.DataFrame]:
    """キャリブレーション付き LightGBM の train_predict_fn を作る

    戻り値の DataFrame には win_prob（較正済み、calibrate=False なら生確率）と
    win_prob_raw（常に生確率）の両列が付く。較正前後の比較に使う。
    """

    def train_predict(train_df: pd.DataFrame, test_df: pd.DataFrame) -> pd.DataFrame:
        # 特徴量付与（merge を含む）で行順が変わっても予測がずれないよう、
        # テスト行には元の位置を表す _row_id を持たせて対応付ける。
        train_marked = train_df.assign(_split="train", _row_id=-1)
        test_marked = test_df.assign(
            _split="test", _row_id=np.arange(len(test_df))
        )
        combined = pd.concat([train_marked, test_marked], ignore_index=True)
        featured = features.add_history_features(combined)
        train_part = featured[featured["_split"] == "train"]
        test_part = featured[featured["_split"] == "test"].sort_values("_row_id")

        result = test_df.copy()
        base_rate = float(train_part["won"].mean()) if len(train_part) else 0.1

        # 学習期間を時系列でサブ学習／較正に分割
        train_dates = sorted(train_part["race_date"].unique())
        n_calib_dates = max(1, int(round(len(train_dates) * calib_fraction)))
        if len(train_dates) - n_calib_dates < 1:
            sub = train_part
            calib = train_part.iloc[0:0]
        else:
            calib_dates = set(train_dates[-n_calib_dates:])
            sub = train_part[~train_part["race_date"].isin(calib_dates)]
            calib = train_part[train_part["race_date"].isin(calib_dates)]

        if (
            not HAS_LIGHTGBM
            or len(sub) < 30
            or sub["won"].nunique() < 2
        ):
            # 学習できない場合は学習期間の勝率（ベースレート）で埋める
            result["win_prob_raw"] = base_rate
            result["win_prob"] = base_rate
            return result

        model = _fit_base_model(sub[features.FEATURE_COLUMNS], sub["won"])

        if calibrate and len(calib) >= 20 and calib["won"].nunique() == 2:
            calib_raw = model.predict_proba(calib[features.FEATURE_COLUMNS])[:, 1]
            calibrator = calibration.fit_calibrator(
                calib_raw, calib["won"].to_numpy(), method=method
            )
        else:
            calibrator = calibration.ProbabilityCalibrator("identity")

        test_raw = model.predict_proba(test_part[features.FEATURE_COLUMNS])[:, 1]
        result["win_prob_raw"] = test_raw
        result["win_prob"] = calibrator.predict(test_raw)
        return result

    return train_predict


def market_train_predict_fn(train_df: pd.DataFrame, test_df: pd.DataFrame) -> pd.DataFrame:
    """市場ベースライン: オッズの逆数をレース内で正規化した暗黙確率

    学習は行わない。モデルの LogLoss が市場に届いているかの参照用。
    """
    result = test_df.copy()
    inv = 1.0 / result["odds"]
    result["win_prob"] = inv / inv.groupby(result["race_id"]).transform("sum")
    result["win_prob_raw"] = result["win_prob"]
    return result
