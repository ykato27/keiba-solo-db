"""買い条件（事前登録）の読み込み

条件は evaluation/betting_conditions.yaml に固定し、検証コードは
このモジュール経由でのみ条件を参照する。検証結果を見てから条件を
その場で書き換える運用は、多重検定になるため禁止（KEIBA-PLAN Phase 0）。
"""

from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, Optional

import yaml

DEFAULT_CONDITIONS_PATH = Path(__file__).parent / "betting_conditions.yaml"

# 券種ごとの払戻率（JRA公表値）: 単勝・複勝80%、馬連・ワイド77.5%、
# 三連複75%、三連単72.5%。払戻率が高いほど控除が小さい。
DEFAULT_TICKET_PAYOUT_RATES: Dict[str, float] = {
    "win": 0.80,
    "place": 0.80,
    "quinella": 0.775,
    "wide": 0.775,
    "trio": 0.75,
    "trifecta": 0.725,
}


@dataclass(frozen=True)
class BettingConditions:
    """事前登録された買い条件"""

    ticket_type: str = "win"
    ev_threshold: float = 1.20
    min_win_prob: float = 0.10
    max_bets_per_race: int = 2
    unit_bet: int = 100
    holdout_start: Optional[str] = "2025-09-01"
    n_splits: int = 4
    bootstrap_samples: int = 1000
    bootstrap_seed: int = 42
    # Phase 2: 買い方ポリシー
    ticket_payout_rates: Dict[str, float] = field(
        default_factory=lambda: dict(DEFAULT_TICKET_PAYOUT_RATES)
    )
    max_odds: Optional[float] = 50.0  # 大穴回避: この値以上の単勝オッズは買わない
    kelly_fraction: float = 0.25  # 分数Kelly（1/4 Kelly）
    kelly_requires_calibration: bool = True  # 未較正確率では Kelly を無効化


def load_conditions(path: Optional[Path] = None) -> BettingConditions:
    """YAML から買い条件を読み込む

    Args:
        path: 条件ファイル。None の場合は同梱の betting_conditions.yaml

    Returns:
        BettingConditions
    """
    target = Path(path) if path is not None else DEFAULT_CONDITIONS_PATH
    with open(target, encoding="utf-8") as f:
        raw = yaml.safe_load(f) or {}

    holdout = raw.get("holdout") or {}
    walk_forward = raw.get("walk_forward") or {}
    bootstrap = raw.get("bootstrap") or {}
    policy = raw.get("policy") or {}

    payout_rates = dict(DEFAULT_TICKET_PAYOUT_RATES)
    for key, value in (raw.get("ticket_payout_rates") or {}).items():
        payout_rates[str(key)] = float(value)

    max_odds_raw = policy.get("max_odds", 50.0)

    return BettingConditions(
        ticket_type=str(raw.get("ticket_type", "win")),
        ev_threshold=float(raw.get("ev_threshold", 1.20)),
        min_win_prob=float(raw.get("min_win_prob", 0.10)),
        max_bets_per_race=int(raw.get("max_bets_per_race", 2)),
        unit_bet=int(raw.get("unit_bet", 100)),
        holdout_start=holdout.get("start_date"),
        n_splits=int(walk_forward.get("n_splits", 4)),
        bootstrap_samples=int(bootstrap.get("n_samples", 1000)),
        bootstrap_seed=int(bootstrap.get("seed", 42)),
        ticket_payout_rates=payout_rates,
        max_odds=None if max_odds_raw is None else float(max_odds_raw),
        kelly_fraction=float(policy.get("kelly_fraction", 0.25)),
        kelly_requires_calibration=bool(policy.get("kelly_requires_calibration", True)),
    )
