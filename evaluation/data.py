"""評価用データの読み込み

keiba DB から、検証ハーネスが使う「標準フレーム」を作る。
結果が確定していない行（finish_pos が NULL）は評価に使えないため除外する。

注意（Phase 2 で判明した現行DBの実態）:
- 現行DBは着順が上位3着までしか記録されていない（4着以下は finish_pos=NULL）。
- そのため load_entries_frame が返すのは「3着以内の馬だけ」のフレームで、
  勝率は約33%に歪む。全出走馬を対象に評価する場合は
  load_full_entries_frame を使うこと（NULL は「3着以下」とみなす）。
"""

from pathlib import Path
from typing import Optional

import pandas as pd

from app import db as app_db


def load_entries_frame(db_path: Optional[Path] = None) -> pd.DataFrame:
    """結果確定済み出走行を標準フレームとして読み込む

    標準フレームの列: race_id, race_date, horse_id, horse_no, odds,
    popularity, finish_pos

    Args:
        db_path: DBパス。None の場合は app.db.DB_PATH
    """
    conn = app_db.get_connection(read_only=True, db_path=db_path)
    try:
        frame = pd.read_sql_query(
            """
            SELECT
                r.race_id AS race_id,
                r.race_date AS race_date,
                e.horse_id AS horse_id,
                e.horse_no AS horse_no,
                e.odds AS odds,
                e.popularity AS popularity,
                e.finish_pos AS finish_pos
            FROM race_entries e
            JOIN races r ON r.race_id = e.race_id
            WHERE e.finish_pos IS NOT NULL
              AND e.odds IS NOT NULL
            ORDER BY r.race_date, r.race_id, e.horse_no
            """,
            conn,
        )
    finally:
        conn.close()
    return frame


def load_full_entries_frame(db_path: Optional[Path] = None) -> pd.DataFrame:
    """全出走行を標準フレームとして読み込む（Phase 2）

    現行DBは着順が上位3着までしか記録されていない。勝ち馬（1着）が
    記録されているレースに限り、finish_pos が NULL の行は「4着以下」
    として扱える。勝ち馬が記録されていないレースは単勝の精算が
    できないため除外する。

    標準フレームの列: race_id, race_date, horse_id, jockey_id, trainer_id,
    horse_no, frame_no, age, weight_carried, horse_weight,
    days_since_last_race, is_steeplechase, distance_m, surface, course,
    odds, popularity, finish_pos_raw, finish_pos, won, top3

    finish_pos は「1〜3着はその値、4着以下は 0」に正規化したもの。
    metrics 側は finish_pos == 1 を勝ちとして扱うため、この正規化で
    精算・LogLoss が全行に対して正しく計算できる。
    """
    conn = app_db.get_connection(read_only=True, db_path=db_path)
    try:
        frame = pd.read_sql_query(
            """
            SELECT
                r.race_id AS race_id,
                r.race_date AS race_date,
                e.horse_id AS horse_id,
                e.jockey_id AS jockey_id,
                e.trainer_id AS trainer_id,
                e.horse_no AS horse_no,
                e.frame_no AS frame_no,
                e.age AS age,
                e.weight_carried AS weight_carried,
                e.horse_weight AS horse_weight,
                e.days_since_last_race AS days_since_last_race,
                e.is_steeplechase AS is_steeplechase,
                r.distance_m AS distance_m,
                r.surface AS surface,
                r.course AS course,
                e.odds AS odds,
                e.popularity AS popularity,
                e.finish_pos AS finish_pos_raw
            FROM race_entries e
            JOIN races r ON r.race_id = e.race_id
            WHERE e.odds IS NOT NULL
              AND EXISTS (
                  SELECT 1 FROM race_entries w
                  WHERE w.race_id = r.race_id AND w.finish_pos = 1
              )
            ORDER BY r.race_date, r.race_id, e.horse_no
            """,
            conn,
        )
    finally:
        conn.close()

    frame["won"] = (frame["finish_pos_raw"] == 1).astype(int)
    frame["top3"] = frame["finish_pos_raw"].isin([1, 2, 3]).astype(int)
    frame["finish_pos"] = frame["finish_pos_raw"].where(
        frame["finish_pos_raw"].isin([1, 2, 3]), 0
    )
    return frame
