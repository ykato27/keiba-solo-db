"""
マスタデータ（馬、騎手、調教師）の登録・更新
"""

import logging
from typing import Dict, Any, List
import json

from etl.base import ETLBase

logger = logging.getLogger(__name__)


class MasterDataUpsert(ETLBase):
    """マスタデータのUPSERT処理"""

    def upsert_horses(self, horses: List[Dict[str, Any]]) -> int:
        """馬データの登録・更新

        Args:
            horses: 馬データリスト
                [
                    {
                        'raw_name': '馬名',
                        'sex': '牡|牝|セ',
                        'birth_year': 2020,
                    },
                    ...
                ]

        Returns:
            処理行数
        """
        count = 0

        for horse in horses:
            try:
                # raw_name で検索（名称ゆれは後から補正表で対応）
                self.find_or_create(
                    "horses",
                    "raw_name",
                    horse["raw_name"],
                    {
                        "raw_name": horse["raw_name"],
                        "sex": horse.get("sex"),
                        "birth_year": horse.get("birth_year"),
                    },
                )
                count += 1

            except Exception as e:
                logger.warning(f"馬の登録に失敗: {horse['raw_name']} - {e}")
                continue

        logger.info(f"馬を登録・更新しました: {count}件")
        return count

    def upsert_jockeys(self, jockeys: List[Dict[str, Any]]) -> int:
        """騎手データの登録・更新

        Args:
            jockeys: 騎手データリスト
                [
                    {
                        'raw_name': '騎手名',
                    },
                    ...
                ]

        Returns:
            処理行数
        """
        count = 0

        for jockey in jockeys:
            try:
                self.find_or_create(
                    "jockeys",
                    "raw_name",
                    jockey["raw_name"],
                )
                count += 1

            except Exception as e:
                logger.warning(f"騎手の登録に失敗: {jockey['raw_name']} - {e}")
                continue

        logger.info(f"騎手を登録・更新しました: {count}件")
        return count

    def upsert_trainers(self, trainers: List[Dict[str, Any]]) -> int:
        """調教師データの登録・更新

        Args:
            trainers: 調教師データリスト
                [
                    {
                        'raw_name': '調教師名',
                    },
                    ...
                ]

        Returns:
            処理行数
        """
        count = 0

        for trainer in trainers:
            try:
                self.find_or_create(
                    "trainers",
                    "raw_name",
                    trainer["raw_name"],
                )
                count += 1

            except Exception as e:
                logger.warning(f"調教師の登録に失敗: {trainer['raw_name']} - {e}")
                continue

        logger.info(f"調教師を登録・更新しました: {count}件")
        return count


def get_id_by_name(table: str, raw_name: str) -> int:
    """名前からIDを取得

    Args:
        table: テーブル名 (horses|jockeys|trainers)
        raw_name: 名前

    Returns:
        ID、見つからない場合は None
    """
    etl = MasterDataUpsert()
    conn = etl.get_connection(read_only=True)
    cursor = conn.cursor()

    try:
        cursor.execute(
            f"SELECT rowid FROM {table} WHERE raw_name=?",
            (raw_name,),
        )
        row = cursor.fetchone()
        return row[0] if row else None

    finally:
        conn.close()


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)

    # テスト
    etl = MasterDataUpsert()

    horses = [
        {"raw_name": "テスト馬1", "sex": "牡", "birth_year": 2020},
        {"raw_name": "テスト馬2", "sex": "牝", "birth_year": 2021},
    ]

    jockeys = [
        {"raw_name": "テスト騎手1"},
        {"raw_name": "テスト騎手2"},
    ]

    trainers = [
        {"raw_name": "テスト調教師1"},
        {"raw_name": "テスト調教師2"},
    ]

    print(f"馬: {etl.upsert_horses(horses)}")
    print(f"騎手: {etl.upsert_jockeys(jockeys)}")
    print(f"調教師: {etl.upsert_trainers(trainers)}")
