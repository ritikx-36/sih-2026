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
import numpy as np
import plotly.graph_objects as go
import streamlit as st

from thermalshelter import climate, comfort, engine, geometry
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


# --------------------------------------------------------------------------- #
#  Pure compute (no st.* here) — cached
# --------------------------------------------------------------------------- #
def _location(region_key):
    r = REGIONS[region_key]
    return climate.Location(name=region_key, latitude=r["lat"], longitude=r["lon"],
                            altitude=r["alt"], timezone="Asia/Kolkata", albedo=r["albedo"])


def _climate(region_key, days, t_min, t_max):
    t_max = max(t_max, t_min + 1.0)          # keep the daily swing sane
    return climate.synthetic_day(_location(region_key), t_min=t_min, t_max=t_max,
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


@st.cache_data(show_spinner=False)
def run_design(region_key, days, t_min, t_max, insulated, glazing_key, wwr, facades, orientation,
               L, W, H, ach, mass_kind, mass_vol, mass_area, setpoint, vent_high):
    clim = _climate(region_key, days, t_min, t_max)
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
def run_baseline(region_key, days, t_min, t_max, setpoint):
    """Fixed reference: an existing-style uninsulated, leaky, single-glazed hut."""
    clim = _climate(region_key, days, t_min, t_max)
    shelter = geometry.box_shelter(
        wall=geometry.UNINSULATED_STONE, roof=BARE_ROOF, floor=BARE_FLOOR,
        glazing=geometry.SINGLE_GLAZING, window_wall_ratio=0.12,
        window_facades=("S",), infiltration_ach=2.0, name="Baseline hut")
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
FACADE_LABEL = {("S",): "S", ("S", "E", "W"): "S + E + W"}
N_CANDIDATES = len(OPT_GLAZING) * len(OPT_WWR) * len(OPT_FACADES) * len(OPT_MASS)


@st.cache_data(show_spinner=False)
def _aux_only(region_key, days, t_min, t_max, glazing_key, wwr, facades,
              orientation, L, W, H, ach, mass_kind, mass_vol, mass_area, setpoint):
    """Heating demand (kWh/day) for one candidate — a single heated simulation."""
    clim = _climate(region_key, days, t_min, t_max)
    shelter = _build_shelter(True, glazing_key, wwr, facades, orientation,
                             L, W, H, ach, mass_kind, mass_vol, mass_area)
    return engine.simulate(shelter, clim, heating_setpoint=setpoint).energy_per_day()["aux_heating"]


@st.cache_data(show_spinner=False)
def optimize(region_key, days, t_min, t_max, orientation, L, W, H, ach, setpoint):
    """Rank passive-envelope options by heating demand, lowest first. Site,
    geometry and air-leakage stay at the user's values; insulated envelope assumed."""
    out = []
    for g in OPT_GLAZING:
        for wwr in OPT_WWR:
            for fac in OPT_FACADES:
                for mk, mv, ma in OPT_MASS:
                    aux = _aux_only(region_key, days, t_min, t_max, g, wwr, fac,
                                    orientation, L, W, H, ach, mk, mv, ma, setpoint)
                    out.append(dict(glazing=g, wwr=wwr, facades=fac,
                                    mass_kind=mk, mass_vol=mv, mass_area=ma, aux=aux))
    out.sort(key=lambda x: x["aux"])
    return out


# --------------------------------------------------------------------------- #
#  UI
# --------------------------------------------------------------------------- #
st.set_page_config(page_title="Thermal-Shelter", page_icon="🏔️", layout="wide")

# ---- sidebar: design controls -------------------------------------------- #
sb = st.sidebar
sb.title("Design controls")

with sb.expander("Climate & region", expanded=True):
    region_key = st.selectbox("Region", list(REGIONS), index=0,
                              help="Deployment site — sets latitude, altitude, snow albedo "
                                   "and a typical clear-winter-day temperature range. "
                                   "The model works for any location.")
    r = REGIONS[region_key]
    days = st.slider("Days simulated", 1, 7, 5)
    t_min = st.slider("Coldest night (°C)", -40.0, 5.0, r["t_min"], 1.0, key=f"tmin_{region_key}")
    t_max = st.slider("Warmest afternoon (°C)", -20.0, 20.0, r["t_max"], 1.0, key=f"tmax_{region_key}")

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
d = run_design(region_key, days, t_min, t_max, insulated, glazing_key, wwr, tuple(facades),
               orientation, L, W, H, ach, mass_kind, mass_vol, mass_area, setpoint, vent_high)
b = run_baseline(region_key, days, t_min, t_max, setpoint)

m = d["metrics"]
solar = d["energy"]["solar_windows"]              # useful solar into the room (through glass)
incident = solar + d["energy"]["solar_opaque"]    # total sun absorbed on the whole shell
aux, base_aux = d["aux"], b["aux"]
saving = (1 - aux / base_aux) * 100 if base_aux else 0.0

# ---- header ------------------------------------------------------------ #
st.title("Thermal-Shelter — passive design studio")
st.caption(f"Design an area-specific shelter for {region_key} and see how warm it stays — "
           "and how little heating it needs — against a baseline hut.  "
           "SIH 2026 · PS 26051 (DRDO, Software).")

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
elif base_aux:
    st.warning(f"This design needs **{-saving:.0f}% more** heating than the baseline "
               f"({aux:.1f} vs {base_aux:.1f} kWh/day) — try more insulation, south glazing, or mass.")

# ---- auto-optimiser ---------------------------------------------------- #
with st.expander("Auto-optimise — let the tool search for the best passive design", expanded=False):
    st.caption(f"Holds your site ({region_key}), size ({L:.0f}×{W:.0f}×{H:.1f} m) and air-leakage "
               f"fixed, then simulates {N_CANDIDATES} combinations of glazing, window area, window "
               f"facades and thermal mass to find the one that needs the least heating "
               f"(insulated envelope assumed).")
    if st.button("Find the best design", type="primary"):
        with st.spinner(f"Simulating {N_CANDIDATES} candidate designs…"):
            ranked = optimize(region_key, days, t_min, t_max, orientation, L, W, H, ach, setpoint)
        best = ranked[0]
        best_saving = (1 - best["aux"] / base_aux) * 100 if base_aux else 0.0
        st.success(
            f"**Best design — {best['glazing']}, {best['wwr'] * 100:.0f}% windows on "
            f"{FACADE_LABEL[best['facades']]}, {best['mass_kind']} {best['mass_vol']:.1f} m³**  →  "
            f"**{best['aux']:.1f} kWh/day**, {best_saving:.0f}% less heating than the baseline hut.")
        delta = aux - best["aux"]
        if delta > 0.1:
            st.caption(f"That is **{delta:.1f} kWh/day less** than the design currently on screen "
                       f"({aux:.1f} kWh/day). Set these values in the sidebar to apply it.")
        else:
            st.caption("Your current design is already at or near the best in this search.")
        st.dataframe(
            [{"Glazing": r["glazing"],
              "Windows": f"{r['wwr'] * 100:.0f}% {FACADE_LABEL[r['facades']]}",
              "Thermal mass": f"{r['mass_kind']} {r['mass_vol']:.1f} m³",
              "Heating (kWh/day)": round(r["aux"], 1),
              "vs baseline": f"{(1 - r['aux'] / base_aux) * 100:.0f}% less" if base_aux else "—"}
             for r in ranked[:5]],
            hide_index=True, width="stretch")

# ---- tabs -------------------------------------------------------------- #
tab_t, tab_e, tab_f = st.tabs(["Temperature", "Energy balance", "Heat-flow over time"])

with tab_t:
    fig = go.Figure()
    fig.add_hrect(y0=COMFORT_LO, y1=COMFORT_HI, fillcolor=C_BAND, opacity=0.25,
                  line_width=0, annotation_text="comfort band", annotation_position="top left")
    fig.add_hline(y=0, line_color="#cccccc", line_width=1)
    fig.add_trace(go.Scatter(x=d["time_days"], y=d["T_out"], name="ambient air",
                             line=dict(color=C_AMB, dash="dash", width=1.5)))
    fig.add_trace(go.Scatter(x=b["time_days"], y=b["T_in"], name="baseline hut",
                             line=dict(color=C_BASE, width=2.2)))
    for k, v in d["storage"].items():
        fig.add_trace(go.Scatter(x=d["time_days"], y=v, name=k,
                                 line=dict(color=C_MASS, dash="dashdot", width=1.4), opacity=0.75))
    fig.add_trace(go.Scatter(x=d["time_days"], y=d["T_in"], name="your design",
                             line=dict(color=C_DESIGN, width=3)))
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

with st.expander("Shelter details"):
    st.text(d["summary"])
