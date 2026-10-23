"""JRAEN 取り込み（実データ用DB）のテスト

フィクスチャのパース結果を一時DBへ取り込み、スキーマ拡張（payouts）と
評価用フレーム読み込みが実データ形式でも動くことを確認する。
本番DB・実データDBには触れない。
"""

import sqlite3
from pathlib import Path

import pytest

from evaluation.data import load_full_entries_frame
from scraper import jraen_import
from scraper.jraen import parse_running_html

FIXTURE = Path(__file__).parent / "fixtures" / "jraen_running_sample.html"
REF = {"race_ymd": "20250105", "jo_cd": "06", "kai": "01", "hi": "01", "race_no": 1}


@pytest.fixture()
def real_db(tmp_path):
    db_path = tmp_path / "keiba_real.db"
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    jraen_import.ensure_real_schema(conn)
    parsed = parse_running_html(FIXTURE.read_text(encoding="utf-8"), REF)
    dims = jraen_import.DimensionCache(conn)
    race_id = jraen_import.import_race(conn, parsed, REF, dims)
    yield db_path, race_id
    conn.close()


def test_import_creates_race_entries_and_payouts(real_db):
    db_path, race_id = real_db
    conn = sqlite3.connect(str(db_path))
    try:
        n_entries = conn.execute(
            "SELECT COUNT(*) FROM race_entries WHERE race_id = ?", (race_id,)
        ).fetchone()[0]
        assert n_entries == 16
        win = conn.execute(
            "SELECT combination, payout_yen FROM payouts"
            " WHERE race_id = ? AND bet_type = 'win'",
            (race_id,),
        ).fetchall()
        assert win == [("11", 250)]
        n_place = conn.execute(
            "SELECT COUNT(*) FROM payouts WHERE race_id = ? AND bet_type = 'place'",
            (race_id,),
        ).fetchone()[0]
        assert n_place == 3
        race = conn.execute(
            "SELECT race_date, course, surface, distance_m FROM races"
            " WHERE race_id = ?",
            (race_id,),
        ).fetchone()
        assert race == ("2025-01-05", "中山", "ダート", 1200)
    finally:
        conn.close()


def test_full_frame_loads_real_format(real_db):
    db_path, race_id = real_db
    frame = load_full_entries_frame(db_path=db_path)
    assert len(frame) == 16
    # 実データは全着順があるので、勝ち馬はちょうど1頭
    assert int(frame["won"].sum()) == 1
    assert int(frame["top3"].sum()) == 3
    winner = frame[frame["won"] == 1].iloc[0]
    assert winner["horse_no"] == 11
    assert winner["odds"] == 2.5
