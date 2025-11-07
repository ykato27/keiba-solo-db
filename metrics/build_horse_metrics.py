"""
馬の成績指標を計算して horse_metrics テーブルに保存
"""

import logging
from typing import Dict, Any, Optional, List
import json
import sqlite3
from pathlib import Path
from collections import defaultdict

logger = logging.getLogger(__name__)

DB_PATH = Path(__file__).parent.parent / "data" / "keiba.db"

# ========================
# 指標計算の定義
# ========================

# 近走指数の計算
RECENT_RACES_COUNT = 5  # 直近何走を対象にするか

# 着順点の定義（古い走ほど低い重みを掛ける）
FINISH_POINTS = {
    1: 5,  # 1着
    2: 3,  # 2着
    3: 2,  # 3着
}

# 人気による係数（人気が高いほど加点を抑える）
POPULARITY_WEIGHT = {
    1: 1.0,
    2: 0.95,
    3: 0.90,
    4: 0.85,
    5: 0.80,
}


def get_connection(read_only: bool = False) -> sqlite3.Connection:
    """DB接続を取得"""
    if read_only:
        uri = f"file:{DB_PATH}?mode=ro"
        conn = sqlite3.connect(uri, uri=True, timeout=10)
    else:
        conn = sqlite3.connect(str(DB_PATH), timeout=10)

    conn.row_factory = sqlite3.Row
    return conn


def build_all_horse_metrics(incremental: bool = False) -> int:
    """全ての馬の指標を計算

    Args:
        incremental: インクリメンタル更新か (最終更新以降の馬のみ)

    Returns:
        更新した馬の数
    """
    conn = get_connection()
    cursor = conn.cursor()

    try:
        if incremental:
            # 最近更新されたレースに出走した馬のみを更新
            cursor.execute(
                """
                SELECT DISTINCT horse_id FROM race_entries
                WHERE race_id IN (
                    SELECT race_id FROM races
                    WHERE race_date >= date('now', '-7 days')
                )
                """
            )
        else:
            # 全ての馬を対象
            cursor.execute("SELECT DISTINCT horse_id FROM horses")

        horse_ids = [row[0] for row in cursor.fetchall()]
        conn.close()

        count = 0
        for horse_id in horse_ids:
            if _build_horse_metrics(horse_id):
                count += 1

        logger.info(f"馬の指標を計算しました: {count}件")
        return count

    except Exception as e:
        logger.error(f"指標計算に失敗: {e}")
        conn.close()
        raise


def _build_horse_metrics(horse_id: int) -> bool:
    """単一馬の指標を計算して保存

    Args:
        horse_id: 馬ID

    Returns:
        成功時は True
    """
    try:
        metrics = _calculate_horse_metrics(horse_id)

        if metrics is None:
            return False

        # horse_metrics テーブルに保存
        conn = get_connection()
        cursor = conn.cursor()

        cursor.execute(
            """
            INSERT OR REPLACE INTO horse_metrics
            (horse_id, races_count, win_rate, place_rate, show_rate, recent_score, distance_pref, surface_pref, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, datetime('now'))
            """,
            (
                horse_id,
                metrics["races_count"],
                metrics["win_rate"],
                metrics["place_rate"],
                metrics["show_rate"],
                metrics["recent_score"],
                metrics["distance_pref_json"],
                metrics["surface_pref_json"],
            ),
        )

        conn.commit()
        conn.close()

        return True

    except Exception as e:
        logger.error(f"馬 {horse_id} の指標計算に失敗: {e}")
        return False


def _calculate_horse_metrics(horse_id: int) -> Optional[Dict[str, Any]]:
    """馬の指標を計算

    Args:
        horse_id: 馬ID

    Returns:
        指標データ
    """
    conn = get_connection(read_only=True)
    cursor = conn.cursor()

    try:
        # その馬の全出走情報を取得
        cursor.execute(
            """
            SELECT finish_pos, popularity, race_id FROM race_entries
            WHERE horse_id = ?
            ORDER BY race_id DESC
            """,
            (horse_id,),
        )

        entries = cursor.fetchall()

        if not entries:
            conn.close()
            return None

        races_count = len(entries)

        # 1. 勝率、連対率、複勝率
        wins = sum(1 for e in entries if e[0] == 1)
        places = sum(1 for e in entries if e[0] in (1, 2))
        shows = sum(1 for e in entries if e[0] in (1, 2, 3))

        win_rate = wins / races_count if races_count > 0 else 0
        place_rate = places / races_count if races_count > 0 else 0
        show_rate = shows / races_count if races_count > 0 else 0

        # 2. 近走指数（直近5走を重み付きで合算）
        recent_score = _calculate_recent_score(entries[:RECENT_RACES_COUNT])

        # 3. 距離別成績
        distance_pref = _calculate_distance_preference(horse_id)

        # 4. 馬場別成績
        surface_pref = _calculate_surface_preference(horse_id)

        conn.close()

        return {
            "races_count": races_count,
            "win_rate": round(win_rate, 4),
            "place_rate": round(place_rate, 4),
            "show_rate": round(show_rate, 4),
            "recent_score": round(recent_score, 2),
            "distance_pref_json": json.dumps(distance_pref, ensure_ascii=False),
            "surface_pref_json": json.dumps(surface_pref, ensure_ascii=False),
        }

    except Exception as e:
        logger.error(f"馬 {horse_id} の指標計算エラー: {e}")
        conn.close()
        return None


def _calculate_recent_score(recent_entries: List) -> float:
    """近走指数を計算

    直近5走を対象に、着順と人気から指数を計算
    """
    score = 0.0

    for i, entry in enumerate(recent_entries):
        finish_pos = entry[0]
        popularity = entry[1]

        # 着順点を取得（着外なら0）
        points = FINISH_POINTS.get(finish_pos, 0)

        # 古い走ほど重みを下げる
        recency_weight = (RECENT_RACES_COUNT - i) / RECENT_RACES_COUNT

        # 人気による係数
        popularity_coef = POPULARITY_WEIGHT.get(popularity, 0.75)

        # スコアに加算
        score += points * recency_weight * popularity_coef

    return score


def _calculate_distance_preference(horse_id: int) -> Dict[str, Any]:
    """距離別成績を計算

    Args:
        horse_id: 馬ID

    Returns:
        距離別成績
        {
            "1200m": {"races": 5, "wins": 1, "places": 2},
            ...
        }
    """
    conn = get_connection(read_only=True)
    cursor = conn.cursor()

    try:
        cursor.execute(
            """
            SELECT r.distance_m, re.finish_pos
            FROM race_entries re
            JOIN races r ON re.race_id = r.race_id
            WHERE re.horse_id = ?
            """,
            (horse_id,),
        )

        entries = cursor.fetchall()
        conn.close()

        distance_stats = defaultdict(lambda: {"races": 0, "wins": 0, "places": 0})

        for distance, finish_pos in entries:
            distance_key = f"{distance}m"
            distance_stats[distance_key]["races"] += 1

            if finish_pos == 1:
                distance_stats[distance_key]["wins"] += 1
            if finish_pos in (1, 2):
                distance_stats[distance_key]["places"] += 1

        return dict(distance_stats)

    except Exception as e:
        logger.error(f"距離別成績計算エラー: {e}")
        conn.close()
        return {}


def _calculate_surface_preference(horse_id: int) -> Dict[str, Any]:
    """馬場別成績を計算

    Args:
        horse_id: 馬ID

    Returns:
        馬場別成績
        {
            "芝": {"races": 10, "wins": 2, "places": 4},
            "ダート": {"races": 5, "wins": 1, "places": 2},
        }
    """
    conn = get_connection(read_only=True)
    cursor = conn.cursor()

    try:
        cursor.execute(
            """
            SELECT r.surface, re.finish_pos
            FROM race_entries re
            JOIN races r ON re.race_id = r.race_id
            WHERE re.horse_id = ?
            """,
            (horse_id,),
        )

        entries = cursor.fetchall()
        conn.close()

        surface_stats = defaultdict(lambda: {"races": 0, "wins": 0, "places": 0})

        for surface, finish_pos in entries:
            surface_stats[surface]["races"] += 1

            if finish_pos == 1:
                surface_stats[surface]["wins"] += 1
            if finish_pos in (1, 2):
                surface_stats[surface]["places"] += 1

        return dict(surface_stats)

    except Exception as e:
        logger.error(f"馬場別成績計算エラー: {e}")
        conn.close()
        return {}


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)

    # 全馬の指標を計算
    count = build_all_horse_metrics(incremental=False)
    print(f"計算完了: {count}件")
