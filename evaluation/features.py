"""評価用モデルの特徴量（Phase 2）

原則: 特徴量は「そのレースの発走時点で知り得た情報」だけで作る。
- 過去成績の集計は、対象レースより前の日付（race_date が厳密に小さい）
  の結果だけを使う。同じ日のレース同士は互いに参照しない。
- horse_metrics テーブルは使わない。あれは全期間の集計値であり、
  時系列検証にそのまま使うと未来情報の混入（リーク）になる。
- オッズ・人気は特徴量に入れない。市場の暗黙確率そのものであり、
  EV 判定（予測確率 × オッズ）と二重計算になるため。モデルは
  「市場以外の情報」から勝率を推定する役割に限定する。
"""

import numpy as np
import pandas as pd

_ENTITIES = ("horse_id", "jockey_id", "trainer_id")
_ENTITY_PREFIX = {"horse_id": "horse", "jockey_id": "jockey", "trainer_id": "trainer"}

BASE_FEATURE_COLUMNS = [
    "horse_no",
    "frame_no",
    "age",
    "weight_carried",
    "horse_weight",
    "days_since_last_race",
    "is_steeplechase",
    "distance_m",
    "is_turf",
    "field_size",
]

HISTORY_FEATURE_COLUMNS = [
    f"{prefix}_{stat}"
    for prefix in ("horse", "jockey", "trainer")
    for stat in ("prior_starts", "prior_win_rate", "prior_top3_rate")
]

FEATURE_COLUMNS = BASE_FEATURE_COLUMNS + HISTORY_FEATURE_COLUMNS

_DEFAULT_DAYS_SINCE_LAST = 14.0


def _prior_stats(frame: pd.DataFrame, entity: str) -> pd.DataFrame:
    """エンティティ×日付の「その日より前」の累積成績を返す

    戻り値は (entity, race_date, prior_starts, prior_wins, prior_top3) の表。
    日付単位で集計してから累積し、1日分ずらすことで、同日のレース結果が
    同日の別レースの特徴量に混入しないようにする。
    """
    daily = (
        frame.groupby([entity, "race_date"], as_index=False)
        .agg(starts=("race_id", "count"), wins=("won", "sum"), top3=("top3", "sum"))
        .sort_values([entity, "race_date"])
    )
    grouped = daily.groupby(entity)
    for source, target in (
        ("starts", "prior_starts"),
        ("wins", "prior_wins"),
        ("top3", "prior_top3"),
    ):
        daily[target] = grouped[source].cumsum() - daily[source]
    return daily[[entity, "race_date", "prior_starts", "prior_wins", "prior_top3"]]


def add_history_features(frame: pd.DataFrame) -> pd.DataFrame:
    """標準フレーム（全出走版）に特徴量列を追加する

    入力に必要な列: race_id, race_date, horse_id, jockey_id, trainer_id,
    horse_no, frame_no, age, weight_carried, horse_weight,
    days_since_last_race, is_steeplechase, distance_m, surface, won, top3
    """
    result = frame.copy()

    result["field_size"] = result.groupby("race_id")["horse_id"].transform("count")
    result["is_turf"] = (result["surface"] == "芝").astype(float)
    result["days_since_last_race"] = result["days_since_last_race"].fillna(
        _DEFAULT_DAYS_SINCE_LAST
    )

    for entity in _ENTITIES:
        prefix = _ENTITY_PREFIX[entity]
        stats = _prior_stats(result, entity)
        result = result.merge(stats, on=[entity, "race_date"], how="left")
        starts = result["prior_starts"].fillna(0).astype(float)
        result[f"{prefix}_prior_starts"] = starts
        result[f"{prefix}_prior_win_rate"] = np.where(
            starts > 0, result["prior_wins"].fillna(0) / starts.clip(lower=1), 0.0
        )
        result[f"{prefix}_prior_top3_rate"] = np.where(
            starts > 0, result["prior_top3"].fillna(0) / starts.clip(lower=1), 0.0
        )
        result = result.drop(columns=["prior_starts", "prior_wins", "prior_top3"])

    for column in FEATURE_COLUMNS:
        result[column] = pd.to_numeric(result[column], errors="coerce").fillna(0.0)
    return result
