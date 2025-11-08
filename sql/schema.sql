PRAGMA journal_mode=WAL;
PRAGMA synchronous=NORMAL;

CREATE TABLE IF NOT EXISTS horses (
  horse_id INTEGER PRIMARY KEY,
  raw_name TEXT NOT NULL,
  sex TEXT,
  birth_year INTEGER,
  created_at TEXT DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS jockeys (
  jockey_id INTEGER PRIMARY KEY,
  raw_name TEXT NOT NULL,
  created_at TEXT DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS trainers (
  trainer_id INTEGER PRIMARY KEY,
  raw_name TEXT NOT NULL,
  created_at TEXT DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS races (
  race_id INTEGER PRIMARY KEY,
  race_date TEXT NOT NULL,              -- YYYY-MM-DD
  course TEXT NOT NULL,
  race_no INTEGER NOT NULL,
  distance_m INTEGER NOT NULL,
  surface TEXT NOT NULL,                -- 芝/ダート
  going TEXT,                           -- 馬場状態
  grade TEXT,                           -- G1/G2/G3/OP/他
  title TEXT,
  UNIQUE (race_date, course, race_no)
);

CREATE TABLE IF NOT EXISTS race_entries (
  entry_id INTEGER PRIMARY KEY,
  race_id INTEGER NOT NULL REFERENCES races(race_id) ON DELETE CASCADE,
  horse_id INTEGER NOT NULL REFERENCES horses(horse_id),
  jockey_id INTEGER REFERENCES jockeys(jockey_id),
  trainer_id INTEGER REFERENCES trainers(trainer_id),
  frame_no INTEGER,
  horse_no INTEGER,
  age INTEGER,
  weight_carried REAL,                  -- 斤量
  horse_weight REAL,                    -- 馬の体重
  finish_pos INTEGER,                   -- 確定前はnull
  finish_time_seconds REAL,
  margin TEXT,
  odds REAL,
  popularity INTEGER,
  corner_order TEXT,                    -- "3-3-2"など
  remark TEXT,
  days_since_last_race INTEGER,         -- 前走からの経過日数
  is_steeplechase INTEGER DEFAULT 0,    -- 障害フラグ
  UNIQUE (race_id, horse_id)
);

CREATE TABLE IF NOT EXISTS alias_horse (
  alias TEXT PRIMARY KEY,
  horse_id INTEGER NOT NULL REFERENCES horses(horse_id)
);

CREATE TABLE IF NOT EXISTS alias_jockey (
  alias TEXT PRIMARY KEY,
  jockey_id INTEGER NOT NULL REFERENCES jockeys(jockey_id)
);

CREATE TABLE IF NOT EXISTS alias_trainer (
  alias TEXT PRIMARY KEY,
  trainer_id INTEGER NOT NULL REFERENCES trainers(trainer_id)
);

CREATE TABLE IF NOT EXISTS horse_metrics (
  horse_id INTEGER PRIMARY KEY REFERENCES horses(horse_id),
  races_count INTEGER NOT NULL,
  win_rate REAL NOT NULL,
  place_rate REAL NOT NULL,             -- 連対率
  show_rate REAL NOT NULL,              -- 複勝率
  recent_score REAL NOT NULL,           -- 近走指数
  distance_pref TEXT,                   -- JSON文字列
  surface_pref TEXT,                    -- JSON文字列
  updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS horse_pedigree (
  horse_id INTEGER PRIMARY KEY REFERENCES horses(horse_id),
  sire_id INTEGER REFERENCES horses(horse_id),         -- 父
  dam_sire_id INTEGER REFERENCES horses(horse_id),     -- 母父
  sire_win_rate REAL,                                  -- 父の産駒勝率
  dam_sire_win_rate REAL,                              -- 母父の産駒勝率
  updated_at TEXT DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS horse_weight_history (
  history_id INTEGER PRIMARY KEY,
  horse_id INTEGER NOT NULL REFERENCES horses(horse_id),
  race_id INTEGER REFERENCES races(race_id),
  weight REAL,
  weight_change REAL,                   -- 前レースからの体重変化
  recorded_at TEXT NOT NULL,
  UNIQUE (horse_id, race_id)
);

-- Indexes
CREATE INDEX IF NOT EXISTS idx_entries_race  ON race_entries(race_id);
CREATE INDEX IF NOT EXISTS idx_entries_horse ON race_entries(horse_id);
CREATE INDEX IF NOT EXISTS idx_races_date    ON races(race_date);
CREATE INDEX IF NOT EXISTS idx_races_course  ON races(course);
CREATE INDEX IF NOT EXISTS idx_horse_name    ON horses(raw_name);
CREATE INDEX IF NOT EXISTS idx_jockey_name   ON jockeys(raw_name);
CREATE INDEX IF NOT EXISTS idx_trainer_name  ON trainers(raw_name);
