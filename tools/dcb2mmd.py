#!/usr/bin/env python3
"""Digimon Digital Card Battle (PS1) battle models -> Digimon World MMDs.

The card game draws its Digimon with DW1-style models (rigid one-mesh-per-bone, same
units and axes, 4 bpp texture with per-face palettes). Its data is read with the `dcb`
package of $DCB_ROOT (docs/dw1-port.md there); everything DW1-side
is tools/mmdport.py. Documented in docs/mods/models.md, "Importing from Digimon
Digital Card Battle".

  dcb2mmd.py info ID                          bones, budgets, animations of F.DRV/ID.PAK
  dcb2mmd.py convert ID TYPE OUT_DIR [--slot ANIM=SLOT ...] [--tol 1]
                       OUT_DIR/<Name>.MMD (TMD + the 8 battle animations through glTF and
                       import-anim), <Name>.TIM (ALLTIM-style texture entry), <Name>.gltf,
                       <Name>.skeleton.json (the "bones" of a species definition)
  dcb2mmd.py partner SPEC.json OUT_DIR        a full partner animation set (mmdport.build_partner)
  dcb2mmd.py sheet ID OUT.png [--every 8]     the card game's own render of every animation

Conversion: DCB bone i -> DW1 bone i+1 (object i), bone 0 = the entity; a DCB pose
T(offset + t)·Ry·Rx·Rz·S is written as glTF TRS (quaternions) and import-anim turns it
into DW1's Rx·Ry·Rz Euler keys at 20 ticks/s (the card game runs 30). The model root's
translation stays on DW1 bone 1 (it does not move the entity) unless a clip says
otherwise. Default slots: anim_00 idle -> 0 and 0x21, anim_01..03 -> 0x2E..0x30,
anim_04 -> 0x28 (hit), anim_05 -> 0x2B (faint), anim_06 -> 0x2A (victory); anim_07 (the
entrance, which grows the model from scale 0) is not used.

Releases: the recipes are made from the USA disc. $DCB_DISC / $DCB_DRV (default $DCB_ROOT/disc and
$DCB_ROOT/drv) give the extracted disc and DRVs; the boot file tells the release. Digimon Digital Card
Battle (Europe) and Digital Card Arena (Japan) carry the same models; tools/dcbrelease.py checks them and
gives their executables' unpack routine.
The bundled player converter uses only the Python standard library. The packed animations are unpacked by dcb/unpack.py, the game's routine
rewritten in plain Python (no emulator, no executable).
"""

# Allow both direct script execution and package imports.
import sys as _image_sys
from pathlib import Path as _ImagePath
_image_sys.path.insert(0, str(next(p for p in _ImagePath(__file__).resolve().parents if (p / 'tools').is_dir())))
import argparse
import json
import os
import sys

DCB_ROOT = os.environ.get('DCB_ROOT', os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), 'digimoncardbattle'))
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)


def _dcb():
    sys.path.insert(0, DCB_ROOT)
    release()                           # rule: a disc of a known release (its models are checked in pak_path)
    import dcb.model, dcb.anim, dcb.pose  # noqa: E401
    return dcb


import mmdport  # noqa: E402

DEFAULT_SLOTS = {'anim_00': [0, 0x21], 'anim_01': [0x2E], 'anim_02': [0x2F], 'anim_03': [0x30],
                 'anim_04': [0x28], 'anim_05': [0x2B], 'anim_06': [0x2A]}


# boot file -> release. The recipes are made from the USA disc; another release is read with its own executable
# and only for models equal to the USA files (tools/dcbrelease.py).
RELEASES = {'SLUS_013.28': 'us', 'SLES_039.00': 'eu', 'SLPS_031.01': 'jp'}


def disc_dir():
    return os.environ.get('DCB_DISC', os.path.join(DCB_ROOT, 'disc'))


def drv_dir():
    return os.environ.get('DCB_DRV', os.path.join(DCB_ROOT, 'drv'))


def release():
    """(release, boot file) of the disc in disc_dir()."""
    cnf = open(os.path.join(disc_dir(), 'SYSTEM.CNF'), encoding='latin-1').read()
    boot = cnf.split('cdrom:')[1].lstrip('\\').split(';')[0].strip().upper()
    if boot not in RELEASES:
        raise SystemExit(f'dcb2mmd: {disc_dir()} boots {boot}, not a known Digimon Digital Card Battle release')
    return RELEASES[boot], boot


def pak_path(fid, drv='F'):
    path = os.path.join(drv_dir(), drv, f'{int(fid):03d}.PAK')
    rel = release()[0]
    if rel != 'us':
        import dcbrelease
        dcbrelease.check_model(rel, path, fid)
    return path


def card_name(fid):
    p = os.path.join(DCB_ROOT, 'out', 'battle', 'index.tsv')
    if os.path.exists(p):
        for line in open(p):
            f = line.rstrip('\n').split('\t')
            if f[0].split('_')[0] == f'{int(fid):03d}':
                return f[3]
    return f'dcb{int(fid):03d}'


def load(fid, log=print, max_palettes=16):
    """F.DRV/<fid>.PAK as an mmdport.Model. `max_palettes` > 16 lets a caller that merges
    palettes afterwards (tools/import_batch.py) receive models with more CLUT rows."""
    dcb = _dcb()
    import numeric as np
    m = dcb.model.parse_model(open(pak_path(fid), 'rb').read(), str(fid))
    tims = [t for t in m.textures if t.bpp == 4]
    if not tims:
        raise SystemExit(f'{fid}: no 4 bpp texture')
    tim = tims[0]
    ix, iy = tim.image_xy
    cx, cy = tim.clut_xy
    h, w = tim.pixels.shape
    vscale = 1.0
    if w > 256 or h > 256:
        raise SystemExit(f'{fid}: texture {w}x{h} does not fit the 256x128 slot')
    if h > 128:      # rule: rows below 128 that no face samples are dropped (Magnamon is 256x136)
        vmax = max((v - (iy - ((p.tpage >> 4) & 1) * 256) for b in m.bones for p in b.mesh.prims if p.uvs
                    for u, v in p.uvs), default=0)
        if vmax >= 128:         # rule: faces sample them: squash the rows to 128 (nearest) and scale V to match
            if h > 144:
                raise SystemExit(f'{fid}: texture {w}x{h} does not fit the 256x128 slot (faces use row {vmax})')
            log(f'  note: texture {w}x{h} squashed to 256x128 (nearest rows, V scaled by {128 / h:.3f})')
            vscale = 128.0 / h
            tim.pixels = tim.pixels[[min(h - 1, int(y / vscale)) for y in range(128)]]
            h = 128
        else:
            log(f'  note: texture {w}x{h}: rows 128+ are not sampled by any face, cropped to 256x128')
            h = 128
    # palettes: the CLUT rows the faces use, renumbered in VRAM order
    rows_used = sorted({m.vram.resolve_clut(p.clut) for b in m.bones for p in b.mesh.prims if p.uvs})
    if len(rows_used) > max_palettes:
        raise SystemExit(f'{fid}: {len(rows_used)} palettes, the slot has 16 CLUT rows')
    if len(rows_used) == 16:
        log('  note: 16 palettes: row 15 (the flat tournament sprite\'s) is used by the model')
    row_of = {c: k for k, c in enumerate(rows_used)}
    pals = [[int(x) for x in m.vram.words[y, x0:x0 + 16]] for (x0, y) in rows_used]
    idx = bytearray(256 * 128)
    pix = np.asarray(tim.pixels, np.uint8)
    for y in range(h):
        idx[y * 256:y * 256 + w] = bytes(pix[y])
    missing = sum(1 for b in m.bones for p in b.mesh.prims if p.uvs and p.clut not in m.vram.clut_rows)
    if missing:
        log(f'  note: {missing} faces point at CLUT rows the file does not carry (nearest row used)')
    bones = []
    for b in m.bones:
        prims = []
        for p in b.mesh.prims:
            px, py = (p.tpage & 15) * 64, ((p.tpage >> 4) & 1) * 256
            du, dv = (ix - px) * 4, iy - py
            uvs = [(u - du, (v - dv) * vscale) for u, v in p.uvs] if p.uvs else None
            prims.append(dict(verts=list(p.verts), norms=list(p.normals) if p.normals else None, uvs=uvs,
                              row=row_of[m.vram.resolve_clut(p.clut)] if p.uvs else 0, semi=bool(p.semi),
                              abr=(p.tpage >> 5) & 3, color=tuple(p.color)))
        bones.append(dict(parent=b.parent, offset=tuple(float(x) for x in b.offset), rest=mmdport.IDENTITY_Q,
                          verts=[tuple(v) for v in b.mesh.vertices], norms=[tuple(n) for n in b.mesh.normals],
                          prims=prims))
    anims = {}
    def convert_frames(fr):
        frames = []
        for f in fr:
            row = []
            for i, b in enumerate(m.bones):
                t, R, s = dcb.pose.local_trs(b, f[i])        # R = Ry·Rx·Rz (the card game's order)
                row.append((mmdport.quat_of_matrix(R.tolist()), tuple(float(x) for x in t),
                            tuple(float(x) for x in s)))
            frames.append(row)
        return frames
    for aid, raw in sorted(m.animations.items()):
        fr, ev, looped = dcb.anim.play(raw, len(m.bones))
        anims[f'anim_{aid:02d}'] = mmdport.Anim(lambda fr=fr: convert_frames(fr), 30.0, bool(looped))
    return mmdport.Model(card_name(fid), bones, idx, pals, anims)


def cmd_info(a):
    m = load(a.id)
    nv = sum(len(b['verts']) for b in m.bones)
    npr = sum(len(b['prims']) for b in m.bones)
    print(f'{a.id} {m.name}: {len(m.bones)} bones (+ the entity = {len(m.bones) + 1}), {nv} vertices, {npr} primitives, '
          f'{len(m.pals)} palettes, max {max(len(b["verts"]) for b in m.bones)} vertices per bone')
    for k, an in m.anims.items():
        print(f'  {k}: {len(an.frames)} ticks at 30 fps ({len(an.frames) * 20 / 30:.0f} DW1 ticks){" loop" if an.loop else ""}')


def cmd_convert(a):
    m = load(a.id)
    slots = dict(DEFAULT_SLOTS)
    for spec in a.slot or []:
        name, _, s = spec.partition('=')
        slots[name] = [int(x, 0) for x in s.split(',')] if s else []
    os.makedirs(a.out_dir, exist_ok=True)
    stem = os.path.join(a.out_dir, m.name)
    mmdport.convert(m, a.type, stem + '.MMD', stem + '.TIM', slots, stem + '.gltf', a.tol)
    json.dump(dict(bones=[list(x) for x in mmdport.skeleton(m)]), open(stem + '.skeleton.json', 'w'))
    print(f'{stem}.skeleton.json: {len(m.bones) + 1} bones')


def cmd_partner(a):
    spec = json.load(open(a.spec))
    m = load(spec['dcb'])
    if spec.get('meshfix') is not None:        # tools/meshfix.py: the mesh edits a batch spec records (same parameters, no search)
        import meshfix
        meshfix.apply(m, spec['meshfix'])
    os.makedirs(a.out_dir, exist_ok=True)
    stem = os.path.join(a.out_dir, spec.get('name', m.name))
    mmdport.build_partner(m, spec, stem + '.MMD', stem + '.TIM', a.out_dir)
    json.dump(dict(bones=[list(x) for x in mmdport.skeleton(m)]), open(stem + '.skeleton.json', 'w'))


def cmd_sheet(a):
    dcb = _dcb()
    import numpy as np  # developer preview uses the external renderer
    from tools.image import Image, ImageDraw
    from dcb.render import draw
    m = dcb.model.parse_model(open(pak_path(a.id), 'rb').read(), str(a.id))
    S, rows = a.size, []
    fit = (np.array([-a.fit, -1.6 * a.fit, -a.fit]), np.array([a.fit, 0.2 * a.fit, a.fit]))
    for aid, raw in sorted(m.animations.items()):
        fr, _, _ = dcb.anim.play(raw, len(m.bones))
        ims = []
        for t in range(0, len(fr), a.every):
            f = np.array(fr[t])
            if a.no_root:
                f[0, 3] = f[0, 5] = 0
            ims.append(draw(m, f, yaw_deg=a.yaw, size=S, fit=fit))
        rows.append((aid, ims))
    out = Image.new('RGB', (max(len(r[1]) for r in rows) * S, S * len(rows)), (40, 40, 40))
    d = ImageDraw.Draw(out)
    for i, (aid, ims) in enumerate(rows):
        for j, im in enumerate(ims):
            out.paste(im, (j * S, i * S))
            d.text((j * S + 2, i * S + S - 12), str(j * a.every), fill=(200, 200, 200))
        d.text((2, i * S + 2), f'anim_{aid:02d}', fill=(255, 255, 0))
    out.save(a.out)
    print(f'{a.out}: {len(rows)} animations')


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest='cmd', required=True)
    p = sub.add_parser('info'); p.add_argument('id', type=int); p.set_defaults(f=cmd_info)
    p = sub.add_parser('convert'); p.add_argument('id', type=int); p.add_argument('type', type=lambda s: int(s, 0))
    p.add_argument('out_dir'); p.add_argument('--slot', action='append', help='anim_NN=SLOT[,SLOT] (empty: not used)')
    p.add_argument('--tol', type=int, default=1); p.set_defaults(f=cmd_convert)
    p = sub.add_parser('partner'); p.add_argument('spec'); p.add_argument('out_dir'); p.set_defaults(f=cmd_partner)
    p = sub.add_parser('sheet'); p.add_argument('id', type=int); p.add_argument('out')
    p.add_argument('--every', type=int, default=8); p.add_argument('--size', type=int, default=150)
    p.add_argument('--yaw', type=float, default=30.0); p.add_argument('--fit', type=float, default=300.0)
    p.add_argument('--no-root', action='store_true'); p.set_defaults(f=cmd_sheet)
    a = ap.parse_args()
    a.f(a)


if __name__ == '__main__':
    main()
