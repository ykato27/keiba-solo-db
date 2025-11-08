"""
スクレイピングのレート制限と再試行ロジック
JRA側への負荷軽減のため、一定間隔で待機を入れる
"""

import time
import logging
from functools import wraps
from typing import Callable, Any
import requests
from pathlib import Path
from datetime import datetime

logger = logging.getLogger(__name__)

# ========================
# 設定値
# ========================

REQUESTS_PER_MINUTE = 10  # 1分間のリクエスト数制限
MIN_INTERVAL_SECONDS = 60 / REQUESTS_PER_MINUTE  # 最小リクエスト間隔

MAX_RETRIES = 3  # 最大リトライ回数
RETRY_WAIT_SECONDS = 5  # リトライ時の待機秒数

# User-Agent（礼儀正しく、HTMLクローラであることを明示）
USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/120.0.0.0 Safari/537.36"
)

HEADERS = {
    "User-Agent": USER_AGENT,
    "Accept-Language": "ja-JP,ja;q=0.9",
    "Accept-Encoding": "gzip, deflate",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
}

# ========================
# グローバル状態管理
# ========================

_last_request_time = 0.0


def _wait_for_rate_limit():
    """レート制限に基づいて待機"""
    global _last_request_time

    if _last_request_time > 0:
        elapsed = time.time() - _last_request_time
        if elapsed < MIN_INTERVAL_SECONDS:
            wait_time = MIN_INTERVAL_SECONDS - elapsed
            logger.info(f"レート制限: {wait_time:.1f}秒待機")
            time.sleep(wait_time)

    _last_request_time = time.time()


def _save_error_log(url: str, html: str, error: str):
    """エラー発生時のHTMLとURLをログ保存"""
    log_dir = Path("data/logs")
    log_dir.mkdir(parents=True, exist_ok=True)

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

    # URL ログ
    with open(log_dir / f"error_urls_{timestamp}.txt", "a", encoding="utf-8") as f:
        f.write(f"{url}\n{error}\n\n")

    # HTML フラグメント ログ
    with open(log_dir / f"error_html_{timestamp}.html", "a", encoding="utf-8") as f:
        f.write(f"<!-- {url} -->\n{html[:2000]}\n\n")

    logger.error(f"エラーログを保存: {log_dir}")


# ========================
# デコレータ
# ========================


def with_rate_limit_and_retry(func: Callable) -> Callable:
    """レート制限と自動リトライを適用するデコレータ"""

    @wraps(func)
    def wrapper(*args: Any, **kwargs: Any) -> Any:
        _wait_for_rate_limit()

        for attempt in range(MAX_RETRIES):
            try:
                logger.info(f"{func.__name__} を実行中... (試行 {attempt + 1}/{MAX_RETRIES})")
                return func(*args, **kwargs)
            except (requests.RequestException, Exception) as e:
                logger.warning(f"失敗 (試行 {attempt + 1}): {e}")

                if attempt < MAX_RETRIES - 1:
                    logger.info(f"{RETRY_WAIT_SECONDS}秒待機して再試行...")
                    time.sleep(RETRY_WAIT_SECONDS)
                else:
                    logger.error(f"最大リトライ回数に達しました: {func.__name__}")
                    raise

    return wrapper


# ========================
# HTTP リクエスト関数
# ========================


def fetch_url(url: str, timeout: int = 30) -> str:
    """URLを取得してテキストを返す

    Args:
        url: 取得するURL
        timeout: タイムアウト秒数

    Returns:
        HTML文字列

    Raises:
        requests.RequestException: リクエスト失敗時
    """
    _wait_for_rate_limit()

    logger.info(f"Fetching: {url}")

    response = requests.get(
        url,
        headers=HEADERS,
        timeout=timeout,
    )
    response.raise_for_status()

    # エンコーディング修正（JRA側がShift-JISの可能性がある）
    if response.encoding is None or response.encoding.lower() == "iso-8859-1":
        # Content-Typeから charset を抽出
        content_type = response.headers.get("content-type", "")
        if "charset" in content_type:
            charset = content_type.split("charset=")[-1].strip(";")
            response.encoding = charset
        else:
            # デフォルトでUTF-8を試す
            try:
                response.encoding = "utf-8"
                response.text  # テスト
            except UnicodeDecodeError:
                response.encoding = "shift_jis"

    logger.info(f"取得完了: {len(response.text)} 文字")
    return response.text


@with_rate_limit_and_retry
def fetch_url_with_retry(url: str, timeout: int = 30) -> str:
    """レート制限と再試行付きでURLを取得

    Args:
        url: 取得するURL
        timeout: タイムアウト秒数

    Returns:
        HTML文字列
    """
    return fetch_url(url, timeout)


def reset_rate_limit():
    """レート制限カウンタをリセット（テスト用）"""
    global _last_request_time
    _last_request_time = 0.0
