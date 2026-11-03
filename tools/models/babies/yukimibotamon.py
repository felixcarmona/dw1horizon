"""YukimiBotamon (472, fresh): a white snow puff with two round ears, on Botamon's skeleton and animations (DW1 type 1).

The mesh, UVs and texture page are drawn by authoring/yukimibotamon.py; see the package docstring.
"""
from tools.models import babies

SPECIES = 472


def build(extracted):
    """Return (MMD, TIM) generated from the player's DW1 extraction."""
    return babies.build_species(SPECIES, extracted)
