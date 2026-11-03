"""Nyaromon (476, in-training): a wide cat head with two ears and a tail, on Tokomon's skeleton and animations (DW1 type 30).

The mesh, UVs and texture page are drawn by authoring/nyaromon.py; see the package docstring.
"""
from tools.models import babies

SPECIES = 476


def build(extracted):
    """Return (MMD, TIM) generated from the player's DW1 extraction."""
    return babies.build_species(SPECIES, extracted)
