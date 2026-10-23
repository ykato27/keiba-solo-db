"""リーク（未来情報の混入）・データ整合性の自動チェック

チェック項目の考え方は evaluation/LEAK_CHECKS.md に文書化している。
ここではコード化できるものを実装する。
"""

from typing import Sequence

import pandas as pd

# JRA単勝の払戻は10円未満切り捨て。恒等式はこの範囲で成り立つ。
_PAYOUT_TRUNCATION_TOLERANCE = 10.0


def check_win_payout_identity(
    frame: pd.DataFrame,
    odds_col: str = "odds",
    payout_col: str = "win_payout",
    stake: int = 100,
) -> dict:
    """恒等式チェック: 単勝払戻金 ≒ 単勝オッズ × 賭金（100円基準）

    勝ち馬行について |払戻 - オッズ×賭金| が切り捨て誤差（10円未満）の
    範囲に収まることを確認する。逸脱は、オッズ列と払戻列の取り違え
    （例: 特徴量のオッズが確定オッズでない、行のズレ）を示唆する。

    払戻データが無いデータソースでは checked=0 で返る（スキップ扱い）。

    Returns:
        {"checked": 件数, "violations": 件数, "max_diff": 最大乖離, "ok": bool}
    """
    if payout_col not in frame.columns:
        return {"checked": 0, "violations": 0, "max_diff": 0.0, "ok": True}

    winners = frame[(frame["finish_pos"] == 1) & frame[payout_col].notna()]
    if winners.empty:
        return {"checked": 0, "violations": 0, "max_diff": 0.0, "ok": True}

    expected = winners[odds_col] * stake
    diff = (winners[payout_col] - expected).abs()
    violations = int((diff >= _PAYOUT_TRUNCATION_TOLERANCE).sum())
    return {
        "checked": int(len(winners)),
        "violations": violations,
        "max_diff": float(diff.max()),
        "ok": violations == 0,
    }


def check_race_integrity(frame: pd.DataFrame) -> dict:
    """レース単位の整合性チェック

    - 結果確定レースの勝ち馬は各レース1頭だけ
    - オッズは1.0倍以上
    - 同一レース内で確定着順が重複しない
    """
    finished = frame[frame["finish_pos"].notna()]

    winners_per_race = finished[finished["finish_pos"] == 1].groupby("race_id").size()
    multi_winner_races = int((winners_per_race > 1).sum())

    invalid_odds = int((frame["odds"].notna() & (frame["odds"] < 1.0)).sum())

    dup_positions = int(
        finished.groupby(["race_id", "finish_pos"]).size().gt(1).sum()
    )

    return {
        "multi_winner_races": multi_winner_races,
        "invalid_odds": invalid_odds,
        "duplicate_positions": dup_positions,
        "ok": multi_winner_races == 0 and invalid_odds == 0 and dup_positions == 0,
    }


def check_popularity_odds_consistency(frame: pd.DataFrame) -> dict:
    """人気順とオッズ順の整合性チェック

    1番人気の馬はそのレースで最小オッズ（同率可）でなければならない。
    崩れている場合、人気列とオッズ列の時点がズレている（＝どちらかが
    発走前でない情報）可能性がある。
    """
    if "popularity" not in frame.columns:
        return {"checked_races": 0, "violations": 0, "ok": True}

    violations = 0
    checked = 0
    for _, group in frame.dropna(subset=["popularity", "odds"]).groupby("race_id"):
        favorites = group[group["popularity"] == 1]
        if favorites.empty:
            continue
        checked += 1
        if favorites["odds"].min() > group["odds"].min() + 1e-9:
            violations += 1
    return {"checked_races": checked, "violations": violations, "ok": violations == 0}


def check_temporal_separation(train_dates: Sequence[str], test_dates: Sequence[str]) -> bool:
    """学習期間が検証期間より完全に前にあることを確認する"""
    if not train_dates or not test_dates:
        return False
    return max(train_dates) < min(test_dates)


def run_all_checks(frame: pd.DataFrame) -> dict:
    """すべてのチェックをまとめて実行する"""
    return {
        "payout_identity": check_win_payout_identity(frame),
        "race_integrity": check_race_integrity(frame),
        "popularity_odds": check_popularity_odds_consistency(frame),
    }
