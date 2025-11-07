"""
ETL処理の基本クラスと共通機能
"""

import sqlite3
import logging
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

DB_PATH = Path(__file__).parent.parent / "data" / "keiba.db"


class ETLBase:
    """ETL処理の基本クラス"""

    def __init__(self):
        self.db_path = DB_PATH

    def get_connection(self, read_only: bool = False) -> sqlite3.Connection:
        """データベース接続を取得"""
        if read_only:
            uri = f"file:{self.db_path}?mode=ro"
            conn = sqlite3.connect(uri, uri=True, timeout=10)
        else:
            conn = sqlite3.connect(str(self.db_path), timeout=10)

        conn.row_factory = sqlite3.Row
        return conn

    def execute_query(self, query: str, params: tuple = (), fetch: bool = False):
        """クエリを実行"""
        conn = self.get_connection()
        cursor = conn.cursor()

        try:
            cursor.execute(query, params)
            conn.commit()

            if fetch:
                return cursor.fetchall()

            return cursor.rowcount

        except Exception as e:
            logger.error(f"クエリ実行エラー: {e}")
            conn.rollback()
            raise

        finally:
            conn.close()

    def upsert_or_insert(
        self,
        table: str,
        data: dict,
        unique_cols: list = None,
        id_field: str = None,
    ) -> Optional[int]:
        """
        UPSERT操作 (INSERT OR REPLACE)

        Args:
            table: テーブル名
            data: 挿入・更新するデータ (辞書)
            unique_cols: 一意制約のカラム (指定時はこれで既存行チェック)
            id_field: プライマリキー (指定時は REPLACE を使用)

        Returns:
            挿入/更新されたID、または影響した行数
        """
        conn = self.get_connection()
        cursor = conn.cursor()

        try:
            # 既存行チェック
            if unique_cols:
                where_clause = " AND ".join([f"{col}=?" for col in unique_cols])
                values = [data[col] for col in unique_cols]

                cursor.execute(f"SELECT rowid FROM {table} WHERE {where_clause}", values)
                existing = cursor.fetchone()

                if existing:
                    # UPDATE
                    set_clause = ", ".join([f"{k}=?" for k in data.keys()])
                    values = list(data.values()) + [existing[0]]
                    cursor.execute(
                        f"UPDATE {table} SET {set_clause} WHERE rowid=?",
                        values,
                    )
                else:
                    # INSERT
                    cols = ", ".join(data.keys())
                    placeholders = ", ".join(["?"] * len(data))
                    cursor.execute(
                        f"INSERT INTO {table} ({cols}) VALUES ({placeholders})",
                        list(data.values()),
                    )
            else:
                # REPLACE
                cols = ", ".join(data.keys())
                placeholders = ", ".join(["?"] * len(data))
                cursor.execute(
                    f"INSERT OR REPLACE INTO {table} ({cols}) VALUES ({placeholders})",
                    list(data.values()),
                )

            conn.commit()
            return cursor.lastrowid

        except Exception as e:
            logger.error(f"UPSERT失敗: {table} - {e}")
            conn.rollback()
            raise

        finally:
            conn.close()

    def find_or_create(
        self,
        table: str,
        search_field: str,
        search_value: str,
        insert_data: dict = None,
    ) -> int:
        """
        検索し、見つからなければ作成

        Args:
            table: テーブル名
            search_field: 検索カラム
            search_value: 検索値
            insert_data: 挿入時に使用するデータ (search_field を含める必要がある)

        Returns:
            見つかった或いは作成されたID
        """
        conn = self.get_connection()
        cursor = conn.cursor()

        try:
            # 検索
            cursor.execute(
                f"SELECT rowid FROM {table} WHERE {search_field}=?",
                (search_value,),
            )
            existing = cursor.fetchone()

            if existing:
                return existing[0]

            # 作成
            if insert_data is None:
                insert_data = {search_field: search_value}
            else:
                insert_data[search_field] = search_value

            cols = ", ".join(insert_data.keys())
            placeholders = ", ".join(["?"] * len(insert_data))
            cursor.execute(
                f"INSERT INTO {table} ({cols}) VALUES ({placeholders})",
                list(insert_data.values()),
            )

            conn.commit()
            return cursor.lastrowid

        except Exception as e:
            logger.error(f"find_or_create失敗: {table}.{search_field} - {e}")
            conn.rollback()
            raise

        finally:
            conn.close()
