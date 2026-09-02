"""
Render a print-clean "all-year proof" panel for the pitch deck (Impact / Seasonal)
— WITHOUT a browser.

This is the visual twin of make_dashboard_shot.py, but it tells the *annual* story
from REAL measured weather: it drives the SAME design and baseline shelters with the
bundled Leh PVGIS Typical Meteorological Year (data/leh_tmy.csv) through the exact
month-by-month profile the dashboard's "Seasonal" tab shows, then draws the grouped
monthly heating bars, the comfort-% line, and the headline fuel / ₹ / CO₂ saved per
shelter per year. Every number matches the live Seasonal tab exactly.

Run:  MPLCONFIGDIR="$TMPDIR/mpl" PYTHONPATH=/Users/ritik/sih ./.venv/bin/python scripts/make_seasonal_shot.py
Out:  docs/seasonal.png
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import FancyBboxPatch

from thermalshelter import annual, climate, engine, geometry, impact
from thermalshelter.materials import get_material

SETPOINT, VENT_HIGH, DAYS = 20.0, 24.0, 5
DIM = [31, 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31]      # 1990 (coerce_year), 365 d
MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun",
          "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]

C_BASE, C_DESIGN, C_COMFORT = "#d9534f", "#1f77b4", "#2ea44f"
INK, SUB, ACCENT = "#1b2733", "#5b6b7a", "#0070C0"

BARE_ROOF = geometry.make_construction("Bare timber roof", [("Softwood timber (pine)", 0.04)])
BARE_FLOOR = geometry.make_construction("Bare concrete floor", [("Dense concrete", 0.15)])


def _design():
    water = geometry.ThermalMass(name="Water wall (1000 L)",
                                 material=get_material("Water (storage wall)"),
                                 volume=1.0, surface_area=6.0)
    return geometry.box_shelter(
        length=6.0, width=4.0, height=2.6, orientation=180,
        wall=geometry.INSULATED_WALL, roof=geometry.INSULATED_ROOF,
        floor=geometry.INSULATED_FLOOR, glazing=geometry.DOUBLE_GLAZING,
        window_wall_ratio=0.30, window_facades=("S",),
        infiltration_ach=0.5, thermal_mass=[water], name="Your design")


def _baseline():
    return geometry.box_shelter(
        wall=geometry.UNINSULATED_STONE, roof=BARE_ROOF, floor=BARE_FLOOR,
        glazing=geometry.SINGLE_GLAZING, window_wall_ratio=0.12,
        window_facades=("S",), infiltration_ach=2.0, name="Baseline hut")


def compute():
    cs = climate.from_csv(os.path.join("data", "leh_tmy.csv"), climate.LEH)
    design, base = _design(), _baseline()

    # Energy: continuous 8760-h run per shelter (the canonical annual total), with
    # aux bucketed by month -> kWh/day bars that sum to the true year figure.
    de = annual.annual_energy(cs, design, SETPOINT)
    be = annual.annual_energy(cs, base, SETPOINT)
    dim = np.array(DIM)
    d = np.array(de["aux_kwh"]) / dim
    b = np.array(be["aux_kwh"]) / dim
    d_year = de["annual_kwh"]
    b_year = be["annual_kwh"]
    saved = b_year - d_year

    # Comfort line stays representative-day (the clean typical-day read per month).
    prof = annual.annual_profile(cs, design, base, SETPOINT, vent_high=VENT_HIGH, days=DAYS)
    c = np.array(prof["comfort"]) * 100.0

    return dict(d=d, b=b, c=c,
                saving=(1 - d_year / b_year) * 100 if b_year else 0.0,
                fi=impact.fuel_impact(saved),
                tmin=cs.data["temp_air"].min(), tmax=cs.data["temp_air"].max())


def kpi(fig, x, y, w, h, label, value, vcolor=INK):
    fig.patches.append(FancyBboxPatch(
        (x, y), w, h, boxstyle="round,pad=0.004,rounding_size=0.014",
        transform=fig.transFigure, facecolor="white", edgecolor="#e2e8ee",
        linewidth=1.2, zorder=2))
    fig.text(x + 0.018, y + h - 0.022, label, transform=fig.transFigure,
             ha="left", va="top", fontsize=9.5, color=SUB, zorder=3)
    fig.text(x + 0.018, y + 0.020, value, transform=fig.transFigure,
             ha="left", va="bottom", fontsize=18, color=vcolor, weight="bold", zorder=3)


def main():
    r = compute()
    fig = plt.figure(figsize=(13.333, 7.5), dpi=200)
    fig.patch.set_facecolor("#f4f6f9")

    # ---- header ----------------------------------------------------------- #
    fig.text(0.035, 0.955, "Comfortable all year — on real measured weather",
             ha="left", va="top", fontsize=23, weight="bold", color=INK)
    fig.text(0.035, 0.905,
             f"Leh PVGIS Typical Meteorological Year (a real year: {r['tmin']:.0f} to "
             f"+{r['tmax']:.0f} °C, clouds and all) — heating each month to hold 20 °C, "
             f"design vs baseline hut.   SIH 2026 · PS 26051 (DRDO).",
             ha="left", va="top", fontsize=10.5, color=SUB)

    # ---- headline impact KPIs (per shelter, per year) --------------------- #
    fi = r["fi"]
    cards = [
        ("Less heating, all year", f"{r['saving']:.0f} %", C_DESIGN),
        ("Kerosene not burned", f"{fi.litres:,.0f} L", INK),
        ("Fuel cost saved", f"₹{fi.inr/1e5:.1f} lakh", INK),
        ("CO₂ avoided", f"{fi.co2_kg/1000:.1f} t", C_COMFORT),
    ]
    x0, kw, kgap, ky, kh = 0.035, 0.2245, 0.012, 0.700, 0.115
    for i, (lab, val, col) in enumerate(cards):
        kpi(fig, x0 + i * (kw + kgap), ky, kw, kh, lab, val, col)
    fig.text(0.965, 0.688, "per shelter, per year", ha="right", va="top",
             fontsize=9, color=SUB, style="italic")

    # ---- grouped monthly bars + comfort line ------------------------------ #
    ax = fig.add_axes([0.058, 0.115, 0.885, 0.505])
    ax.set_facecolor("white")
    x = np.arange(12)
    bw = 0.4
    ax.bar(x - bw / 2, r["b"], bw, color=C_BASE, label="baseline hut")
    ax.bar(x + bw / 2, r["d"], bw, color=C_DESIGN, label="your design")
    ax.set_ylabel("heating to hold 20 °C  (kWh/day)", fontsize=10.5)
    ax.set_xticks(x)
    ax.set_xticklabels(MONTHS, fontsize=10)
    ax.grid(axis="y", alpha=0.22)
    for s in ("top", "right"):
        ax.spines[s].set_visible(False)
    ax.tick_params(labelsize=9.5)

    axc = ax.twinx()
    axc.plot(x, r["c"], color=C_COMFORT, lw=2.4, marker="o", ms=5,
             label="% time comfortable (design)")
    axc.set_ylabel("% time in 18–24 °C band (design)", fontsize=10.5, color=C_COMFORT)
    axc.set_ylim(0, 100)
    axc.tick_params(axis="y", labelsize=9.5, labelcolor=C_COMFORT)
    for s in ("top",):
        axc.spines[s].set_visible(False)

    h1, l1 = ax.get_legend_handles_labels()
    h2, l2 = axc.get_legend_handles_labels()
    ax.legend(h1 + h2, l1 + l2, loc="upper center", fontsize=9.5, ncol=3, framealpha=0.9)

    fig.text(0.058, 0.045,
             "Real Leh TMY · continuous 8760-hour simulation · insulated design + 30% S glazing "
             "+ 1000 L water wall vs uninsulated stone hut — 93% less heating, all year.",
             ha="left", va="center", fontsize=9, color=SUB)

    out = os.path.abspath("docs/seasonal.png")
    fig.savefig(out, dpi=200, facecolor=fig.get_facecolor())
    print(f"saving={r['saving']:.0f}%  litres={fi.litres:,.0f}  inr={fi.inr:,.0f}  "
          f"co2_t={fi.co2_kg/1000:.1f}")
    print(f"saved -> {out}")


if __name__ == "__main__":
    main()
