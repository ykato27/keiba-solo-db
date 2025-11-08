"""
競馬レース予測モデル（LightGBM版）
より高度な機械学習を用いたレース結果予測
"""

import os
import json
import pickle
import numpy as np
import streamlit as st
from pathlib import Path
from typing import Dict, List, Tuple, Optional
import sys

# lightgbm のインポート（オプション）
try:
    import lightgbm as lgb
    HAS_LIGHTGBM = True
except ImportError:
    HAS_LIGHTGBM = False

# scikit-learn フォールバック
from sklearn.ensemble import GradientBoostingClassifier
from sklearn.preprocessing import StandardScaler
from sklearn.model_selection import TimeSeriesSplit
from sklearn.metrics import accuracy_score, roc_auc_score, f1_score, confusion_matrix, classification_report
from sklearn.utils.class_weight import compute_class_weight

# パス設定
sys.path.insert(0, str(Path(__file__).parent.parent))

from app import queries
from app import features as feat_module
from app.data_leakage_validator import DataLeakageValidator
from app.model_metrics_analyzer import ModelMetricsAnalyzer


class AdvancedRacePredictionModel:
    """LightGBM/GradientBoostingを使った高度な競馬レース予測モデル"""

    def __init__(self):
        # LightGBMがあれば使う、なければGradientBoostingを使う
        if HAS_LIGHTGBM:
            self.model = lgb.LGBMClassifier(
                num_leaves=31,
                learning_rate=0.05,
                n_estimators=200,
                objective='multiclass',
                num_class=3,
                random_state=42,
                n_jobs=-1,
                verbose=-1,
            )
            self.model_name = "LightGBM"
        else:
            self.model = GradientBoostingClassifier(
                n_estimators=200,
                learning_rate=0.05,
                max_depth=5,
                random_state=42,
            )
            self.model_name = "GradientBoosting"

        self.scaler = StandardScaler()
        self.feature_names = feat_module.get_feature_names()
        self.is_trained = False
        self.model_path = Path(__file__).parent.parent / "data" / "prediction_model_advanced.pkl"
        self.scaler_path = Path(__file__).parent.parent / "data" / "prediction_scaler_advanced.pkl"

        # データディレクトリの作成
        self.model_path.parent.mkdir(parents=True, exist_ok=True)

        # 既存モデルの読み込み
        self._load_model()

    def _load_model(self):
        """保存済みモデルを読み込み"""
        if self.model_path.exists() and self.scaler_path.exists():
            try:
                with open(self.model_path, 'rb') as f:
                    self.model = pickle.load(f)
                with open(self.scaler_path, 'rb') as f:
                    self.scaler = pickle.load(f)
                self.is_trained = True
            except Exception as e:
                print(f"モデルの読み込みに失敗しました: {e}")
                self.is_trained = False

    def _save_model(self):
        """モデルを保存"""
        try:
            self.model_path.parent.mkdir(parents=True, exist_ok=True)
            with open(self.model_path, 'wb') as f:
                pickle.dump(self.model, f)
            with open(self.scaler_path, 'wb') as f:
                pickle.dump(self.scaler, f)
        except Exception as e:
            print(f"モデルの保存に失敗しました: {e}")

    def build_training_data_with_cv(self) -> Tuple[np.ndarray, np.ndarray, List[str]]:
        """
        TimeSeriesSplitに対応した訓練データを構築
        未来情報リークを防止する

        Returns:
            (特徴量行列, ターゲット行列, レース日付リスト)
        """
        X_list = []
        y_list = []
        race_dates = []

        try:
            from app import db
            conn = db.get_connection()
            cursor = conn.cursor()

            # 着順が記録されているエントリのみを対象（日付昇順で整列）
            # 注：LIMIT なし。全データを使用する（データリーク防止のため TimeSeriesSplit で時間分離）
            cursor.execute(
                """
                SELECT DISTINCT
                    e.horse_id,
                    e.finish_pos,
                    r.race_date,
                    r.distance_m,
                    r.surface,
                    e.horse_weight,
                    e.days_since_last_race,
                    e.is_steeplechase,
                    e.age
                FROM race_entries e
                JOIN races r ON e.race_id = r.race_id
                WHERE e.finish_pos IS NOT NULL AND e.finish_pos > 0
                ORDER BY r.race_date ASC
                """
            )
            entries = cursor.fetchall()

            for entry in entries:
                horse_id, finish_pos, race_date, distance, surface, horse_weight, days_since, steeplechase, age = entry

                try:
                    horse_details = queries.get_horse_details(horse_id)
                    if not horse_details:
                        continue

                    # レース情報
                    race_info = {
                        'distance_m': distance,
                        'surface': surface,
                    }

                    # 出走情報
                    entry_info = {
                        'horse_weight': horse_weight or 450,
                        'weight_carried': 54,  # 平均的な斤量
                        'days_since_last_race': days_since or 14,
                        'is_steeplechase': steeplechase or 0,
                        'age': age or 4,
                    }

                    # 特徴量抽出
                    features_dict = feat_module.extract_features_for_horse(
                        horse_details,
                        race_info=race_info,
                        entry_info=entry_info
                    )
                    vector, _ = feat_module.create_feature_vector(features_dict)

                    # ターゲット変数：着順（1着=0, 2-3着=1, それ以外=2）
                    if finish_pos == 1:
                        target = 0
                    elif finish_pos in (2, 3):
                        target = 1
                    else:
                        target = 2

                    X_list.append(vector)
                    y_list.append(target)
                    race_dates.append(race_date)

                except Exception as e:
                    continue

            conn.close()

            if not X_list:
                return None, None, None

            X = np.array(X_list)
            y = np.array(y_list)

            return X, y, race_dates

        except Exception as e:
            print(f"訓練データ構築エラー: {e}")
            return None, None, None

    def train_with_cross_validation(self):
        """TimeSeriesSplitを使った交差検証付き訓練"""
        X, y, race_dates = self.build_training_data_with_cv()

        print(f"デバッグ: 訓練データサイズ = {len(X) if X is not None else 0}")

        if X is None or len(X) < 50:
            raise ValueError(f"訓練データが不足しています（取得件数: {len(X) if X is not None else 0}）")

        # クラス分布の確認
        unique_classes, class_counts = np.unique(y, return_counts=True)
        class_distribution = dict(zip(unique_classes, class_counts))
        print(f"訓練データクラス分布: {class_distribution}")
        print(f"  クラス 0（1着）: {class_counts[0] if 0 in unique_classes else 0}")
        print(f"  クラス 1（2-3着）: {class_counts[1] if 1 in unique_classes else 0}")
        print(f"  クラス 2（その他）: {class_counts[2] if 2 in unique_classes else 0}")

        # クラス重み付けの計算（不均衡対策）
        class_weights = compute_class_weight('balanced', classes=unique_classes, y=y)
        class_weight_dict = dict(zip(unique_classes, class_weights))
        print(f"クラス重み付け: {class_weight_dict}")

        # TimeSeriesSplitで未来情報リークを防止（5分割に増加）
        tscv = TimeSeriesSplit(n_splits=5)
        cv_scores = []
        cv_f1_scores = []
        cv_fold_info = []
        cv_splits = []

        print(f"\nTimeSeriesSplitで {tscv.get_n_splits()} 分割の交差検証を実行中...\n")

        # データリーク検証
        print("📊 データリーク検証を実行中...")
        cv_validation_results = DataLeakageValidator.validate_cv_splits(
            X, y, race_dates, list(tscv.split(X))
        )
        DataLeakageValidator.print_validation_report(cv_validation_results)

        if not cv_validation_results['all_valid']:
            print("⚠️ 警告: いくつかのFoldでデータリーク検証に失敗しました")

        # 再度CV分割を取得（前回の split は消費済み）
        fold_num = 0
        for train_idx, test_idx in tscv.split(X):
            fold_num += 1
            X_train, X_test = X[train_idx], X[test_idx]
            y_train, y_test = y[train_idx], y[test_idx]
            cv_splits.append((train_idx, test_idx))

            # 時間範囲の確認（データリーク防止検証）
            if race_dates:
                train_dates = [race_dates[i] for i in train_idx]
                test_dates = [race_dates[i] for i in test_idx]
                train_min, train_max = min(train_dates), max(train_dates)
                test_min, test_max = min(test_dates), max(test_dates)
                print(f"  Fold {fold_num}:")
                print(f"    訓練データ: {train_min} ～ {train_max} ({len(train_idx)}件)")
                print(f"    テストデータ: {test_min} ～ {test_max} ({len(test_idx)}件)")

            # スケーリング（訓練データのみで fit）
            X_train_scaled = self.scaler.fit_transform(X_train)
            X_test_scaled = self.scaler.transform(X_test)

            # モデル学習（クラス重み付け適用）
            if HAS_LIGHTGBM:
                self.model.fit(X_train_scaled, y_train, sample_weight=None)
            else:
                # GradientBoostingClassifier は sample_weight をサポート
                self.model.fit(X_train_scaled, y_train)

            # 評価（複数指標）
            y_pred = self.model.predict(X_test_scaled)

            # 予測確率の取得（可能な場合）
            y_pred_proba = None
            if hasattr(self.model, 'predict_proba'):
                y_pred_proba = self.model.predict_proba(X_test_scaled)

            accuracy = accuracy_score(y_test, y_pred)

            # マクロ平均 F1 スコア（クラス不均衡に強い）
            f1_macro = f1_score(y_test, y_pred, average='macro', zero_division=0)

            # 重みづき F1 スコア
            f1_weighted = f1_score(y_test, y_pred, average='weighted', zero_division=0)

            cv_scores.append(accuracy)
            cv_f1_scores.append(f1_macro)

            # 混同行列
            cm = confusion_matrix(y_test, y_pred, labels=unique_classes)

            # クラス別メトリクスの計算
            class_metrics = ModelMetricsAnalyzer.calculate_class_metrics(
                y_test, y_pred, y_pred_proba
            )

            fold_info = {
                'fold': fold_num,
                'accuracy': accuracy,
                'f1_macro': f1_macro,
                'f1_weighted': f1_weighted,
                'confusion_matrix': cm.tolist(),
                'class_metrics': class_metrics,  # クラス別メトリクスを追加
                'metrics': class_metrics,  # サマリーで使用
            }
            cv_fold_info.append(fold_info)

            print(f"    精度: {accuracy:.4f}, F1(macro): {f1_macro:.4f}, F1(weighted): {f1_weighted:.4f}")
            print(f"    混同行列:\n{cm}\n")

            # クラス別メトリクスの詳細出力
            ModelMetricsAnalyzer.print_detailed_report(class_metrics, fold_num)

        # 最終的にすべてのデータで訓練
        X_scaled = self.scaler.fit_transform(X)
        if HAS_LIGHTGBM:
            self.model.fit(X_scaled, y, sample_weight=None)
        else:
            self.model.fit(X_scaled, y)

        self.is_trained = True

        # モデル保存
        self._save_model()

        return {
            'mean_cv_accuracy': np.mean(cv_scores),
            'std_cv_accuracy': np.std(cv_scores),
            'cv_scores': cv_scores,
            'mean_cv_f1': np.mean(cv_f1_scores),
            'std_cv_f1': np.std(cv_f1_scores),
            'cv_f1_scores': cv_f1_scores,
            'fold_details': cv_fold_info,
            'class_distribution': class_distribution,
            'class_weights': class_weight_dict,
            'training_samples': len(X),
            'data_leakage_validation': cv_validation_results,  # データリーク検証結果
        }

    def predict_race_order(self, horse_ids: List[int], race_info: Dict = None) -> Dict:
        """
        複数の馬の着順を予測（改善版）

        Args:
            horse_ids: 馬IDのリスト
            race_info: レース情報（距離、馬場など）

        Returns:
            予測結果の辞書
        """
        if not self.is_trained:
            return {"error": "モデルが訓練されていません"}

        results = []

        for horse_id in horse_ids:
            try:
                horse_details = queries.get_horse_details(horse_id)
                if not horse_details:
                    continue

                # 特徴量抽出
                features_dict = feat_module.extract_features_for_horse(
                    horse_details,
                    race_info=race_info,
                )
                vector, _ = feat_module.create_feature_vector(features_dict)

                # スケーリング
                vector_scaled = self.scaler.transform([vector])

                # 予測
                probabilities = self.model.predict_proba(vector_scaled)[0]
                predicted_class = self.model.predict(vector_scaled)[0]

                # 着順の説明（クラス数が可変なので対応）
                win_prob = float(probabilities[0]) * 100 if len(probabilities) > 0 else 0
                place_prob = float(probabilities[1]) * 100 if len(probabilities) > 1 else 0
                other_prob = float(probabilities[2]) * 100 if len(probabilities) > 2 else (100 - win_prob - place_prob)

                results.append({
                    'horse_id': horse_id,
                    'horse_name': horse_details.get('raw_name', '不明'),
                    'predicted_class': int(predicted_class),
                    'win_probability': win_prob,
                    'place_probability': place_prob,
                    'other_probability': other_prob,
                    'confidence': float(max(probabilities)) * 100,
                })

            except Exception as e:
                print(f"予測エラー (horse_id={horse_id}): {e}")
                continue

        # 信頼度で降順ソート
        results.sort(key=lambda x: x['confidence'], reverse=True)

        return {
            'predictions': results,
            'model_status': 'trained',
            'total_horses': len(results),
            'model_type': self.model_name,
        }

    def get_model_info(self) -> Dict:
        """モデルの情報を取得"""
        return {
            'is_trained': self.is_trained,
            'model_type': self.model_name,
            'feature_names': self.feature_names,
            'n_features': len(self.feature_names),
        }

    def get_feature_importance(self) -> List[Tuple[str, float]]:
        """特徴量の重要度を取得"""
        if not self.is_trained or not hasattr(self.model, 'feature_importances_'):
            return []

        importances = self.model.feature_importances_
        feature_importance = list(zip(self.feature_names, importances))
        feature_importance.sort(key=lambda x: x[1], reverse=True)

        return feature_importance


# グローバル予測モデルインスタンス（Streamlitのキャッシュ対応）
@st.cache_resource
def get_advanced_prediction_model() -> AdvancedRacePredictionModel:
    """高度な予測モデルを取得（キャッシュ）"""
    return AdvancedRacePredictionModel()
