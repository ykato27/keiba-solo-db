"""
モデル評価メトリクス分析モジュール
クラス別の詳細メトリクスを計算し、モデルの真の性能を評価

機能:
1. クラス別 Precision, Recall, F1スコア
2. 混同行列の詳細分析
3. 着順予測の特性評価（1着, 複勝, その他ごと）
4. キャリブレーション分析
5. 予測信頼度の分布
"""

import numpy as np
from typing import Dict, List, Tuple, Any, Optional
from sklearn.metrics import (
    precision_recall_fscore_support,
    confusion_matrix,
    classification_report,
    roc_auc_score,
    log_loss,
)


class ModelMetricsAnalyzer:
    """モデル評価メトリクス分析エンジン"""

    # クラスラベルの定義
    CLASS_LABELS = {0: "1着", 1: "複勝(2-3着)", 2: "その他"}

    @staticmethod
    def calculate_class_metrics(
        y_true: np.ndarray, y_pred: np.ndarray, y_pred_proba: Optional[np.ndarray] = None
    ) -> Dict[str, Any]:
        """
        クラス別の詳細メトリクスを計算

        Args:
            y_true: 真のラベル
            y_pred: 予測ラベル
            y_pred_proba: 予測確率（オプション）

        Returns:
            クラス別メトリクスの辞書
        """
        result = {
            "global_metrics": {},
            "class_metrics": {},
            "confusion_matrix": None,
            "class_distribution": {},
        }

        # グローバルメトリクス
        unique_classes = np.unique(y_true)

        # マクロ平均と重み平均の Precision, Recall, F1
        p_macro, r_macro, f1_macro, _ = precision_recall_fscore_support(
            y_true, y_pred, average="macro", zero_division=0
        )
        p_weighted, r_weighted, f1_weighted, _ = precision_recall_fscore_support(
            y_true, y_pred, average="weighted", zero_division=0
        )

        result["global_metrics"] = {
            "accuracy": float(np.mean(y_pred == y_true)),
            "precision_macro": float(p_macro),
            "recall_macro": float(r_macro),
            "f1_macro": float(f1_macro),
            "precision_weighted": float(p_weighted),
            "recall_weighted": float(r_weighted),
            "f1_weighted": float(f1_weighted),
        }

        # クラス別メトリクス
        precision, recall, f1, support = precision_recall_fscore_support(
            y_true, y_pred, average=None, labels=unique_classes, zero_division=0
        )

        for i, cls in enumerate(unique_classes):
            class_name = ModelMetricsAnalyzer.CLASS_LABELS.get(int(cls), f"Class {cls}")
            result["class_metrics"][int(cls)] = {
                "class_name": class_name,
                "precision": float(precision[i]),
                "recall": float(recall[i]),
                "f1_score": float(f1[i]),
                "support": int(support[i]),
            }

        # 混同行列
        cm = confusion_matrix(y_true, y_pred, labels=unique_classes)
        result["confusion_matrix"] = {
            "matrix": cm.tolist(),
            "labels": [int(c) for c in unique_classes],
            "normalized_by_true": cm.astype("float") / cm.sum(axis=1, keepdims=True),
            "normalized_by_pred": cm.astype("float") / cm.sum(axis=0, keepdims=True),
        }

        # クラス分布
        for cls in unique_classes:
            count = np.sum(y_true == cls)
            pct = count / len(y_true) * 100
            result["class_distribution"][int(cls)] = {
                "count": int(count),
                "percentage": float(pct),
                "class_name": ModelMetricsAnalyzer.CLASS_LABELS.get(int(cls), f"Class {cls}"),
            }

        # 予測確率がある場合、追加のメトリクス
        if y_pred_proba is not None:
            result["probability_metrics"] = ModelMetricsAnalyzer._analyze_probabilities(
                y_true, y_pred_proba, unique_classes
            )

        return result

    @staticmethod
    def _analyze_probabilities(
        y_true: np.ndarray, y_pred_proba: np.ndarray, unique_classes: np.ndarray
    ) -> Dict[str, Any]:
        """予測確率の分析"""
        prob_result = {
            "mean_confidence": float(np.max(y_pred_proba, axis=1).mean()),
            "median_confidence": float(np.median(np.max(y_pred_proba, axis=1))),
            "confidence_by_class": {},
            "log_loss": 0.0,
        }

        # クラス別の平均信頼度
        for cls in unique_classes:
            mask = y_true == cls
            if np.sum(mask) > 0:
                max_probs_for_class = np.max(y_pred_proba[mask], axis=1)
                prob_result["confidence_by_class"][int(cls)] = {
                    "mean": float(max_probs_for_class.mean()),
                    "std": float(max_probs_for_class.std()),
                    "min": float(max_probs_for_class.min()),
                    "max": float(max_probs_for_class.max()),
                }

        # ログロス（ネイティブにはサポートされている）
        try:
            prob_result["log_loss"] = float(log_loss(y_true, y_pred_proba))
        except:
            prob_result["log_loss"] = None

        return prob_result

    @staticmethod
    def calculate_per_fold_metrics(fold_results: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        複数のFoldの結果から統計サマリーを計算

        Args:
            fold_results: 各Foldの結果リスト

        Returns:
            統計サマリー
        """
        summary = {
            "total_folds": len(fold_results),
            "accuracy_mean": 0.0,
            "accuracy_std": 0.0,
            "accuracy_min": 0.0,
            "accuracy_max": 0.0,
            "f1_macro_mean": 0.0,
            "f1_macro_std": 0.0,
            "f1_weighted_mean": 0.0,
            "f1_weighted_std": 0.0,
            "class_specific_stats": {},
        }

        accuracies = []
        f1_macros = []
        f1_weighteds = []

        for fold_result in fold_results:
            if "metrics" in fold_result:
                metrics = fold_result["metrics"]
                accuracies.append(metrics.get("global_metrics", {}).get("accuracy", 0))
                f1_macros.append(metrics.get("global_metrics", {}).get("f1_macro", 0))
                f1_weighteds.append(metrics.get("global_metrics", {}).get("f1_weighted", 0))

        if accuracies:
            summary["accuracy_mean"] = float(np.mean(accuracies))
            summary["accuracy_std"] = float(np.std(accuracies))
            summary["accuracy_min"] = float(np.min(accuracies))
            summary["accuracy_max"] = float(np.max(accuracies))

        if f1_macros:
            summary["f1_macro_mean"] = float(np.mean(f1_macros))
            summary["f1_macro_std"] = float(np.std(f1_macros))

        if f1_weighteds:
            summary["f1_weighted_mean"] = float(np.mean(f1_weighteds))
            summary["f1_weighted_std"] = float(np.std(f1_weighteds))

        return summary

    @staticmethod
    def print_detailed_report(metrics_dict: Dict[str, Any], fold_num: Optional[int] = None) -> None:
        """詳細メトリクスレポートをコンソール出力"""
        header = f"Fold {fold_num}" if fold_num else "全体評価"
        print("\n" + "=" * 80)
        print(f"📊 {header} - 詳細メトリクス")
        print("=" * 80)

        # グローバルメトリクス
        if "global_metrics" in metrics_dict:
            print("\n【グローバルメトリクス】")
            gm = metrics_dict["global_metrics"]
            print(f"  精度 (Accuracy):         {gm.get('accuracy', 0):.4f}")
            print(f"  Precision (マクロ平均): {gm.get('precision_macro', 0):.4f}")
            print(f"  Recall (マクロ平均):    {gm.get('recall_macro', 0):.4f}")
            print(f"  F1 Score (マクロ平均):  {gm.get('f1_macro', 0):.4f}")
            print(f"  Precision (重み平均):   {gm.get('precision_weighted', 0):.4f}")
            print(f"  Recall (重み平均):      {gm.get('recall_weighted', 0):.4f}")
            print(f"  F1 Score (重み平均):    {gm.get('f1_weighted', 0):.4f}")

        # クラス別メトリクス
        if "class_metrics" in metrics_dict:
            print("\n【クラス別メトリクス】")
            for class_id, metrics in metrics_dict["class_metrics"].items():
                class_name = metrics.get("class_name", f"Class {class_id}")
                print(f"\n  {class_name}:")
                print(f"    Precision: {metrics.get('precision', 0):.4f}")
                print(f"    Recall:    {metrics.get('recall', 0):.4f}")
                print(f"    F1 Score:  {metrics.get('f1_score', 0):.4f}")
                print(f"    Support:   {metrics.get('support', 0)}")

        # クラス分布
        if "class_distribution" in metrics_dict:
            print("\n【クラス分布】")
            for class_id, dist in metrics_dict["class_distribution"].items():
                class_name = dist.get("class_name", f"Class {class_id}")
                print(f"  {class_name}: {dist.get('count', 0)} ({dist.get('percentage', 0):.1f}%)")

        # 混同行列
        if "confusion_matrix" in metrics_dict:
            print("\n【混同行列】")
            cm = np.array(metrics_dict["confusion_matrix"]["matrix"])
            print(cm)

        # 予測確率メトリクス
        if "probability_metrics" in metrics_dict:
            print("\n【予測確率メトリクス】")
            pm = metrics_dict["probability_metrics"]
            print(f"  平均信頼度: {pm.get('mean_confidence', 0):.4f}")
            print(f"  中央値信頼度: {pm.get('median_confidence', 0):.4f}")
            if pm.get("log_loss"):
                print(f"  Log Loss: {pm.get('log_loss', 0):.4f}")

        print("\n" + "=" * 80 + "\n")

    @staticmethod
    def get_model_strength_assessment(metrics_dict: Dict[str, Any]) -> Dict[str, str]:
        """
        モデルの強み・弱みを評価

        Returns:
            強み・弱みの評価
        """
        assessment = {
            "strengths": [],
            "weaknesses": [],
            "recommendations": [],
        }

        if "global_metrics" not in metrics_dict:
            return assessment

        gm = metrics_dict["global_metrics"]
        f1_macro = gm.get("f1_macro", 0)

        # F1スコアの評価
        if f1_macro >= 0.7:
            assessment["strengths"].append("✅ 全体的に良好な予測精度（F1 >= 0.7）")
        elif f1_macro >= 0.5:
            assessment["strengths"].append("⚠️ 中程度の予測精度（F1 >= 0.5）")
        else:
            assessment["weaknesses"].append(
                "❌ 低い予測精度（F1 < 0.5）。特徴量エンジニアリングの改善が必要"
            )
            assessment["recommendations"].append("特徴量を追加・改良する（騎手、調教師情報など）")

        # クラス別性能の不均衡
        if "class_metrics" in metrics_dict:
            f1_scores = [m.get("f1_score", 0) for m in metrics_dict["class_metrics"].values()]
            if max(f1_scores) - min(f1_scores) > 0.2:
                assessment["weaknesses"].append(
                    f"クラス別性能が不均衡（F1の差: {max(f1_scores) - min(f1_scores):.2f}）"
                )
                assessment["recommendations"].append(
                    "クラスの重み付けを調整するか、アンダーサンプリング/オーバーサンプリングを検討"
                )

        # Recallが低い場合
        recall_macro = gm.get("recall_macro", 0)
        if recall_macro < 0.5:
            assessment["weaknesses"].append("❌ Recall（再現率）が低い。予測漏れが多い可能性")
            assessment["recommendations"].append(
                "シンプルなモデルで試す、またはクラス重み付けを調整"
            )

        return assessment
