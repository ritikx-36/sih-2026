"""
Verification suite for the Thermal-Shelter engine.

These are *verification* checks — "did we solve the model right?" — as distinct
from *validation* against measured data or an independent building-energy tool
(EnergyPlus / ANSYS: the next phase). Each check is a closed-form or convergence
argument that the transient RC solver in `thermalshelter/engine.py` is
self-consistent and numerically sound. Nothing here trusts the engine to grade
itself: the references are hand calculations and an independent ODE integration.

    1. Steady state = UA·ΔT     with no sun and no sky cooling the settled indoor
                                temperature and heating load must equal a textbook
                                hand calculation of the shelter's loss coefficient.
    2. First-law energy closure over a free-float run the change in stored energy
                                must equal the net heat that crossed the envelope.
    3. Transient = independent  the engine's indoor-temperature curve must match a
       ODE                      high-accuracy SciPy integration of the same RC
                                network driven by the same weather.
    4. Time-step convergence    the answer must stop changing as dt → 0, and the
                                shipped 60 s step must already sit on that limit.

The trick that makes 1–3 exact: force a *pure-conduction* regime — pass
`cloud_fraction=1.0` (so the sky radiates at air temperature, killing the
long-wave term) and drive with a climate whose ghi/dni/dhi are zero (no solar).
The engine then reduces to a linear two-node network (indoor air + envelope mass)
with constant coefficients, which we can both solve analytically and integrate
independently.

Run:
    MPLCONFIGDIR="$TMPDIR/mpl" ./.venv/bin/python scripts/validate.py

Writes a deck-ready figure to docs/validation.png and prints a PASS/FAIL table.
"""
from __future__ import annotations

import os
import sys

# Keep matplotlib's cache inside the sandbox-writable temp dir, and run headless.
os.environ.setdefault("MPLCONFIGDIR", os.path.join(os.environ.get("TMPDIR", "/tmp"), "mpl"))
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import numpy as np
import pandas as pd
import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from scipy.integrate import solve_ivp

from thermalshelter.climate import ClimateSeries, LEH, dewpoint_from_rh
from thermalshelter.engine import CP_AIR, R_GROUND, air_density, simulate
from thermalshelter.geometry import box_shelter

# A cold, still, sunless site: altitude 0 keeps ρ_air textbook-simple, and the
# checks are about the solver, not about Ladakh specifically.
SITE = LEH
TOL_STEADY = 0.02      # K   — free-float must settle onto ambient this tightly
TOL_UA = 0.5           # %   — settled load vs hand-calc UA·ΔT
TOL_CLOSE = 1.0        # %   — first-law residual vs energy throughput
TOL_ODE = 0.10         # K   — engine transient vs independent ODE (max abs error)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def conduction_climate(temp: np.ndarray, freq_minutes: int = 60) -> ClimateSeries:
    """A ClimateSeries carrying temp_air(t) with zero solar and zero wind.

    Zero ghi/dni/dhi columns make `solar.clearsky_irradiance` return measured
    (=0) rather than synthesising a clear-sky day, so POA is zero everywhere.
    Zero wind pins the exterior film to h_out = 5.7 W/m²K. Combined with
    `simulate(cloud_fraction=1.0)` the engine is a pure-conduction linear network.
    """
    n = len(temp)
    start = pd.Timestamp("2026-01-15", tz=SITE.timezone)
    index = pd.date_range(start=start, periods=n, freq=f"{freq_minutes}min")
    rh = np.full(n, 40.0)
    df = pd.DataFrame(
        {
            "temp_air": np.asarray(temp, dtype=float),
            "wind_speed": np.zeros(n),
            "relative_humidity": rh,
            "dewpoint": dewpoint_from_rh(np.asarray(temp, dtype=float), rh),
            "ghi": np.zeros(n),
            "dni": np.zeros(n),
            "dhi": np.zeros(n),
        },
        index=index,
    )
    return ClimateSeries(location=SITE, data=df)


def coefficients(shelter, wind: float = 0.0) -> dict:
    """Reconstruct the engine's constant RC coefficients from the shelter, using
    the *same* formulas engine.py assembles (so a mismatch here is a real bug).

    Returns conductances [W/K] and capacities [J/K]:
        C_air, C_m          air and envelope-mass heat capacities
        G_in                Σ mass→indoor-air conductance
        G_out_air           Σ outdoor(sol-air)→mass conductance (walls + roof)
        G_out_gnd           Σ ground→mass conductance (floor)
        G_win, G_inf        window conduction and infiltration to indoor air
    """
    rho = air_density(SITE.altitude)
    h_out = 5.7 + 3.8 * wind
    C_air = shelter.volume * rho * CP_AIR
    C_m = sum(s.area * s.construction.C_area for s in shelter.opaque_surfaces)
    G_in = sum(s.area / s.construction.R_inner for s in shelter.opaque_surfaces)

    G_out_air = 0.0   # walls/roof: driven by outdoor sol-air (here just T_out)
    G_out_gnd = 0.0   # floor: driven by ground temperature
    for s in shelter.opaque_surfaces:
        Rcond = s.construction.R_cond
        if s.ground_coupled:
            G_out_gnd += s.area / (0.5 * Rcond + R_GROUND)
        else:
            G_out_air += s.area / (1.0 / h_out + 0.5 * Rcond)

    G_win = sum(w.UA for w in shelter.windows)
    G_inf = shelter.infiltration_ach * shelter.volume * rho * CP_AIR / 3600.0
    return dict(C_air=C_air, C_m=C_m, G_in=G_in, G_out_air=G_out_air,
                G_out_gnd=G_out_gnd, G_win=G_win, G_inf=G_inf)


def ua_total(c: dict) -> float:
    """Steady-state indoor-air → outdoor loss coefficient [W/K] when every path
    (walls, roof, floor, windows, infiltration) drives to the same outdoor
    temperature. The envelope path is the series combination of ΣG_out and ΣG_in
    through the single mass node."""
    g_out = c["G_out_air"] + c["G_out_gnd"]
    g_env = g_out * c["G_in"] / (g_out + c["G_in"])
    return g_env + c["G_win"] + c["G_inf"]


# ---------------------------------------------------------------------------
# Check 1 — steady state equals a UA·ΔT hand calculation
# ---------------------------------------------------------------------------
def check_steady(shelter, c):
    T_out = -10.0
    days = 40                       # >> the mass time constant, so it fully settles
    clim = conduction_climate(np.full(days * 24, T_out))

    # (a) free-float with no sun and no sky loss must settle exactly onto ambient
    free = simulate(shelter, clim, cloud_fraction=1.0, T_ground=T_out, vent_high=None)
    err_free = abs(free.T_in[-1] - T_out)

    # (b) heated: the settled load must equal UA·ΔT, and be linear through the origin
    UA = ua_total(c)
    setpoints = [0.0, 10.0, 20.0, 30.0]
    pred, meas = [], []
    for Ts in setpoints:
        r = simulate(shelter, clim, heating_setpoint=Ts, cloud_fraction=1.0,
                     T_ground=T_out, vent_high=None)
        steady_w = float(np.mean(r.flux["aux"][-24:]))   # last day, W
        pred.append(UA * (Ts - T_out))
        meas.append(steady_w)
    pred, meas = np.array(pred), np.array(meas)
    dev = np.max(np.abs(meas - pred) / np.clip(pred, 1e-9, None)) * 100.0

    passed = (err_free < TOL_STEADY) and (dev < TOL_UA)
    detail = (f"free-float settles to {free.T_in[-1]:+.4f} °C vs ambient {T_out:+.1f} "
              f"(|Δ|={err_free:.1e} K); heated load = UA·ΔT within {dev:.2f}% "
              f"(UA={UA:.2f} W/K)")
    return dict(name="1. Steady state = UA·ΔT hand-calc", passed=passed, detail=detail,
                plot=dict(setpoints=np.array(setpoints), T_out=T_out,
                          pred=pred, meas=meas, UA=UA))


# ---------------------------------------------------------------------------
# Check 2 — first-law energy closure over a free-float run
# ---------------------------------------------------------------------------
def check_closure(shelter, c):
    dt = 30.0
    hours = 48
    t = np.arange(hours)
    temp = -10.0 + 8.0 * np.sin(2 * np.pi * t / 24.0)     # a diurnal swing
    clim = conduction_climate(temp)
    T_ground = float(np.mean(temp))

    r = simulate(shelter, clim, dt=dt, output_dt=dt, cloud_fraction=1.0,
                 T_ground=T_ground, vent_high=None)

    # Change in stored energy of the two capacitive nodes [J]
    dU = c["C_air"] * (r.T_in[-1] - r.T_in[0]) + c["C_m"] * (r.T_mass[-1] - r.T_mass[0])

    # Net heat that crossed the envelope into those nodes, integrated over the run.
    secs = r.time_h * 3600.0
    p_ext = (c["G_out_air"] * (r.T_out - r.T_mass)
             + c["G_out_gnd"] * (T_ground - r.T_mass)
             + c["G_win"] * (r.T_out - r.T_in)
             + c["G_inf"] * (r.T_out - r.T_in))
    q_in = np.trapezoid(p_ext, secs)                       # [J]
    throughput = np.trapezoid(np.abs(p_ext), secs)
    resid_pct = abs(dU - q_in) / throughput * 100.0

    passed = resid_pct < TOL_CLOSE
    detail = (f"stored ΔU={dU/3.6e6:+.3f} kWh vs net cross-envelope "
              f"{q_in/3.6e6:+.3f} kWh — first law closes to {resid_pct:.2f}% "
              f"of throughput")
    return dict(name="2. First-law energy closure", passed=passed, detail=detail)


# ---------------------------------------------------------------------------
# Check 3 — transient matches an independent ODE integration
# ---------------------------------------------------------------------------
def check_transient(shelter, c):
    dt = 60.0
    hours = 72
    t = np.arange(hours)
    temp = -10.0 + 8.0 * np.sin(2 * np.pi * t / 24.0)
    clim = conduction_climate(temp)
    T_ground = float(np.mean(temp))

    r = simulate(shelter, clim, dt=dt, output_dt=dt, cloud_fraction=1.0,
                 T_ground=T_ground, vent_high=None)

    # Independent reference: integrate the same 2-node linear ODE with SciPy,
    # driven by the identical interpolated outdoor temperature the engine sees.
    secs_src = clim.seconds
    temp_src = clim.temp_air
    T_out_of = lambda tt: np.interp(tt, secs_src, temp_src)

    Ca, Cm = c["C_air"], c["C_m"]
    Gin, Gwin, Ginf = c["G_in"], c["G_win"], c["G_inf"]
    Goa, Gog = c["G_out_air"], c["G_out_gnd"]

    def rhs(tt, y):
        Tin, Tm = y
        To = T_out_of(tt)
        dTin = (Gin * (Tm - Tin) + Gwin * (To - Tin) + Ginf * (To - Tin)) / Ca
        dTm = (Goa * (To - Tm) + Gog * (T_ground - Tm) + Gin * (Tin - Tm)) / Cm
        return [dTin, dTm]

    y0 = [temp_src[0], temp_src[0]]                        # engine inits nodes to T_out[0]
    t_eval = r.time_h * 3600.0
    sol = solve_ivp(rhs, (t_eval[0], t_eval[-1]), y0, t_eval=t_eval,
                    method="RK45", rtol=1e-9, atol=1e-9)
    ref_Tin = sol.y[0]
    max_err = float(np.max(np.abs(r.T_in - ref_Tin)))

    # Report the network's two natural time constants (eigenvalues of A).
    A = np.array([[-(Gin + Gwin + Ginf) / Ca, Gin / Ca],
                  [Gin / Cm, -(Goa + Gog + Gin) / Cm]])
    taus = sorted(-1.0 / np.linalg.eigvals(A).real / 3600.0)   # hours, ascending

    passed = max_err < TOL_ODE
    detail = (f"max |engine − independent ODE| = {max_err:.3f} °C over {hours} h "
              f"(τ_fast≈{taus[0]:.1f} h, τ_slow≈{taus[1]:.1f} h)")
    return dict(name="3. Transient vs independent ODE", passed=passed, detail=detail,
                plot=dict(time_h=r.time_h, T_out=r.T_out, T_in=r.T_in, ref=ref_Tin,
                          max_err=max_err))


# ---------------------------------------------------------------------------
# Check 4 — time-step convergence
# ---------------------------------------------------------------------------
def check_convergence():
    # The *actual* shipped demo design (insulated shell, 30% south glazing,
    # 1000 L water wall) on the 5-day Ladakh winter day, heated to 20 °C — so
    # the number here is the deck's headline load, not a toy case.
    from thermalshelter.climate import ladakh_winter_day
    from thermalshelter.geometry import ThermalMass
    from thermalshelter.materials import get_material

    water_wall = ThermalMass(name="Water wall (1000 L)",
                             material=get_material("Water (storage wall)"),
                             volume=1.0, surface_area=6.0)
    shelter = box_shelter(window_wall_ratio=0.30, infiltration_ach=0.5,
                          thermal_mass=[water_wall], name="Passive design")
    clim = ladakh_winter_day(days=5, freq_minutes=30)

    dts = [240.0, 120.0, 60.0, 30.0, 15.0]
    aux = []
    for dt in dts:
        r = simulate(shelter, clim, dt=dt, heating_setpoint=20.0)
        aux.append(r.energy_per_day()["aux_heating"])
    aux = np.array(aux)

    # Reference = a step finer than anything shipped; error is measured against it.
    ref = simulate(shelter, clim, dt=7.5, heating_setpoint=20.0).energy_per_day()["aux_heating"]
    err = np.abs(aux - ref)
    err60 = err[dts.index(60.0)] / ref * 100.0

    passed = err60 < 1.0
    detail = (f"heating load {aux[dts.index(60.0)]:.2f} kWh/day at dt=60 s vs "
              f"{ref:.2f} at dt=7.5 s — {err60:.2f}% from the dt→0 limit")
    return dict(name="4. Time-step convergence", passed=passed, detail=detail,
                plot=dict(dts=np.array(dts), err=err, err60=err60,
                          aux60=aux[dts.index(60.0)]))


# ---------------------------------------------------------------------------
# Figure + report
# ---------------------------------------------------------------------------
def make_figure(steady, transient, conv, path="docs/validation.png"):
    plt.rcParams.update({"font.size": 11, "axes.grid": True,
                         "grid.alpha": 0.25, "axes.axisbelow": True})
    fig, (ax1, ax2, ax3) = plt.subplots(1, 3, figsize=(15.0, 4.6))
    BLUE, ORANGE, GREY = "#0070C0", "#E8820C", "#8a8f98"

    # Panel 1 — transient overlay
    p = transient["plot"]
    ax1.plot(p["time_h"], p["T_out"], color=GREY, lw=1.4, label="outdoor air")
    ax1.plot(p["time_h"], p["T_in"], color=BLUE, lw=2.4, label="engine  T_in")
    ax1.plot(p["time_h"], p["ref"], color=ORANGE, lw=1.4, ls=(0, (5, 4)),
             label="independent ODE")
    ax1.set_xlabel("time  [h]")
    ax1.set_ylabel("temperature  [°C]")
    ax1.set_title(f"Transient matches independent ODE\nmax error {p['max_err']:.3f} °C",
                  fontsize=11.5)
    ax1.legend(frameon=False, fontsize=9.5, loc="upper right")

    # Panel 2 — steady-state load vs hand calc
    p = steady["plot"]
    lim = max(p["pred"].max(), p["meas"].max()) * 1.08
    ax2.plot([0, lim], [0, lim], color=GREY, lw=1.2, ls=(0, (4, 4)), label="y = x")
    ax2.scatter(p["pred"], p["meas"], s=70, color=BLUE, zorder=3,
                label="setpoints 0–30 °C")
    ax2.set_xlim(0, lim)
    ax2.set_ylim(0, lim)
    ax2.set_xlabel("hand-calc  UA·ΔT  [W]")
    ax2.set_ylabel("engine settled load  [W]")
    ax2.set_title(f"Settled heating load = UA·ΔT\nUA = {p['UA']:.2f} W/K",
                  fontsize=11.5)
    ax2.legend(frameon=False, fontsize=9.5, loc="upper left")

    # Panel 3 — grid convergence (error vs the dt->0 limit, log-log)
    p = conv["plot"]
    dts, err = p["dts"], p["err"]
    ax3.loglog(dts, err, "-o", color=BLUE, lw=2.0, ms=6, zorder=3)
    # first-order (∝ dt) reference slope through the coarsest point, for context
    ref_line = err[0] * (dts / dts[0])
    ax3.loglog(dts, ref_line, ls=(0, (2, 3)), color=GREY, lw=1.3,
               label="first-order  ∝ dt")
    i60 = list(dts).index(60.0)
    ax3.scatter([60.0], [err[i60]], s=150, facecolor="none", edgecolor=ORANGE,
                lw=2.2, zorder=4, label="shipped  dt = 60 s")
    ax3.set_xticks(dts)
    ax3.set_xticklabels([f"{int(d)}" for d in dts])
    ax3.minorticks_off()
    ax3.set_xlabel("time step  dt  [s]  (log)")
    ax3.set_ylabel("error vs dt→0 limit  [kWh/day]  (log)")
    ax3.set_title(f"Grid-converged: error → 0 as dt → 0\n"
                  f"60 s step within {p['err60']:.2f}% of the limit", fontsize=11.5)
    ax3.legend(frameon=False, fontsize=9.5, loc="upper left")

    fig.suptitle("Thermal-Shelter engine — verification against analytic limits",
                 fontsize=13.5, fontweight="bold", y=1.02)
    fig.tight_layout()
    fig.savefig(path, dpi=140, bbox_inches="tight", facecolor="white")
    plt.close(fig)
    return path


def main():
    shelter = box_shelter()
    c = coefficients(shelter)

    results = [
        check_steady(shelter, c),
        check_closure(shelter, c),
        check_transient(shelter, c),
        check_convergence(),
    ]

    print("\n" + "=" * 78)
    print("  Thermal-Shelter — engine verification suite")
    print("=" * 78)
    for r in results:
        mark = "PASS" if r["passed"] else "FAIL"
        print(f"  [{mark}]  {r['name']}")
        print(f"          {r['detail']}")
    n_pass = sum(r["passed"] for r in results)
    print("-" * 78)
    print(f"  {n_pass}/{len(results)} checks passed")

    path = make_figure(results[0], results[2], results[3])
    print(f"  figure written to {path}")
    print("=" * 78 + "\n")

    return 0 if n_pass == len(results) else 1


if __name__ == "__main__":
    raise SystemExit(main())
