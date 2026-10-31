#!/usr/bin/env python3
"""The map signs translated, pasted into the player's disc backgrounds (docs/mods/language.md, MAP SIGNS).

  signs.py OUTDIR [--extracted DIR] [--file DEST=SRC ...]
  signs.py --make-cutouts [--src DIR] [--extracted DIR ...]     (the developer: tools/image.py)
  signs(out, extracted, files)   the same from Python (tools/derive's signs step, D9); files {DEST: SRC}

Our sign edits are masked RGB deltas (tools/localize/cutout.py:
content/localized/signs/delta/<lang>/<sign>.png and index.json). The build adds
the deltas to the player's canonical disc crop to recover the generator edit,
then applies the original threshold and one-pixel mask growth at each placement.
Only differences and masks are committed; unchanged original colours are read
from the disc. Requantization and sprite pasting are unchanged.

--file DEST=SRC (DEST a disc path, MAP/MAP1/MAYO10.TFS): the build puts SRC on the disc in place of the disc's file (a story
mod's retouch, the story compiler's map with its Digimon): the sign is pasted into SRC. Which pixels are the sign's is
still decided on the disc's own background, the one the edits were made from, so a retouch beside the sign is kept.

No Pillow (stage 9, the owner's decision of 2026-10-26: the player's build has none): the cut-outs are read with
dwmap.png_read; the difference mask, its one-pixel growth (Pillow's MaxFilter(3)) and the paste are plain Python.

--make-cutouts (the developer) reads private full edits and sized copies from
build/localized-src/signs. It preserves the union mask across all supplied bases
and stores a delta against the first placement's canonical crop. Every supplied
base must have that same crop; unknown crops fail rather than guessing.
"""
import argparse, os, struct, sys, tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, os.path.join(ROOT, 'tools'))
sys.path.insert(0, os.path.join(ROOT, 'content', 'localized', 'signs'))
import dwmap  # noqa: E402
from jobs import JOBS  # noqa: E402
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)
from tools.localize import cutout  # noqa: E402

# a sign's job -> the maps that show it (the Toy Town interiors share theirs; the Mt. Panorama arrow is on two maps)
MAPS = {'twnb_open': [f'MAP/MAP13/TWNB1{i}' for i in range(6)] + ['MAP/MAP14/TWNB16', 'MAP/MAP14/TWNB17'],
        'twnb_tool': [f'MAP/MAP13/TWNB1{i}' for i in range(6)] + ['MAP/MAP14/TWNB16', 'MAP/MAP14/TWNB17'],
        'mayo01_2': ['MAP/MAP8/MAYO01_2', 'MAP/MAP8/MAYO02_2']}
EXTRA = {'room02': ('ROOM02', (60, 232, 228, 344))}   # the first test, made before jobs.py
THRESHOLD = 40                                         # summed RGB difference that counts as changed


class Pixels:
    """w x h pixels row-major, with the two things sprite_paste asks of an image (width/height, getpixel)."""
    def __init__(self, w, h, px):
        self.width, self.height, self.px = w, h, px

    def getpixel(self, xy):
        return self.px[xy[1] * self.width + xy[0]]


def sign_mask(orig, new, w, h, inside=None):
    """The pixels the edit changed (summed RGB difference above THRESHOLD: 255, else 0; only where inside, the cut-out's
    alpha, says there is a pixel of ours), grown by one pixel (the maximum of each 3 x 3 neighbourhood, the image's
    edge repeated: Pillow's MaxFilter(3), which it replaces)."""
    d = [255 if abs(a[0] - b[0]) + abs(a[1] - b[1]) + abs(a[2] - b[2]) > THRESHOLD else 0 for a, b in zip(orig, new)]
    if inside is not None:
        d = [v if i else 0 for v, i in zip(d, inside)]
    out = [0] * (w * h)
    for y in range(h):
        rows = [d[yy * w:(yy + 1) * w] for yy in (max(0, y - 1), y, min(h - 1, y + 1))]
        for x in range(w):
            x0, x1 = max(0, x - 1), min(w, x + 2)
            if any(r[xx] for r in rows for xx in range(x0, x1)):
                out[y * w + x] = 255
    return out


def sprite_paste(m, t, new, mask, x0, y0):
    """The sprites drawn over the sign (MAP instances: pieces of the background that cover the characters) get the
    edit too, where their pixel is opaque and the edit changed the background: requantized to the sprite's palette.
    -> how many pixels changed"""
    box = (x0, y0, x0 + new.width, y0 + new.height)
    tims = [dwmap.TIM(r) for r in m.tims]
    n = 0
    for i in dwmap.covering_instances(m, *box):
        inst = m.instances[i]
        for f in {f for f in inst['frames'] if 0 <= f < len(m.sprites)}:
            sp = m.sprites[f]
            bpp = 4 if 0 <= sp['clut'] < 16 else 8
            page = 384 + (sp['texX'] // 256) * (128 if bpp == 8 else 64)
            for k, tim in enumerate(tims):
                if tim.bpp != bpp:
                    continue
                per = 2 if bpp == 8 else 4                       # pixels per VRAM halfword
                u0 = (page - tim.x) * per + sp['texX'] % 256
                if not (0 <= u0 and u0 + sp['width'] <= tim.w * per and tim.y <= sp['texY'] and sp['texY'] + sp['height'] <= tim.y + tim.h):
                    continue
                raw = bytearray(m.tims[k])
                pix = 8 + (struct.unpack_from('<I', raw, 8)[0] if tim.flag & 8 else 0) + 12
                cx, cy, cw, ch, cl = tim.clut
                if sp['clut'] < 0:
                    clut = t.cluts[0]
                elif sp['clut'] < 16:
                    clut = cl[16 * sp['clut']:16 * sp['clut'] + 16] if len(cl) >= 16 * (sp['clut'] + 1) else cl[:16]
                else:
                    row = sp['clut'] + 468 - cy
                    clut = cl[row * cw:(row + 1) * cw] if 0 <= row < ch else cl[:cw]
                rq = dwmap.Requant([dwmap.bgr555_to_rgb(c) for c in clut], clut)
                stride = tim.w * 2
                for sy in range(sp['height']):
                    for sx in range(sp['width']):
                        X, Y = inst['x'] + sx - x0, inst['y'] + sy - y0
                        if not (0 <= X < new.width and 0 <= Y < new.height) or not mask.getpixel((X, Y)):
                            continue
                        u, v = u0 + sx, sp['texY'] - tim.y + sy
                        o = pix + v * stride + (u if bpp == 8 else u // 2)
                        old = raw[o] if bpp == 8 else (raw[o] >> (4 * (u & 1))) & 15
                        if old == 0:
                            continue                              # transparent: the background shows
                        val = rq(*new.getpixel((X, Y)))
                        if bpp == 8:
                            raw[o] = val
                        else:
                            raw[o] = (raw[o] & ~(15 << (4 * (u & 1)))) | ((val & 15) << (4 * (u & 1)))
                        n += 1
                m.tims[k] = bytes(raw)
                tims[k] = dwmap.TIM(m.tims[k])
                break
    return n


def find_map(name, ext):
    for d, _, fs in os.walk(os.path.join(ext, 'MAP')):
        if f'{name}.MAP' in fs:
            return os.path.relpath(os.path.join(d, name), ext).replace(os.sep, '/')
    sys.exit(f'no {name}.MAP in {ext}')


def places(sign, extracted):
    """-> [(map path without extension, crop box)] where the sign is shown ([] for a name that is no sign)"""
    import json
    audit = json.load(open(os.path.join(ROOT, 'content', 'localized', 'signs', 'audit.json')))
    copies = {f'audit-{k}': [(c['map'], c['box']) for c in v['copies']] for k, v in audit.items()}
    boxes = {j[0]: (j[1], j[2]) for j in JOBS}
    boxes.update(EXTRA)
    if sign in copies:
        return copies[sign]
    if sign in boxes:
        src, box = boxes[sign]
        return [(mp, box) for mp in MAPS.get(sign, [find_map(src, extracted)])]
    return []


def disc_crop(extracted, mp, box, cache):
    """-> the disc's own day background inside box, [(r, g, b)] row-major, and its (MapFile, TfsFile)"""
    if mp not in cache:
        cache[mp] = (dwmap.MapFile(open(os.path.join(extracted, mp + '.MAP'), 'rb').read()),
                     dwmap.TfsFile(open(os.path.join(extracted, mp + '.TFS'), 'rb').read()))
    m0, t0 = cache[mp]
    W, H, idx = t0.image_indices(m0)
    pal = t0.palette_rgb(0)
    x0, y0, x1, y1 = box
    return [tuple(pal[idx[y][x]][:3]) for y in range(y0, y1) for x in range(x0, x1)]


def signs(out, extracted=None, files=None, languages=('en', 'es')):
    """The signs of languages (those with cut-outs) into out (see the module's docstring): extracted the disc's files
    (default the repository's), files {DEST: SRC} what --file gives. -> the files.txt lines"""
    extracted = extracted or os.path.join(ROOT, 'extracted')
    given = dict(files or {})

    def source(mp, ext):
        """the file the disc carries for map path mp (no extension) + ext: --file's, else the disc's"""
        return given.get(mp + ext) or os.path.join(extracted, mp + ext)
    edits = {}                                             # (lang, map path) -> TfsFile
    maps = {}                                              # the disc's own map and background: the edits were made from them
    placed = {}                                            # map path -> the MapFile the disc carries (where the sign goes)
    mapcopies = {}                                         # (lang, map path) -> MapFile: its sprites edited too
    sprites_changed = set()

    def mapcopy(lang, mp):
        if (lang, mp) not in mapcopies:
            mapcopies[(lang, mp)] = dwmap.MapFile(open(source(mp, '.MAP'), 'rb').read())
        return mapcopies[(lang, mp)]
    with tempfile.TemporaryDirectory() as tmp:
        for lang in sorted({n.split('/')[0] for n in cutout.index()} - {'fromjp'}, reverse=True):   # (pt-br, ..., en)
            if lang not in languages:
                continue
            for sign in cutout.names(lang):
                canonical_map, canonical_box = places(sign, extracted)[0]
                base = disc_crop(extracted, canonical_map, canonical_box, maps)
                cw, ch, cut = cutout.load(f'{lang}/{sign}', base)
                new = [p[:3] for p in cut]
                inside = [p[3] for p in cut]
                for mp, box in places(sign, extracted):
                    orig = disc_crop(extracted, mp, box, maps)
                    key = (lang, mp)
                    if key not in edits:
                        edits[key] = dwmap.TfsFile(open(source(mp, '.TFS'), 'rb').read())
                    t = edits[key]
                    if mp not in placed:
                        placed[mp] = dwmap.MapFile(open(source(mp, '.MAP'), 'rb').read())
                    m = placed[mp]
                    x0, y0, x1, y1 = box
                    w, h = x1 - x0, y1 - y0
                    if (w, h) != (cw, ch):
                        sys.exit(f'{lang}/{sign}: the cut-out is for a {cw}x{ch} crop, {mp} shows it at {box}')
                    mask = sign_mask(orig, new, w, h, inside)
                    p = os.path.join(tmp, f'{lang}-{sign}-{os.path.basename(mp)}.png')
                    dwmap.png_write(p, w, h, [bytes(c for i in range(y * w, (y + 1) * w) for c in (*new[i], mask[i]))
                                              for y in range(h)], mode='RGBA')
                    dwmap.bg_paste(m, t, p, x0, y0)
                    if sprite_paste(mapcopy(lang, mp), t, Pixels(w, h, new), Pixels(w, h, mask), x0, y0):
                        sprites_changed.add((lang, mp))
        lines = []
        for (lang, mp), t in sorted(edits.items()):
            dest = os.path.join(out, lang, mp + '.TFS')
            os.makedirs(os.path.dirname(dest), exist_ok=True)
            open(dest, 'wb').write(t.build())
            lines.append(f'{lang} {mp}.TFS')
        for lang, mp in sorted(sprites_changed):
            dest = os.path.join(out, lang, mp + '.MAP')
            open(dest, 'wb').write(mapcopies[(lang, mp)].build())
            lines.append(f'{lang} {mp}.MAP')
    os.makedirs(out, exist_ok=True)
    open(os.path.join(out, 'files.txt'), 'w').write('\n'.join(lines) + '\n')
    print(f'{out}: {len(lines)} backgrounds with translated signs')
    return lines


def make_cutouts(src=None, extracted=None):
    """The developer's: every edit in src/<lang>/ cut to the pixels it changed (see the module's docstring)
    -> the names written"""
    from tools.localize import sized
    src = src or cutout.SRC
    if not extracted:
        extracted = [os.path.join(ROOT, 'extracted')]
        jp = os.path.join(ROOT, 'build', 'discs', 'base-jp1', 'extracted')
        if os.path.isdir(os.path.join(jp, 'MAP')):
            extracted.append(jp)
    caches = {e: {} for e in extracted}
    done, scaled = [], []
    for lang in sorted(os.listdir(src)):
        d = os.path.join(src, lang)
        if lang in ('sized', 'fromjp') or not os.path.isdir(d):
            continue
        for f in sorted(os.listdir(d)):
            sign = f[:-4]
            if not f.endswith('.png') or not places(sign, extracted[0]):
                continue
            size, new, union = None, None, None
            for ext in extracted:
                for mp, box in places(sign, ext):
                    x0, y0, x1, y1 = box
                    w, h = x1 - x0, y1 - y0
                    if size is None:
                        size = (w, h)
                        # (a new edit's sized copy is written once, then kept: the cut-out does not follow Pillow)
                        folder = os.path.join(src, 'sized', lang)
                        made = any(o.rsplit('-', 1)[0] == sign for o in (os.listdir(folder) if os.path.isdir(folder) else []))
                        new = sized.rgb_at(os.path.join(d, f), size, folder, not made, scaled)
                        union = [0] * (w * h)
                    elif size != (w, h):
                        sys.exit(f'{lang}/{sign}: shown at crops of two sizes, {size} and {(w, h)} ({mp})')
                    mask = sign_mask(disc_crop(ext, mp, box, caches[ext]), new, w, h)
                    union = [a | b for a, b in zip(union, mask)]
            w, h = size
            mp, box = places(sign, extracted[0])[0]
            base = disc_crop(extracted[0], mp, box, caches[extracted[0]])
            for ext in extracted:
                other_mp, other_box = places(sign, ext)[0]
                if disc_crop(ext, other_mp, other_box, caches[ext]) != base:
                    raise ValueError(f'{lang}/{sign}: supplied bases have different canonical crops')
            cutout.save(f'{lang}/{sign}', w, h,
                        [(*new[i], 255) if union[i] else (0, 0, 0, 0) for i in range(w * h)], base)
            done.append(f'{lang}/{sign}')
    print(f'{cutout.CUTOUTS}: {len(done)} sign cut-outs from {src} (backgrounds of {", ".join(extracted)})')
    if scaled:
        print(f'note: {len(scaled)} edits had no sized copy in {src}/sized and were scaled here with tools/image.py')
    return done


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('out', nargs='?')
    ap.add_argument('--extracted', action='append', help='the disc\'s files (default extracted/); several with --make-cutouts')
    ap.add_argument('--file', action='append', default=[], help='DEST=SRC: the file the disc gets in place of DEST')
    ap.add_argument('--make-cutouts', action='store_true', help='remake content/localized/signs/delta from --src')
    ap.add_argument('--src', help=f'the full edits (default {os.path.relpath(cutout.SRC, ROOT)})')
    ap.add_argument('--languages', default='en,es', help='comma-separated languages (en,es,pt-br,fr,de,it,ja,ca)')
    a = ap.parse_args()
    if a.make_cutouts:
        make_cutouts(a.src, [os.path.abspath(e) for e in a.extracted or []])
        return
    if not a.out:
        ap.error('OUTDIR is needed')
    if a.extracted and len(a.extracted) > 1:
        ap.error('one --extracted for a build')
    from tools.languages import CODES
    languages = tuple(a.languages.split(','))
    if len(set(languages)) != len(languages) or any(lang not in CODES for lang in languages):
        ap.error('--languages must contain unique languages from ' + ','.join(CODES))
    signs(a.out, (a.extracted or [os.path.join(ROOT, 'extracted')])[0], dict(f.split('=', 1) for f in a.file),
          languages=languages)


if __name__ == '__main__':
    main()
