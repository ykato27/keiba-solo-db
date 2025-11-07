"""
SQLiteデータベースアクセス層
読み取り専用操作とスキーマ管理
"""

import sqlite3
import logging
from pathlib import Path
from typing import List, Dict, Any, Optional, Tuple

logger = logging.getLogger(__name__)

DB_PATH = Path(__file__).parent.parent.parent / "data" / "keiba.db"
SCHEMA_PATH = Path(__file__).parent.parent.parent / "sql" / "schema.sql"


def get_connection(read_only: bool = False) -> sqlite3.Connection:
    """データベース接続を取得

    Args:
        read_only: 読み取り専用モードかどうか

    Returns:
        sqlite3.Connection
    """
    # 読み取り専用モード: URIを使用
    if read_only:
        uri = f"file:{DB_PATH}?mode=ro"
        conn = sqlite3.connect(uri, uri=True, timeout=10)
    else:
        conn = sqlite3.connect(str(DB_PATH), timeout=10)

    # Row factory を設定（辞書アクセスを可能にする）
    conn.row_factory = sqlite3.Row

    return conn


def init_schema():
    """スキーマを初期化（存在しない場合のみ）"""
    if not DB_PATH.exists():
        logger.info(f"新しいデータベースを作成: {DB_PATH}")
        DB_PATH.parent.mkdir(parents=True, exist_ok=True)

    conn = get_connection()
    cursor = conn.cursor()

    try:
        # スキーマを読み込んで実行
        with open(SCHEMA_PATH, "r", encoding="utf-8") as f:
            schema = f.read()

        cursor.executescript(schema)
        conn.commit()
        logger.info("スキーマを初期化しました")

    except Exception as e:
        logger.error(f"スキーマ初期化に失敗: {e}")
        conn.rollback()
        raise

    finally:
        conn.close()


def verify_schema() -> bool:
    """スキーマが正常か検証"""
    try:
        conn = get_connection(read_only=True)
        cursor = conn.cursor()

        # 主要テーブルの存在を確認
        tables = [
            "horses",
            "jockeys",
            "trainers",
            "races",
            "race_entries",
        ]

        for table in tables:
            cursor.execute(f"SELECT 1 FROM {table} LIMIT 1")

        conn.close()
        return True

    except Exception as e:
        logger.error(f"スキーマ検証エラー: {e}")
        return False


# ========================
# レース情報クエリ
# ========================

def get_race_dates(start_date: Optional[str] = None, end_date: Optional[str] = None) -> List[str]:
    """開催日の一覧を取得

    Args:
        start_date: 開始日 (YYYY-MM-DD)
        end_date: 終了日 (YYYY-MM-DD)

    Returns:
        開催日のリスト
    """
    conn = get_connection(read_only=True)
    cursor = conn.cursor()

    query = "SELECT DISTINCT race_date FROM races ORDER BY race_date DESC"

    if start_date and end_date:
        query = f"SELECT DISTINCT race_date FROM races WHERE race_date BETWEEN '{start_date}' AND '{end_date}' ORDER BY race_date DESC"

    cursor.execute(query)
    dates = [row[0] for row in cursor.fetchall()]

    conn.close()
    return dates


def get_courses_by_date(race_date: str) -> List[str]:
    """指定日の開催場の一覧を取得

    Args:
        race_date: 開催日 (YYYY-MM-DD)

    Returns:
        開催場のリスト
    """
    conn = get_connection(read_only=True)
    cursor = conn.cursor()

    cursor.execute(
        "SELECT DISTINCT course FROM races WHERE race_date = ? ORDER BY course",
        (race_date,),
    )

    courses = [row[0] for row in cursor.fetchall()]
    conn.close()
    return courses


def get_races_by_date_and_course(race_date: str, course: str) -> List[Dict[str, Any]]:
    """指定日と開催場のレース一覧を取得

    Args:
        race_date: 開催日 (YYYY-MM-DD)
        course: 開催場

    Returns:
        レース情報のリスト
    """
    conn = get_connection(read_only=True)
    cursor = conn.cursor()

    cursor.execute(
        """
        SELECT
            race_id,
            race_no,
            distance_m,
            surface,
            going,
            grade,
            title
        FROM races
        WHERE race_date = ? AND course = ?
        ORDER BY race_no
        """,
        (race_date, course),
    )

    races = [dict(row) for row in cursor.fetchall()]
    conn.close()
    return races


def get_race_entries(race_id: int) -> List[Dict[str, Any]]:
    """レースの出走馬一覧を取得

    Args:
        race_id: レースID

    Returns:
        出走馬のリスト
    """
    conn = get_connection(read_only=True)
    cursor = conn.cursor()

    cursor.execute(
        """
        SELECT
            re.entry_id,
            re.horse_id,
            h.raw_name as horse_name,
            re.jockey_id,
            j.raw_name as jockey_name,
            re.trainer_id,
            t.raw_name as trainer_name,
            re.frame_no,
            re.horse_no,
            re.age,
            re.weight_carried,
            re.finish_pos,
            re.finish_time_seconds,
            re.margin,
            re.odds,
            re.popularity,
            re.corner_order,
            re.remark,
            hm.win_rate,
            hm.place_rate,
            hm.show_rate,
            hm.races_count,
            hm.recent_score
        FROM race_entries re
        LEFT JOIN horses h ON re.horse_id = h.horse_id
        LEFT JOIN jockeys j ON re.jockey_id = j.jockey_id
        LEFT JOIN trainers t ON re.trainer_id = t.trainer_id
        LEFT JOIN horse_metrics hm ON re.horse_id = hm.horse_id
        WHERE re.race_id = ?
        ORDER BY re.horse_no
        """,
        (race_id,),
    )

    entries = [dict(row) for row in cursor.fetchall()]
    conn.close()
    return entries


def get_horse_details(horse_id: int) -> Optional[Dict[str, Any]]:
    """馬の詳細情報を取得

    Args:
        horse_id: 馬ID

    Returns:
        馬の詳細情報
    """
    conn = get_connection(read_only=True)
    cursor = conn.cursor()

    cursor.execute(
        """
        SELECT
            h.horse_id,
            h.raw_name,
            h.sex,
            h.birth_year,
            hm.races_count,
            hm.win_rate,
            hm.place_rate,
            hm.show_rate,
            hm.recent_score,
            hm.distance_pref,
            hm.surface_pref,
            hm.updated_at
        FROM horses h
        LEFT JOIN horse_metrics hm ON h.horse_id = hm.horse_id
        WHERE h.horse_id = ?
        """,
        (horse_id,),
    )

    row = cursor.fetchone()
    conn.close()

    return dict(row) if row else None


def get_horse_race_history(horse_id: int, limit: int = 50) -> List[Dict[str, Any]]:
    """馬の過去成績を取得

    Args:
        horse_id: 馬ID
        limit: 取得件数上限

    Returns:
        過去成績のリスト
    """
    conn = get_connection(read_only=True)
    cursor = conn.cursor()

    cursor.execute(
        """
        SELECT
            r.race_id,
            r.race_date,
            r.course,
            r.race_no,
            r.distance_m,
            r.surface,
            r.going,
            r.grade,
            r.title,
            re.frame_no,
            re.horse_no,
            re.age,
            re.weight_carried,
            re.finish_pos,
            re.finish_time_seconds,
            re.margin,
            re.odds,
            re.popularity,
            re.corner_order,
            j.raw_name as jockey_name,
            t.raw_name as trainer_name
        FROM race_entries re
        JOIN races r ON re.race_id = r.race_id
        LEFT JOIN jockeys j ON re.jockey_id = j.jockey_id
        LEFT JOIN trainers t ON re.trainer_id = t.trainer_id
        WHERE re.horse_id = ?
        ORDER BY r.race_date DESC
        LIMIT ?
        """,
        (horse_id, limit),
    )

    history = [dict(row) for row in cursor.fetchall()]
    conn.close()
    return history
