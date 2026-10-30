#!/usr/bin/env python3
"""Which game to take each Digimon's model and animations from, per Digimon.

Reads docs/data/crossgame-models.csv (tools/crossgame.py: which games have each
Digimon and how their meshes relate), measures every candidate model against DW1's
limits (docs/mods/models.md) and writes docs/data/crossgame-sources.csv:

  section 'new'  every identified Digimon DW1 does not have: model_from, anims_from,
                 everyday_anims and the reason;
  section 'dw1'  DW1 Digimon whose same mesh in another game carries animations DW1's
                 own file lacks (a field walk, more battle animations).

Rules:

- fit: primitives <= 713, vertices <= 706 and vertices per piece <= 172 (identical
  positions counted once, as the importers store them), bones (+ the entity) <= 34,
  palettes <= 15 (16 accepted with a note: row 15 is the flat sprite's, as Puppetmon
  already ships), texture inside the 256x128 slot (DCB: TIM <= 256x128;
  DW2: its 128x256 page is cut in two 128x128 halves, so no face may cross row 128; DW2003: UVs in rows 0..127).
- model_from: of the games that have the Digimon and fit without loss (a texture
  that only has to be repacked into the slot counts as fitting), Card Battle first (DW1
  units, its importer), then DW2, then DW2003. When Card Battle and DW2 both fit and
  the meshes are not identical, the more complete one: DCB when it is an edit of DW2's
  mesh that adds at least as many pieces as it removes, else the one with more
  primitives; but DW2 when its version has its own field walk (DemiDevimon). When nothing fits: the game with the fewest failed limits, same order.
  Pocket Digimon World is measured but never chosen (its models are Card Battle's).
- anims_from: among the games whose mesh is identical to model_from's (so the pieces
  match by shape and the animations transfer), the one whose own animations fill the
  most DW1 partner slots (estimate in `slots`, below); ties keep model_from.
- everyday_anims: 'own-walk' when anims_from has a field idle/walk (DW2's city-walker
  bank D, 17 models), else 'borrowed'. Care animations (eat, sleep, poop, training)
  exist in none of the four games: they are always borrowed from a DW1 Digimon.

DW1 partner slots counted (all 64 partner MMDs have them): idle 0, 1, 0x21, 0x22;
walk/run/stroll 2, 3, 4; reactions 0x23, 0x24, 0x28, 0x2A (victory), 0x2B, 0x2C;
techniques 0x2E.. (up to 8); 20 care/field slots no other game covers.
What each game's animations are:
- DCB (and Pocket): 8, battle only: idle, 3 attacks, hit, faint, victory, entrance
  (tools/dcb2mmd.py).
- DW2 (from the decompilation, ref/DW2-PC): banks A..K; battle: A0 idle, B0 hit,
  C0-C2 knock-back hops, F0/G0/H0 the 3 technique casts, I0 the second action,
  J0 downed, K0 lying (stag3000/fighter.c); bank D, only on 17 models: the city
  walker's D0 idle, D1 walk, D2 turn/talk, D5 run (stag2000/walker.c).
- DW2003: slot meanings not decoded; slots 0/1 loop (idle), technique sequences in
  runs of slots >= 14; a looping slot whose root moves horizontally each cycle is
  counted as a run/walk candidate (the dash towards the target).

Usage (needs numpy + unicorn: the card-battle repo's venv):
  PY=$DCB_ROOT/.venv/bin/python
  $PY -I tools/crossgame_sources.py              # CSV + summary (metrics cached in build/crossgame/)
  $PY -I tools/crossgame_sources.py --reload     # re-measure every model
  $PY -I tools/crossgame_sources.py --import     # also fill imported/ (gitignored)
  $PY -I tools/crossgame_sources.py --import --mmd   # ...and convert with dcb2mmd/dw3mmd
"""
import argparse
import csv
import glob
import json
import os
import re
import shutil
import subprocess
import sys
from collections import Counter

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PROJ = os.path.dirname(ROOT)
DW2 = os.path.join(PROJ, 'digimonworld2')
DCB = os.path.join(PROJ, 'digimoncardbattle')
PDW = os.path.join(PROJ, 'digimonworldpocket')
DW3 = os.path.join(PROJ, 'digimonworld2003')
MODELS_CSV = os.path.join(ROOT, 'docs', 'data', 'crossgame-models.csv')
OUT_CSV = os.path.join(ROOT, 'docs', 'data', 'crossgame-sources.csv')
CACHE = os.path.join(ROOT, 'build', 'crossgame', 'metrics.json')
IMPORTED = os.path.join(ROOT, 'imported')

os.environ.setdefault('DCB_EXE', os.path.join(DCB, 'disc', 'SLUS_013.28'))
for p in (os.path.join(ROOT, 'tools'), DW2, DCB, PDW, DW3):
    if p not in sys.path:
        sys.path.append(p)

LIMITS = dict(prims=713, verts=706, max_piece=172, bones=34, palettes=15)
SCALE = dict(dcb=1.0, pdw=1.0, dw2=1 / 5.1, dw3=None)     # dw3: per model, from its height
DW3_DEFAULT_SCALE = 1 / 4.7
SHORT = {'dw1': 'DW1', 'dw2': 'DW2', 'pdw': 'Pocket', 'dcb': 'DCB', 'dw3': 'DW2003'}
GAME_OF = {v: k for k, v in SHORT.items()}
PREFERENCE = ['dcb', 'dw2', 'dw3']
TECH_MAX = 8
CARE_SLOTS = 20


# ---------------------------------------------------------------- measuring
_MEASURED = {}       # 'game:id' -> metrics, once measured (lets first_id skip unparsable files)


def ids_of(cell):
    """'136; 243 (boss variant)' -> ['136', '243']: plain ids first, then variants."""
    parts = [x.strip() for x in cell.split(';') if x.strip()]
    plain = [x for x in parts if '(' not in x]
    var = [x.split('(')[0].strip() for x in parts if '(' in x]
    return plain + var


def first_id(cell, game=None):
    """The model used for a game: the first plain id, else the first variant (Galacticmon's
    form 1); with `game`, the first one that parsed (GrapLeomon: M391GRPL is broken on the
    disc, its copy M456GRP9 is not)."""
    ids = ids_of(cell)
    if game:
        for i in ids:
            m = _MEASURED.get(f'{game}:{i}')
            if m is not None and 'error' not in m:
                return i
    return ids[0] if ids else None


def dw2_path(code):
    g = glob.glob(os.path.join(DW2, 'disc/AAA/4.AAA/MODEL/MODEL*', code + '.BIN'))
    return g[0] if g else None


def uniq(verts):
    """Vertices of a piece as the importers store them: identical positions once."""
    return len({tuple(v) for v in verts})


def measure_dw2(code):
    import numpy as np
    from dw2.model import load, world_matrices
    path = dw2_path(code)
    m = load(path)
    prims = [p for b in m.bones for p in b.prims]
    v_used = [v for p in prims for _, v in p.uvs]
    names = [f'{a.bank}{a.slot}' for a in m.animations]
    # the 128x256 page goes into the slot as two 128x128 halves: a face may not cross row 128
    straddle = sum(1 for p in prims if p.uvs and min(v for _, v in p.uvs) < 128 <= max(v for _, v in p.uvs))
    h = 0.0
    if m.animations:
        W = world_matrices(m, m.animations[0], 0)
        ys = [(np.array(b.vertices, float) @ W[b.index][:3, :3].T + W[b.index][:3, 3])[:, 1]
              for b in m.bones if b.vertices]
        h = float(-min(y.min() for y in ys)) if ys else 0.0
    return dict(prims=len(prims), quads=sum(len(p.verts) == 4 for p in prims),
                verts=sum(uniq(b.vertices) for b in m.bones), normals=sum(len(b.normals) for b in m.bones),
                max_piece=max(uniq(b.vertices) for b in m.bones), bones=len(m.bones) + 1,
                palettes=len({p.clut for p in prims}), tex_rows=(max(v_used) + 1) if v_used else 0,
                straddle=straddle, tex_fits=straddle == 0, height=round(h), anims=names,
                loops=[a.loop_to is not None for a in m.animations])


def measure_dcb(fid):
    import numpy as np
    from dcb.model import parse_model
    m = parse_model(open(os.path.join(DCB, 'drv/F', f'{fid}.PAK'), 'rb').read(), fid)
    tex_src, vram, tims = fid, m.vram, [t for t in m.textures if t.bpp == 4]
    if not tims and m.texture_name[:3].isdigit():
        tex_src = m.texture_name[:3]
        src = parse_model(open(os.path.join(DCB, 'drv/F', tex_src + '.PAK'), 'rb').read(), tex_src)
        vram, tims = src.vram, [t for t in src.textures if t.bpp == 4]
    prims = [p for b in m.bones for p in b.mesh.prims]
    tex = [p for p in prims if p.uvs]
    th, tw = tims[0].pixels.shape if tims else (0, 0)
    uv_rows = uv_cols = 0          # UVs relative to the image, as dcb2mmd places them in the slot
    if tims:
        ix, iy = tims[0].image_xy
        for p in tex:
            px, py = (p.tpage & 15) * 64, ((p.tpage >> 4) & 1) * 256
            uv_cols = max(uv_cols, max(u - (ix - px) * 4 for u, _ in p.uvs) + 1)
            uv_rows = max(uv_rows, max(v - (iy - py) for _, v in p.uvs) + 1)
    # rest pose: joints at the accumulated offsets, no rotation
    pos = {}

    def joint(i):              # parents can come after their children in the file
        if i not in pos:
            b = m.bones[i]
            pos[i] = np.array(b.offset, float) + (joint(b.parent) if b.parent >= 0 else 0)
        return pos[i]

    for b in m.bones:
        joint(b.index)
    ys = [np.array(b.mesh.vertices, float)[:, 1] + pos[b.index][1] for b in m.bones if b.mesh.vertices]
    return dict(prims=len(prims), quads=sum(len(p.verts) == 4 for p in prims),
                verts=sum(uniq(b.mesh.vertices) for b in m.bones),
                normals=sum(len(b.mesh.normals) for b in m.bones),
                max_piece=max(uniq(b.mesh.vertices) for b in m.bones), bones=len(m.bones) + 1,
                palettes=len({vram.resolve_clut(p.clut) for p in tex}), tex_rows=int(th), tex_width=int(tw),
                tex_fits=bool(tims) and th <= 128 and tw <= 256 and uv_rows <= 128 and uv_cols <= 256,
                uv_rows=int(uv_rows), tex_from=tex_src,
                missing_clut=sum(1 for p in tex if p.clut not in vram.clut_rows),
                height=round(float(-min(y.min() for y in ys))) if ys else 0,
                anims=[f'anim_{k:02d}' for k in sorted(m.animations)], loops=[])


def measure_dw3(code):
    import numpy as np
    import dw3_extra; dw3_extra.patch()   # empty section slots
    from dw3.model import parse_model
    from dw3.pose import animation_frames, sample, world_matrices
    m = parse_model(open(os.path.join(DW3, 'disc/AAA/DAT/FIGHT/MODEL', code + '.BIN'), 'rb').read(), code)
    prims = [p for b in m.bones for p in b.mesh.prims]
    tex = [p for p in prims if p.uvs]
    rows = [p.material[2] + v for p in tex for _, v in p.uvs]
    cols = [(p.material[0] | p.material[1] << 8) + u for p in tex for u, _ in p.uvs]
    f0 = animation_frames(m.animations[0])[0] if m.animations else 0
    W = world_matrices(m, f0, unit_scale=True)
    ys = [(np.array(b.mesh.vertices, float) @ W[b.index - 1][:3, :3].T + W[b.index - 1][:3, 3])[:, 1]
          for b in m.bones if b.mesh.vertices]
    h = float(-min(y.min() for y in ys)) if ys else 0.0
    roots = [b for b in m.bones if b.parent == 0]
    loco = []
    for a in m.animations:
        fr = animation_frames(a)
        if not a.loop or not fr or not roots:
            continue
        t0, t1 = sample(roots[0].translation, fr[0]), sample(roots[0].translation, fr[-1])
        if h and np.hypot(t1[0] - t0[0], t1[2] - t0[2]) > 0.04 * h:
            loco.append(a.slot)
    return dict(prims=len(prims), quads=sum(len(p.verts) == 4 for p in prims),
                verts=sum(uniq(b.mesh.vertices) for b in m.bones), normals=sum(len(b.mesh.normals) for b in m.bones),
                max_piece=max(uniq(b.mesh.vertices) for b in m.bones), bones=len(m.bones) + 1,
                palettes=len({(p.material[3], p.material[4]) for p in tex}),
                tex_rows=(max(rows) + 1) if rows else 0,
                tex_fits=m.texture is not None and (not rows or (max(rows) <= 127 and max(cols) <= 255)),
                has_texture=m.texture is not None, height=round(h),
                anims=[f'anim_{a.slot:02d}' for a in m.animations], loops=[bool(a.loop) for a in m.animations],
                loco=loco)


def measure_pdw_index():
    out = {}
    p = os.path.join(PDW, 'out', 'index.tsv')
    for r in csv.DictReader(open(p), delimiter='\t'):
        if r['drv'] == 'F' and r['status'] == 'ok':
            out[r['model']] = dict(bones=int(r['bones']) + 1, tris=int(r['triangles']),
                                   anims=[f'anim_{k:02d}' for k in range(int(r['animations'] or 0))])
    return out


MEASURE = dict(dw2=measure_dw2, dcb=measure_dcb, dw3=measure_dw3)


def metrics(rows, reload=False):
    cache = {}
    if os.path.exists(CACHE) and not reload:
        cache = json.load(open(CACHE))
    pdw = None
    changed = False
    for r in rows:
        for g in ('dw2', 'dcb', 'dw3', 'pdw'):
            for mid in ids_of(r[g]):
                k = f'{g}:{mid}'
                if k not in cache:
                    if g == 'pdw':
                        pdw = pdw or measure_pdw_index()
                        cache[k] = pdw.get(mid, dict(error='not in index'))
                    else:
                        try:
                            cache[k] = MEASURE[g](mid)
                        except Exception as ex:          # DW2003's 5 files with a broken hierarchy
                            cache[k] = dict(error=f'{ex.__class__.__name__}: {ex}')
                    changed = True
                if 'error' not in cache[k]:
                    break
    if changed:
        os.makedirs(os.path.dirname(CACHE), exist_ok=True)
        json.dump(cache, open(CACHE, 'w'))
    _MEASURED.update(cache)
    return cache


def dw1_anims():
    """DW1 code -> (distinct animations, used slots)."""
    import mmd
    e = mmd.exe()
    out = {}
    for p in mmd.all_mmds():
        code = os.path.basename(p)[:-4]
        m = mmd.MMD.load(p, e.names.index(code))
        used = [i for i, x in enumerate(m.anims.table) if x is not None]
        out[code] = (len({m.anims.table[i] for i in used}), used)
    return out


# ---------------------------------------------------------------- judging
def scale_of(g, m):
    return round(SCALE[g] or DW3_DEFAULT_SCALE, 4)


def tmd_bytes(m):
    """TMD size estimate (models.md § 6: 36 per quad, 28 per triangle, 8 per vertex and normal);
    the partner buffer (0x18800 = 100 352) also has to hold the animations."""
    q = m.get('quads', 0)
    return 36 * q + 28 * (m.get('prims', 0) - q) + 8 * (m.get('verts', 0) + m.get('normals', 0))


def fit_text(fails, m):
    if [x for x in fails if x != 'texture']:
        return 'no'
    notes = (['texture to repack'] if fails else []) + \
        (['16 palettes (row 15, the flat sprite\'s)'] if m.get('palettes') == 16 else [])
    return ', '.join(['yes'] + notes)


def failures(g, m):
    if 'error' in m:
        return ['not parsed']
    f = [k for k, lim in LIMITS.items() if m.get(k, 0) > lim and not (k == 'palettes' and m[k] == 16)]
    if not m.get('tex_fits', True):
        f.append('texture' if m.get('has_texture', True) else 'no texture')
    return f


def kinds(g, m):
    """(what the animations are, DW1 partner slots they fill, has a field walk, usable animations).
    Slots: idle 0/1/0x21/0x22 (4), reactions 0x23/0x24/0x28/0x2A/0x2B/0x2C (up to 6),
    techniques 0x2E.. (up to 8), walk/stroll 2/4 and run 3."""
    a = m.get('anims', [])
    if g in ('dcb', 'pdw'):
        n = len(a)
        tech = min(3, max(0, n - 5))
        slots = (4 + 5 + tech) if n >= 7 else min(n, 4)       # hit 0x23/0x28, faint 0x24/0x2B, victory 0x2A
        return (f'battle only: idle, {tech} attacks, hit, faint, victory, entrance (unused)', slots, False,
                max(0, n - 1))
    if g == 'dw2':
        bank = Counter(x[0] for x in a)
        d = sorted(x for x in a if x[0] == 'D')
        walk = 'D1' in d
        tech = sum(bank[c] for c in 'FGH')
        react = 2 * bool(bank['B']) + bool(bank['C']) + bool(bank['J']) + bool(bank['K'])   # no victory
        slots = 4 + react + min(TECH_MAX, tech) + (2 if walk else 0) + (1 if 'D5' in d else 0)
        txt = (f'battle: idle, hit, {bank["C"]} knock-backs, {tech} technique casts, second action, downed, '
               'lying; no victory')
        if d:
            txt += f'; field (city walker): {" ".join(d)}' + (' = idle, walk, turn, run' if walk else '')
        return txt, slots, walk, len(a)
    if g == 'dw3':
        slots_n = sorted(int(x[5:]) for x in a)
        runs, prev = 0, None
        for s in slots_n:
            if 14 <= s < 44 and (prev is None or s != prev + 1):
                runs += 1
            if 14 <= s < 44:
                prev = s
        loco = m.get('loco', [])
        reactions = 5 if len(a) >= 8 else 2
        slots = 4 + reactions + min(TECH_MAX, max(runs, 1)) + (1 if loco else 0)
        txt = (f'battle (slots not decoded): {sum(m.get("loops", []))} loops, ~{max(runs, 1)} technique sequences'
               + (f', looping dash in slot {",".join(map(str, loco))} (run candidate)' if loco else ''))
        return txt, slots, False, len(a)
    return '', 0, False, 0


def identical(rel):
    return rel in ('reference',) or rel.startswith('identical')


def rel_between(row, g1, g2):
    """Mesh relation between two games' models of one row (both compared to `reference`)."""
    ref = GAME_OF.get(row['reference'], row['reference'].lower())
    r1, r2 = row.get('rel_' + g1, '—'), row.get('rel_' + g2, '—')
    if g1 == g2:
        return 'same'
    if g1 == ref:
        return r2
    if g2 == ref:
        return r1
    if identical(r1) and identical(r2):
        return 'identical (via the reference)'
    return 'unknown'


def pieces_added_removed(rel):
    a = re.search(r'\+(\d+)', rel)
    r = re.search(r'-(\d+)', rel)
    return (int(a.group(1)) if a else 0), (int(r.group(1)) if r else 0)


def choose(row, M):
    have = {g: M[f'{g}:{first_id(row[g], g)}'] for g in PREFERENCE if first_id(row[g], g)}
    if not have:
        return None
    fails = {g: failures(g, m) for g, m in have.items()}
    lossy = {g: [x for x in f if x != 'texture'] for g, f in fails.items()}
    fit = [g for g in PREFERENCE if g in have and not lossy[g]]     # a texture repack loses nothing
    reason = []
    if fit:
        model = fit[0]
        if 'dcb' in fit and 'dw2' in fit:
            rel = rel_between(row, 'dcb', 'dw2')
            if not identical(rel) and rel != 'identical (via the reference)':
                add, rem = pieces_added_removed(rel)
                if kinds('dw2', have['dw2'])[2]:
                    model = 'dw2'
                    reason.append(f'DCB and DW2 fit, meshes {rel.split(" ")[0]}: DW2, whose version has its own '
                                  'field walk (city-walker bank D)')
                elif rel.startswith('modified') and add >= rem:
                    model = 'dcb'
                    reason.append(f'DCB and DW2 fit; DCB is DW2\'s mesh {rel}: DCB (native units)')
                else:
                    model = 'dcb' if have['dcb']['prims'] >= have['dw2']['prims'] else 'dw2'
                    reason.append(f'DCB and DW2 fit, meshes {rel.split(" ")[0]}: the more detailed '
                                  f'({have[model]["prims"]} primitives)')
            else:
                reason.append('DCB and DW2 fit, same mesh: DCB (native units, its importer)')
        elif len(fit) > 1:
            reason.append(f'fits as-is; preferred over {", ".join(SHORT[g] for g in fit if g != fit[0])}')
        else:
            reason.append('the only version that fits' if len(have) > 1 else 'the only version')
        skipped = [f'{SHORT[g]} ({", ".join(lossy[g])})' for g in PREFERENCE if g in have and lossy[g]]
        if skipped:
            reason.append('not fitting: ' + '; '.join(skipped))
        if 'texture' in fails[model]:
            reason.append('texture to repack into the 256x128 slot')
    else:
        model = min((g for g in PREFERENCE if g in have and 'not parsed' not in fails[g]),
                    key=lambda g: (len(lossy[g]), PREFERENCE.index(g)), default=None)
        if model is None:
            return None
        reason.append('nothing fits without loss; fewest limits over: ' +
                      '; '.join(f'{SHORT[g]} ({", ".join(fails[g])})' for g in PREFERENCE if g in have))
    # animations
    cand = {}
    for g in ('dcb', 'dw2', 'dw3'):
        if g not in have or 'error' in have[g]:
            continue
        rel = rel_between(row, model, g)
        if g == model or identical(rel) or rel == 'identical (via the reference)':
            cand[g] = kinds(g, have[g])
    best = max(cand, key=lambda g: (cand[g][1], cand[g][3], g == model))
    if best != model:
        reason.append(f'animations from {SHORT[best]} (same mesh; {cand[best][1]} vs {cand[model][1]} DW1 slots, '
                      f'{cand[best][3]} vs {cand[model][3]} usable animations)')
    return dict(model=model, anims=best, fails=fails, have=have, cand=cand, reason='; '.join(reason))


COLUMNS = ['section', 'name', 'model_from', 'model_id', 'fits', 'over_limits', 'tmd_bytes', 'scale', 'height_dw1',
           'anims_from', 'anims_id', 'everyday_anims', 'dw1_slots_own', 'anims_n', 'anim_kinds',
           'fidelity', 'reason'] + \
    [f'{g}_{k}' for g in ('dcb', 'dw2', 'dw3') for k in
     ('id', 'prims', 'verts', 'max_piece', 'palettes', 'tex_rows', 'bones', 'height', 'anims', 'fits')] + \
    ['pdw_id', 'pdw_anims']


def game_cols(row, M):
    out = {}
    for g in ('dcb', 'dw2', 'dw3'):
        mid = first_id(row[g], g)
        m = M.get(f'{g}:{mid}', {}) if mid else {}
        out[f'{g}_id'] = mid or ''
        for k in ('prims', 'verts', 'max_piece', 'palettes', 'tex_rows', 'bones', 'height'):
            out[f'{g}_{k}'] = m.get(k, '')
        out[f'{g}_anims'] = len(m.get('anims', [])) if m else ''
        out[f'{g}_fits'] = ('yes' if not failures(g, m) else 'no: ' + ', '.join(failures(g, m))) if m else ''
    pid = first_id(row['pdw'], 'pdw')
    out['pdw_id'] = pid or ''
    out['pdw_anims'] = len(M.get(f'pdw:{pid}', {}).get('anims', [])) if pid else ''
    return out


def build(rows, M, dw1):
    out, skipped = [], []
    for row in rows:
        if row['dw1']:
            continue
        if row['name'].startswith('?'):
            skipped.append(row['name'])
            continue
        c = choose(row, M)
        if c is None:
            skipped.append(row['name'])
            continue
        g, a = c['model'], c['anims']
        m = c['have'][g]
        kind, slots, walk, _ = c['cand'][a]
        out.append(dict(section='new', name=row['name'], model_from=SHORT[g], model_id=first_id(row[g], g),
                        fits=fit_text(c['fails'][g], m),
                        over_limits=', '.join(c['fails'][g]), tmd_bytes=tmd_bytes(m),
                        scale=scale_of(g, m), height_dw1=round(m.get('height', 0) * scale_of(g, m)),
                        anims_from=SHORT[a], anims_id=first_id(row[a], a),
                        everyday_anims='own-walk' if walk else 'borrowed', dw1_slots_own=slots,
                        anims_n=len(c['have'][a].get('anims', [])), anim_kinds=kind,
                        fidelity=f'{SHORT[g]} vs {row["reference"]}: {row["rel_" + g]}'
                        + (f', texture {row["tex_" + g]}' if row['rel_' + g] not in ('reference', '—') else ''),
                        reason=c['reason']) | game_cols(row, M))
    # section 2: DW1 Digimon with more animations elsewhere (same or modified mesh)
    for row in rows:
        if not row['dw1']:
            continue
        code = first_id(row['dw1'])
        n1, used = dw1.get(code, (0, []))
        best = None
        for g in ('dw2', 'dw3', 'dcb'):
            mid = first_id(row[g], g)
            rel = row['rel_' + g]
            if not mid or not (identical(rel) or rel.startswith('modified')):
                continue
            m = M.get(f'{g}:{mid}', {})
            if 'error' in m:
                continue
            kind, slots, walk, _ = kinds(g, m)
            n = len(m.get('anims', []))
            extra = (walk and 2 not in used) or n > n1
            if extra and (best is None or (walk, identical(rel), n) > (best[3], identical(best[5]), best[4])):
                best = (g, kind, slots, walk, n, rel)
        if not best:
            continue
        g, kind, slots, walk, n, rel = best
        why = []
        if walk:
            why.append('a field idle/walk (DW2 city walker) DW1\'s file lacks' if 2 not in used
                       else 'also a field idle/walk (DW2 city walker)')
        if n > n1:
            why.append(f'{n} animations vs {n1} distinct in DW1 {code}')
        out.append(dict(section='dw1', name=row['name'], model_from='DW1', model_id=code, fits='yes',
                        over_limits='', tmd_bytes='', scale=1.0, height_dw1='', anims_from=SHORT[g], anims_id=first_id(row[g], g),
                        everyday_anims='own' if 2 in used else ('own-walk' if walk else 'borrowed'),
                        dw1_slots_own=len(used), anims_n=n, anim_kinds=kind,
                        fidelity=f'{SHORT[g]} vs DW1: {rel}',
                        reason='; '.join(why) + ('' if identical(rel) else ' (modified mesh: retarget by the shared pieces)'))
                   | game_cols(row, M))
    return out, skipped


# ---------------------------------------------------------------- imported/
def files_for(g, mid):
    """(model glb, preview png, raw files) of one model in its repo."""
    if g == 'dw2':
        raw = dw2_path(mid)
        banks = sorted(glob.glob(os.path.join(os.path.dirname(raw), f'[A-K]{mid[1:]}.BIN'))) if raw else []
        return (os.path.join(DW2, 'out/models', mid + '.glb'), os.path.join(DW2, 'out/models/preview', mid + '.png'),
                ([raw] if raw else []) + banks)
    if g == 'dcb':
        glb = (glob.glob(os.path.join(DCB, 'out/battle', f'{mid}_*.glb')) or [''])[0]
        prev = (glob.glob(os.path.join(DCB, 'out/battle/preview', f'{mid}_*.png')) or [''])[0]
        return glb, prev, [os.path.join(DCB, 'drv/F', mid + '.PAK')]
    if g == 'dw3':
        return (os.path.join(DW3, 'out/fight', mid + '.glb'), os.path.join(DW3, 'out/fight/preview', mid + '.png'),
                [os.path.join(DW3, 'disc/AAA/DAT/FIGHT/MODEL', mid + '.BIN')])
    raise ValueError(g)


def copy(src, dst_dir, name=None):
    if src and os.path.exists(src):
        dst = os.path.join(dst_dir, name or os.path.basename(src))
        if not os.path.exists(dst) or os.path.getmtime(dst) < os.path.getmtime(src):
            shutil.copy2(src, dst)
        return os.path.basename(dst)
    return None


def safe(name):
    return re.sub(r'[^A-Za-z0-9._-]+', '_', name)


def convert_mmd(r, d, M):
    """dcb2mmd/dw3mmd convert into d/mmd/ (placeholder type 250). Returns a status string."""
    g, mid = GAME_OF[r['model_from']], r['model_id']
    if r['fits'] == 'no':
        return 'skipped: does not fit as-is'
    if r['over_limits']:
        return 'skipped: texture to repack by hand first'
    out = os.path.join(d, 'mmd')
    if glob.glob(os.path.join(out, '*.MMD')):
        return 'done'
    if g == 'dcb':
        cmd = [sys.executable, '-I', os.path.join(ROOT, 'tools', 'dcb2mmd.py'), 'convert', mid, '250', out]
    elif g == 'dw3':
        cmd = [sys.executable, '-I', os.path.join(ROOT, 'tools', 'dw3mmd.py'), 'convert', mid, '250', out,
               '--height', str(r['height_dw1'] or 300)]
    else:
        return 'skipped: no DW2 importer yet'
    try:
        p = subprocess.run(['nice', '-n', '15'] + cmd, capture_output=True, text=True, timeout=600)
    except subprocess.TimeoutExpired:
        return 'failed: timeout'
    if p.returncode or not glob.glob(os.path.join(out, '*.MMD')):
        msg = (p.stderr or p.stdout).strip().splitlines()
        shutil.rmtree(out, ignore_errors=True)
        return 'failed: ' + (msg[-1] if msg else f'exit {p.returncode}')
    return 'done'


def mmd_size(d):
    f = glob.glob(os.path.join(d, 'mmd', '*.MMD'))
    return os.path.getsize(f[0]) if f else ''


def fill_imported(out, M, mmd=False):
    os.makedirs(IMPORTED, exist_ok=True)
    index = []
    for r in out:
        if r['section'] != 'new':
            continue
        d = os.path.join(IMPORTED, safe(r['name']))
        os.makedirs(d, exist_ok=True)
        g, mid = GAME_OF[r['model_from']], r['model_id']
        glb, prev, raw = files_for(g, mid)
        tag = r['model_from']
        info = dict(name=r['name'], model=dict(game=tag, id=mid, files=[], metrics=M[f'{g}:{mid}']),
                    choice={k: r[k] for k in ('model_from', 'anims_from', 'everyday_anims', 'fits', 'over_limits',
                                              'scale', 'height_dw1', 'dw1_slots_own', 'anim_kinds', 'fidelity')},
                    reason=r['reason'], previews=[])
        info['model']['files'] = [x for x in [copy(glb, d, f'{tag}_{os.path.basename(glb)}')] +
                                  [copy(x, d, f'{tag}_raw_{os.path.basename(x)}') for x in raw] if x]
        if g == 'dcb' and M[f'dcb:{mid}'].get('tex_from', mid) != mid:      # a variant: its texture's PAK too
            src = os.path.join(DCB, 'drv/F', M[f'dcb:{mid}']['tex_from'] + '.PAK')
            info['model']['files'].append(copy(src, d, f'{tag}_raw_texture_{os.path.basename(src)}'))
        info['previews'].append(copy(prev, d, f'{tag}_{os.path.basename(prev)}'))
        # every other game's preview, to compare
        for og in ('dcb', 'dw2', 'dw3'):
            oid = r.get(f'{og}_id')
            if og != g and oid:
                p2 = files_for(og, oid)[1]
                info['previews'].append(copy(p2, d, f'{SHORT[og]}_{os.path.basename(p2)}'))
        if r['anims_from'] != r['model_from']:
            ag, aid = GAME_OF[r['anims_from']], r['anims_id']
            aglb = files_for(ag, aid)[0]
            info['anims'] = dict(game=r['anims_from'], id=aid, metrics=M[f'{ag}:{aid}'],
                                 files=[copy(aglb, d, f'{r["anims_from"]}_anims_{os.path.basename(aglb)}')])
            if ag == 'dw2':      # the raw animation banks
                info['anims']['files'] += [copy(x, d, f'DW2_raw_{os.path.basename(x)}') for x in files_for(ag, aid)[2]]
        info['previews'] = [x for x in info['previews'] if x]
        if mmd:
            info['mmd'] = convert_mmd(r, d, M)
            if info['mmd'] == 'done':
                info['mmd_bytes'] = mmd_size(d)
                info['mmd_note'] = ('mmd/: `convert` output, type 250 as a placeholder (skeleton in '
                                    '*.skeleton.json), the source\'s battle clips at full length in the default '
                                    'slots and tol 1: usually over PARTNER_MODEL_BUFFER (100 352 bytes); a partner '
                                    'is rebuilt with `partner SPEC.json` (cut clips, tol 6)')
            print(f'{r["name"]}: mmd {info["mmd"]}', flush=True)
        elif os.path.exists(os.path.join(d, 'info.json')):
            old = json.load(open(os.path.join(d, 'info.json')))
            for k in ('mmd', 'mmd_note', 'mmd_bytes'):
                if k in old:
                    info[k] = old[k]
        json.dump(info, open(os.path.join(d, 'info.json'), 'w'), indent=1)
        index.append([r['name'], safe(r['name']), r['model_from'], mid, r['anims_from'], r['anims_id'],
                      r['fits'], r['everyday_anims'], info.get('mmd', ''), info.get('mmd_bytes', '')])
    with open(os.path.join(IMPORTED, 'index.tsv'), 'w') as f:
        f.write('name\tfolder\tmodel_from\tmodel_id\tanims_from\tanims_id\tfits\teveryday_anims\tmmd\tmmd_bytes\n')
        for x in index:
            f.write('\t'.join(map(str, x)) + '\n')
    with open(os.path.join(IMPORTED, 'README.md'), 'w') as f:
        f.write(README)


README = """# imported/ (not tracked: copyrighted game data)

The final material picked for every Digimon DW1 does not have, one folder per
Digimon, made by `tools/crossgame_sources.py --import [--mmd]` from the sister
repos (read only). The choice and its reasons: `docs/data/crossgame-sources.csv`
(written by this tool).
Re-running the tool updates the folders; it never deletes anything.

Per folder:
- `<GAME>_*.glb`: the chosen model as its repo exports it (skinned glTF with
  every animation of that game; for viewing, not for import).
- `<GAME>_raw_*`: the file(s) on the source disc the model came from (DW2: the
  model `M*.BIN` and its animation banks `A..K*.BIN`; Card Battle: `F.DRV`'s
  `NNN.PAK`, plus the PAK that holds the texture for variants; DW2003:
  `FIGHT/MODEL/M*.BIN`). These are what `tools/dcb2mmd.py` / `tools/dw3mmd.py` read.
- `<GAME>_anims_*.glb` (and DW2's raw banks): the animation source, when it is a
  different game from the model (same mesh).
- `<GAME>_*.png`: the repos' previews of every version, to compare.
- `info.json`: game, file ids, metrics, the choice and the reason.
- `mmd/` (when made with `--mmd`): the DW1 `.MMD`, `.TIM` texture entry, glTF and
  `skeleton.json` from `dcb2mmd.py convert` / `dw3mmd.py convert`, with type 250
  as a placeholder and the converter's default slots. These carry the source's
  battle clips at full length with tol 1, so most are over the partner buffer
  (0x18800 = 100 352 bytes; `mmd_bytes` in index.tsv): NPC/wild size at best. A
  partner is rebuilt with `partner SPEC.json` (cut clips, tol 6), and a real
  species still needs its type and data.

`index.tsv` lists the folders.
"""


# ---------------------------------------------------------------- main
def summary(out, skipped):
    new = [r for r in out if r['section'] == 'new']
    print(f'new Digimon: {len(new)} (skipped {len(skipped)} unidentified/unmeasurable)')
    print('  model_from:', dict(Counter(r['model_from'] for r in new)))
    print('  fits:', dict(Counter((r['model_from'], 'no' if r['fits'] == 'no' else
                                   'repack' if 'repack' in r['fits'] else 'yes') for r in new)))
    print('  anims_from:', dict(Counter(r['anims_from'] for r in new)))
    print('  anims_from != model_from:', sum(r['anims_from'] != r['model_from'] for r in new),
          dict(Counter(f'{r["model_from"]}->{r["anims_from"]}' for r in new if r['anims_from'] != r['model_from'])))
    print('  everyday_anims:', dict(Counter(r['everyday_anims'] for r in new)))
    old = [r for r in out if r['section'] == 'dw1']
    print(f'DW1 Digimon with more animations elsewhere: {len(old)}', dict(Counter(r['anims_from'] for r in old)),
          'with a field walk:', sum('walk' in r['anim_kinds'] for r in old))


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--reload', action='store_true', help='re-measure every model')
    ap.add_argument('--import', dest='imp', action='store_true', help='fill imported/')
    ap.add_argument('--mmd', action='store_true', help='with --import: convert with dcb2mmd/dw3mmd')
    a = ap.parse_args()
    rows = list(csv.DictReader(open(MODELS_CSV)))
    M = metrics(rows, a.reload)
    out, skipped = build(rows, M, dw1_anims())
    with open(OUT_CSV, 'w', newline='') as f:
        w = csv.DictWriter(f, COLUMNS, lineterminator='\n')
        w.writeheader()
        w.writerows(out)
    summary(out, skipped)
    if a.imp:
        fill_imported(out, M, a.mmd)


if __name__ == '__main__':
    main()
