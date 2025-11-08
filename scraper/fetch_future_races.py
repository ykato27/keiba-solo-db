"""
将来のレース情報を取得
今週末、来週末などの未来のレース日程と出走馬情報を収集
"""

import logging
import re
from typing import List, Dict, Any, Optional
from datetime import datetime, timedelta
from pathlib import Path
import json
import time
import random

from bs4 import BeautifulSoup

from .rate_limit import fetch_url_with_retry
from .selectors import BASE_URL

logger = logging.getLogger(__name__)

# ログディレクトリ
LOG_DIR = Path("data/logs")


def fetch_upcoming_races(days_ahead: int = 14, use_mock: bool = False) -> List[Dict[str, Any]]:
    """
    将来のレース情報を取得（今日から指定日数先まで）

    Args:
        days_ahead: 何日先までのレースを取得するか（デフォルト14日）
        use_mock: テスト用モックデータを使用するか

    Returns:
        レース情報リスト: [
            {
                'race_date': 'YYYY-MM-DD',
                'course': '東京',
                'race_no': 1,
                'distance_m': 2000,
                'surface': '芝',
                'title': 'レース名',
                'race_id': 'YYYYMMMDDCCCC',
            },
            ...
        ]
    """
    LOG_DIR.mkdir(parents=True, exist_ok=True)

    all_races = []

    try:
        # テスト用モックデータ（JRA側の403回避）
        if use_mock:
            logger.warning("⚠️ モックデータモードで実行中（本番データではありません）")
            races = _generate_mock_races(days_ahead=days_ahead)
            return races

        # JRA公式サイトのカレンダーエンドポイントを試す（複数の候補）
        urls_to_try = [
            f"{BASE_URL}/keiba/schedule/",  # スケジュール
            f"{BASE_URL}/keiba/",  # トップページ
            f"{BASE_URL}/keiba/latest/",  # 最新情報
        ]

        for url in urls_to_try:
            try:
                logger.info(f"将来レース情報取得開始: {url}")
                html = fetch_url_with_retry(url)
                races = _parse_upcoming_races(html, days_ahead=days_ahead)

                if races:
                    all_races.extend(races)
                    logger.info(f"取得したレース数: {len(races)}")
                    break
                else:
                    logger.warning(f"URLからレース情報を抽出できませんでした: {url}")

            except Exception as e:
                logger.warning(f"URL取得失敗 {url}: {e}")
                continue

        if not all_races:
            logger.warning("すべてのURLでレース取得に失敗。モックデータで代替します")
            all_races = _generate_mock_races(days_ahead=days_ahead)

        # ログ保存
        log_file = LOG_DIR / f"upcoming_races_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        with open(log_file, "w", encoding="utf-8") as f:
            json.dump(all_races, f, ensure_ascii=False, indent=2)
        logger.info(f"ログを保存: {log_file}")

        return all_races

    except Exception as e:
        logger.error(f"将来レース情報の取得に失敗: {e}")
        logger.warning("モックデータで代替します")
        return _generate_mock_races(days_ahead=days_ahead)


def fetch_race_card_for_future(race_id: str) -> Dict[str, Any]:
    """
    将来のレースの出馬表を取得

    Args:
        race_id: レースID（例: 202501010101）

    Returns:
        レース情報と出走馬リスト
    """
    try:
        # race_id から URL を構築
        # 例: https://www.jra.go.jp/keiba/race/202501010101/
        url = f"{BASE_URL}/keiba/race/{race_id}/"

        logger.info(f"将来レースの出馬表取得: {url}")
        html = fetch_url_with_retry(url)

        race_info = _parse_future_race_card(html, race_id)
        logger.info(f"出走馬数: {len(race_info.get('entries', []))}")

        return race_info

    except Exception as e:
        logger.error(f"出馬表取得エラー (race_id={race_id}): {e}")
        return {
            "race_id": race_id,
            "entries": [],
            "error": str(e),
        }


def fetch_multiple_race_cards(race_ids: List[str]) -> List[Dict[str, Any]]:
    """
    複数のレースの出馬表を取得

    Args:
        race_ids: レースIDのリスト

    Returns:
        レース情報リスト
    """
    all_races = []

    for race_id in race_ids:
        logger.info(f"出馬表取得: {race_id}")
        race_info = fetch_race_card_for_future(race_id)
        all_races.append(race_info)

        # レート制限のため少し待機
        time.sleep(1)

    # ログ保存
    log_file = LOG_DIR / f"race_cards_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    with open(log_file, "w", encoding="utf-8") as f:
        json.dump(all_races, f, ensure_ascii=False, indent=2)
    logger.info(f"出馬表ログを保存: {log_file}")

    return all_races


def _parse_upcoming_races(html: str, days_ahead: int = 14) -> List[Dict[str, Any]]:
    """
    将来レース情報をHTMLからパース

    Args:
        html: JRAサイトのHTML
        days_ahead: 何日先までのレースを対象とするか

    Returns:
        レース情報リスト
    """
    races = []

    try:
        soup = BeautifulSoup(html, "lxml")

        # JRAサイトのセレクタ候補（複数用意して堅牢性向上）
        # JRAサイトの構造変更に対応するため、複数のセレクタパターンを試行
        race_links = []
        selector_candidates = [
            lambda s: s.find_all("a", href=re.compile(r"/keiba/race/\d{12}/")),  # 標準セレクタ
            lambda s: s.find_all("a", href=re.compile(r"/keiba/entry.*\d{12}")),  # 代替セレクタ1
            lambda s: s.find_all("a", href=re.compile(r"/keiba.*race.*\d{12}")),  # 代替セレクタ2
        ]

        for i, selector_func in enumerate(selector_candidates):
            try:
                race_links = selector_func(soup)
                if race_links:
                    logger.info(f"セレクタ #{i} 成功: {len(race_links)}件のリンク取得")
                    break
            except Exception as e:
                logger.debug(f"セレクタ #{i} 失敗: {e}")
                continue

        if not race_links:
            logger.warning("いずれのセレクタもレース情報を抽出できませんでした")
            logger.debug(f"HTML先頭500文字:\n{html[:500]}")
            return races

        for link in race_links:
            try:
                href = link.get("href", "")

                # URLからrace_idを抽出（複数パターンに対応）
                race_id = None
                race_id_patterns = [
                    r"/keiba/race/(\d{12})/",  # 標準: /keiba/race/202501010101/
                    r"race_id[=?](\d{12})",  # 代替: race_id=202501010101 or race_id?202501010101
                    r"/(\d{12})[/?]",  # 広いパターン: /202501010101/
                ]

                for pattern in race_id_patterns:
                    match = re.search(pattern, href)
                    if match:
                        race_id = match.group(1)
                        break

                if not race_id:
                    logger.debug(f"race_id抽出失敗: {href}")
                    continue

                # race_idから日付を抽出
                year = int(race_id[0:4])
                month = int(race_id[4:6])
                day = int(race_id[6:8])

                try:
                    race_date = datetime(year, month, day).date()
                except ValueError:
                    logger.warning(f"Invalid date in race_id: {race_id}")
                    continue

                # 日数チェック
                days_from_today = (race_date - datetime.now().date()).days
                if days_from_today < 0 or days_from_today > days_ahead:
                    continue

                # コース情報はリンクテキストから抽出
                title = link.get_text(strip=True)

                races.append(
                    {
                        "race_id": race_id,
                        "race_date": str(race_date),
                        "title": title,
                        "url": href,
                        "days_from_today": days_from_today,
                    }
                )

            except Exception as e:
                logger.warning(f"レース情報パース失敗: {e}")
                continue

        return races

    except Exception as e:
        logger.error(f"将来レース情報パース失敗: {e}")
        return races


def _parse_future_race_card(html: str, race_id: str) -> Dict[str, Any]:
    """
    将来レースの出馬表HTMLをパース

    Args:
        html: レースページのHTML
        race_id: レースID

    Returns:
        レース情報と出走馬リスト
    """
    race_info = {
        "race_id": race_id,
        "entries": [],
        "parsed_at": datetime.now().isoformat(),
    }

    try:
        soup = BeautifulSoup(html, "lxml")

        # 出馬表テーブルを探す
        # JRAサイトの構造に合わせてセレクタを調整
        tables = soup.find_all("table")

        for table in tables:
            rows = table.find_all("tr")

            for row in rows:
                cells = row.find_all("td")

                # 最小限のセル数チェック（枠番、馬番は最低限必要）
                if len(cells) < 3:
                    continue

                try:
                    entry = _parse_entry_row(cells)
                    if entry:
                        race_info["entries"].append(entry)
                except Exception as e:
                    logger.warning(f"エントリ行パース失敗: {e}")
                    continue

        logger.info(f"レース {race_id} から {len(race_info['entries'])} 頭を抽出")

    except Exception as e:
        logger.error(f"出馬表パース失敗 (race_id={race_id}): {e}")

    return race_info


def _parse_entry_row(cells: List) -> Optional[Dict[str, Any]]:
    """
    出走馬情報の行をパース

    Args:
        cells: テーブルセルのリスト

    Returns:
        出走馬情報、またはNone
    """
    try:
        entry = {}

        # セル数に応じて柔軟にパース
        if len(cells) >= 1:
            entry["frame_no"] = _safe_int(cells[0].text)

        if len(cells) >= 2:
            entry["horse_no"] = _safe_int(cells[1].text)

        if len(cells) >= 3:
            entry["horse_name"] = cells[2].text.strip()

        if len(cells) >= 4:
            entry["jockey_name"] = cells[3].text.strip()

        if len(cells) >= 5:
            entry["trainer_name"] = cells[4].text.strip()

        if len(cells) >= 6:
            entry["age"] = _safe_int(cells[5].text)

        if len(cells) >= 7:
            entry["weight_carried"] = _safe_float(cells[6].text)

        if len(cells) >= 8:
            entry["odds"] = _safe_float(cells[7].text)

        if len(cells) >= 9:
            entry["popularity"] = _safe_int(cells[8].text)

        # 必須フィールドをチェック
        if entry.get("horse_name") and entry.get("frame_no") is not None:
            return entry
        else:
            return None

    except Exception as e:
        logger.warning(f"エントリ行パース失敗: {e}")
        return None


def _safe_int(value: str) -> Optional[int]:
    """安全に整数変換"""
    try:
        return int(value.strip())
    except (ValueError, AttributeError):
        return None


def _safe_float(value: str) -> Optional[float]:
    """安全に浮動小数点変換"""
    try:
        return float(value.strip())
    except (ValueError, AttributeError):
        return None


def _generate_mock_races(days_ahead: int = 14) -> List[Dict[str, Any]]:
    """
    テスト用モックレースデータを生成
    JRA公式サイトへのアクセス不可時の代替

    Args:
        days_ahead: 何日先までのレースを生成するか

    Returns:
        モックレース情報リスト
    """
    mock_races = []

    courses = ["東京", "中山", "阪神", "京都", "小倉", "新潟"]
    surfaces = ["芝", "ダート"]
    distances = [1200, 1400, 1600, 1800, 2000, 2200, 2400, 2800]

    today = datetime.now().date()

    # 週末（金土日）を中心にレースを生成
    for days_offset in range(1, days_ahead + 1):
        race_date = today + timedelta(days=days_offset)
        weekday = race_date.weekday()

        # 日曜日 (6) のみレースを生成
        if weekday != 6:
            continue

        # 1日に2-4開催場
        num_courses = min(random.randint(2, 4), len(courses))
        selected_courses = random.sample(courses, num_courses)

        for course in selected_courses:
            # 各開催場で11-12レース
            num_races = random.randint(11, 12)

            for race_no in range(1, num_races + 1):
                # race_id を生成: YYYYMMDDHHMM
                race_id = (
                    f"{race_date.year:04d}"
                    f"{race_date.month:02d}"
                    f"{race_date.day:02d}"
                    f"{race_no:04d}"
                )

                mock_races.append(
                    {
                        "race_id": race_id,
                        "race_date": str(race_date),
                        "course": course,
                        "race_no": race_no,
                        "distance_m": random.choice(distances),
                        "surface": random.choice(surfaces),
                        "title": f"{course}{race_no}R",
                        "days_from_today": days_offset,
                        "is_mock": True,  # モックデータであることを明示
                    }
                )

    logger.info(f"モックレースデータを生成: {len(mock_races)} 件")
    return mock_races


if __name__ == "__main__":
    import argparse

    logging.basicConfig(level=logging.INFO)

    parser = argparse.ArgumentParser(description="将来のレース情報を取得")
    parser.add_argument("--days", type=int, default=14, help="何日先までを取得するか")
    parser.add_argument("--race-id", type=str, help="特定のレースIDの出馬表を取得")

    args = parser.parse_args()

    if args.race_id:
        # 単一レースの出馬表を取得
        race_card = fetch_race_card_for_future(args.race_id)
        print(f"取得したレース: {args.race_id}")
        print(f"出走馬数: {len(race_card.get('entries', []))}")
    else:
        # 将来のレース一覧を取得
        upcoming_races = fetch_upcoming_races(days_ahead=args.days)
        print(f"取得したレース数: {len(upcoming_races)}")
        for race in upcoming_races[:5]:
            print(f"  {race.get('race_date')} - {race.get('title')} (ID: {race.get('race_id')})")
