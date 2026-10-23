"""予測ページの機能テスト（pytest形式、Streamlit UIなし）

旧版はスクリプト形式で本番DBに依存していた。現在は一時DBのデモデータで検証する。

既知の問題: リポジトリ同梱の data/prediction_model_advanced.pkl は旧
scikit-learn で作成された GradientBoosting の pickle で、現行 scikit-learn
（_loss モジュールの廃止）では読み込めない。そのため同梱モデルは
「未訓練」と判定される。再学習して pkl を差し替えれば下の xfail は xpass
になり、気づけるようになっている。
"""

import pytest

from app import prediction_model_lightgbm as pml
from app import queries


@pytest.mark.xfail(
    reason="同梱pklが旧scikit-learn形式で現行環境では読み込めない（要再学習）",
    strict=False,
)
def test_saved_model_loads():
    """同梱の学習済みモデル（data/*.pkl）が読み込めること"""
    model = pml.AdvancedRacePredictionModel()
    assert model.get_model_info()["is_trained"] is True


def test_model_class_degrades_gracefully():
    """同梱モデルが読めなくても、例外なくインスタンス化できること"""
    model = pml.AdvancedRacePredictionModel()
    info = model.get_model_info()
    assert info["n_features"] > 0
    assert model.model_name


def test_queries_against_populated_db(populated_db):
    """クエリ関数が一時DBのデモデータを正しく返すこと"""
    dates = queries.get_all_race_dates()
    assert len(dates) == len({r["race_date"] for r in populated_db["races"]})

    courses = queries.get_courses_by_date(dates[0])
    assert courses

    races = queries.get_races(dates[0], courses[0])
    assert races

    entries = queries.get_race_entries_with_metrics(races[0]["race_id"])
    assert len(entries) > 0
    assert all("horse_name" in e for e in entries)


@pytest.fixture()
def trained_model(populated_db, tmp_path):
    """一時DBで学習したモデル（保存先は一時ディレクトリへ付け替え）"""
    model = pml.AdvancedRacePredictionModel()
    model.model_path = tmp_path / "prediction_model_advanced.pkl"
    model.scaler_path = tmp_path / "prediction_scaler_advanced.pkl"
    model.is_trained = False
    model.train_with_cross_validation()
    return model


def test_predict_race_order(populated_db, trained_model):
    """学習済みモデルで一時DBのレースを予測し、結果構造が返ること"""
    assert trained_model.is_trained

    dates = queries.get_all_race_dates()
    races = queries.get_races(dates[0], queries.get_courses_by_date(dates[0])[0])
    race = races[0]
    entries = queries.get_race_entries_with_metrics(race["race_id"])
    horse_ids = [e["horse_id"] for e in entries if e["horse_id"]]

    results = trained_model.predict_race_order(
        horse_ids[:10],
        race_info={"distance_m": race.get("distance_m"), "surface": race.get("surface")},
    )

    assert "predictions" in results
    predictions = results["predictions"]
    assert len(predictions) == len(horse_ids[:10])
    for pred in predictions:
        assert 0.0 <= pred["confidence"] <= 100.0
        assert pred["win_probability"] >= 0.0
    # 信頼度の降順にソートされていること
    confidences = [p["confidence"] for p in predictions]
    assert confidences == sorted(confidences, reverse=True)
