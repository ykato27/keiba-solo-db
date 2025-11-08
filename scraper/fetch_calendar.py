"""
JRAのレース開催カレンダーを取得
年度→月→開催という階層でレース日程を収集
"""

import logging
from typing import List, Dict, Any
from datetime import datetime
from pathlib import Path
import json

from bs4 import BeautifulSoup

from .rate_limit import fetch_url_with_retry
from .selectors import BASE_URL

logger = logging.getLogger(__name__)

# ログディレクトリ
LOG_DIR = Path("data/logs")


def fetch_race_calendar(start_year: int, end_year: int) -> List[Dict[str, Any]]:
    """年度範囲のレース開催情報を取得

    Args:
        start_year: 開始年度 (例: 2019)
        end_year: 終了年度 (例: 2024)

    Returns:
        レース情報リスト: [
            {
                'race_date': 'YYYY-MM-DD',
                'course': '東京',
                'race_no': 1,
                'race_id': '...',
            },
            ...
        ]
    """
    LOG_DIR.mkdir(parents=True, exist_ok=True)

    all_races = []

    for year in range(start_year, end_year + 1):
        logger.info(f"====== 年度 {year} を取得中 ======")
        year_races = _fetch_races_for_year(year)
        all_races.extend(year_races)
        logger.info(f"年度 {year}: {len(year_races)} レース")

    # ログファイルに保存
    log_file = LOG_DIR / f"calendar_{start_year}_{end_year}.json"
    with open(log_file, "w", encoding="utf-8") as f:
        json.dump(all_races, f, ensure_ascii=False, indent=2)
    logger.info(f"カレンダーログを保存: {log_file}")

    return all_races


def _fetch_races_for_year(year: int) -> List[Dict[str, Any]]:
    """指定年度のレース一覧を取得

    実装注：
    JRAサイトの実際の構造に合わせてURLやセレクタを調整が必要
    ここではテンプレート実装
    """
    races = []

    # JRA年度別開催ページの例
    # https://www.jra.go.jp/keiba/2024/ など
    url = f"{BASE_URL}/keiba/{year}/"

    try:
        logger.info(f"URL: {url}")
        html = fetch_url_with_retry(url)

        soup = BeautifulSoup(html, "lxml")

        # 実装に際して調査が必要：
        # - 実際のHTML構造
        # - 開催情報の配置
        # - race_id の取得方法

        # テンプレート実装：
        # 各開催のリンクを抽出し、開催ページを取得
        meeting_links = soup.find_all("a", href=lambda x: x and "kakukai" in x)

        for link in meeting_links:
            meeting_races = _fetch_races_for_meeting(link.get("href"))
            races.extend(meeting_races)

        return races

    except Exception as e:
        logger.error(f"年度 {year} の取得に失敗: {e}")
        return races


def _fetch_races_for_meeting(meeting_url: str) -> List[Dict[str, Any]]:
    """開催ページからレース一覧を取得

    Args:
        meeting_url: 開催ページのURL

    Returns:
        レース情報リスト
    """
    races = []

    try:
        if not meeting_url.startswith("http"):
            meeting_url = f"{BASE_URL}{meeting_url}"

        logger.info(f"開催取得: {meeting_url}")
        html = fetch_url_with_retry(meeting_url)

        soup = BeautifulSoup(html, "lxml")

        # 実装に際して調査が必要：
        # - 開催情報の抽出（日付、開催地）
        # - 各レース情報の抽出

        # テンプレート実装
        # race_no が 1-12 程度のレースを探す
        race_links = soup.find_all("a", href=lambda x: x and "race_id=" in x)

        for link in race_links:
            race_id = _extract_race_id(link.get("href"))
            if race_id:
                races.append(
                    {
                        "race_id": race_id,
                        "url": link.get("href"),
                        "title": link.text.strip(),
                    }
                )

        return races

    except Exception as e:
        logger.error(f"開催取得に失敗: {e}")
        return races


def _extract_race_id(url: str) -> str:
    """URLからrace_idを抽出

    race_id の形式例: 202401010101 (年月日+コース+R)
    """
    import re

    match = re.search(r"race_id[=/]*(\d{12})", url)
    if match:
        return match.group(1)

    return ""


if __name__ == "__main__":
    import argparse

    logging.basicConfig(level=logging.INFO)

    parser = argparse.ArgumentParser(description="JRAレースカレンダーを取得")
    parser.add_argument("--start", type=int, default=2024, help="開始年度")
    parser.add_argument("--end", type=int, default=2024, help="終了年度")

    args = parser.parse_args()

    # テスト実行
    races = fetch_race_calendar(args.start, args.end)
    print(f"取得したレース数: {len(races)}")
