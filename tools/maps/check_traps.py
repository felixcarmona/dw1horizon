#!/usr/bin/env python3
"""Audit isolated body-box trap tiles on every native and generated map.

    python3 tools/maps/check_traps.py --maps build/NAME-maps --jobs 2 --json build/traps.json

Read original geometry from extracted/MAP, prefer the final retouch geometry,
add all generated screens, then apply owned native collision edits. This checks
static floor, not live actors, battle bounds or scripted collision changes.
"""
import argparse
from concurrent.futures import ProcessPoolExecutor
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT / 'tools'), str(ROOT / 'tools/maps')]
import content
import dwmap
import reach


def map_paths(extracted, maps=None):
    paths = {p.stem: p for p in sorted(Path(extracted).rglob('*.MAP'))}
    if maps is not None:
        for folder in ('retouch', 'screens'):
            for p in sorted((Path(maps) / folder).glob('*.MAP')):
                paths[p.stem] = p
    return paths


def check_one(job):
    name, path, edits = job
    m = dwmap.MapFile(Path(path).read_bytes())
    content.apply_map_collision(m, edits, name)
    starts = [(w['x'], w['z']) for w in m.warps if w['targetMap'] != -1]
    if not starts:
        starts = [(w['x'], w['z']) for w in m.warps if w['x'] or w['z']]
    points = reach.reach(m, starts=starts)
    return dict(map=name, points=len(points), traps=reach.trap_tiles(m, points))


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--extracted', type=Path, default=ROOT / 'extracted/MAP')
    ap.add_argument('--maps', type=Path)
    ap.add_argument('--jobs', type=int, default=1)
    ap.add_argument('--json', type=Path)
    args = ap.parse_args()
    if args.jobs < 1:
        ap.error('--jobs must be positive')
    paths = map_paths(args.extracted, args.maps)
    if not paths:
        ap.error('no maps found; extract the player disc first')
    records = content.load_maps()
    jobs = [(name, str(path), records.get(name, {}).get('collision', []))
            for name, path in sorted(paths.items())]
    if args.jobs == 1:
        rows = list(map(check_one, jobs))
    else:
        with ProcessPoolExecutor(max_workers=args.jobs) as pool:
            rows = list(pool.map(check_one, jobs))
    if args.json:
        args.json.parent.mkdir(parents=True, exist_ok=True)
        args.json.write_text(json.dumps(rows, indent=2) + '\n')
    failures = [r for r in rows if r['traps']]
    for row in failures:
        print(f"{row['map']}: {row['traps']}")
    empty = [r['map'] for r in rows if not r['points']]
    if empty:
        print('No free authored arrival: ' + ', '.join(empty))
    print(f"{len(rows)} maps checked; {sum(len(r['traps']) for r in rows)} isolated trap tiles")
    return bool(failures or empty)


if __name__ == '__main__':
    sys.exit(main())
