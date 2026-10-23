"""データパイプラインの統合テスト（pytest形式）

旧版はスクリプト形式で、本番DB（data/keiba.db）を unlink してから再構築する
危険な実装だった。現在は conftest のフィクスチャにより一時DB上でのみ実行され、
本番DBには一切触れない。
"""

from pathlib import Path

import pytest

from app import db as app_db

PROJECT_ROOT = Path(__file__).resolve().parent.parent
PRODUCTION_DB = PROJECT_ROOT / "data" / "keiba.db"


def test_temp_db_is_not_production_db(temp_db):
    """テスト用DBが本番DBと別の場所にあること（安全装置の確認）"""
    assert temp_db != PRODUCTION_DB
    assert temp_db.exists()


def test_pipeline_end_to_end(populated_db):
    """デモデータ生成 → ETL → 指標計算 の一連が一時DBで完走すること"""
    conn = app_db.get_connection(read_only=True)
    try:
        cur = conn.cursor()
        races_count = cur.execute("SELECT COUNT(*) FROM races").fetchone()[0]
        entries_count = cur.execute("SELECT COUNT(*) FROM race_entries").fetchone()[0]
        finished_count = cur.execute(
            "SELECT COUNT(*) FROM race_entries WHERE finish_pos IS NOT NULL"
        ).fetchone()[0]
        metrics_count = cur.execute("SELECT COUNT(*) FROM horse_metrics").fetchone()[0]
    finally:
        conn.close()

    assert races_count == len(populated_db["races"])
    # 処理件数（entry_count）は INSERT OR REPLACE の置換分だけ実行数より多くなる
    assert entries_count == populated_db["entries_rows"] > 0
    assert populated_db["entry_count"] >= entries_count
    # TimeSeriesSplit（3分割）に足る結果付きエントリがあること
    assert finished_count >= 50
    assert metrics_count > 0


def test_model_training_with_cv(populated_db, tmp_path):
    """LightGBMモデルの訓練（TimeSeriesSplit）が一時DBで完走すること

    モデルの保存先は一時ディレクトリへ付け替え、本番のモデルファイル
    （data/prediction_model_advanced.pkl）を上書きしない。
    """
    from app import prediction_model_lightgbm as pml

    model = pml.AdvancedRacePredictionModel()
    model.model_path = tmp_path / "prediction_model_advanced.pkl"
    model.scaler_path = tmp_path / "prediction_scaler_advanced.pkl"
    model.is_trained = False

    results = model.train_with_cross_validation()

    assert model.is_trained
    assert len(results["cv_scores"]) == 5
    assert 0.0 <= results["mean_cv_accuracy"] <= 1.0
    assert results["training_samples"] >= 50
    # 保存先が一時ディレクトリであること
    assert model.model_path.exists()
    assert model.scaler_path.exists()


@pytest.mark.parametrize("table", ["horses", "jockeys", "trainers", "races", "race_entries"])
def test_master_tables_populated(populated_db, table):
    """マスタ系テーブルにデータが入っていること"""
    conn = app_db.get_connection(read_only=True)
    try:
        count = conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
    finally:
        conn.close()
    assert count > 0
