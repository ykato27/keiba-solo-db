"""
特徴量エンジニアリング
レース予測のための特徴量抽出
"""

import json
import numpy as np
from typing import Dict, List, Tuple


def extract_features_for_horse(horse_details: Dict) -> Dict[str, float]:
    """
    馬の統計情報から予測用の特徴量を抽出

    Args:
        horse_details: 馬の詳細情報辞書

    Returns:
        特徴量辞書
    """
    features = {}

    # 基本メトリクス
    features['races_count'] = float(horse_details.get('races_count', 0))
    features['win_rate'] = float(horse_details.get('win_rate', 0) or 0)
    features['place_rate'] = float(horse_details.get('place_rate', 0) or 0)
    features['show_rate'] = float(horse_details.get('show_rate', 0) or 0)
    features['recent_score'] = float(horse_details.get('recent_score', 0) or 0)

    # 距離別成績
    distance_pref = horse_details.get('distance_pref', '{}')
    if isinstance(distance_pref, str):
        try:
            distance_pref = json.loads(distance_pref)
        except:
            distance_pref = {}

    features['distance_win_rate'] = float(distance_pref.get('win_rate', 0) or 0)
    features['distance_place_rate'] = float(distance_pref.get('place_rate', 0) or 0)
    features['distance_show_rate'] = float(distance_pref.get('show_rate', 0) or 0)

    # 馬場別成績
    surface_pref = horse_details.get('surface_pref', '{}')
    if isinstance(surface_pref, str):
        try:
            surface_pref = json.loads(surface_pref)
        except:
            surface_pref = {}

    features['surface_win_rate'] = float(surface_pref.get('win_rate', 0) or 0)
    features['surface_place_rate'] = float(surface_pref.get('place_rate', 0) or 0)
    features['surface_show_rate'] = float(surface_pref.get('show_rate', 0) or 0)

    return features


def create_feature_vector(features_dict: Dict[str, float]) -> Tuple[np.ndarray, List[str]]:
    """
    特徴量辞書から特徴量ベクトルを作成

    Args:
        features_dict: 特徴量辞書

    Returns:
        (特徴量ベクトル, 特徴量名のリスト)
    """
    feature_names = [
        'races_count',
        'win_rate',
        'place_rate',
        'show_rate',
        'recent_score',
        'distance_win_rate',
        'distance_place_rate',
        'distance_show_rate',
        'surface_win_rate',
        'surface_place_rate',
        'surface_show_rate',
    ]

    vector = np.array([features_dict.get(name, 0) for name in feature_names])

    return vector, feature_names


def get_feature_names() -> List[str]:
    """特徴量名を取得"""
    return [
        'races_count',
        'win_rate',
        'place_rate',
        'show_rate',
        'recent_score',
        'distance_win_rate',
        'distance_place_rate',
        'distance_show_rate',
        'surface_win_rate',
        'surface_place_rate',
        'surface_show_rate',
    ]


def normalize_features(X: np.ndarray) -> np.ndarray:
    """
    特徴量を正規化（0-1の範囲）

    Args:
        X: 特徴量行列

    Returns:
        正規化された特徴量行列
    """
    # NaN を 0 に置換
    X = np.nan_to_num(X, nan=0.0, posinf=0.0, neginf=0.0)

    # 各特徴量を 0-1 の範囲に正規化
    X_min = np.min(X, axis=0)
    X_max = np.max(X, axis=0)

    # ゼロ除算を避ける
    X_range = X_max - X_min
    X_range[X_range == 0] = 1

    X_normalized = (X - X_min) / X_range

    return X_normalized
