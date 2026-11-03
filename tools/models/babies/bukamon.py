"""Bukamon (475, in-training): a grey seal pup with a curled tail and a flame tuft, on Koromon's skeleton and animations (DW1 type 2).

The mesh, UVs and texture page are drawn by authoring/bukamon.py; see the package docstring.
"""
from tools.models import babies

SPECIES = 475


def build(extracted):
    """Return (MMD, TIM) generated from the player's DW1 extraction."""
    return babies.build_species(SPECIES, extracted)
