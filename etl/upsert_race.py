"""
レース情報（コース、距離、クラスなど）の登録・更新
"""

import logging
from typing import Dict, Any, List

from etl.base import ETLBase

logger = logging.getLogger(__name__)


class RaceUpsert(ETLBase):
    """レース情報のUPSERT処理"""

    def upsert_races(self, races: List[Dict[str, Any]]) -> int:
        """レース情報の登録・更新

        Args:
            races: レースデータリスト
                [
                    {
                        'race_date': '2024-01-01',
                        'course': '東京',
                        'race_no': 1,
                        'distance_m': 2000,
                        'surface': '芝',
                        'going': '良',
                        'grade': 'G1',
                        'title': 'レース名',
                    },
                    ...
                ]

        Returns:
            処理行数
        """
        count = 0
        conn = self.get_connection()
        cursor = conn.cursor()

        try:
            for race in races:
                try:
                    # unique 制約: (race_date, course, race_no)
                    cursor.execute(
                        """
                        INSERT OR REPLACE INTO races
                        (race_date, course, race_no, distance_m, surface, going, grade, title)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                        """,
                        (
                            race["race_date"],
                            race["course"],
                            race["race_no"],
                            race["distance_m"],
                            race["surface"],
                            race.get("going"),
                            race.get("grade"),
                            race.get("title"),
                        ),
                    )
                    count += 1

                except Exception as e:
                    logger.warning(
                        f"レースの登録に失敗: {race['race_date']} {race['course']} R{race['race_no']} - {e}"
                    )
                    continue

            conn.commit()
            logger.info(f"レースを登録・更新しました: {count}件")
            return count

        except Exception as e:
            logger.error(f"レース登録全体でエラー: {e}")
            conn.rollback()
            raise

        finally:
            conn.close()


def get_race_id(race_date: str, course: str, race_no: int) -> int:
    """レース識別子からレースIDを取得

    Args:
        race_date: 開催日
        course: 開催場
        race_no: レース番号

    Returns:
        レースID、見つからない場合は None
    """
    etl = RaceUpsert()
    conn = etl.get_connection(read_only=True)
    cursor = conn.cursor()

    try:
        cursor.execute(
            "SELECT race_id FROM races WHERE race_date=? AND course=? AND race_no=?",
            (race_date, course, race_no),
        )
        row = cursor.fetchone()
        return row[0] if row else None

    finally:
        conn.close()


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)

    # テスト
    etl = RaceUpsert()

    races = [
        {
            "race_date": "2024-01-01",
            "course": "東京",
            "race_no": 1,
            "distance_m": 2000,
            "surface": "芝",
            "going": "良",
            "grade": "G1",
            "title": "テストレース1",
        },
    ]

    print(f"レース: {etl.upsert_races(races)}")
