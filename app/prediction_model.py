"""
競馬レース予測モデル
機械学習を用いたレース結果予測
"""

import os
import json
import pickle
import numpy as np
import streamlit as st
from pathlib import Path
from typing import Dict, List, Tuple, Optional
from sklearn.ensemble import RandomForestClassifier
from sklearn.preprocessing import StandardScaler
import sys

# パス設定
sys.path.insert(0, str(Path(__file__).parent.parent))

import queries
import features as feat_module


class RacePredictionModel:
    """競馬レース予測モデル"""

    def __init__(self):
        self.model = RandomForestClassifier(
            n_estimators=100,
            max_depth=15,
            min_samples_split=5,
            min_samples_leaf=2,
            random_state=42,
            n_jobs=-1,
        )
        self.scaler = StandardScaler()
        self.feature_names = feat_module.get_feature_names()
        self.is_trained = False
        self.model_path = Path(__file__).parent.parent / "data" / "prediction_model.pkl"
        self.scaler_path = Path(__file__).parent.parent / "data" / "prediction_scaler.pkl"

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

    def build_training_data(self) -> Tuple[np.ndarray, np.ndarray]:
        """
        過去レース結果から訓練データを構築

        Returns:
            (特徴量行列, ターゲット行列)
        """
        X_list = []
        y_list = []

        # すべてのレースエントリを取得
        try:
            # データベースから過去のレースエントリを取得
            # ここではクエリを直接実行（キャッシュをバイパス）
            import db
            conn = db.get_connection()
            cursor = conn.cursor()

            # 着順が記録されているエントリのみを対象
            cursor.execute(
                """
                SELECT DISTINCT e.horse_id, e.finish_pos
                FROM race_entries e
                WHERE e.finish_pos IS NOT NULL AND e.finish_pos > 0
                LIMIT 5000
                """
            )
            entries = cursor.fetchall()

            for horse_id, finish_pos in entries:
                try:
                    horse_details = queries.get_horse_details(horse_id)
                    if not horse_details:
                        continue

                    # 特徴量抽出
                    features_dict = feat_module.extract_features_for_horse(horse_details)
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

    def train(self):
        """モデルを訓練"""
        X, y = self.build_training_data()

        if X is None or len(X) < 10:
            raise ValueError("訓練データが不足しています")

        # スケーリング
        X_scaled = self.scaler.fit_transform(X)

        # モデル学習
        self.model.fit(X_scaled, y)
        self.is_trained = True

        # モデル保存
        self._save_model()

    def predict_race_order(self, horse_ids: List[int]) -> Dict:
        """
        複数の馬の着順を予測

        Args:
            horse_ids: 馬IDのリスト

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
                features_dict = feat_module.extract_features_for_horse(horse_details)
                vector, _ = feat_module.create_feature_vector(features_dict)

                # スケーリング
                vector_scaled = self.scaler.transform([vector])

                # 予測
                probabilities = self.model.predict_proba(vector_scaled)[0]
                predicted_class = self.model.predict(vector_scaled)[0]

                # 着順の説明
                class_names = ['1着の可能性', '2-3着の可能性', 'その他']
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
        }

    def get_model_info(self) -> Dict:
        """モデルの情報を取得"""
        return {
            'is_trained': self.is_trained,
            'model_type': 'Random Forest Classifier',
            'n_estimators': self.model.n_estimators,
            'feature_names': self.feature_names,
            'n_features': len(self.feature_names),
        }


# グローバル予測モデルインスタンス（Streamlitのキャッシュ対応）
@st.cache_resource
def get_prediction_model() -> RacePredictionModel:
    """予測モデルを取得（キャッシュ）"""
    return RacePredictionModel()
