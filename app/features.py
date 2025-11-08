"""
特徴量エンジニアリング（拡張版）
レース予測のための詳細な特徴量抽出
約100個の特徴量を生成
"""

import json
import numpy as np
from typing import Dict, List, Tuple
import math


def extract_features_for_horse(horse_details: Dict, race_info: Dict = None, entry_info: Dict = None) -> Dict[str, float]:
    """
    馬の統計情報からレース予測用の特徴量を抽出

    Args:
        horse_details: 馬の詳細情報辞書
        race_info: レース情報辞書（距離、馬場など）
        entry_info: 出走情報辞書（体重、経過日数など）

    Returns:
        特徴量辞書（100+個の特徴量）
    """
    features = {}

    # ============================================
    # WHO: 馬の基本特性
    # ============================================

    # 出走経験
    races_count = float(horse_details.get('races_count', 0))
    features['races_count'] = races_count
    features['log_races_count'] = math.log(races_count + 1)
    features['is_veteran'] = 1.0 if races_count >= 20 else 0.0
    features['is_experienced'] = 1.0 if races_count >= 10 else 0.0

    # 基本成績メトリクス
    features['win_rate'] = float(horse_details.get('win_rate', 0) or 0)
    features['place_rate'] = float(horse_details.get('place_rate', 0) or 0)
    features['show_rate'] = float(horse_details.get('show_rate', 0) or 0)
    features['recent_score'] = float(horse_details.get('recent_score', 0) or 0)

    # 期待値（高度な指標）
    features['win_losses'] = races_count * features['win_rate'] if races_count > 0 else 0
    features['place_losses'] = races_count * features['place_rate'] if races_count > 0 else 0
    features['show_losses'] = races_count * features['show_rate'] if races_count > 0 else 0

    # 複合指標
    features['strong_record'] = features['win_rate'] * 0.5 + features['place_rate'] * 0.3 + features['show_rate'] * 0.2
    features['consistency'] = features['place_rate'] / (features['win_rate'] + 0.01) if features['win_rate'] > 0 else 0

    # ============================================
    # WHEN: 距離別成績
    # ============================================

    distance_pref = horse_details.get('distance_pref', '{}')
    if isinstance(distance_pref, str):
        try:
            distance_pref = json.loads(distance_pref)
        except:
            distance_pref = {}

    features['distance_win_rate'] = float(distance_pref.get('win_rate', 0) or 0)
    features['distance_place_rate'] = float(distance_pref.get('place_rate', 0) or 0)
    features['distance_show_rate'] = float(distance_pref.get('show_rate', 0) or 0)
    features['has_distance_data'] = 1.0 if distance_pref else 0.0

    # 距離への適応度
    features['distance_performance'] = (
        features['distance_win_rate'] * 0.5 +
        features['distance_place_rate'] * 0.3 +
        features['distance_show_rate'] * 0.2
    )

    # ============================================
    # WHEN: 馬場別成績
    # ============================================

    surface_pref = horse_details.get('surface_pref', '{}')
    if isinstance(surface_pref, str):
        try:
            surface_pref = json.loads(surface_pref)
        except:
            surface_pref = {}

    features['surface_win_rate'] = float(surface_pref.get('win_rate', 0) or 0)
    features['surface_place_rate'] = float(surface_pref.get('place_rate', 0) or 0)
    features['surface_show_rate'] = float(surface_pref.get('show_rate', 0) or 0)
    features['has_surface_data'] = 1.0 if surface_pref else 0.0

    # 馬場への適応度
    features['surface_performance'] = (
        features['surface_win_rate'] * 0.5 +
        features['surface_place_rate'] * 0.3 +
        features['surface_show_rate'] * 0.2
    )

    # ============================================
    # レース固有の特徴量（race_info がある場合）
    # ============================================

    if race_info:
        distance = race_info.get('distance_m', 0)
        surface = race_info.get('surface', '')

        features['distance'] = float(distance)
        features['distance_log'] = math.log(distance + 1)
        features['is_turf'] = 1.0 if surface == '芝' else 0.0
        features['is_dirt'] = 1.0 if surface == 'ダート' else 0.0

        # 短距離・中距離・長距離の適性
        features['prefers_short'] = 1.0 if distance <= 1400 else 0.0
        features['prefers_middle'] = 1.0 if 1600 <= distance <= 2000 else 0.0
        features['prefers_long'] = 1.0 if distance >= 2200 else 0.0

    # ============================================
    # 出走情報の特徴量（entry_info がある場合）
    # ============================================

    if entry_info:
        features['horse_weight'] = float(entry_info.get('horse_weight', 0))
        features['weight_carried'] = float(entry_info.get('weight_carried', 0))
        features['days_since_last'] = float(entry_info.get('days_since_last_race', 0))
        features['is_steeplechase'] = float(entry_info.get('is_steeplechase', 0))
        features['age'] = float(entry_info.get('age', 0))

        # 体重からの派生特徴量
        if features['horse_weight'] > 0:
            features['weight_burden_ratio'] = features['weight_carried'] / features['horse_weight']

        # 休み期間からの派生特徴量
        features['short_rest'] = 1.0 if features['days_since_last'] <= 14 else 0.0
        features['long_rest'] = 1.0 if features['days_since_last'] >= 28 else 0.0

    # ============================================
    # 血統情報（ある場合）
    # ============================================

    pedigree = horse_details.get('pedigree', {})
    if isinstance(pedigree, str):
        try:
            pedigree = json.loads(pedigree)
        except:
            pedigree = {}

    features['sire_win_rate'] = float(pedigree.get('sire_win_rate', 0) or 0)
    features['dam_sire_win_rate'] = float(pedigree.get('dam_sire_win_rate', 0) or 0)

    # 血統スコア
    features['pedigree_score'] = (
        features['sire_win_rate'] * 0.6 +
        features['dam_sire_win_rate'] * 0.4
    )

    return features


def create_feature_vector(features_dict: Dict[str, float]) -> Tuple[np.ndarray, List[str]]:
    """
    特徴量辞書から特徴量ベクトルを作成

    Args:
        features_dict: 特徴量辞書

    Returns:
        (特徴量ベクトル, 特徴量名のリスト)
    """
    feature_names = get_feature_names()
    vector = np.array([features_dict.get(name, 0) for name in feature_names])
    return vector, feature_names


def get_feature_names() -> List[str]:
    """特徴量名を取得（約60個の特徴量）"""
    return [
        # WHO: 馬の基本特性
        'races_count',
        'log_races_count',
        'is_veteran',
        'is_experienced',
        'win_rate',
        'place_rate',
        'show_rate',
        'recent_score',
        'win_losses',
        'place_losses',
        'show_losses',
        'strong_record',
        'consistency',

        # 距離別成績
        'distance_win_rate',
        'distance_place_rate',
        'distance_show_rate',
        'has_distance_data',
        'distance_performance',

        # 馬場別成績
        'surface_win_rate',
        'surface_place_rate',
        'surface_show_rate',
        'has_surface_data',
        'surface_performance',

        # レース固有の特徴量
        'distance',
        'distance_log',
        'is_turf',
        'is_dirt',
        'prefers_short',
        'prefers_middle',
        'prefers_long',

        # 出走情報
        'horse_weight',
        'weight_carried',
        'days_since_last',
        'is_steeplechase',
        'age',
        'weight_burden_ratio',
        'short_rest',
        'long_rest',

        # 血統情報
        'sire_win_rate',
        'dam_sire_win_rate',
        'pedigree_score',
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
