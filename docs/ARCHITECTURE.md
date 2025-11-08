# System Architecture - keiba-solo-db

## 📐 High-Level Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                    Streamlit UI Layer                        │
│  (app/Home.py, app/pages/*.py - Interactive Dashboard)      │
└────────────────────────┬────────────────────────────────────┘
                         │
        ┌────────────────┼────────────────┐
        │                │                │
        ▼                ▼                ▼
┌──────────────┐  ┌──────────────┐  ┌──────────────┐
│  Database    │  │   Features   │  │   Models     │
│  Layer       │  │   & Metrics  │  │   & Predict  │
│  (app/db.py) │  │ (app/feat..) │  │ (app/model..)│
└──────────────┘  └──────────────┘  └──────────────┘
        │                │                │
        └────────────────┼────────────────┘
                         │
        ┌────────────────┼────────────────┐
        │                │                │
        ▼                ▼                ▼
┌──────────────┐  ┌──────────────┐  ┌──────────────┐
│  SQLite DB   │  │  Scraper     │  │  ETL         │
│  (data/      │  │  (scraper/)  │  │  (etl/)      │
│   keiba.db)  │  │  Fetch data  │  │  Transform   │
└──────────────┘  └──────────────┘  └──────────────┘
        │                │                │
        └────────────────┼────────────────┘
                         │
                         ▼
                   JRA Official Site
                (Japan Racing Association)
```

## 📦 Project Structure

```
keiba-solo-db/
│
├── app/                          # Main Streamlit Application
│   ├── Home.py                   # Landing page & data overview
│   ├── pages/
│   │   ├── 1_Race.py            # Race details & entries
│   │   ├── 2_FutureRaces.py     # Future race predictions
│   │   ├── 3_Horse.py           # Horse statistics
│   │   ├── 4_Prediction.py      # ML model predictions
│   │   └── 5_Betting.py         # Betting optimization
│   ├── db.py                     # Database operations (unified module)
│   ├── queries.py                # Cached queries with @st.cache_data
│   ├── charts.py                 # Plotly chart generation
│   ├── features.py               # Feature extraction & engineering
│   ├── prediction_model.py       # ML model implementations
│   ├── prediction_model_lightgbm.py  # Advanced LightGBM model
│   └── betting_optimizer.py      # Kelly Criterion optimization
│
├── scraper/                      # Web Scraping Layer
│   ├── selectors.py              # HTML selectors management
│   ├── rate_limit.py             # Rate limiting & retry logic
│   ├── fetch_calendar.py         # Race calendar scraping
│   ├── fetch_card.py             # Horse entry data
│   ├── fetch_result.py           # Race results
│   └── cache_future_races.py     # Future race data caching
│
├── etl/                          # ETL (Extract-Transform-Load)
│   ├── base.py                   # Base ETL class
│   ├── upsert_master.py          # Master data (horses, jockeys, trainers)
│   ├── upsert_race.py            # Race information
│   ├── upsert_entry.py           # Race entries
│   ├── apply_alias.py            # Name standardization
│   └── init_db.py                # Database schema initialization
│
├── metrics/                      # Metrics & Analytics
│   └── build_horse_metrics.py    # Horse performance metrics
│
├── tests/                        # Test Suite
│   ├── __init__.py
│   ├── test_pipeline.py          # Integration tests
│   ├── test_csv_export.py        # CSV export validation
│   ├── test_prediction_page.py   # Prediction page tests
│   ├── test_betting_optimizer.py # Betting strategy tests
│   └── test_ds_improvements.py   # Model validation tests
│
├── docs/                         # Documentation
│   ├── INDEX.md                  # Documentation index
│   ├── ARCHITECTURE.md           # This file
│   ├── API.md                    # Type definitions & functions
│   ├── DEVELOPMENT.md            # Developer guidelines
│   ├── TESTING.md                # Testing documentation
│   ├── CLAUDE.md                 # AI development guidelines
│   ├── CRITICAL_IMPROVEMENTS_IMPLEMENTED.md
│   ├── DS_CRITICAL_IMPROVEMENTS.md
│   ├── DS_REVIEW.md
│   ├── BETTING_OPTIMIZATION_GUIDE.md
│   ├── STREAMLIT_CACHE_FIX.md
│   └── LOCAL_TEST_RESULTS.md
│
├── data/                         # Data Directory
│   ├── keiba.db                  # SQLite database (primary data store)
│   └── logs/                     # Scraping operation logs
│
├── sql/                          # Database Schema
│   └── schema.sql                # Table definitions
│
├── requirements.txt              # Python dependencies
├── pyproject.toml                # Black, isort, pytest config
├── mypy.ini                      # Type checker configuration
├── .flake8                       # Style checker configuration
├── lint.bat                      # Windows: Code quality script
├── lint.sh                       # Unix/macOS: Code quality script
├── README.md                     # Main project README
└── CLAUDE.md                     # Development principles (root)
```

## 🗄️ Database Schema

### Master Tables

#### horses
```sql
CREATE TABLE horses (
    horse_id INTEGER PRIMARY KEY,
    raw_name TEXT UNIQUE NOT NULL,      -- Original name from JRA
    standardized_name TEXT,             -- After alias resolution
    sex TEXT,                           -- M/F/G
    birth_year INTEGER,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

#### jockeys & trainers
```sql
CREATE TABLE jockeys (
    jockey_id INTEGER PRIMARY KEY,
    raw_name TEXT UNIQUE NOT NULL,
    standardized_name TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
-- Similar structure for trainers table
```

#### Alias Tables (Name Standardization)
```sql
CREATE TABLE alias_horse (
    alias_id INTEGER PRIMARY KEY,
    raw_name TEXT NOT NULL,
    standard_name TEXT NOT NULL,
    horse_id INTEGER,
    FOREIGN KEY (horse_id) REFERENCES horses(horse_id)
);
-- Similar for alias_jockey and alias_trainer
```

### Transaction Tables

#### races
```sql
CREATE TABLE races (
    race_id INTEGER PRIMARY KEY,
    race_date TEXT NOT NULL,           -- YYYY-MM-DD
    course TEXT NOT NULL,              -- 東京, 京都, etc.
    race_no INTEGER,                   -- Race number at venue
    distance_m INTEGER,                -- Distance in meters
    surface TEXT,                      -- 芝, ダ, 障害 (turf/dirt/steeplechase)
    going TEXT,                        -- 良, 稍, 悪, 重 (track condition)
    title TEXT,
    grade TEXT,                        -- G1, G2, G3, Listed
    prize_total INTEGER,               -- Total prize in yen
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

#### race_entries
```sql
CREATE TABLE race_entries (
    entry_id INTEGER PRIMARY KEY,
    race_id INTEGER NOT NULL,
    horse_id INTEGER NOT NULL,
    horse_name TEXT,                   -- Denormalized for query speed
    bracket_no INTEGER,                -- 枠番
    horse_no INTEGER,                  -- 馬番
    jockey_id INTEGER,
    jockey_name TEXT,
    trainer_id INTEGER,
    trainer_name TEXT,
    weight INTEGER,                    -- Horse weight (kg)
    days_since_last_race INTEGER,      -- Rest period (days)
    is_steeplechase INTEGER DEFAULT 0, -- 障害flag
    horse_weight REAL,                 -- Recent weight (optional)

    -- Results (filled after race)
    result_no INTEGER,                 -- Finishing position
    time_str TEXT,                     -- Time format (MM:SS.S)
    margin TEXT,                       -- Margin between 1st and 2nd
    odds REAL,                         -- Betting odds
    popularity INTEGER,                -- Popularity (人気)

    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (race_id) REFERENCES races(race_id),
    FOREIGN KEY (horse_id) REFERENCES horses(horse_id),
    FOREIGN KEY (jockey_id) REFERENCES jockeys(jockey_id),
    FOREIGN KEY (trainer_id) REFERENCES trainers(trainer_id)
);
```

### Analytics Tables

#### horse_metrics
```sql
CREATE TABLE horse_metrics (
    metric_id INTEGER PRIMARY KEY,
    horse_id INTEGER NOT NULL UNIQUE,

    -- Basic metrics
    total_races INTEGER,
    wins INTEGER,
    seconds INTEGER,
    thirds INTEGER,

    -- Win rates
    win_rate REAL,                     -- 勝率
    place_rate REAL,                   -- 連対率
    show_rate REAL,                    -- 複勝率

    -- Distance preferences (JSON)
    distance_stats TEXT,               -- {"1000": {...}, "1200": {...}, ...}

    -- Surface preferences (JSON)
    surface_stats TEXT,                -- {"芝": {...}, "ダ": {...}, "障害": {...}}

    -- Recent form (JSON)
    recent_form TEXT,                  -- Last 5 races summary

    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (horse_id) REFERENCES horses(horse_id)
);
```

## 🔄 Data Flow

### 1. Data Acquisition (Scraper)

```
JRA Official Site
        ↓
scraper/fetch_calendar.py     → Get race dates & venues
scraper/fetch_card.py         → Get horse entry data
scraper/fetch_result.py       → Get race results
        ↓
Raw HTML/JSON Data
```

### 2. Data Transformation (ETL)

```
Raw Data
    ↓
etl/upsert_master.py         → Insert/Update horses, jockeys, trainers
etl/upsert_race.py           → Insert/Update races
etl/upsert_entry.py          → Insert/Update race_entries
etl/apply_alias.py           → Standardize names (alias resolution)
    ↓
Normalized Data in SQLite
```

### 3. Feature Engineering (Metrics)

```
Normalized Data
    ↓
metrics/build_horse_metrics.py
    ├── Calculate win rates
    ├── Group by distance
    ├── Group by surface
    └── Extract recent form
    ↓
horse_metrics table (Updated)
```

### 4. Prediction (ML Models)

```
Feature Extraction (app/features.py)
    ├── WHO: Horse characteristics (60+ features)
    ├── WHEN: Distance/surface preferences
    ├── RACE: Race conditions
    ├── ENTRY: Jockey/trainer/weight
    └── PEDIGREE: Lineage data
    ↓
LightGBM / Random Forest Models
    ├── Model Training (TimeSeriesSplit)
    └── Cross-validation Results
    ↓
Predictions (Rank, Win Probability)
```

### 5. User Interface (Streamlit)

```
SQLite Database
    ↓
app/queries.py (@st.cache_data)
    ↓
app/charts.py (Plotly Visualizations)
    ↓
Streamlit Pages (Interactive Dashboard)
    ├── Home: Overview
    ├── Race: Race details
    ├── Horse: Statistics
    ├── Prediction: ML results
    ├── Betting: Optimization
    └── FutureRaces: Tomorrow's races
```

## 🎯 Key Design Patterns

### 1. Resource Management (Database Connections)
```python
# All database operations use try-finally to prevent connection leaks
conn = get_connection(read_only=True)
try:
    cursor = conn.cursor()
    # ... query execution
    return results
finally:
    conn.close()  # Always executes, even on exception
```

**Why**: SQLite connections are limited resources. Failing to close causes "database is locked" errors.

### 2. Type Safety (TypedDict)
```python
class RaceInfo(TypedDict, total=False):
    race_id: int
    race_no: int
    distance_m: int
    surface: str
    # ... 20+ fields

# Functions return typed dicts, not generic Dict[str, Any]
def get_races(date: str) -> List[RaceInfo]:
    # ...
```

**Why**: Enables IDE autocomplete, type checking with mypy, and clearer contracts.

### 3. Caching Strategy
```python
# Resource-intensive initialization (once per session)
@st.cache_resource
def get_model() -> PredictionModel:
    return PredictionModel()

# Data queries (cached until dependencies change)
@st.cache_data
def fetch_races(date: str) -> List[RaceInfo]:
    return queries.get_races(date)
```

**Why**: Streamlit reruns entire script on interaction. Caching prevents redundant computation.

### 4. Time-Series Validation (ML)
```python
from sklearn.model_selection import TimeSeriesSplit

tscv = TimeSeriesSplit(n_splits=3)
for train_idx, test_idx in tscv.split(X):
    # Train on past data, test on future data
    # Prevents data leakage (future info leaking into past)
```

**Why**: Horse racing is sequential. Future race results don't affect past races.

## 📊 Feature Engineering (5 Dimensions)

### WHO - Horse Characteristics
- Veteran status, experience level, performance metrics
- Weight, age, condition indicators

### WHEN - Distance & Surface Preferences
- Historical performance at different distances
- Track surface preferences (turf/dirt/steeplechase)
- Seasonal patterns

### RACE - Race Conditions
- Race grade (G1, G2, G3, Listed)
- Distance type (short/middle/long)
- Field strength

### ENTRY - Entry Information
- Jockey performance
- Trainer statistics
- Weight changes, rest period

### PEDIGREE - Lineage Data
- Sire win rates
- Dam sire performance
- Genetic performance indicators

**Total**: 60+ engineered features for model training.

## 🔐 Data Consistency

### Alias Resolution
Multiple horses may be recorded under different names:
```sql
SELECT h.horse_id, h.standardized_name
FROM horses h
JOIN alias_horse a ON h.horse_id = a.horse_id
WHERE a.raw_name = '馬の別名';
```

### Normalization Flow
1. Raw data from JRA (may contain inconsistencies)
2. etl/apply_alias.py matches aliases to standard names
3. Subsequent queries use standardized_name

## 🚀 Performance Optimizations

### 1. Database Indexing
```sql
CREATE INDEX idx_races_date ON races(race_date);
CREATE INDEX idx_entries_race ON race_entries(race_id);
CREATE INDEX idx_entries_horse ON race_entries(horse_id);
```

### 2. Streamlit Caching
- @st.cache_resource: Expensive initialization (models, DB connections)
- @st.cache_data: Query results (refresh on code change)

### 3. Query Optimization
- Use LIMIT in queries where possible
- Denormalize horse_name in race_entries for faster retrieval
- JSON storage for distance/surface stats (flexible schema)

## 🔄 Update Cycle

### Weekly Automation (GitHub Actions - Disabled)
- Saturday 6:00 AM JST: Fetch entry cards
- Sunday 11:30 PM + Monday 6:00 AM JST: Fetch results & compute metrics

### Manual Workflow (Current)
```bash
python -m scraper.fetch_calendar --start 2019 --end 2024
python -m scraper.fetch_card --years 2019 2020 2021 2022 2023 2024
python -m scraper.fetch_result --years 2019 2020 2021 2022 2023 2024
python -m etl.upsert_master
python -m etl.upsert_race
python -m etl.upsert_entry
python -m etl.apply_alias
python -m metrics.build_horse_metrics
```

## 📈 Scalability Considerations

### Current Capacity
- 3-5 years of historical data: ~800-1,200 races
- ~8-14 horses per race: 6,400-16,800 race entries
- SQLite comfortably handles this volume

### Future Scaling
- 10+ years: Consider PostgreSQL or MySQL
- Real-time predictions: Consider message queue (Redis)
- Advanced analytics: Consider data warehouse (Snowflake, BigQuery)

---

**Last Updated**: 2025-11-08
**Architecture Version**: 2.0 (Professional Refactoring)
