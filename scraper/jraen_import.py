"""JRAEN から取得した実データを実データ用DB（data/keiba_real.db）へ取り込む

本番DB（data/keiba.db）とは分離し、同じスキーマ（sql/schema.sql）に
払戻テーブル（payouts）を追加したものを使う。既存ETLと同じく
「名前で get-or-create したIDを引く」流儀に合わせる。

払戻（payouts）の粒度: 1レース × 券種 × 組合せ に1行。
combination は馬番を '-' でつないだ文字列（単勝・複勝は馬番のみ）、
payout_yen は 100円あたりの払戻金額。
"""

import sqlite3
from pathlib import Path
from typing import Dict

_SCHEMA_PATH = Path(__file__).resolve().parent.parent / "sql" / "schema.sql"

EXTRA_SCHEMA = """
CREATE TABLE IF NOT EXISTS payouts (
  payout_id INTEGER PRIMARY KEY,
  race_id INTEGER NOT NULL REFERENCES races(race_id) ON DELETE CASCADE,
  bet_type TEXT NOT NULL,          -- win / place / quinella / exacta / trio / trifecta / bracket_quinella / quinella_place
  combination TEXT NOT NULL,       -- 馬番を '-' で接続（単勝・複勝は馬番のみ）
  payout_yen INTEGER NOT NULL,     -- 100円あたり払戻金額
  UNIQUE (race_id, bet_type, combination)
);
CREATE INDEX IF NOT EXISTS idx_payouts_race ON payouts(race_id);

CREATE TABLE IF NOT EXISTS import_meta (
  key TEXT PRIMARY KEY,
  value TEXT NOT NULL
);
"""


def ensure_real_schema(conn: sqlite3.Connection) -> None:
    """基本スキーマ＋払戻テーブルを作成する"""
    with open(_SCHEMA_PATH, "r", encoding="utf-8") as f:
        conn.executescript(f.read())
    conn.executescript(EXTRA_SCHEMA)
    conn.commit()


def race_id_for(ref: Dict) -> int:
    """JRAEN の参照（日付・場コード・レース番号）から一意な race_id を作る"""
    return int(f"{ref['race_ymd']}{ref['jo_cd']}{int(ref['race_no']):02d}")


class DimensionCache:
    """horses / jockeys / trainers の名前→ID 変換（get-or-create）"""

    def __init__(self, conn: sqlite3.Connection):
        self.conn = conn
        self.cache: Dict[str, Dict[str, int]] = {
            "horses": {},
            "jockeys": {},
            "trainers": {},
        }

    def get_id(self, table: str, name: str) -> int:
        name = (name or "").strip()
        if name in self.cache[table]:
            return self.cache[table][name]
        row = self.conn.execute(
            f"SELECT {table[:-1]}_id FROM {table} WHERE raw_name = ?", (name,)
        ).fetchone()
        if row is not None:
            entity_id = int(row[0])
        else:
            cursor = self.conn.execute(
                f"INSERT INTO {table} (raw_name) VALUES (?)", (name,)
            )
            entity_id = int(cursor.lastrowid)
        self.cache[table][name] = entity_id
        return entity_id


def import_race(
    conn: sqlite3.Connection,
    parsed: Dict,
    ref: Dict,
    dims: DimensionCache,
) -> int:
    """パース済みレースを1トランザクションで取り込む。戻り値は race_id"""
    race_id = race_id_for(ref)
    conn.execute(
        "INSERT OR REPLACE INTO races"
        " (race_id, race_date, course, race_no, distance_m, surface, going,"
        "  grade, title)"
        " VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (
            race_id,
            parsed["race_date"],
            parsed["course"],
            parsed["race_no"],
            parsed["distance_m"],
            parsed["surface"],
            parsed["going"],
            None,
            None,
        ),
    )
    conn.execute("DELETE FROM race_entries WHERE race_id = ?", (race_id,))
    for entry in parsed["entries"]:
        conn.execute(
            "INSERT INTO race_entries"
            " (race_id, horse_id, jockey_id, trainer_id, frame_no, horse_no,"
            "  age, weight_carried, horse_weight, finish_pos,"
            "  finish_time_seconds, margin, odds, popularity, corner_order,"
            "  days_since_last_race, is_steeplechase)"
            " VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                race_id,
                dims.get_id("horses", entry["horse_name"]),
                dims.get_id("jockeys", entry["jockey_name"]) if entry["jockey_name"] else None,
                dims.get_id("trainers", entry["trainer_name"]) if entry["trainer_name"] else None,
                entry["frame_no"],
                entry["horse_no"],
                entry["age"],
                entry["weight_carried"],
                None,
                entry["finish_pos"],
                entry["finish_time_seconds"],
                entry["margin"],
                entry["odds"],
                entry["popularity"],
                entry["corner_order"],
                None,
                parsed["is_steeplechase"],
            ),
        )
    conn.execute("DELETE FROM payouts WHERE race_id = ?", (race_id,))
    conn.executemany(
        "INSERT INTO payouts (race_id, bet_type, combination, payout_yen)"
        " VALUES (?, ?, ?, ?)",
        [
            (race_id, p["bet_type"], p["combination"], p["payout_yen"])
            for p in parsed["payoffs"]
        ],
    )
    conn.commit()
    return race_id


def recompute_days_since_last_race(conn: sqlite3.Connection) -> int:
    """各馬の前走からの日数を、取り込み済みデータ内だけで再計算する

    初出走（取り込み範囲内で初登場）は NULL のままにする
    （特徴量側で既定値にフォールバックする）。
    """
    rows = conn.execute(
        "SELECT e.entry_id, e.horse_id, r.race_date"
        " FROM race_entries e JOIN races r ON r.race_id = e.race_id"
        " ORDER BY e.horse_id, r.race_date, e.race_id"
    ).fetchall()
    from datetime import date

    def to_date(text: str) -> date:
        y, m, d = (int(part) for part in text.split("-"))
        return date(y, m, d)

    previous: Dict[int, date] = {}
    updated = 0
    for entry_id, horse_id, race_date_text in rows:
        current = to_date(race_date_text)
        if horse_id in previous:
            days = (current - previous[horse_id]).days
            conn.execute(
                "UPDATE race_entries SET days_since_last_race = ?"
                " WHERE entry_id = ?",
                (days, entry_id),
            )
            updated += 1
        previous[horse_id] = current
    conn.commit()
    return updated


def set_meta(conn: sqlite3.Connection, key: str, value: str) -> None:
    conn.execute(
        "INSERT OR REPLACE INTO import_meta (key, value) VALUES (?, ?)",
        (key, value),
    )
    conn.commit()
