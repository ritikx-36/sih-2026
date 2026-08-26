#!/usr/bin/env python3
"""
Pre-fetch a real Typical Meteorological Year (TMY) from PVGIS and cache it to CSV.

Run this ONCE with internet access to create the offline demo file the dashboard
falls back to (data/leh_tmy.csv), or to cache any other site. PVGIS is free and
needs no API key.

    python scripts/fetch_tmy.py                                  # Leh -> data/leh_tmy.csv
    python scripts/fetch_tmy.py --lat 34.43 --lon 75.75 \
        --name "Drass, Kargil" --out data/drass_tmy.csv

The dashboard also fetches live per-site when you pick "Real TMY"; this script just
guarantees an offline copy so a demo never depends on a flaky conference network.
"""
import argparse
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from thermalshelter import climate


def main() -> int:
    p = argparse.ArgumentParser(description="Fetch a PVGIS TMY and save it as CSV.")
    p.add_argument("--lat", type=float, default=climate.LEH.latitude, help="latitude °N")
    p.add_argument("--lon", type=float, default=climate.LEH.longitude, help="longitude °E")
    p.add_argument("--alt", type=float, default=climate.LEH.altitude, help="altitude m")
    p.add_argument("--albedo", type=float, default=climate.LEH.albedo, help="ground albedo")
    p.add_argument("--name", default=climate.LEH.name, help="site label")
    p.add_argument("--out", default=os.path.join("data", "leh_tmy.csv"), help="output CSV path")
    a = p.parse_args()

    loc = climate.Location(name=a.name, latitude=a.lat, longitude=a.lon,
                           altitude=a.alt, timezone="Asia/Kolkata", albedo=a.albedo)
    print(f"Fetching PVGIS TMY for {a.name} ({a.lat:.3f}, {a.lon:.3f})…")
    cs = climate.from_pvgis_tmy(loc)   # NETWORK

    out = os.path.abspath(a.out)
    os.makedirs(os.path.dirname(out), exist_ok=True)
    cs.data.to_csv(out, index_label="time")   # from_csv default time_col="time" reads this back
    print(cs.summary())
    print(f"\nSaved {len(cs.data):,} hourly rows -> {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
