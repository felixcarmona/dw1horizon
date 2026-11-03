"""Nyokimon (473, fresh): a teardrop seed with a leaning sprout and two leaves, on Yuramon's skeleton and animations (DW1 type 43).

The mesh, UVs and texture page are drawn by authoring/nyokimon.py; see the package docstring.
"""
from tools.models import babies

SPECIES = 473


def build(extracted):
    """Return (MMD, TIM) generated from the player's DW1 extraction."""
    return babies.build_species(SPECIES, extracted)
