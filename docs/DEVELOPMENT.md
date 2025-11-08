# Development Guide - keiba-solo-db

## 🛠️ Setup & Environment

### Prerequisites
- Python 3.9 or higher
- [uv](https://docs.astral.sh/uv/) - Python package manager
- Git for version control
- SQLite3 (usually included with Python)

### Installation

1. **Clone the repository**
```bash
git clone <repository-url>
cd keiba-solo-db
```

2. **Install dependencies with uv (automatically creates virtual environment)**
```bash
uv sync
```

3. **Activate virtual environment**
```bash
# macOS/Linux
source .venv/bin/activate
# OR Windows
.venv\Scripts\activate
```

4. **Initialize database**
```bash
python -c "from app.db import init_schema; init_schema()"
```

5. **Start development**
```bash
streamlit run app/Home.py
```

---

## 📦 Project Structure Overview

```
keiba-solo-db/
├── app/                    # Main application code
│   ├── Home.py            # Landing page
│   ├── pages/             # Multi-page views
│   ├── db.py              # Database operations
│   ├── queries.py         # Cached queries
│   ├── charts.py          # Visualization
│   ├── features.py        # Feature engineering
│   ├── prediction_model.py         # ML models
│   ├── betting_optimizer.py        # Betting logic
│   └── __pycache__/       # Auto-generated
│
├── scraper/               # Data collection
│   ├── fetch_calendar.py
│   ├── fetch_card.py
│   ├── fetch_result.py
│   └── ...
│
├── etl/                   # Data transformation
│   ├── upsert_*.py
│   ├── apply_alias.py
│   └── ...
│
├── metrics/               # Analytics
│   └── build_horse_metrics.py
│
├── tests/                 # Test suite
│   ├── test_*.py
│   └── __init__.py
│
├── docs/                  # Documentation
│   ├── INDEX.md
│   ├── ARCHITECTURE.md
│   ├── API.md
│   ├── DEVELOPMENT.md     # This file
│   ├── TESTING.md
│   └── ...
│
├── data/
│   ├── keiba.db          # SQLite database
│   └── logs/             # Operation logs
│
├── requirements.txt       # Dependencies
├── pyproject.toml        # Black, isort, pytest config
├── mypy.ini              # Type checker config
├── .flake8               # Linter config
├── lint.bat / lint.sh    # Code quality scripts
└── README.md             # Project README
```

---

## 🎯 Code Standards

### Type Hints
**All new functions MUST include type hints.**

```python
from typing import List, Optional, Dict, Any
from app.db import RaceInfo, RaceEntry

def calculate_win_rate(entries: List[RaceEntry]) -> float:
    """Calculate win rate from race entries.

    Args:
        entries: List of RaceEntry objects

    Returns:
        Win rate as decimal [0.0, 1.0]
    """
    wins = sum(1 for e in entries if e.get('result_no') == 1)
    return wins / len(entries) if entries else 0.0
```

**Why**:
- IDE autocomplete support
- Catch bugs with mypy type checker
- Clearer function contracts
- Better code documentation

---

### Docstrings
Use Google-style docstrings:

```python
def fetch_race_data(date: str, course: str) -> List[RaceInfo]:
    """Fetch race data for a specific date and course.

    This function queries the database for all races matching
    the given date and venue. Results are cached automatically.

    Args:
        date: Race date in YYYY-MM-DD format
        course: Venue name (e.g., '東京', '京都')

    Returns:
        List of RaceInfo objects containing race details.
        Returns empty list if no races found.

    Raises:
        sqlite3.DatabaseError: If database query fails
        ValueError: If date format is invalid

    Example:
        >>> races = fetch_race_data("2025-11-08", "東京")
        >>> print(f"Found {len(races)} races")
    """
    # Implementation
```

---

### Code Formatting
All code must follow PEP 8 standards enforced by Black:

```bash
# Format code
black app etl scraper metrics --line-length 100

# Check without modifying
black --check app etl scraper metrics --line-length 100
```

**Key Rules**:
- Line length: 100 characters
- 4 spaces for indentation (no tabs)
- Two blank lines between top-level definitions
- One blank line between method definitions

---

### Import Organization
Use isort for consistent import ordering:

```python
# 1. Standard library
import json
import sqlite3
from pathlib import Path
from typing import List, Optional

# 2. Third-party libraries
import numpy as np
import pandas as pd
import streamlit as st
from sklearn.ensemble import RandomForestClassifier

# 3. Local imports
from app.db import get_connection, RaceInfo
from app.features import extract_features
```

---

### Error Handling
Be specific with exceptions - avoid bare `except:`:

```python
# ✅ Good - Specific exception handling
try:
    data = json.loads(response.text)
except json.JSONDecodeError:
    st.error("Invalid JSON response")
    data = {}
except ValueError:
    st.error("Value parsing error")
    data = {}

# ❌ Bad - Catches everything including KeyboardInterrupt
try:
    data = json.loads(response.text)
except:
    pass
```

---

### Resource Management
Always close database connections:

```python
# ✅ Good - Connection always closed
conn = get_connection(read_only=True)
try:
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM races LIMIT 1")
    return cursor.fetchall()
finally:
    conn.close()  # Runs even if exception occurs

# ❌ Bad - Connection may leak if exception occurs
conn = get_connection(read_only=True)
cursor = conn.cursor()
cursor.execute("SELECT * FROM races LIMIT 1")
result = cursor.fetchall()
conn.close()
return result
```

---

## ✅ Code Quality Checks

### Running All Checks
```bash
# Windows
lint.bat

# macOS/Linux
bash lint.sh
```

This runs all three checkers in order: Black → Flake8 → mypy

---

### 1. Black (Code Formatter)
Automatically formats code to PEP 8 standard.

```bash
uv run black app etl scraper metrics --line-length 100
```

**What it fixes**:
- Line length violations
- Whitespace issues
- Quote style consistency
- Indentation problems

---

### 2. Flake8 (Linter)
Checks for style violations and potential bugs.

```bash
uv run flake8 app etl scraper metrics --max-line-length 100
```

**Common issues detected**:
- Unused imports
- Undefined names
- Line too long (>100 chars)
- Trailing whitespace
- Bare except clauses

**Configuration** (.flake8):
```ini
[flake8]
max-line-length = 100
max-complexity = 10
extend-ignore = E203, W503, E501, E701, E704
```

---

### 3. mypy (Type Checker)
Validates type hints for correctness.

```bash
uv run mypy app etl scraper metrics --ignore-missing-imports
```

**What it checks**:
- Type hint accuracy
- Function argument types
- Return value types
- Type compatibility

**Configuration** (mypy.ini):
```ini
[mypy]
python_version = 3.9
warn_return_any = True
check_untyped_defs = True
strict_equality = True
ignore_missing_imports = True
```

---

## 📝 Adding New Features

### Step 1: Create Feature Branch
```bash
git checkout -b feature/your-feature-name
```

**Branch naming conventions**:
- `feature/` - New functionality
- `fix/` - Bug fixes
- `refactor/` - Code improvements
- `docs/` - Documentation updates
- `test/` - Test additions

---

### Step 2: Implement Feature
Write your code following standards above:
- Include type hints
- Add docstrings
- Use try-finally for resources
- Specific exception handling

---

### Step 3: Run Code Quality Checks
```bash
# Windows
lint.bat

# macOS/Linux
bash lint.sh
```

Fix any issues until all checks pass.

---

### Step 4: Write Tests
Add test cases to `tests/` folder:
```python
# tests/test_my_feature.py
import pytest
from app.my_module import my_function

def test_my_function_with_valid_input():
    result = my_function("input")
    assert result == "expected"

def test_my_function_with_invalid_input():
    with pytest.raises(ValueError):
        my_function(None)
```

Run tests:
```bash
uv run pytest tests/test_my_feature.py -v
```

---

### Step 5: Commit & Push
```bash
git add app/my_module.py tests/test_my_feature.py
git commit -m "feat: Add new feature description"
git push origin feature/your-feature-name
```

**Commit message format**:
- `feat:` - New feature
- `fix:` - Bug fix
- `refactor:` - Code refactoring
- `docs:` - Documentation
- `test:` - Tests
- `chore:` - Maintenance

---

### Step 6: Pull Request
Create a PR on GitHub with:
- **Title**: Clear description of changes
- **Description**:
  - What changed
  - Why it changed
  - How to test it
- **Tests**: Include test results or screenshots

---

## 🐛 Common Debugging Scenarios

### Scenario 1: "database is locked" Error
**Problem**: Connection not properly closed

**Solution**:
```python
# Ensure try-finally block
conn = get_connection()
try:
    # ... your code
finally:
    conn.close()
```

---

### Scenario 2: Type Checker Warnings
**Problem**: mypy reports type errors

**Solution**:
```bash
# Run mypy to see exact errors
python -m mypy app --show-error-codes

# Fix type hints
def my_func(x: int) -> str:
    return str(x)  # ✅ Returns str, type matches
```

---

### Scenario 3: Streamlit Cache Issues
**Problem**: Changes not reflected, data seems stale

**Solution**:
```bash
# Clear Streamlit cache
streamlit cache clear

# Or use @st.cache_data with ttl parameter
@st.cache_data(ttl=3600)  # Refresh every hour
def fetch_data():
    return get_races()
```

---

### Scenario 4: Import Errors
**Problem**: "ModuleNotFoundError: No module named..."

**Solution**:
```bash
# Ensure current directory is project root
pwd  # Should be keiba-solo-db/

# Reinstall dependencies
pip install -r requirements.txt

# Check Python path
python -c "import sys; print(sys.path)"
```

---

## 📚 Additional Resources

### Type Hints Documentation
- [Python typing module](https://docs.python.org/3/library/typing.html)
- [TypedDict guide](https://docs.python.org/3/library/typing.html#typing.TypedDict)
- [mypy documentation](https://mypy.readthedocs.io/)

### Code Quality Tools
- [Black documentation](https://black.readthedocs.io/)
- [Flake8 rules](https://www.flake8rules.com/)
- [PEP 8 style guide](https://pep8.org/)

### Streamlit
- [Streamlit docs](https://docs.streamlit.io/)
- [Caching decorators](https://docs.streamlit.io/library/api-reference/performance)
- [Session state](https://docs.streamlit.io/library/api-reference/session-state)

### SQLite
- [SQLite documentation](https://www.sqlite.org/docs.html)
- [Python sqlite3 module](https://docs.python.org/3/library/sqlite3.html)

---

## 🚀 Performance Optimization Tips

### 1. Use Streamlit Caching
```python
# Cache expensive initialization
@st.cache_resource
def get_model():
    return PredictionModel()  # Runs once per session

# Cache data fetching
@st.cache_data
def fetch_races(date):
    return queries.get_races(date)
```

### 2. Optimize Database Queries
```python
# ❌ Inefficient - N+1 queries
for horse_id in horse_ids:
    horse = queries.get_horse_details(horse_id)  # Multiple queries!

# ✅ Efficient - Single query
horses = queries.get_horses_by_ids(horse_ids)
```

### 3. Use Connection Pooling (Future)
Currently single-connection, but consider:
```python
from sqlalchemy import create_engine
engine = create_engine('sqlite:///data/keiba.db', pool_size=5)
```

---

## 📋 Checklist for New Features

- [ ] Feature implemented with type hints
- [ ] Docstrings added (Google style)
- [ ] Code formatted with Black
- [ ] Flake8 passes without warnings
- [ ] mypy passes type checking
- [ ] Tests written and passing
- [ ] No resource leaks (connections closed)
- [ ] Error handling is specific (not bare except)
- [ ] Performance considered (caching where needed)
- [ ] Documentation updated

---

**Last Updated**: 2025-11-08
**Standards Version**: 1.0 (Professional)
