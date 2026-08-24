"""
Thermal-Shelter — a software model for designing area-specific passive shelters
that maintain thermal comfort with minimal energy.

SIH 2026 · Problem 26051 · DRDO.

Sub-modules
-----------
materials  : thermal-property database for construction & thermal-mass materials
climate    : ambient climate data (Ladakh presets + user-supplied CSV)      [wip]
solar      : solar position & irradiance on each shelter surface (pvlib)     [wip]
geometry   : shelter geometry (walls / roof / floor / openings)              [wip]
engine     : transient thermal model — predicts indoor temperature & heat flows [wip]
comfort    : thermal-comfort metrics                                          [wip]
"""

__version__ = "0.1.0"

# materials.py is pure-Python (no third-party deps), so it is safe to import even
# before the scientific stack is installed. Heavier modules are imported lazily by
# the code that needs them.
from . import materials  # noqa: E402,F401

__all__ = ["materials", "__version__"]
