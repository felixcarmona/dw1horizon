#!/usr/bin/env python3
"""World atlas: labelled contact sheets of every screen's background, one sheet
per zone, plus one overview sheet. Output goes to build/atlas/ (game assets:
never commit it).

Usage:
  atlas.py [--night] [--out build/atlas] [--thumb 240]

Each tile shows: screen id, file, name, and its exits as "-> id name".
Uses tools/image.py and bundled bitmap labels. Backgrounds come from tools/dwmap.py (extracted/MAP).
"""

# Allow both direct script execution and package imports.
import sys as _image_sys
from pathlib import Path as _ImagePath
_image_sys.path.insert(0, str(next(p for p in _ImagePath(__file__).resolve().parents if (p / 'tools').is_dir())))
import argparse, csv, glob, os, sys
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
from tools.image import Image, ImageDraw, ImageFont
sys.path.insert(0, os.path.join(ROOT, 'tools'))
import dwmap  # noqa: E402


def font(size):
    for f in ('/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf', '/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf'):
        if os.path.exists(f):
            return ImageFont.truetype(f, size)
    return ImageFont.load_default()


def background(map_path, clut):
    m = dwmap.MapFile(open(map_path, 'rb').read())
    tp = dwmap.find_tfs(map_path)
    if not tp:
        return None, m
    t = dwmap.TfsFile(open(tp, 'rb').read())
    W, H, idx = t.image_indices(m)
    pal = t.palette_rgb(min(clut, len(t.cluts) - 1))
    img = Image.new('RGB', (W, H))
    img.putdata([pal[v] for row in idx for v in row])
    return img, m


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--night', action='store_true'); ap.add_argument('--out', default=os.path.join(ROOT, 'build/atlas'))
    ap.add_argument('--thumb', type=int, default=240)
    a = ap.parse_args()
    rows = list(csv.DictReader(open(os.path.join(ROOT, 'docs/data/map_files.csv'))))
    zones = {int(r['id']): r['name'] for r in csv.DictReader(open(os.path.join(ROOT, 'docs/data/map_names.csv')))}
    name = {int(r['id']): r['map_name'] for r in rows}
    paths = {os.path.basename(p)[:-4]: p for p in glob.glob(os.path.join(ROOT, 'extracted/MAP/*/*.MAP'))}
    os.makedirs(a.out, exist_ok=True)
    T = a.thumb; LABEL = 64; f1, f2 = font(15), font(12)
    tiles = {}
    for r in rows:
        sid = int(r['id']); p = paths.get(r['file'])
        tile = Image.new('RGB', (T, T * 3 // 4 + LABEL), (24, 24, 32))
        d = ImageDraw.Draw(tile)
        if p:
            img, m = background(p, 2 if a.night else 0)
            if img:
                img.thumbnail((T, T * 3 // 4)); tile.paste(img, ((T - img.width) // 2, 0))
        d.text((4, T * 3 // 4 + 2), f"{sid} {r['file']}", font=f1, fill=(255, 220, 120))
        d.text((4, T * 3 // 4 + 20), name[sid][:30], font=f2, fill=(230, 230, 230))
        tiles[sid] = (tile, int(r['loading_name']), p)
    # exits from the JSON dump (MapFile keeps them as parsed data)
    by_zone = {}
    for sid, (tile, zone, p) in tiles.items():
        by_zone.setdefault(zone, []).append(sid)
        if p:
            ws = dwmap.MapFile(open(p, 'rb').read()).to_json().get('warps', [])
            tg = sorted({w['targetMap'] for w in ws if 0 <= w['targetMap'] < len(rows) and 0 <= w['targetExit'] < 10})
            ImageDraw.Draw(tile).text((4, T * 3 // 4 + 36), ('exits to ' + ' '.join(map(str, tg)))[:44], font=f2, fill=(140, 200, 255))

    def sheet(ids, title, path, cols=4):
        tw, th = tiles[ids[0]][0].size
        n = len(ids); rws = (n + cols - 1) // cols
        s = Image.new('RGB', (cols * tw, rws * th + 40), (10, 10, 14))
        ImageDraw.Draw(s).text((8, 8), title, font=font(22), fill=(255, 255, 255))
        for i, sid in enumerate(ids):
            s.paste(tiles[sid][0], ((i % cols) * tw, 40 + (i // cols) * th))
        s.save(path); return path

    out = []
    for zone, ids in sorted(by_zone.items()):
        zn = zones.get(zone, f'zone {zone}')
        safe = ''.join(c if c.isalnum() else '-' for c in zn).strip('-')
        out.append(sheet(sorted(ids), f'{zn} ({len(ids)} screens)', os.path.join(a.out, f'zone-{zone:03}-{safe}.png'), cols=min(4, len(ids))))
    print('\n'.join(out))


if __name__ == '__main__':
    main()
