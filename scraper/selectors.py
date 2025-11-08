"""
JRAサイトのHTML構造に対するCSS/XPath選択子を集約管理
HTML構造の変更に対応しやすくするため、ここで一元管理
"""

# ========================
# JRA top page selectors
# ========================

# 年度別の開催一覧ページ
YEAR_LINKS = "a[href*='year=']"  # 年度選択リンク

# 開催一覧ページ
RACE_MEETING_ROWS = "table.race tr"  # 開催行
MEETING_DATE_SELECTOR = "td:nth-child(1)"  # 開催日
MEETING_COURSE_SELECTOR = "td:nth-child(2)"  # 開催場
MEETING_LINK = "a[href*='race_id']"  # レースへのリンク

# ========================
# 出馬表（race card）セレクタ
# ========================

# レース基本情報
RACE_TITLE = "h1, .race-title"
RACE_DATE = "[data-race-date], .race-date"
RACE_COURSE = "[data-course], .course-name"
RACE_NO = "[data-race-no], .race-no"
RACE_DISTANCE = "[data-distance], .distance"
RACE_SURFACE = "[data-surface], .surface"  # 芝/ダート
RACE_GOING = "[data-going], .going"  # 馬場状態
RACE_GRADE = "[data-grade], .grade"  # G1/G2/G3

# 出馬表（エントリーリスト）
ENTRY_TABLE_ROWS = "table.race-entries tbody tr, table.entry-list tbody tr"

# 各エントリーの列
ENTRY_FRAME_NO = "td:nth-child(1)"  # 枠番
ENTRY_HORSE_NO = "td:nth-child(2)"  # 馬番
ENTRY_HORSE_NAME = "td.horse-name a, td:nth-child(3) a"  # 馬名
ENTRY_JOCKEY_NAME = "td.jockey-name, td:nth-child(5)"  # 騎手
ENTRY_TRAINER_NAME = "td.trainer-name, td:nth-child(6)"  # 調教師
ENTRY_AGE = "td.age, td:nth-child(7)"  # 年齢
ENTRY_WEIGHT = "td.weight, td:nth-child(8)"  # 斤量
ENTRY_ODDS = "td.odds, td:nth-child(9)"  # オッズ
ENTRY_POPULARITY = "td.popularity, td:nth-child(10)"  # 人気

# ========================
# 結果（race result）セレクタ
# ========================

# 結果テーブル
RESULT_TABLE_ROWS = "table.race-result tbody tr, table.result-list tbody tr"

# 各結果行の列
RESULT_FINISH_POS = "td.finish-pos, td:nth-child(1)"  # 着順
RESULT_FRAME_NO = "td.frame-no, td:nth-child(2)"  # 枠番
RESULT_HORSE_NO = "td.horse-no, td:nth-child(3)"  # 馬番
RESULT_HORSE_NAME = "td.horse-name a, td:nth-child(4) a"  # 馬名
RESULT_JOCKEY_NAME = "td.jockey-name, td:nth-child(6)"  # 騎手
RESULT_TRAINER_NAME = "td.trainer-name, td:nth-child(7)"  # 調教師
RESULT_WEIGHT = "td.weight, td:nth-child(8)"  # 斤量
RESULT_ODDS = "td.odds, td:nth-child(9)"  # 確定オッズ
RESULT_POPULARITY = "td.popularity, td:nth-child(10)"  # 人気
RESULT_TIME = "td.time, td:nth-child(11)"  # 着時間
RESULT_MARGIN = "td.margin, td:nth-child(12)"  # 着差
RESULT_CORNER_ORDER = "td.corner-order, td:nth-child(13)"  # コーナー順位
RESULT_REMARK = "td.remark, td:nth-child(14)"  # 備考

# ========================
# ヘルパー関数
# ========================


def get_selector(selector_name: str) -> str:
    """セレクタを名前で取得"""
    return globals().get(selector_name, "")


# ========================
# API エンドポイント定義
# ========================

BASE_URL = "https://www.jra.go.jp"
RACE_CALENDAR_URL_TEMPLATE = "https://www.jra.go.jp/keiba/calendar/index.html"
RACE_CARD_URL_TEMPLATE = "https://www.jra.go.jp/keiba/race/{race_id}/"
RACE_RESULT_URL_TEMPLATE = "https://www.jra.go.jp/keiba/result/{race_id}/"

# ページネーション・検索パラメータ
SEARCH_PARAMS = {
    "calendar": {"year": None, "month": None},
    "card": {"race_id": None},
    "result": {"race_id": None},
}
