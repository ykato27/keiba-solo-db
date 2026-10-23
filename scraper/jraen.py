"""JRA公式英語データサービス（jra.jp/JRAEN）からの結果取得

経緯:
- 従来 scraper/ が想定していた www.jra.go.jp の URL 形式
  （/keiba/result/{race_id}/ など）は実在せず、www.jra.go.jp 自体も
  本環境からは 403 を返す。
- JRA公式の英語ポータル japanracing.jp の「Race Card & Results」は
  https://jra.jp/JRAEN/AP/common/main を開く。この JRAEN サービスは
  サーバーレンダリングの HTML で、全着順・確定オッズ・人気・払戻
  （PAY-OFF）を含む公式結果を返すため、こちらを正規の取得経路とする。
- netkeiba は利用規約上のリスクが指摘されているため使用しない。

礼儀:
- リクエスト間隔は最低 min_interval 秒（既定6秒 = 10件/分、
  リポジトリ既存の scraper/rate_limit.py の方針に合わせる）。
- User-Agent は明示する。
- 403 / 429 が返ったら、その時点で取得を中止する（FetchBlocked）。
  タイムアウト等は呼び出し側で最大1回だけ再試行する。
"""

import logging
import re
import time
from typing import Dict, List, Optional

import requests
from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)

BASE_URL = "https://jra.jp/JRAEN"
USER_AGENT = "keiba-solo-db/1.0 (personal research; data fetch with 6s interval)"

COURSE_BY_JO_CODE = {
    "01": "札幌", "02": "函館", "03": "福島", "04": "新潟", "05": "東京",
    "06": "中山", "07": "中京", "08": "京都", "09": "阪神", "10": "小倉",
}
COURSE_EN_TO_JP = {
    "SAPPORO": "札幌", "HAKODATE": "函館", "FUKUSHIMA": "福島",
    "NIIGATA": "新潟", "TOKYO": "東京", "NAKAYAMA": "中山",
    "CHUKYO": "中京", "KYOTO": "京都", "HANSHIN": "阪神", "KOKURA": "小倉",
}
SURFACE_EN_TO_JP = {"Turf": "芝", "Dirt": "ダート"}
GOING_EN_TO_JP = {
    # 芝
    "Firm": "良", "Good to Firm": "良", "Good": "稍重",
    "Yielding": "重", "Soft": "不良",
    # ダート
    "Standard": "良", "Muddy": "重", "Sloppy": "不良",
}

BET_TYPE_BY_COLUMN = {
    "Win": "win",
    "Show": "place",
    "Bracket Q.": "bracket_quinella",
    "Quinella": "quinella",
    "Q.Place": "quinella_place",
    "Exacta": "exacta",
    "Trio": "trio",
    "Trifecta": "trifecta",
}


class FetchBlocked(Exception):
    """403/429 など、取得元に拒否された（その取得元は中止する）"""


class FetchError(Exception):
    """一時的な取得失敗"""


class JraenClient:
    def __init__(self, min_interval: float = 6.0, timeout=(10, 45)):
        # timeout は (接続, 読み取り) のタプル。読み取りは「無通信の間隔」
        # に対する制限で、低速なサーバーでも無期限に固まらないようにする。
        self.min_interval = min_interval
        self.timeout = timeout
        self.session = requests.Session()
        self.session.headers.update(
            {"User-Agent": USER_AGENT, "Accept-Language": "en-US,en;q=0.9"}
        )
        self._last_request_at = 0.0

    def _request(self, method: str, path: str, data: Optional[dict] = None) -> str:
        wait = self.min_interval - (time.time() - self._last_request_at)
        if wait > 0:
            time.sleep(wait)
        url = f"{BASE_URL}{path}"
        try:
            response = self.session.request(
                method, url, data=data, timeout=self.timeout
            )
        except requests.RequestException as e:
            raise FetchError(f"リクエスト失敗: {url}: {e}") from e
        finally:
            self._last_request_at = time.time()
        if response.status_code in (403, 429):
            raise FetchBlocked(
                f"取得元に拒否されました (HTTP {response.status_code}): {url}"
            )
        if response.status_code != 200:
            raise FetchError(f"HTTP {response.status_code}: {url}")
        response.encoding = "utf-8"
        if "SYSTEM ERROR OCCURRED" in response.text:
            # このサーバーは一時的に HTTP 200 でエラーページを返すことがある
            raise FetchError(f"サーバーエラー応答 (SYSTEM ERROR): {url}")
        return response.text

    def fetch_meeting_dates(self, year: int) -> List[str]:
        """指定年の開催日リスト（YYYYMMDD）を返す（セッション確立も兼ねる）"""
        self._request("GET", "/AP/kaisai/kaisaiRaceInit")
        html = self._request(
            "POST", "/AP/kaisai/kaisaiRaceSearch", data={"raceYear": str(year)}
        )
        return sorted(set(re.findall(r"displayRace\('SelectRace', '(\d{8})'\)", html)))

    def fetch_race_refs(self, race_ymd: str) -> List[Dict[str, str]]:
        """開催日のレース一覧（displayRunning の引数）を返す"""
        html = self._request(
            "POST", "/AP/kaisai/raceSelect", data={"raceYmd": race_ymd}
        )
        refs = []
        seen = set()
        for m in re.finditer(
            r"displayRunning\('SelectRunning',\s*'(\d{8})',\s*'(\d{2})',\s*"
            r"'(\d{2})',\s*'(\d{2})',\s*'(\d{1,2})'\)",
            html,
        ):
            ymd, jo, kai, hi, race_no = m.groups()
            key = (ymd, jo, race_no)
            if key in seen:
                continue
            seen.add(key)
            refs.append(
                {
                    "race_ymd": ymd,
                    "jo_cd": jo,
                    "kai": kai,
                    "hi": hi,
                    "race_no": int(race_no),
                }
            )
        return refs

    def fetch_race_result_html(self, ref: Dict[str, str]) -> str:
        return self._request(
            "POST",
            "/AP/kaisai/running",
            data={
                "raceYmd": ref["race_ymd"],
                "raceJoCd": ref["jo_cd"],
                "raceKai": ref["kai"],
                "raceHi": ref["hi"],
                "raceNo": str(ref["race_no"]),
            },
        )


_ORDINAL_RE = re.compile(r"^(\d+)(st|nd|rd|th)$")
_COMBINATION_RE = re.compile(r"^\d+(\s*-\s*\d+)*$")


def parse_ordinal(text: str) -> Optional[int]:
    m = _ORDINAL_RE.match(text.strip())
    return int(m.group(1)) if m else None


def _parse_finish_time(text: str) -> Optional[float]:
    text = text.strip()
    if ":" in text:
        try:
            minutes, seconds = text.split(":", 1)
            return int(minutes) * 60 + float(seconds)
        except ValueError:
            return None
    try:
        return float(text)
    except ValueError:
        return None


def _split_br(cell) -> List[str]:
    """<br> 区切りのセル（騎手<br>調教師など）をテキストのリストにする"""
    parts = []
    for chunk in re.split(r"<br\s*/?>", cell.decode_contents()):
        text = BeautifulSoup(chunk, "lxml").get_text(" ", strip=True)
        parts.append(text)
    return parts


def parse_payoffs(soup: BeautifulSoup) -> List[Dict]:
    """PAY-OFF 表から払戻レコードを抽出する

    戻り値: [{bet_type, combination, payout_yen}]
    combination は馬番を '-' でつないだ文字列（単勝・複勝は馬番のみ）。
    ラベル行は（組合せ, 金額）のペアが券種の列順に並び、継続行には
    複勝（単独の馬番）とワイド（2頭の組合せ）の追加分だけが現れる。
    """
    table = None
    for candidate in soup.find_all("table"):
        if "PAY-OFF" in candidate.get_text(" ", strip=True):
            table = candidate
            break
    if table is None:
        return []

    rows = table.find_all("tr", recursive=False)
    if len(rows) < 3:
        return []

    def direct_cells(row):
        return [
            c.get_text(" ", strip=True)
            for c in row.find_all(["td", "th"], recursive=False)
        ]

    header = direct_cells(rows[0])
    bet_types = [BET_TYPE_BY_COLUMN.get(name) for name in header[1:]]

    payoffs: List[Dict] = []

    def add(bet_type, combination, amount_text):
        if bet_type is None:
            return
        try:
            amount = int(amount_text.replace(",", ""))
        except ValueError:
            return
        payoffs.append(
            {
                "bet_type": bet_type,
                "combination": re.sub(r"\s+", "", combination),
                "payout_yen": amount,
            }
        )

    for row in rows[2:]:
        cells = direct_cells(row)
        if not cells:
            continue
        if cells[0].startswith("PAY-OFF"):
            pairs = cells[1:]
            for i, bet_type in enumerate(bet_types):
                if 2 * i + 1 < len(pairs):
                    add(bet_type, pairs[2 * i], pairs[2 * i + 1])
        else:
            # 継続行: 複勝（馬番のみ）とワイド（2頭）の追加ペアだけが現れる
            i = 0
            while i < len(cells):
                combination = cells[i]
                if _COMBINATION_RE.match(combination or ""):
                    amount = cells[i + 1] if i + 1 < len(cells) else ""
                    bet_type = "place" if "-" not in combination else "quinella_place"
                    add(bet_type, combination, amount)
                    i += 2
                else:
                    i += 1
    return payoffs


def parse_running_html(html: str, ref: Dict[str, str]) -> Dict:
    """レース結果ページ（running）を構造化データにする

    戻り値: {
      race_date, course, race_no, distance_m, surface, going_en, going,
      is_steeplechase, entries: [...], payoffs: [...]
    }
    entries の各要素: finish_pos（完走しなかった場合は None）, frame_no,
    horse_no, horse_name, sex, age, weight_carried, corner_order,
    finish_time_seconds, margin, popularity, odds, jockey_name, trainer_name
    """
    soup = BeautifulSoup(html, "lxml")
    page_text = soup.get_text(" ", strip=True)

    # レース見出し: "January 5, 2025, 1200m, Dirt Standard, Fine, Post time 10:05"
    header_match = re.search(
        r"(\d+)m,\s*(Turf|Dirt)\s+([A-Za-z ]+?),\s*[A-Za-z]+,\s*Post time",
        page_text,
    )
    if not header_match:
        raise FetchError("レース見出し（距離・馬場）が解析できませんでした")
    distance_m = int(header_match.group(1))
    surface_en = header_match.group(2)
    going_en = header_match.group(3).strip()

    course = COURSE_BY_JO_CODE.get(ref["jo_cd"])
    course_pattern = re.compile(
        rf"^({'|'.join(COURSE_EN_TO_JP)})\s+\d+R$"
    )
    for candidate in soup.find_all("table"):
        m = course_pattern.match(candidate.get_text(" ", strip=True))
        if m:
            course = COURSE_EN_TO_JP[m.group(1)]
            break

    # 結果表（'Win Odds' を含む表）
    result_table = None
    for candidate in soup.find_all("table"):
        if "Win Odds" in candidate.get_text(" ", strip=True):
            result_table = candidate
            break
    if result_table is None:
        raise FetchError("結果表が見つかりませんでした")

    entries: List[Dict] = []
    skipped_rows = 0
    for row in result_table.find_all("tr"):
        cells = [c.get_text(" ", strip=True) for c in row.find_all(["td", "th"])]
        if len(cells) < 10:
            continue
        finish_pos = parse_ordinal(cells[0])
        if finish_pos is None:
            # 見出し行・コーナー行はここで落ちる。着順として解釈できない
            # データ行（完走しなかった馬など）は件数だけ数えて報告する。
            if cells[0] not in ("FP",) and not cells[0].endswith("c"):
                skipped_rows += 1
            continue
        try:
            frame_no = int(cells[1])
            horse_no = int(cells[2])
            popularity = int(cells[-2])
            odds = float(cells[-1])
        except ValueError:
            continue
        sex_age = cells[4]
        age_match = re.search(r"(\d+)$", sex_age)
        corners = [c for c in cells[6:10]]
        entries.append(
            {
                "finish_pos": finish_pos,
                "frame_no": frame_no,
                "horse_no": horse_no,
                "horse_name": re.sub(r"\([A-Z]{2,3}\)$", "", cells[3]).strip(),
                "sex": sex_age[0] if sex_age else None,
                "age": int(age_match.group(1)) if age_match else None,
                "weight_carried": _safe_float(cells[5]),
                "corner_order": "-".join(c for c in corners if c) or None,
                "finish_time_seconds": _parse_finish_time(cells[-4]),
                "margin": cells[-3] or None,
                "popularity": popularity,
                "odds": odds,
            }
        )

    # 騎手・調教師表（FP で突き合わせ）
    for candidate in soup.find_all("table"):
        header_text = candidate.get_text(" ", strip=True)
        if "Jockey" not in header_text or "Trainer" not in header_text:
            continue
        for row in candidate.find_all("tr"):
            cells = row.find_all(["td", "th"])
            if len(cells) < 5:
                continue
            finish_pos = parse_ordinal(cells[0].get_text(" ", strip=True))
            if finish_pos is None:
                continue
            parts = _split_br(cells[4])
            for entry in entries:
                if entry["finish_pos"] == finish_pos:
                    entry["jockey_name"] = parts[0] if parts else ""
                    entry["trainer_name"] = parts[1] if len(parts) > 1 else ""
        break

    for entry in entries:
        entry.setdefault("jockey_name", "")
        entry.setdefault("trainer_name", "")

    ymd = ref["race_ymd"]
    return {
        "race_date": f"{ymd[0:4]}-{ymd[4:6]}-{ymd[6:8]}",
        "course": course,
        "race_no": int(ref["race_no"]),
        "distance_m": distance_m,
        "surface": SURFACE_EN_TO_JP.get(surface_en, surface_en),
        "going_en": going_en,
        "going": GOING_EN_TO_JP.get(going_en),
        "is_steeplechase": 1 if "steeplechase" in page_text.lower() else 0,
        "entries": entries,
        "payoffs": parse_payoffs(soup),
        "skipped_result_rows": skipped_rows,
    }


def _safe_float(text: str) -> Optional[float]:
    try:
        return float(text.strip())
    except (ValueError, AttributeError):
        return None
