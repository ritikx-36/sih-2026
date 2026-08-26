"""
Climate inputs for the Thermal-Shelter model.

The thermal engine is driven by the *ambient* conditions around the shelter:

    temp_air           [°C]   outdoor dry-bulb air temperature (the big driver)
    wind_speed         [m/s]  sets the outside convective film coefficient
    relative_humidity  [%]    -> dewpoint -> clear-sky long-wave / sky temperature
    (optional) ghi/dni/dhi    measured solar irradiance; if absent, solar.py
                              synthesises a clear-sky day from location + date.

Two things this module provides:

1.  `Location`      — where the shelter is (lat/lon/altitude/tz + ground albedo).
                      Snow in Ladakh pushes albedo to ~0.7, which strongly boosts
                      solar reflected onto the walls — so it is a first-class input.
2.  `ClimateSeries` — an hourly (or finer) time series of the ambient conditions,
                      either a realistic *synthetic* day or loaded from a user CSV.

It also exposes `sky_temperature()`, the effective radiant temperature of the sky,
which is what makes clear high-altitude nights so cold: surfaces radiate heat to a
sky far colder than the air, and that loss is a leading cause of the post-sunset
temperature crash the problem statement describes.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

import numpy as np
import pandas as pd

# Stefan-Boltzmann constant [W/(m²·K⁴)]
SIGMA = 5.670374419e-8


@dataclass(frozen=True)
class Location:
    """Geographic location of the shelter."""

    name: str
    latitude: float        # degrees North (+)
    longitude: float       # degrees East (+)
    altitude: float        # metres above sea level
    timezone: str          # IANA tz name, e.g. "Asia/Kolkata"
    albedo: float = 0.20   # ground solar reflectance (fresh snow ≈ 0.7–0.85)


# --- Preset: Leh, Ladakh (the problem statement's target region) -------------
LEH = Location(
    name="Leh, Ladakh",
    latitude=34.15,
    longitude=77.57,
    altitude=3500.0,
    timezone="Asia/Kolkata",
    albedo=0.70,           # assume winter snow cover; user can override
)


@dataclass
class ClimateSeries:
    """A time series of ambient conditions at a location."""

    location: Location
    data: pd.DataFrame     # tz-aware DatetimeIndex; cols: temp_air, wind_speed,
                           # relative_humidity, dewpoint, [ghi, dni, dhi]

    # -- convenience accessors (numpy arrays the engine can consume) --
    @property
    def times(self) -> pd.DatetimeIndex:
        return self.data.index

    @property
    def temp_air(self) -> np.ndarray:
        return self.data["temp_air"].to_numpy()

    @property
    def wind_speed(self) -> np.ndarray:
        return self.data["wind_speed"].to_numpy()

    @property
    def dewpoint(self) -> np.ndarray:
        return self.data["dewpoint"].to_numpy()

    @property
    def seconds(self) -> np.ndarray:
        """Elapsed seconds from the start — the engine's time axis."""
        t = self.times
        return (t - t[0]).total_seconds().to_numpy()

    def summary(self) -> str:
        t = self.data["temp_air"]
        return (
            f"{self.location.name}: {len(self.data)} steps "
            f"({self.times[0]} → {self.times[-1]})\n"
            f"  air temp  min {t.min():+.1f} °C  max {t.max():+.1f} °C  "
            f"mean {t.mean():+.1f} °C"
        )


# ---------------------------------------------------------------------------
# Psychrometrics
# ---------------------------------------------------------------------------
def dewpoint_from_rh(temp_air: np.ndarray, rh: np.ndarray) -> np.ndarray:
    """Dewpoint [°C] from air temperature [°C] and relative humidity [%] (Magnus)."""
    a, b = 17.62, 243.12
    rh = np.clip(rh, 1.0, 100.0)
    gamma = np.log(rh / 100.0) + a * temp_air / (b + temp_air)
    return b * gamma / (a - gamma)


def sky_temperature(
    temp_air: np.ndarray,
    dewpoint: np.ndarray,
    cloud_fraction: float = 0.0,
) -> np.ndarray:
    """
    Effective sky temperature [°C] for long-wave radiative exchange.

    Uses the Berdahl–Martin clear-sky emissivity correlation (a function of
    dewpoint), then corrects for cloud cover. On a clear, dry Ladakh night the
    sky emissivity is low (~0.7), so the sky "sees" as very cold and surfaces
    lose a lot of heat radiatively — the physical reason nights crash.
    """
    T_air_K = temp_air + 273.15
    eps_clear = 0.741 + 0.0062 * dewpoint            # Berdahl–Martin
    eps_clear = np.clip(eps_clear, 0.6, 1.0)
    c = np.clip(cloud_fraction, 0.0, 1.0)
    eps_sky = eps_clear + (1.0 - eps_clear) * c       # clouds -> toward blackbody
    T_sky_K = T_air_K * eps_sky ** 0.25
    return T_sky_K - 273.15


# ---------------------------------------------------------------------------
# Diurnal air-temperature profile
# ---------------------------------------------------------------------------
def _diurnal_temp(
    hour: np.ndarray, t_min: float, t_max: float, hour_min: float, hour_max: float
) -> np.ndarray:
    """
    Smooth asymmetric daily temperature curve: minimum at `hour_min` (≈ sunrise),
    maximum at `hour_max` (≈ mid-afternoon), built from two cosine half-waves so
    the morning rise and the long evening fall are handled separately.
    """
    span_rise = hour_max - hour_min
    span_fall = 24.0 - span_rise
    amp = 0.5 * (t_max - t_min)

    x_rise = (hour - hour_min) / span_rise
    rising = t_min + amp * (1.0 - np.cos(np.pi * x_rise))

    dh = np.mod(hour - hour_max, 24.0)
    x_fall = dh / span_fall
    falling = t_max - amp * (1.0 - np.cos(np.pi * x_fall))

    is_rising = (hour >= hour_min) & (hour <= hour_max)
    return np.where(is_rising, rising, falling)


def synthetic_day(
    location: Location,
    date: str = "2026-01-15",
    t_min: float = -14.0,
    t_max: float = 2.0,
    hour_min: float = 6.0,
    hour_max: float = 15.0,
    wind_speed: float = 2.0,
    relative_humidity: float = 40.0,
    days: int = 2,
    freq_minutes: int = 60,
) -> ClimateSeries:
    """
    Build a realistic *synthetic* ambient day (repeated `days` times so the engine
    can settle into a periodic daily cycle). Defaults describe a clear Leh winter
    day. Every value is overridable — real measured data can be fed via `from_csv`.
    """
    # Defensive bounds so a direct API call can't build a degenerate series:
    # days<1 empties the index (IndexError downstream) and hour_min==hour_max
    # gives a zero rise/fall span that divides by zero in _diurnal_temp.
    days = max(1, int(days))
    freq_minutes = max(1, int(freq_minutes))
    hour_min = float(np.clip(hour_min, 0.0, 22.0))
    hour_max = float(np.clip(hour_max, hour_min + 1.0, 23.5))

    start = pd.Timestamp(date, tz=location.timezone)
    n = max(2, int(days * 24 * 60 / freq_minutes))
    index = pd.date_range(start=start, periods=n, freq=f"{freq_minutes}min")

    hour = index.hour.to_numpy() + index.minute.to_numpy() / 60.0
    temp = _diurnal_temp(hour, t_min, t_max, hour_min, hour_max)
    rh = np.full(n, float(relative_humidity))
    dp = dewpoint_from_rh(temp, rh)

    df = pd.DataFrame(
        {
            "temp_air": temp,
            "wind_speed": np.full(n, float(wind_speed)),
            "relative_humidity": rh,
            "dewpoint": dp,
        },
        index=index,
    )
    return ClimateSeries(location=location, data=df)


def ladakh_winter_day(days: int = 2, freq_minutes: int = 60) -> ClimateSeries:
    """Preset: a clear January day in Leh (min −14 °C, max +2 °C)."""
    return synthetic_day(LEH, days=days, freq_minutes=freq_minutes)


def from_csv(
    path: str,
    location: Location,
    time_col: str = "time",
    temp_col: str = "temp_air",
    wind_col: Optional[str] = "wind_speed",
    rh_col: Optional[str] = "relative_humidity",
) -> ClimateSeries:
    """
    Load measured ambient data from a CSV. Requires a datetime column and an air
    temperature column; wind and humidity are filled with mild defaults if absent.
    Missing solar columns are fine — solar.py will synthesise clear-sky irradiance.
    """
    raw = pd.read_csv(path)
    idx = pd.to_datetime(raw[time_col])
    if idx.dt.tz is None:
        idx = idx.dt.tz_localize(location.timezone)
    df = pd.DataFrame(index=pd.DatetimeIndex(idx))
    df["temp_air"] = raw[temp_col].to_numpy()
    df["wind_speed"] = raw[wind_col].to_numpy() if wind_col in raw else 2.0
    df["relative_humidity"] = raw[rh_col].to_numpy() if rh_col in raw else 40.0
    df["dewpoint"] = dewpoint_from_rh(
        df["temp_air"].to_numpy(), df["relative_humidity"].to_numpy()
    )
    for c in ("ghi", "dni", "dhi"):
        if c in raw:
            df[c] = raw[c].to_numpy()
    return ClimateSeries(location=location, data=df)


if __name__ == "__main__":
    cs = ladakh_winter_day(days=1)
    print(cs.summary())
    print("\nEvery 3 h:")
    sub = cs.data.iloc[::3]
    sky = sky_temperature(sub["temp_air"].to_numpy(), sub["dewpoint"].to_numpy())
    for i, (ts, row) in enumerate(sub.iterrows()):
        print(
            f"  {ts:%H:%M}  air {row['temp_air']:+6.1f} °C   "
            f"dewpoint {row['dewpoint']:+6.1f} °C   sky {sky[i]:+6.1f} °C"
        )
