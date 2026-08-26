# Thermal-Shelter — a shelter that stays warm on sunlight, not fuel.

**Smart India Hackathon 2026 | PS ID: 26051 | Category: Software | Theme: Miscellaneous | Team ID: To be allotted after selection | Team Name: HimTaap**

## Problem

Heating remote high-altitude posts in Ladakh and along the border means hauling diesel and kerosene up long, treacherous supply lines at high cost and risk. Problem Statement 26051 asks for a software tool that, from a site's climate, geometry and materials, predicts three things: indoor temperature over a full day–night cycle, solar thermal energy captured, and heat flow versus the ambient air over a chosen period. The aim is to design a passive shelter that holds thermal comfort with minimal active heating.

## Proposed Solution

Thermal-Shelter is a fast Python design tool for cold, high-altitude shelters. You give it the site's climate, the shelter's shape and its materials; it simulates a complete day-and-night cycle and returns exactly the three required outputs — indoor temperature over time, solar energy captured, and heat flow versus ambient. You then redesign it live — walls, glazing, orientation, thermal mass — and watch the heating the shelter needs fall toward zero against a fixed baseline hut. Because each design solves in under one second, you can search hundreds of options instead of hand-checking one.

## Technical Approach & Novelty

- **Transient RC engine:** the shelter is modelled as a lumped resistance–capacitance thermal network stepped forward in time, so it captures the post-sunset temperature crash that steady-state calculators miss.
- **The cold sky and the snow — what quick tools ignore:** an ASHRAE sol-air driving temperature plus Berdahl–Martin long-wave sky cooling. On a clear Leh night the air is −14 °C but the sky behaves like about −45 °C; omit this and you badly over-promise warmth.
- **Solar on every face:** pvlib computes irradiance on each wall, roof and window, including ground-reflected gain off snow at albedo 0.70.
- **Thermal mass as a heat battery:** a water wall soaks up daytime sun and releases it after dark, carrying the room through the night.
- **Sub-second runtime enables optimisation** across material, size, orientation and glazing; ANSYS is then used only to validate the winning design, not to run the design loop.

## Key Results

- **82–86% less heating** than a baseline hut across four sites — Leh, Drass, Siachen, Tawang — evaluated over 5 clear winter days while holding a 20 °C setpoint.
- **Leh: 84% less heating — 27.6 vs 170.5 kWh/day.**
- Comfort is scored as the fraction of time held in the 18–24 °C band, and each full multi-day design runs in under 1 second.

## Impact

The tool serves armed forces and border posts, high-altitude communities, and disaster-relief deployments. Cutting heating demand by roughly 80% or more slashes the diesel and kerosene convoy burden, lowers emissions in a fragile Himalayan ecosystem, and improves energy resilience where supply lines are thin — while shortening shelter design from months of manual analysis to minutes.

## Tech stack

Python 3.12, NumPy/SciPy/pandas, pvlib, Streamlit + Plotly, matplotlib; ANSYS for validation.
