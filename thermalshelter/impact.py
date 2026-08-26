"""
Real-world impact of the heating-energy savings.

The engine reports auxiliary heating in kWh. In this problem's domain — remote,
high-altitude posts with no grid — that heat is produced by *burning kerosene*
(or diesel/LPG) in space heaters that must be flown or portered in at great cost.
This module converts the physical kWh into the terms a planner actually budgets
in: litres of fuel, rupees, and CO₂. It turns "84 % less heating" into "≈ N fewer
litres of kerosene and X kg less CO₂ per winter" — the language the end user speaks.

Every factor is explicit, conservative, and easy to defend in a review; nothing
here feeds back into the physics — it is a post-processing translation only.
"""
from __future__ import annotations

import math
from dataclasses import dataclass

# --- Kerosene space-heating factors ----------------------------------------
KEROSENE_KWH_PER_L = 10.3   # net calorific value of kerosene [kWh per litre]
HEATER_EFFICIENCY = 0.80    # useful heat delivered ÷ fuel energy (portable heater)
CO2_KG_PER_L = 2.5          # CO₂ released per litre of kerosene burned [kg/L]
INR_PER_L = 90.0            # representative retail price [₹ per litre]

# A Ladakh heating season runs roughly October–April; use ~180 core-winter days
# to scale a per-day saving into a per-season figure.
WINTER_DAYS = 180


@dataclass(frozen=True)
class FuelImpact:
    """Fuel, cost and carbon equivalent of an amount of delivered heat."""

    kwh: float       # delivered (useful) heat [kWh]
    litres: float    # kerosene burned to deliver it [L]
    inr: float       # cost of that fuel [₹]
    co2_kg: float    # CO₂ emitted [kg]


def fuel_impact(kwh: float, inr_per_l: float = INR_PER_L) -> FuelImpact:
    """
    Kerosene, cost and CO₂ needed to deliver ``kwh`` of useful heat.

    Divides by the heater efficiency because only ~80 % of the fuel's energy
    reaches the room; the rest goes up the flue. ``kwh`` may be zero or negative
    (the result scales accordingly, e.g. a negative saving). Non-finite input
    returns a zeroed result rather than propagating NaN into the UI.
    """
    if not math.isfinite(kwh):
        return FuelImpact(0.0, 0.0, 0.0, 0.0)
    litres = kwh / (KEROSENE_KWH_PER_L * HEATER_EFFICIENCY)
    return FuelImpact(
        kwh=kwh,
        litres=litres,
        inr=litres * inr_per_l,
        co2_kg=litres * CO2_KG_PER_L,
    )
