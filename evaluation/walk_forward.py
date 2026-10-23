"""ウォークフォワード検証ハーネス

時系列順の expanding window 分割のみを使う。ランダム分割は未来情報の
混入（リーク）を招くため、このモジュールでは一切提供しない。

使い方:
    frame = load_entries_frame()              # evaluation.data
    conditions = load_conditions()            # evaluation.conditions
    result = run_walk_forward(frame, conditions, train_predict_fn)

    train_predict_fn(train_df, test_df) は test_df に win_prob 列を
    付けた DataFrame を返すコールバック（モデルの学習・予測方法は問わない）。
"""

from typing import Callable, List, Tuple

import pandas as pd

from evaluation import metrics
from evaluation.conditions import BettingConditions

TrainPredictFn = Callable[[pd.DataFrame, pd.DataFrame], pd.DataFrame]


def walk_forward_splits(dates: List[str], n_splits: int) -> List[Tuple[List[str], List[str]]]:
    """日付リストを expanding window で分割する

    Args:
        dates: ソート済みのユニークな日付リスト（YYYY-MM-DD）
        n_splits: 検証フォールド数

    Returns:
        (train_dates, test_dates) のリスト。すべてのフォールドで
        max(train_dates) < min(test_dates) が保証される。
    """
    unique_dates = sorted(set(dates))
    if n_splits < 1:
        raise ValueError("n_splits は1以上が必要です")
    if len(unique_dates) < n_splits + 1:
        raise ValueError(
            f"日付が不足しています（{len(unique_dates)}日 < フォールド数+1={n_splits + 1}）"
        )

    chunk = len(unique_dates) // (n_splits + 1)
    splits = []
    for i in range(n_splits):
        train_end = chunk * (i + 1)
        test_end = chunk * (i + 2) if i < n_splits - 1 else len(unique_dates)
        train_dates = unique_dates[:train_end]
        test_dates = unique_dates[train_end:test_end]
        if not test_dates:
            break
        # 時系列の分離を保証する（ここが崩れる実装変更は即エラーにする）
        assert max(train_dates) < min(test_dates), "学習期間と検証期間が重なっています"
        splits.append((train_dates, test_dates))
    return splits


def exclude_holdout(frame: pd.DataFrame, conditions: BettingConditions) -> pd.DataFrame:
    """封印期間（holdout）以降のデータを除外する"""
    if conditions.holdout_start is None:
        return frame
    return frame[frame["race_date"] < conditions.holdout_start].reset_index(drop=True)


def run_walk_forward(
    frame: pd.DataFrame,
    conditions: BettingConditions,
    train_predict_fn: TrainPredictFn,
    include_holdout: bool = False,
) -> dict:
    """ウォークフォワード検証を実行する

    Args:
        frame: 標準フレーム（race_id, race_date, odds, finish_pos を含む）
        conditions: 事前登録された買い条件
        train_predict_fn: (train_df, test_df) -> test_df に win_prob を付けたもの
        include_holdout: True の場合のみ封印期間も検証に含める。
            最終評価以外で True にしてはいけない。

    Returns:
        {
            "folds": [フォールドごとのサマリ],
            "overall": 全フォールド合算のサマリ（回収率+95%CI+Top5除外版）,
            "bets": 全フォールドの買い目（精算済み）,
            "predictions": 全フォールドの予測（LogLoss計算用）,
            "log_loss": 予測全体の LogLoss,
            "holdout_included": bool,
        }
    """
    working = frame if include_holdout else exclude_holdout(frame, conditions)
    if working.empty:
        raise ValueError("検証対象データが空です（封印期間の除外後に残りませんでした）")

    dates = sorted(working["race_date"].unique())
    splits = walk_forward_splits(dates, conditions.n_splits)

    fold_summaries = []
    all_bets = []
    all_predictions = []

    for fold_no, (train_dates, test_dates) in enumerate(splits, start=1):
        train_df = working[working["race_date"].isin(train_dates)]
        test_df = working[working["race_date"].isin(test_dates)]

        predicted = train_predict_fn(train_df.copy(), test_df.copy())
        if "win_prob" not in predicted.columns:
            raise ValueError("train_predict_fn は win_prob 列を付けて返す必要があります")

        bets = metrics.settle(metrics.select_bets(predicted, conditions), conditions)
        summary = metrics.summarize_bets(bets, conditions)
        summary["fold"] = fold_no
        summary["train_period"] = (train_dates[0], train_dates[-1])
        summary["test_period"] = (test_dates[0], test_dates[-1])
        summary["log_loss"] = metrics.log_loss(predicted)
        fold_summaries.append(summary)

        all_bets.append(bets)
        all_predictions.append(predicted)

    combined_bets = (
        pd.concat(all_bets, ignore_index=True) if all_bets else pd.DataFrame()
    )
    combined_predictions = (
        pd.concat(all_predictions, ignore_index=True) if all_predictions else pd.DataFrame()
    )

    return {
        "folds": fold_summaries,
        "overall": metrics.summarize_bets(combined_bets, conditions),
        "bets": combined_bets,
        "predictions": combined_predictions,
        "log_loss": metrics.log_loss(combined_predictions),
        "holdout_included": include_holdout,
    }
