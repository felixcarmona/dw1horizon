#!/usr/bin/env python3
"""TAMER.DAT: the tamer's other looks (bald and the hairstyles), made from the player's own disc.

  tamer_pack.py build OUT [--model BOYS.MMD] [--alltim ALLTIM.TIM]
  tamer_pack.py list

Look 0 is the original tamer and is not in the file: the game loads the disc's own model and texture for it.
Looks 1.. are tools/tamer_looks (bald, then the hairstyles). The file, in 2048-byte sectors, little endian:

  sector 0   "TLK1", u16 looks, u16 texture sector, u16 cold sector, u16 cold sectors, u16 colours
             0x10: per look u16 first sector, u16 sectors
             0x80: per hair colour r, g, b
  texture    the bald head's texture, one ALLTIM entry (9 sectors), shared by every look
  cold       the animations of COLD_SLOTS, the same for every look, laid out by tools/coldsplit.py
  models     one resident model per look

A look's model is larger than the original, and the tamer's buffer (TAMER_MMD_MAX) does not grow, so the
animations of COLD_SLOTS leave the model: their table entries become cold entries (COLD_ANIM_FLAG, as the partners')
and the game reads one into the last 4096 bytes of the buffer when it starts. The resident model therefore has to
fit in TAMER_MMD_MAX - 4096 bytes. The meshes are never simplified for that: more room means more cold slots.

Hair polygons are untextured and carry a grey level; the game multiplies it by the chosen colour when it loads the
model (updateTMDTextureData), so one model serves every colour.
"""
import argparse
import os
import struct
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import coldsplit  # noqa: E402
import mmd  # noqa: E402
import tamer_looks  # noqa: E402

SECTOR = 2048
TAMER_MMD_MAX = 0xE000          # include/dw/memmap.h
COLD_BUFFER = 0x1000            # the tail of the tamer's buffer (TAMER_COLD_BUFFER)
RESIDENT_MAX = TAMER_MMD_MAX - COLD_BUFFER
# Animations that leave the model: the ones only scenes start (13, 15-26: the engine itself never asks for them) and
# the gym's (9), which the game reads while the gym loads (modTamerColdPrefetch).
COLD_SLOTS = (9, 13) + tuple(range(15, 27))
HEAD = 1                        # the head's object in the tamer model
HAIR_MODE = 0x30                # untextured gouraud triangle
MODEL = os.path.join(mmd.EXTRACTED, 'CHDAT', 'MMD0', 'BOYS.MMD')
ALLTIM = mmd.ALLTIM

# Hair colours, in the order the game numbers them. A hair polygon shows colour * grey / 128.
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
        hair = d['mode'] == HAIR_MODE
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


def resident(model, nbones):
    """(resident model, cold part) of one look. Nothing is simplified to make it fit: a look that does not is an error."""
    slim_head(model)
    res, cold = coldsplit.split(model.build(), nbones, slots=COLD_SLOTS, buffer_bytes=COLD_BUFFER)
    if len(res) > RESIDENT_MAX:
        raise SystemExit(f'tamer look does not fit: {len(res)} > {RESIDENT_MAX} bytes')
    return res, cold


def pad(data):
    return data + b'\0' * (-len(data) % SECTOR)


def build(model_path, alltim_path):
    """(TAMER.DAT bytes, report lines)."""
    model = mmd.MMD.load(model_path, 0)
    texture, looks = tamer_looks.build(model, mmd.load_tim(alltim_path, 0))
    texture = texture.to_bytes()
    assert len(texture) == mmd.ALLTIM_STRIDE, len(texture)
    parts, cold_part, report = [], None, []
    for name, look in looks:
        res, cold = resident(look, model.nbones)
        assert cold_part in (None, cold), 'the cold animations differ between looks'
        cold_part = cold
        parts.append(pad(res))
        report.append(f'{name}: {len(res)} bytes resident ({RESIDENT_MAX - len(res)} spare)')
    header = bytearray(SECTOR)
    tex_sector = 1
    cold_sector = tex_sector + len(texture) // SECTOR
    cold_sectors = len(pad(cold_part)) // SECTOR
    struct.pack_into('<4s5H', header, 0, b'TLK1', len(parts), tex_sector, cold_sector, cold_sectors, len(COLOURS))
    sector = cold_sector + cold_sectors
    for i, part in enumerate(parts):
        struct.pack_into('<2H', header, 0x10 + 4 * i, sector, len(part) // SECTOR)
        sector += len(part) // SECTOR
    for i, (_, rgb) in enumerate(COLOURS):
        header[0x80 + 3 * i:0x83 + 3 * i] = bytes(rgb)
    report.append(f'cold animations: {len(cold_part)} bytes, {cold_sectors} sectors')
    return bytes(header) + texture + pad(cold_part) + b''.join(parts), report


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
        return
    data, report = build(args.model, args.alltim)
    with open(args.out, 'wb') as f:
        f.write(data)
    for line in report:
        print(line)
    print(f'{args.out}: {len(data)} bytes')


if __name__ == '__main__':
    main()
