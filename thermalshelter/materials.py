"""
Material thermal-property database for the Thermal-Shelter model.

Every construction layer and thermal-mass element is made of a material with three
bulk thermal properties that drive how it stores and conducts heat:

    k    thermal conductivity      [W/(m·K)]   -> how fast heat conducts through it
    rho  density                   [kg/m³]     -> mass per unit volume
    cp   specific heat capacity    [J/(kg·K)]  -> heat stored per kg per degree

From these we derive the two quantities the thermal engine actually uses:

    volumetric heat capacity   C_v = rho * cp         [J/(m³·K)]
        -> the "thermal mass": heat a cubic metre soaks up per degree of warming.
    thermal diffusivity        alpha = k / (rho * cp) [m²/s]
        -> how quickly a temperature change travels through the material.
           LOW alpha = slow: heat absorbed by day emerges slowly at night, which is
           exactly the behaviour that keeps a passive Ladakh shelter warm after dark.

Two optional surface-optical properties matter for the outer skin of the shelter:

    solar_absorptance  (0-1)   fraction of incident sunlight the surface absorbs
    emissivity         (0-1)   long-wave emission — drives night-sky radiative loss

Phase-change materials (PCM) additionally absorb a large chunk of *latent* heat as
they melt near a set temperature; those fields feed the engine's later
apparent-heat-capacity treatment.

All numbers below are typical handbook values used as sensible defaults. The whole
point of the tool (and the problem statement) is that the user can override any
property for their own measured materials — see `custom()`.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Optional


@dataclass(frozen=True)
class Material:
    """A single material and its thermal properties."""

    name: str
    category: str  # insulation | mass | structure | glazing | pcm | finish | air
    k: float       # thermal conductivity  [W/(m·K)]
    rho: float     # density               [kg/m³]
    cp: float      # specific heat         [J/(kg·K)]
    solar_absorptance: float = 0.6
    emissivity: float = 0.90
    # --- PCM only (None for ordinary materials) ---
    latent_heat: Optional[float] = None  # [J/kg]
    phase_temp: Optional[float] = None   # [°C] centre of the melt/freeze range
    phase_band: float = 2.0              # [°C] half-width of the melt/freeze range
    note: str = ""

    @property
    def volumetric_heat_capacity(self) -> float:
        """C_v = rho * cp  [J/(m³·K)] — thermal mass per unit volume."""
        return self.rho * self.cp

    @property
    def thermal_diffusivity(self) -> float:
        """alpha = k / (rho * cp)  [m²/s] — speed a thermal front travels."""
        return self.k / (self.rho * self.cp)

    @property
    def is_pcm(self) -> bool:
        return self.latent_heat is not None and self.phase_temp is not None


# ---------------------------------------------------------------------------
# Curated database. Values are representative of materials relevant to
# high-altitude cold-region shelters (insulation, earthen/stone mass, glazing,
# and thermal-storage options including water and PCM).
# ---------------------------------------------------------------------------
_DB: List[Material] = [
    # --- Insulation (low k, low mass): cuts conduction loss ---------------
    Material("Expanded polystyrene (EPS)", "insulation", k=0.035, rho=20, cp=1400,
             note="Cheap rigid board insulation."),
    Material("Extruded polystyrene (XPS)", "insulation", k=0.033, rho=35, cp=1400,
             note="Denser, moisture-resistant board."),
    Material("Glass wool", "insulation", k=0.040, rho=20, cp=840,
             note="Common fibrous insulation blanket."),
    Material("Rock/mineral wool", "insulation", k=0.038, rho=100, cp=840,
             note="Fibrous insulation, better fire rating."),
    Material("Polyurethane (PU) foam", "insulation", k=0.025, rho=35, cp=1400,
             note="Best-in-class conductivity for the thickness."),

    # --- Structure / thermal mass (high k or high C_v) --------------------
    Material("Dense concrete", "mass", k=1.70, rho=2300, cp=880,
             solar_absorptance=0.65, note="Good thermal mass; high loss if uninsulated."),
    Material("Reinforced concrete", "mass", k=2.00, rho=2400, cp=880,
             solar_absorptance=0.65),
    Material("Stone (granite)", "mass", k=2.80, rho=2600, cp=790,
             solar_absorptance=0.55, note="Locally abundant in Ladakh; heavy mass."),
    Material("Fired-clay brick", "structure", k=0.72, rho=1920, cp=835,
             solar_absorptance=0.70),
    Material("Adobe / mud brick", "mass", k=0.75, rho=1600, cp=880,
             solar_absorptance=0.60, note="Traditional earthen wall; decent mass, low k."),
    Material("Rammed earth", "mass", k=1.25, rho=2000, cp=880,
             solar_absorptance=0.60),
    Material("Softwood timber (pine)", "structure", k=0.13, rho=520, cp=1600,
             solar_absorptance=0.60),
    Material("Plywood", "structure", k=0.13, rho=545, cp=1215),
    Material("Gypsum board", "finish", k=0.16, rho=800, cp=1090,
             note="Interior lining board."),
    Material("Steel", "structure", k=50.0, rho=7800, cp=450,
             solar_absorptance=0.70, emissivity=0.30,
             note="High conductivity — a thermal bridge if not broken."),

    # --- Glazing ----------------------------------------------------------
    Material("Glass (single pane)", "glazing", k=1.00, rho=2500, cp=840,
             solar_absorptance=0.10, emissivity=0.90,
             note="Solar enters, but high U-value: big night-time loss."),

    # --- Thermal-storage options -----------------------------------------
    Material("Water (storage wall)", "mass", k=0.60, rho=1000, cp=4186,
             note="Very high heat capacity per m³ — excellent daytime heat store."),
    Material("Air (cavity)", "air", k=0.026, rho=1.2, cp=1005,
             note="Modelled as a thermal resistance, not a mass."),

    # --- Phase-change material -------------------------------------------
    Material("PCM (paraffin, ~22°C)", "pcm", k=0.20, rho=800, cp=2000,
             latent_heat=180_000, phase_temp=22.0, phase_band=2.0,
             note="Stores ~180 kJ/kg latent heat near 22°C; buffers indoor temp."),
]

# name (lowercased) -> Material
MATERIALS: Dict[str, Material] = {m.name.lower(): m for m in _DB}


# ---------------------------------------------------------------------------
# Accessors
# ---------------------------------------------------------------------------
def get_material(name: str) -> Material:
    """Look up a material by name (case-insensitive)."""
    key = name.strip().lower()
    if key not in MATERIALS:
        raise KeyError(
            f"Unknown material {name!r}. Available: {', '.join(sorted(m.name for m in _DB))}"
        )
    return MATERIALS[key]


def list_materials(category: Optional[str] = None) -> List[str]:
    """List material names, optionally filtered to one category."""
    items = _DB if category is None else [m for m in _DB if m.category == category]
    return sorted(m.name for m in items)


def categories() -> List[str]:
    """All distinct material categories."""
    return sorted({m.category for m in _DB})


def custom(
    name: str,
    k: float,
    rho: float,
    cp: float,
    category: str = "custom",
    solar_absorptance: float = 0.6,
    emissivity: float = 0.90,
    latent_heat: Optional[float] = None,
    phase_temp: Optional[float] = None,
    phase_band: float = 2.0,
    note: str = "user-defined",
) -> Material:
    """Build a user-defined material (the PS explicitly wants custom properties)."""
    return Material(
        name=name, category=category, k=k, rho=rho, cp=cp,
        solar_absorptance=solar_absorptance, emissivity=emissivity,
        latent_heat=latent_heat, phase_temp=phase_temp, phase_band=phase_band,
        note=note,
    )


if __name__ == "__main__":
    # Quick self-test — runs on plain Python, no third-party deps required.
    print(f"{'Material':28s} {'k':>6s} {'Cv(kJ/m³K)':>11s} {'alpha(mm²/s)':>13s}  category")
    print("-" * 78)
    for m in _DB:
        print(
            f"{m.name:28s} {m.k:6.3f} {m.volumetric_heat_capacity/1000:11.1f} "
            f"{m.thermal_diffusivity*1e6:13.3f}  {m.category}"
        )
    print(f"\n{len(_DB)} materials across categories: {', '.join(categories())}")
