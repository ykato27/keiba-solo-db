# API Reference - keiba-solo-db

## 📋 Type Definitions (TypedDict)

All major data types are defined using `TypedDict` for type safety and IDE support. These are the contracts returned by API functions.

### RaceInfo
Represents a single race event.

```python
class RaceInfo(TypedDict, total=False):
    race_id: int                  # Unique race identifier
    race_no: int                  # Race number at venue
    race_date: str                # YYYY-MM-DD format
    course: str                   # Venue (東京, 京都, etc.)
    distance_m: int               # Distance in meters
    surface: str                  # 芝 (turf), ダ (dirt), 障害 (steeplechase)
    going: str                    # Track condition: 良, 稍, 悪, 重
    title: str                    # Race name
    grade: str                    # Race grade: G1, G2, G3, Listed
    prize_total: int              # Total prize money in yen
    created_at: str               # ISO timestamp
    updated_at: str               # ISO timestamp
```

**Usage Example**:
```python
races: List[RaceInfo] = queries.get_races_by_date_and_course("2025-11-08", "東京")
for race in races:
    print(f"Race {race['race_no']}: {race['title']} ({race['distance_m']}m)")
```

---

### RaceEntry
Represents a horse's entry in a specific race (before or after the race).

```python
class RaceEntry(TypedDict, total=False):
    # Identifiers
    entry_id: int                 # Unique entry identifier
    race_id: int                  # Reference to race
    horse_id: int                 # Reference to horse

    # Race Position
    bracket_no: int               # Starting bracket (枠番)
    horse_no: int                 # Horse number (馬番)

    # Participant Information
    horse_name: str               # Horse name
    jockey_id: int                # Jockey identifier
    jockey_name: str              # Jockey name
    trainer_id: int               # Trainer identifier
    trainer_name: str             # Trainer name

    # Pre-race Information
    weight: int                   # Horse weight in kg
    days_since_last_race: int     # Days since last race
    is_steeplechase: int          # 1 if steeplechase, 0 otherwise
    horse_weight: float           # Optional: recent weight record

    # Post-race Results
    result_no: int                # Finishing position (null if not finished)
    time_str: str                 # Race time (MM:SS.S format)
    margin: str                   # Margin from 1st place
    odds: float                   # Betting odds
    popularity: int               # Popularity ranking

    # Metadata
    created_at: str               # ISO timestamp
    updated_at: str               # ISO timestamp
```

**Usage Example**:
```python
entries: List[RaceEntry] = queries.get_race_entries(race_id=12345)
for entry in entries:
    status = f"{entry['result_no']}着" if entry['result_no'] else "未出走"
    print(f"{entry['horse_name']} - {entry['jockey_name']} - {status}")
```

---

### HorseInfo
Represents a horse's master data.

```python
class HorseInfo(TypedDict, total=False):
    # Basic Information
    horse_id: int                 # Unique horse identifier
    raw_name: str                 # Original name from JRA
    standardized_name: str        # Alias-resolved name
    sex: str                      # M (male), F (female), G (gelding)
    birth_year: int               # Year of birth

    # Metadata
    created_at: str               # ISO timestamp
    updated_at: str               # ISO timestamp
```

**Usage Example**:
```python
horse: Optional[HorseInfo] = queries.get_horse_details(horse_id=1001)
if horse:
    age = 2025 - horse['birth_year']
    print(f"{horse['standardized_name']} ({horse['sex']}) - Age {age}")
```

---

### RaceHistory
Represents a single race entry from a horse's historical perspective.

```python
class RaceHistory(TypedDict, total=False):
    # Race Identification
    race_id: int                  # Reference to race
    race_no: int                  # Race number at venue
    race_date: str                # YYYY-MM-DD format
    course: str                   # Venue

    # Race Details
    distance_m: int               # Distance in meters
    surface: str                  # Track surface type
    going: str                    # Track condition
    title: str                    # Race name
    grade: str                    # Race grade

    # Entry Information
    bracket_no: int               # Starting bracket
    horse_no: int                 # Horse number
    jockey_name: str              # Jockey name
    trainer_name: str             # Trainer name

    # Results
    result_no: int                # Finishing position
    time_str: str                 # Race time
    margin: str                   # Margin from 1st
    odds: float                   # Betting odds
    popularity: int               # Popularity ranking

    # Metadata
    created_at: str               # ISO timestamp
    updated_at: str               # ISO timestamp
```

**Usage Example**:
```python
history: List[RaceHistory] = queries.get_horse_race_history(horse_id=1001)
recent_5 = history[:5]  # Last 5 races
for race in recent_5:
    print(f"{race['race_date']}: {race['distance_m']}m - {race['result_no']}着")
```

---

## 🔌 Database API Functions

### app/db.py

#### `init_schema() → None`
Initialize database schema. Creates all tables and indexes.

```python
from app.db import init_schema

init_schema()  # Creates all tables if they don't exist
```

**Parameters**: None
**Returns**: None
**Raises**: sqlite3.Error on database issues

---

#### `get_connection(read_only: bool = False) → sqlite3.Connection`
Get database connection with type support.

```python
from app.db import get_connection

conn = get_connection(read_only=True)
try:
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM races LIMIT 1")
finally:
    conn.close()
```

**Parameters**:
- `read_only` (bool): If True, opens in read-only mode (default: False)

**Returns**: sqlite3.Connection object
**Raises**: sqlite3.DatabaseError if connection fails

---

#### `get_race_dates() → List[str]`
Get all unique race dates in database.

```python
from app.queries import get_race_dates

dates = get_race_dates()
print(dates)  # ['2025-11-01', '2025-11-02', '2025-11-08', ...]
```

**Parameters**: None
**Returns**: List of YYYY-MM-DD date strings
**Caching**: @st.cache_data (30 min default)

---

#### `get_courses_by_date(date: str) → List[str]`
Get all racing venues for a specific date.

```python
from app.queries import get_courses_by_date

courses = get_courses_by_date("2025-11-08")
print(courses)  # ['東京', '京都', '福島']
```

**Parameters**:
- `date` (str): YYYY-MM-DD format

**Returns**: List of course/venue names
**Caching**: @st.cache_data

---

#### `get_races_by_date_and_course(date: str, course: str) → List[RaceInfo]`
Get all races for a specific date and venue.

```python
from app.queries import get_races_by_date_and_course

races = get_races_by_date_and_course("2025-11-08", "東京")
```

**Parameters**:
- `date` (str): YYYY-MM-DD format
- `course` (str): Venue name

**Returns**: List[RaceInfo] - Race details
**Caching**: @st.cache_data
**Error Handling**: Returns empty list if no races found

---

#### `get_race_entries(race_id: int) → List[RaceEntry]`
Get all entries for a specific race.

```python
from app.queries import get_race_entries

entries = get_race_entries(race_id=12345)
for entry in entries:
    print(f"{entry['bracket_no']}-{entry['horse_no']}: {entry['horse_name']}")
```

**Parameters**:
- `race_id` (int): Race identifier

**Returns**: List[RaceEntry] - Horse entries
**Caching**: @st.cache_data
**Sorting**: By bracket_no, then horse_no

---

#### `get_horse_details(horse_id: int) → Optional[HorseInfo]`
Get master data for a specific horse.

```python
from app.queries import get_horse_details

horse = get_horse_details(horse_id=1001)
if horse:
    print(f"Name: {horse['standardized_name']}, Sex: {horse['sex']}")
else:
    print("Horse not found")
```

**Parameters**:
- `horse_id` (int): Horse identifier

**Returns**: HorseInfo if found, None otherwise
**Caching**: @st.cache_data

---

#### `get_horse_race_history(horse_id: int, limit: int = 100) → List[RaceHistory]`
Get race history for a specific horse.

```python
from app.queries import get_horse_race_history

# Get last 20 races
history = get_horse_race_history(horse_id=1001, limit=20)

# Calculate win rate from history
wins = sum(1 for race in history if race['result_no'] == 1)
win_rate = wins / len(history) if history else 0.0
```

**Parameters**:
- `horse_id` (int): Horse identifier
- `limit` (int): Maximum number of races to return (default: 100)

**Returns**: List[RaceHistory] - Sorted by race_date (newest first)
**Caching**: @st.cache_data

---

#### `get_all_races() → List[RaceInfo]`
Get all races in database (used for historical data queries).

```python
from app.queries import get_all_races

all_races = get_all_races()
print(f"Total races in database: {len(all_races)}")
```

**Parameters**: None
**Returns**: List[RaceInfo] - All races
**Caching**: @st.cache_data
**Performance**: O(n) on all races - use date filters when possible

---

## 🔮 Prediction API Functions

### app/prediction_model.py (Random Forest)

#### `PredictionModel` (Class)

```python
class PredictionModel:
    def __init__(self):
        """Initialize Random Forest model"""

    def train(self, X: np.ndarray, y: np.ndarray) -> Dict[str, Any]:
        """Train model with feature matrix X and labels y

        Returns:
            {
                'accuracy': float,
                'cross_val_scores': List[float],
                'model': RandomForestClassifier
            }
        """

    def predict(self, X: np.ndarray) -> np.ndarray:
        """Predict class for input features

        Args:
            X: Feature matrix (n_samples, n_features)

        Returns:
            Predicted classes [0, 1, 2] for each sample
        """

    def predict_proba(self, X: np.ndarray) -> np.ndarray:
        """Predict probabilities for each class

        Returns:
            Probabilities (n_samples, 3) where each row sums to 1
        """
```

---

### app/prediction_model_lightgbm.py (Advanced Model)

#### `PredictionModelLightGBM` (Class)

```python
class PredictionModelLightGBM:
    def __init__(self):
        """Initialize LightGBM model with TimeSeriesSplit validation"""

    def train(self, X: np.ndarray, y: np.ndarray) -> Dict[str, Any]:
        """Train model with time-series validation

        Returns:
            {
                'accuracy': float,
                'cross_val_scores': List[float],
                'cross_val_std': float,
                'feature_importance': pd.DataFrame,
                'model': LGBMClassifier
            }
        """

    def predict(self, X: np.ndarray) -> np.ndarray:
        """Predict class for input features

        Returns:
            Predicted classes [0, 1, 2]
        """

    def predict_proba(self, X: np.ndarray) -> np.ndarray:
        """Predict probabilities for each class

        Returns:
            Probabilities (n_samples, 3)
        """

    def get_feature_importance(self) -> pd.DataFrame:
        """Get top feature importances

        Returns:
            DataFrame with 'feature' and 'importance' columns
        """
```

---

### app/betting_optimizer.py

#### `BettingOptimizer` (Class)

```python
class BettingOptimizer:
    def __init__(self, win_probability: float, odds: float):
        """Initialize optimizer with prediction and odds

        Args:
            win_probability: Predicted win probability [0, 1]
            odds: Betting odds (JRA format)
        """

    def calculate_kelly_bet(self, bankroll: float, safety_factor: float = 0.25) -> float:
        """Calculate Kelly Criterion bet size

        Args:
            bankroll: Available funds to bet
            safety_factor: Conservative factor [0, 1] (default: 0.25)

        Returns:
            Recommended bet amount in yen
        """

    def calculate_expected_value(self) -> float:
        """Calculate expected value of the bet

        Returns:
            EV (positive = profitable, negative = loss)
        """

    def is_profitable(self) -> bool:
        """Check if bet has positive expected value

        Returns:
            True if EV > 0
        """
```

---

## 🎨 Chart Generation API

### app/charts.py

#### `create_distance_chart(history: List[RaceHistory]) → go.Figure`
Create bar chart of race results by distance.

```python
from app.charts import create_distance_chart

fig = create_distance_chart(race_history)
st.plotly_chart(fig)
```

**Parameters**:
- `history` (List[RaceHistory]): Race history to visualize

**Returns**: Plotly Figure object
**Visualization**: Grouped bar chart (wins/places/shows by distance)

---

#### `create_surface_chart(history: List[RaceHistory]) → go.Figure`
Create chart of race results by surface type.

```python
from app.charts import create_surface_chart

fig = create_surface_chart(race_history)
st.plotly_chart(fig)
```

**Parameters**:
- `history` (List[RaceHistory]): Race history to visualize

**Returns**: Plotly Figure object
**Visualization**: Performance breakdown by 芝/ダ/障害

---

## ⚙️ Configuration

### Environment Variables
Currently no environment variables required. Database path is hardcoded as `data/keiba.db`.

**Future Enhancement**: Consider using `DATABASE_URL` or similar for flexibility.

### Type Checking
Run mypy to validate types:

```bash
mypy app etl scraper metrics --ignore-missing-imports
```

### Code Quality Tools
```bash
# Format code
black app etl scraper metrics --line-length 100

# Check style
flake8 app etl scraper metrics --max-line-length 100

# Type check
mypy app etl scraper metrics --ignore-missing-imports
```

---

## 📚 Usage Examples

### Example 1: Get Race Data for a Date
```python
from app.queries import get_races_by_date_and_course

date = "2025-11-08"
course = "東京"

races = get_races_by_date_and_course(date, course)
for race in races:
    print(f"Race {race['race_no']}: {race['distance_m']}m {race['title']}")
```

### Example 2: Get Horse Statistics
```python
from app.queries import get_horse_details, get_horse_race_history

horse = get_horse_details(horse_id=1001)
history = get_horse_race_history(horse_id=1001, limit=10)

total = len(history)
wins = sum(1 for r in history if r['result_no'] == 1)
win_rate = (wins / total * 100) if total > 0 else 0

print(f"{horse['standardized_name']}: Win rate {win_rate:.1f}%")
```

### Example 3: Make Predictions
```python
from app.features import extract_features
from app.prediction_model_lightgbm import PredictionModelLightGBM

# Extract features for a race
features = extract_features(race_entries)

# Load and predict
model = PredictionModelLightGBM()
probs = model.predict_proba(features)

# Top 3 predictions
for i, prob in enumerate(sorted(enumerate(probs[:, 0]), key=lambda x: x[1], reverse=True)[:3]):
    print(f"{i+1}. Horse #{prob[0]}: {prob[1]*100:.1f}%")
```

---

**Last Updated**: 2025-11-08
**API Version**: 2.0 (TypedDict with Type Safety)
