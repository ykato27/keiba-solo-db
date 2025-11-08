"""
特徴量診断モジュール
多重共線性、データ品質、特徴量相関を分析

このモジュールは Data Scientist が特徴量エンジニアリングの
品質を検証するためのツール群を提供します。
"""

import numpy as np
import pandas as pd
from typing import Dict, Tuple, List, Optional
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from app import queries


class FeatureDiagnostics:
    """特徴量診断エンジン"""

    @staticmethod
    def calculate_vif(X: np.ndarray, feature_names: List[str]) -> pd.DataFrame:
        """
        VIF（Variance Inflation Factor）を計算

        VIF > 5 の特徴量は高い多重共線性を示す
        VIF > 10 の特徴量は削除推奨

        Args:
            X: 特徴量行列 (n_samples, n_features)
            feature_names: 特徴量名のリスト

        Returns:
            VIF スコア DataFrame
        """
        try:
            from statsmodels.stats.outliers_influence import variance_inflation_factor
        except ImportError:
            return pd.DataFrame(
                {
                    "Feature": feature_names,
                    "VIF": [np.nan] * len(feature_names),
                    "Status": ["statsmodels not installed"] * len(feature_names),
                }
            )

        # NaN と inf を処理
        X_clean = np.nan_to_num(X, nan=0.0, posinf=0.0, neginf=0.0)

        vif_data = []
        for i in range(X_clean.shape[1]):
            try:
                vif = variance_inflation_factor(X_clean, i)
                status = self._vif_status(vif)
                vif_data.append({"Feature": feature_names[i], "VIF": vif, "Status": status})
            except Exception as e:
                vif_data.append(
                    {"Feature": feature_names[i], "VIF": np.nan, "Status": f"Error: {str(e)[:30]}"}
                )

        return pd.DataFrame(vif_data).sort_values("VIF", ascending=False)

    @staticmethod
    def _vif_status(vif: float) -> str:
        """VIF スコアからステータスを判定"""
        if np.isnan(vif) or np.isinf(vif):
            return "⚠️ 計算不可"
        elif vif > 10:
            return "🔴 削除推奨 (VIF > 10)"
        elif vif > 5:
            return "🟡 確認推奨 (VIF > 5)"
        elif vif > 2:
            return "🟢 注意 (VIF > 2)"
        else:
            return "✅ 良好 (VIF <= 2)"

    @staticmethod
    def calculate_correlation_matrix(X: np.ndarray, feature_names: List[str]) -> pd.DataFrame:
        """
        特徴量間の相関行列を計算

        相関係数 > 0.8 の特徴量ペアは高度に相関している

        Args:
            X: 特徴量行列
            feature_names: 特徴量名

        Returns:
            相関行列 DataFrame
        """
        X_clean = np.nan_to_num(X, nan=0.0, posinf=0.0, neginf=0.0)

        corr_matrix = np.corrcoef(X_clean.T)

        return pd.DataFrame(corr_matrix, index=feature_names, columns=feature_names)

    @staticmethod
    def find_highly_correlated_pairs(
        X: np.ndarray, feature_names: List[str], threshold: float = 0.8
    ) -> List[Dict]:
        """
        高度に相関した特徴量ペアを検出

        Args:
            X: 特徴量行列
            feature_names: 特徴量名
            threshold: 相関係数の閾値 (デフォルト 0.8)

        Returns:
            相関ペア情報のリスト
        """
        corr_matrix = FeatureDiagnostics.calculate_correlation_matrix(X, feature_names)

        pairs = []
        for i in range(len(feature_names)):
            for j in range(i + 1, len(feature_names)):
                corr = abs(corr_matrix.iloc[i, j])
                if corr > threshold:
                    pairs.append(
                        {
                            "Feature 1": feature_names[i],
                            "Feature 2": feature_names[j],
                            "Correlation": corr,
                            "Recommendation": self._correlation_recommendation(corr),
                        }
                    )

        return sorted(pairs, key=lambda x: x["Correlation"], reverse=True)

    @staticmethod
    def _correlation_recommendation(corr: float) -> str:
        """相関係数からの推奨を生成"""
        if corr > 0.95:
            return "🔴 どちらか削除"
        elif corr > 0.85:
            return "🟡 関連性確認後、片方削除を検討"
        else:
            return "⚠️ 監視"

    @staticmethod
    def check_feature_variance(X: np.ndarray, feature_names: List[str]) -> pd.DataFrame:
        """
        各特徴量の分散を確認
        分散が極端に小さい特徴量は予測力が弱い

        Args:
            X: 特徴量行列
            feature_names: 特徴量名

        Returns:
            分散情報 DataFrame
        """
        X_clean = np.nan_to_num(X, nan=0.0, posinf=0.0, neginf=0.0)

        variances = np.var(X_clean, axis=0)
        means = np.mean(X_clean, axis=0)

        # Coefficient of Variation
        cv = np.where(means != 0, variances / (means**2), 0)

        variance_data = []
        for i, feature_name in enumerate(feature_names):
            variance_data.append(
                {
                    "Feature": feature_name,
                    "Variance": variances[i],
                    "Mean": means[i],
                    "Std": np.sqrt(variances[i]),
                    "CV": cv[i],
                    "Status": self._variance_status(variances[i]),
                }
            )

        return pd.DataFrame(variance_data).sort_values("Variance", ascending=False)

    @staticmethod
    def _variance_status(variance: float) -> str:
        """分散からのステータスを判定"""
        if variance < 0.001:
            return "🔴 ほぼ定数 (削除推奨)"
        elif variance < 0.01:
            return "🟡 低分散"
        else:
            return "✅ 正常"

    @staticmethod
    def check_missing_values(X: np.ndarray, feature_names: List[str]) -> pd.DataFrame:
        """
        各特徴量の欠損値を確認

        Args:
            X: 特徴量行列（NaN を含む可能性あり）
            feature_names: 特徴量名

        Returns:
            欠損情報 DataFrame
        """
        missing_counts = np.sum(np.isnan(X), axis=0)
        total_samples = X.shape[0]
        missing_pct = (missing_counts / total_samples) * 100

        missing_data = []
        for i, feature_name in enumerate(feature_names):
            missing_data.append(
                {
                    "Feature": feature_name,
                    "Missing Count": int(missing_counts[i]),
                    "Missing %": missing_pct[i],
                    "Status": self._missing_status(missing_pct[i]),
                }
            )

        return pd.DataFrame(missing_data).sort_values("Missing %", ascending=False)

    @staticmethod
    def _missing_status(missing_pct: float) -> str:
        """欠損率からのステータスを判定"""
        if missing_pct > 30:
            return "🔴 削除推奨"
        elif missing_pct > 10:
            return "🟡 補完方法を検討"
        else:
            return "✅ 許容範囲"

    @staticmethod
    def generate_diagnostics_report(
        X: np.ndarray, feature_names: List[str], output_path: Optional[Path] = None
    ) -> Dict:
        """
        包括的な診断レポートを生成

        Args:
            X: 特徴量行列
            feature_names: 特徴量名
            output_path: レポート保存先（オプション）

        Returns:
            診断結果の辞書
        """
        report = {
            "vif_analysis": FeatureDiagnostics.calculate_vif(X, feature_names),
            "correlation_pairs": FeatureDiagnostics.find_highly_correlated_pairs(X, feature_names),
            "variance_analysis": FeatureDiagnostics.check_feature_variance(X, feature_names),
            "missing_analysis": FeatureDiagnostics.check_missing_values(X, feature_names),
            "summary": {
                "total_features": len(feature_names),
                "high_vif_features": len(
                    [
                        f
                        for f in report.get("vif_analysis", [])
                        if "VIF > 10" in str(f.get("Status", ""))
                    ]
                ),
                "high_corr_pairs": len(report.get("correlation_pairs", [])),
            },
        }

        if output_path:
            import json

            with open(output_path, "w") as f:
                json.dump(
                    {k: v for k, v in report.items() if k != "summary"}, f, indent=2, default=str
                )

        return report


# 簡略版の診断関数（Streamlit UI 用）
def diagnose_features_simple(X: np.ndarray, feature_names: List[str]) -> Dict:
    """
    簡略診断（重い計算をスキップ）
    Streamlit UI での使用を想定
    """
    diag = FeatureDiagnostics()

    return {
        "variance": diag.check_feature_variance(X, feature_names),
        "missing": diag.check_missing_values(X, feature_names),
        "correlations": diag.find_highly_correlated_pairs(X, feature_names, threshold=0.85),
    }
