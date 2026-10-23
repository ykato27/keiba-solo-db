"""評価用データの読み込み

keiba DB から、検証ハーネスが使う「標準フレーム」を作る。
結果が確定していない行（finish_pos が NULL）は評価に使えないため除外する。
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
