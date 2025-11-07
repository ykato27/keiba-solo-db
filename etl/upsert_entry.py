"""
出走情報（枠番、馬番、騎手、結果など）の登録・更新
"""

import logging
from typing import Dict, Any, List

from etl.base import ETLBase
from etl.upsert_master import get_id_by_name
from etl.upsert_race import get_race_id

logger = logging.getLogger(__name__)


class EntryUpsert(ETLBase):
    """出走情報のUPSERT処理"""

    def upsert_entries(self, entries: List[Dict[str, Any]]) -> int:
        """出走情報の登録・更新

        Args:
            entries: 出走データリスト
                [
                    {
                        'race_date': '2024-01-01',
                        'course': '東京',
                        'race_no': 1,
                        'horse_name': '馬名',
                        'jockey_name': '騎手名',
                        'trainer_name': '調教師名',
                        'frame_no': 1,
                        'horse_no': 1,
                        'age': 3,
                        'weight_carried': 55.0,
                        'finish_pos': 1,  # 出馬表段階では null
                        'finish_time_seconds': 120.5,  # 出馬表段階では null
                        'margin': '1",  # 出馬表段階では null
                        'odds': 2.5,
                        'popularity': 1,
                        'corner_order': '1-1-1',  # 出馬表段階では null
                        'remark': '良',  # 出馬表段階では null
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
            for entry in entries:
                try:
                    # 1. レースID取得
                    race_id = get_race_id(
                        entry["race_date"],
                        entry["course"],
                        entry["race_no"],
                    )

                    if not race_id:
                        logger.warning(
                            f"レースが見つかりません: {entry['race_date']} {entry['course']} R{entry['race_no']}"
                        )
                        continue

                    # 2. 馬ID取得
                    horse_id = get_id_by_name("horses", entry["horse_name"])
                    if not horse_id:
                        logger.warning(f"馬が見つかりません: {entry['horse_name']}")
                        continue

                    # 3. 騎手ID取得（optional）
                    jockey_id = None
                    if entry.get("jockey_name"):
                        jockey_id = get_id_by_name("jockeys", entry["jockey_name"])

                    # 4. 調教師ID取得（optional）
                    trainer_id = None
                    if entry.get("trainer_name"):
                        trainer_id = get_id_by_name("trainers", entry["trainer_name"])

                    # 5. 出走情報をUPSERT
                    cursor.execute(
                        """
                        INSERT OR REPLACE INTO race_entries
                        (race_id, horse_id, jockey_id, trainer_id, frame_no, horse_no,
                         age, weight_carried, finish_pos, finish_time_seconds, margin,
                         odds, popularity, corner_order, remark)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                        """,
                        (
                            race_id,
                            horse_id,
                            jockey_id,
                            trainer_id,
                            entry.get("frame_no"),
                            entry.get("horse_no"),
                            entry.get("age"),
                            entry.get("weight_carried"),
                            entry.get("finish_pos"),
                            entry.get("finish_time_seconds"),
                            entry.get("margin"),
                            entry.get("odds"),
                            entry.get("popularity"),
                            entry.get("corner_order"),
                            entry.get("remark"),
                        ),
                    )
                    count += 1

                except Exception as e:
                    logger.warning(
                        f"出走情報の登録に失敗: {entry.get('horse_name')} - {e}"
                    )
                    continue

            conn.commit()
            logger.info(f"出走情報を登録・更新しました: {count}件")
            return count

        except Exception as e:
            logger.error(f"出走情報登録全体でエラー: {e}")
            conn.rollback()
            raise

        finally:
            conn.close()

    def update_result_fields(
        self,
        race_id: int,
        horse_id: int,
        result_data: Dict[str, Any],
    ) -> bool:
        """出走結果フィールドを更新（結果が確定した場合のみ）

        Args:
            race_id: レースID
            horse_id: 馬ID
            result_data: 更新するデータ
                {
                    'finish_pos': 1,
                    'finish_time_seconds': 120.5,
                    'margin': '1",
                    'corner_order': '1-1-1',
                    'remark': '良',
                }

        Returns:
            成功時は True
        """
        conn = self.get_connection()
        cursor = conn.cursor()

        try:
            update_fields = []
            values = []

            for key in [
                "finish_pos",
                "finish_time_seconds",
                "margin",
                "corner_order",
                "remark",
            ]:
                if key in result_data and result_data[key] is not None:
                    update_fields.append(f"{key}=?")
                    values.append(result_data[key])

            if not update_fields:
                logger.warning("更新フィールドがありません")
                return False

            values.extend([race_id, horse_id])

            cursor.execute(
                f"""
                UPDATE race_entries
                SET {', '.join(update_fields)}
                WHERE race_id=? AND horse_id=?
                """,
                values,
            )

            conn.commit()
            return cursor.rowcount > 0

        except Exception as e:
            logger.error(f"結果更新に失敗: {e}")
            conn.rollback()
            return False

        finally:
            conn.close()


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)

    # テスト用
    print("ETL module loaded")
