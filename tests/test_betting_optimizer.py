"""
馬券配分最適化エンジンのテスト

実行方法:
    python test_betting_optimizer.py
"""

import sys
from pathlib import Path
import pandas as pd

sys.path.insert(0, str(Path(__file__).parent))

from app.betting_optimizer import BettingOptimizer, BettingRecommendation


def test_kelly_calculation():
    """Kelly基準の計算テスト"""
    print("=" * 80)
    print("テスト 1: Kelly基準の計算")
    print("=" * 80)

    optimizer = BettingOptimizer()

    # テストケース
    test_cases = [
        {"prob": 0.25, "odds": 3.0, "name": "1着確率25%, オッズ3.0"},
        {"prob": 0.10, "odds": 8.0, "name": "1着確率10%, オッズ8.0"},
        {"prob": 0.50, "odds": 1.5, "name": "1着確率50%, オッズ1.5"},
    ]

    print("\n勝つ確率別のKelly値（セーフティファクター25%）:")
    print("-" * 80)

    for test in test_cases:
        kelly = optimizer.calculate_kelly_fraction(test["prob"], test["odds"])
        print(f"\n{test['name']}")
        print(f"  → Kelly値: {kelly:.2%}")
        print(f"  → 解釈: 予算の{kelly:.2%}を賭ける")

    print("\n✅ Kelly基準計算テスト完了")


def test_expected_value():
    """期待値計算テスト"""
    print("\n" + "=" * 80)
    print("テスト 2: 期待値計算")
    print("=" * 80)

    optimizer = BettingOptimizer()

    bet_amount = 1000
    test_cases = [
        {"prob": 0.25, "odds": 3.0},
        {"prob": 0.33, "odds": 2.5},
        {"prob": 0.50, "odds": 1.5},
    ]

    print(f"\n賭け額: {bet_amount}円")
    print("-" * 80)

    for test in test_cases:
        roi, profit = optimizer.calculate_expected_value(
            test["prob"], test["odds"], bet_amount
        )
        print(f"\n確率{test['prob']:.0%}, オッズ{test['odds']}")
        print(f"  期待ROI: {roi:+.2f}%")
        print(f"  期待利益: {profit:+.0f}円")

    print("\n✅ 期待値計算テスト完了")


def test_portfolio_optimization():
    """ポートフォリオ最適化テスト"""
    print("\n" + "=" * 80)
    print("テスト 3: ポートフォリオ最適化")
    print("=" * 80)

    # テスト用の予測データ
    predictions = [
        {"horse_name": "ドリームキャスト", "win_probability": 0.25, "expected_odds": 3.0},
        {"horse_name": "サンダーバード", "win_probability": 0.20, "expected_odds": 4.0},
        {"horse_name": "クリスタルスター", "win_probability": 0.15, "expected_odds": 5.0},
        {"horse_name": "ブラックダイア", "win_probability": 0.12, "expected_odds": 7.0},
        {"horse_name": "シルバーウイング", "win_probability": 0.08, "expected_odds": 10.0},
    ]

    optimizer = BettingOptimizer()
    budget = 10000

    print(f"\n投資予算: {budget:,}円")
    print("-" * 80)

    recommendations = optimizer.optimize_portfolio(predictions, total_budget=budget)

    print("\n推奨配分:")
    for i, rec in enumerate(recommendations, 1):
        print(f"\n{i}. {rec.horse_name}")
        print(f"   勝つ確率: {rec.win_probability:.1%}")
        print(f"   配分割合: {rec.kelly_fraction:.2%}")
        print(f"   推奨賭金: {rec.kelly_bet:,.0f}円")
        print(f"   期待ROI: {rec.expected_roi:+.2f}%")
        print(f"   期待利益: {rec.expected_profit:+,.0f}円")

    # ポートフォリオ統計
    stats = optimizer.calculate_portfolio_stats(recommendations)
    print("\n" + "-" * 80)
    print("ポートフォリオ統計:")
    print(f"  総投資額: {stats['total_bet']:,.0f}円")
    print(f"  加重勝率: {stats['weighted_win_prob']:.1%}")
    print(f"  期待利益: {stats['expected_total_profit']:+,.0f}円")
    print(f"  期待ROI: {stats['expected_total_roi']:+.2f}%")
    print(f"  対象馬数: {stats['num_bets']}")

    print("\n✅ ポートフォリオ最適化テスト完了")


def test_scenario_recommendations():
    """複数予算シナリオテスト"""
    print("\n" + "=" * 80)
    print("テスト 4: 複数予算シナリオ")
    print("=" * 80)

    predictions = [
        {"horse_name": "馬1", "win_probability": 0.30, "expected_odds": 2.5},
        {"horse_name": "馬2", "win_probability": 0.20, "expected_odds": 4.0},
        {"horse_name": "馬3", "win_probability": 0.15, "expected_odds": 6.0},
    ]

    optimizer = BettingOptimizer()
    budgets = [1000, 5000, 10000]

    scenarios = optimizer.generate_scenario_recommendations(predictions, budgets)

    print("\n予算別の推奨配分:")
    print("-" * 80)

    for budget, recommendations in scenarios.items():
        print(f"\n💵 予算: {budget:,}円")

        if recommendations:
            for rec in recommendations:
                print(f"  {rec.horse_name}: {rec.kelly_bet:,.0f}円 (期待利益: {rec.expected_profit:+,.0f}円)")
        else:
            print("  推奨なし")

    print("\n✅ シナリオテスト完了")


def main():
    """全テストを実行"""
    print("\n" + "=" * 80)
    print("[馬券配分最適化エンジン テストスイート]")
    print("=" * 80)

    try:
        test_kelly_calculation()
        test_expected_value()
        test_portfolio_optimization()
        test_scenario_recommendations()

        print("\n" + "=" * 80)
        print("[OK] すべてのテストが完了しました")
        print("=" * 80)

    except Exception as e:
        print(f"\n❌ テスト失敗: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()
