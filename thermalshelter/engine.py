"""
Transient thermal engine — the core of the model.

Predicts the shelter's indoor air temperature over time (and a full heat-flow
breakdown) by stepping a lumped resistance–capacitance (RC) network forward in
time. This is what answers the problem statement's three required outputs:

    1. indoor temperature vs time      -> SimulationResult.T_in
    2. solar thermal energy captured   -> energies["solar_windows"/"solar_opaque"]
    3. heat flow vs ambient over time  -> the q_* flux series + energy totals

Network
-------
    T_in : indoor air            (small capacity  C_air)
    T_m  : envelope thermal mass (large capacity  C_m — walls/roof/floor)
    T_s  : optional storage node (water wall / PCM / slab)  [zero or more]

    outdoor --sol-air--> [R_out] --> (T_m) --> [R_in] --> (T_in)
    outdoor --------------------- windows / infiltration --------> (T_in)
    ground  ----------------- floor -------------------------> (T_m)
    (T_s) --convective-- (T_in)

Each opaque surface's outdoor driving temperature is its **sol-air temperature**:
ambient air warmed by absorbed sunlight and *cooled* by long-wave radiation to the
cold sky — so daytime solar gain and night-time radiative loss both fall out of one
consistent term. Integration is explicit (default 60 s steps); the dominant thermal
mass keeps the system well-conditioned and the stepping stable and transparent.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional

import numpy as np
import pandas as pd

from .climate import ClimateSeries, sky_temperature, SIGMA
from .geometry import Shelter, R_FILM_INT
from .solar import poa_on_elements

CP_AIR = 1005.0          # specific heat of air [J/(kg·K)]
R_GROUND = 0.5           # extra resistance of ground contact under the floor [m²K/W]


def air_density(altitude_m: float) -> float:
    """Air density [kg/m³] falling with altitude — ~0.8 at Ladakh's 3500 m vs 1.2 at sea level."""
    return 1.225 * np.exp(-altitude_m / 8500.0)


@dataclass
class SimulationResult:
    name: str
    time_h: np.ndarray                 # hours from start
    index: pd.DatetimeIndex
    T_in: np.ndarray                   # indoor air [°C]
    T_mass: np.ndarray                 # envelope mass [°C]
    T_out: np.ndarray                  # ambient air [°C]
    T_sky: np.ndarray                  # effective sky [°C]
    T_storage: Dict[str, np.ndarray]   # added-mass node temps
    flux: Dict[str, np.ndarray]        # instantaneous heat flows into the air [W]
    energies: Dict[str, float]         # integrated energies over the run [kWh]
    n_days: float

    # ---- convenience ----
    def last_day(self) -> "SimulationResult":
        """Slice to the final 24 h (steady daily cycle) for plotting/metrics."""
        mask = self.time_h >= (self.time_h[-1] - 24.0)
        return SimulationResult(
            name=self.name, time_h=self.time_h[mask], index=self.index[mask],
            T_in=self.T_in[mask], T_mass=self.T_mass[mask], T_out=self.T_out[mask],
            T_sky=self.T_sky[mask],
            T_storage={k: v[mask] for k, v in self.T_storage.items()},
            flux={k: v[mask] for k, v in self.flux.items()},
            energies=self.energies, n_days=self.n_days,
        )

    def energy_per_day(self) -> Dict[str, float]:
        return {k: v / self.n_days for k, v in self.energies.items()}

    def to_dataframe(self) -> pd.DataFrame:
        df = pd.DataFrame(
            {"T_in": self.T_in, "T_mass": self.T_mass,
             "T_out": self.T_out, "T_sky": self.T_sky},
            index=self.index,
        )
        for k, v in self.T_storage.items():
            df[f"T_{k}"] = v
        for k, v in self.flux.items():
            df[f"q_{k}"] = v
        return df


def simulate(
    shelter: Shelter,
    climate: ClimateSeries,
    dt: float = 60.0,
    heating_setpoint: Optional[float] = None,
    vent_high: Optional[float] = None,   # open windows to purge heat above this [°C]
    vent_ach: float = 4.0,               # air-change rate while venting [1/h]
    T_ground: float = 5.0,
    cloud_fraction: float = 0.0,
    f_solar_air: float = 0.4,      # transmitted solar split: to air vs to mass
    output_dt: float = 600.0,
) -> SimulationResult:
    """
    Run the transient simulation.

    heating_setpoint: if None, the shelter free-floats (the passive-design curve).
    If set (e.g. 20 °C), an ideal heater tops the air up to the setpoint and the
    required auxiliary energy is recorded in energies["aux_heating"].
    """
    loc = climate.location
    rho_air = air_density(loc.altitude)

    # ---- fine time grid + interpolated forcings -------------------------------
    t_src = climate.seconds
    total = float(t_src[-1])
    t = np.arange(0.0, total + dt * 0.5, dt)
    n = t.size

    def interp(arr):
        return np.interp(t, t_src, arr)

    T_out = interp(climate.temp_air)
    dew = interp(climate.dewpoint)
    wind = interp(climate.wind_speed)
    T_sky = sky_temperature(T_out, dew, cloud_fraction)
    h_out = 5.7 + 3.8 * wind                      # exterior film [W/m²K]
    T_out_K, T_sky_K = T_out + 273.15, T_sky + 273.15
    lw_pot = SIGMA * (T_out_K ** 4 - T_sky_K ** 4)  # long-wave loss potential [W/m²]

    # ---- solar on every element (computed at climate resolution, interpolated) -
    elements = [*shelter.walls, shelter.roof, *shelter.windows]
    poa = poa_on_elements(climate, elements)

    # ---- opaque envelope: precompute per-surface conductances & sol-air --------
    sumGout = np.zeros(n)          # Σ G_out (outdoor→mass) at each step [W/K]
    sumGoutTsol = np.zeros(n)      # Σ G_out · T_sol            [W·K/K = W... driving]
    q_solar_opaque = np.zeros(n)   # solar absorbed on opaque skins [W]
    q_skyrad = np.zeros(n)         # long-wave loss from opaque skins [W]
    G_in_sum = 0.0                 # Σ G_in (mass→indoor air) [W/K]
    C_m = 0.0                      # envelope mass heat capacity [J/K]

    for s in shelter.opaque_surfaces:
        Rcond = s.construction.R_cond
        G_in = s.area / s.construction.R_inner
        G_in_sum += G_in
        C_m += s.area * s.construction.C_area

        if s.ground_coupled:                       # floor: driven by ground temp
            G_out = np.full(n, s.area / (0.5 * Rcond + R_GROUND))
            T_sol = np.full(n, T_ground)
        else:                                      # wall / roof: sol-air driven
            F_sky = 1.0 if s.tilt < 45.0 else 0.5  # roof sees whole sky; wall ~half
            poa_i = poa[s.name].to_numpy()
            poa_i = interp(poa_i)
            G_out = s.area / (1.0 / h_out + 0.5 * Rcond)
            T_sol = T_out + (s.solar_absorptance * poa_i
                             - s.emissivity * F_sky * lw_pot) / h_out
            q_solar_opaque += s.solar_absorptance * poa_i * s.area
            q_skyrad += s.emissivity * F_sky * lw_pot * s.area

        sumGout += G_out
        sumGoutTsol += G_out * T_sol

    # ---- windows: conduction (incl. night-sky radiation) + transmitted solar ---
    # A window also loses long-wave radiation from its outer pane to the cold sky,
    # not just conduction to ambient air. Fold that into an effective outdoor
    # temperature — the sol-air idea with zero absorbed solar, since sunlight
    # passes through the glass rather than being absorbed in it.
    G_win = 0.0
    win_drive = np.zeros(n)          # Σ UA · T_out_effective  [W]
    q_win_solar = np.zeros(n)
    for w in shelter.windows:
        F_sky = 1.0 if w.tilt < 45.0 else 0.5
        T_win_out = T_out - w.glazing.emissivity * F_sky * lw_pot / h_out
        G_win += w.UA
        win_drive += w.UA * T_win_out
        q_win_solar += w.glazing.SHGC * w.area * interp(poa[w.name].to_numpy())

    # ---- infiltration & air capacity ------------------------------------------
    G_inf = shelter.infiltration_ach * shelter.volume * rho_air * CP_AIR / 3600.0
    G_vent = vent_ach * shelter.volume * rho_air * CP_AIR / 3600.0
    C_air = shelter.volume * rho_air * CP_AIR

    # ---- added thermal-storage nodes ------------------------------------------
    stores = []
    for m in shelter.thermal_mass:
        stores.append({
            "name": m.name, "C": m.C, "G": m.G, "T": T_out[0],
            "pcm": m.material.is_pcm,
            "mL": (m.volume * m.material.rho * (m.material.latent_heat or 0.0)),
            "Tp": m.material.phase_temp or 0.0, "band": m.material.phase_band,
        })
    sumC_store = sum(s["C"] for s in stores)   # for splitting solar across stores

    # ---- state & accumulators -------------------------------------------------
    T_in, T_m = T_out[0], T_out[0]
    E = dict(solar_windows=0.0, solar_opaque=0.0, sky_radiation=0.0,
             window_conduction=0.0, infiltration=0.0, envelope_conduction=0.0,
             storage_exchange=0.0, aux_heating=0.0)

    every = max(1, int(round(output_dt / dt)))
    rec_i, rec_Tin, rec_Tm = [], [], []
    rec_store = {s["name"]: [] for s in stores}
    fl = {k: [] for k in ("solar_windows", "envelope", "window_cond",
                           "infiltration", "storage", "aux")}

    # ---- march forward in time -------------------------------------------------
    for k in range(n):
        # transmitted window solar lands on the room air + interior storage
        # (water wall / slab), NOT the exterior-coupled envelope mass. With no
        # interior storage, all of it warms the air directly (direct-gain hut).
        Q_sol_air = f_solar_air * q_win_solar[k]
        Q_sol_store = (1.0 - f_solar_air) * q_win_solar[k]
        if not stores:
            Q_sol_air += Q_sol_store
            Q_sol_store = 0.0

        # mass node balance: driven by outdoor sol-air and indoor air only
        Q_m = (sumGoutTsol[k] - sumGout[k] * T_m          # outdoor/sol-air ↔ mass
               + G_in_sum * (T_in - T_m))                 # indoor air ↔ mass

        # air node balance (auxiliary heat added afterwards)
        Q_env = G_in_sum * (T_m - T_in)
        Q_wc = win_drive[k] - G_win * T_in
        G_if = G_vent if (vent_high is not None and T_in > vent_high) else G_inf
        Q_if = G_if * (T_out[k] - T_in)
        Q_st = sum(s["G"] * (s["T"] - T_in) for s in stores)
        Q_air = Q_env + Q_wc + Q_if + Q_sol_air + Q_st

        # advance mass and storage
        T_m += Q_m / C_m * dt
        for s in stores:
            Ceff = s["C"]
            if s["pcm"] and s["mL"] > 0:
                z = (s["T"] - s["Tp"]) / s["band"]
                Ceff += s["mL"] * np.exp(-z * z) / (s["band"] * np.sqrt(np.pi))
            q_sol_s = Q_sol_store * (s["C"] / sumC_store) if sumC_store else 0.0
            s["T"] += (s["G"] * (T_in - s["T"]) + q_sol_s) / Ceff * dt

        # advance air with optional thermostat
        T_in_cand = T_in + Q_air / C_air * dt
        if heating_setpoint is not None and T_in_cand < heating_setpoint:
            Q_aux = (heating_setpoint - T_in_cand) * C_air / dt
            T_in = heating_setpoint
        else:
            Q_aux = 0.0
            T_in = T_in_cand

        # integrate energies [J]
        E["solar_windows"] += q_win_solar[k] * dt
        E["solar_opaque"] += q_solar_opaque[k] * dt
        E["sky_radiation"] += q_skyrad[k] * dt
        E["window_conduction"] += Q_wc * dt
        E["infiltration"] += Q_if * dt
        E["envelope_conduction"] += Q_env * dt
        E["storage_exchange"] += Q_st * dt
        E["aux_heating"] += Q_aux * dt

        if k % every == 0:
            rec_i.append(k)
            rec_Tin.append(T_in)
            rec_Tm.append(T_m)
            for s in stores:
                rec_store[s["name"]].append(s["T"])
            fl["solar_windows"].append(q_win_solar[k])
            fl["envelope"].append(Q_env)
            fl["window_cond"].append(Q_wc)
            fl["infiltration"].append(Q_if)
            fl["storage"].append(Q_st)
            fl["aux"].append(Q_aux)

    idx = np.array(rec_i)
    n_days = total / 86400.0
    index = climate.times[0] + pd.to_timedelta(t[idx], unit="s")

    return SimulationResult(
        name=shelter.name,
        time_h=t[idx] / 3600.0,
        index=pd.DatetimeIndex(index),
        T_in=np.array(rec_Tin),
        T_mass=np.array(rec_Tm),
        T_out=T_out[idx],
        T_sky=T_sky[idx],
        T_storage={k: np.array(v) for k, v in rec_store.items()},
        flux={k: np.array(v) for k, v in fl.items()},
        energies={k: v / 3.6e6 for k, v in E.items()},   # J -> kWh
        n_days=n_days,
    )
