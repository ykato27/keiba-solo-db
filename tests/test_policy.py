"""買い方ポリシー（evaluation/policy・条件拡張）のテスト

すべて合成データで、期待される選定・除外を直接確認する。
"""

import pandas as pd
import pytest

from evaluation import metrics, policy
from evaluation.conditions import BettingConditions, load_conditions

CONDITIONS = BettingConditions(
    ev_threshold=1.20,
    min_win_prob=0.10,
    max_bets_per_race=2,
    unit_bet=100,
    holdout_start="2025-09-01",
    n_splits=4,
    bootstrap_samples=200,
    bootstrap_seed=42,
    max_odds=50.0,
    kelly_fraction=0.25,
    kelly_requires_calibration=True,
)


class TestConditionsExtension:
    def test_load_default_conditions_includes_policy(self):
        conditions = load_conditions()
        assert conditions.max_odds == 50.0
        assert conditions.kelly_fraction == 0.25
        assert conditions.kelly_requires_calibration is True

    def test_ticket_payout_rates_are_jra_values(self):
        rates = load_conditions().ticket_payout_rates
        assert rates["win"] == pytest.approx(0.80)
        assert rates["place"] == pytest.approx(0.80)
        assert rates["quinella"] == pytest.approx(0.775)
        assert rates["wide"] == pytest.approx(0.775)
        assert rates["trio"] == pytest.approx(0.75)
        assert rates["trifecta"] == pytest.approx(0.725)


class TestLongshotAvoidance:
    FRAME = pd.DataFrame(
        [
            # 通常の候補（EV 1.5）
            {"race_id": "A", "race_date": "2025-01-05", "horse_id": 1, "odds": 3.0,
             "finish_pos": 1, "win_prob": 0.5},
            # 大穴: EV は 3.0 と高いが、オッズ 60 倍 >= 上限 50 で除外されるべき
            {"race_id": "A", "race_date": "2025-01-05", "horse_id": 2, "odds": 60.0,
             "finish_pos": 2, "win_prob": 0.05 + 0.10},
            # 境界: オッズ 50.0 ちょうどは「50倍以上は買わない」ので除外
            {"race_id": "B", "race_date": "2025-01-05", "horse_id": 3, "odds": 50.0,
             "finish_pos": 1, "win_prob": 0.3},
            # 境界の内側: オッズ 49.9 は対象になる
            {"race_id": "B", "race_date": "2025-01-05", "horse_id": 4, "odds": 49.9,
             "finish_pos": 2, "win_prob": 0.3},
        ]
    )

    def test_is_longshot_boundary(self):
        assert policy.is_longshot(49.9, CONDITIONS) is False
        assert policy.is_longshot(50.0, CONDITIONS) is True
        assert policy.is_longshot(120.0, CONDITIONS) is True

    def test_select_bets_excludes_longshots(self):
        bets = metrics.select_bets(self.FRAME, CONDITIONS)
        selected = {(row.race_id, row.horse_id) for row in bets.itertuples()}
        assert selected == {("A", 1), ("B", 4)}

    def test_no_cap_when_max_odds_is_none(self):
        uncapped = BettingConditions(
            ev_threshold=1.20, min_win_prob=0.10, max_bets_per_race=2,
            holdout_start="2025-09-01", max_odds=None,
        )
        bets = metrics.select_bets(self.FRAME, uncapped)
        selected = {(row.race_id, row.horse_id) for row in bets.itertuples()}
        assert ("A", 2) in selected  # 大穴も選ばれる


class TestMaxBetsPerRace:
    def test_cap_applies(self):
        rows = [
            {"race_id": "A", "race_date": "2025-01-05", "horse_id": i,
             "odds": 3.0 + i, "finish_pos": 2, "win_prob": 0.5}
            for i in range(1, 6)  # 候補5頭すべて EV >= 1.2
        ]
        bets = policy.select_policy_bets(pd.DataFrame(rows), CONDITIONS, calibrated=True)
        assert len(bets) == 2


class TestKellyGate:
    def test_kelly_disabled_without_calibration(self):
        # EV が十分に高い（0.5 × 3.0 = 1.5）ケースでも未較正では 0
        assert policy.kelly_fraction(0.5, 3.0, CONDITIONS, calibrated=False) == 0.0

    def test_kelly_enabled_with_calibration_is_fractional(self):
        frac = policy.kelly_fraction(0.5, 3.0, CONDITIONS, calibrated=True)
        # フルKelly = (3.0*0.5 - 0.5) / 3.0 = 1/3、その 1/4 がポリシー値
        assert frac == pytest.approx((1.0 / 3.0) * 0.25)
        assert frac < 1.0 / 3.0  # 必ずフルKelly未満

    def test_kelly_zero_for_negative_ev(self):
        assert policy.kelly_fraction(0.2, 3.0, CONDITIONS, calibrated=True) == 0.0

    def test_kelly_gate_off_allows_uncalibrated(self):
        open_conditions = BettingConditions(
            holdout_start="2025-09-01",
            kelly_fraction=0.25,
            kelly_requires_calibration=False,
        )
        frac = policy.kelly_fraction(0.5, 3.0, open_conditions, calibrated=False)
        assert frac == pytest.approx((1.0 / 3.0) * 0.25)

    def test_policy_bets_attach_kelly_column(self):
        rows = [
            {"race_id": "A", "race_date": "2025-01-05", "horse_id": 1, "odds": 3.0,
             "finish_pos": 1, "win_prob": 0.5},
        ]
        frame = pd.DataFrame(rows)
        uncal = policy.select_policy_bets(frame, CONDITIONS, calibrated=False)
        assert uncal["kelly_fraction"].tolist() == [0.0]
        cal = policy.select_policy_bets(frame, CONDITIONS, calibrated=True)
        assert cal["kelly_fraction"].iloc[0] == pytest.approx((1.0 / 3.0) * 0.25)
