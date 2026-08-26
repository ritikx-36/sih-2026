"""
Annual / seasonal performance — month-by-month, without a full-year simulation.

The engine's air node is stiff (it needs ~60 s steps), so simulating 8760 continuous
hours is slow and buys no design-relevant fidelity. Instead, for each calendar month
we collapse that month's real weather (TMY) to a single *representative day* (mean by
hour-of-day) and run three short sims — free-floating design, heated design, heated
baseline. Twelve of these run in ~1 s total at the same 60 s fidelity, and together
they answer the question a single winter clip can't: *is it comfortable all year, and
how much heating does each month actually need?*
"""
from __future__ import annotations

from typing import Dict, Iterable, List, Optional

from . import climate, comfort, engine
from .geometry import Shelter


def annual_profile(
    cs_full: climate.ClimateSeries,
    design: Shelter,
    baseline: Shelter,
    setpoint: float,
    vent_high: Optional[float] = None,
    months: Iterable[int] = range(1, 13),
    days: int = 5,
) -> Dict[str, List[float]]:
    """
    Run the design and baseline shelters against a representative day for each month.

    Mirrors the dashboard's single-clip logic exactly: the design free-floats with
    optional venting (its temperature/comfort curve), while the design and baseline are
    each heated to `setpoint` for the auxiliary-energy comparison. Returns lists (one
    entry per month) of daily heating [kWh/day], comfort fraction and night low.
    """
    out: Dict[str, List[float]] = {
        "month": [], "design_aux": [], "baseline_aux": [],
        "comfort": [], "night_low": [],
    }
    for m in months:
        rep = climate.representative_day(cs_full, m, days=days)
        free = engine.simulate(design, rep, vent_high=vent_high)
        design_heated = engine.simulate(design, rep, heating_setpoint=setpoint)
        base_heated = engine.simulate(baseline, rep, heating_setpoint=setpoint)
        cm = comfort.comfort_metrics(free.last_day())
        out["month"].append(int(m))
        out["design_aux"].append(design_heated.energy_per_day()["aux_heating"])
        out["baseline_aux"].append(base_heated.energy_per_day()["aux_heating"])
        out["comfort"].append(cm["comfort_fraction"])
        out["night_low"].append(cm["night_low"])
    return out
