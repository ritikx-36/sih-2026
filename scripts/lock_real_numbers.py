"""
One-off: lock the exact real-TMY numbers used in the pitch materials.

Drives the SAME design/baseline the dashboard uses (identical to
make_dashboard_shot.py) with the REAL bundled Leh TMY (data/leh_tmy.csv),
runs the 12-month annual profile (exactly what the Seasonal tab shows), and
prints the January representative-day figures, the full-year aggregate, and
the fuel/₹/CO₂ impact. Numbers printed here are the canonical deck figures.

Run:  PYTHONPATH=/Users/ritik/sih ./.venv/bin/python scripts/lock_real_numbers.py
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from thermalshelter import annual, climate, comfort, engine, geometry, impact
from thermalshelter.materials import get_material

SETPOINT, VENT_HIGH, DAYS = 20.0, 24.0, 5
DIM = [31, 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31]   # 1990 (coerce_year), 365 d

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


def main():
    cs = climate.from_csv(os.path.join("data", "leh_tmy.csv"), climate.LEH)
    ta = cs.data["temp_air"]
    print("=== REAL PVGIS TMY (data/leh_tmy.csv) ===")
    print(f"rows={len(cs.data):,}  temp_air  min={ta.min():.1f}  "
          f"max={ta.max():.1f}  mean={ta.mean():.1f} degC")

    design, base = _design(), _baseline()

    # ---- January representative day (the Real-TMY live clip) ----
    rep = climate.representative_day(cs, 1, days=DAYS)
    free = engine.simulate(design, rep, vent_high=VENT_HIGH)
    d_heat = engine.simulate(design, rep, heating_setpoint=SETPOINT)
    b_heat = engine.simulate(base, rep, heating_setpoint=SETPOINT)
    cm = comfort.comfort_metrics(free.last_day())
    d_aux = d_heat.energy_per_day()["aux_heating"]
    b_aux = b_heat.energy_per_day()["aux_heating"]
    e = free.energy_per_day()
    jan_save = (1 - d_aux / b_aux) * 100 if b_aux else 0.0
    print("\n=== JANUARY representative day (Real-TMY live clip) ===")
    print(f"mean_in={cm['mean']:.1f}  night_low={cm['night_low']:.1f}  "
          f"comfort={cm['comfort_fraction']*100:.0f}%  solar_win={e['solar_windows']:.1f} kWh/d")
    print(f"design_aux={d_aux:.1f}  baseline_aux={b_aux:.1f} kWh/d  -> {jan_save:.0f}% less")
    fi_day = impact.fuel_impact(b_aux - d_aux)
    print(f"per-day saved: {fi_day.litres:.1f} L  Rs{fi_day.inr:,.0f}  {fi_day.co2_kg:.1f} kg CO2")
    fi_win = impact.fuel_impact((b_aux - d_aux) * impact.WINTER_DAYS)
    print(f"x{impact.WINTER_DAYS}-day winter: {fi_win.litres:,.0f} L  "
          f"Rs{fi_win.inr:,.0f}  {fi_win.co2_kg/1000:.1f} t CO2")

    # ---- Full-year annual profile (exactly the Seasonal tab) ----
    prof = annual.annual_profile(cs, design, base, SETPOINT, vent_high=VENT_HIGH, days=DAYS)
    d_year = sum(a * d for a, d in zip(prof["design_aux"], DIM))
    b_year = sum(a * d for a, d in zip(prof["baseline_aux"], DIM))
    saved = b_year - d_year
    yr_save = (1 - d_year / b_year) * 100 if b_year else 0.0
    comfort_year = sum(c * d for c, d in zip(prof["comfort"], DIM)) / sum(DIM) * 100
    fi = impact.fuel_impact(saved)
    print("\n=== FULL-YEAR annual integral (Seasonal tab, x days-in-month) ===")
    print(f"design={d_year:,.0f}  baseline={b_year:,.0f} kWh/yr  saved={saved:,.0f} kWh/yr "
          f"-> {yr_save:.0f}% less")
    print(f"year-mean comfort={comfort_year:.0f}%")
    print(f"IMPACT/yr: {fi.litres:,.0f} L kerosene   Rs{fi.inr:,.0f}   {fi.co2_kg/1000:.1f} t CO2")
    print("\nper-month design_aux:", [round(x, 1) for x in prof["design_aux"]])
    print("per-month baseline_aux:", [round(x, 1) for x in prof["baseline_aux"]])
    print("per-month comfort%:", [round(x * 100) for x in prof["comfort"]])


if __name__ == "__main__":
    main()
