"""
Demo / verification: does passive design actually keep a Ladakh shelter warmer?

Simulates two shelters through the same clear Leh winter days:

    BASELINE  — uninsulated stone, single glazing, leaky (like an existing hut)
    PASSIVE   — insulated envelope, double glazing, tight, large south glazing
                (30% WWR) + a 1000 L water wall for thermal mass

and reports indoor temperature, comfort, and the auxiliary heating energy each
would need to hold 20 °C. Saves a comparison chart to outputs/demo_curve.png.

Run:  ./.venv/bin/python scripts/run_demo.py
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

from thermalshelter.climate import ladakh_winter_day
from thermalshelter.comfort import comfort_metrics
from thermalshelter.engine import SimulationResult, simulate
from thermalshelter.geometry import (
    SINGLE_GLAZING, UNINSULATED_STONE, ThermalMass, box_shelter,
    make_construction,
)
from thermalshelter.materials import get_material


def last_full_day(res):
    """Slice a run to its last complete calendar day (a converged diurnal cycle).

    The deep thermal mass (water wall + envelope) has a multi-day time constant,
    so the first days are warm-up; the final full day is the steady cycle a
    shelter in continuous winter use would actually settle into.
    """
    dates = np.array([ts.date() for ts in res.index])
    uniq, counts = np.unique(dates, return_counts=True)
    full = uniq[counts == counts.max()]        # drop any truncated tail day
    m = dates == full[-1]
    return SimulationResult(
        name=res.name, time_h=res.time_h[m], index=res.index[m],
        T_in=res.T_in[m], T_mass=res.T_mass[m], T_out=res.T_out[m], T_sky=res.T_sky[m],
        T_storage={k: v[m] for k, v in res.T_storage.items()},
        flux={k: v[m] for k, v in res.flux.items()},
        energies=res.energies, n_days=res.n_days,
    )


def baseline_shelter():
    bare_roof = make_construction("Bare timber roof",
                                  [("Softwood timber (pine)", 0.04)])
    bare_floor = make_construction("Bare concrete floor",
                                   [("Dense concrete", 0.15)])
    return box_shelter(
        wall=UNINSULATED_STONE, roof=bare_roof, floor=bare_floor,
        glazing=SINGLE_GLAZING, window_wall_ratio=0.12,
        infiltration_ach=2.0, name="Baseline (existing-style hut)",
    )


def passive_shelter():
    water_wall = ThermalMass(
        name="Water wall (1000 L)", material=get_material("Water (storage wall)"),
        volume=1.0, surface_area=6.0,
    )
    return box_shelter(
        window_wall_ratio=0.30, infiltration_ach=0.5,
        thermal_mass=[water_wall], name="Passive (area-specific design)",
    )


def report(tag, result, aux_kwh):
    m = comfort_metrics(result)
    e = result.energy_per_day()
    print(f"\n=== {tag} ===")
    print(f"  indoor temp:  min {m['min']:+5.1f}  night-low {m['night_low']:+5.1f}  "
          f"max {m['max']:+5.1f}  mean {m['mean']:+5.1f} °C")
    print(f"  comfort:      {m['comfort_fraction']*100:4.0f}% of day in 18–24 °C  "
          f"(swing {m['swing']:.1f} °C)")
    print(f"  solar gain:   {e['solar_windows']:.1f} kWh/day via windows")
    print(f"  losses:       envelope {e['envelope_conduction']:+.1f}  "
          f"window {e['window_conduction']:+.1f}  infiltration {e['infiltration']:+.1f} kWh/day")
    print(f"  AUX HEATING to hold 20 °C:  {aux_kwh:.1f} kWh/day")


def main():
    N_DAYS = 5
    climate = ladakh_winter_day(days=N_DAYS, freq_minutes=30)

    runs, results, aux = {}, {}, {}
    for tag, shelter in [("BASELINE", baseline_shelter()),
                         ("PASSIVE", passive_shelter())]:
        free = simulate(shelter, climate, vent_high=24.0)     # free-float + night/​day venting
        heated = simulate(shelter, climate, heating_setpoint=20.0)
        runs[tag] = free
        results[tag] = last_full_day(free)          # last day, for comfort metrics
        aux[tag] = heated.energy_per_day()["aux_heating"]
        report(tag, results[tag], aux[tag])

    saving = (1 - aux["PASSIVE"] / aux["BASELINE"]) * 100 if aux["BASELINE"] else 0
    print(f"\n>>> Passive design cuts heating energy by {saving:.0f}%  "
          f"({aux['BASELINE']:.1f} -> {aux['PASSIVE']:.1f} kWh/day)\n")

    # ---- money chart: multi-day transient from a cold start -------------------
    # Both shelters start cold; the passive design charges its thermal mass over
    # successive sunny days and climbs into the comfort band, while the baseline
    # hut tracks the freezing ambient. This is the transient the PS asks for.
    b, p = runs["BASELINE"], runs["PASSIVE"]
    xb, xp = b.time_h / 24.0, p.time_h / 24.0
    wall = next(iter(p.T_storage.values()), None)

    fig, ax = plt.subplots(figsize=(11, 5.5))
    ax.axhspan(18, 24, color="#8fd19e", alpha=0.25, label="comfort band (18–24 °C)")
    ax.axhline(0, color="#bbb", lw=0.8)                       # freezing line
    ax.plot(xb, b.T_out, color="#888", lw=1.3, ls="--", label="ambient air")
    if wall is not None:
        ax.plot(xp, wall, color="#1f77b4", lw=1.3, ls="-.", alpha=0.5,
                label="water-wall store (charging)")
    ax.plot(xb, b.T_in, color="#d9534f", lw=2.2, label="indoor — baseline hut")
    ax.plot(xp, p.T_in, color="#1f77b4", lw=2.6, label="indoor — passive design")

    ax.text(0.985, 0.045,
            f"Passive design needs {saving:.0f}% less\nheating to hold 20 °C",
            transform=ax.transAxes, ha="right", va="bottom", fontsize=10.5,
            bbox=dict(boxstyle="round,pad=0.4", fc="#eef6ee", ec="#8fd19e"))

    ax.set_xlabel("day  (clear Leh winter, both shelters from the same cold start)")
    ax.set_ylabel("temperature [°C]")
    ax.set_title("Indoor temperature over 5 clear winter days\n"
                 "baseline hut vs area-specific passive design")
    ax.set_xlim(0, N_DAYS)
    ax.set_xticks(range(0, N_DAYS + 1))
    ax.grid(alpha=0.25)
    ax.legend(loc="upper left", fontsize=9, ncol=2)
    fig.tight_layout()

    os.makedirs("outputs", exist_ok=True)
    out = os.path.abspath("outputs/demo_curve.png")
    fig.savefig(out, dpi=130)
    print(f"Chart saved -> {out}")


if __name__ == "__main__":
    main()
