#!/usr/bin/env python3
"""The translated textures, made from the player's disc (docs/mods/language.md).

  build.py OUTDIR [--extracted DIR]
  build(out, extracted, run_with=None, scratch=None)   the same from Python (tools/derive's localize step, D10)

Runs the word recipes of textures/ (our letters drawn into each texture's own pixels: fi-info, systemw, misc,
cards-cups) on the textures of the disc and writes whole disc files:

  OUTDIR/es/<disc path>   the Spanish copy of a file (ETCDAT/FI_INFO.TIM, ETCDAT/ETCTIM.BIN, CARD/CARD.ALL, ...)
  OUTDIR/en/<disc path>   a file the English game shows changed too (the cards' names in Latin letters)
  OUTDIR/files.txt        one line per file: "<lang> <disc path>"

Only the pixel indices change; each TIM keeps its header, CLUT and size.

The recipes run in this process (tools/derive/runner.py run_script; `run_with` is the caller's, tools/derive's ctx.run),
each in a copy of its folder (they write their idx files and previews beside themselves) with the disc's files from
LOCALIZE_EXTRACTED. rule: the recipes share module names (idx, pixfont, tex, build), so the modules a recipe imported
from its copy are forgotten after it runs, wherever the copy is.
"""
import argparse, os, shutil, struct, sys, tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)
from tools import mediancut  # noqa: E402
DELTA = os.path.join(ROOT, 'content', 'localized', 'tournament', 'delta')   # <lang>/<banner>.png
DELTA_SRC = os.path.join(ROOT, 'build', 'localized-src', 'tournament')      # the developer's: <lang>/, sized/<lang>/


def tim_entries(data):
    """-> [(offset of the pixel data, bpp, width in pixels, height)] of a TIM or a stack of TIMs (ETCTIM.BIN, STDTIM.BIN)"""
    out, off = [], 0
    while off + 8 <= len(data):
        magic, flag = struct.unpack_from('<II', data, off)
        if magic != 0x10:
            break
        p = off + 8
        if flag & 8:
            p += struct.unpack_from('<I', data, p)[0]
        ln, _, _, w, h = struct.unpack_from('<IHHHH', data, p)
        bpp = flag & 3
        out.append((p + 12, bpp, {0: w * 4, 1: w * 2, 2: w}[bpp], h))
        off = (p + ln + 3) & ~3
    return out


def put_indices(data, entry, idx):
    """data (bytearray of the file) with entry's pixels replaced by idx (one index per pixel, row-major)"""
    pos, bpp, w, h = tim_entries(data)[entry]
    if len(idx) != w * h:
        sys.exit(f'{len(idx)} indices for a {w}x{h} image')
    if bpp == 0:
        packed = bytes(idx[i] & 15 | (idx[i + 1] & 15) << 4 for i in range(0, len(idx), 2))
    elif bpp == 1:
        packed = bytes(idx)
    else:
        sys.exit('a 16-bit TIM has no indices')
    data[pos:pos + len(packed)] = packed


def tim_rgb(data, entry=0):
    """-> (w, h, RGBA pixels row-major, the TIM's CLUT offset, CLUT colours) of an 8-bit TIM; colour 0x0000 is
    transparent"""
    off = 0
    magic, flag = struct.unpack_from('<II', data, off)
    p = off + 8
    ln, cx, cy, cw, ch = struct.unpack_from('<IHHHH', data, p)
    clut = list(struct.unpack_from('<%dH' % cw, data, p + 12))
    pos, bpp, w, h = tim_entries(data)[entry]
    def c15(v): return (0, 0, 0, 0) if v == 0 else ((v & 31) << 3, ((v >> 5) & 31) << 3, ((v >> 10) & 31) << 3, 255)
    return w, h, [c15(clut[i]) for i in data[pos:pos + w * h]], p + 12, clut


def put_rgb(data, px, transparent):
    """data (bytearray, an 8-bit TIM with a 256-colour CLUT) with px (RGB pixels at the TIM's size) quantized into it:
    a new palette of 255 colours (tools/mediancut.py: Pillow's MEDIANCUT, which it replaces, the same palette and
    indices), index 0 the transparent 0x0000 for the pixels transparent(r, g, b) says"""
    w, h, _, clut_at, _ = tim_rgb(bytes(data))
    if len(px) != w * h:
        sys.exit(f'{len(px)} pixels for a {w}x{h} TIM')
    pal, q = mediancut.quantize(px, 255)
    pal = (pal + [(0, 0, 0)] * 255)[:255]
    clut = [0] + [max(1, (r >> 3) | (g >> 3) << 5 | (b >> 3) << 10) for r, g, b in pal]
    clut += [0] * (256 - len(clut))
    data[clut_at:clut_at + 512] = struct.pack('<256H', *clut)
    idx = [0 if transparent(*px[i]) else v + 1 for i, v in enumerate(q)]
    put_indices(data, 0, idx)


def banner_bg(r, g, b):
    """the generator's banners: the flat dark navy they were given for the transparent background"""
    return r < 28 and g < 28 and b < 72


def art_size(name, w, h):
    """the size our art of banner name is used at: a GRADE one is its logo band (the banner's width x 64)"""
    return (w, 64) if name.startswith('GRADE') else (w, h)


def disc_rgb(px, n):
    """the first n pixels of a TIM drawn by tim_rgb, as (r, g, b): the transparent ones (0, 0, 0)"""
    return [p[:3] for p in px[:n]]


def _dwmap():
    if os.path.join(ROOT, 'tools') not in sys.path:
        sys.path.insert(0, os.path.join(ROOT, 'tools'))
    import dwmap
    return dwmap


def banner_art(name, lang, disc):
    """our art of banner name (the generator's, at the size it is used at) = the disc's banner (disc: its TIM's bytes,
    the player's own) + our delta (DELTA/<lang>/<name>.png, per channel, mod 256) -> [(r, g, b)] row-major"""
    w, h, base, _, _ = tim_rgb(disc)
    aw, ah = art_size(name, w, h)
    dw, dh, mode, rows, _ = _dwmap().png_read(os.path.join(DELTA, lang, name + '.png'))
    if (dw, dh, mode) != (aw, ah, 'RGB'):
        sys.exit(f'{lang}/{name}.png: a {dw}x{dh} {mode} delta, the banner\'s art is {aw}x{ah} RGB')
    d = [r[3 * x:3 * x + 3] for r in rows for x in range(aw)]
    return [((a[0] + b[0]) & 255, (a[1] + b[1]) & 255, (a[2] + b[2]) & 255)
            for a, b in zip(disc_rgb(base, aw * ah), d)]


def make_deltas(extracted, src=None):
    """The developer's (through tools/localize/sized.py): every banner art of src/<lang>/ (the generator's
    redrawn banners, read at their size from src/sized/<lang>/, a new one's copy written once and then kept) as its
    delta against the disc's banner in extracted: DELTA/<lang>/<name>.png = (ours - the disc's) mod 256 per channel,
    an RGB PNG. -> the names written"""
    from tools.localize import sized
    src = src or DELTA_SRC
    done, scaled = [], []
    for lang in sorted(os.listdir(src)):
        d = os.path.join(src, lang)
        if lang == 'sized' or not os.path.isdir(d):
            continue
        for f in sorted(f for f in os.listdir(d) if f.lower().endswith('.png')):
            name = f[:-4]
            w, h, base, _, _ = tim_rgb(open(os.path.join(extracted, f'STDDAT/GRADE/{name}.TIM'), 'rb').read())
            aw, ah = art_size(name, w, h)
            folder = os.path.join(src, 'sized', lang)
            made = any(o.rsplit('-', 1)[0] == name for o in (os.listdir(folder) if os.path.isdir(folder) else []))
            art = sized.rgb_at(os.path.join(d, f), (aw, ah), folder, not made, scaled)
            disc_px = disc_rgb(base, aw * ah)
            rows = [bytes((art[i][k] - disc_px[i][k]) & 255 for i in range(y * aw, (y + 1) * aw) for k in range(3))
                    for y in range(ah)]
            os.makedirs(os.path.join(DELTA, lang), exist_ok=True)
            _dwmap().png_write(os.path.join(DELTA, lang, name + '.png'), aw, ah, rows, mode='RGB')
            done.append(f'{lang}/{name}')
    print(f'{DELTA}: {len(done)} banner deltas from {src}' + (f' ({len(scaled)} scaled here with tools/image.py)' if scaled else ''))
    return done


def card_offsets(data):
    """CARD.ALL: 66 TIMs, 14 sectors each (game_menu.c loadCardImage: id x 14)"""
    return [i * 14 * 2048 for i in range(66)]


def _forget(folder):
    """forgets the modules imported from folder (a recipe's copy: the next recipe has its own idx.py, tex.py...)"""
    folder = os.path.join(os.path.abspath(folder), '')
    for name, m in list(sys.modules.items()):
        f = getattr(m, '__file__', None)
        if f and os.path.abspath(f).startswith(folder):
            del sys.modules[name]


def run_script(script, argv, env=None, cwd=None):
    """a recipe run in this process (tools/derive/runner.py), when no caller gives its own"""
    if ROOT not in sys.path:
        sys.path.insert(0, ROOT)
    from tools.derive import runner
    return runner.run_script(script, argv, env=env, cwd=cwd)


def run(recipe, args, work, ext, runner=None, language="es"):
    """copies textures/RECIPE into work and runs each [script, argv...] of args there; -> the copy's folder"""
    d = os.path.join(work, recipe)
    shutil.copytree(os.path.join(HERE, 'textures', recipe), d)
    for sub in ('cartas', 'torneo', 'es', 'study'):
        os.makedirs(os.path.join(d, sub), exist_ok=True)
    for a in args:
        try:
            # (the copy is thrown away: no previews, so no Pillow on the player's path)
            (runner or run_script)(os.path.join(d, a[0]), a[1:], env={'LOCALIZE_EXTRACTED': ext, 'LOCALIZE_PREVIEWS': '0', 'LOCALIZE_LANGUAGE': language},
                                   cwd=d)
        finally:
            _forget(d)
    return d


def build(out, extracted, run_with=None, scratch=None, language="es"):
    """The translated textures of the disc in extracted (see the module's docstring) into out; run_with(script, argv,
    env=, cwd=) runs a recipe (default: tools/derive's runner), scratch is where the recipes' copies go (a temporary
    folder in it). -> the files.txt lines"""
    ext = extracted
    files = {}

    def edit(lang, path, entry, idx_path, base=None):
        key = (lang, path)
        if key not in files:
            files[key] = bytearray(open(base or os.path.join(ext, path), 'rb').read())
        put_indices(files[key], entry, open(idx_path, 'rb').read())

    if scratch:
        os.makedirs(scratch, exist_ok=True)
    with tempfile.TemporaryDirectory(dir=scratch) as work:
        d = run('fi-info', [['build.py', os.path.join(ext, 'ETCDAT/FI_INFO.TIM'), 'FI_INFO.es.idx']], work, ext, run_with, language=language)
        edit(language, 'ETCDAT/FI_INFO.TIM', 0, f'{d}/FI_INFO.es.idx')
        edit(language, 'ETCDAT/ETCTIM.BIN', 4, f'{d}/FI_INFO.es.idx')

        d = run('systemw', [['build.py']], work, ext, run_with, language=language)
        edit(language, 'ETCDAT/SYSTEM_W.TIM', 0, f'{d}/SYSTEM_W.es.idx')
        edit(language, 'ETCDAT/ETCTIM.BIN', 8, f'{d}/SYSTEM_W.es.idx')

        d = run('misc', [['build.py', 'push', 'life', 'title', 'timeup', 'vsmode', 'taisen_f', 'banner']], work, ext, run_with, language=language)
        edit(language, 'ETCDAT/BI_IN.TIM', 0, f'{d}/BI_IN.TIM.es.idx')
        edit(language, 'ETCDAT/ETCTIM.BIN', 0, f'{d}/ETCTIM.BIN.0.es.idx')
        edit(language, 'ETCHI/LIFE.TIM', 0, f'{d}/LIFE.TIM.es.idx')
        edit(language, 'ETCNA/TITLE256.TIM', 0, f'{d}/TITLE256.TIM.es.idx')
        saved = sys.path[:]
        try:
            sys.path.insert(0, os.path.join(ROOT, 'tools')); import title_stamp   # HORIZON, as on the English one
        finally:
            sys.path[:] = saved
        # (placed by the disc's own file: the Japanese title has its own place, title_stamp.RELEASE_PLACES)
        title_stamp.stamp(files[(language, 'ETCNA/TITLE256.TIM')], 'ETCNA/TITLE256.TIM',
                          disc=open(os.path.join(ext, 'ETCNA/TITLE256.TIM'), 'rb').read())
        edit(language, 'STDDAT/STDTIM.BIN', 2, f'{d}/STDTIM.BIN.2.es.idx')
        edit(language, 'STDDAT/TAISEN_F.TIM', 0, f'{d}/TAISEN_F.TIM.es.idx')
        edit(language, 'STDDAT/TAISEN2.TIM', 0, f'{d}/TAISEN2.TIM.es.idx')
        shutil.copy(f'{d}/battle-banner-es.json', os.path.join(work, 'battle-banner-es.json'))

        d = run('cards-cups', [['cards_out.py'], ['grades_es.py'], ['fr_es.py']], work, ext, run_with, language=language)
        card = bytearray(open(os.path.join(ext, 'CARD/CARD.ALL'), 'rb').read())
        for lang in (language, 'en'):
            c = bytearray(card)
            for k, off in enumerate(card_offsets(card)):
                src = f'{d}/cartas/card-{k:02d}.es.idx' if not (lang == 'en' and k == 0) else f'{d}/cartas/card-00.en-latin.idx'
                sub = bytearray(c[off:off + 14 * 2048])
                put_indices(sub, 0, open(src, 'rb').read())
                c[off:off + 14 * 2048] = sub
            files[(lang, 'CARD/CARD.ALL')] = c
        for g in 'DCBA':
            edit(language, f'STDDAT/GRADE/GRADE{g}.TIM', 0, f'{d}/torneo/GRADE{g}.es.idx')
        edit(language, 'STDDAT/GRADE/FR.TIM', 0, f'{d}/torneo/FR.es.idx')

        # the tournament banners whose logo is Japanese art: the generator's, kept as deltas against the disc's own
        # banner (content/localized/tournament/delta/<lang>/, banner_art: no Pillow, nothing of the banner in the
        # repository); a GRADE one is its logo band (the art at the banner's width x 64) over the banner (the translated
        # lines under it from grades_es.py) on the flat navy (0, 0, 40) where the banner is transparent
        for lang in ('en', language):
            if not os.path.isdir(os.path.join(DELTA, lang)):
                continue
            for f in sorted(f for f in os.listdir(os.path.join(DELTA, lang)) if f.lower().endswith('.png')):
                name = f[:-4]; path = f'STDDAT/GRADE/{name}.TIM'
                data = files.get((lang, path)) or bytearray(open(os.path.join(ext, path), 'rb').read())
                w, h, base, _, _ = tim_rgb(bytes(data))
                art = banner_art(name, lang, open(os.path.join(ext, path), 'rb').read())
                if name.startswith('GRADE'):
                    px = art[:w * min(64, h)] + [p[:3] if p[3] else (0, 0, 40) for p in base[w * 64:]]
                else:
                    px = art
                put_rgb(data, px, banner_bg)
                files[(lang, path)] = data

        from tools.localize import labels
        labels.apply(files, language, work)

        lines = []
        for (lang, path), data in sorted(files.items()):
            p = os.path.join(out, lang, path)
            os.makedirs(os.path.dirname(p), exist_ok=True)
            open(p, 'wb').write(data)
            lines.append(f'{lang} {path}')
        os.makedirs(out, exist_ok=True)
        shutil.copy(os.path.join(work, 'battle-banner-es.json'), os.path.join(out, f'battle-banner-{language}.json'))
        open(os.path.join(out, 'files.txt'), 'w').write('\n'.join(lines) + '\n')
    print(f'{out}: {len(lines)} files ({", ".join(sorted({p for _, p in files}))})')
    return lines


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('out', nargs='?')
    ap.add_argument('--extracted', default=os.path.join(ROOT, 'extracted'))
    from tools.languages import CODES
    ap.add_argument('--language', choices=CODES[1:], default='es')
    ap.add_argument('--make-deltas', action='store_true',
                    help='the developer\'s: remake content/localized/tournament/delta from --src (tools/image.py)')
    ap.add_argument('--src', help='the redrawn banners (default build/localized-src/tournament)')
    a = ap.parse_args()
    if a.make_deltas:
        make_deltas(os.path.abspath(a.extracted), a.src)
        return
    if not a.out:
        ap.error('OUTDIR is needed')
    build(a.out, os.path.abspath(a.extracted), language=a.language)


if __name__ == '__main__':
    main()
