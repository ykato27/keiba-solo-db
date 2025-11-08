"""
改善されたモデル訓練モジュール
Early Stopping、Learning Curve、過学習診断を含む

このモジュールは prediction_model_lightgbm.py を補完し、
プロダクションレベルのモデル検証を提供します。
"""

import numpy as np
import pandas as pd
from typing import Dict, List, Tuple, Optional
from sklearn.metrics import accuracy_score, f1_score, roc_auc_score
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

try:
    import lightgbm as lgb
    HAS_LIGHTGBM = True
except ImportError:
    HAS_LIGHTGBM = False


class ModelTrainingEnhanced:
    """拡張モデル訓練エンジン"""

    @staticmethod
    def train_with_early_stopping(
        X_train: np.ndarray,
        y_train: np.ndarray,
        X_val: np.ndarray,
        y_val: np.ndarray,
        model_class=None,
        model_params: Dict = None,
        early_stopping_rounds: int = 50,
        verbose: bool = True
    ):
        """
        Early Stopping 付きで LightGBM モデルを訓練

        Args:
            X_train: 訓練データ
            y_train: 訓練ラベル
            X_val: 検証データ
            y_val: 検証ラベル
            model_class: モデルクラス（LGBMClassifier or GradientBoostingClassifier）
            model_params: モデルパラメータ
            early_stopping_rounds: Early Stopping の待機ラウンド数
            verbose: ログ出力

        Returns:
            訓練済みモデル、訓練履歴、診断情報
        """
        if model_params is None:
            model_params = {
                'num_leaves': 31,
                'learning_rate': 0.05,
                'n_estimators': 500,  # Early Stopping で削減される
                'random_state': 42,
            }

        if not HAS_LIGHTGBM:
            raise ImportError("LightGBM is required for early stopping training")

        # LightGBM のデータセット形式に変換
        train_data = lgb.Dataset(X_train, label=y_train)
        val_data = lgb.Dataset(X_val, label=y_val, reference=train_data)

        # Early Stopping コールバック
        callbacks = [
            lgb.early_stopping(early_stopping_rounds),
            lgb.log_evaluation(period=0) if verbose else lgb.log_evaluation(period=0)
        ]

        # モデル訓練
        booster = lgb.train(
            params=model_params,
            train_set=train_data,
            num_boost_round=model_params.get('n_estimators', 500),
            valid_sets=[val_data],
            callbacks=callbacks,
            verbose_eval=False
        )

        # 訓練履歴の取得
        evals_result = booster.evals_result_

        # 診断情報
        training_history = {
            'num_rounds': booster.num_trees(),
            'train_loss': evals_result.get('training', {}).get('multi_logloss', []),
            'val_loss': evals_result.get('valid_1', {}).get('multi_logloss', []),
            'stopped_round': early_stopping_rounds,
        }

        if verbose:
            print(f"✅ Early Stopping により {booster.num_trees()} ラウンドで訓練完了")
            print(f"   （設定: max {model_params.get('n_estimators', 500)} ラウンド）")

        return booster, training_history

    @staticmethod
    def analyze_learning_curve(
        train_losses: List[float],
        val_losses: List[float]
    ) -> Dict:
        """
        Learning Curve を分析して過学習を診断

        Args:
            train_losses: 訓練損失のリスト
            val_losses: 検証損失のリスト

        Returns:
            過学習の診断情報
        """
        if len(train_losses) < 10:
            return {
                'status': '⚠️ サンプル不足',
                'message': '10ラウンド以上の訓練が必要です'
            }

        # 最後の 10% のデータで傾向を確認
        window_size = max(5, len(train_losses) // 10)
        final_train = np.mean(train_losses[-window_size:])
        final_val = np.mean(val_losses[-window_size:])

        # 初期と最終の損失差分
        initial_train = train_losses[0]
        initial_val = val_losses[0]

        gap = final_val - final_train
        gap_trend = (val_losses[-1] - train_losses[-1]) - (val_losses[0] - train_losses[0])

        diagnosis = {
            'final_train_loss': final_train,
            'final_val_loss': final_val,
            'generalization_gap': gap,
            'gap_trend': gap_trend,
            'status': None,
            'recommendation': None
        }

        # 過学習判定
        if gap < 0.05:
            diagnosis['status'] = '✅ 正常'
            diagnosis['recommendation'] = 'モデルは適切に汎化している'
        elif gap < 0.15:
            diagnosis['status'] = '🟡 軽微な過学習'
            diagnosis['recommendation'] = 'early_stopping_rounds を増加させるか、正則化を強化'
        elif gap < 0.3:
            diagnosis['status'] = '🟠 中程度の過学習'
            diagnosis['recommendation'] = 'max_depth を削減、learning_rate を下げる、n_estimators を削減'
        else:
            diagnosis['status'] = '🔴 重度の過学習'
            diagnosis['recommendation'] = 'モデル構造の見直しが必須'

        # トレンド分析
        if gap_trend > 0.01:
            diagnosis['trend'] = '悪化傾向あり'
        elif gap_trend < -0.01:
            diagnosis['trend'] = '改善傾向あり'
        else:
            diagnosis['trend'] = '安定'

        return diagnosis

    @staticmethod
    def compute_fold_wise_metrics(
        y_true_list: List[np.ndarray],
        y_pred_list: List[np.ndarray],
        y_pred_proba_list: List[np.ndarray]
    ) -> Dict:
        """
        Fold ごとのメトリクスを計算

        Args:
            y_true_list: 各 Fold の真値リスト
            y_pred_list: 各 Fold の予測値リスト
            y_pred_proba_list: 各 Fold の予測確率リスト

        Returns:
            Fold ごとのメトリクス
        """
        fold_metrics = []

        for fold_idx, (y_true, y_pred, y_proba) in enumerate(
            zip(y_true_list, y_pred_list, y_pred_proba_list),
            start=1
        ):
            # 各クラスごとの精度
            accuracy = accuracy_score(y_true, y_pred)
            f1_macro = f1_score(y_true, y_pred, average='macro', zero_division=0)
            f1_weighted = f1_score(y_true, y_pred, average='weighted', zero_division=0)

            # AUC-ROC（3クラス分類の場合は ovr）
            try:
                auc_score = roc_auc_score(
                    y_true, y_proba, multi_class='ovr', average='weighted', zero_division=0
                )
            except:
                auc_score = np.nan

            fold_metrics.append({
                'fold': fold_idx,
                'accuracy': accuracy,
                'f1_macro': f1_macro,
                'f1_weighted': f1_weighted,
                'auc': auc_score,
                'samples': len(y_true)
            })

        return {
            'fold_metrics': pd.DataFrame(fold_metrics),
            'mean_accuracy': np.mean([m['accuracy'] for m in fold_metrics]),
            'std_accuracy': np.std([m['accuracy'] for m in fold_metrics]),
            'mean_f1_macro': np.mean([m['f1_macro'] for m in fold_metrics]),
            'std_f1_macro': np.std([m['f1_macro'] for m in fold_metrics]),
            'mean_auc': np.mean([m['auc'] for m in fold_metrics if not np.isnan(m['auc'])]),
        }

    @staticmethod
    def generate_training_report(
        training_history: Dict,
        fold_metrics: Dict,
        learning_curve_diagnosis: Dict
    ) -> Dict:
        """
        訓練レポートを生成

        Args:
            training_history: Early Stopping の履歴
            fold_metrics: Fold ごとのメトリクス
            learning_curve_diagnosis: 過学習診断

        Returns:
            統合レポート
        """
        return {
            'training_summary': {
                'num_rounds': training_history.get('num_rounds'),
                'stopped_at': training_history.get('stopped_round'),
            },
            'model_performance': {
                'mean_accuracy': fold_metrics.get('mean_accuracy'),
                'std_accuracy': fold_metrics.get('std_accuracy'),
                'mean_f1': fold_metrics.get('mean_f1_macro'),
                'mean_auc': fold_metrics.get('mean_auc'),
            },
            'overfitting_diagnosis': learning_curve_diagnosis,
            'fold_details': fold_metrics.get('fold_metrics'),
            'recommendations': ModelTrainingEnhanced._generate_recommendations(
                fold_metrics, learning_curve_diagnosis
            )
        }

    @staticmethod
    def _generate_recommendations(fold_metrics: Dict, overfitting_diag: Dict) -> List[str]:
        """訓練結果から改善推奨を生成"""
        recommendations = []

        # 精度ベースの推奨
        mean_acc = fold_metrics.get('mean_accuracy', 0)
        if mean_acc < 0.5:
            recommendations.append('🔴 精度が低い（< 50%）。特徴量の見直しが必須')
        elif mean_acc < 0.6:
            recommendations.append('🟡 精度が改善の余地あり（< 60%）。特徴量エンジニアリングを検討')

        # 過学習ベースの推奨
        if overfitting_diag.get('status') in ['🔴 重度の過学習', '🟠 中程度の過学習']:
            recommendations.append('🔴 過学習が発生している。モデル複雑性を削減してください')
        elif overfitting_diag.get('status') == '🟡 軽微な過学習':
            recommendations.append('🟡 軽微な過学習あり。Early Stopping ラウンドの調整を検討')

        # 分散ベースの推奨
        std_acc = fold_metrics.get('std_accuracy', 0)
        if std_acc > 0.1:
            recommendations.append('🟡 Fold 間の精度に大きなばらつきあり。データの時系列構造を再確認')

        if not recommendations:
            recommendations.append('✅ モデルは良好な状態です')

        return recommendations
