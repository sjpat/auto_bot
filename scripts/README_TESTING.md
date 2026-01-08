# Testing Guide

## Quick Tests

### Run All Unit Tests
```bash
pytest tests/ -v
```

### Run Specific Test File
```bash
pytest tests/test_fee_calculator.py -v
pytest tests/test_risk_manager_critical.py -v
pytest tests/test_spike_detector.py -v
```

### Run With Coverage
```bash
pytest tests/ --cov=src --cov-report=html
open htmlcov/index.html  # View coverage report
```

### Run Quick Validation 
```bash
python scripts/quick_test.py
```

### Run Pre-Deployment Check
```bash
python scripts/pre_deploy_check.py
```

