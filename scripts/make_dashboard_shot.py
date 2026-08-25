"""
Render a print-clean "dashboard panel" PNG for the pitch deck (Slide 3, working
prototype) — WITHOUT a browser.

The live Streamlit app (app.py) is the real prototype, but a raw browser
screenshot is (a) low-DPI and (b) blocked by the sandbox here. So this script
reproduces the app's default view — the KPI row, the "% less heating" banner and
the temperature chart — from the SAME engine calls app.py makes, rendered at high
DPI with matplotlib. Every number therefore matches the live dashboard exactly.

Run:  MPLCONFIGDIR="$TMPDIR/mpl" ./.venv/bin/python scripts/make_dashboard_shot.py
Out:  docs/dashboard.png
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import FancyBboxPatch

from thermalshelter import climate, comfort, engine, geometry
from thermalshelter.materials import get_material

# --- app defaults (app.py sidebar initial values) -------------------------- #
REGION = "Leh, Ladakh"
LAT, LON, ALT, ALB = 34.15, 77.57, 3500, 0.70
T_MIN, T_MAX, DAYS = -14.0, 2.0, 5
SETPOINT, VENT_HIGH = 20.0, 24.0

C_AMB, C_BASE, C_DESIGN, C_BAND, C_MASS = "#8a8a8a", "#d9534f", "#1f77b4", "#8fd19e", "#f0ad4e"
INK, SUB, ACCENT = "#1b2733", "#5b6b7a", "#0070C0"

BARE_ROOF = geometry.make_construction("Bare timber roof", [("Softwood timber (pine)", 0.04)])
BARE_FLOOR = geometry.make_construction("Bare concrete floor", [("Dense concrete", 0.15)])


def _clim():
    loc = climate.Location(name=REGION, latitude=LAT, longitude=LON, altitude=ALT,
                           timezone="Asia/Kolkata", albedo=ALB)
    return climate.synthetic_day(loc, t_min=T_MIN, t_max=T_MAX, days=DAYS, freq_minutes=30)


def _design(clim):
    water = geometry.ThermalMass(name="Water wall (1000 L)",
                                 material=get_material("Water (storage wall)"),
                                 volume=1.0, surface_area=6.0)
    return geometry.box_shelter(
        length=6.0, width=4.0, height=2.6, orientation=180,
        wall=geometry.INSULATED_WALL, roof=geometry.INSULATED_ROOF,
        floor=geometry.INSULATED_FLOOR, glazing=geometry.DOUBLE_GLAZING,
        window_wall_ratio=0.30, window_facades=("S",),
        infiltration_ach=0.5, thermal_mass=[water], name="Your design")


def _baseline(clim):
    return geometry.box_shelter(
        wall=geometry.UNINSULATED_STONE, roof=BARE_ROOF, floor=BARE_FLOOR,
        glazing=geometry.SINGLE_GLAZING, window_wall_ratio=0.12,
        window_facades=("S",), infiltration_ach=2.0, name="Baseline hut")


def compute():
    clim = _clim()
    dsn, base = _design(clim), _baseline(clim)
    d_free = engine.simulate(dsn, clim, vent_high=VENT_HIGH)
    d_heat = engine.simulate(dsn, clim, heating_setpoint=SETPOINT)
    b_free = engine.simulate(base, clim)
    b_heat = engine.simulate(base, clim, heating_setpoint=SETPOINT)

    m = comfort.comfort_metrics(d_free.last_day())
    e = d_free.energy_per_day()
    aux, base_aux = d_heat.energy_per_day()["aux_heating"], b_heat.energy_per_day()["aux_heating"]
    saving = (1 - aux / base_aux) * 100 if base_aux else 0.0
    wall = next(iter(d_free.T_storage.values()), None)
    return dict(
        t=d_free.time_h / 24.0, tb=b_free.time_h / 24.0,
        T_out=d_free.T_out, T_base=b_free.T_in, T_design=d_free.T_in, wall=wall,
        mean=m["mean"], night=m["night_low"], comfort=m["comfort_fraction"] * 100,
        solar=e["solar_windows"], aux=aux, base_aux=base_aux, saving=saving,
    )


# --- drawing helpers -------------------------------------------------------- #
def pill(fig, x, y, w, h, text, fc, ec, tc):
    fig.patches.append(FancyBboxPatch(
        (x, y), w, h, boxstyle="round,pad=0.004,rounding_size=0.012",
        transform=fig.transFigure, facecolor=fc, edgecolor=ec, linewidth=1.0, zorder=2))
    fig.text(x + w / 2, y + h / 2, text, transform=fig.transFigure,
             ha="center", va="center", fontsize=9.0, color=tc, zorder=3)


def kpi(fig, x, y, w, h, label, value):
    fig.patches.append(FancyBboxPatch(
        (x, y), w, h, boxstyle="round,pad=0.004,rounding_size=0.014",
        transform=fig.transFigure, facecolor="white", edgecolor="#e2e8ee",
        linewidth=1.2, zorder=2))
    fig.text(x + 0.018, y + h - 0.020, label, transform=fig.transFigure,
             ha="left", va="top", fontsize=9, color=SUB, zorder=3)
    fig.text(x + 0.018, y + 0.020, value, transform=fig.transFigure,
             ha="left", va="bottom", fontsize=17, color=INK, weight="bold", zorder=3)


def main():
    r = compute()

    fig = plt.figure(figsize=(13.333, 7.5), dpi=200)
    fig.patch.set_facecolor("#f4f6f9")

    # ---- header ----------------------------------------------------------- #
    fig.text(0.035, 0.955, "Thermal-Shelter", ha="left", va="top",
             fontsize=25, weight="bold", color=INK)
    fig.text(0.30, 0.958, "passive design studio", ha="left", va="top",
             fontsize=15, color=ACCENT, weight="bold")
    fig.text(0.035, 0.905,
             f"Area-specific shelter for {REGION} — how warm it stays, and how little heating "
             f"it needs, against a baseline hut.   SIH 2026 · PS 26051 (DRDO, Software).",
             ha="left", va="top", fontsize=10.5, color=SUB)

    # ---- config chips (the active design) --------------------------------- #
    chips = ["Leh, Ladakh  ·  5 clear winter days", "Well-insulated envelope",
             "Double glazing · 30% south", "Water wall 1000 L", "Hold 20 °C"]
    cx, cw, gap, ch, cy = 0.035, 0.0, 0.010, 0.040, 0.828
    widths = [0.185, 0.150, 0.165, 0.120, 0.088]
    for text, w in zip(chips, widths):
        pill(fig, cx, cy, w, ch, text, "#eaf3fb", "#cfe4f6", ACCENT)
        cx += w + gap

    # ---- KPI row ---------------------------------------------------------- #
    labels_vals = [
        ("Mean indoor", f"{r['mean']:.1f} °C"),
        ("Coldest night", f"{r['night']:.1f} °C"),
        ("Time comfortable", f"{r['comfort']:.0f} %"),
        ("Solar gain", f"{r['solar']:.1f} kWh/d"),
        ("Heating needed", f"{r['aux']:.1f} kWh/d"),
    ]
    x0, kw, kgap, ky, kh = 0.035, 0.176, 0.0113, 0.680, 0.099
    for i, (lab, val) in enumerate(labels_vals):
        kpi(fig, x0 + i * (kw + kgap), ky, kw, kh, lab, val)

    # ---- success banner --------------------------------------------------- #
    bx, bw, by, bh = 0.035, 0.930, 0.606, 0.058
    fig.patches.append(FancyBboxPatch(
        (bx, by), bw, bh, boxstyle="round,pad=0.004,rounding_size=0.014",
        transform=fig.transFigure, facecolor="#e6f4ea", edgecolor="#9bd3ac",
        linewidth=1.3, zorder=2))
    fig.text(bx + 0.016, by + bh / 2, "✓", transform=fig.transFigure,
             ha="left", va="center", fontsize=17, color="#2ea44f", weight="bold", zorder=3)
    fig.text(bx + 0.045, by + bh / 2,
             f"This design needs {r['saving']:.0f}% less heating than the baseline hut "
             f"to hold 20 °C   ({r['aux']:.1f} vs {r['base_aux']:.1f} kWh/day).",
             transform=fig.transFigure, ha="left", va="center",
             fontsize=13, color="#1d6b34", weight="bold", zorder=3)

    # ---- temperature chart ------------------------------------------------ #
    ax = fig.add_axes([0.035, 0.075, 0.930, 0.475])
    ax.set_facecolor("white")
    ax.axhspan(18, 24, color=C_BAND, alpha=0.25, label="comfort band (18–24 °C)")
    ax.axhline(0, color="#cccccc", lw=0.9)
    ax.plot(r["t"], r["T_out"], color=C_AMB, lw=1.4, ls="--", label="ambient air")
    if r["wall"] is not None:
        ax.plot(r["t"], r["wall"], color=C_MASS, lw=1.5, ls="-.", alpha=0.85,
                label="water-wall store")
    ax.plot(r["tb"], r["T_base"], color=C_BASE, lw=2.3, label="indoor — baseline hut")
    ax.plot(r["t"], r["T_design"], color=C_DESIGN, lw=3.0, label="indoor — your design")
    ax.set_xlim(0, DAYS)
    ax.set_xticks(range(0, DAYS + 1))
    ax.set_xlabel("day  (clear Leh winter, both shelters from the same cold start)", fontsize=10.5)
    ax.set_ylabel("temperature (°C)", fontsize=10.5)
    ax.grid(alpha=0.22)
    ax.legend(loc="upper left", fontsize=9.5, ncol=3, framealpha=0.9)
    for s in ("top", "right"):
        ax.spines[s].set_visible(False)
    ax.tick_params(labelsize=9.5)

    out = os.path.abspath("docs/dashboard.png")
    fig.savefig(out, dpi=200, facecolor=fig.get_facecolor())
    print(f"mean={r['mean']:.1f}  night={r['night']:.1f}  comfort={r['comfort']:.0f}%  "
          f"solar={r['solar']:.1f}  aux={r['aux']:.1f}  base={r['base_aux']:.1f}  "
          f"saving={r['saving']:.0f}%")
    print(f"saved -> {out}")


if __name__ == "__main__":
    main()
