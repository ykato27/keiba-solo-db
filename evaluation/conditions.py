"""買い条件（事前登録）の読み込み

条件は evaluation/betting_conditions.yaml に固定し、検証コードは
このモジュール経由でのみ条件を参照する。検証結果を見てから条件を
その場で書き換える運用は、多重検定になるため禁止（KEIBA-PLAN Phase 0）。
"""

from dataclasses import dataclass
from pathlib import Path
from typing import Optional

import yaml

DEFAULT_CONDITIONS_PATH = Path(__file__).parent / "betting_conditions.yaml"


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
    )
