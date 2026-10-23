"""JRAEN（JRA公式英語サービス）パーサのテスト

フィクスチャは 2025-01-05 中山1R の実ページから必要テーブルだけを
抽出したもの。期待値はページの実データと手で突き合わせてある。
ネットワークには接続しない。
"""

from pathlib import Path

import pytest

from scraper.jraen import parse_ordinal, parse_running_html

FIXTURE = (
    Path(__file__).parent / "fixtures" / "jraen_running_sample.html"
)
REF = {"race_ymd": "20250105", "jo_cd": "06", "kai": "01", "hi": "01", "race_no": 1}


@pytest.fixture(scope="module")
def parsed():
    html = FIXTURE.read_text(encoding="utf-8")
    return parse_running_html(html, REF)


class TestParseOrdinal:
    @pytest.mark.parametrize(
        "text,expected",
        [("1st", 1), ("2nd", 2), ("3rd", 3), ("4th", 4), ("11th", 11),
         ("FP", None), ("1c", None), ("", None)],
    )
    def test_ordinal(self, text, expected):
        assert parse_ordinal(text) == expected


class TestParseRunning:
    def test_race_header(self, parsed):
        assert parsed["race_date"] == "2025-01-05"
        assert parsed["course"] == "中山"
        assert parsed["race_no"] == 1
        assert parsed["distance_m"] == 1200
        assert parsed["surface"] == "ダート"
        assert parsed["going_en"] == "Standard"
        assert parsed["going"] == "良"
        assert parsed["is_steeplechase"] == 0

    def test_all_finishers_present(self, parsed):
        entries = parsed["entries"]
        assert len(entries) == 16  # 全着順（上位3着だけではない）
        assert [e["finish_pos"] for e in entries] == list(range(1, 17))
        assert parsed["skipped_result_rows"] == 0

    def test_winner_row(self, parsed):
        winner = parsed["entries"][0]
        assert winner["horse_name"] == "Pizza Napoli"
        assert winner["horse_no"] == 11
        assert winner["frame_no"] == 6
        assert winner["age"] == 3
        assert winner["sex"] == "F"
        assert winner["weight_carried"] == 55.0
        assert winner["odds"] == 2.5
        assert winner["popularity"] == 1
        assert winner["finish_time_seconds"] == pytest.approx(72.2)

    def test_jockey_trainer_split_by_br(self, parsed):
        winner = parsed["entries"][0]
        assert winner["jockey_name"] == "Takuya Ono"
        assert winner["trainer_name"] == "Koichi Shinkai"
        assert all(e["jockey_name"] for e in parsed["entries"])

    def test_payoffs(self, parsed):
        by_type = {}
        for p in parsed["payoffs"]:
            by_type.setdefault(p["bet_type"], []).append(p)
        # 単勝: 11番 ¥250（勝ち馬のオッズ 2.5 と一致）
        assert by_type["win"] == [
            {"bet_type": "win", "combination": "11", "payout_yen": 250}
        ]
        # 複勝: 3頭分
        place = {p["combination"]: p["payout_yen"] for p in by_type["place"]}
        assert place == {"11": 120, "3": 280, "13": 1980}
        # その他の券種
        assert by_type["quinella"][0]["payout_yen"] == 1510
        assert by_type["exacta"][0]["payout_yen"] == 2330
        assert by_type["trio"][0]["payout_yen"] == 50260
        assert by_type["trifecta"][0]["payout_yen"] == 126370
        wide = {p["combination"]: p["payout_yen"] for p in by_type["quinella_place"]}
        assert wide == {"3-11": 530, "11-13": 4260, "3-13": 11210}
