"""
レースの出馬表を取得
各レースの出走馬情報（枠番、馬名、騎手、調教師など）を収集
"""

import logging
from typing import List, Dict, Any
from pathlib import Path
import json

from bs4 import BeautifulSoup

from .rate_limit import fetch_url_with_retry
from .selectors import ENTRY_TABLE_ROWS

logger = logging.getLogger(__name__)

LOG_DIR = Path("data/logs")


def fetch_race_cards(race_ids: List[str]) -> List[Dict[str, Any]]:
    """複数レースの出馬表を取得

    Args:
        race_ids: レースIDのリスト

    Returns:
        出走馬情報リスト
    """
    LOG_DIR.mkdir(parents=True, exist_ok=True)

    all_entries = []

    for race_id in race_ids:
        logger.info(f"出馬表取得: {race_id}")
        entries = fetch_single_race_card(race_id)
        all_entries.extend(entries)

    # ログ保存
    log_file = LOG_DIR / f"cards_{len(race_ids)}.json"
    with open(log_file, "w", encoding="utf-8") as f:
        json.dump(all_entries, f, ensure_ascii=False, indent=2)
    logger.info(f"出馬表ログを保存: {log_file}")

    return all_entries


def fetch_single_race_card(race_id: str) -> List[Dict[str, Any]]:
    """単一レースの出馬表を取得

    Args:
        race_id: レースID (例: 202401010101)

    Returns:
        出走馬情報リスト
    """
    entries = []

    # race_id から URL を構築
    # 例: https://www.jra.go.jp/keiba/race/202401010101/
    url = f"https://www.jra.go.jp/keiba/race/{race_id}/"

    try:
        logger.info(f"URL: {url}")
        html = fetch_url_with_retry(url)

        entries = _parse_race_card(html, race_id)
        logger.info(f"出走馬数: {len(entries)}")

        return entries

    except Exception as e:
        logger.error(f"出馬表取得エラー (race_id={race_id}): {e}")
        _save_error_log(url, html if 'html' in locals() else "", str(e))
        return entries


def _parse_race_card(html: str, race_id: str) -> List[Dict[str, Any]]:
    """出馬表HTMLをパース

    Args:
        html: レースページのHTML
        race_id: レースID

    Returns:
        出走馬情報リスト
    """
    entries = []

    soup = BeautifulSoup(html, "lxml")

    # 実装に際して調査が必要：
    # - 出馬表テーブルの正確なセレクタ
    # - 各列の対応関係
    # - 馬名、騎手、調教師などのテキスト抽出方法

    # テンプレート実装
    table_rows = soup.select(ENTRY_TABLE_ROWS)

    for row in table_rows:
        try:
            cells = row.find_all("td")
            if len(cells) < 10:
                continue

            entry = {
                "race_id": race_id,
                "frame_no": _safe_int(cells[0].text),
                "horse_no": _safe_int(cells[1].text),
                "horse_name": cells[2].text.strip(),
                "jockey_name": cells[4].text.strip(),
                "trainer_name": cells[5].text.strip(),
                "age": _safe_int(cells[6].text),
                "weight_carried": _safe_float(cells[7].text),
                "odds": _safe_float(cells[8].text),
                "popularity": _safe_int(cells[9].text),
            }

            entries.append(entry)

        except Exception as e:
            logger.warning(f"行のパース失敗: {e}")
            continue

    return entries


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


def _save_error_log(url: str, html: str, error: str):
    """エラーログを保存"""
    LOG_DIR.mkdir(parents=True, exist_ok=True)

    with open(LOG_DIR / "error_urls.txt", "a", encoding="utf-8") as f:
        f.write(f"{url}\n{error}\n\n")


if __name__ == "__main__":
    import argparse

    logging.basicConfig(level=logging.INFO)

    parser = argparse.ArgumentParser(description="競馬レースの出馬表を取得")
    parser.add_argument("--years", nargs="+", type=int, help="対象年度（複数指定可）")
    parser.add_argument("--latest", action="store_true", help="最新の出馬表を取得")

    args = parser.parse_args()

    # テスト実行
    print("fetch_card module loaded")
    # race_ids = []  # 実装時に race_ids を設定
    # entries = fetch_race_cards(race_ids)
    # print(f"取得した出走馬数: {len(entries)}")
