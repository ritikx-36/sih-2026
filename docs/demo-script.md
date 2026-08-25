# 3-Minute Demo Script — Thermal-Shelter live dashboard

Internal hackathon walkthrough. Click-by-click, with a line to say at each beat.
Target: 3 minutes. Everything is live and re-runs in under a second, so you can
improvise — but this path hits all three problem-statement outputs plus the
optimiser, in the order that lands best.

---

## Before you start (30 sec setup, off the clock)

1. Launch the app in your terminal:
   ```bash
   ./.venv/bin/streamlit run app.py
   ```
   It opens at `http://localhost:8501`.
2. **Maximise the browser window** (the layout is wide — a narrow window stacks
   the KPIs into one column and looks worse).
3. Confirm the default view loaded: **Region = Leh, Ladakh**, and the green banner
   reads **"This design needs 84% less heating than the baseline hut."**
   If not, hit refresh — it resets to this state.
4. Have the sidebar **open** (the `»` / `«` toggle top-left controls it).

If Wi-Fi or the terminal is flaky on the day, the whole thing runs offline on
localhost — nothing here needs the internet.

---

## The 3 minutes

### 0:00 — Frame the problem (20 sec)
*Don't touch anything yet. Point at the temperature chart.*

> "This is a shelter in Leh — 3,500 m, and outside the air hits minus 14 at night.
> The problem statement asks for software that predicts, from climate and materials,
> how warm a shelter stays, how much solar it captures, and how heat flows — so you
> can design one that stays comfortable **without hauling diesel up the mountain.**"

### 0:20 — Read the temperature chart (35 sec)
*Point to each line in turn.*

> "Grey dashed is the outside air. **Red** is a normal uninsulated hut — it just
> tracks the freezing air; unlivable without burning fuel non-stop.
> **Blue is our passive design — and there's no heater running in this view.**
> Watch it climb: over five days it soaks up sunlight into a water wall —"

*Point to the orange dash-dot line (the thermal-mass store).*

> "— that's the heat battery charging by day and releasing at night, carrying the
> room up toward the comfort band on sunlight alone."

### 0:55 — The headline number (25 sec)
*Point to the KPI row, then the green banner.*

> "And when you do want to hold a real setpoint — 20 degrees — look at the bottom
> line: **84% less heating than the baseline hut. 27.6 versus 170.5 kilowatt-hours
> a day.** That's the diesel convoy you don't have to run."

### 1:20 — The other two required outputs (30 sec)
*Click the **Energy balance** tab.*

> "Output two — the energy balance. Green is solar coming in through the glazing;
> red bars are the losses — envelope, windows, air leakage, and long-wave cooling
> to the cold night sky, which most quick tools ignore."

*Click the **Heat-flow over time** tab.*

> "Output three — heat flow over time. Solar spikes every afternoon; and after
> sunset the thermal-mass line flips positive — the store discharging back into
> the room. That's the passive design working while everyone's asleep."

### 1:50 — Area-specific, any site (25 sec)
*Sidebar → Climate & region → change **Region** to **Siachen (base)**.*

> "It's area-specific — one engine, any cold site. Switch to Siachen: colder
> climate, different latitude and snow albedo, and every number and curve
> recomputes live, in under a second."

*Change **Region** back to **Leh, Ladakh**.*

### 2:15 — The optimiser (35 sec)
*Expand **"Auto-optimise — let the tool search for the best passive design"**,
then click **"Find the best design."***

> "And because each design solves in under a second, the tool can search for you.
> This tries 24 combinations of glazing, window area, facing and thermal mass —"

*Wait ~2 seconds for the result banner + table.*

> "— and finds an even better one: **86% less heating** — low-e glass, windows on
> three sides, water wall. That's the loop CFD can't do — you'd wait hours per case.
> Here you screen hundreds in software, then validate only the winner in ANSYS."

### 2:50 — Close (10 sec)

> "Standard, defensible physics — ASHRAE sol-air, Berdahl–Martin sky cooling,
> the pvlib solar model. Runs on any laptop. That's Thermal-Shelter."

---

## If a judge interrupts with a question
Answer briefly and return to the script — don't lose the thread. The full
prepared answers (the ANSYS question, "why not steady-state", validation,
assumptions) are in [`docs/qa-defense.md`](qa-defense.md). The three you'll most
likely get:

- **"Is 9°C mean / 6% comfort not weak?"** → "That's the *free-float* run with
  **zero heating**, from a cold start — it's honestly showing the transient climb,
  not a cherry-picked converged day. The robust headline is the heating reduction:
  84% less fuel to hold 20°C. Both are on screen."
- **"Why not just use ANSYS?"** → "ANSYS is hours per case — you can't design in it.
  We screen hundreds of options in seconds, then validate the winner in ANSYS.
  It's the design loop, not a replacement for CFD."
- **"Where's the night-sky / snow modelling?"** → Point to the Energy-balance tab.
  "The loss terms already include long-wave cooling to a −45°C sky and solar
  reflected off snow at 0.70 albedo — that's why we don't over-promise warmth."

## Recovery
- Anything looks wrong → **refresh the page**; it resets to the Leh default instantly.
- A slider stuck at a weird value → the numbers are always self-consistent, so just
  narrate what's on screen; there are no crash states (edge values tested).
- Running long → skip the region switch (beat 1:50) and go straight to the optimiser.
