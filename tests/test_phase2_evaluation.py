"""Phase 2: 全出走フレーム・履歴特徴量・評価用モデルのテスト

すべて合成データで、手計算できる期待値と比較する。
"""

import numpy as np
import pandas as pd
import pytest

from app import db as app_db
from evaluation import features, model
from evaluation.data import load_full_entries_frame


def _entry_row(date, race_id, horse_id, horse_no, won, top3, odds=5.0):
    return {
        "race_id": race_id,
        "race_date": date,
        "horse_id": horse_id,
        "jockey_id": 100 + horse_id,
        "trainer_id": 200 + horse_id,
        "horse_no": horse_no,
        "frame_no": horse_no,
        "age": 4,
        "weight_carried": 57.0,
        "horse_weight": 480.0,
        "days_since_last_race": 21,
        "is_steeplechase": 0,
        "distance_m": 1600,
        "surface": "芝",
        "odds": odds,
        "popularity": horse_no,
        "finish_pos": 1 if won else (2 if top3 else 0),
        "won": won,
        "top3": top3,
    }


class TestHistoryFeatures:
    def test_prior_stats_use_only_earlier_dates(self):
        rows = [
            _entry_row("2025-01-01", "R1", 1, 1, won=1, top3=1),
            _entry_row("2025-01-08", "R2", 1, 1, won=0, top3=1),
            _entry_row("2025-01-15", "R3", 1, 1, won=0, top3=0),
        ]
        frame = features.add_history_features(pd.DataFrame(rows))
        frame = frame.sort_values("race_date").reset_index(drop=True)
        # 初出走: 過去成績なし
        assert frame.loc[0, "horse_prior_starts"] == 0
        assert frame.loc[0, "horse_prior_win_rate"] == 0
        # 2走目: 過去1走・1勝
        assert frame.loc[1, "horse_prior_starts"] == 1
        assert frame.loc[1, "horse_prior_win_rate"] == pytest.approx(1.0)
        assert frame.loc[1, "horse_prior_top3_rate"] == pytest.approx(1.0)
        # 3走目: 過去2走・1勝・複勝率 2/2
        assert frame.loc[2, "horse_prior_starts"] == 2
        assert frame.loc[2, "horse_prior_win_rate"] == pytest.approx(0.5)
        assert frame.loc[2, "horse_prior_top3_rate"] == pytest.approx(1.0)

    def test_same_day_results_do_not_leak(self):
        rows = [
            _entry_row("2025-01-01", "R1", 1, 1, won=1, top3=1),
            _entry_row("2025-01-01", "R2", 1, 1, won=0, top3=0),
        ]
        frame = features.add_history_features(pd.DataFrame(rows))
        # 同日の結果は互いに見えない（両行とも prior は 0）
        assert (frame["horse_prior_starts"] == 0).all()

    def test_field_size_and_turf_flag(self):
        rows = [
            _entry_row("2025-01-01", "R1", 1, 1, won=1, top3=1),
            _entry_row("2025-01-01", "R1", 2, 2, won=0, top3=1),
            _entry_row("2025-01-01", "R1", 3, 3, won=0, top3=0),
        ]
        frame = features.add_history_features(pd.DataFrame(rows))
        assert (frame["field_size"] == 3).all()
        assert (frame["is_turf"] == 1.0).all()
        assert set(features.FEATURE_COLUMNS) <= set(frame.columns)


def _make_frame(n_dates=12, races_per_date=3, field=6):
    rows = []
    race_seq = 0
    for d in range(n_dates):
        date = f"2025-{(d // 28) + 1:02d}-{(d % 28) + 1:02d}"
        for _ in range(races_per_date):
            race_seq += 1
            race_id = f"R{race_seq:03d}"
            for horse_no in range(1, field + 1):
                horse_id = (race_seq * 10 + horse_no) % 23 + 1
                won = 1 if horse_no == 1 else 0
                rows.append(
                    _entry_row(date, race_id, horse_id, horse_no, won, 1 if horse_no <= 3 else 0)
                )
    return pd.DataFrame(rows)


class TestModelFn:
    def test_returns_probabilities_and_preserves_rows(self):
        frame = _make_frame()
        dates = sorted(frame["race_date"].unique())
        train = frame[frame["race_date"].isin(dates[:8])]
        test = frame[frame["race_date"].isin(dates[8:])]
        fn = model.make_train_predict_fn(method="platt", calibrate=True)
        predicted = fn(train, test)
        assert len(predicted) == len(test)
        assert {"win_prob", "win_prob_raw"} <= set(predicted.columns)
        assert predicted["win_prob"].between(0, 1).all()
        assert predicted["win_prob_raw"].between(0, 1).all()

    def test_row_alignment_under_shuffle(self):
        """テスト行の順序を変えても、同じ行には同じ確率が付くこと"""
        frame = _make_frame()
        dates = sorted(frame["race_date"].unique())
        train = frame[frame["race_date"].isin(dates[:8])]
        test = frame[frame["race_date"].isin(dates[8:])]
        fn = model.make_train_predict_fn(method="isotonic", calibrate=True)
        base = fn(train, test)
        shuffled = fn(train, test.sample(frac=1.0, random_state=7))
        keys = ["race_id", "horse_id", "horse_no"]
        merged = base.merge(shuffled, on=keys, suffixes=("_a", "_b"))
        assert len(merged) == len(base)
        assert np.allclose(merged["win_prob_a"], merged["win_prob_b"])

    def test_market_baseline_normalizes_within_race(self):
        frame = pd.DataFrame(
            [
                _entry_row("2025-01-01", "R1", 1, 1, won=1, top3=1, odds=2.0),
                _entry_row("2025-01-01", "R1", 2, 2, won=0, top3=1, odds=4.0),
            ]
        )
        predicted = model.market_train_predict_fn(frame, frame)
        probs = predicted.sort_values("horse_no")["win_prob"].tolist()
        assert probs == pytest.approx([2 / 3, 1 / 3])


class TestFullEntriesFrame:
    def test_normalization_and_race_exclusion(self, temp_db):
        conn = app_db.get_connection()
        try:
            conn.executemany(
                "INSERT INTO races (race_id, race_date, course, race_no, distance_m,"
                " surface, going, grade, title) VALUES (?,?,?,?,?,?,?,?,?)",
                [
                    (1, "2025-01-05", "東京", 1, 1600, "芝", "良", "", "R1"),
                    (2, "2025-01-05", "東京", 2, 1600, "芝", "良", "", "R2"),
                ],
            )
            conn.executemany(
                "INSERT INTO race_entries (race_id, horse_id, horse_no, odds,"
                " popularity, finish_pos) VALUES (?,?,?,?,?,?)",
                [
                    (1, 11, 1, 3.0, 1, 1),  # 勝ち馬あり
                    (1, 12, 2, 5.0, 2, 2),
                    (1, 13, 3, 9.0, 3, None),  # 4着以下（未記録）
                    (2, 14, 1, 3.0, 1, 2),  # 勝ち馬が記録されていないレース
                    (2, 15, 2, 5.0, 2, None),
                ],
            )
            conn.commit()
        finally:
            conn.close()

        frame = load_full_entries_frame(db_path=temp_db)
        # 勝ち馬のあるレース1のみが対象（3行）
        assert set(frame["race_id"]) == {1}
        assert len(frame) == 3
        by_horse = frame.set_index("horse_id")
        assert by_horse.loc[11, "finish_pos"] == 1
        assert by_horse.loc[11, "won"] == 1
        assert by_horse.loc[12, "top3"] == 1
        # 未記録行は「4着以下」= finish_pos 0 / won 0 / top3 0 に正規化
        assert by_horse.loc[13, "finish_pos"] == 0
        assert by_horse.loc[13, "won"] == 0
        assert by_horse.loc[13, "top3"] == 0
