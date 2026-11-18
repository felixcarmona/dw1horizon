#!/usr/bin/env python3
"""Composed effect chunks: one of the disc's own technique effects (ETCHI/EFEDAT.EFE chunks 0-121) used as a
template, with a look of its own: recoloured and resized, its script, variables, launch table and timing kept
byte for byte, so the technique plays and hits exactly as the template does.

An entry of content/battle/own-effects.json is composed when it has "compose" (docs/mods/signature-effects.md):

    "162": {"name": "Nightmare Shock", "stands_for": 62,
            "compose": {"recolour": {"ramp": ["#1a0026", "#6a1aa8", "#e0b0ff"]}, "scale": 1.3},
            "check": {"hue": 280}}

- stands_for: the template, the chunk of the finisher the species' technique is (its launch table and script).
- recolour: every palette colour of the template's texture, and the colours its script hands the engine as
  data (sprite tints, model colours, flashes), mapped to the new look. "ramp": colours from dark to bright,
  each palette colour takes the ramp's colour at its own brightness; or "hue": degrees, each colour turned to
  that hue, with "saturation" (a floor, 0-1; default 0.6). "rows": the palette rows to change (default all).
  Transparent colour 0 stays transparent, the semi-transparency bit stays as it is, and no colour becomes 0.
- texture: a list of texel rectangles copied from other disc chunks over the template's texture, each
  {"from": chunk, "rect": [u, v, w, h], "to": [u, v], "palettes": [[from row, to row]]}: a new picture on the
  sprites or faces that use those texels (efesim's draws say which). It is copied before the recolour.
- scale: the template's model (TMD vertices) resized, one factor or [x, y, z]. Sprites keep their size.
- sounds: {template sound id: new sound id}: the sound each of the template's playSound calls plays (the id it
  pushes just before the call), for an effect that keeps the sounds of the attack it stands for (a Card Battle
  attack's cues as tools/dcbsound.py matched them). Every key must be a sound the template plays.
- check: what tools/efecheck.py --composed expects: "hue", the main hue in degrees.

    python -m tools.efecompose sheet KEY [--out PNG]     template above, composed below, one tick per column
"""
import colorsys
import json
import math
import os
import struct

from tools import efescript
from tools import efesim as S

CHUNK = 0x5000
HEADER = 0x34
OWN_EFFECTS = 'content/battle/own-effects.json'
ARCHIVE = 'extracted/ETCHI/EFEDAT.EFE'


def header(chunk):
    return dict(zip(efescript.FIELDS, struct.unpack_from('<13i', chunk, 0)))


def tim_layout(chunk):
    """(CLUT offset, rows, colours per row, pixel offset, words per row, rows) of the chunk's 4-bit TIM."""
    t = HEADER + header(chunk)['timStart']
    magic, flags = struct.unpack_from('<2I', chunk, t)
    if magic != 0x10 or flags != 0x8:
        raise ValueError(f'composed effect: the template\'s texture is not a 4-bit TIM with a palette ({flags:#x})')
    clen, _x, _y, cw, ch = struct.unpack_from('<I4H', chunk, t + 8)
    p = t + 8 + clen
    _plen, _x, _y, pw, ph = struct.unpack_from('<I4H', chunk, p)
    return t + 20, ch, cw, p + 12, pw, ph


# ----------------------------------------------------------------- colour

def parse_colour(c):
    c = c.lstrip('#')
    return tuple(int(c[i:i + 2], 16) for i in (0, 2, 4))


def from15(c):
    return tuple(((c >> s) & 0x1F) * 255 // 31 for s in (0, 5, 10))


def to15(rgb, stp):
    r, g, b = (max(0, min(31, round(x * 31 / 255))) for x in rgb)
    v = r | g << 5 | b << 10
    if v == 0:                      # 0 is transparent: keep a visible colour visible
        v = 1 << 10 if b >= r and b >= g else 1 << 5 if g >= r else 1
    return v | (0x8000 if stp else 0)


def luminance(rgb):
    return (0.299 * rgb[0] + 0.587 * rgb[1] + 0.114 * rgb[2]) / 255


def mapper(spec):
    """rgb (0-255) -> rgb under the entry's recolour."""
    if 'ramp' in spec:
        ramp = [parse_colour(c) for c in spec['ramp']]
        if len(ramp) < 2:
            raise ValueError('composed effect: a ramp needs at least two colours')

        def f(rgb):
            x = max(0.0, min(1.0, max(rgb) / 255)) * (len(ramp) - 1)       # brightness: the value, not the hue
            i = min(int(x), len(ramp) - 2)
            t = x - i
            return tuple(round(a + (b - a) * t) for a, b in zip(ramp[i], ramp[i + 1]))
        return f
    if 'hue' in spec:
        hue, floor = spec['hue'] % 360 / 360, spec.get('saturation', 0.6)

        def f(rgb):
            _h, s, v = colorsys.rgb_to_hsv(*(x / 255 for x in rgb))
            return tuple(round(x * 255) for x in colorsys.hsv_to_rgb(hue, max(s, floor), v))
        return f
    raise ValueError('composed effect: recolour needs "ramp" or "hue"')


def recolour_palettes(chunk, spec):
    clut, rows, cols, *_ = tim_layout(chunk)
    f = mapper(spec)
    keep = spec.get('rows')
    for r in range(rows):
        if keep is not None and r not in keep:
            continue
        for k in range(cols):
            at = clut + 2 * (r * cols + k)
            c = struct.unpack_from('<H', chunk, at)[0]
            if c == 0:
                continue
            struct.pack_into('<H', chunk, at, to15(f(from15(c)), c & 0x8000))


def code_bytes(chunk):
    """The set of chunk offsets (from the header's end) that hold script instructions."""
    out = set()
    for pc, (_text, size) in efescript.disassemble(chunk).items():
        out.update(range(pc, pc + size))
    return out


def script_colours(chunk, launch):
    """[offset from the header's end] of the colour vectors (three int32) the template's script hands the engine
    and never writes: the ones a recolour may change. A run of the template finds them."""
    sim = run(chunk, launch)
    code = code_bytes(chunk)
    before = chunk[HEADER:]
    out = []
    for addr in sorted(sim.colours):
        o = addr - S.BASE
        if o < 0 or o + 12 > len(before) or code & set(range(o, o + 12)):
            continue
        if bytes(sim.mem[o:o + 12]) != bytes(before[o:o + 12]):
            continue                # the script computes it
        rgb = struct.unpack_from('<3i', before, o)
        if all(0 <= x <= 255 for x in rgb):
            out.append(o)
    return out


def recolour_script(chunk, spec, offsets):
    f = mapper(spec)
    for o in offsets:
        rgb = struct.unpack_from('<3i', chunk, HEADER + o)
        _h, s, v = colorsys.rgb_to_hsv(*(min(255, x) / 255 for x in rgb))
        if s < 0.15:
            continue                # a grey tint only scales the texture's own colours
        struct.pack_into('<3i', chunk, HEADER + o, *f(rgb))


def sound_sites(chunk):
    """[(offset of the pushed id from the header's end, sound id)] of every `push N` followed by `sub playSound`."""
    insts = efescript.disassemble(chunk)
    out = []
    for pc, (text, size) in sorted(insts.items()):
        nxt = insts.get(pc + size)
        if text.startswith('push ') and nxt and nxt[0] == 'sub playSound':
            out.append((pc + 2, struct.unpack_from('<h', chunk, HEADER + pc + 2)[0]))
    return out


def remap_sounds(chunk, template, mapping):
    sites = sound_sites(template)
    played = {sid for _o, sid in sites}
    missing = sorted(int(k) for k in mapping if int(k) not in played)
    if missing:
        raise ValueError(f'composed effect: the template plays no sound {missing} (it plays {sorted(played)})')
    n = 0
    for o, sid in sites:
        if str(sid) in mapping:
            struct.pack_into('<h', chunk, HEADER + o, int(mapping[str(sid)]))
            n += 1
    return n


# ----------------------------------------------------------------- shape

def tmd_vertex_ranges(chunk):
    """[(offset, count)] of the TMD objects' vertex tables."""
    h = header(chunk)
    if h['tmdStart'] == h['tmdEnd']:
        return []
    base = HEADER + h['tmdStart']
    n = struct.unpack_from('<I', chunk, base + 8)[0]
    out = []
    for i in range(n):
        vt, nv = struct.unpack_from('<2I', chunk, base + 12 + 28 * i)
        out.append((base + 12 + vt, nv))
    return out


def rescale(chunk, scale):
    s = scale if isinstance(scale, (list, tuple)) else (scale, scale, scale)
    done = set()
    for at, n in tmd_vertex_ranges(chunk):
        for k in range(n):
            p = at + 8 * k
            if p in done:
                continue
            done.add(p)
            v = struct.unpack_from('<3h', chunk, p)
            struct.pack_into('<3h', chunk, p, *(max(-32768, min(32767, round(x * f))) for x, f in zip(v, s)))


def texture_rect(chunk, rect):
    """[(offset, length)] of the pixel bytes of a texel rectangle [u, v, w, h] of the chunk's TIM (u, w even)."""
    _clut, _rows, _cols, pix, words, height = tim_layout(chunk)
    u, v, w, h = rect
    if u % 2 or w % 2 or u < 0 or v < 0 or u + w > 4 * words or v + h > height:
        raise ValueError(f'composed effect: texel rectangle {rect} is outside the texture or not on a byte')
    return [(pix + y * 2 * words + u // 2, w // 2) for y in range(v, v + h)]


def copy_texture(chunk, spec, archive):
    """Texels (and their palette row) from another disc chunk over a rectangle of the template's texture:
    {"from": chunk, "rect": [u, v, w, h], "to": [u, v] (default the same), "palettes": [[from row, to row]]}."""
    src = template_of(archive, {'name': 'texture', 'stands_for': spec['from']})
    u, v, w, h = spec['rect']
    to = spec.get('to', [u, v])
    for (a, n), (b, _n) in zip(texture_rect(src, spec['rect']), texture_rect(chunk, [*to, w, h])):
        chunk[b:b + n] = src[a:a + n]
    sclut, _r, scols, *_ = tim_layout(src)
    dclut, drows, dcols, *_ = tim_layout(chunk)
    for f, t in spec.get('palettes', []):
        if t >= drows or scols != dcols:
            raise ValueError(f'composed effect: palette row {t} does not fit the template\'s palette')
        chunk[dclut + 2 * t * dcols:dclut + 2 * (t + 1) * dcols] = src[sclut + 2 * f * scols:sclut + 2 * (f + 1) * scols]


# ----------------------------------------------------------------- compose

def launch_table(chunk):
    from tools.derive.steps import effects as E
    return E.launch_table(chunk)


def template_of(archive, entry):
    t = entry['stands_for']
    if not 0 <= t < 122:
        raise ValueError(f'composed effect {entry["name"]}: the template must be one of the disc\'s chunks')
    return bytes(archive[t * CHUNK:(t + 1) * CHUNK])


def compose(template, spec, archive=None):
    """The composed chunk (bytes) and what was changed. archive: the disc's effect archive, for "texture"."""
    out = bytearray(template)
    info = {}
    for t in spec.get('texture', []):
        if archive is None:
            raise ValueError('composed effect: "texture" needs the effect archive')
        copy_texture(out, t, archive)
        info.setdefault('texture from', []).append(t['from'])
    if 'recolour' in spec:
        recolour_palettes(out, spec['recolour'])
        offsets = script_colours(template, launch_table(template))
        recolour_script(out, spec['recolour'], offsets)
        info['script colours'] = len(offsets)
    if 'scale' in spec:
        rescale(out, spec['scale'])
    if 'sounds' in spec:
        info['sounds'] = remap_sounds(out, template, spec['sounds'])
    unknown = set(spec) - {'recolour', 'scale', 'texture', 'sounds'}
    if unknown:
        raise ValueError(f'composed effect: unknown fields {sorted(unknown)}')
    info['kept'] = header(out)['tmdEnd'] + HEADER
    return bytes(out), info


def allowed_bytes(chunk, spec):
    """The offsets a composition may change: the TIM's palette, the TMD's vertices and the script's static
    colour vectors."""
    out = set()
    clut, rows, cols, *_ = tim_layout(chunk)
    out.update(range(clut, clut + 2 * rows * cols))
    for t in spec.get('texture', []):
        u, v, w, h = t['rect']
        for at, n in texture_rect(chunk, [*t.get('to', [u, v]), w, h]):
            out.update(range(at, at + n))
    if 'scale' in spec:
        for at, n in tmd_vertex_ranges(chunk):
            out.update(range(at, at + 8 * n))
    for o in script_colours(chunk, launch_table(chunk)):
        out.update(range(HEADER + o, HEADER + o + 12))
    if 'sounds' in spec:
        for o, sid in sound_sites(chunk):
            if str(sid) in spec['sounds']:
                out.update(range(HEADER + o, HEADER + o + 2))
    return out


# ----------------------------------------------------------------- running and drawing

def run(chunk, launch, limit=240, seed=1):
    """The chunk run in tools/efesim against the stage efecheck uses (caster 1, target 2, two more enemies)."""
    from tools import efecheck as C
    sim = S.Sim(chunk, C.stage(launch), 1, 2, seed=seed)
    for _ in range(limit):
        sim.step(reset_hits=False)
        if not sim.live():
            break
    return sim


def frames(chunk, sim, w=160, h=100, ticks=None):
    """{tick: pixels} of the run, from efecheck's side camera."""
    from tools import efecheck as C
    _c2, cam = C.cameras(w, h)
    ticks = range(1, sim.tick + 1) if ticks is None else ticks
    return {t: S.render(chunk, sim, t, cam, fighters=False, bg=(0, 0, 0)) for t in ticks}


def lit_ticks(sim):
    return sorted({d[0] for d in sim.draws} | {s[0] for s in sim.sprites} | {q[0] for q in sim.quads})


def _box(pixels, w):
    xs = [i % w for i, c in enumerate(pixels) if c != (0, 0, 0)]
    ys = [i // w for i, c in enumerate(pixels) if c != (0, 0, 0)]
    return (min(xs), min(ys), max(xs) + 1, max(ys) + 1) if xs else None


def sheet(template, ours, launch, path, cols=8, tile=240):
    """Template's frames above ours at cols ticks spread over the lit part of the run. Each column is cropped
    around what either draws at that tick, every column to the same size, so shapes show at a readable size."""
    from tools import image as img
    a, b = run(template, launch), run(ours, launch)
    lit = lit_ticks(a)
    if not lit:
        raise ValueError('composed effect: the template draws nothing in the simulation')
    ticks = sorted({lit[round(i * (len(lit) - 1) / max(1, cols - 1))] for i in range(cols)})
    w, h = 640, 400
    fa, fb = frames(template, a, w, h, ticks), frames(ours, b, w, h, ticks)
    boxes = {}
    for t in ticks:
        bs = [x for x in (_box(fa[t], w), _box(fb[t], w)) if x]
        if bs:
            boxes[t] = (min(x[0] for x in bs), min(x[1] for x in bs), max(x[2] for x in bs), max(x[3] for x in bs))
    side = max([max(x[2] - x[0], x[3] - x[1]) for x in boxes.values()] or [w])
    side = min(h, max(24, round(side * 1.15)))
    out = img.new('RGB', (len(ticks) * (tile + 4), 2 * tile + 4), (60, 60, 60))
    for n, t in enumerate(ticks):
        x0, y0, x1, y1 = boxes.get(t, (0, 0, w, h))
        cx, cy = (x0 + x1) // 2, (y0 + y1) // 2
        left, top = max(0, min(w - side, cx - side // 2)), max(0, min(h - side, cy - side // 2))
        for row, px in enumerate((fa[t], fb[t])):
            full = img.frombytes('RGB', (w, h), bytes(c for p in px for c in p))
            part = full.crop((left, top, left + side, top + side)).resize((tile, tile), img.Resampling.NEAREST)
            out.paste(part, (n * (tile + 4), row * (tile + 4)))
    out.save(path)
    return ticks


def load_entry(key, root='.'):
    with open(os.path.join(root, OWN_EFFECTS)) as f:
        spec = json.load(f)
    e = spec[str(key)]
    if 'compose' not in e:
        raise SystemExit(f'own effect {key} is not composed')
    return e


def main():
    import argparse
    ap = argparse.ArgumentParser(description=__doc__.split('\n\n')[0])
    sub = ap.add_subparsers(dest='cmd', required=True)
    p = sub.add_parser('sheet', help='render the template and the composed chunk side by side')
    p.add_argument('key')
    p.add_argument('--archive', default=ARCHIVE)
    p.add_argument('--out')
    a = ap.parse_args()
    with open(a.archive, 'rb') as f:
        archive = f.read()
    e = load_entry(a.key)
    template = template_of(archive, e)
    ours, info = compose(template, e['compose'], archive)
    out = a.out or f'{a.key}-{e["name"].replace(" ", "")}.png'
    ticks = sheet(template, ours, launch_table(template), out)
    print(f'{a.key} {e["name"]}: {out}, ticks {ticks}; ' + ', '.join(f'{k} {v}' for k, v in info.items()))


if __name__ == '__main__':
    main()
