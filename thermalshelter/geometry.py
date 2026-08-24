"""
Shelter geometry & envelope for the Thermal-Shelter model.

A shelter is a box made of opaque `Surface`s (walls, roof, floor) plus `Window`s.
Each opaque surface has a `Construction`: an ordered stack of `Layer`s (a material
at a thickness). From that stack we compute the two things the thermal engine needs
for every surface:

    R  — thermal resistance   [m²·K/W]   (how much it resists heat flow; ~ insulation)
    C  — areal heat capacity  [J/(m²·K)] (how much heat its mass stores; ~ thermal mass)

For the transient RC model we split each construction at its mid-plane into an
*outer* resistance (skin → mass) and an *inner* resistance (mass → indoor air), so a
single lumped "envelope mass" node sits in the middle and can store daytime heat.

Windows are treated as massless: a U-value (conduction) and an SHGC (fraction of
incident sunlight transmitted indoors).

`box_shelter(...)` assembles a complete, oriented shelter from high-level inputs so
the UI/optimiser can build one in a single call.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

from .materials import Material, get_material

# Surface air-film resistances [m²·K/W] (ASHRAE, still air interior / moving exterior)
R_FILM_EXT = 0.04
R_FILM_INT = 0.13


# ---------------------------------------------------------------------------
# Constructions
# ---------------------------------------------------------------------------
@dataclass(frozen=True)
class Layer:
    material: Material
    thickness: float  # [m]

    @property
    def R(self) -> float:
        """Conductive resistance of this layer [m²·K/W]."""
        return self.thickness / self.material.k

    @property
    def C_area(self) -> float:
        """Areal heat capacity of this layer [J/(m²·K)]."""
        return self.thickness * self.material.rho * self.material.cp


@dataclass
class Construction:
    """An ordered layer stack, listed OUTER surface → INNER surface."""

    name: str
    layers: List[Layer]

    @property
    def R_cond(self) -> float:
        return sum(l.R for l in self.layers)

    @property
    def C_area(self) -> float:
        return sum(l.C_area for l in self.layers)

    @property
    def R_total(self) -> float:
        """Air-to-air resistance including surface films [m²·K/W]."""
        return R_FILM_EXT + self.R_cond + R_FILM_INT

    @property
    def U(self) -> float:
        """Overall heat-transfer coefficient [W/(m²·K)]."""
        return 1.0 / self.R_total

    @property
    def R_outer(self) -> float:
        """Resistance from outdoor air to the mid-plane mass node."""
        return R_FILM_EXT + 0.5 * self.R_cond

    @property
    def R_inner(self) -> float:
        """Resistance from the mid-plane mass node to indoor air."""
        return R_FILM_INT + 0.5 * self.R_cond

    @property
    def outer_material(self) -> Material:
        return self.layers[0].material


def make_construction(name: str, layers: List[Tuple[str, float]]) -> Construction:
    """Build a Construction from (material_name, thickness) pairs, outer → inner."""
    return Construction(name, [Layer(get_material(m), t) for m, t in layers])


# --- A few ready-made constructions (outer → inner) --------------------------
UNINSULATED_STONE = make_construction(
    "Uninsulated stone (0.4 m)", [("Stone (granite)", 0.40)]
)
INSULATED_WALL = make_construction(
    "Insulated stone wall",
    [("Stone (granite)", 0.20), ("Extruded polystyrene (XPS)", 0.10),
     ("Gypsum board", 0.0125)],
)
INSULATED_ROOF = make_construction(
    "Insulated timber roof",
    [("Softwood timber (pine)", 0.02), ("Polyurethane (PU) foam", 0.15),
     ("Plywood", 0.012)],
)
INSULATED_FLOOR = make_construction(
    "Insulated concrete floor",
    [("Dense concrete", 0.15), ("Extruded polystyrene (XPS)", 0.05)],
)


# ---------------------------------------------------------------------------
# Glazing
# ---------------------------------------------------------------------------
@dataclass(frozen=True)
class Glazing:
    name: str
    U: float      # [W/(m²·K)] air-to-air, including films
    SHGC: float   # solar heat gain coefficient (0–1)
    emissivity: float = 0.90


SINGLE_GLAZING = Glazing("Single glazing", U=5.7, SHGC=0.85)
DOUBLE_GLAZING = Glazing("Double glazing", U=2.8, SHGC=0.76)
DOUBLE_LOWE = Glazing("Double glazing, low-e", U=1.8, SHGC=0.60)


# ---------------------------------------------------------------------------
# Surfaces, windows, added thermal mass
# ---------------------------------------------------------------------------
@dataclass
class Surface:
    """An opaque face of the shelter."""

    name: str
    area: float           # [m²] opaque area (windows already subtracted)
    azimuth: float        # [deg] compass direction it faces (0=N, 90=E, 180=S, 270=W)
    tilt: float           # [deg] from horizontal (90 = vertical wall, 0 = flat roof)
    construction: Construction
    ground_coupled: bool = False   # floors exchange with ground, not sky/sun

    @property
    def solar_absorptance(self) -> float:
        return self.construction.outer_material.solar_absorptance

    @property
    def emissivity(self) -> float:
        return self.construction.outer_material.emissivity

    @property
    def UA(self) -> float:
        return self.construction.U * self.area


@dataclass
class Window:
    name: str
    area: float
    azimuth: float
    tilt: float
    glazing: Glazing

    @property
    def UA(self) -> float:
        return self.glazing.U * self.area


@dataclass
class ThermalMass:
    """Extra interior thermal storage: a water wall, PCM panel, stone floor slab…"""

    name: str
    material: Material
    volume: float          # [m³]
    surface_area: float    # [m²] area exposed to indoor air (convective coupling)
    h_couple: float = 8.0  # [W/(m²·K)] interior surface coefficient

    @property
    def C(self) -> float:
        """Sensible heat capacity [J/K]."""
        return self.volume * self.material.rho * self.material.cp

    @property
    def G(self) -> float:
        """Conductance to indoor air [W/K]."""
        return self.surface_area * self.h_couple


# ---------------------------------------------------------------------------
# Shelter
# ---------------------------------------------------------------------------
_CARDINALS = [(0, "N"), (90, "E"), (180, "S"), (270, "W"), (360, "N")]


def _cardinal(azimuth: float) -> str:
    az = azimuth % 360
    return min(_CARDINALS, key=lambda c: abs(c[0] - az))[1]


@dataclass
class Shelter:
    name: str
    length: float          # [m]
    width: float           # [m]
    height: float          # [m]
    walls: List[Surface]
    roof: Surface
    floor: Surface
    windows: List[Window] = field(default_factory=list)
    infiltration_ach: float = 0.5          # air changes per hour
    thermal_mass: List[ThermalMass] = field(default_factory=list)

    # -- derived geometry --
    @property
    def volume(self) -> float:
        return self.length * self.width * self.height

    @property
    def floor_area(self) -> float:
        return self.length * self.width

    @property
    def opaque_surfaces(self) -> List[Surface]:
        return [*self.walls, self.roof, self.floor]

    @property
    def window_area(self) -> float:
        return sum(w.area for w in self.windows)

    @property
    def envelope_area(self) -> float:
        return sum(s.area for s in self.opaque_surfaces) + self.window_area

    def summary(self) -> str:
        lines = [
            f"{self.name}: {self.length}×{self.width}×{self.height} m  "
            f"(floor {self.floor_area:.1f} m², volume {self.volume:.1f} m³)",
            f"  infiltration {self.infiltration_ach} ACH, "
            f"window area {self.window_area:.1f} m²",
            "  Opaque surfaces:",
        ]
        for s in self.opaque_surfaces:
            lines.append(
                f"    {s.name:14s} {s.area:5.1f} m²  U={s.construction.U:4.2f} "
                f"C={s.construction.C_area/1000:6.0f} kJ/m²K  "
                f"({s.construction.name})"
            )
        for w in self.windows:
            lines.append(
                f"    {w.name:14s} {w.area:5.1f} m²  U={w.glazing.U:4.2f} "
                f"SHGC={w.glazing.SHGC:.2f}  ({w.glazing.name})"
            )
        for m in self.thermal_mass:
            lines.append(
                f"    + mass {m.name}: {m.C/1e6:.1f} MJ/K ({m.material.name})"
            )
        return "\n".join(lines)


def box_shelter(
    length: float = 6.0,
    width: float = 4.0,
    height: float = 2.6,
    orientation: float = 180.0,          # azimuth the "front" (length) wall faces
    wall: Construction = INSULATED_WALL,
    roof: Construction = INSULATED_ROOF,
    floor: Construction = INSULATED_FLOOR,
    glazing: Glazing = DOUBLE_GLAZING,
    window_wall_ratio: float = 0.15,
    window_facades: Tuple[str, ...] = ("S",),   # cardinal faces that get windows
    infiltration_ach: float = 0.5,
    thermal_mass: Optional[List[ThermalMass]] = None,
    name: str = "Shelter",
) -> Shelter:
    """
    Assemble a rectangular shelter. The front (length-facing) wall points at
    `orientation`; the other three follow at 90° steps. Windows are placed on the
    requested cardinal facades as a fraction (`window_wall_ratio`) of that wall.
    """
    # azimuth of each wall and its gross area
    faces = {
        "front": (orientation % 360, length * height),
        "right": ((orientation + 90) % 360, width * height),
        "back": ((orientation + 180) % 360, length * height),
        "left": ((orientation + 270) % 360, width * height),
    }

    # map requested cardinal window facades onto whichever wall points that way
    want = {c.upper() for c in window_facades}
    windows: List[Window] = []
    walls: List[Surface] = []
    for _pos, (az, gross) in faces.items():
        card = _cardinal(az)
        win_area = gross * window_wall_ratio if card in want else 0.0
        if win_area > 0:
            windows.append(
                Window(f"Window-{card}", win_area, az, 90.0, glazing)
            )
        walls.append(
            Surface(f"Wall-{card}", gross - win_area, az, 90.0, wall)
        )

    roof_s = Surface("Roof", length * width, orientation % 360, 0.0, roof)
    floor_s = Surface(
        "Floor", length * width, orientation % 360, 180.0, floor, ground_coupled=True
    )

    return Shelter(
        name=name, length=length, width=width, height=height,
        walls=walls, roof=roof_s, floor=floor_s, windows=windows,
        infiltration_ach=infiltration_ach,
        thermal_mass=list(thermal_mass or []),
    )


if __name__ == "__main__":
    s = box_shelter()
    print(s.summary())
    print(f"\nEnvelope area {s.envelope_area:.1f} m², "
          f"total UA (opaque) "
          f"{sum(x.UA for x in s.opaque_surfaces):.1f} W/K")
