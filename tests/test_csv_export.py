"""CSVエクスポート機能のテスト（pytest形式）

旧版はスクリプト形式で本番DBの実データに依存していた。現在は一時DBに
投入したデモデータに対して、CSVの行数と内容を検証する。
"""

from app import csv_export, queries


def _lines(csv_text: str) -> list:
    return [ln for ln in csv_text.strip().splitlines() if ln.strip()]


def test_export_race_entries(populated_db):
    dates = queries.get_all_race_dates()
    assert dates
    races = queries.get_races(dates[0], queries.get_courses_by_date(dates[0])[0])
    race_id = races[0]["race_id"]

    entries = queries.get_race_entries_with_metrics(race_id)
    csv_text = csv_export.export_race_entries_to_csv(race_id)

    assert csv_text
    lines = _lines(csv_text)
    # ヘッダー + 出走馬の行数
    assert len(lines) == len(entries) + 1
    assert "horse_name" in lines[0]


def test_export_all_races(populated_db):
    csv_text = csv_export.export_all_races_to_csv()
    assert csv_text
    assert len(_lines(csv_text)) == len(populated_db["races"]) + 1


def test_export_horse_metrics(populated_db):
    csv_text = csv_export.export_horse_metrics_to_csv()
    assert csv_text
    assert len(_lines(csv_text)) == populated_db["metrics_count"] + 1


def test_export_entry_details(populated_db):
    csv_text = csv_export.export_entry_details_to_csv()
    assert csv_text
    assert len(_lines(csv_text)) == populated_db["entries_rows"] + 1


def test_export_training_features(populated_db):
    csv_text = csv_export.export_training_features_to_csv()
    assert csv_text
    lines = _lines(csv_text)
    # 結果付きエントリの分だけ学習サンプルが得られる（ヘッダー込み）
    assert len(lines) > 51
