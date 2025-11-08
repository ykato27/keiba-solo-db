"""
データリーク検証モジュール
Information Leakage の完全排除を確保

機能:
1. TimeSeriesSplit の時間範囲の厳密な検証
2. テストセットに過去情報が混在していないか確認
3. クラス分布のバイアス検出
4. 日付の時間的順序性確認
"""

import numpy as np
from typing import List, Tuple, Dict, Any
from datetime import datetime


class DataLeakageValidator:
    """データリーク検証エンジン"""

    @staticmethod
    def validate_timeseries_split(
        X: np.ndarray,
        y: np.ndarray,
        race_dates: List[str],
        train_idx: np.ndarray,
        test_idx: np.ndarray
    ) -> Dict[str, Any]:
        """
        TimeSeriesSplit の厳密な検証

        Args:
            X: 特徴量行列
            y: ターゲット行列
            race_dates: レース日付リスト
            train_idx: 訓練データのインデックス
            test_idx: テストデータのインデックス

        Returns:
            検証結果の辞書
        """
        validation_result = {
            'is_valid': True,
            'errors': [],
            'warnings': [],
            'train_date_range': None,
            'test_date_range': None,
            'time_overlap': False,
            'class_distribution_train': None,
            'class_distribution_test': None,
            'class_balance': True,
        }

        # 日付範囲の取得
        train_dates = [race_dates[i] for i in train_idx]
        test_dates = [race_dates[i] for i in test_idx]

        train_dates_sorted = sorted(train_dates)
        test_dates_sorted = sorted(test_dates)

        train_min = train_dates_sorted[0]
        train_max = train_dates_sorted[-1]
        test_min = test_dates_sorted[0]
        test_max = test_dates_sorted[-1]

        validation_result['train_date_range'] = (train_min, train_max)
        validation_result['test_date_range'] = (test_min, test_max)

        # 1. 時間範囲の厳密な分離確認
        if train_max >= test_min:
            validation_result['errors'].append(
                f"❌ 時間重複エラー: 訓練データの最大日付 ({train_max}) >= テストデータの最小日付 ({test_min})"
            )
            validation_result['is_valid'] = False
            validation_result['time_overlap'] = True
        else:
            # 訓練データと テストデータの時間差を計算
            try:
                train_max_dt = datetime.strptime(train_max, '%Y-%m-%d')
                test_min_dt = datetime.strptime(test_min, '%Y-%m-%d')
                days_gap = (test_min_dt - train_max_dt).days
                validation_result['days_gap'] = days_gap

                if days_gap < 0:
                    validation_result['errors'].append(
                        f"❌ 時系列順序エラー: テスト日付が訓練日付より前です（{days_gap}日）"
                    )
                    validation_result['is_valid'] = False
                elif days_gap == 0:
                    validation_result['warnings'].append(
                        "⚠️ 警告: 訓練データとテストデータが同じ日付です。未来情報リークのリスク有り"
                    )
                else:
                    validation_result['status'] = f"✅ 時間分離OK: {days_gap}日間のギャップ"
            except ValueError:
                validation_result['warnings'].append(
                    "⚠️ 日付フォーマットが解析できません。手動検証が必要"
                )

        # 2. クラス分布の確認
        y_train = y[train_idx]
        y_test = y[test_idx]

        unique_classes = np.unique(y)
        train_dist = {}
        test_dist = {}

        for cls in unique_classes:
            train_count = np.sum(y_train == cls)
            test_count = np.sum(y_test == cls)
            train_pct = train_count / len(y_train) * 100 if len(y_train) > 0 else 0
            test_pct = test_count / len(y_test) * 100 if len(y_test) > 0 else 0

            train_dist[int(cls)] = {
                'count': int(train_count),
                'percentage': round(train_pct, 2)
            }
            test_dist[int(cls)] = {
                'count': int(test_count),
                'percentage': round(test_pct, 2)
            }

        validation_result['class_distribution_train'] = train_dist
        validation_result['class_distribution_test'] = test_dist

        # クラス分布のバイアス検出（テストセットのクラスが訓練セットにない場合）
        train_classes = set(unique_classes)
        test_classes = set(np.unique(y_test))

        missing_in_train = test_classes - train_classes
        if missing_in_train:
            validation_result['errors'].append(
                f"❌ クラス不足エラー: テストセットに訓練セットにないクラスが含まれています: {missing_in_train}"
            )
            validation_result['is_valid'] = False
        else:
            validation_result['status'] = "✅ クラス分布OK: テストセットのすべてのクラスが訓練セットに含まれています"

        return validation_result

    @staticmethod
    def validate_cv_splits(
        X: np.ndarray,
        y: np.ndarray,
        race_dates: List[str],
        cv_splits: List[Tuple[np.ndarray, np.ndarray]]
    ) -> Dict[str, Any]:
        """
        複数のCV分割を一括検証

        Args:
            X: 特徴量行列
            y: ターゲット行列
            race_dates: レース日付リスト
            cv_splits: (train_idx, test_idx) のリスト

        Returns:
            複数分割の検証結果
        """
        results = {
            'total_folds': len(cv_splits),
            'all_valid': True,
            'folds': [],
            'summary': {}
        }

        for fold_num, (train_idx, test_idx) in enumerate(cv_splits, 1):
            fold_result = DataLeakageValidator.validate_timeseries_split(
                X, y, race_dates, train_idx, test_idx
            )
            fold_result['fold_num'] = fold_num
            results['folds'].append(fold_result)

            if not fold_result['is_valid']:
                results['all_valid'] = False

        # サマリー
        results['summary'] = {
            'total_valid_folds': sum(1 for f in results['folds'] if f['is_valid']),
            'total_invalid_folds': sum(1 for f in results['folds'] if not f['is_valid']),
            'all_passed': results['all_valid']
        }

        return results

    @staticmethod
    def check_feature_leakage(
        feature_names: List[str],
        excluded_patterns: List[str] = None
    ) -> Dict[str, Any]:
        """
        機能レベルでのリーク検出
        （未来情報を含む可能性のある特徴量を警告）

        Args:
            feature_names: 特徴量名のリスト
            excluded_patterns: 除外すべき特徴量のパターンリスト

        Returns:
            リーク検出結果
        """
        if excluded_patterns is None:
            excluded_patterns = [
                'future',
                'next',
                'ahead',
                'forward',
                'upcoming',
                'predicted',
                'forecast'
            ]

        potential_leakage = []
        safe_features = []

        for feature in feature_names:
            feature_lower = feature.lower()
            is_suspicious = any(pattern in feature_lower for pattern in excluded_patterns)

            if is_suspicious:
                potential_leakage.append(feature)
            else:
                safe_features.append(feature)

        return {
            'safe_features_count': len(safe_features),
            'potential_leakage_count': len(potential_leakage),
            'potential_leakage_features': potential_leakage,
            'safe_features': safe_features,
            'status': '✅ OK' if len(potential_leakage) == 0 else '⚠️ 警告: 疑わしい特徴量がある'
        }

    @staticmethod
    def validate_entry_completeness(
        X: np.ndarray,
        entries_data: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """
        エントリデータの完全性検証
        （着順なしの馬が訓練に含まれていないか確認）

        Args:
            X: 特徴量行列
            entries_data: エントリ情報のリスト

        Returns:
            完全性検証結果
        """
        result = {
            'total_samples': len(X),
            'samples_with_finish_pos': 0,
            'samples_without_finish_pos': 0,
            'finish_pos_coverage': 0.0,
            'is_valid': True,
            'warnings': []
        }

        if entries_data:
            finish_pos_count = sum(1 for e in entries_data if e.get('finish_pos') is not None)
            result['samples_with_finish_pos'] = finish_pos_count
            result['samples_without_finish_pos'] = len(entries_data) - finish_pos_count
            result['finish_pos_coverage'] = (finish_pos_count / len(entries_data) * 100) if entries_data else 0

            if result['finish_pos_coverage'] < 90:
                result['warnings'].append(
                    f"⚠️ 警告: 着順記録のカバレッジが {result['finish_pos_coverage']:.1f}% です（推奨: 95%以上）"
                )
                result['is_valid'] = False

        return result

    @staticmethod
    def print_validation_report(cv_results: Dict[str, Any]) -> None:
        """検証結果をコンソール出力"""
        print("\n" + "="*80)
        print("📊 データリーク検証レポート")
        print("="*80)

        for fold in cv_results['folds']:
            fold_num = fold.get('fold_num', '?')
            print(f"\n【 Fold {fold_num} 】")
            print(f"  訓練期間: {fold['train_date_range'][0]} ～ {fold['train_date_range'][1]}")
            print(f"  テスト期間: {fold['test_date_range'][0]} ～ {fold['test_date_range'][1]}")

            if fold.get('days_gap') is not None:
                print(f"  時間ギャップ: {fold['days_gap']}日")

            print(f"  検証結果: {'✅ OK' if fold['is_valid'] else '❌ NG'}")

            if fold.get('errors'):
                for error in fold['errors']:
                    print(f"    {error}")

            if fold.get('warnings'):
                for warning in fold['warnings']:
                    print(f"    {warning}")

            # クラス分布
            print(f"\n  クラス分布:")
            print(f"    訓練: {fold['class_distribution_train']}")
            print(f"    テスト: {fold['class_distribution_test']}")

        print("\n" + "-"*80)
        print(f"サマリー: {cv_results['summary']['total_valid_folds']}/{cv_results['total_folds']} Fold が有効")
        print(f"全体判定: {'✅ 合格' if cv_results['all_valid'] else '❌ 不合格'}")
        print("="*80 + "\n")
