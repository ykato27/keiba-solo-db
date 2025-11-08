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
from sklearn.metrics import accuracy_score, roc_auc_score

# パス設定
sys.path.insert(0, str(Path(__file__).parent.parent))

import queries
import features as feat_module


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

    def build_training_data_with_cv(self) -> Tuple[np.ndarray, np.ndarray]:
        """
        TimeSeriesSplitに対応した訓練データを構築
        未来情報リークを防止する

        Returns:
            (特徴量行列, ターゲット行列)
        """
        X_list = []
        y_list = []
        race_dates = []

        try:
            import db
            conn = db.get_connection()
            cursor = conn.cursor()

            # 着順が記録されているエントリのみを対象
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
                LIMIT 3000
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
                return None, None

            X = np.array(X_list)
            y = np.array(y_list)

            return X, y

        except Exception as e:
            print(f"訓練データ構築エラー: {e}")
            return None, None

    def train_with_cross_validation(self):
        """TimeSeriesSplitを使った交差検証付き訓練"""
        X, y = self.build_training_data_with_cv()

        print(f"デバッグ: 訓練データサイズ = {len(X) if X is not None else 0}")

        if X is None or len(X) < 50:
            raise ValueError(f"訓練データが不足しています（取得件数: {len(X) if X is not None else 0}）")

        # TimeSeriesSplitで未来情報リークを防止
        tscv = TimeSeriesSplit(n_splits=3)
        cv_scores = []

        print(f"TimeSeriesSplitで {tscv.get_n_splits()} 分割の交差検証を実行中...")

        for train_idx, test_idx in tscv.split(X):
            X_train, X_test = X[train_idx], X[test_idx]
            y_train, y_test = y[train_idx], y[test_idx]

            # スケーリング
            X_train_scaled = self.scaler.fit_transform(X_train)
            X_test_scaled = self.scaler.transform(X_test)

            # モデル学習
            self.model.fit(X_train_scaled, y_train)

            # 評価
            y_pred = self.model.predict(X_test_scaled)
            accuracy = accuracy_score(y_test, y_pred)
            cv_scores.append(accuracy)

            print(f"  Fold Accuracy: {accuracy:.4f}")

        # 最終的にすべてのデータで訓練
        X_scaled = self.scaler.fit_transform(X)
        self.model.fit(X_scaled, y)
        self.is_trained = True

        # モデル保存
        self._save_model()

        return {
            'mean_cv_accuracy': np.mean(cv_scores),
            'std_cv_accuracy': np.std(cv_scores),
            'cv_scores': cv_scores,
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

                # 着順の説明
                win_prob = float(probabilities[0]) * 100
                place_prob = float(probabilities[1]) * 100
                other_prob = float(probabilities[2]) * 100

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
