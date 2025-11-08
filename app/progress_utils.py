"""
進捗表示ユーティリティ
処理時間の推定と進捗の可視化
"""

import time
from datetime import datetime, timedelta


class ProgressTracker:
    """処理進捗を追跡するクラス"""

    def __init__(self, st=None):
        self.st = st
        self.start_time = None
        self.items_processed = 0
        self.total_items = 0

    def start(self, total_items):
        """処理開始"""
        self.start_time = time.time()
        self.total_items = total_items
        self.items_processed = 0

    def update(self, count=1):
        """進捗を更新"""
        self.items_processed += count

    def get_progress_ratio(self):
        """0-1 の進捗率を取得"""
        if self.total_items == 0:
            return 0
        return min(self.items_processed / self.total_items, 1.0)

    def get_elapsed_time(self):
        """経過時間を取得（秒）"""
        if self.start_time is None:
            return 0
        return time.time() - self.start_time

    def get_estimated_remaining_time(self):
        """推定残り時間を取得（秒）"""
        if self.items_processed == 0:
            return None

        elapsed = self.get_elapsed_time()
        avg_time_per_item = elapsed / self.items_processed
        remaining_items = self.total_items - self.items_processed

        if remaining_items <= 0:
            return 0

        return avg_time_per_item * remaining_items

    def format_time(self, seconds):
        """秒を見やすい形式に変換"""
        if seconds is None:
            return "計算中..."

        seconds = int(seconds)
        if seconds < 60:
            return f"{seconds}秒"
        elif seconds < 3600:
            minutes = seconds // 60
            secs = seconds % 60
            return f"{minutes}分 {secs}秒"
        else:
            hours = seconds // 3600
            minutes = (seconds % 3600) // 60
            return f"{hours}時間 {minutes}分"

    def display_progress_with_streamlit(self, st, label="処理中"):
        """Streamlitで進捗を表示"""
        progress_ratio = self.get_progress_ratio()
        elapsed = self.get_elapsed_time()
        remaining = self.get_estimated_remaining_time()

        # プログレスバー
        st.progress(progress_ratio)

        # 詳細情報
        col1, col2, col3 = st.columns(3)

        with col1:
            st.metric("進捗", f"{self.items_processed:,} / {self.total_items:,}")

        with col2:
            st.metric("経過時間", self.format_time(elapsed))

        with col3:
            st.metric("推定残り時間", self.format_time(remaining))


def format_duration(seconds):
    """秒を見やすい形式に変換"""
    if seconds < 60:
        return f"{seconds:.0f}秒"
    elif seconds < 3600:
        minutes = seconds / 60
        return f"{minutes:.1f}分"
    else:
        hours = seconds / 3600
        return f"{hours:.1f}時間"
