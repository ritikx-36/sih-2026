"""
Test suite for Thermal-Shelter engine verification.

Wraps the validation checks from scripts/validate.py as pytest tests.
Run with: pytest tests/ -v
"""
import sys
import os

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest
import numpy as np
from thermalshelter.geometry import box_shelter
from scripts.validate import (
    check_steady,
    check_closure,
    check_transient,
    check_convergence,
    coefficients,
)


def test_steady_state_validation():
    """
    Verify engine matches UA·ΔT hand calculation.

    With no sun and no sky cooling, the settled indoor temperature
    must equal ambient in free-float, and the heated load must match
    the textbook UA·ΔT loss coefficient.
    """
    shelter = box_shelter()
    c = coefficients(shelter)
    result = check_steady(shelter, c)

    assert result["passed"], (
        f"Steady-state validation failed: {result['detail']}\n"
        f"The engine's settled load should match UA·ΔT hand calculation."
    )


def test_first_law_closure():
    """
    Verify energy conservation (first law of thermodynamics).

    Over a free-float run, the change in stored energy must equal
    the net heat that crossed the envelope boundary.
    """
    shelter = box_shelter()
    c = coefficients(shelter)
    result = check_closure(shelter, c)

    assert result["passed"], (
        f"First-law closure failed: {result['detail']}\n"
        f"Energy accounting error indicates a bug in the balance equations."
    )


def test_transient_vs_independent_ode():
    """
    Verify transient solution against independent ODE solver.

    The engine's indoor temperature curve must track a high-accuracy
    SciPy RK45 integration of the same RC network to within 0.1 °C.
    """
    shelter = box_shelter()
    c = coefficients(shelter)
    result = check_transient(shelter, c)

    assert result["passed"], (
        f"Transient validation failed: {result['detail']}\n"
        f"Large error vs independent solver suggests integration bug."
    )


def test_time_step_convergence():
    """
    Verify grid convergence (time-step independence).

    The shipped 60-second time step must be on the converged plateau
    (within 1% of the dt→0 limit), proving the result is physics, not
    a numerical artifact.
    """
    result = check_convergence()

    assert result["passed"], (
        f"Grid convergence failed: {result['detail']}\n"
        f"The 60s time step is not converged; reduce dt or investigate stability."
    )


def test_all_validation_checks():
    """
    Meta-test: run all four validation checks and report overall status.

    This ensures the full validation suite passes in one pytest run.
    """
    shelter = box_shelter()
    c = coefficients(shelter)

    results = [
        check_steady(shelter, c),
        check_closure(shelter, c),
        check_transient(shelter, c),
        check_convergence(),
    ]

    failures = [r for r in results if not r["passed"]]

    if failures:
        msg = "\n".join([f"  ❌ {r['name']}: {r['detail']}" for r in failures])
        pytest.fail(f"\n{len(failures)}/{len(results)} validation checks failed:\n{msg}")

    # All passed
    print(f"\n✅ All {len(results)} validation checks passed:")
    for r in results:
        print(f"  ✓ {r['name']}")


# --- Basic smoke tests for core modules ---

def test_shelter_creation():
    """Verify basic shelter geometry construction."""
    shelter = box_shelter(
        length=6.0,
        width=4.0,
        height=2.6,
        window_wall_ratio=0.30,
        infiltration_ach=0.5,
    )

    assert shelter.volume == pytest.approx(6.0 * 4.0 * 2.6)
    assert shelter.floor_area == pytest.approx(6.0 * 4.0)
    assert len(shelter.walls) == 4
    assert shelter.window_area > 0  # Should have windows


def test_shelter_invalid_dimensions():
    """Verify shelter construction rejects invalid dimensions."""
    with pytest.raises(ValueError, match="positive"):
        box_shelter(length=0.0, width=4.0, height=2.6)

    with pytest.raises(ValueError, match="positive"):
        box_shelter(length=6.0, width=-1.0, height=2.6)

    with pytest.raises(ValueError, match="positive"):
        box_shelter(length=6.0, width=4.0, height=0.0)


def test_shelter_orientation_validation():
    """Verify orientation parameter is properly validated and normalized."""
    # Valid orientations should work
    shelter1 = box_shelter(orientation=180.0)
    assert shelter1 is not None

    shelter2 = box_shelter(orientation=0.0)
    assert shelter2 is not None

    shelter3 = box_shelter(orientation=360.0)
    assert shelter3 is not None

    # Large values should be normalized via modulo
    shelter4 = box_shelter(orientation=720.0)  # Should normalize to 0
    assert shelter4 is not None

    shelter5 = box_shelter(orientation=-90.0)  # Should normalize to 270
    assert shelter5 is not None

    # Non-numeric orientation should raise ValueError
    with pytest.raises(ValueError, match="must be a number"):
        box_shelter(orientation="south")  # type: ignore


def test_climate_synthetic_day():
    """Verify synthetic climate generation."""
    from thermalshelter.climate import synthetic_day, LEH

    clim = synthetic_day(LEH, days=2, freq_minutes=60)

    assert len(clim.data) == 2 * 24  # 2 days, hourly
    assert clim.temp_air.min() < clim.temp_air.max()  # Should have variation
    assert "temp_air" in clim.data.columns
    assert "wind_speed" in clim.data.columns
    assert "dewpoint" in clim.data.columns


def test_engine_basic_simulation():
    """Verify engine runs without errors and produces valid output."""
    from thermalshelter.climate import ladakh_winter_day
    from thermalshelter.engine import simulate

    shelter = box_shelter(window_wall_ratio=0.30, infiltration_ach=0.5)
    clim = ladakh_winter_day(days=2, freq_minutes=60)

    result = simulate(shelter, clim, heating_setpoint=20.0)

    assert len(result.T_in) > 0
    assert np.all(np.isfinite(result.T_in))  # No NaN or inf
    assert result.energies["aux_heating"] >= 0  # Non-negative heating
    assert result.n_days == pytest.approx(2.0, rel=0.03)  # Allow 3% tolerance for exact hour boundaries


def test_coefficients_calculation():
    """Verify thermal coefficients are computed correctly."""
    shelter = box_shelter()
    c = coefficients(shelter)

    # All conductances should be positive
    assert c["C_air"] > 0
    assert c["C_m"] > 0
    assert c["G_in"] > 0
    assert c["G_out_air"] > 0
    assert c["G_win"] >= 0
    assert c["G_inf"] > 0


if __name__ == "__main__":
    # Allow running directly: python tests/test_engine.py
    pytest.main([__file__, "-v"])
