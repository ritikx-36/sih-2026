"""
Annual / seasonal performance — month-by-month.

Two complementary views of the same TMY:

* ``annual_energy`` — the *energy* answer. One **continuous 8760-hour** heated run
  per shelter, with the auxiliary heating bucketed by calendar month. This is the
  physically faithful annual total: the thermal mass carries real heat from the fat
  sunny days into the cold ones, exactly as it does in the field. (A representative
  day, being a monthly *average* day, flattens away those sunny peaks and so badly
  over-states heating for storage-heavy passive-solar designs — ~3.7× here.) A full
  year runs in ~2.5 s at the engine's native 60 s step, so there is no reason to
  approximate the number that ends up on the slide.

* ``annual_profile`` — the *comfort* answer. For each month we collapse that month's
  weather to a single representative day (mean by hour-of-day) and read the comfort
  curve off it. A representative day is the right lens for "what does a typical day
  in this month feel like?" — a clean daily temperature cycle instead of a noisy
  full-month scatter — and comfort (a time-in-band fraction) is not distorted by the
  averaging the way stored-heat energy is.
"""
from __future__ import annotations

from typing import Dict, Iterable, List, Optional

from . import climate, comfort, engine
from .geometry import Shelter


def annual_energy(
    cs_full: climate.ClimateSeries,
    shelter: Shelter,
    setpoint: float,
    dt: float = 60.0,
) -> Dict[str, object]:
    """
    Auxiliary heating over a full year, from **one continuous 8760-hour** simulation.

    Runs the shelter heated to ``setpoint`` against the whole measured series in one
    pass (so thermal storage coasts naturally across days and seasons), then buckets
    the integrated auxiliary energy by calendar month. Recording every step
    (``output_dt=dt``) makes the monthly buckets exact — their sum equals the run's
    integrated ``aux_heating`` to rounding.

    Returns ``month`` (1–12), ``aux_kwh`` (per-month total kWh, calendar-correct),
    and ``annual_kwh`` (the exact integrated year total). Divide ``aux_kwh`` by each
    month's day count for a kWh/day figure.

    Note: the run cold-starts on 1 Jan with every node at ambient, so January carries
    a small (~2 % of the annual) mass warm-up load — a mild, honest conservatism (a
    shelter first heated in deep winter), not a modelling error.
    """
    r = engine.simulate(shelter, cs_full, dt=dt, heating_setpoint=setpoint, output_dt=dt)
    per_step_kwh = r.flux["aux"] * dt / 3.6e6          # exact: energy added each step
    month_of = r.index.month.to_numpy()
    aux_kwh = [float(per_step_kwh[month_of == m].sum()) for m in range(1, 13)]
    return {
        "month": list(range(1, 13)),
        "aux_kwh": aux_kwh,
        "annual_kwh": float(r.energies["aux_heating"]),
    }


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

    ``comfort``/``night_low`` are the intended output here. The ``*_aux`` fields are a
    representative-day heating *estimate*; for the canonical annual energy total use the
    continuous :func:`annual_energy` instead (a representative day over-states stored-heat
    designs — see the module docstring).
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
