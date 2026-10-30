#!/usr/bin/env python3
"""Which Digimon models are the same mesh across five PS1 games.

Loads every Digimon battle/character model of Digimon World 1 (this repo),
Digimon World 2, Pocket Digimon World, Digimon Digital Card Battle and Digimon
World 2003 through each sister repo's own parser, and compares them by SHAPE:

- pieces: the rigid one-mesh-per-bone parts, as a multiset of vertex counts
  (duplicate vertex positions merged, since games split vertices at seams
  differently; pieces with fewer than 4 vertices ignored);
- triangles: total, a quad counting as 2 (reported, not used to classify);
- shape: per piece, the sorted pairwise vertex distances divided by their RMS
  (scale invariant), resampled to 64 quantiles; two pieces with the same vertex
  count match when the median relative difference of those quantiles is below
  SHAPE_TOL (3 %) plus ROUNDING game units of integer rounding. Pieces are paired
  greedily, best first, inside each vertex count; the vertex-weighted median size
  ratio of the pairs is the model's scale (DW2 ~5.1x, DW2003 ~4.7x DW1, card game
  and Pocket 1x) and a second pass pairs again requiring it (within SCALE_TOL),
  so look-alike pieces of graduated sizes pair correctly. Pieces left over that
  have the same vertex count and shape at another size are "rescaled" (DW2 and
  DW2003 store some pieces at another scale and scale them in the bone matrix).

  identical   every piece of both models paired ("(N pieces rescaled)" if any)
  modified    paired pieces hold at least half of each model's vertices and are
              at least half of the larger piece count; the text says how many
              were added (+), removed (-) and changed (~: unpaired on both sides)
  different   otherwise

Texture: the mean colour of each piece's texels, sampled under its UV triangles
(4 points per triangle, weighted by UV area) through the palette each face uses,
compared between paired pieces. This does not depend on how each game lays out
its texture page and tells recolours apart. "same" when the vertex-weighted
median RGB distance is <= TEX_SAME and under TEX_FAR_SHARE of the paired
vertices are further than TEX_FAR; only paired pieces are compared, so on a
"modified" model the remade pieces are not. "—" when a model has no texture,
"n/a" when the meshes are different (nothing to pair).

Usage (needs numpy + OpenCV + unicorn: the card-battle repo's venv has them):
  PY=/path/to/developer-venv/bin/python
  $PY -I tools/crossgame.py                 # table + doc data (uses build/crossgame/models.pkl)
  $PY -I tools/crossgame.py --reload        # re-parse every model (~30 s)
  $PY -I tools/crossgame.py --spot DIR      # side-by-side previews for the spot check
Writes docs/data/crossgame-models.csv and prints the summary used in
docs/reference/imported-species.md."""

# Allow both direct script execution and package imports.
import sys as _image_sys
from pathlib import Path as _ImagePath
_image_sys.path.insert(0, str(next(p for p in _ImagePath(__file__).resolve().parents if (p / 'tools').is_dir())))
import argparse
import csv
import glob
import math
import json
import os
import pickle
import random
import struct
import sys
from collections import Counter, defaultdict

import numpy as np

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PROJ = os.path.dirname(ROOT)
DW2 = os.path.join(PROJ, 'digimonworld2')
DCB = os.path.join(PROJ, 'digimoncardbattle')
PDW = os.path.join(PROJ, 'digimonworldpocket')
DW3 = os.path.join(PROJ, 'digimonworld2003')
CACHE = os.path.join(ROOT, 'build', 'crossgame', 'models.pkl')
CSV_OUT = os.path.join(ROOT, 'docs', 'data', 'crossgame-models.csv')
IDENT_CSV = os.path.join(ROOT, 'docs', 'data', 'crossgame-identified.csv')   # names of models the codes don't give

GAMES = ['dw1', 'dw2', 'pdw', 'dcb', 'dw3']
GAME_NAME = {'dw1': 'Digimon World', 'dw2': 'Digimon World 2', 'pdw': 'Pocket Digimon World',
             'dcb': 'Digimon Digital Card Battle', 'dw3': 'Digimon World 2003'}
SHAPE_TOL = 0.03       # median relative error of a piece's distance quantiles
SCALE_TOL = 0.05       # spread allowed in the size ratio of matched pieces
MIN_VERTS = 4
ROUNDING = 1.5         # game units of integer rounding, added to SHAPE_TOL relative to the piece size
TEX_FAR, TEX_FAR_SHARE = 45, 0.12   # ...and under 12 % of it (by vertices) further than 45
TEX_SAME = 20          # median RGB distance of the matched pieces' mean colours

os.environ.setdefault('DCB_EXE', os.path.join(DCB, 'disc', 'SLUS_013.28'))
for p in (os.path.join(ROOT, 'tools'), DW2, DCB, PDW, DW3):
    if p not in sys.path:
        sys.path.append(p)

# ---------------------------------------------------------------- model records
# A record: dict(game, file, code, pieces=[float32 (n,3)], tris, prims, hist (512,) float, textured)

BARY = np.array([[1 / 3, 1 / 3, 1 / 3], [2 / 3, 1 / 6, 1 / 6], [1 / 6, 2 / 3, 1 / 6], [1 / 6, 1 / 6, 2 / 3]])


class TexSampler:
    """Accumulates texel colours under UV triangles into a 512-bin histogram."""

    def __init__(self):
        self.hist = np.zeros(512)
        self.piece = {}            # piece index -> [sum r, sum g, sum b, weight]
        self.cur = 0               # piece the next faces belong to

    def add(self, uv, lookup):
        """uv: (k,2) texel coords of one face (k = 3 or 4); lookup(u, v) -> RGBA rows."""
        uv = np.asarray(uv, float)
        for tri in ([(0, 1, 2)] if len(uv) == 3 else [(0, 1, 2), (1, 3, 2)]):
            t = uv[list(tri)]
            area = abs((t[1, 0] - t[0, 0]) * (t[2, 1] - t[0, 1]) - (t[2, 0] - t[0, 0]) * (t[1, 1] - t[0, 1])) / 2
            pts = BARY @ t
            rgba = lookup(pts[:, 0].astype(int), pts[:, 1].astype(int))
            ok = rgba[:, 3] > 0
            if not ok.any():
                continue
            c = rgba[ok, :3].astype(int) >> 5
            w = (area + 1) / 4
            np.add.at(self.hist, c[:, 0] * 64 + c[:, 1] * 8 + c[:, 2], w)
            acc = self.piece.setdefault(self.cur, np.zeros(4))
            acc[:3] += rgba[ok, :3].sum(0) * w
            acc[3] += ok.sum() * w


def record(game, file, code, pieces, tris, prims, sampler, textured=True):
    pieces = [np.asarray(p, np.float32) for p in pieces]
    h = sampler.hist
    colours = {k: v[:3] / v[3] for k, v in sampler.piece.items() if v[3]}
    return dict(game=game, file=file, code=code, pieces=pieces, colours=colours,
                tris=tris, prims=prims, hist=h / h.sum() if h.sum() else None, textured=textured)


def load_dw1():
    import mmd
    e = mmd.exe()
    alltim = open(mmd.ALLTIM, 'rb').read()
    out = []
    for path in mmd.all_mmds():
        code = os.path.basename(path)[:-4]
        t = e.names.index(code)
        m = mmd.MMD.load(path, t)
        tim = mmd.Tim4(mmd.alltim_entry(alltim, t))
        idx = np.frombuffer(bytes(tim.idx), np.uint8).reshape(tim.h, tim.w)
        pals = np.array([[mmd.c15_to_rgba(c) for c in row] for row in tim.pal], np.uint8)
        smp = TexSampler()
        pieces, tris = [], 0
        for i, ob in enumerate(m.tmd.objects):
            smp.cur = i
            pieces.append([v[:3] for v in m.tmd.obj_verts(i)])
            for p in ob.prims:
                tris += 2 if p.mode & 8 else 1
                if p.mode & 4:
                    d = p.decode()
                    row = min(max((d['cba'] >> 6) - 488, 0), tim.ch - 1)
                    smp.add(d['uv'], lambda u, v, row=row: pals[row][idx[np.clip(v, 0, tim.h - 1), np.clip(u, 0, tim.w - 1)]])
        out.append(record('dw1', os.path.relpath(path, ROOT), code, pieces, tris,
                          sum(len(o.prims) for o in m.tmd.objects), smp) | dict(type=t))
    return out


def load_dw2():
    from dw2.model import parse_model
    from dw2.texture import image_halfwords, rgba15
    out = []
    for path in sorted(glob.glob(os.path.join(DW2, 'disc/AAA/4.AAA/MODEL/MODEL*/M*.BIN'))):
        code = os.path.basename(path)[:-4]
        if int(code[1:4]) >= 400:          # Digi-Beetle tanks and parts, field objects
            continue
        m = parse_model(open(path, 'rb').read(), code)
        hw = image_halfwords(m.texture)
        idx = np.empty((hw.shape[0], hw.shape[1] * 4), np.uint8)
        for i in range(4):
            idx[:, i::4] = (hw >> (4 * i)) & 0xF
        H, W = idx.shape
        smp = TexSampler()
        pals = {}
        for k, b in enumerate(m.bones):
            smp.cur = k
            for p in b.prims:
                if p.clut not in pals:
                    row, x = p.clut >> 6, (p.clut & 0x3F) * 16
                    pals[p.clut] = rgba15(hw[row % H, x:x + 16])
                pal = pals[p.clut]
                smp.add(p.uvs, lambda u, v, pal=pal: pal[idx[np.clip(v, 0, H - 1), np.clip(u, 0, W - 1)]])
        out.append(record('dw2', os.path.relpath(path, DW2), code, [b.vertices for b in m.bones],
                          sum(2 if len(p.verts) == 4 else 1 for b in m.bones for p in b.prims),
                          sum(len(b.prims) for b in m.bones), smp))
    return out


def load_dcb():
    from dcb.model import parse_model
    out = []
    paths = sorted(glob.glob(os.path.join(DCB, 'drv/F/[0-9]*.PAK')))
    for path in paths:
        base = os.path.basename(path)[:-4]
        if int(base) in (235, 300):        # the tamer, the arena logo
            continue
        m = parse_model(open(path, 'rb').read(), base)
        vram = m.vram
        if not m.textures and m.texture_name[:3].isdigit():   # variants reuse another file's TIM
            src = os.path.join(DCB, 'drv/F', m.texture_name[:3] + '.PAK')
            if os.path.exists(src):
                vram = parse_model(open(src, 'rb').read(), m.texture_name[:3]).vram
        smp, pages = TexSampler(), {}
        for k, b in enumerate(m.bones):
            smp.cur = k
            for p in b.mesh.prims:
                if not p.uvs:
                    continue
                key = (p.tpage & 0x19f, vram.resolve_clut(p.clut))
                if key not in pages:
                    pages[key] = vram.page(*key)
                pg = pages[key]
                smp.add(p.uvs, lambda u, v, pg=pg: pg[np.clip(v, 0, 255), np.clip(u, 0, 255)])
        out.append(record('dcb', os.path.relpath(path, DCB), base, [b.mesh.vertices for b in m.bones],
                          sum(2 if len(p.verts) == 4 else 1 for b in m.bones for p in b.mesh.prims),
                          sum(len(b.mesh.prims) for b in m.bones), smp) | dict(texture=m.texture_name))
    return out


def load_pdw():
    from pdw.archive import drv_entries
    from pdw.model import parse_pak, texture_pages
    out = []
    for _t, name, data in drv_entries(open(os.path.join(PDW, 'disc/F.DRV'), 'rb').read()):
        if name.startswith('BG'):
            continue
        for ch in parse_pak(name, data):
            pages = texture_pages(ch)
            smp = TexSampler()
            pieces, tris, prims = [], 0, 0
            for k, b in enumerate(ch.model.bones):
                smp.cur = k
                pieces.append([v for c in b.chunks for v in c.vertices])
                for c in b.chunks:
                    for p in c.prims:
                        tris += 2 if len(p.verts) == 4 else 1
                        prims += 1
                        if p.uvs:
                            pg = pages[(p.clut, p.tpage)]
                            smp.add(p.uvs, lambda u, v, pg=pg: pg[np.clip(v, 0, 255), np.clip(u, 0, 255)])
            out.append(record('pdw', f'disc/F.DRV:{name}', ch.name, pieces, tris, prims, smp))
    return out


def load_dw3():
    import dw3_extra; dw3_extra.patch()   # empty section slots
    from dw3.model import parse_model
    from dw3.texture import clut_rgba, indices_4bpp, tim_halfwords
    out = []
    for path in sorted(glob.glob(os.path.join(DW3, 'disc/AAA/DAT/FIGHT/MODEL/M*.BIN'))):
        code = os.path.basename(path)[:-4]
        if code[1:5] in ('457C', '458C', '459C', '460C', '461C', '462C', '463C', '464C'):
            continue                        # M457CDC1..M464CDS2: not Digimon
        try:
            m = parse_model(open(path, 'rb').read(), code)
        except Exception as ex:             # 5 files with the hierarchy overwritten on the disc
            print(f'dw3 {code}: not parsed ({ex.__class__.__name__}: {ex})', file=sys.stderr)
            out.append(record('dw3', os.path.relpath(path, DW3), code, [], 0, 0, TexSampler(), False)
                       | dict(broken=True))
            continue
        smp, textured = TexSampler(), bool(m.texture)
        if textured:
            hw = tim_halfwords(m.texture)
            idx = indices_4bpp(hw)
            pals = {}
        for k, b in enumerate(m.bones):
            smp.cur = k
            for p in b.mesh.prims:
                if p.uvs and textured:
                    mt = p.material
                    u0, v0 = mt[0] | mt[1] << 8, mt[2]
                    if (mt[3], mt[4]) not in pals:
                        pals[(mt[3], mt[4])] = clut_rgba(hw, mt[3], mt[4])
                    pal = pals[(mt[3], mt[4])]
                    uv = [((u0 + u) & 255, (v0 + v) & 255) for u, v in p.uvs]
                    smp.add(uv, lambda u, v, pal=pal: pal[idx[np.clip(v, 0, 255), np.clip(u, 0, 255)]])
        out.append(record('dw3', os.path.relpath(path, DW3), code, [b.mesh.vertices for b in m.bones],
                          sum(2 if len(p.verts) == 4 else 1 for b in m.bones for p in b.mesh.prims),
                          sum(len(b.mesh.prims) for b in m.bones), smp, textured))
    return out


LOADERS = dict(dw1=load_dw1, dw2=load_dw2, pdw=load_pdw, dcb=load_dcb, dw3=load_dw3)


def load_all(reload=False, games=GAMES):
    cache = {}
    if os.path.exists(CACHE) and not reload:
        cache = pickle.load(open(CACHE, 'rb'))
    changed = False
    for g in games:
        if g not in cache:
            print(f'loading {GAME_NAME[g]}...', file=sys.stderr, flush=True)
            cache[g] = LOADERS[g]()
            changed = True
    if changed:
        os.makedirs(os.path.dirname(CACHE), exist_ok=True)
        pickle.dump(cache, open(CACHE, 'wb'))
    return cache


# ---------------------------------------------------------------- shape comparison
NQ = 64


def signatures(rec):
    """Per piece (>= MIN_VERTS vertices): (vertex count, RMS distance, 64 normalised quantiles)."""
    if '_sig' not in rec:
        sig = []
        for k, v in enumerate(rec['pieces']):
            v = np.unique(v.astype(np.float64), axis=0)   # games split vertices differently at seams
            if len(v) < MIN_VERTS:
                continue
            d = np.sqrt(((v[:, None] - v[None]) ** 2).sum(-1))[np.triu_indices(len(v), 1)]
            rms = float(np.sqrt((d ** 2).mean())) or 1.0
            q = np.quantile(d / rms, np.linspace(0, 1, NQ))
            sig.append((len(v), rms, q, k))
        rec['_sig'] = sig
    return rec['_sig']


def piece_error(qa, qb):
    return float(np.median(np.abs(qa - qb) / np.maximum((qa + qb) / 2, 0.02)))


def _greedy(sa, sb, log_ratio=None):
    """Pairs (i, j, err) of same-vertex-count pieces, best shape first. With log_ratio, a pair
    must also have that size ratio (within SCALE_TOL), so look-alike pieces of graduated sizes
    (tails, fingers) pair with the right one."""
    by_a, by_b = defaultdict(list), defaultdict(list)
    for i, s in enumerate(sa):
        by_a[s[0]].append(i)
    for j, s in enumerate(sb):
        by_b[s[0]].append(j)
    pairs = []
    for n in by_a.keys() & by_b.keys():
        cand = []
        for i in by_a[n]:
            for j in by_b[n]:
                e = piece_error(sa[i][2], sb[j][2])
                # integer coordinates: about one unit of rounding on the coarser of the two
                if e > SHAPE_TOL + ROUNDING / min(sa[i][1], sb[j][1]):
                    continue
                key = e
                if log_ratio is not None:
                    d = abs(np.log(sb[j][1] / sa[i][1]) - log_ratio)
                    if d > SCALE_TOL + ROUNDING / min(sa[i][1], sb[j][1]):
                        continue
                    key = e + d
                cand.append((key, e, i, j))
        used_a, used_b = set(), set()
        for _k, e, i, j in sorted(cand):
            if i not in used_a and j not in used_b:
                used_a.add(i); used_b.add(j); pairs.append((i, j, e))
    return pairs


def compare(a, b):
    """Pair the pieces of two models by shape (a is the reference, usually DW1).
    Returns a dict: cls (identical / modified / different), matched (same vertex count, shape
    and size ratio), rescaled (same vertex count and shape at another size ratio: DW2 and
    DW2003 keep some pieces at another scale and scale them back in the bone matrices),
    pieces of each, added, removed, changed (unmatched on both sides), ratio (size of b over
    a), err (median piece error), vfrac_a/vfrac_b (share of each model's vertices in matched
    or rescaled pieces)."""
    sa, sb = signatures(a), signatures(b)
    pairs = _greedy(sa, sb)
    ratio = None
    rescaled = []
    if pairs:
        # the same mesh in other units scales as a whole: take the vertex-weighted median
        # ratio of the first pairing, then pair again requiring it
        lr = np.array([np.log(sb[j][1] / sa[i][1]) for i, j, e in pairs])
        med = float(np.median(np.repeat(lr, [sa[i][0] for i, j, e in pairs])))
        pairs = _greedy(sa, sb, med)
        ratio = float(np.exp(med))
        ma, mb = {i for i, j, e in pairs}, {j for i, j, e in pairs}
        rest_a = [s if k not in ma else (-1,) + s[1:] for k, s in enumerate(sa)]
        rest_b = [s if k not in mb else (-2,) + s[1:] for k, s in enumerate(sb)]
        rescaled = _greedy(rest_a, rest_b)
    both = pairs + rescaled
    ma = {i for i, j, e in both}
    mb = {j for i, j, e in both}
    ua = [i for i in range(len(sa)) if i not in ma]
    ub = [j for j in range(len(sb)) if j not in mb]
    changed = min(len(ua), len(ub))          # unmatched on both sides: a piece remade
    removed, added = len(ua) - changed, len(ub) - changed
    vfa = sum(sa[i][0] for i in ma) / max(sum(s[0] for s in sa), 1)
    vfb = sum(sb[j][0] for j in mb) / max(sum(s[0] for s in sb), 1)
    if pairs and not ua and not ub:
        cls = 'identical'
    elif pairs and min(vfa, vfb) >= 0.5 and len(both) >= 0.5 * max(len(sa), len(sb)):
        cls = 'modified'
    else:
        cls = 'different'
    return dict(cls=cls, matched=len(pairs), rescaled=len(rescaled), a_pieces=len(sa), b_pieces=len(sb),
                added=added, removed=removed, changed=changed, ratio=ratio, vfrac_a=vfa, vfrac_b=vfb,
                ua=[sa[i][0] for i in ua], ub=[sb[j][0] for j in ub],
                piece_pairs=[(sa[i][3], sb[j][3], sa[i][0]) for i, j, e in both],
                err=float(np.median([e for i, j, e in pairs])) if pairs else None)


def score(cm):
    """How much of both models a comparison explains (to pick the best candidate)."""
    return min(cm['vfrac_a'], cm['vfrac_b']) + 0.001 * (cm['cls'] == 'identical')


def _soft(rec):
    """The 8x8x8 colour histogram blurred by one bin along each channel (palettes a little
    lighter or darker in another game still overlap)."""
    if '_soft' not in rec:
        x = rec['hist'].reshape(8, 8, 8)
        for ax in range(3):
            pad = np.pad(x, [(1, 1) if i == ax else (0, 0) for i in range(3)])
            sl = lambda lo, hi: tuple(slice(lo, hi) if i == ax else slice(None) for i in range(3))
            x = (pad[sl(0, -2)] + 2 * pad[sl(1, -1)] + pad[sl(2, None)]) / 4
        rec['_soft'] = x.ravel() / x.sum()
    return rec['_soft']


def hist_overlap(a, b):
    """Intersection of the whole-model colour histograms (1 = same colours overall)."""
    if a['hist'] is None or b['hist'] is None:
        return None
    return float(np.minimum(_soft(a), _soft(b)).sum())


def tex_distance(a, b, cm):
    """Texture comparison on the matched pieces: the mean texel colour of each piece (sampled
    under its UV triangles) compared between the two models; returns the vertex-weighted
    median RGB distance (0-441) and the vertex share of pieces further apart than TEX_FAR, or
    None when either has no texture or no piece matched.
    Comparing piece by piece makes it independent of how each game lays out its texture page,
    and tells recolours (same mesh, other colours) apart."""
    if not a['textured'] or not b['textured'] or not cm['piece_pairs']:
        return None
    d, w = [], []
    for i, j, n in cm['piece_pairs']:
        if i in a['colours'] and j in b['colours']:
            d.append(float(np.linalg.norm(a['colours'][i] - b['colours'][j])))
            w.append(n)
    if not d:
        return None
    d, w = np.array(d), np.array(w, float)
    o = np.argsort(d)
    cw = np.cumsum(w[o])
    median = float(d[o[np.searchsorted(cw, cw[-1] / 2)]])
    far = float(w[d > TEX_FAR].sum() / w.sum())
    return median, far


# ---------------------------------------------------------------- names
# Canonical names are DW1's English names (content/species) where DW1 has the Digimon,
# else the English dub names. Keys of ALIASES are compared lower-case without punctuation.
# The other games' spellings of a renamed DW1 species map to its new name.
ALIASES = {
    'hkabuterimon': 'HerculesKabuterimon', 'herculeskabuterimon': 'HerculesKabuterimon', 'dokunemmon': 'Dokunemon', 'zassomon': 'Weedmon',
    'mastertyrannomon': 'MasterTyrannomon', 'kingofsukamon': 'KingSukamon', 'kingsukamon': 'KingSukamon', 'chimeramon': 'Kimeramon',
    'metalgreymon': 'MetalGreymonVirus', 'goburimon': 'Goblimon', 'snowgoburimon': 'SnowGoblimon',
    'sharmamon': 'Shamamon', 'darkrizamon': 'DarkLizardmon', 'panjyamon': 'IceLeomon', 'rockmon': 'Golemon',
    'pinocchimon': 'Puppetmon', 'ltoyagumon': 'ToyAgumon', 'holydramon': 'Magnadramon',
    'holyangemon': 'MagnaAngemon', 'tailmon': 'Gatomon', 'vamdemon': 'Myotismon', 'omegamon': 'Omnimon',
    'hanumon': 'Apemon', 'rukamon': 'Dolphmon', 'thunderballmon': 'Thundermon', 'picodevimon': 'DemiDevimon',
    'kurisarimon': 'Chrysalimon', 'dukemon': 'Gallantmon', 'megalogrowmon': 'WarGrowlmon',
    'apokarimon': 'Apocalymon', 'rgatomon': 'R-Gatomon', 'bkgatomon': 'BlackGatomon', 'dotamamon': 'D-Otamamon',
}

# DW2 / DW2003 four-letter codes that are not DW1 file names (identified from the previews and,
# where possible, confirmed by an identical or modified mesh in the card game, whose names
# come from its cards). Codes missing here are listed as unidentified.
CODES = {
    'VDRM': 'Veedramon', 'GAZI': 'Gazimon', 'GIZA': 'Gizamon', 'CYCL': 'Cyclonemon', 'DVDR': 'Devidramon',
    'TUSK': 'Tuskmon', 'FLYM': 'Flymon', 'DELT': 'Deltamon', 'RARE': 'Raremon', 'MTRN': 'MetalTyrannomon',
    'NANO': 'Nanomon', 'XTRN': 'ExTyrannomon', 'CLOK': 'Clockmon', 'ROSE': 'Rosemon', 'NTVA': 'Veemon',
    'VMON': 'Veemon', 'NTVB': 'Flamedramon', 'NTVC': 'Raidramon', 'IPDR': 'Imperialdramon',
    'OMGM': 'Omnimon', 'DBLM': 'Diaboromon', 'ARVR': 'AeroVeedramon', 'AKAB': 'MegaKabuterimon',
    'GOMA': 'Gomamon', 'WGAR': 'WereGarurumon', 'TOGE': 'Togemon', 'ZUDO': 'Zudomon', 'RIRI': 'Lillymon',
    'GRDM': 'Garudamon', 'CAND': 'Candlemon', 'BOLT': 'Boltmon', 'FLRA': 'Floramon', 'DERA': 'Deramon',
    'GRFO': 'Gryphonmon', 'WIZA': 'Wizardmon', 'PMAM': 'PrinceMamemon', 'MGAR': 'MetalGarurumon',
    'GANI': 'Ganimon', 'KIWI': 'Kiwimon', 'STAR': 'Starmon', 'BLSA': 'Blossomon', 'PUMP': 'Pumpkinmon',
    'ANOM': 'Anomalocarimon', 'TRCR': 'Triceramon', 'MSDR': 'MetalSeadramon', 'SLEO': 'SaberLeomon',
    'BAKU': 'Bakumon', 'HANU': 'Apemon', 'TOTA': 'Tortomon', 'IKAK': 'Ikkakumon', 'RUKA': 'Dolphmon',
    'HANG': 'MagnaAngemon', 'MANM': 'Mammothmon', 'WGRE': 'WarGreymon', 'MANG': 'MarineAngemon',
    'PDEV': 'DemiDevimon', 'SHAK': 'Shakomon', 'MUSH': 'Mushroomon', 'GESO': 'Gesomon', 'OCTA': 'Octomon',
    'WOOD': 'Woodmon', 'PHNT': 'Phantomon', 'MDEV': 'MarineDevimon', 'DAGO': 'Dagomon', 'OKWA': 'Okuwamon',
    'GARB': 'Garbagemon', 'PIEM': 'Piedmon', 'PUKU': 'Pukumon', 'PINO': 'Puppetmon', 'PLES': 'Plesiomon',
    'TAIL': 'Gatomon', 'ANGW': 'Angewomon', 'HDRA': 'Magnadramon', 'VVND': 'VenomMyotismon',
    'CHMR': 'Kimeramon', 'EBDR': 'Ebidramon', 'DKGM': 'Dokugumon', 'GOKI': 'Gokimon', 'MTAR': 'Minotarumon',
    'MSHA': 'Musyamon', 'KRSR': 'Chrysalimon', 'TDBL': 'Thundermon', 'LDDV': 'LadyDevimon', 'SNAI': 'Snimon',
    'HNGY': 'Hangyomon', 'SKST': 'SkullSatamon', 'INFR': 'Infermon', 'DEMN': 'Daemon', 'KGET': 'KingEtemon',
    'APKR': 'Apocalymon', 'PLDR': 'Paildramon', 'EXVM': 'ExVeemon', 'STNG': 'Stingmon', 'BKWG': 'BlackWarGreymon',
    'VALK': 'Valkyrimon', 'VIKI': 'Vikemon', 'SHDR': 'Shadramon', 'QTRU': 'Quetzalmon', 'BARO': 'Baronmon',
    'TIRO': 'Tylomon', 'GAGO': 'Gargoylemon', 'HAND': 'HiAndromon', 'PHAR': 'Pharaohmon',
    'IPDF': 'Imperialdramon', 'IPDP': 'Imperialdramon', 'ANTR': 'Antylamon', 'MUMY': 'Mummymon',
    'ARCH': 'Arukenimon', 'GIRU': 'Guilmon', 'GRAW': 'Growlmon', 'MGRW': 'WarGrowlmon', 'DUKE': 'Gallantmon',
    'RENA': 'Renamon', 'KYBI': 'Kyubimon', 'TAOM': 'Taomon', 'SKYA': 'Sakuyamon', 'BLZB': 'Beelzemon',
    'BVND': 'MaloMyotismon', 'ARMG': 'Armagemon', 'DINO': 'Dinohumon', 'GRIZ': 'Grizzlymon', 'MARS': 'Marsmon',
    'KNGT': 'Knightmon', 'SRPH': 'Seraphimon', 'BAST': 'Bastemon', 'FUJI': 'Fujinmon', 'SIJN': 'Suijinmon', 'RAIZ': 'Raijinmon',
}
# per-game overrides (the same code means something else in one game)
CODE_OVERRIDES = {
    ('dw3', 'M230GKWA'): 'GranKuwagamon',    # DW2003's model 230 is GranKuwagamon too (digimon_profiles.toml + esdignam.toml); no Gokuwmon exists
    ('dw2', 'M230GKWA'): 'GranKuwagamon',    # modified mesh of the card game's GranKuwagamon
    ('dw2', 'M214ARMG'): 'Seraphimon',       # DW2's own data names id 214 Seraphimon (DCB 184 mesh);
}                                            # DW2003's ARMG (M382) is Armagemon, its Seraphimon is M214SRPH
VARIANT_CODES = {   # alternative versions: code -> (base code, what it is)
    ('dw2', 'M244CPER'): ('M228PIEM', 'boss recolour CPER'),
    ('dw2', 'M245CMGR'): ('M204MSDR', 'boss recolour CMGR'),
    ('dw2', 'M246CWGR'): ('M213WGRE', 'boss recolour CWGR'),
    ('dw3', 'M359IPDF'): ('M148IPDR', 'Fighter Mode'),
    ('dw3', 'M381IPDP'): ('M148IPDR', 'Paladin Mode'),
}
# DW2 "Q" chibi models (M300-M375): their 3 letters -> the Digimon
Q_CODES = {
    'CAN': 'Candlemon', 'PAT': 'Patamon', 'GAB': 'Gabumon', 'GAN': 'Ganimon', 'TNK': 'Tankmon',
    'YNM': 'Yanmamon', 'COC': 'Kokatorimon', 'CNT': 'Centarumon', 'DRI': 'Drimogemon', 'TYR': 'Tyrannomon',
    'SED': 'Seadramon', 'DMR': 'Devidramon', 'PMP': 'Pumpkinmon', 'PCC': 'Piximon', 'MAM': 'Mamemon',
    'TRC': 'Triceramon', 'MSD': 'MegaSeadramon', 'BLT': 'Boltmon', 'PYO': 'Biyomon', 'TAG': 'ToyAgumon',
    'BAK': 'Bakumon', 'PEN': 'Penguinmon', 'AIR': 'Airdramon', 'BRD': 'Birdramon', 'LEO': 'Leomon',
    'ANG': 'Angemon', 'UNI': 'Unimon', 'GRE': 'Greymon', 'AKB': 'MegaKabuterimon', 'MAN': 'Mammothmon',
    'GIR': 'Giromon', 'AND': 'Andromon', 'MGR': 'MetalGreymonVirus', 'ZUD': 'Zudomon', 'WGR': 'WarGreymon',
    'HAG': 'Hagurumon', 'SGB': 'SnowGoblimon', 'BET': 'Betamon', 'NUM': 'Numemon', 'KWA': 'Kuwagamon',
    'WOD': 'Woodmon', 'BKE': 'Bakemon', 'DEV': 'Devimon', 'DLT': 'Deltamon', 'GEK': 'Gekomon',
    'VED': 'Vademon', 'OKW': 'Okuwamon', 'JRE': 'Cherrymon', 'MDV': 'MarineDevimon', 'PNO': 'Puppetmon',
    'PIE': 'Piedmon', 'PUK': 'Pukumon', 'HKB': 'HerculesKabuterimon', 'OME': 'Omnimon', 'JIJ': 'Jijimon',
    'TIS': 'MasterTyrannomon', 'CWG': 'WarGreymon', 'CPE': 'Piedmon', 'CMG': 'MetalSeadramon', 'TIN': 'Tinmon',
}
# QMSD is MegaSeadramon (QMTS, identical to QCMG, is MetalSeadramon). The Q codes of the 61 models
# identified later (QKMM, QMTS, ...) are in IDENT_CSV, not here.


def identified():
    """{(game, code): (name, variant, is_digimon)} from docs/data/crossgame-identified.csv:
    the DW2/DW2003 models identified from the games' own data (DW2's MODELDT*.BIN names by
    model id, DW2003's partner profiles and name table), text and previews."""
    games = {v: k for k, v in SHORT.items()}
    out = {}
    for r in csv.DictReader(open(IDENT_CSV)):
        out[(games[r['game']], r['code'])] = (r['name'], r['variant'], r['is_digimon'] == 'yes')
    return out
NO_DW1_MODEL = {'WereGarurumon': 62}     # DIGIMON_DATA entries with no MMD (docs/mods/models.md § 7)
NOT_DIGIMON = {('dw1', 'BOYS'), ('dw1', 'ANLG'), ('dw1', 'TENS')}


def key(name):
    return ''.join(ch for ch in name.lower() if ch.isalnum())


def canon(name):
    return ALIASES.get(key(name), name)


def dw1_names():
    names = {}
    import species                                  # content/species: the 180 of the disc
    for t, r in species.all_rows().items():
        if t < species.NUM_ORIGINAL: names[t] = r['name']
    return names


def dcb_names():
    out = {}
    for r in csv.DictReader(open(os.path.join(DCB, 'out', 'battle', 'index.tsv')), delimiter='\t'):
        out[r['id'].zfill(3)] = (r['name'], r['how named'])
    return out


def name_models(data):
    """Sets rec['name'] (canonical Digimon name, or '' if unidentified) and rec['variant'] on
    every record; drops the ones that are not Digimon."""
    n1, nd, ident = dw1_names(), dcb_names(), identified()
    dw1_code = {}
    for r in data['dw1']:
        t = r['type']
        r['name'] = canon(n1[t])
        r['variant'] = ('enemy' if t >= 125 and r['code'][0] == 'E' else
                        'enemy (CE)' if t >= 125 and r['code'][:2] == 'CE' else '')
        dw1_code[r['code']] = r['name']
    for r in data['dcb']:
        name, how = nd.get(r['code'], ('', ''))
        r['name'] = canon(name)
        r['variant'] = 'boss variant' if how.startswith('variant (texture') else (
            'second model' if r['code'] == '234' else '')
    for r in data['pdw']:
        name = nd.get(r['code'], ('', ''))[0]
        r['name'], r['variant'] = canon(name), ''
    for g in ('dw2', 'dw3'):
        for r in data[g]:
            code, c4 = r['code'], r['code'][4:]
            r['variant'] = ''
            if (g, code) in CODE_OVERRIDES:
                r['name'] = CODE_OVERRIDES[(g, code)]
            elif g == 'dw2' and int(code[1:4]) >= 300:
                r['name'] = Q_CODES.get(c4[1:], '')
                r['variant'] = 'Q (chibi)'
            elif c4 in dw1_code:
                r['name'] = dw1_code[c4]
            elif c4 in CODES:
                r['name'] = CODES[c4]
            else:
                r['name'] = ''
            if (g, code) in VARIANT_CODES and VARIANT_CODES[(g, code)][1]:
                r['variant'] = VARIANT_CODES[(g, code)][1]
            if (g, code) in ident:
                r['name'], r['variant'] = ident[(g, code)][:2]
    not_digimon = NOT_DIGIMON | {k for k, v in ident.items() if not v[2]}
    for g in GAMES:
        data[g] = [r for r in data[g] if (g, r['code']) not in not_digimon]
    for (g, code), (base, what) in VARIANT_CODES.items():
        for r in data[g]:
            if r['code'] == code and base:
                r['name'] = next(q['name'] for q in data[g] if q['code'] == base)
    # Pocket ids the card game has no card for (143, 144): named after an identical DW1 mesh
    for r in data['pdw']:
        if not r['name']:
            for q in data['dw1']:
                if q['variant'] == '' and plausible(q, r) and compare(q, r)['cls'] == 'identical':
                    r['name'], r['variant'] = q['name'], f'no card; mesh of DW1 {q["code"]}'
                    break
    # DW2003 numbered copies (M395KUW2, M413NUM2... M449MTG9): the model of the same game whose
    # code starts with the same three letters and whose mesh is identical or modified
    for r in data['dw3']:
        if r['name'] or not r['code'][-1].isdigit():
            continue
        for q in data['dw3']:
            if q is not r and q['name'] and q['code'][4:7] == r['code'][4:7] and \
                    not q['code'][-1].isdigit() and (q.get('broken') or r.get('broken')
                                                     or compare(q, r)['cls'] != 'different'):
                r['name'], r['variant'] = q['name'], f'copy of {q["code"]}'
                break
    return data


# ---------------------------------------------------------------- table
ORDER = ['dw1', 'dw2', 'pdw', 'dcb', 'dw3']     # release order (Japan): 1999, 2000, 2000, 2000-01, 2002
SHORT = {'dw1': 'DW1', 'dw2': 'DW2', 'pdw': 'Pocket', 'dcb': 'DCB', 'dw3': 'DW2003'}


def multiset(rec):
    if '_ms' not in rec:
        rec['_ms'] = Counter(s[0] for s in signatures(rec))
    return rec['_ms']


def plausible(a, b):
    """Cheap filter before a full comparison: enough shared piece sizes."""
    ov = sum((multiset(a) & multiset(b)).values())
    return ov >= 0.3 * max(1, min(sum(multiset(a).values()), sum(multiset(b).values())))


def rel_text(cm):
    if cm is None:
        return '—'
    if cm['cls'] == 'identical' and cm['rescaled']:
        return f'identical ({cm["rescaled"]} pieces rescaled)'
    if cm['cls'] == 'modified':
        parts = [f'+{cm["added"]}' if cm['added'] else '', f'-{cm["removed"]}' if cm['removed'] else '',
                 f'~{cm["changed"]}' if cm['changed'] else '']
        txt = 'modified ' + ' '.join(p for p in parts if p)
        return txt + (f' ({cm["rescaled"]} rescaled)' if cm['rescaled'] else '')
    return cm['cls']


def tex_text(t):
    if t is None:
        return '—'
    return 'same' if t[0] <= TEX_SAME and t[1] < TEX_FAR_SHARE else 'different'


def best_pair(refs, others):
    """The pair (ref, other, comparison, texture similarity) explaining the most mesh."""
    best = None
    for a in refs:
        for b in others:
            cm = compare(a, b)
            ts = tex_distance(a, b, cm)
            k = (score(cm), -(ts[0] if ts is not None else 999))
            if best is None or k > best[0]:
                best = (k, a, b, cm, ts)
    return best[1:] if best else None


def model_label(r):
    lab = r['code']
    return f'{lab} ({r["variant"]})' if r['variant'] else lab


def mesh_twins(data):
    """{id(record): [(name, 'DCB 184'), ...]}: identical meshes with another name. Identical
    needs the same multiset of piece vertex counts, so only those groups are compared."""
    groups = defaultdict(list)
    for g in GAMES:
        for r in data[g]:
            if not r.get('broken') and not r['variant'].startswith('Q') and multiset(r):
                groups[frozenset(multiset(r).items())].append(r)
    out = defaultdict(list)
    for grp in groups.values():
        for i, a in enumerate(grp):
            for b in grp[i + 1:]:
                if a['name'] != b['name'] and compare(a, b)['cls'] == 'identical':
                    out[id(a)].append((b['name'] or '?', f'{SHORT[b["game"]]} {b["code"]}'))
                    out[id(b)].append((a['name'] or '?', f'{SHORT[a["game"]]} {a["code"]}'))
    return out


def build_rows(data):
    groups = defaultdict(lambda: defaultdict(list))
    for g in GAMES:
        for r in data[g]:
            groups[r['name'] or f'? {SHORT[g]} {r["code"]}'][g].append(r)
    twins = mesh_twins(data)
    named = {g: [r for r in data[g] if r['name'] and not r.get('broken')] for g in GAMES}
    rows = []
    imported = imported_species()
    for name in sorted(groups, key=lambda n: (n.startswith('?'), n.lower())):
        gm = groups[name]
        ref_game = next(g for g in ORDER if g in gm)
        row = dict(name=name, first=SHORT[ref_game], reference=SHORT[ref_game])
        notes = []
        for g in GAMES:
            row[g] = '; '.join(model_label(r) for r in gm.get(g, []))
        usable = lambda rs: [r for r in rs if not r.get('broken')]
        refs = usable([r for r in gm[ref_game] if not r['variant'].startswith('Q')] or gm[ref_game])
        if not refs:
            notes.append(f'{SHORT[ref_game]} model not parsed (hierarchy overwritten on the disc)')
        for g in GAMES:
            if g == ref_game:
                row[f'rel_{g}'] = 'reference'
                row[f'tex_{g}'] = ''
                continue
            mine = [r for r in gm.get(g, []) if not r['variant'].startswith('Q')]
            if not mine or not refs or not usable(mine):
                row[f'rel_{g}'] = ('—' if not gm.get(g) else 'different (Q only)' if not mine
                                   else 'not parsed' if not usable(mine) else '— (reference not parsed)')
                row[f'tex_{g}'] = '—'
                continue
            mine = usable(mine)
            a, b, cm, ts = best_pair(refs, mine)
            row[f'rel_{g}'] = rel_text(cm)
            row[f'tex_{g}'] = tex_text(ts) if cm['cls'] != 'different' else 'n/a'
            row[f'_cmp_{g}'] = (a, b, cm, ts)
            if cm['cls'] == 'modified':
                ch = []
                if cm['ua'] or cm['ub']:
                    ch.append(f'vertices of the unmatched pieces {"/".join(map(str, sorted(cm["ua"]))) or "none"}'
                              f' -> {"/".join(map(str, sorted(cm["ub"]))) or "none"}')
                notes.append(f'{SHORT[g]} {b["code"]}: ' + '; '.join(ch) + f', triangles {a["tris"]} -> {b["tris"]}')
            if a['variant'] or b['variant']:
                notes.append(f'{SHORT[g]}: best pair {b["code"]} vs {SHORT[ref_game]} {a["code"]}')
        # the same mesh under another name (recolours, reused bodies), in any game
        tw = defaultdict(dict)
        for g in GAMES:
            for r in gm.get(g, []):
                for other_name, label in twins.get(id(r), []):
                    tw[other_name][label] = 1
        for other_name in sorted(tw):
            notes.append(f'same mesh as {other_name} ({", ".join(tw[other_name])})')
        if name.startswith('?'):          # unidentified: the closest named model of any game
            r = next(iter(next(iter(gm.values()))))
            best = None
            for g in GAMES:
                for q in named.get(g, []):
                    if q is not r and not r.get('broken') and plausible(q, r):
                        cm = compare(q, r)
                        if cm['cls'] != 'different' and (best is None or score(cm) > best[0]):
                            best = (score(cm), q, cm)
            if best:
                notes.append(f'{best[2]["cls"]} vs {SHORT[best[1]["game"]]} {best[1]["code"]} ({best[1]["name"]})')
        if name in NO_DW1_MODEL:
            notes.append(f'DW1 has it as type {NO_DW1_MODEL[name]} but no model file')
        row['notes'] = '; '.join(dict.fromkeys(notes))
        row['_groups'] = gm
        row['source'] = source(row)
        row['species'] = imported.get(name.lower().replace(' ', '').replace('-', ''), '')
        rows.append(row)
    return rows


COLUMNS = ['name', 'first', 'dw1', 'dw2', 'pdw', 'dcb', 'dw3', 'reference',
           'rel_dw2', 'tex_dw2', 'rel_pdw', 'tex_pdw', 'rel_dcb', 'tex_dcb', 'rel_dw3', 'tex_dw3',
           'rel_dw1', 'notes', 'source', 'species']
SOURCE_ORDER = [('dw1', 'DW1'), ('dcb', 'Card Battle'), ('dw2', 'DW2'), ('pdw', 'Pocket'), ('dw3', 'DW2003')]


def imported_species():
    """{lower-case name: species id} of the playable species made from these models in content/species: the imports
    (ids >= 180) and the record originals (docs/mods/species.md: an original id with an imported model, e.g. Tentomon
    111). A renamed species is found under its former name too (`"_former_name"` in its file)."""
    out = {}
    for p in sorted(glob.glob(os.path.join(ROOT, 'content', 'species', '*.json'))):
        i, _, n = os.path.basename(p)[:-5].partition('-')
        if not i.isdigit(): continue
        s = json.load(open(p))
        if int(i) >= 180 or 'skeleton' in s.get('model', {}):
            out[n.replace('-', '')] = int(i)
            for former in ([s['_former_name']] if isinstance(s.get('_former_name'), str) else s.get('_former_name', [])):
                out[former.lower().replace(' ', '').replace('-', '')] = int(i)
    return out


def source(row):
    """Where to take the model from for DW1: DW1 > Card Battle > DW2 > Pocket > DW2003
    (a DW2 "Q" chibi alone does not count)."""
    for g, label in SOURCE_ORDER:
        if any(not r['variant'].startswith('Q') for r in row['_groups'].get(g, [])):
            return label
    return ''


def write_csv(rows, path=CSV_OUT):
    with open(path, 'w', newline='') as f:
        w = csv.writer(f)
        w.writerow(COLUMNS)
        for r in rows:
            w.writerow([r.get(c, '') for c in COLUMNS])


def summary(rows, data):
    out = []
    p = out.append
    p('Models per game (Digimon only, all variants):')
    for g in GAMES:
        p(f'  {SHORT[g]}: {len(data[g])} models, {sum(1 for r in rows if r[g])} Digimon names'
          f' ({sum(1 for r in rows if r[g] and r["name"].startswith("?"))} unidentified)')
    p('Imported as species (content/species, column `species`) per source of the model:')
    for _, label in SOURCE_ORDER[1:]:
        names = [r for r in rows if r['source'] == label]
        done = sum(1 for r in names if r['species'])
        p(f'  {label}: {done} done, {len(names) - done} left of {len(names)}')
    p('Relation to DW1 (Digimon DW1 has):')
    for g in GAMES[1:]:
        c = Counter(('not parsed' if r[f'rel_{g}'].startswith('not') else r[f'rel_{g}'].split(' ')[0])
                    for r in rows if r['reference'] == 'DW1' and r[g])
        p(f'  {SHORT[g]}: ' + ', '.join(f'{k} {v}' for k, v in c.most_common()))
    p('Texture same as DW1 (pairs not "different"):')
    for g in GAMES[1:]:
        c = Counter(r[f'tex_{g}'] for r in rows if r['reference'] == 'DW1' and r[g]
                    and not r[f'rel_{g}'].startswith('different'))
        p(f'  {SHORT[g]}: ' + ', '.join(f'{k} {v}' for k, v in c.most_common()))
    p('New Digimon (not in DW1) per game:')
    for g in GAMES[1:]:
        n = [r for r in rows if r[g] and not r['dw1']]
        first = [r for r in n if r['first'] == SHORT[g]]
        p(f'  {SHORT[g]}: {len(n)} names ({sum(1 for r in n if r["name"].startswith("?"))} unidentified),'
          f' {len(first)} first seen here')
    return '\n'.join(out)


# ---------------------------------------------------------------- spot check
def preview(rec, height=170):
    """A preview strip of a model: the sister repos' own previews, DW1 rendered with mmd.py."""
    from tools.image import Image
    g, code = rec['game'], rec['code']
    if g == 'dw1':
        import mmd
        m = mmd.MMD.load(os.path.join(ROOT, rec['file']), rec['type'])
        tim = mmd.load_tim(mmd.ALLTIM, rec['type'])
        nb = mmd.exe().bone_count[rec['type']]
        frames, _ = mmd.simulate(m.anims.anims[m.anims.table[0]], nb, max_ticks=1)
        pose = frames[0]
        pose[0] = [4096, 4096, 4096, 0, 0, 0, 0, 0, 0]
        ims = []
        for yaw in (0, 90, 180):
            px = mmd.render(m, tim, pose, height, math.radians(yaw))
            ims.append(Image.frombytes('RGBA', (height, height), bytes(px)).convert('RGB'))
        out = Image.new('RGB', (3 * height, height))
        for k, im in enumerate(ims):
            out.paste(im, (k * height, 0))
        return out
    path = {'dw2': f'{DW2}/out/models/preview/{code}.png', 'pdw': f'{PDW}/out/F/preview/{code}.png',
            'dw3': f'{DW3}/out/fight/preview/{code}.png'}.get(g)
    if g == 'dcb':
        path = (glob.glob(f'{DCB}/out/battle/preview/{code}_*.png') + [f'{DCB}/out/battle/preview/{code}.png'])[0]
    try:
        im = Image.open(path).convert('RGB')
    except OSError:
        return Image.new('RGB', (3 * height, height), (90, 0, 0))
    im.thumbnail((3 * height, height))
    return im


def spot_check(rows, out_dir, seed=1, per_sheet=4):
    """Side-by-side previews: 5 random 'identical' pairs and every 'modified' one."""
    from tools.image import Image, ImageDraw
    os.makedirs(out_dir, exist_ok=True)
    ident, modif = [], []
    for r in rows:
        for g in GAMES:
            c = r.get(f'_cmp_{g}')
            if not c:
                continue
            (modif if c[2]['cls'] == 'modified' else ident if c[2]['cls'] == 'identical' else []).append((r, g, c))
    random.Random(seed).shuffle(ident)
    picks = [('identical', x) for x in ident[:5]] + [('modified', x) for x in modif]
    sheets = []
    for k in range(0, len(picks), per_sheet):
        chunk = picks[k:k + per_sheet]
        H = 170
        sheet = Image.new('RGB', (2 * 3 * H + 10, len(chunk) * (H + 18)), (25, 25, 25))
        dr = ImageDraw.Draw(sheet)
        for i, (kind, (r, g, c)) in enumerate(chunk):
            a, b, cm, ts = c
            y = i * (H + 18)
            dr.text((2, y + 2), f'{r["name"]}: {SHORT[a["game"]]} {a["code"]} vs {SHORT[g]} {b["code"]} -> '
                    f'{rel_text(cm)} ({cm["matched"]}/{cm["a_pieces"]}/{cm["b_pieces"]} pieces, tris '
                    f'{a["tris"]}/{b["tris"]}) tex {tex_text(ts)} {ts if ts is None else (round(ts[0]), round(ts[1], 2))}', fill=(255, 255, 0))
            sheet.paste(preview(a, H), (0, y + 18))
            sheet.paste(preview(b, H), (3 * H + 10, y + 18))
        path = os.path.join(out_dir, f'spot-{k // per_sheet:02d}.png')
        sheet.save(path)
        sheets.append(path)
    print(f'{len(picks)} pairs ({len(modif)} modified) in {len(sheets)} sheets under {out_dir}')
    return sheets


def main():
    ap = argparse.ArgumentParser(description=__doc__.split('\n')[0])
    ap.add_argument('--reload', action='store_true', help='re-parse every model')
    ap.add_argument('--spot', metavar='DIR', help='write side-by-side previews for the spot check')
    ap.add_argument('--seed', type=int, default=1)
    a = ap.parse_args()
    data = name_models(load_all(a.reload))
    rows = build_rows(data)
    write_csv(rows)
    print(f'{CSV_OUT}: {len(rows)} rows')
    print(summary(rows, data))
    if a.spot:
        spot_check(rows, a.spot, a.seed)


if __name__ == '__main__':
    main()
