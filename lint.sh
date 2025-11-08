#!/bin/bash
# Code quality check and format script

set -e

echo "======================================"
echo "Code Quality Check & Format"
echo "======================================"

# Color output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# 1. Black（コード整形）
echo -e "\n${YELLOW}1. Running black (code formatter)...${NC}"
black app/ etl/ scraper/ metrics/ --line-length 100
echo -e "${GREEN}✓ Black completed${NC}"

# 2. Flake8（スタイルチェック）
echo -e "\n${YELLOW}2. Running flake8 (style checker)...${NC}"
if flake8 app/ etl/ scraper/ metrics/ --max-line-length 100; then
    echo -e "${GREEN}✓ Flake8 passed${NC}"
else
    echo -e "${RED}✗ Flake8 failed (see above)${NC}"
    exit 1
fi

# 3. mypy（型チェック）
echo -e "\n${YELLOW}3. Running mypy (type checker)...${NC}"
if mypy app/ etl/ scraper/ metrics/ --ignore-missing-imports; then
    echo -e "${GREEN}✓ mypy passed${NC}"
else
    echo -e "${YELLOW}⚠ mypy warnings detected (see above)${NC}"
fi

echo -e "\n${GREEN}======================================"
echo "Code quality checks completed!"
echo "======================================${NC}"
