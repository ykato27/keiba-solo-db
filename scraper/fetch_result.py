"""
レースの確定結果を取得
着順、着時間、着差、コーナー順位などの情報を収集
"""

import logging
from typing import List, Dict, Any
from pathlib import Path
import json

from bs4 import BeautifulSoup

from scraper.rate_limit import fetch_url_with_retry
from scraper.selectors import RESULT_TABLE_ROWS

logger = logging.getLogger(__name__)

LOG_DIR = Path("data/logs")


def fetch_race_results(race_ids: List[str]) -> List[Dict[str, Any]]:
    """複数レースの結果を取得

    Args:
        race_ids: レースIDのリスト

    Returns:
        結果情報リスト
    """
    LOG_DIR.mkdir(parents=True, exist_ok=True)

    all_results = []

    for race_id in race_ids:
        logger.info(f"結果取得: {race_id}")
        results = fetch_single_race_result(race_id)
        all_results.extend(results)

    # ログ保存
    log_file = LOG_DIR / f"results_{len(race_ids)}.json"
    with open(log_file, "w", encoding="utf-8") as f:
        json.dump(all_results, f, ensure_ascii=False, indent=2)
    logger.info(f"結果ログを保存: {log_file}")

    return all_results


def fetch_single_race_result(race_id: str) -> List[Dict[str, Any]]:
    """単一レースの結果を取得

    Args:
        race_id: レースID (例: 202401010101)

    Returns:
        結果情報リスト
    """
    results = []

    # race_id から URL を構築
    # 例: https://www.jra.go.jp/keiba/result/202401010101/
    url = f"https://www.jra.go.jp/keiba/result/{race_id}/"

    try:
        logger.info(f"URL: {url}")
        html = fetch_url_with_retry(url)

        results = _parse_race_result(html, race_id)
        logger.info(f"結果数: {len(results)}")

        return results

    except Exception as e:
        logger.error(f"結果取得エラー (race_id={race_id}): {e}")
        _save_error_log(url, html if 'html' in locals() else "", str(e))
        return results


def _parse_race_result(html: str, race_id: str) -> List[Dict[str, Any]]:
    """結果HTMLをパース

    Args:
        html: レース結果ページのHTML
        race_id: レースID

    Returns:
        結果情報リスト
    """
    results = []

    soup = BeautifulSoup(html, "lxml")

    # 実装に際して調査が必要：
    # - 結果テーブルの正確なセレクタ
    # - 各列の対応関係
    # - 着時間、着差などのテキスト抽出方法

    # テンプレート実装
    table_rows = soup.select(RESULT_TABLE_ROWS)

    for row in table_rows:
        try:
            cells = row.find_all("td")
            if len(cells) < 14:
                continue

            result = {
                "race_id": race_id,
                "finish_pos": _safe_int(cells[0].text),
                "frame_no": _safe_int(cells[1].text),
                "horse_no": _safe_int(cells[2].text),
                "horse_name": cells[3].text.strip(),
                "jockey_name": cells[5].text.strip(),
                "trainer_name": cells[6].text.strip(),
                "weight_carried": _safe_float(cells[7].text),
                "odds": _safe_float(cells[8].text),
                "popularity": _safe_int(cells[9].text),
                "finish_time_seconds": _parse_finish_time(cells[10].text),
                "margin": cells[11].text.strip(),
                "corner_order": cells[12].text.strip(),
                "remark": cells[13].text.strip() if len(cells) > 13 else "",
            }

            results.append(result)

        except Exception as e:
            logger.warning(f"結果行のパース失敗: {e}")
            continue

    return results


def _safe_int(value: str) -> int:
    """安全に整数変換"""
    try:
        return int(value.strip())
    except (ValueError, AttributeError):
        return None


def _safe_float(value: str) -> float:
    """安全に浮動小数点変換"""
    try:
        return float(value.strip())
    except (ValueError, AttributeError):
        return None


def _parse_finish_time(time_str: str) -> float:
    """着時間を秒に変換

    形式例: "1:23.4" -> 83.4
    """
    try:
        time_str = time_str.strip()
        if ":" not in time_str:
            return None

        parts = time_str.split(":")
        minutes = int(parts[0])
        seconds = float(parts[1])

        return minutes * 60 + seconds

    except (ValueError, AttributeError):
        return None


def _save_error_log(url: str, html: str, error: str):
    """エラーログを保存"""
    LOG_DIR.mkdir(parents=True, exist_ok=True)

    with open(LOG_DIR / "error_urls.txt", "a", encoding="utf-8") as f:
        f.write(f"{url}\n{error}\n\n")


if __name__ == "__main__":
    import argparse

    logging.basicConfig(level=logging.INFO)

    parser = argparse.ArgumentParser(description="競馬レースの結果を取得")
    parser.add_argument("--years", nargs="+", type=int, help="対象年度（複数指定可）")
    parser.add_argument("--latest", action="store_true", help="最新の結果を取得")

    args = parser.parse_args()

    # テスト実行
    print("fetch_result module loaded")
    # race_ids = []  # 実装時に race_ids を設定
    # results = fetch_race_results(race_ids)
    # print(f"取得した結果数: {len(results)}")
