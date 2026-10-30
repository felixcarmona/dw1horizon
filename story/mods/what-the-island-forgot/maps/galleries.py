#!/usr/bin/env python3
"""The Galleries arc's screens (338 and up; 337 has its own recipe): every description in maps/author/galleries/*.json
whose art and map data exist is built from the player's disc: the donor's structure (tile layout, TIMs, lights) with
the screen's camera, our collision and exits (maps/<name>-data.json, made by author/gallery.py layout) and our art
(art/<name>.png). Its wild Digimon are placed by the story (early-game.py).

    python3 galleries.py OUT_DIR [SET [FILE...]]  writes OUT_DIR/<FILE>.MAP and <FILE>.TFS for each screen (SET: another
    folder of descriptions, e.g. district: File City's new district, built the same way; FILE...: only those screens,
    the same bytes: tools/derive builds the screens side by side with them)
"""
import glob, json, os, sys
from mapbase import base_map, import_png, MOD, check_arrivals
from foreground import apply as apply_foreground


def main(out, folder='galleries', *only):
    os.makedirs(out, exist_ok=True)
    for cfg in sorted(glob.glob(os.path.join(MOD, 'maps', 'author', folder, '*.json'))):
        c = json.load(open(cfg))
        if only and c['file'] not in only: continue
        data = os.path.join(MOD, 'maps', c['name'] + '-data.json'); art = os.path.join(MOD, 'art', c['name'] + '.png')
        if not (os.path.exists(data) and os.path.exists(art)): continue
        d = json.load(open(data))
        m = base_map(c['donor'], *d['camera']); m.projection = d['projection']
        m.collision = list(d['collision']); m.warps = d['warps']
        background = os.path.join(out, c['file'] + '.TFS')
        import_png(c['donor'], art, background)
        if 346 <= c['id'] <= 357:
            from foreground_c import apply
            apply(m, c['id'], background)
        elif folder == 'district' and 358 <= c['id'] <= 365:
            from district_foreground import apply
            apply(m, c['name'], background)
        else:
            apply_foreground(m, c['name'], background)
        check_arrivals(m, c['file'])
        open(os.path.join(out, c['file'] + '.MAP'), 'wb').write(m.build())
        print(f'{c["file"]}: free tiles {m.collision.count(0)}, exits {[(w["targetMap"], w["targetExit"]) for w in m.warps if w["targetMap"] != -1]}')


if __name__ == '__main__':
    if len(sys.argv) < 2: sys.exit(__doc__)
    main(*sys.argv[1:])
