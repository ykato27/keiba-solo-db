"""馬券配分最適化エンジンのテスト（pytest形式）

旧版は結果を print するだけで assert が無かった。ここでは Kelly 計算と
期待値計算について、既知の入力に対する既知の出力を検証する。

Kelly基準: f* = (b*p - q) / b 、実装はセーフティファクター（既定0.25）を
掛けたうえで上限0.5でキャップする。
"""

import pytest

from app.betting_optimizer import BettingOptimizer, recommend_bets


class TestKellyFraction:
    @pytest.mark.parametrize(
        "prob,odds,expected",
        [
            # (3.0*0.5 - 0.5)/3.0 = 1/3 → ×0.25 = 1/12
            (0.50, 3.0, 1 / 12),
            # (5.0*0.25 - 0.75)/5.0 = 0.1 → ×0.25 = 0.025
            (0.25, 5.0, 0.025),
            # (1.5*0.5 - 0.5)/1.5 = 1/6 → ×0.25 = 1/24
            (0.50, 1.5, 1 / 24),
        ],
    )
    def test_known_values(self, prob, odds, expected):
        assert BettingOptimizer.calculate_kelly_fraction(prob, odds) == pytest.approx(expected)

    @pytest.mark.parametrize(
        "prob,odds",
        [
            (0.10, 8.0),  # (0.8 - 0.9)/8 < 0 → 期待値マイナスは賭けない
            (0.25, 3.0),  # (0.75 - 0.75)/3 = 0 → ちょうどゼロ
            (0.0, 3.0),  # 確率0はガードで0
            (1.0, 3.0),  # 確率1はガードで0
            (0.5, 0.0),  # オッズ0以下はガードで0
        ],
    )
    def test_zero_cases(self, prob, odds):
        assert BettingOptimizer.calculate_kelly_fraction(prob, odds) == 0.0

    def test_cap_at_half(self):
        # safety_factor=1.0 のとき full Kelly は (10*0.9-0.1)/10 = 0.89 → 上限0.5
        assert BettingOptimizer.calculate_kelly_fraction(0.9, 10.0, safety_factor=1.0) == 0.5

    def test_safety_factor_scales_linearly(self):
        full = BettingOptimizer.calculate_kelly_fraction(0.5, 3.0, safety_factor=1.0)
        quarter = BettingOptimizer.calculate_kelly_fraction(0.5, 3.0, safety_factor=0.25)
        assert quarter == pytest.approx(full * 0.25)


class TestExpectedValue:
    @pytest.mark.parametrize(
        "prob,odds,bet,expected_roi,expected_profit",
        [
            # 勝ち利益2000*0.25 - 1000*0.75 = -250 → ROI -25%
            (0.25, 3.0, 1000, -25.0, -250.0),
            # 勝ち利益2000*0.5 - 1000*0.5 = +500 → ROI +50%
            (0.50, 3.0, 1000, 50.0, 500.0),
            # 勝ち利益500*0.5 - 1000*0.5 = -250 → ROI -25%
            (0.50, 1.5, 1000, -25.0, -250.0),
        ],
    )
    def test_known_values(self, prob, odds, bet, expected_roi, expected_profit):
        roi, profit = BettingOptimizer.calculate_expected_value(prob, odds, bet)
        assert roi == pytest.approx(expected_roi)
        assert profit == pytest.approx(expected_profit)

    def test_zero_bet(self):
        assert BettingOptimizer.calculate_expected_value(0.5, 3.0, 0) == (0.0, 0.0)


# Kelly が正になる予測のみで構成したポートフォリオ（前提条件検証は無効化して検証）
PREDICTIONS = [
    {"horse_name": "本命", "win_probability": 0.50, "expected_odds": 3.0},
    {"horse_name": "対抗", "win_probability": 0.30, "expected_odds": 4.0},
    {"horse_name": "割安でない", "win_probability": 0.10, "expected_odds": 8.0},
    {"horse_name": "低確率", "win_probability": 0.04, "expected_odds": 30.0},
]


class TestPortfolio:
    def test_optimize_portfolio_filters_and_amounts(self):
        recommendations, _validation = BettingOptimizer.optimize_portfolio(
            PREDICTIONS, total_budget=10000, validate_preconditions=False
        )

        # 「割安でない」は Kelly=0、「低確率」は min_probability=0.05 未満で除外
        names = [r.horse_name for r in recommendations]
        assert names == ["本命", "対抗"]  # 期待ROI順（本命+50% > 対抗+20%）

        honmei, taikou = recommendations
        assert honmei.kelly_fraction == pytest.approx(1 / 12)
        assert honmei.kelly_bet == pytest.approx(10000 / 12)
        # (4.0*0.3 - 0.7)/4.0 = 0.125 → ×0.25 = 0.03125
        assert taikou.kelly_fraction == pytest.approx(0.03125)
        assert taikou.kelly_bet == pytest.approx(312.5)

    def test_portfolio_stats(self):
        recommendations, _ = BettingOptimizer.optimize_portfolio(
            PREDICTIONS, total_budget=10000, validate_preconditions=False
        )
        stats = BettingOptimizer.calculate_portfolio_stats(recommendations)

        assert stats["num_bets"] == 2
        assert stats["total_bet"] == pytest.approx(10000 / 12 + 312.5)
        expected_profit = sum(r.expected_profit for r in recommendations)
        assert stats["expected_total_profit"] == pytest.approx(expected_profit)
        assert stats["expected_total_roi"] == pytest.approx(
            expected_profit / stats["total_bet"] * 100
        )
        assert 0.0 < stats["weighted_win_prob"] < 1.0
        assert stats["kelly_efficiency"] == pytest.approx(1 / 12 + 0.03125)

    def test_portfolio_stats_empty(self):
        stats = BettingOptimizer.calculate_portfolio_stats([])
        assert stats["total_bet"] == 0
        assert stats["num_bets"] == 0

    def test_scenario_recommendations(self):
        scenarios = BettingOptimizer.generate_scenario_recommendations(
            PREDICTIONS, budgets=[1000, 10000], validate_once=False
        )
        assert set(scenarios.keys()) == {1000, 10000}
        for budget, (recommendations, _validation) in scenarios.items():
            for rec in recommendations:
                # 賭金は予算×Kelly割合に比例する
                assert rec.kelly_bet == pytest.approx(rec.kelly_fraction * budget)

    def test_recommend_bets_helper(self):
        recommendations, stats = recommend_bets(
            PREDICTIONS, budget=10000, min_probability=0.05
        )
        # recommend_bets は前提条件検証ありで動く。Kelly>0 の馬だけが残る
        assert all(r.kelly_fraction > 0 for r in recommendations)
        assert stats["num_bets"] == len(recommendations)
