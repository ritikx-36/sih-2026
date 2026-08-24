"""
Solar irradiance on the shelter's surfaces.

Given a `Location`, a set of `times`, and each surface's orientation (azimuth &
tilt), this computes the plane-of-array (POA) irradiance [W/m²] striking that
surface — the heat *source* that a passive shelter must capture.

Pipeline (all via pvlib, the industry-standard solar library):

    1. sun position  — apparent zenith & azimuth for every timestamp
    2. clear-sky GHI/DNI/DHI — from a clear-sky model (or measured data if the
       climate series already carries ghi/dni/dhi columns)
    3. transposition — project beam + sky-diffuse + ground-reflected onto each
       surface. The ground-reflected term uses the location albedo, so Ladakh's
       snow (albedo ≈ 0.7) correctly boosts irradiance on the walls.

A south-facing wall at this latitude collects strong *winter* sun (low sun angle
strikes a vertical surface almost head-on), while the north wall gets almost none
— exactly the orientation effect the design study is about.
"""
from __future__ import annotations

from typing import Iterable

import numpy as np
import pandas as pd
import pvlib

from .climate import ClimateSeries


def _pvlib_location(cs: ClimateSeries) -> pvlib.location.Location:
    loc = cs.location
    return pvlib.location.Location(
        latitude=loc.latitude,
        longitude=loc.longitude,
        tz=loc.timezone,
        altitude=loc.altitude,
        name=loc.name,
    )


def solar_position(cs: ClimateSeries) -> pd.DataFrame:
    """Apparent sun position for every timestamp (zenith, azimuth, elevation)."""
    loc = cs.location
    return pvlib.solarposition.get_solarposition(
        cs.times, loc.latitude, loc.longitude, altitude=loc.altitude
    )


def clearsky_irradiance(cs: ClimateSeries) -> pd.DataFrame:
    """
    GHI / DNI / DHI [W/m²]. Uses measured values if present in the climate data,
    otherwise a clear-sky model (Simplified Solis — analytic, works offline and
    suits Ladakh's clean, dry, high-altitude air).
    """
    if {"ghi", "dni", "dhi"}.issubset(cs.data.columns):
        return cs.data[["ghi", "dni", "dhi"]].copy()
    return _pvlib_location(cs).get_clearsky(cs.times, model="simplified_solis")


def poa_on_elements(cs: ClimateSeries, elements: Iterable) -> pd.DataFrame:
    """
    POA global irradiance [W/m²] on each element (walls, roof, windows).

    `elements` is any iterable of objects exposing `.name`, `.azimuth`, `.tilt`
    (both `Surface` and `Window` qualify). Ground-coupled surfaces (floors) get
    zero. The returned DataFrame is indexed by time with one column per element,
    plus reference columns `ghi`, `dni`, `dhi`, `sun_elevation`.
    """
    sp = solar_position(cs)
    csky = clearsky_irradiance(cs)
    albedo = cs.location.albedo

    out = pd.DataFrame(index=cs.times)
    out["ghi"] = csky["ghi"].to_numpy()
    out["dni"] = csky["dni"].to_numpy()
    out["dhi"] = csky["dhi"].to_numpy()
    out["sun_elevation"] = sp["apparent_elevation"].to_numpy()

    for el in elements:
        if getattr(el, "ground_coupled", False):
            out[el.name] = 0.0
            continue
        poa = pvlib.irradiance.get_total_irradiance(
            surface_tilt=el.tilt,
            surface_azimuth=el.azimuth,
            solar_zenith=sp["apparent_zenith"],
            solar_azimuth=sp["azimuth"],
            dni=csky["dni"],
            ghi=csky["ghi"],
            dhi=csky["dhi"],
            albedo=albedo,
            model="isotropic",
        )
        out[el.name] = np.clip(poa["poa_global"].to_numpy(), 0.0, None)

    return out


def daily_insolation(poa: pd.DataFrame, column: str) -> float:
    """Integrate a POA column over the series -> energy [kWh/m²]."""
    seconds = (poa.index - poa.index[0]).total_seconds().to_numpy()
    return float(np.trapezoid(poa[column].to_numpy(), seconds) / 3.6e6)


if __name__ == "__main__":
    from .climate import ladakh_winter_day
    from .geometry import box_shelter

    cs = ladakh_winter_day(days=1, freq_minutes=30)
    shelter = box_shelter()
    elements = [*shelter.walls, shelter.roof, *shelter.windows]

    poa = poa_on_elements(cs, elements)
    peak_sun = poa["sun_elevation"].max()
    print(f"Clear Leh winter day — peak sun elevation {peak_sun:.1f}°\n")
    print(f"{'Surface':12s} {'peak POA':>9s}  {'daily kWh/m²':>12s}")
    print("-" * 38)
    for el in elements:
        print(f"{el.name:12s} {poa[el.name].max():7.0f} W  "
              f"{daily_insolation(poa, el.name):11.2f}")
    print(f"{'(horizontal)':12s} {poa['ghi'].max():7.0f} W  "
          f"{daily_insolation(poa, 'ghi'):11.2f}")
