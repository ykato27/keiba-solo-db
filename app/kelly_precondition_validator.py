"""
Kelly基準の前提条件検証モジュール
期待値がプラスであることを厳密にチェック

Kelly基準が有効であるための必須条件:
  1. 期待値 > 0 （これが最重要）
  2. 勝つ確率が有効 (0 < p < 1)
  3. オッズが有効 (odds > 1)
  4. 確率の信頼度が高い（オプション）
"""

import numpy as np
from typing import Dict, List, Tuple, Any, Optional
from dataclasses import dataclass


@dataclass
class KellyPreconditionResult:
    """Kelly基準前提条件チェック結果"""
    horse_name: str
    win_probability: float
    expected_odds: float
    expected_value: float
    expected_value_pct: float
    kelly_valid: bool
    errors: List[str]
    warnings: List[str]
    recommendations: List[str]


class KellyPreconditionValidator:
    """Kelly基準の前提条件検証エンジン"""

    # Kelly基準が無条件で有効な最小期待値
    MIN_POSITIVE_EV = 0.01  # 1%以上の正の期待値を要求

    @staticmethod
    def validate_single_bet(
        horse_name: str,
        win_probability: float,
        expected_odds: float,
        min_ev_threshold: float = 0.01
    ) -> KellyPreconditionResult:
        """
        単一の馬の Kelly 前提条件をチェック

        Args:
            horse_name: 馬の名前
            win_probability: 勝つ確率 (0-1)
            expected_odds: 期待オッズ（配当倍率）
            min_ev_threshold: 最小期待値閾値（デフォルト 1%）

        Returns:
            チェック結果
        """
        result = KellyPreconditionResult(
            horse_name=horse_name,
            win_probability=win_probability,
            expected_odds=expected_odds,
            expected_value=0.0,
            expected_value_pct=0.0,
            kelly_valid=True,
            errors=[],
            warnings=[],
            recommendations=[]
        )

        # 1. 勝つ確率の妥当性チェック
        if win_probability <= 0:
            result.errors.append(f"❌ 勝つ確率が0以下です（{win_probability}）")
            result.kelly_valid = False
        elif win_probability >= 1:
            result.errors.append(f"❌ 勝つ確率が1以上です（{win_probability}）")
            result.kelly_valid = False
        elif win_probability < 0.01:
            result.warnings.append(
                f"⚠️ 警告: 勝つ確率が非常に低い（{win_probability:.2%}）。予測信頼度の確認推奨"
            )

        # 2. オッズの妥当性チェック
        if expected_odds <= 1:
            result.errors.append(
                f"❌ オッズが無効です（{expected_odds}）。オッズは1より大きい必要があります"
            )
            result.kelly_valid = False
        elif expected_odds <= 1.1:
            result.warnings.append(
                f"⚠️ 警告: オッズが低すぎます（{expected_odds}）。リターンが限定的"
            )
        elif expected_odds > 100:
            result.warnings.append(
                f"⚠️ 警告: オッズが非常に高い（{expected_odds}）。データ入力エラーの可能性を確認"
            )

        # 3. 期待値の計算（最も重要）
        expected_value = (expected_odds - 1) * win_probability - (1 - win_probability)
        expected_value_pct = expected_value * 100

        result.expected_value = expected_value
        result.expected_value_pct = expected_value_pct

        # 4. 期待値の評価（Kelly基準の必須条件）
        if expected_value < 0:
            result.errors.append(
                f"❌ 期待値がマイナスです（{expected_value_pct:.2f}%）"
            )
            result.kelly_valid = False
            result.recommendations.append(
                "この馬には賭けるべきではありません（負の期待値）"
            )
        elif expected_value == 0:
            result.errors.append(
                "❌ 期待値がゼロです（ブレークイーブン）"
            )
            result.kelly_valid = False
            result.recommendations.append(
                "この馬には賭けるべきではありません（利益なし）"
            )
        elif 0 < expected_value < min_ev_threshold:
            result.warnings.append(
                f"⚠️ 警告: 期待値が非常に小さい（{expected_value_pct:.3f}%）。"
                f"リスク・リターン比がフェアではない可能性"
            )
            result.recommendations.append(
                "より高い期待値の馬を探すか、このベットを避けることを検討"
            )
        else:
            # 期待値が十分にプラス
            result.recommendations.append(
                f"✅ Kelly基準を適用可能（期待値: {expected_value_pct:.2f}%）"
            )

        return result

    @staticmethod
    def validate_portfolio(
        predictions: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """
        複数の馬の Kelly 前提条件を一括チェック

        Args:
            predictions: 馬の予測情報リスト
              [
                {
                  'horse_name': '馬名',
                  'win_probability': 勝つ確率,
                  'expected_odds': 期待オッズ,
                },
                ...
              ]

        Returns:
            検証結果の辞書
        """
        results = {
            'total_horses': len(predictions),
            'valid_horses': 0,
            'invalid_horses': 0,
            'warning_horses': 0,
            'horses': [],
            'portfolio_status': '',
            'summary': {}
        }

        valid_predictions = []

        for pred in predictions:
            horse_name = pred.get('horse_name', '不明')
            win_prob = float(pred.get('win_probability', 0))
            odds = float(pred.get('expected_odds', 1.0))

            # 個別検証
            validation = KellyPreconditionValidator.validate_single_bet(
                horse_name, win_prob, odds
            )

            results['horses'].append({
                'horse_name': validation.horse_name,
                'win_probability': validation.win_probability,
                'expected_odds': validation.expected_odds,
                'expected_value_pct': validation.expected_value_pct,
                'kelly_valid': validation.kelly_valid,
                'errors': validation.errors,
                'warnings': validation.warnings,
            })

            if validation.kelly_valid:
                results['valid_horses'] += 1
                valid_predictions.append(pred)
            else:
                results['invalid_horses'] += 1

            if validation.warnings:
                results['warning_horses'] += 1

        # ポートフォリオレベルの分析
        if results['valid_horses'] == 0:
            results['portfolio_status'] = (
                f"❌ 致命的: 有効な予測がありません（{results['total_horses']}頭中0頭）。"
                f"賭けるべきではありません"
            )
        elif results['valid_horses'] < results['total_horses'] * 0.3:
            results['portfolio_status'] = (
                f"⚠️ 警告: 有効な予測が少ない（{results['valid_horses']}/{results['total_horses']}）。"
                f"ポートフォリオが分散不足の可能性"
            )
        else:
            results['portfolio_status'] = (
                f"✅ OK: {results['valid_horses']}/{results['total_horses']}頭が Kelly 基準を満たします"
            )

        # 期待値の統計
        if valid_predictions:
            evs = [
                (pred.get('expected_odds', 1) - 1) * pred.get('win_probability', 0) -
                (1 - pred.get('win_probability', 0))
                for pred in valid_predictions
            ]
            results['summary'] = {
                'valid_predictions_count': len(valid_predictions),
                'mean_expected_value_pct': float(np.mean(evs) * 100),
                'median_expected_value_pct': float(np.median(evs) * 100),
                'min_expected_value_pct': float(np.min(evs) * 100),
                'max_expected_value_pct': float(np.max(evs) * 100),
                'total_expected_roi_pct': float(np.sum(evs) * 100),
            }

        return results

    @staticmethod
    def filter_positive_ev_predictions(
        predictions: List[Dict[str, Any]],
        min_ev_threshold: float = 0.01
    ) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
        """
        期待値がプラスの予測のみをフィルタリング

        Args:
            predictions: 馬の予測情報リスト
            min_ev_threshold: 最小期待値閾値

        Returns:
            (プラスEVの予測, マイナスEVの予測)
        """
        positive_ev = []
        negative_ev = []

        for pred in predictions:
            win_prob = float(pred.get('win_probability', 0))
            odds = float(pred.get('expected_odds', 1.0))

            ev = (odds - 1) * win_prob - (1 - win_prob)

            if ev > min_ev_threshold:
                positive_ev.append(pred)
            else:
                negative_ev.append(pred)

        return positive_ev, negative_ev

    @staticmethod
    def print_validation_report(results: Dict[str, Any]) -> None:
        """検証結果をコンソール出力"""
        print("\n" + "="*80)
        print("📊 Kelly基準 前提条件検証レポート")
        print("="*80)

        print(f"\n【全体統計】")
        print(f"  総馬数: {results['total_horses']}")
        print(f"  ✅ 有効: {results['valid_horses']}")
        print(f"  ❌ 無効: {results['invalid_horses']}")
        print(f"  ⚠️ 警告: {results['warning_horses']}")

        print(f"\n【ポートフォリオ判定】")
        print(f"  {results['portfolio_status']}")

        if results.get('summary'):
            print(f"\n【期待値統計（有効な予測のみ）】")
            summary = results['summary']
            print(f"  平均期待値: {summary.get('mean_expected_value_pct', 0):.2f}%")
            print(f"  中央値期待値: {summary.get('median_expected_value_pct', 0):.2f}%")
            print(f"  最小期待値: {summary.get('min_expected_value_pct', 0):.2f}%")
            print(f"  最大期待値: {summary.get('max_expected_value_pct', 0):.2f}%")
            print(f"  総合期待ROI: {summary.get('total_expected_roi_pct', 0):.2f}%")

        print(f"\n【馬ごとの詳細】")
        for horse in results['horses'][:10]:  # 最初の10頭のみ表示
            status = "✅" if horse['kelly_valid'] else "❌"
            print(f"\n  {status} {horse['horse_name']}")
            print(f"     確率: {horse['win_probability']:.2%}, オッズ: {horse['expected_odds']:.2f}")
            print(f"     期待値: {horse['expected_value_pct']:.2f}%")
            if horse['errors']:
                for error in horse['errors']:
                    print(f"     {error}")

        print("\n" + "="*80 + "\n")
