"""
テストデータ生成
スクレイピング前の動作確認用
"""

from datetime import datetime, timedelta

def generate_test_races():
    """テストレースデータを生成"""
    races = []
    
    # 過去30日間のテストレース
    base_date = datetime.now().date()
    courses = ["東京", "中山", "阪神", "京都"]
    
    for i in range(30):
        race_date = base_date - timedelta(days=i)
        if race_date.weekday() == 6:  # 日曜日のみ
            for course in courses:
                for race_no in range(1, 13):  # 12レース
                    races.append({
                        "race_date": str(race_date),
                        "course": course,
                        "race_no": race_no,
                        "distance_m": 1600 if race_no % 2 == 0 else 2000,
                        "surface": "芝" if race_no % 3 == 0 else "ダート",
                        "going": "良",
                        "grade": "G1" if race_no == 1 else "G2" if race_no == 2 else "OP",
                        "title": f"{course}競馬 {race_no}レース",
                    })
    
    return races


def generate_test_horses():
    """テスト馬データを生成"""
    horse_names = [
        "テスト太郎", "テスト花子", "テスト次郎", "テスト三郎",
        "サンプル馬", "ダミー競馬", "テスト競争馬", "試験馬",
        "データベース号", "クラウド号", "ストリーム号", "アプリ号",
    ]
    
    horses = [
        {
            "raw_name": name,
            "sex": "牡" if i % 2 == 0 else "牝",
            "birth_year": 2020 + (i % 4),
        }
        for i, name in enumerate(horse_names)
    ]
    
    return horses


def generate_test_jockeys():
    """テスト騎手データを生成"""
    jockey_names = [
        "騎手A", "騎手B", "騎手C", "騎手D", "騎手E",
        "テスト騎手1", "テスト騎手2", "テスト騎手3",
    ]
    
    return [{"raw_name": name} for name in jockey_names]


def generate_test_trainers():
    """テスト調教師データを生成"""
    trainer_names = [
        "調教師A", "調教師B", "調教師C", "調教師D",
        "テスト調教師1", "テスト調教師2",
    ]
    
    return [{"raw_name": name} for name in trainer_names]


def generate_test_entries(races, horses, jockeys, trainers):
    """テスト出走データを生成"""
    entries = []
    
    for race in races:
        for horse_no in range(1, 9):  # 8頭出走
            horse = horses[horse_no % len(horses)]
            jockey = jockeys[horse_no % len(jockeys)]
            trainer = trainers[horse_no % len(trainers)]
            
            entries.append({
                "race_date": race["race_date"],
                "course": race["course"],
                "race_no": race["race_no"],
                "horse_name": horse["raw_name"],
                "jockey_name": jockey["raw_name"],
                "trainer_name": trainer["raw_name"],
                "frame_no": (horse_no - 1) // 2 + 1,
                "horse_no": horse_no,
                "age": 3 + (horse_no % 3),
                "weight_carried": 55.0 + (horse_no % 10),
                "finish_pos": horse_no if horse_no <= 3 else None,
                "finish_time_seconds": 120.5 + (horse_no % 10) * 0.5 if horse_no <= 3 else None,
                "margin": "ハナ" if horse_no == 2 else "アタマ" if horse_no == 3 else None if horse_no <= 1 else None,
                "odds": 2.5 + (horse_no * 0.5),
                "popularity": horse_no,
            })
    
    return entries
