"""
バックテスト機能
過去のレースで予測を実行し、的中率を計測
"""

import numpy as np
from typing import Dict, List, Tuple, Optional
from datetime import datetime, timedelta
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from app import db, queries, prediction_model_lightgbm as pml


class BacktestRunner:
    """バックテスト実行エンジン"""

    def __init__(self, model):
        self.model = model
        self.results = []

    def run_backtest(
        self,
        start_date: str = None,
        end_date: str = None,
        sample_races: int = None,
    ) -> Dict:
        """
        指定期間のレースでバックテストを実行

        Args:
            start_date: 開始日 (YYYY-MM-DD)
            end_date: 終了日 (YYYY-MM-DD)
            sample_races: サンプルレース数（Noneの場合は全レース）

        Returns:
            バックテスト結果
        """
        results = {
            "total_races": 0,
            "total_predictions": 0,
            "win_hits": 0,  # 1着予測的中
            "win_accuracy": 0,
            "place_hits": 0,  # 2-3着予測的中
            "place_accuracy": 0,
            "race_details": [],
            "date_range": f"{start_date} ～ {end_date}",
        }

        try:
            conn = db.get_connection()
            cursor = conn.cursor()

            # 期間内のレースを取得
            if start_date and end_date:
                query = """
                    SELECT race_id, race_date, distance_m, surface, course
                    FROM races
                    WHERE race_date BETWEEN ? AND ?
                    ORDER BY race_date ASC
                """
                cursor.execute(query, (start_date, end_date))
            else:
                query = """
                    SELECT race_id, race_date, distance_m, surface, course
                    FROM races
                    ORDER BY race_date ASC
                """
                cursor.execute(query)

            all_races = cursor.fetchall()

            if sample_races and sample_races < len(all_races):
                # ランダムサンプリング（実装が複雑になるため、最後のN個を使用）
                races = all_races[-sample_races:]
            else:
                races = all_races

            results["total_races"] = len(races)

            # 各レースで予測実行
            for race_idx, race in enumerate(races):
                race_id, race_date, distance, surface, course = race

                # このレースの出走馬を取得
                entries = queries.get_race_entries_with_metrics(race_id)

                if not entries or len(entries) < 2:
                    continue

                horse_ids = [e["horse_id"] for e in entries if e["horse_id"]]
                if not horse_ids:
                    continue

                # レース情報
                race_info = {
                    "distance_m": distance,
                    "surface": surface,
                }

                try:
                    # 予測実行
                    prediction_results = self.model.predict_race_order(
                        horse_ids, race_info=race_info
                    )

                    if "predictions" not in prediction_results:
                        continue

                    predictions = prediction_results["predictions"]
                    results["total_predictions"] += len(predictions)

                    # 実際の着順と比較
                    race_detail = {
                        "race_id": race_id,
                        "race_date": race_date,
                        "course": course,
                        "distance_m": distance,
                        "predictions": [],
                        "hits": [],
                    }

                    for rank, pred in enumerate(predictions, 1):
                        horse_id = pred["horse_id"]
                        horse_name = pred["horse_name"]

                        # 実際の着順を取得
                        actual_entry = next((e for e in entries if e["horse_id"] == horse_id), None)

                        if not actual_entry:
                            continue

                        actual_finish = actual_entry.get("finish_pos")

                        if actual_finish is None or actual_finish <= 0:
                            # 着順なし（未出走など）
                            continue

                        # 的中判定
                        is_win_hit = actual_finish == 1
                        is_place_hit = actual_finish in (1, 2, 3)

                        if is_win_hit:
                            results["win_hits"] += 1

                        if is_place_hit:
                            results["place_hits"] += 1

                        race_detail["predictions"].append(
                            {
                                "rank": rank,
                                "horse_name": horse_name,
                                "predicted_win_prob": pred["win_probability"],
                                "actual_finish": actual_finish,
                            }
                        )

                        race_detail["hits"].append(
                            {
                                "horse_name": horse_name,
                                "is_win_hit": is_win_hit,
                                "is_place_hit": is_place_hit,
                                "predicted_rank": rank,
                                "actual_finish": actual_finish,
                            }
                        )

                    if race_detail["hits"]:
                        results["race_details"].append(race_detail)

                except Exception as e:
                    print(f"レース {race_id} でのバックテスト失敗: {e}")
                    continue

            conn.close()

            # 精度計算
            if results["total_predictions"] > 0:
                results["win_accuracy"] = results["win_hits"] / results["total_predictions"] * 100
                results["place_accuracy"] = (
                    results["place_hits"] / results["total_predictions"] * 100
                )

            return results

        except Exception as e:
            print(f"バックテスト実行エラー: {e}")
            import traceback

            traceback.print_exc()
            return results

    def calculate_expected_value(
        self,
        backtest_results: Dict,
        assumed_odds_win: float = 5.0,
        assumed_odds_place: float = 2.0,
    ) -> Dict:
        """
        期待値を計算

        Args:
            backtest_results: バックテスト結果
            assumed_odds_win: 仮定する1着オッズ
            assumed_odds_place: 仮定する複勝オッズ

        Returns:
            期待値情報
        """
        total_predictions = backtest_results["total_predictions"]
        win_hits = backtest_results["win_hits"]
        place_hits = backtest_results["place_hits"]

        if total_predictions == 0:
            return {"error": "予測データがありません"}

        # 1着予測の期待値
        win_win_rate = win_hits / total_predictions
        win_ev = win_win_rate * assumed_odds_win - 1.0  # -1は1単位の賭け金

        # 複勝予測の期待値
        place_hit_rate = place_hits / total_predictions
        place_ev = place_hit_rate * assumed_odds_place - 1.0

        return {
            "win_win_rate": win_win_rate,
            "win_assumed_odds": assumed_odds_win,
            "win_expected_value": win_ev,
            "place_hit_rate": place_hit_rate,
            "place_assumed_odds": assumed_odds_place,
            "place_expected_value": place_ev,
            "recommendation": (
                "👍 期待値が正" if (win_ev > 0 or place_ev > 0) else "❌ 期待値が負（購入非推奨）"
            ),
        }


def get_backtest_runner() -> BacktestRunner:
    """バックテストランナーを取得"""
    model = pml.get_advanced_prediction_model()
    return BacktestRunner(model)
