#!/usr/bin/env python3
"""Size rule of the imported species (docs/mods/models.md, "Sizes of the imported species").

The importers (dcb2mmd, dw2mmd, dw3mmd) bring every model in DW1 units at the scale of its source game
(Card Battle x1, DW2 x1/5.1, DW2003 x0.2128), so the relative size of each Digimon inside its own game
is the natural size. The first rule of import_batch (one height range per level, 500 at most) lost it:
fourteen Ultimates and Megas came out at exactly 500, and wide ones (WarGrowlmon, Plesiomon) were
squeezed by a half-width limit. This tool measures the natural size of each species, applies the new
rule (`rule()`), scales the finished MMD (vertices, joints and translation keys: what the importer does
with `scale_model`, but on the file, so the rig/fit/mesh fixes are kept) and writes the species record.

  sizes.py measure [--content DIR ...]       natural size and current size of every species (CSV on stdout)
  sizes.py plan                              the table build/species-sizes.csv (no files written but the CSV)
  sizes.py apply [--out DIR] [--only NAME ...] [--no-content]
                                             scaled models to DIR/models (default build/sizes/models), species
                                             records to DIR/species; with content: also content/species/*.json
  sizes.py lineup ...                        pictures (see the end of the file)

Species JSON (docs/mods/species.md): `"size": {"height": N, "radius": R}` (optional, by hand: the height of the
model and/or the radius that replace the rule's), `model.height`/`model.radius` (what the rule writes) and `"sizing"` (written by `apply`: what the rule started from, so a
second run starts again from the unscaled model).
"""
import argparse, collections, csv, glob, json, math, os, re, sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, 'tools'))
import mmd
import species

# ---------------------------------------------------------------- the rule
# natural size -> DW1 size, per level of the species (3 Rookie, 4 Champion, 5 Ultimate, 6 Mega):
#   lo/hi    the range of the DW1 partners of the level (idle pose); a model outside is brought into it
#   stretch  Ultimates and Megas are stretched (the same factor for everything of the level, so relative sizes stay)
#   knee/ceil above `knee` the height bends towards `ceil` (exponential, slope 1 at the knee: it never reaches it,
#            so two giants keep their order)
#   hw/hd    half-width and half-depth limits of the posed model (the camera frames radius and height)
RULES = {
    3: dict(lo=180, hi=320, stretch=1.0, knee=None, ceil=None, hw=360, hd=420),
    4: dict(lo=200, hi=460, stretch=1.0, knee=None, ceil=None, hw=360, hd=420),
    5: dict(lo=180, hi=None, stretch=1.35, knee=450, ceil=700, hw=600, hd=700),
    6: dict(lo=450, hi=None, stretch=1.6, knee=640, ceil=900, hw=800, hd=900),
}
RADIUS_MIN, RADIUS_MAX = 100, 300           # the old import rule: 0.6 of the larger half-extent, 100..300
RADIUS_FACTOR = 0.6
RADIUS_HEIGHT = 0.25
# DW2003 draws the big Digimon far bigger than the other games (Seraphimon 1456 against 664 in Card Battle at
# the same x0.2128, Veemon alike 273 / 268): in log space DW2003's height is calibrated to Card Battle and DW2's
# (61 Digimon in two games, crossgame-sources.csv: slope 0.4736, rms 0.25), applied to widths alike
DW3_CAL = (2.856386, 0.473561)


def dw3_factor(h):
    return math.exp(DW3_CAL[0]) * h ** DW3_CAL[1] / h if h > 0 else 1.0


def softcap(x, knee, ceil):
    if x <= knee:
        return x
    return knee + (ceil - knee) * (1 - math.exp(-(x - knee) / (ceil - knee)))


def rule(level, game, top, hw, hd):
    """(scale, height, radius, why) for a species whose model, at the natural scale of its game, is `top` tall
    with half-extents hw, hd (DW1 units). `scale` multiplies the natural model."""
    R = RULES[level]
    f = dw3_factor(top) if game == 'dw3' and level >= 5 else 1.0     # common scale (Ultimates and Megas)
    c = top * f                                                      # natural height on the common scale
    if R['ceil']:
        h = max(R['lo'], softcap(c * R['stretch'], R['knee'], R['ceil']))
    else:
        h = min(R['hi'], max(R['lo'], c))
    s = h / top
    why = 'height'
    for name, lim, w in (('width', R['hw'], hw), ('depth', R['hd'], hd)):
        if w * s > lim:
            s, why = lim / w, name
    return s, top * s, hw * s, hd * s, why


def radius_of(hw, hd, h=0):
    """0.6 of the larger half-extent, not under a quarter of the height (a tall slim model still needs room around it)."""
    return int(round(min(RADIUS_MAX, max(RADIUS_MIN, RADIUS_FACTOR * max(hw, hd), RADIUS_HEIGHT * h))))


# ---------------------------------------------------------------- measuring
def posed_points(m, bones, slot=0):
    """World points of the model in the first tick of an animation slot (the root's own motion and
    scale left out), as import_batch measures it: Y down, ground at 0."""
    nb = len(bones)
    a = m.anims.anims[m.anims.table[slot]]
    p = mmd.AnimPlayer(a, nb, slot)
    p.tick(stop_at_infinite_loop=True)
    pose = [list(v) for v in p.pose]
    pose[0] = [4096, 4096, 4096, 0, 0, 0, 0, 0, 0]
    W = [None] * nb

    def get(b):
        if W[b] is None:
            v = pose[b]
            R = mmd.rot_matrix(*v[3:6])
            L = [[R[i][j] * v[j] / 4096 for j in range(3)] + [v[6 + i]] for i in range(3)] + [[0, 0, 0, 1]]
            par = bones[b][1]
            W[b] = mmd.mat_mul(get(par), L) if par >= 0 else L
        return W[b]
    pts = []
    for b, (oi, _) in enumerate(bones):
        if oi < 0:
            continue
        M = get(b)
        for x, y, z, _ in m.tmd.obj_verts(oi):
            pts.append(tuple(M[r][0] * x + M[r][1] * y + M[r][2] * z + M[r][3] for r in range(3)))
    return pts


def extent(pts):
    """(top, half-width, half-depth) of a posed model."""
    lo = [min(p[k] for p in pts) for k in range(3)]
    hi = [max(p[k] for p in pts) for k in range(3)]
    return -lo[1], max(-lo[0], hi[0]), max(-lo[2], hi[2])


def load_model(path, nbones):
    return mmd.MMD.parse(open(os.path.join(ROOT, path), 'rb').read(), nbones)


def measure_species(spec, path=None):
    """(top, hw, hd) of the species' model file (or `path`)."""
    bones = spec['model']['skeleton']
    m = load_model(path or spec['model']['file'], len(bones))
    return extent(posed_points(m, bones))


# ---------------------------------------------------------------- scaling a finished model
def rescale(m, k):
    """The model grows by k: vertices, and every translation of the animations (the initial pose, the keys, the
    root's momentum). Rotations, scales and normals do not change."""
    t = m.tmd
    t.verts = [tuple(max(-32768, min(32767, int(round(c * k)))) for c in v[:3]) + (v[3],) for v in t.verts]
    clamped = 0
    for a in m.anims.anims:
        ti = (6, 7, 8) if a.has_scale else (3, 4, 5)
        for v in a.pose:
            for i in ti:
                v[i] = max(-32768, min(32767, int(round(v[i] * k))))
        for ins in a.instrs:
            if ins['op'] == 'key':
                for b in ins['bones']:
                    for ch in ('tx', 'ty', 'tz'):
                        if ch in b['vals']:
                            x = int(round(b['vals'][ch] * k))
                            if not -32768 <= x <= 32767:
                                clamped += 1
                                x = max(-32768, min(32767, x))
                            b['vals'][ch] = x
    return clamped


# ---------------------------------------------------------------- where a species came from
SOURCE_SCALE = dict(dcb=1.0, dw2=1 / 5.1, dw3=0.2128)      # units of the game -> DW1 units (documentation: the loaders apply them)
LISTS = os.path.join('mods', 'experimental', 'batch-import')


def list_entries():
    """name -> list entry (game, model, level...) over every import list; the last list wins."""
    out = {}
    for f in sorted(glob.glob(os.path.join(ROOT, LISTS, '*.json')), key=os.path.getmtime):
        for e in json.load(open(f)).get('digimon', []):
            out[e['name']] = e
    return out


def reports():
    """name -> [(report, path)], newest first, of every import run (ids differ between runs: the first batch was renumbered)."""
    out = {}
    for f in sorted(glob.glob(os.path.join(ROOT, 'build', '*', 'report.json')), key=os.path.getmtime):
        try:
            d = json.load(open(f))
        except (ValueError, OSError):
            continue
        for n, r in d.items():
            if isinstance(r, dict) and 'rules' in r:
                out.setdefault(n, []).insert(0, (r, f))
    return out


def applied_scale(rep):
    """The factor the importer applied to the source model (import_batch: 'scaled xS: A -> B tall'), 1 when none."""
    for r in rep['rules']:
        m = re.match(r'scaled x([\d.]+): (\d+) -> (\d+) tall', r)
        if m:
            return int(m.group(3)) / int(m.group(2))
    return 1.0


def game_of(spec, entry):
    if entry:
        return entry.get('game', 'dcb')
    m = re.match(r'(dcb|dw2|dw3|dw1) ', spec.get('_source', ''))
    return m.group(1) if m else None


# ---------------------------------------------------------------- one species
def sizing_of(spec, entries, reps):
    """What the rule starts from: the unscaled-by-this-tool model and the natural size of the species.
    Written to the record's "sizing" the first time, read from it afterwards."""
    if spec.get('sizing'):
        return spec['sizing']
    e = entries.get(spec['name'])
    game = game_of(spec, e)
    top, hw, hd = measure_species(spec)
    rep = next((v for v in reps.get(spec['name'], []) if abs(v[0].get('budget', {}).get('height', 0) - top) <= 0.03 * top), None)
    s0 = applied_scale(rep[0]) if rep else 1.0
    level = 6 if e and e.get('level') == 'mega' else min(5, species.LEVELS.index(spec['level']))
    return dict(game=game, level=level, base_model=spec['model']['file'], base_scale=round(s0, 4),
                natural=dict(height=round(top / s0, 1), half_width=round(hw / s0, 1), half_depth=round(hd / s0, 1)))


def scale_vec(v, k):
    return [x if x == 'any' else int(round(x * k)) for x in v]


def apply_one(spec, entries, reps, out_models):
    """(new record, MMD bytes or None, what limited the size) of a species: the model the record started from, scaled by the rule.
    The record's effect origins and condition bubble (offsets in model units) grow with the model."""
    sz = sizing_of(spec, entries, reps)
    nat = sz['natural']
    top, hw, hd = nat['height'], nat['half_width'], nat['half_depth']
    level = sz['level']
    new = json.loads(json.dumps(spec))
    new['sizing'] = sz
    if level < 3:
        return new, None, 'none'
    ov = spec.get('size', {})
    s, h, w, d, why = rule(level, sz['game'], top, hw, hd)
    if ov.get('height'):
        s = ov['height'] / top
        h, w, d, why = top * s, hw * s, hd * s, 'override'
    radius = ov.get('radius') or radius_of(w, d, h)
    old_h = spec['model']['height']
    new['model']['height'] = int(round(h))
    new['model']['radius'] = int(radius)
    ratio = 1.0 if int(round(h)) == old_h else h / old_h             # origins: from the record's current model
    if ratio != 1.0:
        if spec.get('effect_origins'):
            # only `to` (a point of this model) scales; `from` is the effects type's EFE row, which the game matches
            # exactly (getSpeciesEffectOrigin): scaled, it matched nothing
            new['effect_origins'] = [list(e[:5]) + scale_vec(e[5:], ratio) for e in spec['effect_origins']]
        if spec.get('condition_bubble'):
            c = spec['condition_bubble']
            new['condition_bubble'] = scale_vec(c[:3], ratio) + [c[3]]
    k = s / sz['base_scale']                                          # against the model the record started from
    base = sz['base_model']
    if abs(k - 1) <= 0.005:
        new['model'] = dict(new['model'], file=base)
        return new, None, why
    m = load_model(base, len(spec['model']['skeleton']))
    clamped = rescale(m, k)
    if clamped:
        raise SystemExit(f'{spec["name"]}: {clamped} translation keys over int16 at x{k:.2f}')
    path = os.path.join(out_models, spec['name'] + '.MMD')
    new['model'] = dict(new['model'], file=os.path.relpath(path, ROOT))
    return new, m.build(), why


# ---------------------------------------------------------------- commands
CONTENT_DIR = os.path.join(ROOT, 'content', 'species')
CSV = os.path.join(ROOT, 'docs', 'data', 'species-sizes.csv')
FIELDS = ['id', 'name', 'level', 'source', 'natural_height', 'natural_half_width', 'natural_half_depth', 'old_height',
          'old_radius', 'new_height', 'new_radius', 'limit']
LEVEL_NAME = {3: 'Rookie', 4: 'Champion', 5: 'Ultimate', 6: 'Mega'}


def species_files(dirs):
    out = {}
    for d in dirs:
        for f in sorted(glob.glob(os.path.join(d, '*.json'))):
            out[os.path.basename(f)] = f
    return [out[k] for k in sorted(out)]


def sizeable(spec):
    return ((spec.get('id', 0) >= 183 or spec.get('id', 0) < 180) and 'skeleton' in spec.get('model', {})   # imports, record originals and spec.get('model', {}).get('file', '').startswith('build/')
            and 'tools/import_batch.py' in spec.get('_source', ''))


def run(a):
    entries, reps = list_entries(), reports()
    rows, written = [], 0
    only = set(a.only or [])
    outm = os.path.join(ROOT, a.out, 'models')
    outs = os.path.join(ROOT, a.out, 'species')
    if a.cmd == 'apply':
        os.makedirs(outm, exist_ok=True)
        os.makedirs(outs, exist_ok=True)
    for f in species_files([os.path.join(ROOT, c) for c in a.content]):
        spec = json.load(open(f), object_pairs_hook=collections.OrderedDict)
        if not sizeable(spec) or (only and spec['name'] not in only):
            continue
        new, data, why = apply_one(spec, entries, reps, outm)
        sz, nat = new['sizing'], new['sizing']['natural']
        old = spec['sizing'] if spec.get('sizing') else None
        rows.append(dict(id=spec['id'], name=spec['name'], level=LEVEL_NAME.get(sz['level'], sz['level']),
                         source=sz['game'], natural_height=round(nat['height']), natural_half_width=round(nat['half_width']),
                         natural_half_depth=round(nat['half_depth']),
                         old_height=a.old.get(spec['id'], (spec['model']['height'], spec['model']['radius']))[0],
                         old_radius=a.old.get(spec['id'], (spec['model']['height'], spec['model']['radius']))[1],
                         new_height=new['model']['height'], new_radius=new['model']['radius'], limit=why))
        if a.cmd != 'apply':
            continue
        if data is not None:
            open(os.path.join(ROOT, new['model']['file']), 'wb').write(data)
        name = os.path.basename(f)
        species.write_file(os.path.join(outs, name), new)
        if a.write_content and os.path.dirname(os.path.abspath(f)) == CONTENT_DIR and not re.match(r'4\d\d-', name) or \
                (a.write_content and os.path.dirname(os.path.abspath(f)) == CONTENT_DIR and a.include_4xx):
            species.write_file(f, new)
        written += 1
    if a.cmd in ('plan', 'apply'):
        with open(a.csv, 'w', newline='') as fh:
            w = csv.DictWriter(fh, FIELDS)
            w.writeheader()
            w.writerows(rows)
    print(f'{len(rows)} species{f", {written} written to {a.out}" if a.cmd == "apply" else ""}')
    return rows


def old_sizes(path):
    """The sizes before the rule: from a previous CSV (column old_*), so a rerun keeps them."""
    out = {}
    if os.path.exists(path):
        for r in csv.DictReader(open(path)):
            out[int(r['id'])] = (int(r['old_height']), int(r['old_radius']))
    return out


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('cmd', choices=['plan', 'apply', 'measure'])
    ap.add_argument('--content', nargs='*', default=['content/species'])
    ap.add_argument('--out', default='build/sizes')
    ap.add_argument('--csv', default=CSV)
    ap.add_argument('--only', nargs='*')
    ap.add_argument('--write-content', action='store_true', help='also rewrite content/species/*.json')
    ap.add_argument('--include-4xx', action='store_true')
    a = ap.parse_args()
    a.old = old_sizes(a.csv)
    rows = run(a)
    if a.cmd == 'measure':
        w = csv.DictWriter(sys.stdout, FIELDS)
        w.writeheader()
        w.writerows(rows)


if __name__ == '__main__':
    main()
