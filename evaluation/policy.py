"""買い方ポリシー（Phase 2）

事前登録ファイル（betting_conditions.yaml）の宣言的なポリシーを、
実際の買い目選定と Kelly 計算に接続する層。

ポリシーの要点（KEIBA-PLAN Phase 2）:
- 券種は払戻率の高いものを軸にする前提を、条件ファイルに宣言として保持
  （現状の評価対象は単勝のみ。metrics.select_bets が他券種を拒否する）
- 大穴回避: 単勝オッズが max_odds 以上の馬は買わない
  （選定側の実装は metrics.select_bets が担う）
- EV フィルタは制限形: 確率下限＋事前固定の EV 閾値＋1レース最大点数
- Kelly は分数 Kelly のみとし、確率がキャリブレーション済みの場合に
  のみ有効化する（未較正では kelly_fraction() が常に 0.0 を返す）
"""

import pandas as pd

from app.betting_optimizer import BettingOptimizer
from evaluation import metrics
from evaluation.conditions import BettingConditions


def is_longshot(odds: float, conditions: BettingConditions) -> bool:
    """大穴回避の対象かどうか（オッズ上限以上なら True）"""
    return conditions.max_odds is not None and odds >= conditions.max_odds


def kelly_fraction(
    win_prob: float,
    odds: float,
    conditions: BettingConditions,
    *,
    calibrated: bool,
) -> float:
    """ポリシーに従う Kelly 割合（資金に対する割合）

    - kelly_requires_calibration が True で確率が未較正なら、常に 0.0
      （= Kelly による賭金配分を無効化し、定額買いにフォールバックさせる）
    - 計算式と上限処理は app.betting_optimizer.BettingOptimizer に委譲し、
      セーフティファクターとして条件ファイルの kelly_fraction（分数Kelly）を渡す
    """
    if conditions.kelly_requires_calibration and not calibrated:
        return 0.0
    return BettingOptimizer.calculate_kelly_fraction(
        win_prob, odds, safety_factor=conditions.kelly_fraction
    )


def select_policy_bets(
    frame: pd.DataFrame,
    conditions: BettingConditions,
    *,
    calibrated: bool,
) -> pd.DataFrame:
    """ポリシーで買い目を選定し、kelly_fraction 列を付けて返す

    選定ルール自体は metrics.select_bets（事前登録条件＋大穴回避）に委譲する。
    ここでは各買い目に「ポリシーが許す Kelly 割合」を付与する。
    calibrated=False の場合、kelly_fraction は全行 0.0 になる。
    """
    bets = metrics.select_bets(frame, conditions)
    if bets.empty:
        bets = bets.copy()
        bets["kelly_fraction"] = pd.Series(dtype=float)
        return bets
    bets = bets.copy()
    bets["kelly_fraction"] = [
        kelly_fraction(prob, odds, conditions, calibrated=calibrated)
        for prob, odds in zip(bets["win_prob"], bets["odds"])
    ]
    return bets
