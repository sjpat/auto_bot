#!/bin/bash

echo "🧪 Running Trading Bot Test Suite"
echo "=================================="

# Set test environment
export PYTHONPATH="${PYTHONPATH}:$(pwd)"
export TESTING=true
export KALSHI_DEMO=true

# Run tests with coverage
pytest tests/ \
    -v \
    --cov=src \
    --cov-report=term-missing \
    --cov-report=html:htmlcov \
    --tb=short \
    "$@"

# Check exit code
if [ $? -eq 0 ]; then
    echo ""
    echo "✅ All tests passed!"
    echo "📊 Coverage report: htmlcov/index.html"
else
    echo ""
    echo "❌ Some tests failed"
    exit 1
fi
