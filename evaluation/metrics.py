"""買い目選定と評価指標

回収率（ROI）は必ず信頼区間と併記するのがこのプロジェクトのルール。
点推定だけを見て「儲かる」と判断しない（KEIBA-PLAN Phase 0）。

標準フレームの列:
    race_id, race_date (YYYY-MM-DD), horse_id, odds, finish_pos, win_prob
"""

from typing import Tuple

import numpy as np
import pandas as pd

from evaluation.conditions import BettingConditions

_EPS = 1e-15


def select_bets(frame: pd.DataFrame, conditions: BettingConditions) -> pd.DataFrame:
    """事前登録された条件で買い目を選定する

    選定条件（すべて満たすもの）:
    - win_prob >= min_win_prob（低確率帯は推定誤差に弱いため除外）
    - win_prob * odds >= ev_threshold
    - odds < max_odds（大穴回避。max_odds が None の場合は無制限）
    - 1レースあたり EV の高い順に max_bets_per_race 点まで

    Args:
        frame: win_prob 列を持つ標準フレーム
        conditions: 事前登録された買い条件

    Returns:
        買い目の DataFrame（ev 列を追加）
    """
    if conditions.ticket_type != "win":
        raise ValueError(f"未対応の券種です: {conditions.ticket_type}（現在は win のみ）")

    required = {"race_id", "win_prob", "odds", "finish_pos"}
    missing = required - set(frame.columns)
    if missing:
        raise ValueError(f"標準フレームに必要な列がありません: {sorted(missing)}")

    candidates = frame.dropna(subset=["win_prob", "odds"]).copy()
    candidates["ev"] = candidates["win_prob"] * candidates["odds"]
    candidates = candidates[
        (candidates["win_prob"] >= conditions.min_win_prob)
        & (candidates["ev"] >= conditions.ev_threshold)
    ]
    if conditions.max_odds is not None:
        candidates = candidates[candidates["odds"] < conditions.max_odds]
    if candidates.empty:
        return candidates

    candidates = candidates.sort_values(
        ["race_id", "ev"], ascending=[True, False]
    )
    bets = candidates.groupby("race_id", group_keys=False).head(conditions.max_bets_per_race)
    return bets.sort_values(["race_date", "race_id"]).reset_index(drop=True)


def settle(bets: pd.DataFrame, conditions: BettingConditions) -> pd.DataFrame:
    """買い目に賭金と払戻を付与する（単勝: 払戻 = 賭金 × オッズ）"""
    settled = bets.copy()
    settled["stake"] = conditions.unit_bet
    won = settled["finish_pos"] == 1
    settled["return_amount"] = np.where(won, conditions.unit_bet * settled["odds"], 0.0)
    return settled


def roi_percent(bets: pd.DataFrame) -> float:
    """回収率（%）。賭金総額に対する払戻総額の割合。買い目が無い場合は NaN"""
    if bets.empty or bets["stake"].sum() == 0:
        return float("nan")
    return float(bets["return_amount"].sum() / bets["stake"].sum() * 100)


def hit_rate(bets: pd.DataFrame) -> float:
    """的中率（買い目のうち1着だった割合）。買い目が無い場合は NaN"""
    if bets.empty:
        return float("nan")
    return float((bets["finish_pos"] == 1).mean())


def bootstrap_roi_ci(
    bets: pd.DataFrame,
    conditions: BettingConditions,
    alpha: float = 0.05,
) -> Tuple[float, float]:
    """回収率のブートストラップ信頼区間（レース単位のリサンプリング）

    レースを復元抽出して回収率を再計算し、その分布のパーセンタイルを返す。
    同一レース内の買い目は相関するため、買い目単位ではなくレース単位で抽出する。

    Returns:
        (下限%, 上限%)
    """
    if bets.empty:
        return (float("nan"), float("nan"))

    rng = np.random.default_rng(conditions.bootstrap_seed)
    # 回収率は stake / return の合計だけで決まるため、レース単位に
    # 事前集計してから再標本化する（行を concat し直す方式と統計的に
    # 等価で、はるかに速い）。
    grouped = bets.groupby("race_id")[["stake", "return_amount"]].sum()
    stakes = grouped["stake"].to_numpy(dtype=float)
    returns = grouped["return_amount"].to_numpy(dtype=float)
    total_stake = stakes.sum()
    if total_stake <= 0:
        return (float("nan"), float("nan"))

    rois = []
    for _ in range(conditions.bootstrap_samples):
        idx = rng.integers(0, len(grouped), size=len(grouped))
        stake_sum = stakes[idx].sum()
        if stake_sum > 0:
            rois.append(returns[idx].sum() / stake_sum * 100)
        else:
            rois.append(float("nan"))

    low, high = np.nanpercentile(rois, [alpha / 2 * 100, (1 - alpha / 2) * 100])
    return (float(low), float(high))


def roi_excluding_top_races(bets: pd.DataFrame, k: int = 5) -> float:
    """払戻上位 k レースを除いた回収率（%）

    少数の大穴的中に依存した「見かけの高回収率」を見分けるための指標。
    """
    if bets.empty:
        return float("nan")
    race_returns = bets.groupby("race_id")["return_amount"].sum().sort_values(ascending=False)
    top_races = race_returns.head(k).index
    rest = bets[~bets["race_id"].isin(top_races)]
    return roi_percent(rest)


def log_loss(frame: pd.DataFrame) -> float:
    """勝率予測の LogLoss（finish_pos が確定している行のみ）

    市場オッズ（暗黙の予測）との比較に使う基礎指標。
    """
    scored = frame.dropna(subset=["win_prob", "finish_pos"])
    if scored.empty:
        return float("nan")
    p = scored["win_prob"].clip(_EPS, 1 - _EPS)
    y = (scored["finish_pos"] == 1).astype(float)
    return float(-(y * np.log(p) + (1 - y) * np.log(1 - p)).mean())


def summarize_bets(bets: pd.DataFrame, conditions: BettingConditions) -> dict:
    """買い目全体のサマリ（回収率は信頼区間と Top5除外版を必ず併記する）"""
    ci_low, ci_high = bootstrap_roi_ci(bets, conditions)
    return {
        "n_bets": int(len(bets)),
        "n_races": int(bets["race_id"].nunique()) if not bets.empty else 0,
        "roi_percent": roi_percent(bets),
        "roi_ci_low": ci_low,
        "roi_ci_high": ci_high,
        "roi_excluding_top5_percent": roi_excluding_top_races(bets, k=5),
        "hit_rate": hit_rate(bets),
        "total_stake": float(bets["stake"].sum()) if not bets.empty else 0.0,
        "total_return": float(bets["return_amount"].sum()) if not bets.empty else 0.0,
    }
