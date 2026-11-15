"""Digital Card Battle attack effects into DW1 EFE chunks, through the DW2 converter (tools/dw2efe.py).

A DCB attack is two MSCD scripts: the card's own (the scene at the attacker, with what it throws toward the
defender) and a shared "extra" script (the hit on the defender). tools/dcbeffect.py traces each into objects
with a motion per step and turns them into a dw2effect.Effect; this module resamples the timelines to the
lengths DW1 allows (a cast object at most CAST_FRAMES frames, a hit object HIT_FRAMES), converts, and renders
the original next to the converted chunk.

    DCB_IMAGE=<disc.bin> python tools/dcbefe.py convert <species id> <out dir> [--render]
"""
import json
import os
import struct
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from tools import dcbeffect as C, dw2effect as D, dw2efe, efesim as S          # noqa: E402

LIKE_CHUNK = 63                 # the EFEDAT chunk whose launch table the converted chunks reuse (as dw2 does)
EFFECT_ID, SCALE = 0x17a, 0.266          # EFFECT_ID: only when no species is given;          # both DCB scripts are in the same units: one scale for cast and hit
STAGE_DIST = 2700


def launch_table(chunk):
    """The origin table (10-byte rows to the type -1 row) the chunk's start script hands checkTechCompatibility."""
    start = struct.unpack_from('<i', chunk, 0)[0]
    pc = 0x34 + start + 12
    if struct.unpack_from('<H', chunk, pc - 12)[0] & 0xFF != 17 or struct.unpack_from('<H', chunk, pc)[0] & 0xFF != 12:
        raise ValueError('the chunk does not start with spawn, pusha table')
    at = 0x34 + struct.unpack_from('<h', chunk, pc + 2)[0]
    end = at
    while struct.unpack_from('<h', chunk, end)[0] >= 0:
        end += 10
    return bytes(chunk[at:end + 10])


SPECIES_TABLE = os.path.join('content', 'finishers', 'dcb-effects.json')


def species_entry(species, root='.'):
    """The species' row of content/finishers/dcb-effects.json: its chunk id and its two scripts."""
    with open(os.path.join(root, SPECIES_TABLE)) as f:
        for r in json.load(f)['effects']:
            if r['species'] == species:
                return r
    raise KeyError(f'species {species} has no DCB effect row')


def efedat_table(root='.'):
    with open(os.path.join(root, 'extracted', 'ETCHI', 'EFEDAT.EFE'), 'rb') as f:
        f.seek(LIKE_CHUNK * 0x5000)
        return launch_table(f.read(0x5000))


def window(tr, drawn_kinds=(1, 12, 13, 15, 16)):
    """[first, last) steps in which something is drawn."""
    starts = [i.start for i in tr.instances if i.kind in drawn_kinds]
    if not starts:
        return 0, 0
    ends = [min(i.end, tr.length) for i in tr.instances if i.kind in drawn_kinds]
    return min(starts), max(ends)


def sample(first, last, frames):
    """At most `frames` steps of [first, last), evenly spread (one per step when it fits)."""
    n = last - first
    if n <= frames:
        return list(range(first, last)), 1.0
    return [first + (k * n) // frames for k in range(frames)], n / frames


# what to give up, in order, until the chunk fits: (animated sprite frames, texture shrink, objects per script)
LADDER = ((4, 1, 24), (2, 1, 16), (2, 2, 12), (1, 2, 8), (1, 4, 6), (1, 4, 3), (1, 4, 1))
# Tried when the first fit fails the fidelity check: more alike objects, while the slot still holds them.
DENSER = ((4, 1, 48), (2, 1, 96), (2, 2, None))
# the DW2 converter's own pose detail levels, fewer of them (each try costs a full conversion)
LEVELS = (dw2efe.LEVELS[0], dw2efe.LEVELS[2], dw2efe.LEVELS[5], dw2efe.LEVELS[-1])


class Attack:
    """One DCB attack traced and turned into the cast and hit effects of a DW2-style technique."""

    def __init__(self, disc, attack, extra, max_flip=4):
        scripts = disc.scripts()
        self.attack, self.extra = attack, extra
        self.packs = [disc.pack(attack)] + ([disc.pack(extra)] if extra else [])
        self.cast_tr = C.trace(scripts[attack], attack)
        self.hit_tr = C.trace(scripts[extra], extra) if extra in scripts else None
        self.max_flip = max_flip
        self.notes = {}

    def effects(self, max_flip=None, shrink=1, max_objects=None, cast_frames=dw2efe.CAST_FRAMES,
                hit_frames=dw2efe.HIT_FRAMES):
        mf = self.max_flip if max_flip is None else max_flip
        f0, f1 = window(self.cast_tr)
        steps, k = sample(f0, f1, cast_frames)
        casts, hits = [], []
        notes = {'cast_steps': [f0, f1], 'cast_compression': round(k, 2)}
        if steps:
            e = C.to_effect(self.cast_tr, self.packs, steps, vram_tims=C.sheet_tims(self.cast_tr, self.packs),
                            max_flip=mf, shrink=shrink, max_objects=max_objects)
            casts.append((1, e))
            notes['cast'] = e._drawn.__dict__
        if self.hit_tr is not None:
            h0, h1 = window(self.hit_tr)
            hsteps, hk = sample(h0, h1, hit_frames)
            notes.update(hit_steps=[h0, h1], hit_compression=round(hk, 2))
            if hsteps:
                packs = self.packs[1:] + self.packs[:1]
                e = C.to_effect(self.hit_tr, packs, hsteps, vram_tims=C.sheet_tims(self.hit_tr, packs), max_flip=mf,
                                shrink=shrink, max_objects=max_objects)
                hits.append((1, e))
                notes['hit'] = e._drawn.__dict__
        self.notes = notes
        return casts, hits

    def convert(self, table, effect_id=EFFECT_ID, ladder=LADDER, **kw):
        """(chunk, info): down the LADDER (fewer animated sprite frames, smaller textures, fewer alike objects)
        until the chunk fits."""
        last = None
        for mf, shrink, objs in ladder:
            casts, hits = self.effects(max_flip=mf, shrink=shrink, max_objects=objs)
            if not casts and not hits:
                raise dw2efe.Unconvertible('effect: nothing is ever drawn')
            try:
                chunk, info = convert_skill(casts, hits, table, effect_id, SCALE, hit_scale=SCALE, **kw)
            except dw2efe.Unconvertible as e:
                last = e
                if 'slot has' not in str(e) and 'do not fit' not in str(e):
                    raise
                continue
            info = dict(info, flipbook_frames=mf, texture_shrink=shrink, max_objects=objs, source=self.notes)
            return chunk, info
        raise last


def convert_skill(*args, **kw):
    """dw2efe.convert_skill over LEVELS only."""
    for n, (step, quant, width, sides) in enumerate(LEVELS):
        try:
            chunk, info = dw2efe._convert_skill(*args, step=step, quant=quant, width=width, sides=sides, **kw)
        except dw2efe.Unconvertible as e:
            if 'slot has' not in str(e) or n == len(LEVELS) - 1:
                raise
            continue
        info['detail'] = f'step {step} quant {quant} texture {width}'
        return chunk, info


def stage(table, n_enemies=1, dist=STAGE_DIST):
    kind = struct.unpack_from('<h', table, 0)[0]
    F = [None] * 10
    F[1] = S.Fighter(kind, (0, 0, 0), 0, hp=100)
    F[2] = S.Fighter(kind, (0, 0, -dist), 0x800)
    for k in range(1, n_enemies):
        F[2 + k] = S.Fighter(kind, ((-1) ** k * 900 * ((k + 1) // 2), 0, -dist - 300), 0x800)
    return F


def camera(w, h):
    return D.Camera(w, h, eye=(14000 * SCALE, -4200 * SCALE, -STAGE_DIST / 2),
                    look=(0, -1400 * SCALE, -STAGE_DIST / 2))


def simulate(chunk, table, max_ticks=200):
    sim = S.Sim(chunk, stage(table), 1, 2)
    for _ in range(max_ticks):
        sim.step(reset_hits=True)
        if not sim.live():
            break
    return sim


def converted_frames(chunk, sim, w=320, h=200):
    """The converted chunk's picture at every engine tick (PIL images)."""
    from PIL import Image
    cam = camera(w, h)
    out = []
    for t in range(sim.tick + 1):
        im = Image.new('RGB', (w, h))
        im.putdata(S.render(chunk, sim, t, cam))
        out.append(im)
    return out


def original_frames(atk, w=320, h=200, every=2):
    """The DCB scene as traced (every `every` steps, 30 Hz), the attack at the attacker and the extra script at
    the defender, on the same stage and camera as the converted chunk (DCB units scaled to DW1 units)."""
    from PIL import Image
    placed = []
    f0, f1 = window(atk.cast_tr)
    steps = list(range(f0, f1))
    if steps:
        e = C.to_effect(atk.cast_tr, atk.packs, steps, vram_tims=C.sheet_tims(atk.cast_tr, atk.packs), max_flip=99)
        placed.append(D.Placed(e, (0, 0, 0), False, 0, 2 * len(steps)))
    hits_at = 2 * len(steps)
    cast_end = hits_at
    if atk.hit_tr is not None:
        h0, h1 = window(atk.hit_tr)
        hsteps = list(range(h0, h1))
        if hsteps:
            packs = atk.packs[1:] + atk.packs[:1]
            e = C.to_effect(atk.hit_tr, packs, hsteps, vram_tims=C.sheet_tims(atk.hit_tr, packs), max_flip=99)
            placed.append(D.Placed(e, (0, 0, -STAGE_DIST / SCALE), True, hits_at, 2 * len(hsteps)))
            hits_at += 2 * len(hsteps)
    objs = D.prepare(placed)
    cam = D.Camera(w, h, eye=(14000, -4200, -STAGE_DIST / SCALE / 2), look=(0, -1400, -STAGE_DIST / SCALE / 2))
    out = []
    original_frames.split = (cast_end + 2 * every - 1) // (2 * every)
    for t in range(0, hits_at, 2 * every):
        im = Image.new('RGB', (w, h))
        im.putdata(D.render_tick(objs, t, cam))
        out.append(im)
    return out


BG, POST = (28, 30, 40), (110, 110, 130)
THIN = 300                              # mean drawn pixels of a 320x200 picture
FIDELITY = {'area': 0.3, 'shown': 0.5, 'box': 0.3, 'curve': 0.0}


def lit(im):
    """Where an effect is drawn in a picture: the pixels that are neither the background nor a fighter post."""
    out = []
    w = im.size[0]
    for i, px in enumerate(im.get_flattened_data() if hasattr(im, "get_flattened_data") else im.getdata()):
        if max(abs(a - b) for a, b in zip(px, BG)) > 40 and max(abs(a - b) for a, b in zip(px, POST)) > 12:
            out.append((i % w, i // w, sum(px)))
    return out


def _bins(values, n):
    if not values:
        return [0.0] * n
    return [sum(values[len(values) * k // n:max(len(values) * k // n + 1, len(values) * (k + 1) // n)]) /
            max(1, len(values[len(values) * k // n:max(len(values) * k // n + 1, len(values) * (k + 1) // n)]))
            for k in range(n)]


def _corr(a, b):
    ma, mb = sum(a) / len(a), sum(b) / len(b)
    va = sum((x - ma) ** 2 for x in a) ** .5
    vb = sum((y - mb) ** 2 for y in b) ** .5
    return sum((x - ma) * (y - mb) for x, y in zip(a, b)) / (va * vb) if va and vb else 0.0


def fidelity(orig, conv, bins=20):
    """How much of the original the converted chunk shows, both rendered on the same stage and camera.
    area: mean drawn area (converted / original); shown: the share of the original's busy moments in which the
    converted chunk draws something too; box: overlap of the areas they ever cover (intersection / the smaller one; sizes are judged by area);
    curve: correlation of the drawn area over (normalised) time; energy: like area, weighted by brightness.
    passed is False when the converted chunk is mostly empty, drops parts or draws elsewhere."""
    def stats(frames):
        area, energy, box = [], [], None
        for im in frames:
            pts = lit(im)
            area.append(len(pts))
            energy.append(sum(p[2] for p in pts))
            if pts:
                xs, ys = [p[0] for p in pts], [p[1] for p in pts]
                b = (min(xs), min(ys), max(xs), max(ys))
                box = b if box is None else (min(box[0], b[0]), min(box[1], b[1]), max(box[2], b[2]), max(box[3], b[3]))
        return _bins(area, bins), _bins(energy, bins), box
    oa, oe, ob = stats(orig)
    ca, ce, cb = stats(conv)
    mo, mc = sum(oa) / bins, sum(ca) / bins
    busy = [k for k in range(bins) if oa[k] > 0.1 * max(oa)] if max(oa) else []
    shown = sum(1 for k in busy if ca[k] > 0.05 * max(oa)) / len(busy) if busy else 0.0
    box = 0.0
    if ob and cb:
        ix = max(0, min(ob[2], cb[2]) - max(ob[0], cb[0])) * max(0, min(ob[3], cb[3]) - max(ob[1], cb[1]))
        u = min((ob[2] - ob[0]) * (ob[3] - ob[1]), (cb[2] - cb[0]) * (cb[3] - cb[1]))
        box = min(1.0, ix / u) if u else 0.0
    r = {'area': round(mc / mo, 3) if mo else 0.0,
         'energy': round(sum(ce) / sum(oe), 3) if sum(oe) else 0.0,
         'shown': round(shown, 3), 'box': round(box, 3), 'curve': round(_corr(oa, ca), 3)}
    r['failed'] = [k for k, lim in FIDELITY.items() if r[k] < lim]
    r['passed'] = not r['failed']
    r['thin_source'] = mo < THIN        # the traced original itself draws little: the numbers say less
    return r


def fidelity_parts(orig, conv, osplit, csplit):
    """fidelity() of the whole, the cast (before the hit) and the hit, compared part with part: a chunk passes
    only when every part the original draws is drawn too."""
    r = {'whole': fidelity(orig, conv)}
    for name, o, c in (('cast', orig[:osplit], conv[:csplit]), ('hit', orig[osplit:], conv[csplit:])):
        if o and any(lit(im) for im in o[::max(1, len(o) // 12)]):
            r[name] = fidelity(o, c) if c else {'passed': False, 'failed': ['missing']}
    # a part whose original draws very little (a cast that only flashes) is not judged on its own numbers;
    # a whole that draws very little fails: the trace shows too little to call the conversion faithful
    judged = {k: v for k, v in r.items() if isinstance(v, dict) and (k == 'whole' or not v.get('thin_source'))}
    r['passed'] = all(v['passed'] for v in judged.values()) and not r['whole']['thin_source']
    r['failed'] = [f'{k} {x}' for k, v in judged.items() for x in v['failed']]
    if r['whole']['thin_source']:
        r['failed'].append('thin source')
    return r


def pick(frames, split, n=8):
    """n pictures of the cast and n of the hit, evenly spread."""
    def even(f):
        return [f[len(f) * k // n] for k in range(n)] if len(f) >= n else list(f)
    return even(frames[:split]) + even(frames[split:])


def sheet(frames, cols=8, label=None):
    from PIL import Image, ImageDraw
    if not frames:
        return Image.new('RGB', (320, 200))
    w, h = frames[0].size
    rows = (len(frames) + cols - 1) // cols
    im = Image.new('RGB', (w * cols, h * rows + (14 if label else 0)))
    for i, f in enumerate(frames):
        im.paste(f, ((i % cols) * w, (i // cols) * h + (14 if label else 0)))
    if label:
        ImageDraw.Draw(im).text((4, 1), label, fill=(255, 255, 255))
    return im


def grid_video(out_dir, names, path, w=320, h=200, fps=20, ffmpeg='ffmpeg'):
    """An mp4 of several converted attacks side by side: the traced DCB scene above (15 pictures a second, 30 Hz
    steps two at a time), the DW1 chunk below (20 Hz engine ticks), both at real speed."""
    import subprocess
    from PIL import Image, ImageDraw
    cols = []
    for n in names:
        d = os.path.join(out_dir, f'{n}-frames')
        files = sorted(os.listdir(d))
        cols.append((n, [os.path.join(d, f) for f in files if f.startswith('dcb')],
                     [os.path.join(d, f) for f in files if f.startswith('dw1')]))
    secs = max(max(len(a) / 15, len(b) / ENGINE_FPS) for _, a, b in cols) + 0.5
    W, H = w * len(cols), 2 * h + 28
    p = subprocess.Popen([ffmpeg, '-y', '-loglevel', 'error', '-f', 'rawvideo', '-pix_fmt', 'rgb24', '-s', f'{W}x{H}',
                          '-r', str(fps), '-i', '-', '-pix_fmt', 'yuv420p', '-c:v', 'libx264', '-crf', '20', path],
                         stdin=subprocess.PIPE)
    cache = {}

    def img(f):
        if f not in cache:
            cache[f] = Image.open(f).convert('RGB')
        return cache[f]
    for k in range(int(secs * fps)):
        t = k / fps
        frame = Image.new('RGB', (W, H))
        dr = ImageDraw.Draw(frame)
        for i, (n, a, b) in enumerate(cols):
            dr.text((i * w + 4, 1), f'{n}  DCB', fill=(255, 255, 255))
            dr.text((i * w + 4, h + 15), 'DW1 converted', fill=(255, 255, 255))
            if a:
                frame.paste(img(a[min(int(t * 15), len(a) - 1)]), (i * w, 14))
            if b:
                frame.paste(img(b[min(int(t * ENGINE_FPS), len(b) - 1)]), (i * w, h + 28))
        p.stdin.write(frame.tobytes())
    p.stdin.close()
    p.wait()


ENGINE_FPS = dw2efe.ENGINE_HZ


def main(argv=None):
    import argparse
    ap = argparse.ArgumentParser(description=__doc__.split('\n')[0])
    sub = ap.add_subparsers(dest='cmd', required=True)
    c = sub.add_parser('convert')
    c.add_argument('species', type=int, help='species id (its row in content/finishers/dcb-effects.json)')
    c.add_argument('out')
    c.add_argument('--render', action='store_true', help='also frame sheets and the converted frames as PNGs')
    g = sub.add_parser('grid', help='an mp4 of converted attacks side by side')
    g.add_argument('out')
    g.add_argument('video')
    g.add_argument('names', nargs='+')
    a = ap.parse_args(argv)
    if a.cmd == 'grid':
        grid_video(a.out, a.names, a.video, ffmpeg=os.environ.get('FFMPEG', 'ffmpeg'))
        return 0
    disc = C.Disc(os.environ['DCB_IMAGE'])
    os.makedirs(a.out, exist_ok=True)
    row = species_entry(a.species)
    a.name = row['species_name']
    base = os.path.join(a.out, a.name)
    atk = Attack(disc, row['attack_script'], row['hit_script'])
    table = efedat_table()
    rec = dict(row)
    try:
        chunk, info = atk.convert(table, effect_id=row['chunk'])
    except dw2efe.Unconvertible as e:
        rec['error'] = str(e)
        rec['source'] = atk.notes
        json.dump(rec, open(base + '.json', 'w'), indent=1, default=str)
        print(a.name, 'unconvertible:', e)
        return 1
    with open(base + '.efe', 'wb') as f:
        f.write(chunk)
    rec.update(info)
    json.dump(rec, open(base + '.json', 'w'), indent=1, default=str)
    if a.render:
        sim = simulate(chunk, table)
        conv = converted_frames(chunk, sim)
        orig = original_frames(atk)
        osplit = original_frames.split
        csplit = min((h[0] for h in sim.hits), default=rec.get('cast_ticks', len(conv)))
        rec['fidelity'] = fidelity_parts(orig, conv, osplit, csplit)
        if not rec['fidelity']['passed']:
            # One more round: denser fits, keeping the one with the fewest failed checks.
            best = len(rec['fidelity']['failed'])
            for rung in DENSER:
                try:
                    c2, i2 = atk.convert(table, effect_id=row['chunk'], ladder=(rung,))
                except dw2efe.Unconvertible:
                    continue
                s2 = simulate(c2, table)
                v2 = converted_frames(c2, s2)
                sp2 = min((h[0] for h in s2.hits), default=i2.get('cast_ticks', len(v2)))
                f2 = fidelity_parts(orig, v2, osplit, sp2)
                if len(f2['failed']) < best:
                    best = len(f2['failed'])
                    chunk, sim, conv, csplit = c2, s2, v2, sp2
                    rec.update(i2)
                    rec['fidelity'] = f2
                    with open(base + '.efe', 'wb') as f:
                        f.write(chunk)
                if f2['passed']:
                    break
        json.dump(rec, open(base + '.json', 'w'), indent=1, default=str)
        sheet(pick(orig, osplit), label=f'{a.name} DCB (traced)').save(base + '-dcb.png')
        sheet(pick(conv, csplit), label=f'{a.name} DW1 (converted)').save(base + '-dw1.png')
        fd = base + '-frames'
        os.makedirs(fd, exist_ok=True)
        for i, im in enumerate(conv):
            im.save(os.path.join(fd, f'dw1-{i:03d}.png'))
        for i, im in enumerate(orig):
            im.save(os.path.join(fd, f'dcb-{i:03d}.png'))
    print(a.name, len(chunk), rec.get('detail'), rec.get('flipbook_frames'), rec.get('fidelity'))
    return 0 if rec.get('fidelity', {}).get('passed', True) else 2


if __name__ == '__main__':
    sys.exit(main())
