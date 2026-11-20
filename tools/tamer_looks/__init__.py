"""Tamer looks made from the player's own disc: the bald tamer and the hairstyles built on it.

build(model, texture) takes the original tamer model (mmd.MMD) and texture (mmd.Tim4) and returns the bald texture
and the list of (name, mmd.MMD): 'bald' first, then every hairstyle. Hair polygons are textured gouraud triangles
that use the strand tile and palette row of hairtex: the game writes that row for the chosen hair colour.
"""
from . import bald, hairtex, styles, wig

ORDER = ('classic', 'messy', 'quiff', 'curtains', 'buzz', 'long', 'mullet', 'ponytail', 'pigtails', 'bun', 'buns')


def build(model, texture):
    base, bald_texture = bald.make(model, texture)
    wig.Wig.base = base
    looks = [('bald', base)]
    hairtex.paint(bald_texture)
    for name in ORDER:
        looks.append((name, styles.STYLES[name]().model()))
    return bald_texture, looks
