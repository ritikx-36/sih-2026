# Thermal-Shelter — SIH 2026 Idea PPT content pack

Copy-paste text for the **official SIH 2026 Idea template** (6 slides, title included).
Placeholders in `‹ … ›` are yours to fill. Keep the template's headings, colours and
layout exactly; only the text and images below change.

**Fonts:** the official template uses **Calibri** for body and **Arial** for the section
titles, with the idea-title accent in blue `#0070C0`. Keep it that way — both fonts ship
with PowerPoint/Windows, so nothing reflows when you export to PDF. Don't add a third font.
Suggested sizes: section title 28 pt · idea title 32–36 pt · body bullets 18–20 pt ·
sub-points 14–16 pt. Points, not paragraphs. Export to **PDF** before uploading.

**Images already in this repo:**
- `docs/demo_curve.png` — indoor-temperature chart, baseline hut vs passive design (Slide 2)
- `docs/deck_flow.png` — methodology pipeline (Slide 3)
- `docs/dashboard.png` — the live design studio's default view: KPIs + "84% less heating"
  banner + temperature chart (Slide 3, "working prototype")
- `docs/seasonal.png` — the all-year proof on real measured weather: month-by-month heating
  bars + comfort line + the fuel/₹/CO₂ saved per shelter per year (Slide 5)
- `docs/deck_regions.png` — % less heating by region (Slide 5, optional second image)
- `docs/validation.png` — engine verification against analytic limits: transient vs an independent
  ODE solver, settled load vs UA·ΔT hand-calc, and grid convergence (Slide 4)

---

## Slide 1 — TITLE PAGE

    SMART INDIA HACKATHON 2026

    Problem Statement ID    : 26051
    Problem Statement Title : Software-Based Model Development for Design of
                              Area-Specific Shelter for Thermal Comfort Maintenance
    Theme                   : ‹ as listed against PS 26051 on the SIH portal ›
    PS Category             : Software
    Team ID                 : ‹ your Team ID ›
    Team Name               : ‹ your team name, exactly as registered on the portal ›

---

## Slide 2 — IDEA TITLE + Proposed Solution

**Idea title (the blue accent line):**
> **Thermal-Shelter — a shelter that stays warm on sunlight, not fuel.**

**Proposed solution — what it is:**
- A design tool for cold, high-altitude shelters (Ladakh, and posts like it) that hold a
  comfortable temperature on sunlight and smart materials — with little or no active heating.
- You give it three things: the site's climate, the shelter's shape, and its materials.
  It simulates a full day-and-night cycle and answers exactly what the problem asks:
  how warm it stays inside hour by hour, how much solar heat it captures, and where heat
  is won and lost against the outside air.
- Then you redesign it live — walls, glazing, orientation, thermal mass — and watch the
  heating it needs fall toward zero.

**How it addresses the problem — it outputs all three required results:**
- Indoor temperature over the full day–night cycle
- Solar thermal energy captured through the day
- Heat-flow vs ambient over the chosen period

**What makes it different:**
- **It models the night, not just the average.** A static tool misses the post-sunset crash
  that actually decides comfort. Ours steps through time and catches it.
- **It accounts for the cold sky.** On a clear Leh night the air is −14 °C but the sky
  behaves like −45 °C. Ignore that and you badly over-promise warmth; we model it.
- **It stores the sun.** Stone, water walls and PCM act as a heat "battery" — soaking up
  daytime sun and releasing it after dark.
- **It's area-specific.** One engine, any cold site — Leh, Drass, Siachen, Tawang.
- **It's fast (< 1 second per design),** so you optimise across hundreds of options instead
  of guessing one. ANSYS then validates the winner.

*Image:* `docs/demo_curve.png` — "Simulated Leh winter: the passive design climbs into the
comfort band on sunlight alone, while the baseline hut tracks the freezing outdoor air."

---

## Slide 3 — TECHNICAL APPROACH

**Technologies used:**
- Python 3.12 — NumPy · SciPy · pandas
- pvlib — solar position & irradiance (clear-sky *or* real measured), including snow albedo
- PVGIS / EPW — real measured weather (Typical Meteorological Year) fetched live for any site
- Streamlit + Plotly — the live design dashboard (working prototype)
- matplotlib — figures & reporting
- ANSYS — CFD / thermal cross-validation (later phase)

**Methodology (see the pipeline diagram):**
- Model the shelter as a lumped **resistance–capacitance (RC) thermal network**, stepped
  forward in time.
- Drive it with a **sol-air outdoor temperature** plus **long-wave night-sky cooling**.
- Compute **solar irradiance on every wall, roof and window** with pvlib.
- Run on **real measured weather** — a PVGIS Typical Meteorological Year (or EPW) for the
  site — and roll it up **month-by-month across the year**, not just one design-day.
- Score each design for **comfort** (% of time in 18–24 °C) and **energy** (kWh/day to hold
  20 °C).
- **Compare and rank** designs by material, size, orientation and glazing.

*Images:*
- `docs/deck_flow.png` — the Climate → Solar → RC engine → Comfort+Energy → Compare/Optimise
  pipeline.
- `docs/dashboard.png` — the working prototype: the live design studio holding a Leh shelter
  at "84% less heating," with the indoor-temperature curve. Caption it "Working prototype —
  the live design tool (Streamlit)."

---

## Slide 4 — FEASIBILITY AND VIABILITY

**Why it's feasible:**
- Built on standard, peer-reviewed physics — ASHRAE sol-air & RC networks, Berdahl–Martin
  sky emissivity. It's defensible, not a black box.
- Uses the mature, widely trusted **pvlib** solar model.
- Pure software — runs on any laptop, with no field hardware to build.
- **Numerically verified against closed-form limits** — settled load = a hand-calculated UA·ΔT and
  the first law closes (both exact to rounding); the full transient matches an *independent* SciPy
  solver to **0.006 °C**; the result is grid-converged (60 s step within 0.01% of the dt→0 limit).
  Reproducible in one command: `python scripts/validate.py`. It's defensible, not a black box.

**Viability:**
- Cheap, fast and reusable across regions: screen hundreds of designs in software, then
  validate just the winner in CFD — where each case would otherwise take hours.

**Potential challenges → how we overcome them:**
- Sparse climate data for remote posts → pull a free **PVGIS Typical Meteorological Year**
  (or an EPW) for any coordinates, with built-in region presets and a typical-day generator
  as fallback where nothing else exists.
- A lumped RC model simplifies real 3-D heat flow → the lumped solver is already **verified**
  numerically correct; ANSYS CFD then **validates** the shortlisted design's spatial detail.
- Material properties vary by source → a sourced, editable material-property database.

*Image:* `docs/validation.png` — "Verification against analytic limits: the transient matches an
independent ODE solver to 0.006 °C, settled heating loads sit on the UA·ΔT hand-calculation, and the
engine is grid-converged."

---

## Slide 5 — IMPACT AND BENEFITS

**Headline impact (on a real measured Leh year — PVGIS TMY):**
> **~80% less heating, every month of the year** — 7,960 vs 39,814 kWh/year to hold 20 °C.
> That is **≈3,900 litres of kerosene, ₹3.5 lakh and ~10 tonnes of CO₂ saved — per shelter,
> per year.** *(On a clear design-day the same shelter shows 82–86% less heating across Leh,
> Drass, Siachen and Tawang — Leh 84%.)*

**Who it helps:** armed forces & border posts · high-altitude communities · disaster relief.

**Benefits:**
- **Economic** — ~3,900 fewer litres of kerosene and **₹3.5 lakh saved per shelter per year**,
  cutting the convoy burden on treacherous supply lines; and designs done in minutes, not months.
- **Environmental** — **~10 tonnes less CO₂ per shelter per year**; less combustion in a
  fragile Himalayan ecosystem.
- **Operational & social** — energy resilience where supply lines are thin; warmer, safer
  shelters; fewer cold-related injuries.

*Image:* `docs/seasonal.png` — "Comfortable all year on real measured weather: month-by-month
heating (design vs baseline) and % time comfortable, with the fuel/₹/CO₂ saved per shelter per
year." *(Optional second image: `docs/deck_regions.png` — % less heating by region.)*

---

## Slide 6 — RESEARCH AND REFERENCES

- **pvlib-python** (Sandia National Laboratories) — solar position & clear-sky irradiance —
  https://pvlib-python.readthedocs.io
- **PVGIS** (European Commission Joint Research Centre) — Typical Meteorological Year, free,
  no API key — https://re.jrc.ec.europa.eu/pvg_tools/en/
- **Berdahl, P. & Martin, M. (1984), "Emissivity of clear skies"** — long-wave radiative
  night-sky cooling
- **ASHRAE Handbook of Fundamentals** — sol-air temperature, RC thermal networks, U-values
  & SHGC
- **Balcomb, J. D. / U.S. Department of Energy** — passive-solar design: Trombe & water
  walls, thermal mass
- **DRDO–DIHAR** (Defence Institute of High-Altitude Research), Leh — high-altitude habitat
  & thermal-comfort context
- **Project repository** — https://github.com/ritikx-36/sih-2026

---

*Tip: delete the template's "Important Instructions" slide before exporting, keep it to 6
slides, and save as PDF — the portal only accepts PDF.*
