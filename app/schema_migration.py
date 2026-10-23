"""
スキーママイグレーション管理
CRITICAL改善：オッズデータ統合のためのスキーマ拡張

マイグレーション内容:
1. race_entries テーブルに オッズ関連カラムを追加
   - opening_odds: 開始時オッズ
   - win_odds: 単勝オッズ
   - place_odds: 複勝オッズ
   - odds_timestamp: オッズ取得時刻

2. race_odds テーブルを新規作成（時系列オッズ追跡用）
   - レース中のオッズ変動を記録
"""

import sqlite3
import logging
from typing import Dict, List, Any

from app import db as app_db

logger = logging.getLogger(__name__)


def check_column_exists(conn: sqlite3.Connection, table: str, column: str) -> bool:
    """
    特定のテーブルのカラムが存在するかチェック

    Args:
        conn: SQLite接続
        table: テーブル名
        column: カラム名

    Returns:
        カラムが存在するか
    """
    cursor = conn.cursor()
    try:
        cursor.execute(f"PRAGMA table_info({table})")
        columns = cursor.fetchall()
        column_names = [col[1] for col in columns]
        return column in column_names
    except Exception as e:
        logger.error(f"カラム確認エラー: {e}")
        return False


def migrate_add_odds_columns():
    """race_entriesテーブルにオッズ関連カラムを追加"""
    conn = app_db.get_connection()
    cursor = conn.cursor()

    migration_results = {
        "status": "success",
        "added_columns": [],
        "skipped_columns": [],
        "errors": [],
    }

    try:
        # 追加するカラムの定義
        columns_to_add = [
            ("opening_odds", "REAL", "NULL", "開始時オッズ"),
            ("win_odds", "REAL", "NULL", "単勝オッズ（確定）"),
            ("place_odds", "REAL", "NULL", "複勝オッズ（確定）"),
            ("odds_timestamp", "TEXT", "NULL", "オッズ取得時刻（ISO 8601）"),
        ]

        for col_name, col_type, default, description in columns_to_add:
            if check_column_exists(conn, "race_entries", col_name):
                migration_results["skipped_columns"].append(
                    {"name": col_name, "reason": "カラムが既に存在"}
                )
                logger.info(f"スキップ: {col_name} は既に存在します")
                continue

            # カラムを追加
            alter_sql = f"""
            ALTER TABLE race_entries
            ADD COLUMN {col_name} {col_type} DEFAULT {default}
            """

            try:
                cursor.execute(alter_sql)
                migration_results["added_columns"].append(
                    {"name": col_name, "type": col_type, "description": description}
                )
                logger.info(f"追加成功: {col_name}")
            except sqlite3.OperationalError as e:
                error_msg = f"カラム追加失敗 {col_name}: {e}"
                migration_results["errors"].append(error_msg)
                logger.error(error_msg)

        conn.commit()

    except Exception as e:
        logger.error(f"マイグレーション中にエラー: {e}")
        conn.rollback()
        migration_results["status"] = "error"
        migration_results["errors"].append(str(e))

    finally:
        conn.close()

    return migration_results


def create_race_odds_table():
    """race_oddsテーブルを作成（時系列オッズ追跡）"""
    conn = app_db.get_connection()
    cursor = conn.cursor()

    create_sql = """
    CREATE TABLE IF NOT EXISTS race_odds (
        odds_id INTEGER PRIMARY KEY,
        entry_id INTEGER NOT NULL REFERENCES race_entries(entry_id) ON DELETE CASCADE,
        race_id INTEGER NOT NULL REFERENCES races(race_id) ON DELETE CASCADE,
        horse_id INTEGER NOT NULL REFERENCES horses(horse_id),
        odds REAL NOT NULL,                          -- 現在のオッズ
        odds_type TEXT NOT NULL,                     -- 'win', 'place', 'quinella'など
        recorded_at TEXT NOT NULL,                   -- 記録時刻（ISO 8601）
        is_final INTEGER DEFAULT 0,                  -- 最終オッズか
        UNIQUE (entry_id, odds_type, recorded_at)
    )
    """

    try:
        cursor.execute(create_sql)
        conn.commit()
        logger.info("race_oddsテーブルを作成しました")
        return {"status": "success", "message": "テーブル作成成功"}
    except sqlite3.OperationalError as e:
        if "already exists" in str(e):
            logger.info("race_oddsテーブルは既に存在します")
            return {"status": "info", "message": "テーブルは既に存在"}
        else:
            logger.error(f"テーブル作成エラー: {e}")
            return {"status": "error", "message": str(e)}
    except Exception as e:
        logger.error(f"予期しないエラー: {e}")
        return {"status": "error", "message": str(e)}
    finally:
        conn.close()


def create_odds_indexes():
    """オッズテーブルのインデックスを作成"""
    conn = app_db.get_connection()
    cursor = conn.cursor()

    indexes = [
        ("idx_race_odds_entry", "race_odds(entry_id)"),
        ("idx_race_odds_race", "race_odds(race_id)"),
        ("idx_race_odds_timestamp", "race_odds(recorded_at)"),
        ("idx_race_odds_final", "race_odds(is_final)"),
    ]

    results = {"created": [], "skipped": [], "errors": []}

    try:
        for index_name, index_def in indexes:
            try:
                create_index_sql = f"CREATE INDEX IF NOT EXISTS {index_name} ON {index_def}"
                cursor.execute(create_index_sql)
                results["created"].append(index_name)
                logger.info(f"インデックス作成: {index_name}")
            except sqlite3.OperationalError as e:
                if "already exists" in str(e):
                    results["skipped"].append(index_name)
                else:
                    results["errors"].append(str(e))
                    logger.error(f"インデックス作成エラー {index_name}: {e}")

        conn.commit()
    except Exception as e:
        logger.error(f"インデックス作成エラー: {e}")
        results["errors"].append(str(e))
    finally:
        conn.close()

    return results


def run_all_migrations() -> Dict[str, Any]:
    """すべてのマイグレーションを実行"""
    print("\n" + "=" * 80)
    print("📊 スキーママイグレーション実行")
    print("=" * 80)

    results = {
        "timestamp": None,
        "migrations": {
            "add_odds_columns": None,
            "create_race_odds_table": None,
            "create_odds_indexes": None,
        },
        "status": "success",
    }

    from datetime import datetime

    results["timestamp"] = datetime.now().isoformat()

    # 1. オッズカラムを追加
    print("\n📝 [1/3] race_entriesにオッズカラムを追加...")
    result1 = migrate_add_odds_columns()
    results["migrations"]["add_odds_columns"] = result1
    print(f"  ✅ 追加: {len(result1['added_columns'])}個のカラム")
    if result1["skipped_columns"]:
        print(f"  ⏭️ スキップ: {len(result1['skipped_columns'])}個（既に存在）")

    # 2. race_oddsテーブルを作成
    print("\n📝 [2/3] race_oddsテーブルを作成...")
    result2 = create_race_odds_table()
    results["migrations"]["create_race_odds_table"] = result2
    if result2["status"] == "success":
        print("  ✅ テーブル作成成功")
    elif result2["status"] == "info":
        print("  ℹ️ テーブルは既に存在")
    else:
        print(f"  ❌ エラー: {result2['message']}")
        results["status"] = "partial"

    # 3. インデックスを作成
    print("\n📝 [3/3] インデックスを作成...")
    result3 = create_odds_indexes()
    results["migrations"]["create_odds_indexes"] = result3
    print(f"  ✅ 作成: {len(result3['created'])}個のインデックス")
    if result3["skipped"]:
        print(f"  ⏭️ スキップ: {len(result3['skipped'])}個（既に存在）")

    print("\n" + "=" * 80)
    if results["status"] == "success":
        print("✅ マイグレーション完了")
    else:
        print("⚠️ マイグレーション部分完了（警告有り）")
    print("=" * 80 + "\n")

    return results


def verify_schema_updated() -> bool:
    """スキーマの更新を検証"""
    conn = app_db.get_connection()
    cursor = conn.cursor()

    required_columns = [
        ("race_entries", "opening_odds"),
        ("race_entries", "win_odds"),
        ("race_entries", "place_odds"),
        ("race_entries", "odds_timestamp"),
    ]

    all_exist = True
    for table, column in required_columns:
        exists = check_column_exists(conn, table, column)
        status = "✅" if exists else "❌"
        print(f"  {status} {table}.{column}")
        if not exists:
            all_exist = False

    conn.close()
    return all_exist


if __name__ == "__main__":
    # マイグレーション実行
    run_all_migrations()

    # 検証
    print("📊 スキーマ検証:")
    verify_schema_updated()
