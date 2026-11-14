"""Digital Card Battle attack effects into DW1 EFE chunks, through the DW2 converter (tools/dw2efe.py).

A DCB attack is two MSCD scripts: the card's own (the scene at the attacker, with what it throws toward the
defender) and a shared "extra" script (the hit on the defender). tools/dcbeffect.py traces each into objects
with a motion per step and turns them into a dw2effect.Effect; this module resamples the timelines to the
lengths DW1 allows (a cast object at most CAST_FRAMES frames, a hit object HIT_FRAMES), converts, and renders
the original next to the converted chunk.

    DCB_IMAGE=<disc.bin> python tools/dcbefe.py convert <attack script> <extra script> <out dir> [name]
"""
import json
import os
import struct
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from tools import dcbeffect as C, dw2effect as D, dw2efe, efesim as S          # noqa: E402

LIKE_CHUNK = 63                 # the EFEDAT chunk whose launch table the converted chunks reuse (as dw2 does)
EFFECT_ID, SCALE = 0x17a, 0.266          # both DCB scripts are in the same units: one scale for cast and hit
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

    def effects(self, max_flip=None, cast_frames=dw2efe.CAST_FRAMES, hit_frames=dw2efe.HIT_FRAMES):
        mf = self.max_flip if max_flip is None else max_flip
        f0, f1 = window(self.cast_tr)
        steps, k = sample(f0, f1, cast_frames)
        casts, hits = [], []
        notes = {'cast_steps': [f0, f1], 'cast_compression': round(k, 2)}
        if steps:
            e = C.to_effect(self.cast_tr, self.packs, steps, vram_tims=C.sheet_tims(self.cast_tr, self.packs),
                            max_flip=mf)
            casts.append((1, e))
            notes['cast'] = e._drawn.__dict__
        if self.hit_tr is not None:
            h0, h1 = window(self.hit_tr)
            hsteps, hk = sample(h0, h1, hit_frames)
            notes.update(hit_steps=[h0, h1], hit_compression=round(hk, 2))
            if hsteps:
                packs = self.packs[1:] + self.packs[:1]
                e = C.to_effect(self.hit_tr, packs, hsteps, vram_tims=C.sheet_tims(self.hit_tr, packs), max_flip=mf)
                hits.append((1, e))
                notes['hit'] = e._drawn.__dict__
        self.notes = notes
        return casts, hits

    def convert(self, table, **kw):
        """(chunk, info), dropping flipbook frames until the textures fit the chunk."""
        last = None
        for mf in (self.max_flip, 2, 1):
            casts, hits = self.effects(max_flip=mf)
            if not casts and not hits:
                raise dw2efe.Unconvertible('effect: nothing is ever drawn')
            try:
                chunk, info = dw2efe.convert_skill(casts, hits, table, EFFECT_ID, SCALE, hit_scale=SCALE, **kw)
            except dw2efe.Unconvertible as e:
                last = e
                if 'slot has' not in str(e):
                    raise
                continue
            info = dict(info, flipbook_frames=mf, source=self.notes)
            return chunk, info
        raise last


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
    for t in range(0, hits_at, 2 * every):
        im = Image.new('RGB', (w, h))
        im.putdata(D.render_tick(objs, t, cam))
        out.append(im)
    return out


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
    c.add_argument('attack', type=int)
    c.add_argument('extra', type=int)
    c.add_argument('out')
    c.add_argument('name', nargs='?', default='')
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
    base = os.path.join(a.out, a.name or str(a.attack))
    atk = Attack(disc, a.attack, a.extra)
    table = efedat_table()
    rec = {'attack_script': a.attack, 'extra_script': a.extra, 'name': a.name}
    try:
        chunk, info = atk.convert(table)
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
        sheet(orig[::max(1, len(orig) // 16)][:16], label=f'{a.name} DCB (traced)').save(base + '-dcb.png')
        sheet(conv[::max(1, len(conv) // 16)][:16], label=f'{a.name} DW1 (converted)').save(base + '-dw1.png')
        fd = base + '-frames'
        os.makedirs(fd, exist_ok=True)
        for i, im in enumerate(conv):
            im.save(os.path.join(fd, f'dw1-{i:03d}.png'))
        for i, im in enumerate(orig):
            im.save(os.path.join(fd, f'dcb-{i:03d}.png'))
    print(a.name, len(chunk), rec.get('detail'), rec.get('flipbook_frames'))
    return 0


if __name__ == '__main__':
    sys.exit(main())
