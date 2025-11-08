"""
馬券配分最適化エンジン
Kelly基準を使用した期待収益最大化

概要:
  Kelly基準（Kelly Criterion）は、確率ゲームで資金を最大化する
  最適な賭け額を計算する数学的手法です。

  f* = (bp - q) / b

  ここで：
  f* = 投資額の最適な割合
  b = オッズ（配当倍率）
  p = 勝つ確率
  q = 負ける確率（1-p）

応用例:
  1着予測: p=0.25, オッズ=3.0 の場合
  f* = (3.0 * 0.25 - 0.75) / 3.0 = 0.0833 (8.33%)

  資金 10,000円 × 8.33% = 833円 を賭ける
"""

import numpy as np
import pandas as pd
from typing import Dict, List, Tuple, Optional
from dataclasses import dataclass
import warnings

from .kelly_precondition_validator import KellyPreconditionValidator


@dataclass
class BettingRecommendation:
    """馬券推奨結果"""
    horse_name: str
    win_probability: float
    expected_odds: float
    kelly_fraction: float
    kelly_bet: float
    expected_roi: float  # 期待収益率
    expected_profit: float  # 期待利益


class BettingOptimizer:
    """馬券配分最適化エンジン"""

    # Kelly基準のセーフティファクター（過度な賭けを避ける）
    KELLY_SAFETY_FACTOR = 0.25  # Kelly値の25%を実装（Full Kellyより保守的）

    @staticmethod
    def calculate_kelly_fraction(
        win_probability: float,
        expected_odds: float,
        safety_factor: float = KELLY_SAFETY_FACTOR
    ) -> float:
        """
        Kelly基準から最適な賭け額の割合を計算

        Args:
            win_probability: 勝つ確率 (0-1)
            expected_odds: 期待オッズ（配当倍率）
            safety_factor: セーフティファクター（0-1）

        Returns:
            投資額の最適割合 (0-1)
        """
        if win_probability <= 0 or win_probability >= 1:
            return 0.0

        if expected_odds <= 0:
            return 0.0

        # Kelly基準: f* = (bp - q) / b
        numerator = (expected_odds * win_probability) - (1 - win_probability)
        denominator = expected_odds

        if denominator <= 0:
            return 0.0

        kelly_fraction = numerator / denominator

        # 負のKelly値（期待値がマイナス）の場合は賭けない
        if kelly_fraction < 0:
            return 0.0

        # セーフティファクターを適用（過度な賭けを避ける）
        safe_fraction = kelly_fraction * safety_factor

        # 最大 50% を上限とする（分散化）
        return min(safe_fraction, 0.5)

    @staticmethod
    def calculate_expected_value(
        win_probability: float,
        expected_odds: float,
        bet_amount: float
    ) -> Tuple[float, float]:
        """
        期待値と期待利益を計算

        Args:
            win_probability: 勝つ確率
            expected_odds: 期待オッズ
            bet_amount: 賭け額

        Returns:
            (期待ROI%, 期待利益)
        """
        if bet_amount <= 0:
            return 0.0, 0.0

        # 期待値 = (勝つ場合の利益) × 勝つ確率 - 賭け額 × 負ける確率
        win_profit = (expected_odds - 1) * bet_amount
        lose_loss = bet_amount

        expected_profit = (win_profit * win_probability) - (lose_loss * (1 - win_probability))
        expected_roi = (expected_profit / bet_amount) * 100

        return expected_roi, expected_profit

    @staticmethod
    def validate_predictions(
        predictions: List[Dict]
    ) -> Dict:
        """
        Kelly基準の前提条件をチェック（期待値検証）

        Args:
            predictions: 馬の予測情報リスト

        Returns:
            検証結果の辞書
        """
        return KellyPreconditionValidator.validate_portfolio(predictions)

    @staticmethod
    def optimize_portfolio(
        predictions: List[Dict],
        total_budget: float,
        min_probability: float = 0.05,
        validate_preconditions: bool = True
    ) -> Tuple[List[BettingRecommendation], Dict]:
        """
        複数の馬に対する最適な配分を計算

        Args:
            predictions: 馬の予測情報リスト
              [
                {
                  'horse_name': 馬名,
                  'win_probability': 勝つ確率,
                  'expected_odds': 期待オッズ,
                },
                ...
              ]
            total_budget: 総投資額
            min_probability: 最小確率閾値（これ以下は除外）
            validate_preconditions: Kelly前提条件を検証するか

        Returns:
            (BettingRecommendation のリスト, 検証結果辞書)
        """
        recommendations = []
        validation_result = {}

        # Kelly基準の前提条件をチェック
        if validate_preconditions:
            validation_result = KellyPreconditionValidator.validate_portfolio(predictions)
            print("\n" + "="*80)
            print("Kelly基準 前提条件検証結果:")
            print("="*80)
            KellyPreconditionValidator.print_validation_report(validation_result)

            # 期待値がプラスの予測のみをフィルタリング
            positive_ev_preds, negative_ev_preds = KellyPreconditionValidator.filter_positive_ev_predictions(
                predictions
            )

            if not positive_ev_preds:
                print(f"\n⚠️ 警告: 期待値がプラスの予測がありません（{len(negative_ev_preds)}頭中0頭）")
                print("賭けるべきではありません！")
                return [], validation_result

            predictions_to_use = positive_ev_preds
        else:
            predictions_to_use = predictions

        for pred in predictions_to_use:
            horse_name = pred.get('horse_name', '不明')
            win_prob = float(pred.get('win_probability', 0))
            odds = float(pred.get('expected_odds', 1.0))

            # フィルタリング: 確率が小さすぎる場合は除外
            if win_prob < min_probability:
                continue

            # Kelly基準を計算
            kelly_frac = BettingOptimizer.calculate_kelly_fraction(win_prob, odds)

            # Kelly値がゼロの場合はスキップ
            if kelly_frac <= 0:
                continue

            # 配分額を計算
            bet_amount = kelly_frac * total_budget

            # 期待値を計算
            roi, profit = BettingOptimizer.calculate_expected_value(win_prob, odds, bet_amount)

            recommendations.append(
                BettingRecommendation(
                    horse_name=horse_name,
                    win_probability=win_prob,
                    expected_odds=odds,
                    kelly_fraction=kelly_frac,
                    kelly_bet=bet_amount,
                    expected_roi=roi,
                    expected_profit=profit
                )
            )

        # 期待ROIが高い順にソート
        return sorted(recommendations, key=lambda x: x.expected_roi, reverse=True), validation_result

    @staticmethod
    def generate_scenario_recommendations(
        predictions: List[Dict],
        budgets: List[float] = None,
        validate_once: bool = True
    ) -> Dict[float, Tuple[List[BettingRecommendation], Dict]]:
        """
        複数の予算シナリオに対する推奨を生成

        Args:
            predictions: 馬の予測情報リスト
            budgets: 予算リスト（Noneの場合はデフォルト）
            validate_once: 1度だけ前提条件を検証するか

        Returns:
            予算ごとの推奨配分と検証結果の辞書
        """
        if budgets is None:
            budgets = [1000, 5000, 10000, 50000, 100000]

        scenarios = {}
        validation_result = None

        for i, budget in enumerate(budgets):
            # 最初の予算シナリオだけで前提条件を検証
            should_validate = (i == 0) and validate_once

            recommendations, validation_result = BettingOptimizer.optimize_portfolio(
                predictions, total_budget=budget, validate_preconditions=should_validate
            )
            scenarios[budget] = (recommendations, validation_result if should_validate else {})

        return scenarios

    @staticmethod
    def calculate_portfolio_stats(
        recommendations: List[BettingRecommendation]
    ) -> Dict:
        """
        ポートフォリオ全体の統計情報を計算

        Args:
            recommendations: 推奨配分リスト

        Returns:
            統計情報辞書
        """
        if not recommendations:
            return {
                'total_bet': 0,
                'weighted_win_prob': 0,
                'expected_total_profit': 0,
                'expected_total_roi': 0,
                'num_bets': 0,
                'kelly_efficiency': 0
            }

        bets = np.array([r.kelly_bet for r in recommendations])
        probs = np.array([r.win_probability for r in recommendations])
        profits = np.array([r.expected_profit for r in recommendations])

        total_bet = np.sum(bets)
        weighted_prob = np.average(probs, weights=bets) if total_bet > 0 else 0
        total_profit = np.sum(profits)
        total_roi = (total_profit / total_bet * 100) if total_bet > 0 else 0

        return {
            'total_bet': total_bet,
            'weighted_win_prob': weighted_prob,
            'expected_total_profit': total_profit,
            'expected_total_roi': total_roi,
            'num_bets': len(recommendations),
            'kelly_efficiency': self._calculate_kelly_efficiency(recommendations)
        }

    @staticmethod
    def _calculate_kelly_efficiency(recommendations: List[BettingRecommendation]) -> float:
        """Kelly基準の効率性を計算（0-1、1が最高）"""
        if not recommendations:
            return 0.0

        kelly_fracs = [r.kelly_fraction for r in recommendations]
        total_kelly = sum(kelly_fracs)

        # 理想的には合計Kelly値が 1.0（全額を配分）に近い方が効率的
        return min(total_kelly, 1.0)


# 簡易的な使用例用関数
def recommend_bets(
    predictions: List[Dict],
    budget: float = 10000,
    min_probability: float = 0.05
) -> Tuple[List[BettingRecommendation], Dict]:
    """
    簡易的な馬券推奨関数

    Args:
        predictions: 馬の予測情報リスト
        budget: 投資予算
        min_probability: 最小確率閾値

    Returns:
        (推奨配分, ポートフォリオ統計)
    """
    optimizer = BettingOptimizer()
    recommendations = optimizer.optimize_portfolio(
        predictions, total_budget=budget, min_probability=min_probability
    )
    stats = optimizer.calculate_portfolio_stats(recommendations)

    return recommendations, stats
