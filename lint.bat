@echo off
REM Code quality check and format script for Windows

echo ======================================
echo Code Quality Check ^& Format
echo ======================================

REM 1. Black (code formatter)
echo.
echo 1. Running black (code formatter)...
python -m black app etl scraper metrics --line-length 100
if errorlevel 1 (
    echo Black failed
    exit /b 1
)
echo [OK] Black completed

REM 2. Flake8 (style checker)
echo.
echo 2. Running flake8 (style checker)...
python -m flake8 app etl scraper metrics --max-line-length 100
if errorlevel 1 (
    echo [WARNING] Flake8 detected issues
) else (
    echo [OK] Flake8 passed
)

REM 3. mypy (type checker)
echo.
echo 3. Running mypy (type checker)...
python -m mypy app etl scraper metrics --ignore-missing-imports
if errorlevel 1 (
    echo [WARNING] mypy detected issues
) else (
    echo [OK] mypy passed
)

echo.
echo ======================================
echo Code quality checks completed!
echo ======================================
