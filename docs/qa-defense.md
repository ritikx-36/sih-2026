# Thermal-Shelter — Finals Q&A Defense Pack

Everything a judge could throw at PS 26051, with answers grounded in **our actual engine**.
Read the "How to handle the room" box first — then the categories. The **Cheat Sheet** at the
end is the one page to memorise.

---

## How to handle the room

- **Lead with the robust number, not the fragile one.** The headline is **"82–86% less heating
  than a baseline hut."** That is a *relative* aux-heating reduction and it is rock-solid. Do
  **not** open with "it reaches +18 °C" — that absolute figure depends on how many clear days,
  and a sharp judge will push on it. Comfort-temperature is the *story*; the % saving is the *proof*.
- **Have both proof-numbers ready — a clear day AND a real year.** The 82–86% is a *clear
  design-day*. We also run a **real measured year (PVGIS TMY) for Leh**, and it still shows
  **~80% less heating across all twelve months** — which translates to **≈3,900 L of kerosene,
  ₹3.5 lakh and ~10 t CO₂ saved per shelter, per year.** If a judge suspects the clear day is
  cherry-picked, that's your answer: *"we checked a whole real year, clouds and all — same story."*
- **Own the simplifications before they're attacked.** "It's a lumped RC model — that's a
  deliberate choice, and here's why" beats being cornered into admitting it.
- **Never bluff.** If you don't know: *"We haven't measured that yet — it's in the ANSYS
  validation phase. My expectation is X because Y."* That answer scores; a wrong bluff loses the room.
- **Bring every answer back to the PS.** The PS asks for three outputs (indoor temp over time,
  solar energy captured, heat-flow vs ambient) and mentions ANSYS. Show you understood both.
- **One breath, then the point.** 20–40 seconds per answer. Offer to go deeper if they want.

---

## A. The ANSYS question (this WILL come — the PS names ANSYS repeatedly)

**Q1. The problem statement talks about ANSYS. Why did you build your own Python tool instead of just using ANSYS?**
> Because the **category is Software** and the *task* is **design**, not a single analysis.
> Designing a shelter means comparing hundreds of options — wall build-ups, glazing, orientation,
> thermal mass — across a full day–night cycle. In ANSYS each transient case can take **minutes to
> hours** to set up and solve; you can't explore a design space that way. Our tool runs one full
> multi-day simulation in **under a second**, so we can *search* for the best design, not hand-check
> one. **The right division of labour is: our tool designs and screens; ANSYS validates the winner.**
> That's standard engineering practice — fast reduced-order model up front, high-fidelity solver at the end.

**Q2. So is ANSYS not needed at all?**
> It absolutely is — for **validation**. Our model is a lumped network; it gives one temperature per
> zone. ANSYS CFD gives the **spatial** picture our model can't: air stratification, cold drafts near
> the door, corner condensation, exactly where the water wall should sit. **Phase 6 of our roadmap is
> ANSYS cross-validation of the shortlisted design.** We're not avoiding ANSYS — we're using it where
> it's strong instead of where it's slow.

**Q3. How will you actually validate against ANSYS — what's the plan?**
> Take one converged design, rebuild the same geometry, materials and boundary conditions (sol-air
> temperature, night-sky radiation, solar flux per face) in ANSYS Fluent/Transient Thermal, and
> compare the daily indoor-temperature curve and total heat loss. If our lumped model tracks CFD
> within a few °C on the mean and matches the loss breakdown, the fast tool is trustworthy for
> screening. Any systematic gap becomes a calibration factor.

**Q4. Why not EnergyPlus or TRNSYS — mature tools already exist?**
> Those are excellent general-purpose engines, but they're **heavy, general, and hard to drive** —
> steep learning curve, hundreds of inputs, not interactive. We built a **focused** tool for one
> job: cold, high-altitude, passive design for Indian border regions. It foregrounds the physics that
> actually decides comfort *there* — the cold night sky and snow albedo — surfaces exactly the three
> PS outputs, and runs live so a non-expert can design in minutes. We're not out-engineering
> EnergyPlus; we're out-*fitting* it to this problem. And nothing stops us cross-checking against
> EnergyPlus too.

---

## B. Physics & correctness (the technical grilling)

**Q5. What is the core model — in one sentence?**
> A **lumped resistance–capacitance (RC) thermal network**: walls, roof, floor and windows are
> thermal *resistances*; the room air and thermal mass are *capacitances* (heat stores). We step it
> forward in time and solve the energy balance at each node — the same family of model as the
> ISO 13790 building method, just tailored to our case.

**Q6. What drives the model from outside?**
> Three things per time-step: (1) the **sol-air temperature** — outdoor air plus absorbed solar minus
> long-wave loss, rolled into one equivalent driving temperature for the opaque envelope; (2)
> **solar irradiance on every face** from pvlib, including ground reflection off snow; and (3)
> **long-wave radiation to the cold sky**, which pulls heat out especially at night.

**Q7. What exactly is sol-air temperature and why use it?**
> It's a textbook (ASHRAE) trick: instead of tracking convection, absorbed sunlight and radiative
> loss on a wall's outer surface separately, you combine them into a single *effective* outdoor
> temperature. A sunlit south wall can have a sol-air temperature well above the air; a roof under a
> clear night sky can be *below* it. It lets one conduction equation carry all three effects.

**Q8. You keep mentioning the "cold sky." Explain.**
> A clear, dry, high-altitude sky is nearly transparent to infrared, so surfaces radiate heat to deep
> space. On a clear Leh night the **air is about −14 °C but the sky behaves like ≈ −45 °C**. We model
> this with the **Berdahl–Martin** sky-emissivity correlation. It matters enormously: a tool that
> ignores it will *over-promise* warmth, because it misses the biggest night-time loss. Windows lose
> to this cold sky too, not just by conduction — we fold that into an effective window driving temperature.

**Q9. How does solar gain get into the building?**
> pvlib gives clear-sky irradiance and sun position; we project it onto each wall, roof and window
> (plane-of-array), adding the **snow-reflected** component with albedo 0.70. Through windows,
> transmitted gain = irradiance × glazing SHGC × area. That transmitted heat is split — about **40 %
> to the room air, 60 % into the thermal mass** — because sunlight landing on a heavy floor/water wall
> charges it rather than instantly warming the air.

**Q10. How does thermal mass work in the model, and why does it help?**
> Thermal mass (water wall, concrete, PCM) is a large heat *capacitor*. It soaks up daytime solar and
> releases it after sunset, flattening the day–night swing and carrying the room through the cold
> night. A **1000 L water wall** stores a lot: water holds ~4.2 MJ per m³ per °C. In the model it's a
> node with its own temperature, exchanging heat with the room air. It's the single biggest reason the
> passive design survives the night.

**Q11. How do you compute "% time comfortable" and "heating needed"?**
> Comfort = **fraction of time indoor temperature sits in the 18–24 °C band**, measured on a
> representative day. Heating = we run a second simulation that **pins the room to a 20 °C setpoint**;
> whenever free-float drops below 20 °C we add exactly enough heat to hold it, integrate that over the
> day → **kWh/day of auxiliary heating**. Comparing that number for our design vs the baseline hut
> gives the headline saving.

**Q12. Why do you run TWO simulations (free-float and heated)?**
> They answer two different questions. **Free-float** (no heater) shows *how warm the design gets on
> its own* — that's the comfort story and the temperature curve. **Heated-to-setpoint** shows *how
> much fuel you'd still need* to guarantee 20 °C — that's the energy story and the % saving. Both are
> in the PS: temperature over time, and energy.

**Q13. What's the time-stepping scheme? Is it stable?**
> Explicit Euler at a **30-minute step**. With our capacitances and resistances that's comfortably
> inside the stability limit (the thermal time constants are hours, not minutes). We've checked that
> halving the step doesn't change the daily results — so we're resolved, not riding the stability edge.

**Q14. What about the ventilation logic — why is it there?**
> Real passive-solar buildings **vent excess heat** on sunny afternoons or they'd cook. When indoor
> temperature exceeds **24 °C** we raise the air-change rate to dump heat. Without this the model would
> keep warming on repeated clear days and give unrealistically rosy numbers — so it's both physically
> honest *and* a genuine design feature (free summer cooling).

---

## C. Validation — "how do you know it's right?"

**Q15. Have you validated this against anything? Isn't it just numbers?**
> Three layers. (1) **Physics provenance** — every sub-model is a published, peer-reviewed correlation:
> ASHRAE sol-air, Berdahl–Martin sky, pvlib (Sandia National Labs) solar. We didn't invent the physics.
> (2) **Sanity/behavioural tests** — the model does what physics demands: turn off insulation and the
> gap to the baseline collapses; remove the night-sky term and nights get warmer; shrink the windows
> and solar gain drops. It responds correctly to every lever. (3) **ANSYS cross-validation** is the
> planned high-fidelity check on the winning design. For a shortlisting-stage prototype, provenance +
> correct behaviour is the honest, defensible position.

**Q16. Your baseline needs ~170 kWh/day and your design ~28 kWh/day. Those absolute numbers — are they real?**
> The **relative** reduction is the robust result; absolute kWh depends on assumptions (infiltration,
> the cold-start charging of the thermal mass over the 5-day window). Holding 20 °C inside when it's
> −14 °C and colder outside at 3500 m, in a leaky uninsulated stone hut, genuinely is that punishing —
> that's *why* the problem exists. We quote the **% saving** precisely because it cancels the shared
> assumptions and isolates the effect of the design. If a judge wants, we can show the number move as
> we tighten each assumption.

**Q17. Isn't 84% suspiciously high?**
> It's large because the **baseline is deliberately a worst-case** cold-region hut — uninsulated
> stone, single glazing, very leaky (2.0 air changes/hour). Against a *modern* insulated shell the
> passive extras would add a smaller (still real) increment. We compare to the leaky hut because
> that's what's actually deployed in these regions today — it's the honest "before."

---

## D. Assumptions & limitations (be honest — they'll probe)

**Q18. Biggest weakness of your model?**
> It's **lumped** — one temperature per zone, no spatial detail. It won't tell you about drafts,
> stratification, or a cold corner. That's a deliberate trade for speed and for answering the
> whole-building energy/comfort question the PS asks — and it's exactly the gap ANSYS fills in
> validation.

**Q19. Your demo shows a 5-day transient that's still climbing. Isn't that cherry-picked?**
> The opposite — we deliberately show a **transient from a cold start**, not a hand-picked "converged"
> day, *because that's honest* and it's literally what the PS asks: "temperature over a defined time
> period." You can watch the thermal mass charge day by day into the comfort band. If we ran endless
> identical clear days it would converge even warmer — we chose *not* to quote that optimistic steady
> state. The **aux-heating saving is our headline precisely because it's robust**: pinning the setpoint
> makes it converge fast and it doesn't depend on how many days you show.

**Q20. Clear-sky only? Real weather has clouds and storms.**
> We run **both**. The clear-sky day is the *design* condition — the coldest clear nights are when
> passive heating is hardest, so it's a conservative stress test for comfort. But we also drive the
> model with a **real measured year — a PVGIS Typical Meteorological Year** (clouds, real irradiance,
> the works) for the exact site, and roll it up **month by month** in the Seasonal view. That's how we
> know the saving holds outside the ideal day: **~80% less heating across a real Leh year**, not just
> on a sunny afternoon. A user can also load any **EPW** weather file. Real weather was a data swap, not
> a model change — the engine already accepted an irradiance time-series; now we feed it a measured one.

**Q21. You assume steady, known material properties. They vary.**
> Yes. We use sourced ASHRAE/handbook values and expose them in an **editable material database**, so
> a user can enter measured properties for their actual build. Sensitivity to the big ones (insulation
> conductivity, infiltration) is easy to run because the model is so fast.

**Q22. Single-zone — what about multi-room shelters?**
> Today it's single-zone, which suits the small shelters in the PS. The RC framework extends naturally
> to **multiple coupled zones** (each a node, walls between them as resistances) — it's on the roadmap,
> not a rewrite.

**Q23. No humidity / condensation / occupants?**
> Right now it's a **sensible-heat** model. Occupant and equipment heat gains are a simple additive
> term we can switch on. Moisture and condensation risk are a known extension — and another thing
> ANSYS validation will flag on the winning design.

---

## E. Novelty & differentiation

**Q24. What's genuinely new here?**
> Not the individual physics — the **integration and focus**. A single, fast, interactive tool that
> (a) is purpose-built for **cold high-altitude passive design**, (b) makes the **cold-sky night loss
> and snow albedo** first-class (most quick tools ignore them), (c) is **area-specific** with presets
> for Leh, Drass, Siachen, Tawang, (d) runs **sub-second** so you optimise instead of guess, and
> (e) outputs **exactly the three things the PS asks for**. It turns "analyse one design in ANSYS" into
> "design and rank hundreds, then validate one."

**Q25. Couldn't anyone build this in a weekend?**
> The *skeleton*, maybe. Getting the **night-sky radiation, the solar-to-mass split, and the
> ventilation control right** is where naïve versions go wrong — we know, because our first cut routed
> window solar to the wrong node and predicted absurdly cold rooms. The value is in the correct,
> debugged, region-tuned physics and the interactive design loop around it.

---

## F. Inputs & data

**Q26. Where does the climate data come from?**
> Four routes, best-to-simplest: (1) a **real measured year** — a free **PVGIS Typical
> Meteorological Year** fetched live for any latitude/longitude (no API key), or a **EPW** weather
> file; (2) built-in **region presets** (lat/long/altitude/albedo + typical winter min–max) for the
> border sites; (3) a **typical-day generator** from just a min and max temperature — for a forward
> post with no station; (4) **user CSV** of a measured series. The engine is location-agnostic — feed
> it any site.

**Q27. Solar data — measured or modelled?**
> Either. If you drive it from a **PVGIS TMY or EPW**, the irradiance is **measured/satellite-derived**
> and carried straight through. If you only have coordinates, **pvlib** (Sandia) models sun position and
> clear-sky irradiance from latitude, longitude, altitude and day of year — no external feed needed,
> which matters for remote posts with no weather station. Same engine; the solar input can be modelled or real.

**Q28. How do you handle a site with almost no data — a forward post?**
> That's the common case, and we designed for it: give the tool a **latitude, altitude and a typical
> temperature range** and it generates a defensible design day. When you can reach a network, it will
> also pull a free **PVGIS Typical Meteorological Year** for those exact coordinates — no station on
> site needed. As better data arrives, drop in a CSV or EPW.

---

## G. Feasibility, deployment, scale

**Q29. What does it run on?**
> Pure Python — **any laptop**, no GPU, no cloud, no field hardware. That's a deliberate deployment
> choice for a defence context where connectivity and hardware can't be assumed.

**Q30. Who uses it, and do they need to be an engineer?**
> A design engineer or a planner. The dashboard is sliders and charts — you pick a region, adjust
> walls/glazing/mass, and read comfort and heating live. The physics is under the hood; the interface
> is decisions.

**Q31. How does it scale to "area-specific" across many regions?**
> The engine is **fully location-agnostic** — region is just a set of inputs (coordinates, albedo,
> climate). Adding a region is adding a preset, not changing code. One engine, any cold site.

**Q32. Production readiness / timeline?**
> The prototype already runs, produces all three PS outputs, ingests **real measured weather (PVGIS
> TMY / EPW)** and reports the annual fuel/₹/CO₂ impact. Post-shortlisting: ANSYS validation, a richer
> material database, and multi-zone shelters. Months, not years.

---

## H. Impact & DRDO relevance

**Q33. Why does DRDO care — what's the real-world payoff?**
> Fuel logistics. Heating remote high-altitude posts means **hauling diesel and kerosene** up
> treacherous supply lines at huge cost and risk. Cutting heating demand by **80%+** cuts that convoy
> burden, cuts emissions in a fragile Himalayan ecosystem, and improves **energy resilience** where
> supply lines are thin — plus warmer, safer shelters and fewer cold-injury casualties.

**Q34. Quantify the benefit.**
> On a clear design-day, from ~170 to ~28 kWh/day to hold 20 °C — **~140 kWh/day saved** per shelter.
> Over a **real measured Leh year** it's **7,960 vs 39,814 kWh — ~32,000 kWh saved per shelter, per
> year.** In the language the end user budgets in, that's **≈3,900 litres of kerosene not burned, ₹3.5
> lakh saved, and ~10 tonnes of CO₂ avoided — per shelter, every year** (kerosene 10.3 kWh/L, 80% heater
> efficiency, ₹90/L; all editable). Multiply across a deployment. Every litre not carried is a convoy that
> doesn't run — and the design work itself drops from months of manual analysis to minutes.

**Q35. Beyond defence?**
> High-altitude civilian communities, disaster-relief shelters, and cold-climate rural housing — the
> same physics, the same tool.

---

## I. Software / demo / engineering

**Q36. Show me it works.** *(Have the Streamlit app open before you walk in.)*
> Move a slider — insulation off, or windows smaller — and the indoor curve and the heating number
> update **live**. That responsiveness *is* the pitch: this is a design instrument, not a report.

**Q37. What's the stack?**
> Python 3.12; NumPy/SciPy/pandas for the engine; **pvlib** for solar and **PVGIS/EPW** for real
> measured weather; **Streamlit + Plotly** for the live dashboard; matplotlib for figures. ANSYS for
> later validation.

**Q38. What if the demo crashes on stage?**
> We have the pre-rendered figures in the deck (temperature curve, dashboard panel, regional savings)
> generated by the *same* engine — identical numbers — so the story stands without a live server.

**Q39. Is the code tested / maintainable?**
> It's a clean package (`thermalshelter/`: materials, climate, solar, geometry, engine, comfort) with
> a scripted demo that reproduces the headline number, so any change is instantly checkable against a
> known result.

---

## J. Team & project (softer SIH questions)

**Q40. How did you split the work?** — *(answer honestly for your team: physics/engine, dashboard/UI, validation/deck, etc.)*

**Q41. What was the hardest part?**
> Getting the night-time physics right. Our first version predicted rooms far too cold — we'd routed
> transmitted window solar into the exterior-coupled mass, which leaked it straight back outside.
> Fixing the solar-to-air-vs-storage split, and adding the cold-sky loss and venting, is what made the
> model behave like a real building.

**Q42. What would you do with more time?**
> ANSYS validation first, then multi-zone shelters, humidity and condensation risk, and occupant/
> equipment heat gains. Real measured weather (PVGIS TMY / EPW), an orientation-searching optimiser,
> and the fuel/₹/CO₂ cost layer are **already in** — so more time goes on fidelity and validation, not
> catching up to the claims.

**Q43. What did you learn?**
> That the modelling *judgment calls* — what to lump, what to resolve, which loss dominates — matter
> more than raw solver power, and that a fast honest model you can interrogate beats a slow black box.

---

## K. Curveballs & traps

**Q44. "This is just an Excel heat-loss calculation with a UI."**
> A steady-state heat-loss calc gives one number for a design point. Ours is **transient** — it steps
> through the day–night cycle, so it captures the post-sunset crash and the thermal-mass charge/discharge
> that *actually decide* comfort. That time dimension is the whole point, and it's what the PS asks for.

**Q45. "Your model and ANSYS will disagree. Then what?"**
> Expected — they answer different questions. If they disagree on the daily mean or total loss beyond a
> few °C / a few percent, that's a **calibration signal**: we adjust a lumped parameter (effective
> infiltration, an interior film coefficient) so the fast model matches the high-fidelity one. That's
> how reduced-order models are tuned everywhere in engineering.

**Q46. "Why 18–24 °C? Why 20 °C setpoint?"**
> 18–24 °C is a standard thermal-comfort band (ASHRAE); 20 °C is a reasonable heated setpoint. Both are
> **user-adjustable** — a judge can set their own and the numbers update.

**Q47. "What if there's no sun for days?"**
> Then passive gain can't carry it and you fall back on the auxiliary heater — but you're *still* far
> better off, because the insulation and low infiltration mean that backup heat goes much further. The
> saving comes from the whole envelope, not solar alone.

**Q48. "Prove the night-sky term matters — don't just assert it."**
> Turn it off in the model and clear-night indoor temperatures rise by several degrees — the design
> looks better than reality. That sensitivity is exactly why we include it and why omitting it (as
> quick tools do) is a real error for this climate.

**Q49. "Isn't explicit Euler crude? Why not implicit / a real ODE solver?"**
> For these time constants (hours) at a 30-minute step, explicit Euler is stable and accurate — we
> confirmed by step-halving. An implicit solver buys nothing here and costs simplicity and speed. If we
> ever add very light, fast-responding nodes we'd switch; today it's the right tool.

**Q50. "What's your unfair advantage over the next team with the same PS?"**
> We resisted the **ANSYS trap** — we understood the category is *Software* and the deliverable is a
> *design tool*, so we built something fast, interactive and honest, with the region-specific physics
> that this cold-sky, snow-albedo problem actually needs, and a clear validation path into ANSYS. Most
> teams will either drown in ANSYS setup or hand-wave the night physics. We did neither.

---

## Cheat Sheet — memorise this one page

**One-liner:** *A fast, interactive design tool that predicts how warm a high-altitude shelter stays,
how much sun it captures, and how much heating it needs — so you can design one that runs on sunlight,
not fuel. ANSYS validates the winner.*

**Killer number:** **82–86% less heating** than a baseline hut (Leh 84% — ~28 vs ~170 kWh/day),
across Leh / Drass / Siachen / Tawang. On a **real measured Leh year**, still **~80% less** — ≈**3,900 L
kerosene, ₹3.5 lakh and ~10 t CO₂ saved per shelter per year.** *(Lead with the % — it's robust.
Temperature is the story, % is the proof; the fuel/₹/CO₂ is the payoff DRDO budgets in.)*

**Three PS outputs we deliver:** indoor temperature over time · solar energy captured · heat-flow vs ambient.

**Model:** lumped RC thermal network, transient, 30-min steps → indoor temp; second run pins 20 °C → heating kWh/day.

**Three physics we get right that others miss:**
1. **Cold night sky** (air −14 °C, sky ≈ −45 °C) — Berdahl–Martin.
2. **Snow albedo 0.70** — extra reflected solar.
3. **Thermal mass** (1000 L water wall) charging by day, releasing by night.

**Why not just ANSYS:** category is *Software*, task is *design*. Ours screens hundreds of designs in
**<1 s each**; ANSYS validates one in minutes–hours. Fast model designs, high-fidelity solver validates.

**Provenance (say the names):** ASHRAE (sol-air, U/SHGC) · Berdahl–Martin 1984 (sky) · pvlib/Sandia
(solar) · Balcomb/DOE (passive solar) · DRDO-DIHAR (context).

**Honest limits (own them):** single-zone, clear-sky, lumped (no spatial detail) — all deliberate for
speed, all addressed by the ANSYS validation phase.

**If you don't know:** *"That's in our validation phase — my expectation is X because Y."* Never bluff.
