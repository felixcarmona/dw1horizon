"""Masked sign deltas applied to a crop read from the player's own disc.

The PNG's RGB channels are (edit - disc crop) modulo 256; alpha is the existing
paste mask. Unchanged crop pixels therefore store zero differences. No absolute
crop colours are published. index.json records [w, h, x, y, base RGB SHA-1], so
an unrecognised crop fails before it could produce silently different artwork.
Full generator edits remain private in build/localized-src/signs.

load(name, base) returns the reconstructed RGBA edit; save(name, w, h, px, base)
regenerates its delta. base is the canonical crop's row-major RGB pixels (the
first place in signs.places, or fromjp.art_map for Japanese sprite art).
"""
import hashlib
import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
CUTOUTS = os.path.join(ROOT, 'content', 'localized', 'signs', 'delta')
SRC = os.path.join(ROOT, 'build', 'localized-src', 'signs')
INDEX = os.path.join(CUTOUTS, 'index.json')
_index = None
_making = False        # (the developer's --make-cutouts may start from none)


def _dwmap():
    if os.path.join(ROOT, 'tools') not in sys.path:
        sys.path.insert(0, os.path.join(ROOT, 'tools'))
    import dwmap
    return dwmap


def index():
    global _index
    if _index is None:
        _index = json.load(open(INDEX)) if os.path.isfile(INDEX) else None
        if _index is None and not _making:
            sys.exit(f'no {os.path.relpath(INDEX, ROOT)}: the signs\' cut-outs are missing')
        _index = _index or {}
    return _index


def names(family):
    """the signs of a family (en, es, fromjp) that have a cut-out, sorted"""
    return sorted(n.split('/', 1)[1] for n in index() if n.split('/', 1)[0] == family)


def base_sha1(base):
    return hashlib.sha1(bytes(c for p in base for c in p)).hexdigest()


def load(name, base):
    w, h, x0, y0, expected = index()[name]
    if len(base) != w * h or base_sha1(base) != expected:
        raise ValueError(f'{name}: source sign crop checksum mismatch')
    bw, bh, mode, rows, _ = _dwmap().png_read(os.path.join(CUTOUTS, name + '.png'), alpha=True)
    if mode != 'RGBA' or x0 + bw > w or y0 + bh > h:
        sys.exit(f'{name}.png: {bw}x{bh} {mode} at ({x0}, {y0}) does not fit its {w}x{h} crop')
    px = [(0, 0, 0, 0)] * (w * h)
    for y in range(bh):
        r = rows[y]
        for x in range(bw):
            if r[4 * x + 3]:
                i = (y0 + y) * w + x0 + x
                px[i] = tuple((r[4 * x + c] + base[i][c]) % 256 for c in range(3)) + (r[4 * x + 3],)
    return w, h, px


def save(name, w, h, px, base):
    """px w x h (r, g, b, a): writes the alpha's bounding box (a 1 x 1 transparent pixel when it is empty: the sign is
    still pasted, with nothing)"""
    global _making
    _making = True
    if len(base) != w * h or len(px) != w * h:
        raise ValueError(f'{name}: pixels do not fit the crop')
    expected = base_sha1(base)
    px = [tuple((p[c] - b[c]) % 256 for c in range(3)) + (p[3],) if p[3] else (0, 0, 0, 0)
          for p, b in zip(px, base)]
    on = [i for i, p in enumerate(px) if p[3]]
    if on:
        x0, x1 = min(i % w for i in on), max(i % w for i in on) + 1
        y0, y1 = min(i // w for i in on), max(i // w for i in on) + 1
    else:
        x0, y0, x1, y1 = 0, 0, 1, 1
    rows = [bytes(c for x in range(x0, x1) for c in (px[y * w + x] if px[y * w + x][3] else (0, 0, 0, 0)))
            for y in range(y0, y1)]
    path = os.path.join(CUTOUTS, name + '.png')
    os.makedirs(os.path.dirname(path), exist_ok=True)
    _dwmap().png_write(path, x1 - x0, y1 - y0, rows, mode='RGBA')
    ix = index()
    ix[name] = [w, h, x0, y0, expected]
    with open(INDEX, 'w') as f:
        f.write('{\n' + ',\n'.join(f'  {json.dumps(k)}: {json.dumps(v)}' for k, v in sorted(ix.items())) + '\n}\n')
