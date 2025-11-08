"""
テストデータ生成（拡張版）
本番のような大量データを生成
"""

from datetime import datetime, timedelta
import random

# 実際の競馬場と日程
COURSES = ["東京", "中山", "阪神", "京都", "小倉", "新潟"]
HORSE_NAMES = [
    "ドリームキャスト", "サンダーバード", "クリスタルスター", "ブラックダイヤ",
    "シルバーウイング", "ゴールドラッシュ", "ホワイトナイト", "レッドフェニックス",
    "スカイホーク", "アースクエイク", "ウインドストーム", "フレイムハート",
    "アイスキング", "サンダークラウド", "ムーンライト", "サンセット",
    "ライジングサン", "スターダスト", "コスモス", "オーロラ",
    "アマゾン", "ライオン", "イーグル", "パンサー", "タイガー",
    "ドルフィン", "ペンギン", "フェニックス", "ドラゴン", "ユニコーン",
    "ザ・キング", "クイーン", "プリンス", "プリンセス", "ナイト",
    "ウォーリアー", "チャンピオン", "ビクター", "トライアンフ", "グローリー",
]

JOCKEY_NAMES = [
    "武豊", "岡部幸雄", "蛯名正義", "横山典弘", "福永祐一",
    "内田博幸", "上野広一", "角田晃一", "松山弘平", "田辺裕信",
    "丸山元気", "浜中俊", "池添謙一", "四位洋文", "和田竜二",
    "藤田伸二", "吉田豊", "石橋脩", "北村宏司", "高橋勇二",
]

TRAINER_NAMES = [
    "矢作芳人", "手塚貴久", "石橋守", "高野友和", "相沢郁",
    "奥平雅士", "杉山晴紀", "杉浦宏昭", "菊沢隆徳", "松下武士",
    "石坂正", "栗田徹", "竹内正七", "戸田博文", "渡辺現二",
    "菅原泰夫", "矢野英一", "野中賢二", "黒岩均", "大久根茂利",
]

def generate_test_races(years=3):
    """複数年のテストレースデータを生成"""
    races = []
    
    # 過去N年分のデータを生成
    base_date = datetime.now().date()
    
    for year_offset in range(years):
        # 各年度の日曜日（競馬が開催される日）
        start_date = base_date - timedelta(days=365 * year_offset)
        
        for day_offset in range(365):
            race_date = start_date - timedelta(days=day_offset)
            
            # 日曜日のみ
            if race_date.weekday() != 6:
                continue
            
            # 2-4開催
            num_courses = random.randint(2, 4)
            courses = random.sample(COURSES, num_courses)
            
            for course in courses:
                # 各開催場で11-12レース
                num_races = random.randint(11, 12)
                
                for race_no in range(1, num_races + 1):
                    races.append({
                        "race_date": str(race_date),
                        "course": course,
                        "race_no": race_no,
                        "distance_m": random.choice([1200, 1400, 1600, 1800, 2000, 2200, 2400, 2800]),
                        "surface": random.choice(["芝", "ダート"]),
                        "going": random.choice(["良", "稍", "重", "不"]),
                        "grade": random.choice(["G1", "G2", "G3", "OP", "1000万", "500万", "未勝利"]),
                        "title": f"{course}{race_no}R",
                    })
    
    return sorted(races, key=lambda x: x["race_date"], reverse=True)


def generate_test_horses(count=200):
    """テスト馬データを生成"""
    horses = []
    
    # 基本的な馬名リスト + ランダム組み合わせ
    base_names = HORSE_NAMES
    
    for i in range(count):
        if i < len(base_names):
            name = base_names[i]
        else:
            # ランダム組み合わせ
            suffixes = ["号", "型", "系", "線", "帝"]
            name = f"{random.choice(base_names)}{random.choice(suffixes)}"
        
        horses.append({
            "raw_name": name,
            "sex": random.choice(["牡", "牝", "セ"]),
            "birth_year": random.randint(2018, 2023),
        })
    
    return horses


def generate_test_jockeys(count=50):
    """テスト騎手データを生成"""
    jockeys = []
    
    base = JOCKEY_NAMES
    for i in range(count):
        if i < len(base):
            name = base[i]
        else:
            name = f"騎手{i}"
        
        jockeys.append({"raw_name": name})
    
    return jockeys


def generate_test_trainers(count=50):
    """テスト調教師データを生成"""
    trainers = []
    
    base = TRAINER_NAMES
    for i in range(count):
        if i < len(base):
            name = base[i]
        else:
            name = f"調教師{i}"
        
        trainers.append({"raw_name": name})
    
    return trainers


def generate_test_entries(races, horses, jockeys, trainers):
    """テスト出走データを生成（拡張版：新フィールド対応）"""
    entries = []

    for race in races:
        # 各レースに8-14頭出走
        num_starters = random.randint(8, 14)

        for horse_no in range(1, num_starters + 1):
            horse = random.choice(horses)
            jockey = random.choice(jockeys)
            trainer = random.choice(trainers)

            # 着順（上位3頭は着順あり、他はNone）
            finish_pos = horse_no if horse_no <= 3 else None

            # 馬の体重（350-550kg）
            horse_weight = round(400.0 + random.uniform(-100, 150), 0)

            # 前走からの経過日数（7-35日間が多い）
            days_since_last_race = random.choices(
                [7, 14, 21, 28, 35],
                weights=[30, 35, 20, 10, 5]
            )[0]

            entries.append({
                "race_date": race["race_date"],
                "course": race["course"],
                "race_no": race["race_no"],
                "horse_name": horse["raw_name"],
                "jockey_name": jockey["raw_name"],
                "trainer_name": trainer["raw_name"],
                "frame_no": (horse_no - 1) // 2 + 1,
                "horse_no": horse_no,
                "age": random.randint(3, 8),
                "weight_carried": round(52.0 + random.uniform(0, 10), 1),
                "horse_weight": horse_weight,
                "finish_pos": finish_pos,
                "finish_time_seconds": round(120.0 + random.uniform(0, 60), 1) if finish_pos else None,
                "margin": random.choice(["ハナ", "クビ", "アタマ", "1/2馬身", "1馬身", "2馬身"]) if horse_no == 2 else None,
                "odds": round(1.5 + random.uniform(0, 50), 1),
                "popularity": horse_no,
                "days_since_last_race": days_since_last_race,
                "is_steeplechase": random.choice([0, 0, 0, 0, 1]),  # 20%の確率で障害
            })

    return entries
