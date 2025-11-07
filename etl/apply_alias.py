"""
名称ゆれ補正
別名テーブルを参照して、正規IDに寄せる処理
"""

import logging
from typing import Dict, List

from etl.base import ETLBase

logger = logging.getLogger(__name__)


class AliasApplier(ETLBase):
    """名称ゆれ補正処理"""

    def apply_horse_aliases(self) -> int:
        """馬の別名を適用

        別名テーブルに登録された別名を用いて、出走情報に反映させる
        """
        conn = self.get_connection()
        cursor = conn.cursor()

        count = 0

        try:
            # 別名テーブルをスキャン
            cursor.execute("SELECT alias, horse_id FROM alias_horse")
            aliases = cursor.fetchall()

            for alias_row in aliases:
                alias, horse_id = alias_row[0], alias_row[1]

                # 同じ別名を持つ他の馬を検索
                cursor.execute(
                    "SELECT horse_id FROM horses WHERE raw_name=? AND horse_id != ?",
                    (alias, horse_id),
                )

                other_horses = cursor.fetchall()

                for other_horse_row in other_horses:
                    other_horse_id = other_horse_row[0]

                    # 他の馬の出走情報を正規馬に統合
                    cursor.execute(
                        """
                        UPDATE race_entries
                        SET horse_id = ?
                        WHERE horse_id = ? AND NOT EXISTS (
                            SELECT 1 FROM race_entries re2
                            WHERE re2.race_id = race_entries.race_id
                            AND re2.horse_id = ?
                        )
                        """,
                        (horse_id, other_horse_id, horse_id),
                    )

                    count += cursor.rowcount

                    # 他の馬が不要になったか確認（出走情報がなければ削除）
                    cursor.execute(
                        "SELECT COUNT(*) FROM race_entries WHERE horse_id=?",
                        (other_horse_id,),
                    )

                    if cursor.fetchone()[0] == 0:
                        cursor.execute(
                            "DELETE FROM horses WHERE horse_id=?",
                            (other_horse_id,),
                        )
                        logger.info(f"重複馬を削除: {other_horse_id}")

            conn.commit()
            logger.info(f"馬の別名を適用しました: {count}件")
            return count

        except Exception as e:
            logger.error(f"馬の別名適用に失敗: {e}")
            conn.rollback()
            raise

        finally:
            conn.close()

    def apply_jockey_aliases(self) -> int:
        """騎手の別名を適用"""
        conn = self.get_connection()
        cursor = conn.cursor()

        count = 0

        try:
            cursor.execute("SELECT alias, jockey_id FROM alias_jockey")
            aliases = cursor.fetchall()

            for alias_row in aliases:
                alias, jockey_id = alias_row[0], alias_row[1]

                cursor.execute(
                    "SELECT jockey_id FROM jockeys WHERE raw_name=? AND jockey_id != ?",
                    (alias, jockey_id),
                )

                other_jockeys = cursor.fetchall()

                for other_jockey_row in other_jockeys:
                    other_jockey_id = other_jockey_row[0]

                    cursor.execute(
                        """
                        UPDATE race_entries
                        SET jockey_id = ?
                        WHERE jockey_id = ? AND NOT EXISTS (
                            SELECT 1 FROM race_entries re2
                            WHERE re2.race_id = race_entries.race_id
                            AND re2.jockey_id = ?
                        )
                        """,
                        (jockey_id, other_jockey_id, jockey_id),
                    )

                    count += cursor.rowcount

                    cursor.execute(
                        "SELECT COUNT(*) FROM race_entries WHERE jockey_id=?",
                        (other_jockey_id,),
                    )

                    if cursor.fetchone()[0] == 0:
                        cursor.execute(
                            "DELETE FROM jockeys WHERE jockey_id=?",
                            (other_jockey_id,),
                        )
                        logger.info(f"重複騎手を削除: {other_jockey_id}")

            conn.commit()
            logger.info(f"騎手の別名を適用しました: {count}件")
            return count

        except Exception as e:
            logger.error(f"騎手の別名適用に失敗: {e}")
            conn.rollback()
            raise

        finally:
            conn.close()

    def apply_trainer_aliases(self) -> int:
        """調教師の別名を適用"""
        conn = self.get_connection()
        cursor = conn.cursor()

        count = 0

        try:
            cursor.execute("SELECT alias, trainer_id FROM alias_trainer")
            aliases = cursor.fetchall()

            for alias_row in aliases:
                alias, trainer_id = alias_row[0], alias_row[1]

                cursor.execute(
                    "SELECT trainer_id FROM trainers WHERE raw_name=? AND trainer_id != ?",
                    (alias, trainer_id),
                )

                other_trainers = cursor.fetchall()

                for other_trainer_row in other_trainers:
                    other_trainer_id = other_trainer_row[0]

                    cursor.execute(
                        """
                        UPDATE race_entries
                        SET trainer_id = ?
                        WHERE trainer_id = ? AND NOT EXISTS (
                            SELECT 1 FROM race_entries re2
                            WHERE re2.race_id = race_entries.race_id
                            AND re2.trainer_id = ?
                        )
                        """,
                        (trainer_id, other_trainer_id, trainer_id),
                    )

                    count += cursor.rowcount

                    cursor.execute(
                        "SELECT COUNT(*) FROM race_entries WHERE trainer_id=?",
                        (other_trainer_id,),
                    )

                    if cursor.fetchone()[0] == 0:
                        cursor.execute(
                            "DELETE FROM trainers WHERE trainer_id=?",
                            (other_trainer_id,),
                        )
                        logger.info(f"重複調教師を削除: {other_trainer_id}")

            conn.commit()
            logger.info(f"調教師の別名を適用しました: {count}件")
            return count

        except Exception as e:
            logger.error(f"調教師の別名適用に失敗: {e}")
            conn.rollback()
            raise

        finally:
            conn.close()

    def add_alias(self, alias_table: str, alias: str, canonical_id: int):
        """別名を追加（手動メンテナンス用）

        Args:
            alias_table: alias_horse|alias_jockey|alias_trainer
            alias: 別名
            canonical_id: 正規ID
        """
        try:
            self.upsert_or_insert(
                alias_table,
                {"alias": alias, f"{alias_table[6:-1]}_id": canonical_id},
                id_field="alias",
            )
            logger.info(f"別名を追加: {alias_table} {alias} -> {canonical_id}")

        except Exception as e:
            logger.error(f"別名追加に失敗: {e}")
            raise


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)

    # テスト
    applier = AliasApplier()
    # applier.apply_horse_aliases()
    # applier.apply_jockey_aliases()
    # applier.apply_trainer_aliases()

    print("Alias module loaded")
