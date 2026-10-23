"""再学習スクリプト（scripts/retrain_model.py）のテスト

一時DB（一時ディレクトリ）に対してスクリプトを実行し、同梱先とは別の
場所に pkl が生成され、現行環境で読み込めることを確認する。
本番DB・本番の data/*.pkl には触れない。
"""

import importlib.util
import pickle
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent


def _load_retrain_module():
    spec = importlib.util.spec_from_file_location(
        "retrain_model", PROJECT_ROOT / "scripts" / "retrain_model.py"
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_retrain_script_produces_loadable_pickle(populated_db, tmp_path):
    retrain = _load_retrain_module()
    model_path = tmp_path / "prediction_model_advanced.pkl"
    scaler_path = tmp_path / "prediction_scaler_advanced.pkl"

    exit_code = retrain.main(
        [
            "--model-path",
            str(model_path),
            "--scaler-path",
            str(scaler_path),
            "--db-path",
            str(populated_db["db_path"]),
        ]
    )

    assert exit_code == 0
    assert model_path.exists() and scaler_path.exists()
    with open(model_path, "rb") as f:
        model = pickle.load(f)  # 現行環境で読み込めること
    assert hasattr(model, "predict_proba")


def test_retrain_script_rejects_missing_db(tmp_path):
    retrain = _load_retrain_module()
    exit_code = retrain.main(["--db-path", str(tmp_path / "no_such.db")])
    assert exit_code == 1
