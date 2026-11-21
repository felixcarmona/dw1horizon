#!/usr/bin/env python3
"""TAMER.DAT: the tamer's other looks (bald, the hairstyles, the clothes), made from the player's own disc.

  tamer_pack.py build OUT [--model BOYS.MMD] [--alltim ALLTIM.TIM]
  tamer_pack.py list

Look 0 is the original tamer: with his own clothes and face the game loads the disc's own model and texture.
Looks 1.. are tools/tamer_looks (bald, then the hairstyles). A model in the file has no torso, arms, legs or feet:
those objects are a shirt, a pair of trousers and a pair of shoes (tools/tamer_looks/shirts.py, legs.py, shoes.py),
read behind the model and linked into it, so any head goes with any clothes. Garment 0 of each kind is the original
tamer's. A backpack is a piece of the torso that the game copies into the shirt's (tools/tamer_looks/backpacks.py).
The file, in 2048-byte sectors, little endian:

  sector 0   "TLK1", u16 looks, u16 texture sector, u16 cold sector, u16 cold sectors, u16 colours
             0x10: per look u16 first sector, u16 length in 4-byte words
             0x80: per hair colour r, g, b
             0xC0: the brightness of each of the hair texture's sixteen tones, 128 = the colour itself
             0xD0: u16 shirts, u16 cloth colours; the original tamer's model without his clothes (u16 first
                   sector, u16 words); u16 sector of the original tamer's texture with his first face; u16 trousers,
                   u16 shoes, u16 backpacks
             0x100: per shirt u16 first sector, u16 sectors of geometry (after the shirt's first sector); after
                    the shirts that are chosen, the original hoodie for another backpack and for none
             0x140: the same per pair of trousers
             0x200: per pair of shoes, as per shirt
             0x240: per backpack u16 its sector, u16 0
             0x300: per cloth colour r, g, b of its shade, of the cloth, of its light, and of stripes, prints and
                    trim on it
  texture    the bald head's texture, one ALLTIM entry (9 sectors), shared by every look; one per face (u16 at 0x0E:
             how many), the second drawn by tools/tamer_looks/face.py; after them the original tamer's texture with
             each face but the first (his first face is the disc's own texture)
  cold       the animations of COLD_SLOTS, the same for every look, laid out by tools/coldsplit.py
  models     one resident model per look, then the original tamer's
  clothes    per garment one sector (the size of its geometry, where each object's corners, normals and polygons
             are, how its palette row is coloured, and the pixels it draws on the texture: shirts.head; a boot's leg
             too: shoes.py) and its geometry; per backpack one sector

A look's model is larger than the original, and the tamer's buffer (TAMER_MMD_MAX) does not grow, so the
animations of COLD_SLOTS leave the model: their table entries become cold entries (COLD_ANIM_FLAG, as the partners')
and the game reads one into the last 4096 bytes of the buffer when it starts. The resident model therefore has to
fit in TAMER_MMD_MAX - 4096 bytes together with the largest garment of each kind. The meshes are never simplified for that: more room means more cold slots.

Hair polygons are textured with the strand tile of tools/tamer_looks/hairtex.py and its own palette row; the game
writes that row for the chosen colour (lookHairPalette), so one model serves every colour.
"""
import argparse
import copy
import os
import struct
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import coldsplit  # noqa: E402
import mmd  # noqa: E402
import tamer_looks  # noqa: E402
from tamer_looks import backpacks, face, hairtex, legs, shirts, shoes, wig  # noqa: E402

SECTOR = 2048
TAMER_MMD_MAX = 0xE000          # include/dw/memmap.h
COLD_BUFFER = 0x1000            # the tail of the tamer's buffer (TAMER_COLD_BUFFER)
RESIDENT_MAX = TAMER_MMD_MAX - COLD_BUFFER
# Animations that leave the model: the ones only scenes start (13, 15-26: the engine itself never asks for them) and
# the gym's (9), which the game reads while the gym loads (modTamerColdPrefetch), and the two praising gestures (38, 39),
# read when the praise starts, and fishing's (27-34), which make room for the shirts.
COLD_SLOTS = (9, 13) + tuple(range(15, 27)) + tuple(range(27, 35)) + (38, 39)
CLOTH_AT = 0x300                # in the header: the cloth colours (LOOK_CLOTH)
HEAD = 1                        # the head's object in the tamer model
MODEL = os.path.join(mmd.EXTRACTED, 'CHDAT', 'MMD0', 'BOYS.MMD')
ALLTIM = mmd.ALLTIM

# Hair colours, in the order the game numbers them. A tone of the hair's texture shows colour * level / 128.
COLOURS = (
    ('brown', (120, 84, 48)),
    ('dark brown', (84, 56, 36)),
    ('black', (44, 42, 52)),
    ('chestnut', (150, 84, 44)),
    ('blond', (224, 184, 88)),
    ('light blond', (244, 224, 150)),
    ('ginger', (224, 120, 40)),
    ('red', (200, 48, 44)),
    ('burgundy', (128, 32, 56)),
    ('pink', (216, 112, 152)),
    ('lavender', (184, 160, 224)),
    ('purple', (136, 88, 184)),
    ('navy', (40, 56, 120)),
    ('blue', (64, 112, 208)),
    ('turquoise', (64, 192, 192)),
    ('green', (72, 160, 88)),
    ('lime', (160, 208, 64)),
    ('grey', (128, 132, 140)),
    ('silver', (200, 204, 216)),
    ('white', (240, 240, 244)),
)


def look_names():
    return ('original', 'bald') + tamer_looks.ORDER


def slim_head(model):
    """Drop the head's unused corners and normals and share the hair's equal normals: the same picture, fewer bytes."""
    tm = model.tmd
    ob = tm.objects[HEAD]
    prims = [p.decode() for p in ob.prims]
    verts = tm.verts[ob.vert_start:ob.vert_start + ob.nvert]
    norms = tm.norms[ob.norm_start:ob.norm_start + ob.nnorm]

    new_verts, new_norms, vert_at, norm_at = [], [], {}, {}
    for d in prims:
        hair = d.get('cba') == wig.HAIR_CBA
        for key, old, new, at in (('verts', verts, new_verts, vert_at), ('norms', norms, new_norms, norm_at)):
            out = []
            for i in d[key]:
                value = old[i]
                # Skull corners keep their own entries: only identical hair normals are shared.
                k = (hair, value) if key == 'norms' and hair else (key, i)
                if k not in at:
                    at[k] = len(new)
                    new.append(value)
                out.append(at[k])
            d[key] = out
    dv, dn = len(new_verts) - ob.nvert, len(new_norms) - ob.nnorm
    tm.verts[ob.vert_start:ob.vert_start + ob.nvert] = new_verts
    tm.norms[ob.norm_start:ob.norm_start + ob.nnorm] = new_norms
    ob.nvert, ob.nnorm = len(new_verts), len(new_norms)
    ob.prims = [mmd.Prim.encode(d) for d in prims]
    for o in tm.objects[HEAD + 1:]:
        o.vert_start += dv
        o.norm_start += dn


def resident(model, nbones, room):
    """(resident model, cold part) of one look, without the objects clothes bring. Nothing is simplified to make it
    fit: a look that leaves less than room bytes for the clothes is an error."""
    slim_head(model)
    for objects in (shirts.OBJECTS, legs.OBJECTS, shoes.OBJECTS):
        shirts.strip(model, objects)
    res, cold = coldsplit.split(model.build(), nbones, slots=COLD_SLOTS, buffer_bytes=COLD_BUFFER)
    res += b'\0' * (-len(res) % 4)
    if len(res) + room > RESIDENT_MAX:
        raise SystemExit(f'tamer look does not fit: {len(res)} + {room} > {RESIDENT_MAX} bytes')
    return res, cold


def pad(data):
    return data + b'\0' * (-len(data) % SECTOR)


def build(model_path, alltim_path):
    """(TAMER.DAT bytes, report lines)."""
    model = mmd.MMD.load(model_path, 0)
    original = mmd.load_tim(alltim_path, 0)
    # per kind of garment: its name, where its directory is in the header, and (name, first sector, geometry) of each
    wardrobe = [('shirt', 0x100, [g[:3] for g in shirts.build(model, original)]),
                ('trousers', 0x140, [g[:3] for g in legs.build(model, original)]),
                ('shoes', 0x200, [g[:3] for g in shoes.build(model, original)])]
    packs = backpacks.build(model, original)
    largest = [max(len(body) for _, _, body in garments) for _, _, garments in wardrobe]
    room = sum(largest)
    texture, looks = tamer_looks.build(copy.deepcopy(model), original)
    textures = [texture.to_bytes(), face.make(texture).to_bytes()]      # one per face
    # the original tamer's: from the second face on, then with his first (read when he wears another shirt)
    capped = [face.make(original, lid=False).to_bytes(), original.to_bytes()]
    assert all(len(t) == mmd.ALLTIM_STRIDE for t in textures + capped), [len(t) for t in textures + capped]
    texture = b''.join(textures + capped)
    parts, cold_part, report = [], None, []
    for name, look in looks + [('original', model)]:
        res, cold = resident(look, model.nbones, room)
        assert cold_part in (None, cold), 'the cold animations differ between looks'
        cold_part = cold
        parts.append(res)
        report.append(f'{name}: {len(res)} bytes resident ({RESIDENT_MAX - len(res) - room} spare with the largest clothes)')
    header = bytearray(SECTOR)
    tex_sector = 1
    cold_sector = tex_sector + len(texture) // SECTOR
    cold_sectors = len(pad(cold_part)) // SECTOR
    struct.pack_into('<4s5H', header, 0, b'TLK1', len(looks), tex_sector, cold_sector, cold_sectors, len(COLOURS))
    sector = cold_sector + cold_sectors
    for i, part in enumerate(parts):
        at = 0x10 + 4 * i if i < len(looks) else 0xD4
        struct.pack_into('<2H', header, at, sector, len(part) // 4)
        sector += len(pad(part)) // SECTOR
    for i, (_, rgb) in enumerate(COLOURS):
        header[0x80 + 3 * i:0x83 + 3 * i] = bytes(rgb)
    header[0xC0:0xD0] = bytes(hairtex.LEVELS)
    struct.pack_into('<H', header, 0x0E, len(textures))
    struct.pack_into('<2H', header, 0xD0, len(shirts.NAMES), len(shirts.COLOURS))
    struct.pack_into('<3H', header, 0xDA, len(wardrobe[1][2]), len(wardrobe[2][2]), len(packs))
    struct.pack_into('<H', header, 0xD8, tex_sector + (len(textures) + len(capped) - 1) * (mmd.ALLTIM_STRIDE // SECTOR))
    closet = b''
    before = max(len(p) for p in parts)
    for (kind, at, garments), most in zip(wardrobe, largest):
        if at + 4 * len(garments) > at + 0x40:
            raise SystemExit(f'too many {kind} for the header')
        for i, (name, first, body) in enumerate(garments):
            sectors = len(pad(body)) // SECTOR
            # the game reads whole sectors behind what it has: a read may run into the buffer's tail, never past it
            if before + sectors * SECTOR > TAMER_MMD_MAX:
                raise SystemExit(f'{kind} {name} does not fit behind the largest look')
            struct.pack_into('<2H', header, at + 4 * i, sector, sectors)
            sector += 1 + sectors
            closet += first + pad(body)
            report.append(f'{kind} {name}: {len(body)} bytes')
        before += most
    if len(packs) > 16:
        raise SystemExit('too many backpacks for the header')
    for i, pack in enumerate(packs):
        struct.pack_into('<2H', header, 0x240 + 4 * i, sector, 0)
        sector += 1
        closet += pack[1]
        report.append(f'backpack {pack[0]}')
    for i, cloth in enumerate(shirts.COLOURS):
        header[CLOTH_AT + 12 * i:CLOTH_AT + 12 * i + 12] = bytes(sum(cloth[1:], ()))
    report.append(f'cold animations: {len(cold_part)} bytes, {cold_sectors} sectors')
    return bytes(header) + texture + pad(cold_part) + b''.join(pad(p) for p in parts) + closet, report


def main():
    ap = argparse.ArgumentParser(description=__doc__.split('\n')[0])
    sub = ap.add_subparsers(dest='cmd', required=True)
    b = sub.add_parser('build')
    b.add_argument('out')
    b.add_argument('--model', default=MODEL)
    b.add_argument('--alltim', default=ALLTIM)
    sub.add_parser('list')
    args = ap.parse_args()
    if args.cmd == 'list':
        for i, name in enumerate(look_names()):
            print(f'look {i}: {name}')
        for i, (name, rgb) in enumerate(COLOURS):
            print(f'colour {i}: {name} {rgb}')
        for i, name in enumerate(shirts.NAMES):
            print(f'shirt {i}: {name}')
        for i, name in enumerate(legs.NAMES):
            print(f'trousers {i}: {name}')
        for i, name in enumerate(shoes.NAMES):
            print(f'shoes {i}: {name}')
        for i, name in enumerate(backpacks.NAMES):
            print(f'backpack {i}: {name}')
        for i, (name, _, rgb, _, _) in enumerate(shirts.COLOURS):
            print(f'cloth colour {i}: {name} {rgb}')
        return
    data, report = build(args.model, args.alltim)
    with open(args.out, 'wb') as f:
        f.write(data)
    for line in report:
        print(line)
    print(f'{args.out}: {len(data)} bytes')


if __name__ == '__main__':
    main()
