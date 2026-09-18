# Thermal-Shelter Testing Guide

## Running Tests

### Install pytest
```bash
pip install pytest
```

### Run all tests
```bash
pytest tests/ -v
```

### Run specific test
```bash
pytest tests/test_engine.py::test_steady_state_validation -v
```

### Run with coverage
```bash
pip install pytest-cov
pytest tests/ --cov=thermalshelter --cov-report=html
```

## What Gets Tested

### Core Verification (4 checks)
1. **Steady-state validation** - Engine matches UA·ΔT hand calculation
2. **First-law closure** - Energy conservation verified
3. **Transient vs ODE** - Matches independent SciPy solver (0.006 °C)
4. **Grid convergence** - Time-step independence verified

### Smoke Tests
- Shelter geometry construction
- Invalid input rejection
- Climate data generation
- Basic simulation runs
- Coefficient calculations

## Quick Test
```bash
# Run just the validation suite
pytest tests/test_engine.py::test_all_validation_checks -v
```

Expected output:
```
✅ All 4 validation checks passed:
  ✓ 1. Steady state = UA·ΔT hand-calc
  ✓ 2. First-law energy closure
  ✓ 3. Transient vs independent ODE
  ✓ 4. Time-step convergence
```

## Before Demo Day
Run the full suite once to confirm everything passes:
```bash
pytest tests/ -v
```

All tests should pass. If any fail, the error messages will guide you to the issue.
