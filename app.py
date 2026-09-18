"""
Thermal-Shelter — interactive passive-design studio (Streamlit).

Drag the controls to design an area-specific shelter for a chosen cold-region site;
the app simulates it with the transient engine and shows, live, how it performs
against a baseline hut:

    • indoor temperature over time            (PS output 1)
    • solar thermal energy captured           (PS output 2)
    • heat-flow vs ambient over time          (PS output 3)

Run:  ./.venv/bin/streamlit run app.py

SIH 2026 · Problem Statement 26051 (DRDO, Software).
"""
import os

import numpy as np
import plotly.graph_objects as go
import streamlit as st

from thermalshelter import annual, climate, comfort, engine, geometry, impact
from thermalshelter.materials import get_material

# --------------------------------------------------------------------------- #
#  Presets & palette
# --------------------------------------------------------------------------- #
GLAZING = {
    "Single glazing": geometry.SINGLE_GLAZING,
    "Double glazing": geometry.DOUBLE_GLAZING,
    "Double, low-e": geometry.DOUBLE_LOWE,
}
MASS_MATERIAL = {
    "Water wall": "Water (storage wall)",
    "Concrete": "Dense concrete",
    "PCM (paraffin ~22 C)": "PCM (paraffin, ~22°C)",
}
# Representative cold, high-altitude deployment sites — the problem statement's
# domain. Each sets the solar-relevant geography (lat/lon/altitude), the ground
# snow albedo, and a typical clear-winter-day temperature range (editable below).
# The engine itself is location-agnostic; these are just convenient starting points.
REGIONS = {
    "Leh, Ladakh":    dict(lat=34.15, lon=77.57, alt=3500, albedo=0.70, t_min=-14.0, t_max=2.0),
    "Drass, Kargil":  dict(lat=34.43, lon=75.75, alt=3230, albedo=0.75, t_min=-23.0, t_max=-4.0),
    "Siachen (base)": dict(lat=35.35, lon=77.00, alt=3600, albedo=0.80, t_min=-25.0, t_max=-8.0),
    "Tawang":         dict(lat=27.59, lon=91.87, alt=3050, albedo=0.45, t_min=-4.0, t_max=9.0),
}
# Uninsulated roof/floor, mirroring scripts/run_demo.py baseline
BARE_ROOF = geometry.make_construction("Bare timber roof", [("Softwood timber (pine)", 0.04)])
BARE_FLOOR = geometry.make_construction("Bare concrete floor", [("Dense concrete", 0.15)])

COMFORT_LO, COMFORT_HI = 18.0, 24.0
C_AMB, C_BASE, C_DESIGN, C_BAND, C_MASS = "#8a8a8a", "#d9534f", "#1f77b4", "#8fd19e", "#f0ad4e"

# Real-weather data locations (bundled demo file is committed; the per-site cache is
# written on the first live PVGIS fetch and is git-ignored).
_HERE = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(_HERE, "data")
DATA_CACHE = os.path.join(DATA_DIR, "cache")
BUNDLED_LEH = os.path.join(DATA_DIR, "leh_tmy.csv")
MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun",
          "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]
DAYS_IN_MONTH = [31, 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31]


# --------------------------------------------------------------------------- #
#  Pure compute (no st.* here) — cached
# --------------------------------------------------------------------------- #
def _location(geo):
    # geo = (name, lat, lon, alt, albedo) — a preset or a user-entered custom site
    name, lat, lon, alt, albedo = geo
    return climate.Location(name=name, latitude=lat, longitude=lon,
                            altitude=alt, timezone="Asia/Kolkata", albedo=albedo)


@st.cache_data(show_spinner="Fetching real weather (PVGIS TMY)…")
def _fetch_tmy(geo):
    """Real TMY for a site, cached in-session and to disk. Tries the on-disk cache,
    then a live PVGIS download (persisted for next time), then the bundled Leh TMY as
    offline demo insurance. Returns (ClimateSeries | None, status) where status is one
    of "cache" | "live" | "fallback" | "error". No st.* here — it runs inside caching."""
    name, lat, lon, alt, albedo = geo
    loc = climate.Location(name=name, latitude=lat, longitude=lon,
                           altitude=alt, timezone="Asia/Kolkata", albedo=albedo)
    cache_path = os.path.join(DATA_CACHE, f"{lat:.3f}_{lon:.3f}.csv")
    if os.path.exists(cache_path):
        try:
            return climate.from_csv(cache_path, loc), "cache"
        except Exception:
            pass
    try:
        cs = climate.from_pvgis_tmy(loc)             # NETWORK (first fetch per site)
        try:
            os.makedirs(DATA_CACHE, exist_ok=True)
            cs.data.to_csv(cache_path, index_label="time")
        except OSError:
            pass
        return cs, "live"
    except Exception:
        if os.path.exists(BUNDLED_LEH):
            try:
                return climate.from_csv(BUNDLED_LEH, climate.LEH), "fallback"
            except Exception:
                pass
        return None, "error"


def _climate(wx, geo, days, t_min, t_max):
    if wx == "real":
        cs_full, _status = _fetch_tmy(geo)
        # live clip = a representative January day (the cold-design case); the full
        # year is used by the Seasonal tab. The top-level probe already st.stop()s
        # if no real data is available, so cs_full is not None here.
        return climate.representative_day(cs_full, month=1, days=int(days))
    t_max = max(t_max, t_min + 1.0)          # keep the daily swing sane
    return climate.synthetic_day(_location(geo), t_min=t_min, t_max=t_max,
                                 days=int(days), freq_minutes=30)


def _build_shelter(insulated, glazing_key, wwr, facades, orientation,
                   L, W, H, ach, mass_kind, mass_vol, mass_area):
    if insulated:
        wall, roof, floor = (geometry.INSULATED_WALL, geometry.INSULATED_ROOF,
                             geometry.INSULATED_FLOOR)
    else:
        wall, roof, floor = geometry.UNINSULATED_STONE, BARE_ROOF, BARE_FLOOR

    mass = []
    if mass_kind != "None" and mass_vol > 0:
        mass = [geometry.ThermalMass(
            name=f"{mass_kind} ({mass_vol * 1000:.0f} L)",
            material=get_material(MASS_MATERIAL[mass_kind]),
            volume=mass_vol, surface_area=mass_area)]

    return geometry.box_shelter(
        length=L, width=W, height=H, orientation=orientation,
        wall=wall, roof=roof, floor=floor,
        glazing=GLAZING[glazing_key], window_wall_ratio=wwr,
        window_facades=tuple(facades) if facades else (),
        infiltration_ach=ach, thermal_mass=mass, name="Your design")


def _baseline_shelter(L, W, H, orientation):
    """The naive reference hut — same size/orientation as the design, poor envelope."""
    return geometry.box_shelter(
        length=L, width=W, height=H, orientation=orientation,
        wall=geometry.UNINSULATED_STONE, roof=BARE_ROOF, floor=BARE_FLOOR,
        glazing=geometry.SINGLE_GLAZING, window_wall_ratio=0.12,
        window_facades=("S",), infiltration_ach=2.0, name="Baseline hut")


@st.cache_data(show_spinner=False)
def run_design(wx, geo, days, t_min, t_max, insulated, glazing_key, wwr, facades, orientation,
               L, W, H, ach, mass_kind, mass_vol, mass_area, setpoint, vent_high):
    clim = _climate(wx, geo, days, t_min, t_max)
    shelter = _build_shelter(insulated, glazing_key, wwr, facades, orientation,
                             L, W, H, ach, mass_kind, mass_vol, mass_area)
    free = engine.simulate(shelter, clim, vent_high=vent_high)         # temperature curve
    heated = engine.simulate(shelter, clim, heating_setpoint=setpoint)  # aux demand
    day = free.last_day()
    return {
        "time_days": free.time_h / 24.0,
        "T_in": free.T_in, "T_out": free.T_out,
        "storage": {k: v for k, v in free.T_storage.items()},
        "flux": {k: v for k, v in free.flux.items()},
        "metrics": comfort.comfort_metrics(day),
        "energy": free.energy_per_day(),
        "aux": heated.energy_per_day()["aux_heating"],
        "summary": shelter.summary(),
    }


@st.cache_data(show_spinner=False)
def run_baseline(wx, geo, days, t_min, t_max, setpoint, L, W, H, orientation):
    """Reference hut of the SAME size and orientation as the design, but with a
    naive envelope: uninsulated, leaky, single-glazed. Matching the geometry keeps
    the '% less heating' comparison honest — it isolates the envelope and passive-
    design gains instead of conflating them with a change in shelter size."""
    clim = _climate(wx, geo, days, t_min, t_max)
    shelter = _baseline_shelter(L, W, H, orientation)
    free = engine.simulate(shelter, clim)
    heated = engine.simulate(shelter, clim, heating_setpoint=setpoint)
    return {"time_days": free.time_h / 24.0, "T_in": free.T_in,
            "aux": heated.energy_per_day()["aux_heating"]}


# --------------------------------------------------------------------------- #
#  Auto-optimiser — search sensible passive options for the least heating
# --------------------------------------------------------------------------- #
OPT_GLAZING = ["Double glazing", "Double, low-e"]
OPT_WWR = [0.25, 0.35]
OPT_FACADES = [("S",), ("S", "E", "W")]
OPT_MASS = [("Water wall", 1.0, 6.0), ("Water wall", 2.0, 9.0), ("PCM (paraffin ~22 C)", 1.0, 6.0)]
OPT_ORIENT = (135, 180, 225)                       # SE / S / SW — the useful winter arc
FACADE_LABEL = {("S",): "S", ("S", "E", "W"): "S + E + W"}
ORIENT_LABEL = {135: "135° (SE)", 180: "180° (S)", 225: "225° (SW)"}
N_CANDIDATES = (len(OPT_GLAZING) * len(OPT_WWR) * len(OPT_FACADES)
                * len(OPT_MASS) * len(OPT_ORIENT))


@st.cache_data(show_spinner=False)
def _aux_only(wx, geo, days, t_min, t_max, glazing_key, wwr, facades,
              orientation, L, W, H, ach, mass_kind, mass_vol, mass_area, setpoint):
    """Heating demand (kWh/day) for one candidate — a single heated simulation."""
    clim = _climate(wx, geo, days, t_min, t_max)
    shelter = _build_shelter(True, glazing_key, wwr, facades, orientation,
                             L, W, H, ach, mass_kind, mass_vol, mass_area)
    return engine.simulate(shelter, clim, heating_setpoint=setpoint).energy_per_day()["aux_heating"]


@st.cache_data(show_spinner=False)
def optimize(wx, geo, days, t_min, t_max, L, W, H, ach, setpoint):
    """Rank passive options by heating demand, lowest first. Site, size and air-leakage
    stay at the user's values; the search spans glazing, window area & facades, thermal
    mass AND orientation (insulated envelope assumed)."""
    out = []
    for ori in OPT_ORIENT:
        for g in OPT_GLAZING:
            for wwr in OPT_WWR:
                for fac in OPT_FACADES:
                    for mk, mv, ma in OPT_MASS:
                        aux = _aux_only(wx, geo, days, t_min, t_max, g, wwr, fac,
                                        ori, L, W, H, ach, mk, mv, ma, setpoint)
                        out.append(dict(glazing=g, wwr=wwr, facades=fac, orientation=ori,
                                        mass_kind=mk, mass_vol=mv, mass_area=ma, aux=aux))
    out.sort(key=lambda x: x["aux"])
    return out


@st.cache_data(show_spinner=False)
def run_annual(geo, insulated, glazing_key, wwr, facades, orientation,
               L, W, H, ach, mass_kind, mass_vol, mass_area, setpoint, vent_high, days):
    """Month-by-month heating & comfort for the current design vs the baseline, using
    the site's real TMY. Heavy (12 months × 3 sims) but ~1 s and cached per design."""
    cs_full, _status = _fetch_tmy(geo)
    if cs_full is None:
        return None
    design = _build_shelter(insulated, glazing_key, wwr, facades, orientation,
                            L, W, H, ach, mass_kind, mass_vol, mass_area)
    baseline = _baseline_shelter(L, W, H, orientation)
    return annual.annual_profile(cs_full, design, baseline, setpoint,
                                 vent_high=vent_high, days=int(days))


@st.cache_data(show_spinner=False)
def run_annual_energy(geo, insulated, glazing_key, wwr, facades, orientation,
                      L, W, H, ach, mass_kind, mass_vol, mass_area, setpoint):
    """Canonical annual heating from one **continuous 8760-hour** run per shelter (design
    and baseline), with auxiliary energy bucketed by calendar month. Physically faithful
    (thermal storage coasts across days/seasons) where a representative day over-states
    stored-heat designs. Heavier than the rep-day profile (~5 s) but cached per design."""
    cs_full, _status = _fetch_tmy(geo)
    if cs_full is None:
        return None
    design = _build_shelter(insulated, glazing_key, wwr, facades, orientation,
                            L, W, H, ach, mass_kind, mass_vol, mass_area)
    baseline = _baseline_shelter(L, W, H, orientation)
    return {
        "design": annual.annual_energy(cs_full, design, setpoint),
        "baseline": annual.annual_energy(cs_full, baseline, setpoint),
    }


# --------------------------------------------------------------------------- #
#  UI
# --------------------------------------------------------------------------- #
st.set_page_config(page_title="Thermal-Shelter", page_icon=":material/device_thermostat:", layout="wide")

# ---- sidebar: design controls -------------------------------------------- #
sb = st.sidebar
sb.title("Design controls")

with sb.expander("Climate & region", expanded=True):
    region_key = st.selectbox("Region", list(REGIONS) + ["Custom location"], index=0,
                              help="Deployment site — sets latitude, altitude, snow albedo "
                                   "and a typical clear-winter-day temperature range. Pick a "
                                   "preset, or choose Custom location to enter any site on Earth.")
    if region_key == "Custom location":
        cc1, cc2 = st.columns(2)
        lat = cc1.number_input("Latitude (°N)", -90.0, 90.0, 34.0, 0.5,
                               help="Where the sun sits in the sky. Positive = northern hemisphere.")
        alt = cc2.number_input("Altitude (m)", 0, 8000, 3500, 100,
                               help="Higher = thinner air = stronger, sharper sun.")
        albedo = st.slider("Ground reflectivity (albedo)", 0.10, 0.90, 0.60, 0.05,
                           help="How much sunlight the ground reflects back up. "
                                "Fresh snow ≈ 0.8, old snow ≈ 0.5, bare ground ≈ 0.2.")
        lon = 77.0
        loc_name = "Custom location"
        site_label = f"a custom site ({lat:.1f}°N, {int(alt):,} m)"
        def_tmin, def_tmax = -14.0, 2.0
    else:
        r = REGIONS[region_key]
        lat, lon, alt, albedo = r["lat"], r["lon"], r["alt"], r["albedo"]
        loc_name = site_label = region_key
        def_tmin, def_tmax = r["t_min"], r["t_max"]
    geo = (loc_name, lat, lon, alt, albedo)

    wx_label = st.radio(
        "Weather data", ["Synthetic clear day", "Real TMY (PVGIS)"],
        index=0, horizontal=True,
        help="Synthetic = one idealized clear day from your sliders (fast, always available). "
             "Real TMY = a Typical Meteorological Year for this site — a representative year built "
             "from long-term records (real clouds and irradiance), fetched live from PVGIS and "
             "cached — this also unlocks the Seasonal tab.")
    wx = "real" if wx_label.startswith("Real") else "synthetic"

    days = st.slider("Days simulated", 1, 7, 5)
    if wx == "synthetic":
        t_min = st.slider("Coldest night (°C)", -40.0, 5.0, def_tmin, 1.0, key=f"tmin_{region_key}")
        t_max = st.slider("Warmest afternoon (°C)", -20.0, 20.0, def_tmax, 1.0, key=f"tmax_{region_key}")
    else:
        # Real TMY mode: hide temperature sliders to avoid confusion
        t_min, t_max = def_tmin, def_tmax
        st.info("**Real TMY mode**: Using actual measured weather data for this site. "
                "Indoor results are driven by the site's Typical Meteorological Year. "
                "Open the **Seasonal** tab to see the full year's performance.")

with sb.expander("Envelope", expanded=True):
    insulated = st.radio("Construction", ["Well-insulated", "Uninsulated"],
                         index=0, horizontal=True) == "Well-insulated"
    glazing_key = st.selectbox("Glazing", list(GLAZING), index=1)
    wwr = st.slider("Window-wall ratio", 0.05, 0.50, 0.30, 0.01)
    facades = st.multiselect("Window facades", ["N", "E", "S", "W"], default=["S"])
    orientation = st.slider("Front wall faces (° from North)", 0, 359, 180, 5,
                            help="180° = south-facing, the ideal for winter solar gain")
    ach = st.slider("Air leakage (air changes / hour)", 0.2, 3.0, 0.5, 0.1)

with sb.expander("Geometry", expanded=False):
    L = st.slider("Length (m)", 3.0, 12.0, 6.0, 0.5)
    W = st.slider("Width (m)", 3.0, 10.0, 4.0, 0.5)
    H = st.slider("Height (m)", 2.2, 4.0, 2.6, 0.1)

with sb.expander("Thermal mass (heat battery)", expanded=True):
    mass_kind = st.selectbox("Store", ["None", "Water wall", "Concrete", "PCM (paraffin ~22 C)"],
                             index=1)
    if mass_kind != "None":
        mass_vol = st.slider("Volume (m³)", 0.2, 3.0, 1.0, 0.1)
        mass_area = st.slider("Exposed area (m²)", 2.0, 12.0, 6.0, 0.5)
    else:
        mass_vol, mass_area = 0.0, 0.0

with sb.expander("Operation", expanded=False):
    setpoint = st.slider("Heating setpoint (°C)", 15.0, 24.0, 20.0, 0.5,
                         help="Target the heater holds; used for the energy comparison")
    do_vent = st.checkbox("Vent to prevent overheating", value=True)
    vent_high = st.slider("Vent when above (°C)", 22.0, 30.0, 24.0, 0.5) if do_vent else None

# ---- run --------------------------------------------------------------- #
# Real-weather probe: prime the (cached) TMY fetch once so a status message can be
# shown at the top level, and stop early with a clear message if none is available.
tmy_status = None
if wx == "real":
    _tmy_cs, tmy_status = _fetch_tmy(geo)
    if _tmy_cs is None:
        st.error("Real weather is unavailable: PVGIS was unreachable and no cached or bundled "
                 "TMY was found. Run `python scripts/fetch_tmy.py` once with internet access to "
                 "cache it, or switch **Weather data** back to *Synthetic clear day*.")
        st.stop()

d = run_design(wx, geo, days, t_min, t_max, insulated, glazing_key, wwr, tuple(facades),
               orientation, L, W, H, ach, mass_kind, mass_vol, mass_area, setpoint, vent_high)
b = run_baseline(wx, geo, days, t_min, t_max, setpoint, L, W, H, orientation)

m = d["metrics"]
solar = d["energy"]["solar_windows"]              # useful solar into the room (through glass)
incident = solar + d["energy"]["solar_opaque"]    # total sun absorbed on the whole shell
aux, base_aux = d["aux"], b["aux"]
saving = (1 - aux / base_aux) * 100 if base_aux else 0.0

# Guard: if any headline value came back non-finite (an unstable or degenerate
# configuration), say so clearly instead of rendering "nan" metrics, a broken
# chart, and a meaningless optimiser ranking.
_scalars = (m["mean"], m["night_low"], solar, aux, base_aux)
_arrays = (d["T_in"], b["T_in"])
if not (all(np.isfinite(v) for v in _scalars)
        and all(np.all(np.isfinite(a)) for a in _arrays)):
    st.error("This configuration produced non-finite values (NaN / ∞) — usually an "
             "extreme or numerically unstable combination of inputs. Try adding thermal "
             "mass, reducing air leakage, or shrinking the window area.")
    st.stop()

# ---- header ------------------------------------------------------------ #
st.title("Thermal-Shelter — passive design studio")
st.caption(f"Design an area-specific shelter for {site_label} and see how warm it stays — "
           "and how little heating it needs — against a baseline hut.  "
           "SIH 2026 · PS 26051 (DRDO, Software).")

if wx == "real" and tmy_status == "live":
    st.caption(f"Live PVGIS Typical Meteorological Year for {site_label} — cached for next time.")
elif wx == "real" and tmy_status == "cache":
    st.caption(f"PVGIS Typical Meteorological Year for {site_label} (cached).")
elif wx == "real" and tmy_status == "fallback":
    st.warning("PVGIS was unreachable — showing the **bundled Leh TMY** as a stand-in for this site.")

k1, k2, k3, k4, k5 = st.columns(5)
k1.metric("Mean indoor (°C)", f"{m['mean']:.1f}")
k2.metric("Coldest night (°C)", f"{m['night_low']:.1f}")
k3.metric("Time comfortable", f"{m['comfort_fraction'] * 100:.0f} %",
          help="Share of the final day within 18–24 °C")
k4.metric("Solar gain (kWh/day)", f"{solar:.1f}",
          help="Useful solar entering through the glazing")
k5.metric("Heating needed (kWh/day)", f"{aux:.1f}",
          help="Auxiliary heat to hold the setpoint")

if base_aux and saving >= 0:
    st.success(f"**This design needs {saving:.0f}% less heating than the baseline hut** "
               f"to hold {setpoint:.0f} °C  ({aux:.1f} vs {base_aux:.1f} kWh/day).")
    fi = impact.fuel_impact(base_aux - aux)
    st.caption(
        f"That is about **{fi.litres:.1f} L of kerosene, ₹{fi.inr:,.0f} and {fi.co2_kg:.1f} kg CO₂ "
        f"saved per day** — roughly **{fi.litres * impact.WINTER_DAYS:,.0f} L, "
        f"₹{fi.inr * impact.WINTER_DAYS:,.0f} and {fi.co2_kg * impact.WINTER_DAYS / 1000:.1f} t CO₂** "
        f"over a {impact.WINTER_DAYS}-day winter "
        f"(heater at {impact.HEATER_EFFICIENCY * 100:.0f}% efficiency, ₹{impact.INR_PER_L:.0f}/L).")
elif base_aux:
    st.warning(f"This design needs **{-saving:.0f}% more** heating than the baseline "
               f"({aux:.1f} vs {base_aux:.1f} kWh/day) — try more insulation, south glazing, or mass.")

# ---- auto-optimiser ---------------------------------------------------- #
with st.expander("Auto-optimise — let the tool search for the best passive design", expanded=False):
    st.caption(f"Holds your current site, size ({L:.0f}×{W:.0f}×{H:.1f} m) and air-leakage "
               f"fixed, then simulates {N_CANDIDATES} combinations of glazing, window area, window "
               f"facades, thermal mass and orientation to find the one that needs the least "
               f"heating (insulated envelope assumed).")
    if st.button("Find the best design", type="primary"):
        with st.spinner(f"Simulating {N_CANDIDATES} candidate designs…"):
            ranked = optimize(wx, geo, days, t_min, t_max, L, W, H, ach, setpoint)
        best = ranked[0]
        best_saving = (1 - best["aux"] / base_aux) * 100 if base_aux else 0.0
        st.success(
            f"**Best design — {best['glazing']}, {best['wwr'] * 100:.0f}% windows on "
            f"{FACADE_LABEL[best['facades']]}, facing {ORIENT_LABEL[best['orientation']]}, "
            f"{best['mass_kind']} {best['mass_vol']:.1f} m³**  →  "
            f"**{best['aux']:.1f} kWh/day**, {best_saving:.0f}% less heating than the baseline hut.")
        if base_aux:
            fib = impact.fuel_impact(base_aux - best["aux"])
            st.caption(f"≈ **{fib.litres:.1f} L kerosene · ₹{fib.inr:,.0f} · {fib.co2_kg:.1f} kg CO₂** "
                       f"saved per day versus the baseline hut.")
        delta = aux - best["aux"]
        if delta > 0.1:
            st.caption(f"That is **{delta:.1f} kWh/day less** than the design currently on screen "
                       f"({aux:.1f} kWh/day). Set these values in the sidebar to apply it.")
        else:
            st.caption("Your current design is already at or near the best in this search.")
        st.dataframe(
            [{"Glazing": r["glazing"],
              "Windows": f"{r['wwr'] * 100:.0f}% {FACADE_LABEL[r['facades']]}",
              "Facing": ORIENT_LABEL[r["orientation"]],
              "Thermal mass": f"{r['mass_kind']} {r['mass_vol']:.1f} m³",
              "Heating (kWh/day)": round(r["aux"], 1),
              "vs baseline": f"{(1 - r['aux'] / base_aux) * 100:.0f}% less" if base_aux else "—"}
             for r in ranked[:5]],
            hide_index=True, width="stretch")

# ---- tabs -------------------------------------------------------------- #
tab_t, tab_e, tab_f, tab_s = st.tabs(
    ["Temperature", "Energy balance", "Heat-flow over time", "Seasonal (all year)"])

with tab_t:
    fig = go.Figure()
    fig.add_hrect(y0=COMFORT_LO, y1=COMFORT_HI, fillcolor=C_BAND, opacity=0.25,
                  line_width=0, annotation_text="comfort band", annotation_position="top left")
    fig.add_hline(y=0, line_color="#cccccc", line_width=1)
    # subtle night shading (18:00–08:00) so the post-sunset crash reads at a glance
    _tmax = float(d["time_days"][-1])
    for _k in range(int(np.ceil(_tmax)) + 1):
        fig.add_vrect(x0=_k + 18.0 / 24.0, x1=_k + 1 + 8.0 / 24.0,
                      fillcolor="#3a4a63", opacity=0.05, line_width=0, layer="below")
    fig.add_trace(go.Scatter(x=d["time_days"], y=d["T_out"], name="ambient air",
                             line=dict(color=C_AMB, dash="dash", width=1.5)))
    fig.add_trace(go.Scatter(x=b["time_days"], y=b["T_in"], name="baseline hut",
                             line=dict(color=C_BASE, width=2.2)))
    for k, v in d["storage"].items():
        fig.add_trace(go.Scatter(x=d["time_days"], y=v, name=k,
                                 line=dict(color=C_MASS, dash="dashdot", width=1.4), opacity=0.75))
    fig.add_trace(go.Scatter(x=d["time_days"], y=d["T_in"], name="your design",
                             line=dict(color=C_DESIGN, width=3)))
    # mark the design's coldest point on the settled final day (the "money moment")
    _tin, _td = np.asarray(d["T_in"]), np.asarray(d["time_days"])
    _mask = _td >= (_td[-1] - 1.0)
    if _mask.any():
        _j = np.where(_mask)[0][int(np.argmin(_tin[_mask]))]
        fig.add_annotation(x=_td[_j], y=_tin[_j], text=f"night low {_tin[_j]:.1f} °C",
                           showarrow=True, arrowhead=2, ax=0, ay=32,
                           font=dict(color=C_DESIGN, size=12), arrowcolor=C_DESIGN)
    fig.update_layout(height=470, xaxis_title="day", yaxis_title="temperature (°C)",
                      legend=dict(orientation="h", y=1.02, yanchor="bottom", x=0),
                      margin=dict(l=10, r=10, t=10, b=10))
    st.plotly_chart(fig, width="stretch")
    st.caption("Both shelters start from the same cold state. A good passive design charges "
               "its thermal mass over sunny days and climbs toward the comfort band on solar alone.")

with tab_e:
    e = d["energy"]
    rows = [
        ("Solar through windows", e["solar_windows"]),
        ("Envelope conduction", e["envelope_conduction"]),
        ("Window conduction", e["window_conduction"]),
        ("Air leakage", e["infiltration"]),
        ("Thermal-mass exchange", e["storage_exchange"]),
    ]
    labels = [r[0] for r in rows]
    vals = [r[1] for r in rows]
    colors = ["#2ea44f" if v >= 0 else "#d9534f" for v in vals]
    fig2 = go.Figure(go.Bar(x=vals, y=labels, orientation="h", marker_color=colors,
                            text=[f"{v:+.1f}" for v in vals], textposition="outside"))
    fig2.update_layout(height=430, margin=dict(l=10, r=10, t=10, b=10),
                       xaxis_title="energy into indoor air (kWh/day)   —   positive = gain, negative = loss")
    fig2.update_yaxes(autorange="reversed")
    st.plotly_chart(fig2, width="stretch")
    st.caption(
        f"Net heat flow **into the indoor air** (free-float, no heater). Solar enters through the "
        f"glazing at **{solar:.1f} kWh/day**; the envelope, window and air-leak terms already "
        f"include long-wave cooling to the cold night sky. The shell also soaks up "
        f"~{incident - solar:.0f} kWh/day of sun on its opaque walls and roof, but re-radiates most "
        f"of it straight back — which is exactly why the glazing and thermal mass do the real work.")

with tab_f:
    f = d["flux"]
    flow_map = [("solar_windows", "Solar through windows", "#f4b400"),
                ("envelope", "Envelope conduction", C_DESIGN),
                ("window_cond", "Window conduction", "#4a90d9"),
                ("infiltration", "Air leakage", "#7cb3e8"),
                ("storage", "Thermal-mass exchange", C_MASS)]
    fig3 = go.Figure()
    for key, label, color in flow_map:
        if key in f:
            fig3.add_trace(go.Scatter(x=d["time_days"], y=f[key], name=label,
                                     line=dict(color=color, width=1.7)))
    fig3.add_hline(y=0, line_color="#cccccc", line_width=1)
    fig3.update_layout(height=470, xaxis_title="day", yaxis_title="heat flow into indoor air (W)",
                       legend=dict(orientation="h", y=1.02, yanchor="bottom", x=0),
                       margin=dict(l=10, r=10, t=10, b=10))
    st.plotly_chart(fig3, width="stretch")
    st.caption("Positive = heat flowing into the room, negative = heat leaving. Watch solar spike "
               "by day and the thermal-mass line turn positive after sunset as the store discharges.")

with tab_s:
    if wx != "real":
        st.info("Switch **Weather data** to *Real TMY (PVGIS)* in the sidebar to simulate the "
                "shelter across all 12 months of a Typical Meteorological Year for this site.")
    else:
        st.caption("Month-by-month heating from a continuous full-year (8760-hour) run on the "
                   "site's PVGIS TMY, with a representative-day comfort curve. This is the "
                   "proof the shelter performs **all year**, not just on the coldest design day.")
        if st.button("Run annual simulation (full year)", type="primary"):
            with st.spinner("Simulating a full year (8760 h) + monthly comfort…"):
                prof = run_annual(geo, insulated, glazing_key, wwr, tuple(facades), orientation,
                                  L, W, H, ach, mass_kind, mass_vol, mass_area,
                                  setpoint, vent_high, days)
                en = run_annual_energy(geo, insulated, glazing_key, wwr, tuple(facades),
                                       orientation, L, W, H, ach, mass_kind, mass_vol,
                                       mass_area, setpoint)
            if not prof or not en:
                st.error("Annual run unavailable — no real weather for this site.")
            else:
                dim = np.array(DAYS_IN_MONTH)
                da = np.array(en["design"]["aux_kwh"]) / dim       # continuous kWh/day
                ba = np.array(en["baseline"]["aux_kwh"]) / dim
                cf = np.array(prof["comfort"]) * 100.0             # rep-day comfort curve
                figs = go.Figure()
                figs.add_trace(go.Bar(x=MONTHS, y=ba, name="baseline hut", marker_color=C_BASE))
                figs.add_trace(go.Bar(x=MONTHS, y=da, name="your design", marker_color=C_DESIGN))
                figs.add_trace(go.Scatter(x=MONTHS, y=cf, name="time comfortable (%)",
                                          yaxis="y2", mode="lines+markers",
                                          line=dict(color=C_MASS, width=2.5)))
                figs.update_layout(
                    height=470, barmode="group", xaxis_title="month",
                    yaxis=dict(title="heating (kWh/day)"),
                    yaxis2=dict(title="time comfortable (%)", overlaying="y", side="right",
                                range=[0, 100], showgrid=False),
                    legend=dict(orientation="h", y=1.02, yanchor="bottom", x=0),
                    margin=dict(l=10, r=10, t=10, b=10))
                st.plotly_chart(figs, width="stretch")

                # annual totals: exact integrals from the continuous full-year runs
                design_yr = float(en["design"]["annual_kwh"])
                base_yr = float(en["baseline"]["annual_kwh"])
                fi = impact.fuel_impact(base_yr - design_yr)
                c1, c2, c3 = st.columns(3)
                c1.metric("Heating saved / year", f"{base_yr - design_yr:,.0f} kWh")
                c2.metric("Kerosene saved / year", f"{fi.litres:,.0f} L")
                c3.metric("CO₂ avoided / year", f"{fi.co2_kg / 1000:.1f} t")
                st.caption(
                    f"Over a full year (a continuous 8760-hour run) this design needs "
                    f"**{design_yr:,.0f} kWh** of heating vs **{base_yr:,.0f} kWh** for the "
                    f"baseline hut — about **{fi.litres:,.0f} L of kerosene and ₹{fi.inr:,.0f}** "
                    f"saved. Winter months carry the load; summer sits near zero. The comfort "
                    f"line is the share of each representative day the free-floating design "
                    f"stays within 18–24 °C.")

with st.expander("Shelter details"):
    st.text(d["summary"])
