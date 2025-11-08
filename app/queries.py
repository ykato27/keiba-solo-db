"""
Streamlitアプリで頻出するクエリ（キャッシング対応）

Streamlit @st.cache_data デコレータを使用したクエリ集。
app/db.py とは異なり、頻繁にアクセスされるクエリを Streamlit キャッシュで高速化。

使用例：
    from app import queries
    dates = queries.get_all_race_dates()  # 1時間キャッシュ
"""

import streamlit as st
import sqlite3
from typing import List, Dict, Any
from pathlib import Path

_PROJECT_ROOT = Path(__file__).resolve().parent.parent
DB_PATH = _PROJECT_ROOT / "data" / "keiba.db"


@st.cache_data(ttl=3600)  # 1時間キャッシュ
def get_all_race_dates() -> List[str]:
    """全開催日を取得"""
    conn = sqlite3.connect(str(DB_PATH))
    try:
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        cursor.execute("SELECT DISTINCT race_date FROM races ORDER BY race_date DESC")
        dates = [row[0] for row in cursor.fetchall()]
        return dates
    finally:
        conn.close()


@st.cache_data(ttl=3600)
def get_courses_by_date(race_date: str) -> List[str]:
    """指定日の開催場一覧を取得"""
    conn = sqlite3.connect(str(DB_PATH))
    try:
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        cursor.execute(
            "SELECT DISTINCT course FROM races WHERE race_date = ? ORDER BY course",
            (race_date,),
        )
        courses = [row[0] for row in cursor.fetchall()]
        return courses
    finally:
        conn.close()


@st.cache_data(ttl=3600)
def get_races(race_date: str, course: str) -> List[Dict[str, Any]]:
    """指定日時の開催場のレース一覧を取得"""
    conn = sqlite3.connect(str(DB_PATH))
    try:
        conn.row_factory = sqlite3.Row
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
        return races
    finally:
        conn.close()


@st.cache_data(ttl=1800)  # 30分キャッシュ
def get_race_entries_with_metrics(race_id: int) -> List[Dict[str, Any]]:
    """レースの出走馬を指標付きで取得"""
    conn = sqlite3.connect(str(DB_PATH))
    try:
        conn.row_factory = sqlite3.Row
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
                COALESCE(hm.win_rate, 0) as win_rate,
                COALESCE(hm.place_rate, 0) as place_rate,
                COALESCE(hm.show_rate, 0) as show_rate,
                COALESCE(hm.races_count, 0) as races_count,
                COALESCE(hm.recent_score, 0) as recent_score
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
        return entries
    finally:
        conn.close()


@st.cache_data(ttl=3600)
def get_horse_details(horse_id: int) -> Dict[str, Any]:
    """馬の詳細情報を取得"""
    conn = sqlite3.connect(str(DB_PATH))
    try:
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT
                h.horse_id,
                h.raw_name,
                h.sex,
                h.birth_year,
                COALESCE(hm.races_count, 0) as races_count,
                COALESCE(hm.win_rate, 0) as win_rate,
                COALESCE(hm.place_rate, 0) as place_rate,
                COALESCE(hm.show_rate, 0) as show_rate,
                COALESCE(hm.recent_score, 0) as recent_score,
                COALESCE(hm.distance_pref, '{}') as distance_pref,
                COALESCE(hm.surface_pref, '{}') as surface_pref,
                COALESCE(hm.updated_at, '') as updated_at
            FROM horses h
            LEFT JOIN horse_metrics hm ON h.horse_id = hm.horse_id
            WHERE h.horse_id = ?
            """,
            (horse_id,),
        )
        row = cursor.fetchone()
        return dict(row) if row else {}
    finally:
        conn.close()


@st.cache_data(ttl=3600)
def get_horse_race_history(horse_id: int, limit: int = 50) -> List[Dict[str, Any]]:
    """馬の過去成績を取得"""
    conn = sqlite3.connect(str(DB_PATH))
    try:
        conn.row_factory = sqlite3.Row
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
        return history
    finally:
        conn.close()
