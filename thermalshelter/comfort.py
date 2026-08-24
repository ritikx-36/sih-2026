"""
Thermal-comfort metrics derived from a simulation's indoor temperature.

Turns the raw indoor-temperature curve into the numbers a designer (and an SIH
judge) actually cares about: how warm does it stay, how much of the day is
comfortable, and — the money metric — the post-sunset / dawn low temperature.
"""
from __future__ import annotations

from typing import Dict

import numpy as np

from .engine import SimulationResult


def comfort_metrics(
    result: SimulationResult,
    comfort_low: float = 18.0,
    comfort_high: float = 24.0,
    night_hours: tuple = (18, 8),
) -> Dict[str, float]:
    """Summarise indoor comfort over the simulated (last-day) window."""
    T = result.T_in
    th = result.time_h
    dt_h = float(np.median(np.diff(th))) if th.size > 1 else 1.0

    within = (T >= comfort_low) & (T <= comfort_high)
    below = np.clip(comfort_low - T, 0.0, None)
    above = np.clip(T - comfort_high, 0.0, None)

    hod = result.index.hour + result.index.minute / 60.0
    start, end = night_hours
    is_night = (hod >= start) | (hod < end)
    night_low = float(T[is_night].min()) if np.any(is_night) else float(T.min())

    return {
        "min": float(T.min()),
        "max": float(T.max()),
        "mean": float(T.mean()),
        "night_low": night_low,
        "swing": float(T.max() - T.min()),
        "hours_in_comfort": float(within.sum() * dt_h),
        "comfort_fraction": float(within.mean()),
        "heating_degree_hours": float((below * dt_h).sum()),
        "cooling_degree_hours": float((above * dt_h).sum()),
    }
