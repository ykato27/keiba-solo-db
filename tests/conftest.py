"""pytest 共通フィクスチャ

すべてのテストは一時ディレクトリ上のDBで実行し、本番DB（data/keiba.db）には
一切触れない。DB接続が app.db.get_connection に一本化されているため、
app.db.DB_PATH を差し替えるだけで app / etl / metrics の全経路が一時DBを向く。
"""

import random
import sys
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app import db as app_db  # noqa: E402


# app.queries で @st.cache_data が付いている関数の明示リスト。
# 注意: dir() を走査して .clear を探す方法は、モジュールの __builtins__ 辞書の
# clear() を誤って呼び、インタプリタの組み込み名前空間を破壊するため禁止。
_CACHED_QUERY_FUNCTIONS = [
    "get_all_race_dates",
    "get_courses_by_date",
    "get_races",
    "get_race_entries_with_metrics",
    "get_horse_details",
    "get_horse_race_history",
]


@pytest.fixture(autouse=True)
def _clear_query_cache():
    """Streamlit のクエリキャッシュをテスト間で持ち越さない"""
    from app import queries

    for name in _CACHED_QUERY_FUNCTIONS:
        getattr(queries, name).clear()
    yield


@pytest.fixture()
def temp_db(tmp_path, monkeypatch):
    """スキーマ初期化済みの一時DBのパスを返す"""
    db_file = tmp_path / "keiba.db"
    monkeypatch.setattr(app_db, "DB_PATH", db_file)
    app_db.init_schema()
    return db_file


@pytest.fixture()
def populated_db(temp_db):
    """デモデータを投入し、指標まで計算済みの一時DB

    規模はテスト用に絞る（レース60件分）。生成は乱数を使うため seed を固定する。
    """
    random.seed(42)

    from app import demo_data
    from etl import upsert_entry, upsert_master, upsert_race
    from metrics import build_horse_metrics

    races = demo_data.generate_test_races(years=1)[:60]
    horses = demo_data.generate_test_horses(count=60)
    jockeys = demo_data.generate_test_jockeys(count=20)
    trainers = demo_data.generate_test_trainers(count=20)
    entries = demo_data.generate_test_entries(races, horses, jockeys, trainers)

    upsert_master.MasterDataUpsert().upsert_horses(horses)
    upsert_master.MasterDataUpsert().upsert_jockeys(jockeys)
    upsert_master.MasterDataUpsert().upsert_trainers(trainers)
    upsert_race.RaceUpsert().upsert_races(races)
    entry_count = upsert_entry.EntryUpsert().upsert_entries(entries)
    metrics_count = build_horse_metrics.build_all_horse_metrics(incremental=False)

    # INSERT OR REPLACE のため、処理件数と実テーブル行数は一致しない
    # （同一レースに同じ馬が重複選択されると置換される）。実測値を返しておく。
    conn = app_db.get_connection(read_only=True)
    try:
        entries_rows = conn.execute("SELECT COUNT(*) FROM race_entries").fetchone()[0]
    finally:
        conn.close()

    return {
        "db_path": temp_db,
        "races": races,
        "horses": horses,
        "entries": entries,
        "entry_count": entry_count,
        "entries_rows": entries_rows,
        "metrics_count": metrics_count,
    }
