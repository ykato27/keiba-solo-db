"""検証基盤パッケージ（Phase 0）

ウォークフォワード検証・評価指標・事前登録された買い条件・リークチェックを
提供する。方針の詳細は evaluation/LEAK_CHECKS.md と KEIBA-PLAN.md を参照。
"""

from evaluation.conditions import BettingConditions, load_conditions
from evaluation.data import load_entries_frame
from evaluation.walk_forward import run_walk_forward, walk_forward_splits

__all__ = [
    "BettingConditions",
    "load_conditions",
    "load_entries_frame",
    "run_walk_forward",
    "walk_forward_splits",
]
