# Testing Guide - keiba-solo-db

## 🧪 Testing Strategy

### Test Structure
Tests are organized by functional area in the `tests/` directory:

```
tests/
├── __init__.py                    # Test suite documentation
├── test_pipeline.py               # Integration tests
├── test_csv_export.py             # CSV functionality
├── test_prediction_page.py        # Streamlit prediction UI
├── test_betting_optimizer.py      # Betting logic
└── test_ds_improvements.py        # ML model validation
```

### Testing Philosophy
- **Unit Tests**: Test individual functions in isolation
- **Integration Tests**: Test complete workflows (e.g., data pipeline)
- **Regression Tests**: Ensure fixes stay fixed
- **Performance Tests**: Validate optimization improvements

---

## 🚀 Running Tests

### Run All Tests
```bash
# Run all tests with verbose output
pytest tests/ -v

# Run with coverage report
pytest tests/ --cov=app --cov=etl --cov=scraper --cov=metrics

# Run with coverage and HTML report
pytest tests/ --cov=app --cov=etl --cov=scraper --cov=metrics --cov-report=html
# Open htmlcov/index.html in browser
```

### Run Specific Test File
```bash
pytest tests/test_pipeline.py -v
pytest tests/test_prediction_page.py::test_model_training -v
```

### Run Tests Matching Pattern
```bash
# Run only prediction-related tests
pytest tests/ -k prediction -v

# Run only data science tests
pytest tests/ -k ds -v

# Run tests excluding slow tests
pytest tests/ -m "not slow" -v
```

### Watch Mode (Auto-rerun on Changes)
```bash
# Install pytest-watch
pip install pytest-watch

# Run tests on file changes
ptw tests/
```

---

## 📝 Writing Tests

### Basic Test Structure
```python
import pytest
from app.queries import get_races_by_date_and_course

def test_get_races_returns_list():
    """Test that get_races returns a list of RaceInfo objects."""
    races = get_races_by_date_and_course("2025-11-08", "東京")

    assert isinstance(races, list)
    if races:
        assert 'race_id' in races[0]
        assert 'race_no' in races[0]
```

### Test with Setup & Teardown
```python
import pytest
import sqlite3

class TestDatabase:
    @pytest.fixture(autouse=True)
    def setup_and_teardown(self):
        """Setup test database before each test."""
        # Setup
        self.conn = sqlite3.connect(':memory:')  # In-memory test DB

        yield  # Test runs here

        # Teardown
        self.conn.close()

    def test_insert_race(self):
        """Test inserting a race into database."""
        cursor = self.conn.cursor()
        cursor.execute("""
            CREATE TABLE races (
                race_id INTEGER PRIMARY KEY,
                race_date TEXT
            )
        """)
        cursor.execute("INSERT INTO races (race_id, race_date) VALUES (1, '2025-11-08')")

        cursor.execute("SELECT COUNT(*) FROM races")
        assert cursor.fetchone()[0] == 1
```

### Parametrized Tests (Test Multiple Cases)
```python
import pytest

@pytest.mark.parametrize("date,course,expected_min_races", [
    ("2025-11-08", "東京", 0),      # May have 0-12 races
    ("2025-11-09", "京都", 0),      # May have 0-12 races
    ("2025-11-10", "福島", 0),      # May have 0-12 races
])
def test_get_races_by_various_dates(date, course, expected_min_races):
    """Test get_races works for different dates and courses."""
    races = get_races_by_date_and_course(date, course)

    assert isinstance(races, list)
    assert len(races) >= expected_min_races
```

### Testing Exceptions
```python
import pytest
from app.db import get_connection

def test_connection_with_invalid_db():
    """Test that invalid database path raises error."""
    with pytest.raises(sqlite3.DatabaseError):
        conn = get_connection()
        # Close it to simulate error condition
        conn.close()
        # Subsequent operations should fail
        conn.execute("SELECT 1")
```

### Mocking External Dependencies
```python
from unittest.mock import patch, MagicMock

@patch('app.queries.get_connection')
def test_get_races_with_mock_db(mock_get_connection):
    """Test get_races with mocked database."""
    # Setup mock
    mock_conn = MagicMock()
    mock_cursor = MagicMock()
    mock_conn.cursor.return_value = mock_cursor
    mock_cursor.fetchall.return_value = [
        {'race_id': 1, 'race_no': 1, 'distance_m': 1000},
        {'race_id': 2, 'race_no': 2, 'distance_m': 1200},
    ]
    mock_get_connection.return_value = mock_conn

    # Test
    races = get_races_by_date_and_course("2025-11-08", "東京")

    # Verify
    assert len(races) == 2
    mock_cursor.close.assert_called()
    mock_conn.close.assert_called()
```

---

## 🧬 Test Coverage

### Generate Coverage Report
```bash
# Run with coverage
pytest tests/ --cov=app --cov=etl --cov=scraper --cov=metrics --cov-report=term-missing

# HTML report
pytest tests/ --cov=app --cov=etl --cov=scraper --cov=metrics --cov-report=html
```

### Interpreting Coverage
```
app/db.py: 85%        # 85% of lines executed in tests
app/queries.py: 92%   # 92% of lines executed
app/features.py: 78%  # 78% of lines executed
```

**Target Coverage**: Aim for 80%+ across all modules. Some areas are harder to test:
- UI code (Streamlit) - harder to test, 50-70% acceptable
- External API calls - mock them, 90%+ expected
- Core logic - aim for 90%+

---

## 📋 Current Test Files

### tests/test_pipeline.py
**Purpose**: Integration tests for data pipeline (scraper → ETL → metrics)

**Test Cases**:
- `test_database_initialization` - Schema creation
- `test_upsert_race_data` - Race data insertion
- `test_metrics_calculation` - Horse metrics computation
- `test_data_consistency` - Referential integrity

**How to Run**:
```bash
pytest tests/test_pipeline.py -v
```

---

### tests/test_csv_export.py
**Purpose**: Validate CSV export functionality

**Test Cases**:
- `test_csv_encoding_utf8` - UTF-8 encoding validation
- `test_csv_headers` - Correct headers present
- `test_csv_data_integrity` - Data matches database
- `test_csv_download_format` - Download response format

**How to Run**:
```bash
pytest tests/test_csv_export.py -v
```

---

### tests/test_prediction_page.py
**Purpose**: Streamlit prediction page interaction tests

**Test Cases**:
- `test_model_selection` - Radio button selection
- `test_model_training` - Training execution
- `test_prediction_display` - Results rendering
- `test_feature_importance` - Feature visualization
- `test_cross_validation_results` - CV metrics display

**How to Run**:
```bash
pytest tests/test_prediction_page.py -v

# Or with model selection
pytest tests/test_prediction_page.py::test_model_training -v
```

---

### tests/test_betting_optimizer.py
**Purpose**: Betting strategy and Kelly Criterion validation

**Test Cases**:
- `test_kelly_criterion_calculation` - Correct bet sizing
- `test_expected_value_positive` - Profitable bets detected
- `test_expected_value_negative` - Losing bets detected
- `test_safety_factor_effect` - Conservative sizing
- `test_bankroll_management` - Bet size limits

**How to Run**:
```bash
pytest tests/test_betting_optimizer.py -v
```

**Example Test**:
```python
from app.betting_optimizer import BettingOptimizer

def test_kelly_criterion_with_positive_ev():
    """Test Kelly Criterion with profitable bet."""
    optimizer = BettingOptimizer(
        win_probability=0.35,  # 35% win probability
        odds=3.5               # 3.5 to 1 odds
    )

    ev = optimizer.calculate_expected_value()
    assert ev > 0, "Should detect profitable bet"

    bet_size = optimizer.calculate_kelly_bet(bankroll=100000)
    assert 0 < bet_size < 100000, "Bet size should be within bankroll"
```

---

### tests/test_ds_improvements.py
**Purpose**: ML model validation and data science improvements

**Test Cases**:
- `test_lightgbm_model_training` - LightGBM training
- `test_random_forest_training` - Random Forest training
- `test_feature_engineering` - 60+ features extracted
- `test_time_series_split` - Proper time validation
- `test_model_comparison` - Model performance comparison
- `test_prediction_probability_sum` - Probabilities sum to 1

**How to Run**:
```bash
pytest tests/test_ds_improvements.py -v

# Or run only LightGBM tests
pytest tests/test_ds_improvements.py -k lightgbm -v
```

**Example Test**:
```python
def test_lightgbm_probabilities_sum_to_one():
    """Test that predicted probabilities sum to 1."""
    from app.prediction_model_lightgbm import PredictionModelLightGBM
    import numpy as np

    model = PredictionModelLightGBM()

    # Create dummy features
    X = np.random.randn(10, 60)  # 10 samples, 60 features

    probs = model.predict_proba(X)

    # Each row should sum to 1.0
    for prob_row in probs:
        assert abs(sum(prob_row) - 1.0) < 1e-6, "Probabilities should sum to 1"
```

---

## 🔍 Debugging Failed Tests

### 1. Run with Verbose Output
```bash
pytest tests/test_file.py::test_function -vv
```

### 2. Print Debug Information
```python
def test_something():
    result = some_function()
    print(f"Result: {result}")  # Will print when test fails
    assert result == expected
```

Run with:
```bash
pytest tests/test_file.py -vv -s  # -s shows print output
```

### 3. Drop into Debugger
```python
import pytest

def test_something():
    result = some_function()
    pytest.set_trace()  # Drops into pdb debugger
    assert result == expected
```

Run with:
```bash
pytest tests/test_file.py --pdb
```

### 4. Use pytest Fixtures for Setup
```python
import pytest

@pytest.fixture
def sample_race_data():
    """Provide sample race data for tests."""
    return {
        'race_id': 1,
        'race_date': '2025-11-08',
        'course': '東京',
        'distance_m': 1000,
    }

def test_process_race(sample_race_data):
    """Test with fixture."""
    result = process_race(sample_race_data)
    assert result is not None
```

---

## 📊 Performance Testing

### Benchmark Queries
```python
import pytest
import time

def test_get_races_performance():
    """Ensure query completes within acceptable time."""
    start = time.time()

    races = get_races_by_date_and_course("2025-11-08", "東京")

    elapsed = time.time() - start
    assert elapsed < 0.5, f"Query took {elapsed}s, should be < 0.5s"
```

### Profile Code
```bash
# Install profiler
pip install line_profiler

# Run with profiling
kernprof -l -v test_script.py
```

---

## 🚨 Common Test Failures & Solutions

### Failure 1: "database is locked"
**Problem**: Concurrent test access to SQLite

**Solution**:
```python
# Use in-memory database for tests
@pytest.fixture
def test_db():
    conn = sqlite3.connect(':memory:')
    # Create schema
    yield conn
    conn.close()
```

---

### Failure 2: "ModuleNotFoundError"
**Problem**: Import path issues

**Solution**:
```bash
# Run from project root
cd keiba-solo-db
pytest tests/

# OR explicitly add path
python -m pytest tests/
```

---

### Failure 3: "Cache inconsistency"
**Problem**: Streamlit cache interference

**Solution**:
```bash
# Clear cache before tests
streamlit cache clear
pytest tests/
```

---

### Failure 4: "stale fixture"
**Problem**: Data from previous test interferes

**Solution**:
```python
@pytest.fixture(autouse=True)
def cleanup():
    """Cleanup between tests."""
    yield
    # Cleanup code here
    database.clear()
```

---

## 📚 Resources

### pytest Documentation
- [Official Documentation](https://docs.pytest.org/)
- [Fixtures](https://docs.pytest.org/en/stable/fixture.html)
- [Parametrization](https://docs.pytest.org/en/stable/example/parametrize.html)
- [Markers](https://docs.pytest.org/en/stable/example/markers.html)

### Testing Best Practices
- [Python Testing with pytest](https://pragprog.com/titles/bopytest/python-testing-with-pytest/)
- [Test-Driven Development](https://en.wikipedia.org/wiki/Test-driven_development)
- [Mocking in Python](https://docs.python.org/3/library/unittest.mock.html)

### Coverage Tools
- [coverage.py Documentation](https://coverage.readthedocs.io/)
- [pytest-cov](https://pytest-cov.readthedocs.io/)

---

## ✅ Test Checklist

When adding new features:
- [ ] Unit tests written for new functions
- [ ] Integration tests for new workflows
- [ ] Edge cases tested (None, empty lists, etc.)
- [ ] Error conditions tested (exceptions)
- [ ] Performance validated (< acceptable threshold)
- [ ] Coverage maintained at 80%+
- [ ] All tests pass locally: `pytest tests/ -v`
- [ ] Tests documented with clear docstrings
- [ ] Mocking used for external dependencies
- [ ] Fixtures created for common setup

---

**Last Updated**: 2025-11-08
**Testing Framework**: pytest 7.4+
**Minimum Coverage**: 80%
