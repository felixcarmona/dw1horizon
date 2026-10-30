#!/usr/bin/env python3
"""The map files of the new-screens test (tools/dev/playtest/screens.sh), made from the player's own disc (extracted/), with
new file names (patch 0147: the build gives each new name its FILE_OFFSET_TABLE entry):

  * HOLW01.MAP / HOLW01.TFS, screen 300: the Native Forest clearing (MAYO01, screen 0) with its palettes turned blue;
    its exit 1 (west, to Dragon Eye Lake) leads to screen 0's exit 1, its exit 3 (east, to Kunemon's Bed) to screen
    301's exit 0;
  * HOLW02.MAP / HOLW02.TFS, screen 301: Kunemon's Bed (MAYO02, screen 1) with its palettes turned red; its exit 0
    (west) leads back to screen 300's exit 3;
  * MAYO01.MAP: screen 0 with its exit 1 leading to screen 300's exit 1 (the clearing's west edge).

The screen files of the test (300-test-hollow.json, 301-test-bed.json) are copied beside the maps, so OUT_DIR is a
SCREEN_CONTENT folder: tools/build-full.sh puts a screen's <file>.MAP/.TFS found beside its screen file on the disc.

    python3 tools/dev/playtest/screens/maps.py OUT_DIR
"""

from pathlib import Path as _DevPath
import sys as _dev_sys
_DEV_ROOT = str(next(p for p in _DevPath(__file__).resolve().parents if (p / "tools").is_dir()))
_dev_sys.path.insert(0, _DEV_ROOT)
_dev_sys.path.insert(0, str(_DevPath(_DEV_ROOT) / "tools"))
import os
import shutil
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = _DEV_ROOT
sys.path.insert(0, os.path.join(ROOT, 'tools'))
import dwmap  # noqa: E402

MAP1 = os.path.join(ROOT, 'extracted', 'MAP', 'MAP1')


def tint(kr, kg, kb, add):
    def f(c):
        if c == 0:
            return c                                # transparent
        stp = c & 0x8000
        r, g, b = dwmap.bgr555_to_rgb(c)
        v = [min(255, int(x * k) + a) for x, k, a in ((r, kr, add[0]), (g, kg, add[1]), (b, kb, add[2]))]
        out = dwmap.rgb_to_bgr555(*v) | stp
        return out if out else 0x0421
    return f


def copy(src, name, out, color, exits):
    m = dwmap.MapFile(open(os.path.join(MAP1, src + '.MAP'), 'rb').read())
    t = dwmap.TfsFile(open(os.path.join(MAP1, src + '.TFS'), 'rb').read())
    t.cluts = [[color(c) for c in clut] for clut in t.cluts]
    for i, (screen, exit_) in exits.items():
        m.warps[i]['targetMap'], m.warps[i]['targetExit'] = screen, exit_
    open(os.path.join(out, name + '.MAP'), 'wb').write(m.build())
    open(os.path.join(out, name + '.TFS'), 'wb').write(t.build())


def main():
    out = sys.argv[1] if len(sys.argv) == 2 else sys.exit(__doc__)
    os.makedirs(out, exist_ok=True)
    copy('MAYO01', 'HOLW01', out, tint(0.55, 0.75, 1.1, (0, 0, 40)), {1: (0, 1), 3: (301, 0)})
    copy('MAYO02', 'HOLW02', out, tint(1.1, 0.55, 0.5, (40, 0, 0)), {0: (300, 3)})
    o = dwmap.MapFile(open(os.path.join(MAP1, 'MAYO01.MAP'), 'rb').read())
    o.warps[1]['targetMap'], o.warps[1]['targetExit'] = 300, 1
    open(os.path.join(out, 'MAYO01.MAP'), 'wb').write(o.build())
    for f in ('300-test-hollow.json', '301-test-bed.json'):
        shutil.copyfile(os.path.join(HERE, f), os.path.join(out, f))
    print(f'{out}: HOLW01.MAP/.TFS (screen 300: exit 1 -> 0.1, exit 3 -> 301.0), HOLW02.MAP/.TFS (screen 301: exit 0 -> '
          '300.3), MAYO01.MAP (exit 1 -> 300.1), the two screen files')


if __name__ == '__main__':
    main()
