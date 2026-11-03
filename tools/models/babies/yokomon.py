"""Yokomon (477, in-training): a pink bulb with a flower on its head, on Tanemon's skeleton and animations (DW1 type 44).

The mesh, UVs and texture page are drawn by authoring/yokomon.py; see the package docstring.
"""
from tools.models import babies

SPECIES = 477


def build(extracted):
    """Return (MMD, TIM) generated from the player's DW1 extraction."""
    return babies.build_species(SPECIES, extracted)
