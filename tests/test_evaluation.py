"""検証基盤（evaluation/）のテスト

すべて合成データで、手計算できる期待値と比較する。
"""

import numpy as np
import pandas as pd
import pytest

from evaluation import leak_checks, metrics
from evaluation.conditions import BettingConditions, load_conditions
from evaluation.data import load_entries_frame
from evaluation.walk_forward import run_walk_forward, walk_forward_splits

CONDITIONS = BettingConditions(
    ev_threshold=1.20,
    min_win_prob=0.10,
    max_bets_per_race=2,
    unit_bet=100,
    holdout_start="2025-09-01",
    n_splits=4,
    bootstrap_samples=200,
    bootstrap_seed=42,
)


class TestConditions:
    def test_load_default_conditions(self):
        conditions = load_conditions()
        assert conditions.ticket_type == "win"
        assert conditions.ev_threshold == 1.20
        assert conditions.min_win_prob == 0.10
        assert conditions.max_bets_per_race == 2
        assert conditions.unit_bet == 100
        assert conditions.holdout_start == "2025-09-01"
        assert conditions.n_splits == 4


class TestSelectAndSettle:
    FRAME = pd.DataFrame(
        [
            # レースA: h3 は EV が高いが勝率下限で除外、h4 は EV 閾値未満で除外
            {"race_id": "A", "race_date": "2025-01-05", "horse_id": 1, "odds": 3.0, "finish_pos": 1, "win_prob": 0.5},
            {"race_id": "A", "race_date": "2025-01-05", "horse_id": 2, "odds": 4.0, "finish_pos": 2, "win_prob": 0.3},
            {"race_id": "A", "race_date": "2025-01-05", "horse_id": 3, "odds": 20.0, "finish_pos": 3, "win_prob": 0.09},
            {"race_id": "A", "race_date": "2025-01-05", "horse_id": 4, "odds": 2.0, "finish_pos": 4, "win_prob": 0.5},
            # レースB: 候補3頭 → EV 上位2頭（h5, h1）だけが選ばれる
            {"race_id": "B", "race_date": "2025-01-05", "horse_id": 1, "odds": 3.0, "finish_pos": 1, "win_prob": 0.5},
            {"race_id": "B", "race_date": "2025-01-05", "horse_id": 2, "odds": 4.0, "finish_pos": 2, "win_prob": 0.3},
            {"race_id": "B", "race_date": "2025-01-05", "horse_id": 5, "odds": 10.0, "finish_pos": 3, "win_prob": 0.2},
        ]
    )

    def test_select_bets_rules(self):
        bets = metrics.select_bets(self.FRAME, CONDITIONS)
        selected = {(row.race_id, row.horse_id) for row in bets.itertuples()}
        assert selected == {("A", 1), ("A", 2), ("B", 5), ("B", 1)}

    def test_roi_and_hit_rate_known_values(self):
        settled = metrics.settle(metrics.select_bets(self.FRAME, CONDITIONS), CONDITIONS)
        # 賭金 4点×100円=400円、払戻は A の1着300円 + B の1着300円 = 600円
        assert metrics.roi_percent(settled) == pytest.approx(150.0)
        assert metrics.hit_rate(settled) == pytest.approx(0.5)

    def test_summarize_includes_ci_and_top5(self):
        settled = metrics.settle(metrics.select_bets(self.FRAME, CONDITIONS), CONDITIONS)
        summary = metrics.summarize_bets(settled, CONDITIONS)
        assert summary["n_bets"] == 4
        assert summary["roi_ci_low"] <= summary["roi_percent"] <= summary["roi_ci_high"]
        assert "roi_excluding_top5_percent" in summary


class TestBootstrap:
    def test_degenerate_ci_when_all_races_identical(self):
        bets = pd.DataFrame(
            [
                {"race_id": f"R{i}", "race_date": "2025-01-05", "odds": 3.0,
                 "finish_pos": 1, "stake": 100, "return_amount": 300.0}
                for i in range(3)
            ]
        )
        low, high = metrics.bootstrap_roi_ci(bets, CONDITIONS)
        assert low == high == pytest.approx(300.0)

    def test_ci_contains_point_estimate_and_is_reproducible(self):
        rng = np.random.default_rng(0)
        rows = []
        for i in range(40):
            won = rng.random() < 0.35
            rows.append(
                {"race_id": f"R{i}", "race_date": "2025-01-05", "odds": 3.0,
                 "finish_pos": 1 if won else 2, "stake": 100,
                 "return_amount": 300.0 if won else 0.0}
            )
        bets = pd.DataFrame(rows)
        low1, high1 = metrics.bootstrap_roi_ci(bets, CONDITIONS)
        low2, high2 = metrics.bootstrap_roi_ci(bets, CONDITIONS)
        assert (low1, high1) == (low2, high2)  # seed 固定で再現可能
        assert low1 <= metrics.roi_percent(bets) <= high1


class TestRoiExcludingTop:
    def test_excluding_top_races(self):
        rows = [{"race_id": "BIG", "race_date": "2025-01-05", "odds": 100.0,
                 "finish_pos": 1, "stake": 100, "return_amount": 10000.0}]
        rows += [
            {"race_id": f"L{i}", "race_date": "2025-01-05", "odds": 3.0,
             "finish_pos": 2, "stake": 100, "return_amount": 0.0}
            for i in range(5)
        ]
        bets = pd.DataFrame(rows)
        assert metrics.roi_percent(bets) == pytest.approx(10000 / 600 * 100)
        # 上位5レースを除くと BIG を含むため残りは全敗 → 0%
        assert metrics.roi_excluding_top_races(bets, k=5) == pytest.approx(0.0)


class TestLogLoss:
    def test_known_value(self):
        frame = pd.DataFrame(
            {"win_prob": [0.9, 0.1], "finish_pos": [1, 3]}
        )
        assert metrics.log_loss(frame) == pytest.approx(-np.log(0.9))

    def test_perfect_prediction_is_near_zero(self):
        frame = pd.DataFrame(
            {"win_prob": [1.0, 0.0], "finish_pos": [1, 2]}
        )
        assert metrics.log_loss(frame) == pytest.approx(0.0, abs=1e-12)


class TestWalkForwardSplits:
    DATES = [f"2025-01-{d:02d}" for d in range(1, 12)]  # 11日分

    def test_expanding_and_temporally_separated(self):
        splits = walk_forward_splits(self.DATES, n_splits=4)
        assert len(splits) == 4
        previous_train = []
        for train_dates, test_dates in splits:
            assert leak_checks.check_temporal_separation(train_dates, test_dates)
            assert set(previous_train) <= set(train_dates)  # expanding
            previous_train = train_dates
        assert splits[-1][1][-1] == self.DATES[-1]

    def test_too_few_dates_raises(self):
        with pytest.raises(ValueError):
            walk_forward_splits(["2025-01-01", "2025-01-02"], n_splits=4)


def _synthetic_frame(extra_dates=()):
    """予測ルールと結果が既知の合成フレームを作る

    - horse_no 1: オッズ3.0 / 予測勝率0.5、2: 4.0 / 0.3、3: 8.0 / 0.1、4: 30.0 / 0.04
    - 勝ち馬はレース番号が偶数なら1、奇数なら2
    - 買い目は各レース {1, 2}（4 は勝率下限で除外）→ 払戻は交互に300円/400円
    """
    dates = [f"2025-01-{d:02d}" for d in range(5, 24, 2)] + list(extra_dates)
    rows = []
    race_index = 0
    for date in dates:
        for _ in range(2):
            race_id = f"R{race_index:03d}"
            winner_no = 1 if race_index % 2 == 0 else 2
            for horse_no, (odds, prob) in {
                1: (3.0, 0.5), 2: (4.0, 0.3), 3: (8.0, 0.1), 4: (30.0, 0.04)
            }.items():
                rows.append(
                    {
                        "race_id": race_id,
                        "race_date": date,
                        "horse_id": horse_no,
                        "horse_no": horse_no,
                        "true_prob": prob,
                        "odds": odds,
                        "finish_pos": 1 if horse_no == winner_no else horse_no + 1,
                    }
                )
            race_index += 1
    return pd.DataFrame(rows)


def _fake_predictor(train_df, test_df):
    predicted = test_df.copy()
    predicted["win_prob"] = predicted["true_prob"]
    return predicted


class TestWalkForwardHarness:
    def test_known_overall_roi(self):
        result = run_walk_forward(_synthetic_frame(), load_conditions(), _fake_predictor)
        # 検証対象は先頭2日を除く16レース。各レース賭金200円、
        # 払戻は半分が300円・半分が400円 → 合計 5600/3200 = 175%
        assert len(result["folds"]) == 4
        assert result["overall"]["roi_percent"] == pytest.approx(175.0)
        assert result["overall"]["roi_ci_low"] <= 175.0 <= result["overall"]["roi_ci_high"]
        assert result["holdout_included"] is False
        assert 0 < result["log_loss"] < 1

    def test_fold_periods_never_overlap(self):
        result = run_walk_forward(_synthetic_frame(), load_conditions(), _fake_predictor)
        for fold in result["folds"]:
            assert fold["train_period"][1] < fold["test_period"][0]

    def test_holdout_excluded_by_default(self):
        frame = _synthetic_frame(extra_dates=["2025-10-05", "2025-10-12"])
        result = run_walk_forward(frame, load_conditions(), _fake_predictor)
        assert result["predictions"]["race_date"].max() < "2025-09-01"
        assert result["bets"]["race_date"].max() < "2025-09-01"

    def test_holdout_included_only_with_flag(self):
        frame = _synthetic_frame(extra_dates=["2025-10-05", "2025-10-12"])
        result = run_walk_forward(
            frame, load_conditions(), _fake_predictor, include_holdout=True
        )
        assert result["holdout_included"] is True
        assert result["predictions"]["race_date"].max() >= "2025-09-01"


class TestLeakChecks:
    def test_payout_identity_ok_and_violation(self):
        ok_frame = pd.DataFrame(
            [
                {"race_id": "A", "odds": 3.2, "finish_pos": 1, "win_payout": 320},
                {"race_id": "B", "odds": 3.25, "finish_pos": 1, "win_payout": 320},
                {"race_id": "A", "odds": 5.0, "finish_pos": 2, "win_payout": None},
            ]
        )
        result = leak_checks.check_win_payout_identity(ok_frame)
        assert result == {"checked": 2, "violations": 0, "max_diff": 5.0, "ok": True}

        bad_frame = ok_frame.copy()
        bad_frame.loc[0, "win_payout"] = 500
        result = leak_checks.check_win_payout_identity(bad_frame)
        assert result["violations"] == 1
        assert result["ok"] is False

    def test_payout_identity_skips_without_payout_column(self):
        frame = pd.DataFrame([{"race_id": "A", "odds": 3.0, "finish_pos": 1}])
        assert leak_checks.check_win_payout_identity(frame)["checked"] == 0

    def test_race_integrity_detects_two_winners(self):
        frame = pd.DataFrame(
            [
                {"race_id": "A", "odds": 3.0, "finish_pos": 1},
                {"race_id": "A", "odds": 4.0, "finish_pos": 1},
            ]
        )
        result = leak_checks.check_race_integrity(frame)
        assert result["multi_winner_races"] == 1
        assert result["ok"] is False

    def test_popularity_odds_consistency(self):
        consistent = pd.DataFrame(
            [
                {"race_id": "A", "odds": 2.0, "popularity": 1, "finish_pos": 1},
                {"race_id": "A", "odds": 5.0, "popularity": 2, "finish_pos": 2},
            ]
        )
        assert leak_checks.check_popularity_odds_consistency(consistent)["ok"] is True

        inconsistent = consistent.copy()
        inconsistent.loc[0, "odds"] = 9.0
        result = leak_checks.check_popularity_odds_consistency(inconsistent)
        assert result["violations"] == 1
        assert result["ok"] is False


class TestDataLoader:
    def test_load_entries_frame_from_temp_db(self, populated_db):
        frame = load_entries_frame(db_path=populated_db["db_path"])
        assert {"race_id", "race_date", "odds", "finish_pos"} <= set(frame.columns)
        assert len(frame) > 0
        assert frame["finish_pos"].notna().all()
        # 結果確定レースの勝ち馬は各1頭
        assert leak_checks.check_race_integrity(frame)["multi_winner_races"] == 0
