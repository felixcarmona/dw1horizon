"""Native DW1 MetalGreymon with the gold palette and native technique clips.

Only palette colours, polygon CLUT selections and technique slot assignments
change. Every animation program is copied without retiming or re-encoding.
"""
import hashlib
from pathlib import Path

MODEL_SHA256 = '2b330474fc2c5ab1f308c51b7ddaa3c503c79255c0cd2168e9979073125c304d'
TEXTURE_SHA256 = 'e43a9f7ac7bc7e262f47d7599ab1df9c5666710f4b9488feb55881ed84b091ab'
GOLD = dict(zip(('847bad', '736b9c', '635a8c', '524a7b', '42396b', '31295a', '4a3973'),
                ('ffce42', 'd6ad39', 'bd9431', 'a58429', '8c6b21', '735a21', 'bd9431')))
CREAM = dict(zip(('847bad', '736b9c', '635a8c', '524a7b', '42396b', '31295a'),
                 ('ffffd6', 'efe7bd', 'ded6a5', 'cec68c', 'bdb573', 'b5a563')))
BROWN = dict(zip(('f7f7ef', 'd6d6ce', 'b5b5ad', '94948c', '73736b', '52524a', '313129'),
                 ('8c7b63', '73634a', '635239', '524229', '423121', '392921', '312118')))
# 224 retains its technique order, including the equipped slots in existing saves.
# Shared techniques select their matching native clip. The four additional moves
# use Heat Laser, Meltdown, Megaton Punch and Buster Dive respectively.
TECHNIQUE_SLOTS = (0x36, 0x35, 0x3A, 0x39, 0x37, 0x34, 0x2F,
                   0x2E, 0x30, 0x30, 0x31, 0x31, 0x32, 0x3C)


def build(extracted):
    """Return (MMD, TIM) generated from the player's DW1 extraction."""
    import mmd
    import motionstorage

    extracted = Path(extracted)
    source = (extracted / 'CHDAT/MMD0/MTGR.MMD').read_bytes()
    texture = mmd.load_tim(str(extracted / 'CHDAT/ALLTIM.TIM'), 12)
    for data, expected in ((source, MODEL_SHA256), (texture.to_bytes(), TEXTURE_SHA256)):
        if hashlib.sha256(data).hexdigest() != expected:
            raise ValueError('MetalGreymon: native source SHA-256 mismatch')
    model = mmd.MMD.parse(source, 30)

    def recolour(palette, mapping):
        result = []
        for colour in palette:
            key = '%02x%02x%02x' % tuple(mmd.c15_to_rgba(colour)[:3])
            if key in mapping:
                red, green, blue = (int(mapping[key][i:i + 2], 16) >> 3 for i in (0, 2, 4))
                colour = red | green << 5 | blue << 10 | (colour & 0x8000)
            result.append(colour)
        return result

    base = list(texture.pal[1])
    texture.pal[5] = recolour(base, CREAM)
    texture.pal[6] = recolour(recolour(base, BROWN), GOLD)
    texture.pal[7] = recolour(base, {key: value for key, value in GOLD.items() if key != '31295a'})
    for row in (0, 1, 2, 4):
        texture.pal[row] = recolour(texture.pal[row], GOLD)

    for object_id, obj in enumerate(model.tmd.objects):
        for primitive_id, primitive in enumerate(obj.prims):
            polygon = primitive.decode()
            row = (polygon['cba'] >> 6) - 488
            uv = (min(u for u, v in polygon['uv']), min(v for u, v in polygon['uv']))
            selected = None
            if row == 1 and uv in ((192, 56), (216, 32)) and object_id in (9, 18, 21):
                selected = 5
            elif object_id == 2 and (36 <= primitive_id <= 41 or 55 <= primitive_id <= 60):
                selected = 6
            elif row == 1 and object_id in (7, 8, 13, 14, 15, 16, 19):
                selected = 7
            if selected is not None:
                polygon['cba'] = (polygon['cba'] & 63) | ((488 + selected) << 6)
                obj.prims[primitive_id] = mmd.Prim.encode(polygon)

    # Read from a snapshot: several assignments form cycles in the slot table.
    native_slots = list(model.anims.table)
    for destination, native in enumerate(TECHNIQUE_SLOTS, 0x2E):
        if native_slots[native] is None:
            raise ValueError(f'MetalGreymon: native technique slot {native:#x} is empty')
        model.anims.table[destination] = native_slots[native]
    result = model.build()
    motionstorage.require(result, 30)
    return result, texture.to_bytes()
