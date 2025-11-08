"""
CSVエクスポート機能
JRAデータと学習用特徴量データをCSV形式でエクスポート
"""

import csv
import io
from datetime import datetime
from typing import List, Dict, Any
import pandas as pd

from app import queries, features as feat_module


def export_race_entries_to_csv(race_id: int) -> str:
    """
    単一レースの出走馬情報をCSV形式でエクスポート

    Args:
        race_id: レースID

    Returns:
        CSV文字列
    """
    entries = queries.get_race_entries_with_metrics(race_id)

    if not entries:
        return ""

    # DataFrameに変換
    df = pd.DataFrame(entries)

    # 不要なカラムを削除
    drop_cols = [col for col in df.columns if col in ['created_at', 'updated_at']]
    if drop_cols:
        df = df.drop(columns=drop_cols)

    # CSV形式に変換
    csv_buffer = io.StringIO()
    df.to_csv(csv_buffer, index=False, encoding='utf-8-sig')

    return csv_buffer.getvalue()


def export_all_races_to_csv(start_date: str = None, end_date: str = None) -> str:
    """
    指定期間のすべてのレース情報をCSV形式でエクスポート

    Args:
        start_date: 開始日 (YYYY-MM-DD)
        end_date: 終了日 (YYYY-MM-DD)

    Returns:
        CSV文字列
    """
    from app import db

    conn = db.get_connection()
    cursor = conn.cursor()

    if start_date and end_date:
        query = """
            SELECT *
            FROM races
            WHERE race_date BETWEEN ? AND ?
            ORDER BY race_date DESC, course, race_no
        """
        cursor.execute(query, (start_date, end_date))
    else:
        query = """
            SELECT *
            FROM races
            ORDER BY race_date DESC, course, race_no
        """
        cursor.execute(query)

    # カラム名を取得（fetchする前に）
    columns = [description[0] for description in cursor.description]
    races = cursor.fetchall()
    conn.close()

    if not races:
        return ""

    # DataFrameに変換
    df = pd.DataFrame([dict(zip(columns, race)) for race in races])

    # CSV形式に変換
    csv_buffer = io.StringIO()
    df.to_csv(csv_buffer, index=False, encoding='utf-8-sig')

    return csv_buffer.getvalue()


def export_training_features_to_csv() -> str:
    """
    モデル学習用の特徴量データをCSV形式でエクスポート

    Returns:
        CSV文字列
    """
    from app import db

    conn = db.get_connection()
    cursor = conn.cursor()

    # 着順が記録されているエントリを取得
    cursor.execute("""
        SELECT DISTINCT
            e.entry_id,
            e.horse_id,
            e.race_id,
            r.race_date,
            r.distance_m,
            r.surface,
            h.raw_name as horse_name,
            h.sex,
            h.birth_year,
            e.age,
            e.weight_carried,
            e.horse_weight,
            e.days_since_last_race,
            e.is_steeplechase,
            e.odds,
            e.popularity,
            e.finish_pos,
            j.raw_name as jockey_name,
            t.raw_name as trainer_name,
            hm.races_count,
            hm.win_rate,
            hm.place_rate,
            hm.show_rate,
            hm.recent_score,
            hm.distance_pref,
            hm.surface_pref
        FROM race_entries e
        JOIN races r ON e.race_id = r.race_id
        JOIN horses h ON e.horse_id = h.horse_id
        LEFT JOIN jockeys j ON e.jockey_id = j.jockey_id
        LEFT JOIN trainers t ON e.trainer_id = t.trainer_id
        LEFT JOIN horse_metrics hm ON e.horse_id = hm.horse_id
        WHERE e.finish_pos IS NOT NULL AND e.finish_pos > 0
        ORDER BY r.race_date ASC
        LIMIT 5000
    """)

    entries = cursor.fetchall()
    columns = [description[0] for description in cursor.description]
    conn.close()

    if not entries:
        return ""

    # 各エントリから特徴量を抽出
    feature_rows = []

    for entry in entries:
        entry_dict = dict(zip(columns, entry))

        try:
            # 馬の詳細情報を構築
            horse_details = {
                'horse_id': entry_dict['horse_id'],
                'raw_name': entry_dict['horse_name'],
                'sex': entry_dict['sex'],
                'birth_year': entry_dict['birth_year'],
                'races_count': entry_dict['races_count'],
                'win_rate': entry_dict['win_rate'],
                'place_rate': entry_dict['place_rate'],
                'show_rate': entry_dict['show_rate'],
                'recent_score': entry_dict['recent_score'],
                'distance_pref': entry_dict['distance_pref'],
                'surface_pref': entry_dict['surface_pref'],
            }

            # レース情報を構築
            race_info = {
                'distance_m': entry_dict['distance_m'],
                'surface': entry_dict['surface'],
            }

            # 出走情報を構築
            entry_info = {
                'horse_weight': entry_dict['horse_weight'] or 450,
                'weight_carried': entry_dict['weight_carried'] or 54,
                'days_since_last_race': entry_dict['days_since_last_race'] or 14,
                'is_steeplechase': entry_dict['is_steeplechase'] or 0,
                'age': entry_dict['age'] or 4,
            }

            # 特徴量を抽出
            features_dict = feat_module.extract_features_for_horse(
                horse_details,
                race_info=race_info,
                entry_info=entry_info
            )

            # ターゲット変数を追加
            finish_pos = entry_dict['finish_pos']
            if finish_pos == 1:
                target = 0
            elif finish_pos in (2, 3):
                target = 1
            else:
                target = 2

            # 基本情報 + 特徴量 + ターゲット
            row = {
                'entry_id': entry_dict['entry_id'],
                'horse_id': entry_dict['horse_id'],
                'horse_name': entry_dict['horse_name'],
                'race_date': entry_dict['race_date'],
                'race_id': entry_dict['race_id'],
                'distance_m': entry_dict['distance_m'],
                'surface': entry_dict['surface'],
                'finish_pos': finish_pos,
                'target': target,
                'target_label': ['1着', '2-3着', 'その他'][target],
                **features_dict
            }

            feature_rows.append(row)

        except Exception as e:
            # エラーが発生したエントリはスキップ
            continue

    if not feature_rows:
        return ""

    # DataFrameに変換
    df = pd.DataFrame(feature_rows)

    # CSV形式に変換
    csv_buffer = io.StringIO()
    df.to_csv(csv_buffer, index=False, encoding='utf-8-sig')

    return csv_buffer.getvalue()


def export_horse_metrics_to_csv() -> str:
    """
    馬のメトリクスデータをCSV形式でエクスポート

    Returns:
        CSV文字列
    """
    from app import db

    conn = db.get_connection()
    cursor = conn.cursor()

    cursor.execute("""
        SELECT
            hm.horse_id,
            h.raw_name as horse_name,
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
        FROM horse_metrics hm
        JOIN horses h ON hm.horse_id = h.horse_id
        ORDER BY hm.recent_score DESC
    """)

    metrics = cursor.fetchall()
    columns = [description[0] for description in cursor.description]
    conn.close()

    if not metrics:
        return ""

    # DataFrameに変換
    df = pd.DataFrame([dict(zip(columns, metric)) for metric in metrics])

    # CSV形式に変換
    csv_buffer = io.StringIO()
    df.to_csv(csv_buffer, index=False, encoding='utf-8-sig')

    return csv_buffer.getvalue()


def export_entry_details_to_csv(race_id: int = None, start_date: str = None, end_date: str = None) -> str:
    """
    出走情報の詳細データをCSV形式でエクスポート

    Args:
        race_id: レースID（指定時は1レースのみ）
        start_date: 開始日
        end_date: 終了日

    Returns:
        CSV文字列
    """
    try:
        from app import db

        conn = db.get_connection()
        cursor = conn.cursor()

        if race_id:
            query = """
                SELECT
                    e.entry_id,
                    e.race_id,
                    r.race_date,
                    r.course,
                    r.race_no,
                    r.distance_m,
                    r.surface,
                    r.going,
                    r.grade,
                    h.raw_name as horse_name,
                    j.raw_name as jockey_name,
                    t.raw_name as trainer_name,
                    e.frame_no,
                    e.horse_no,
                    e.age,
                    e.weight_carried,
                    e.horse_weight,
                    e.days_since_last_race,
                    e.is_steeplechase,
                    e.odds,
                    e.popularity,
                    e.finish_pos,
                    e.finish_time_seconds,
                    e.margin,
                    e.corner_order,
                    e.remark
                FROM race_entries e
                JOIN races r ON e.race_id = r.race_id
                LEFT JOIN horses h ON e.horse_id = h.horse_id
                LEFT JOIN jockeys j ON e.jockey_id = j.jockey_id
                LEFT JOIN trainers t ON e.trainer_id = t.trainer_id
                WHERE e.race_id = ?
                ORDER BY e.horse_no
            """
            cursor.execute(query, (race_id,))
        elif start_date and end_date:
            query = """
                SELECT
                    e.entry_id,
                    e.race_id,
                    r.race_date,
                    r.course,
                    r.race_no,
                    r.distance_m,
                    r.surface,
                    r.going,
                    r.grade,
                    h.raw_name as horse_name,
                    j.raw_name as jockey_name,
                    t.raw_name as trainer_name,
                    e.frame_no,
                    e.horse_no,
                    e.age,
                    e.weight_carried,
                    e.horse_weight,
                    e.days_since_last_race,
                    e.is_steeplechase,
                    e.odds,
                    e.popularity,
                    e.finish_pos,
                    e.finish_time_seconds,
                    e.margin,
                    e.corner_order,
                    e.remark
                FROM race_entries e
                JOIN races r ON e.race_id = r.race_id
                LEFT JOIN horses h ON e.horse_id = h.horse_id
                LEFT JOIN jockeys j ON e.jockey_id = j.jockey_id
                LEFT JOIN trainers t ON e.trainer_id = t.trainer_id
                WHERE r.race_date BETWEEN ? AND ?
                ORDER BY r.race_date DESC, r.course, r.race_no, e.horse_no
                LIMIT 10000
            """
            cursor.execute(query, (start_date, end_date))
        else:
            query = """
                SELECT
                    e.entry_id,
                    e.race_id,
                    r.race_date,
                    r.course,
                    r.race_no,
                    r.distance_m,
                    r.surface,
                    r.going,
                    r.grade,
                    h.raw_name as horse_name,
                    j.raw_name as jockey_name,
                    t.raw_name as trainer_name,
                    e.frame_no,
                    e.horse_no,
                    e.age,
                    e.weight_carried,
                    e.horse_weight,
                    e.days_since_last_race,
                    e.is_steeplechase,
                    e.odds,
                    e.popularity,
                    e.finish_pos,
                    e.finish_time_seconds,
                    e.margin,
                    e.corner_order,
                    e.remark
                FROM race_entries e
                JOIN races r ON e.race_id = r.race_id
                LEFT JOIN horses h ON e.horse_id = h.horse_id
                LEFT JOIN jockeys j ON e.jockey_id = j.jockey_id
                LEFT JOIN trainers t ON e.trainer_id = t.trainer_id
                ORDER BY r.race_date DESC, r.course, r.race_no, e.horse_no
                LIMIT 10000
            """
            cursor.execute(query)

        # カラム名をfetchする前に取得
        columns = [description[0] for description in cursor.description]
        entries = cursor.fetchall()
        conn.close()

        if not entries:
            return ""

        # DataFrameに変換
        df = pd.DataFrame([dict(zip(columns, entry)) for entry in entries])

        # CSV形式に変換
        csv_buffer = io.StringIO()
        df.to_csv(csv_buffer, index=False, encoding='utf-8-sig')

        return csv_buffer.getvalue()

    except Exception as e:
        print(f"Error in export_entry_details_to_csv: {e}")
        import traceback
        traceback.print_exc()
        return ""
