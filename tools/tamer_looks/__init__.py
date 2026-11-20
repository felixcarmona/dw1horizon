"""Tamer looks made from the player's own disc: the bald tamer and the hairstyles built on it.

build(model, texture) takes the original tamer model (mmd.MMD) and texture (mmd.Tim4) and returns the bald texture
and the list of (name, mmd.MMD): 'bald' first, then every hairstyle. Hair polygons are untextured gouraud triangles
whose colour is a grey level (128 lit, 79 underside): the game tints them with the chosen hair colour at load.
"""
from . import bald, styles, wig

ORDER = ('classic', 'messy', 'quiff', 'curtains', 'buzz', 'long', 'mullet', 'ponytail', 'pigtails', 'bun', 'buns')


def build(model, texture):
    base, bald_texture = bald.make(model, texture)
    wig.Wig.base = base
    looks = [('bald', base)]
    for name in ORDER:
        looks.append((name, styles.STYLES[name]().model()))
    return bald_texture, looks
