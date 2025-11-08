# Documentation Index - keiba-solo-db

Welcome to the keiba-solo-db documentation. This guide will help you navigate all available resources.

## 📚 Documentation Structure

### Getting Started
- **[README.md](../README.md)** - Project overview, installation, and quick start guide

### Core Documentation

#### Architecture & Design
- **[ARCHITECTURE.md](./ARCHITECTURE.md)** - System design, data flow, and module organization
- **[API.md](./API.md)** - TypedDict definitions, function signatures, and type contracts

#### Development Guides
- **[DEVELOPMENT.md](./DEVELOPMENT.md)** - Developer setup, coding standards, and contribution guidelines
- **[TESTING.md](./TESTING.md)** - Testing strategy, pytest configuration, and test execution
- **[CLAUDE.md](./CLAUDE.md)** - AI-assisted development guidelines and autonomous judgment principles

#### Implementation Reviews & Improvements
- **[CRITICAL_IMPROVEMENTS_IMPLEMENTED.md](./CRITICAL_IMPROVEMENTS_IMPLEMENTED.md)** - Major refactoring and feature improvements
- **[DS_CRITICAL_IMPROVEMENTS.md](./DS_CRITICAL_IMPROVEMENTS.md)** - Data science model and feature engineering enhancements
- **[DS_REVIEW.md](./DS_REVIEW.md)** - Detailed data science implementation review

#### Optimization Guides
- **[BETTING_OPTIMIZATION_GUIDE.md](./BETTING_OPTIMIZATION_GUIDE.md)** - Betting strategy optimization and Kelly Criterion implementation
- **[STREAMLIT_CACHE_FIX.md](./STREAMLIT_CACHE_FIX.md)** - Performance optimization through Streamlit caching

#### Test Results & Validation
- **[LOCAL_TEST_RESULTS.md](./LOCAL_TEST_RESULTS.md)** - Test execution results and validation reports

---

## 🎯 Quick Navigation by Role

### 👤 For New Developers
1. Start with [README.md](../README.md) - Installation and project overview
2. Read [ARCHITECTURE.md](./ARCHITECTURE.md) - Understand system design
3. Follow [DEVELOPMENT.md](./DEVELOPMENT.md) - Setup development environment
4. Check [TESTING.md](./TESTING.md) - Run and write tests

### 🔧 For Maintenance & Bug Fixes
1. Review [CRITICAL_IMPROVEMENTS_IMPLEMENTED.md](./CRITICAL_IMPROVEMENTS_IMPLEMENTED.md) - Understand refactoring history
2. Check [API.md](./API.md) - Function signatures and types
3. Look at [LOCAL_TEST_RESULTS.md](./LOCAL_TEST_RESULTS.md) - Validation status
4. Follow [DEVELOPMENT.md](./DEVELOPMENT.md) - Code standards

### 📊 For Data Science Work
1. Start with [DS_CRITICAL_IMPROVEMENTS.md](./DS_CRITICAL_IMPROVEMENTS.md) - Model architecture
2. Review [DS_REVIEW.md](./DS_REVIEW.md) - Detailed analysis
3. Check [BETTING_OPTIMIZATION_GUIDE.md](./BETTING_OPTIMIZATION_GUIDE.md) - Optimization strategies
4. Follow [TESTING.md](./TESTING.md) - Model validation

### 🚀 For Performance Optimization
1. Read [STREAMLIT_CACHE_FIX.md](./STREAMLIT_CACHE_FIX.md) - Caching strategies
2. Review [BETTING_OPTIMIZATION_GUIDE.md](./BETTING_OPTIMIZATION_GUIDE.md) - Algorithm optimization
3. Check [DEVELOPMENT.md](./DEVELOPMENT.md) - Code quality tools

---

## 📋 Key Topics & Where to Find Them

| Topic | Location |
|-------|----------|
| Installation & Setup | [README.md](../README.md) |
| Database Schema | [ARCHITECTURE.md](./ARCHITECTURE.md) |
| Type Definitions | [API.md](./API.md) |
| Code Standards | [DEVELOPMENT.md](./DEVELOPMENT.md) |
| Testing Procedures | [TESTING.md](./TESTING.md) |
| ML Models & Features | [DS_CRITICAL_IMPROVEMENTS.md](./DS_CRITICAL_IMPROVEMENTS.md) |
| Betting Strategy | [BETTING_OPTIMIZATION_GUIDE.md](./BETTING_OPTIMIZATION_GUIDE.md) |
| Performance Tips | [STREAMLIT_CACHE_FIX.md](./STREAMLIT_CACHE_FIX.md) |
| Refactoring History | [CRITICAL_IMPROVEMENTS_IMPLEMENTED.md](./CRITICAL_IMPROVEMENTS_IMPLEMENTED.md) |
| Test Results | [LOCAL_TEST_RESULTS.md](./LOCAL_TEST_RESULTS.md) |

---

## 🛠️ Development Commands

### Code Quality
```bash
# Format and lint check (Windows)
lint.bat

# Format and lint check (Unix/macOS)
bash lint.sh

# Individual tools
black app etl scraper metrics --line-length 100
flake8 app etl scraper metrics --max-line-length 100
mypy app etl scraper metrics --ignore-missing-imports
```

### Testing
```bash
# Run all tests
pytest tests/

# Run with coverage
pytest tests/ --cov=app --cov=etl --cov=scraper --cov=metrics

# Run specific test file
pytest tests/test_pipeline.py -v
```

### Application
```bash
# Initialize database schema
python -c "from app.db import init_schema; init_schema()"

# Run Streamlit app
streamlit run app/Home.py

# Manual ETL workflow
python -m etl.upsert_master
python -m etl.upsert_race
python -m etl.upsert_entry
python -m metrics.build_horse_metrics
```

---

## 📞 Support & Resources

### For Issues
1. Check relevant documentation above
2. Review [LOCAL_TEST_RESULTS.md](./LOCAL_TEST_RESULTS.md) for known issues
3. Check `data/logs/` directory for error logs
4. Refer to [CLAUDE.md](./CLAUDE.md) for autonomous judgment and troubleshooting guidelines

### For Questions
- Architecture questions → [ARCHITECTURE.md](./ARCHITECTURE.md)
- Development questions → [DEVELOPMENT.md](./DEVELOPMENT.md)
- Testing questions → [TESTING.md](./TESTING.md)
- Data science questions → [DS_CRITICAL_IMPROVEMENTS.md](./DS_CRITICAL_IMPROVEMENTS.md)

---

## 📅 Documentation Status

- **Last Updated**: 2025-11-08
- **Python Version**: 3.9+
- **Structure**: Professional enterprise standard
- **Type Checking**: mypy enabled
- **Code Formatting**: Black (line-length: 100)
- **Linting**: Flake8 (max-complexity: 10)

---

**Navigation Tips**: Use Ctrl+F to search this index, or browse the links above to explore specific topics.
