"""Pichimon (471, fresh): a round fish baby with a tail fin, two feelers and a beak, on Koromon's skeleton and animations (DW1 type 2).

The mesh, UVs and texture page are drawn by authoring/pichimon.py; see the package docstring.
"""
from tools.models import babies

SPECIES = 471


def build(extracted):
    """Return (MMD, TIM) generated from the player's DW1 extraction."""
    return babies.build_species(SPECIES, extracted)
