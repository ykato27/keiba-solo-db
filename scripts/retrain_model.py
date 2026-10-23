"""同梱モデルの再学習スクリプト（Phase 2）

背景: data/prediction_model_advanced.pkl は旧 scikit-learn で作られた
GradientBoosting の pickle で、現行 scikit-learn では読み込めない
（No module named '_loss'）。このスクリプトで現行の正系統
（LightGBM: app/prediction_model_lightgbm.py）により再学習し、
現行環境で読み込める形式で保存し直す。

使い方:
    uv run python scripts/retrain_model.py
    uv run python scripts/retrain_model.py --model-path /tmp/model.pkl \
        --scaler-path /tmp/scaler.pkl

注意（現行DBの限界）:
- DBへのアクセスは読み取りのみ（学習データ構築は SELECT のみ）。
- 現行DBの着順は上位3着までしか記録されておらず、3クラス分類の
  クラス2（4着以下）のサンプルは 0 件。学習されるのは実質
  「1着 vs 2-3着」の2クラスであり、予測の解釈にはこの制約が伴う。
- 学習データは合成データ中心とみられ、モデルの実力評価は
  evaluation/ のウォークフォワード検証で行うこと（本スクリプトの
  CV 指標は同一データ内での参考値にすぎない）。
"""

import argparse
import pickle
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

DEFAULT_MODEL_PATH = PROJECT_ROOT / "data" / "prediction_model_advanced.pkl"
DEFAULT_SCALER_PATH = PROJECT_ROOT / "data" / "prediction_scaler_advanced.pkl"


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="同梱モデルを現行形式で再学習する")
    parser.add_argument("--model-path", type=Path, default=DEFAULT_MODEL_PATH)
    parser.add_argument("--scaler-path", type=Path, default=DEFAULT_SCALER_PATH)
    parser.add_argument(
        "--db-path",
        type=Path,
        default=None,
        help="学習に使うDB（省略時は app.db.DB_PATH = data/keiba.db）",
    )
    args = parser.parse_args(argv)

    if args.db_path is not None:
        from app import db as app_db

        if not args.db_path.exists():
            print(f"エラー: DBが見つかりません: {args.db_path}")
            return 1
        app_db.DB_PATH = args.db_path

    from app import prediction_model_lightgbm as pml

    model = pml.AdvancedRacePredictionModel()
    model.model_path = args.model_path
    model.scaler_path = args.scaler_path
    model.is_trained = False

    result = model.train_with_cross_validation()

    if not (args.model_path.exists() and args.scaler_path.exists()):
        print("エラー: モデルの保存に失敗しました")
        return 1

    # 保存した pkl が現行環境で読み込めることを確認する
    with open(args.model_path, "rb") as f:
        reloaded = pickle.load(f)
    print("=" * 60)
    print("再学習が完了しました")
    print(f"  モデル: {args.model_path}（{type(reloaded).__name__}）")
    print(f"  スケーラ: {args.scaler_path}")
    print(f"  学習サンプル数: {result['training_samples']}")
    print(f"  クラス分布: {result['class_distribution']}")
    print(
        "  CV精度（同一データ内・参考値）: "
        f"{result['mean_cv_accuracy']:.4f} ± {result['std_cv_accuracy']:.4f}"
    )
    if result["class_distribution"].get(2, 0) == 0:
        print(
            "  注意: クラス2（4着以下）のサンプルが 0 件です。"
            "現行DBは着順が上位3着までしか記録されていないため、"
            "このモデルは実質2クラス（1着 vs 2-3着）です。"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
