"""Pabumon (470, fresh): a round drop with a tuft and two small bubbles, on Punimon's skeleton and animations (DW1 type 15).

The mesh, UVs and texture page are drawn by authoring/pabumon.py; see the package docstring.
"""
from tools.models import babies

SPECIES = 470


def build(extracted):
    """Return (MMD, TIM) generated from the player's DW1 extraction."""
    return babies.build_species(SPECIES, extracted)
