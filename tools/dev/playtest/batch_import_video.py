#!/usr/bin/env python3
"""The batch video: each new partner walking in File City, then its finisher (a card-game
clip) in the wild battle, captioned, from the clips playtest.py recorded.

  python3 tools/dev/playtest/batch_import_video.py [LIST.json] [--play build/batch/play]
         [--out build/batch/batch-import-first-10.mp4] [--walk 1.5:5.5] [--attack 24.5:8.5]
         [--at NAME=START ...]

Re-encodes with -crf 28 (montage.py); if the result is over 20 MB it is encoded again
at -crf 32.
"""

from pathlib import Path as _DevPath
import sys as _dev_sys
_DEV_ROOT = str(next(p for p in _DevPath(__file__).resolve().parents if (p / "tools").is_dir()))
_dev_sys.path.insert(0, _DEV_ROOT)
_dev_sys.path.insert(0, str(_DevPath(_DEV_ROOT) / "tools"))
import argparse, json, os, subprocess, sys
ROOT = _DEV_ROOT
MONTAGE = os.path.join(ROOT, 'tools/dev/playtest/montage.py')
PY = os.environ.get('PY', sys.executable)     # image/video developer dependencies


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('list', nargs='?', default=os.path.join(ROOT, 'content/imports/lists/first-10.json'))
    ap.add_argument('--play', default='build/batch/play')
    ap.add_argument('--out', default='build/batch/batch-import-first-10.mp4')
    ap.add_argument('--walk', default='1.5:5.5')
    ap.add_argument('--attack', default='24.5:8.5')
    ap.add_argument('--at', nargs='*', default=[], help='NAME=START of the attack cut')
    a = ap.parse_args()
    L = json.load(open(a.list))
    rep = json.load(open(os.path.join(ROOT, L.get('out', 'build/batch'), 'report.json')))
    at = dict(x.split('=') for x in a.at)
    play = os.path.join(ROOT, a.play)
    parts = []
    lv = {3: 'Rookie', 4: 'Champion', 5: 'Ultimate', 6: 'Mega'}
    for i, e in enumerate(L['digimon']):
        n = e['name']
        r = rep[n]
        walk, battle = os.path.join(play, n + '-walk.mp4'), os.path.join(play, n + '-battle.mp4')
        if not (os.path.exists(walk) and os.path.exists(battle)):
            continue
        cap = f'{L["first_id"] + i} {n} ({lv[r["level"]]}) - card game model, everyday moves from {r["donor"]["name"]}'
        ws, wd = a.walk.split(':')
        bs, bd = at.get(n, a.attack.split(':')[0]), a.attack.split(':')[1]
        parts.append(f'{walk}:{ws}:{wd}:{cap}')
        parts.append(f'{battle}:{bs}:{bd}:{n}: finisher (card-game attack, {r["donor"]["name"]}\'s effect)')
    out = os.path.join(ROOT, a.out)
    subprocess.check_call([PY, MONTAGE, out] + parts)
    size = os.path.getsize(out)
    if size > 20 * 1024 * 1024:
        tmp = out + '.tmp.mp4'
        subprocess.check_call(['ffmpeg', '-loglevel', 'error', '-y', '-i', out, '-c:v', 'libx264', '-crf', '32',
                               '-preset', 'slow', '-pix_fmt', 'yuv420p', tmp])
        os.replace(tmp, out)
    print(out, os.path.getsize(out), 'bytes')


if __name__ == '__main__':
    main()
