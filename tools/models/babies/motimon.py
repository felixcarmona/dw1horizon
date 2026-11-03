"""Motimon (474, in-training): a soft pink mochi bell, on Koromon's skeleton and animations (DW1 type 2).

The mesh, UVs and texture page are drawn by authoring/motimon.py; see the package docstring.
"""
from tools.models import babies

SPECIES = 474


def build(extracted):
    """Return (MMD, TIM) generated from the player's DW1 extraction."""
    return babies.build_species(SPECIES, extracted)
