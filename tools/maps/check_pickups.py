#!/usr/bin/env python3
"""Every pickup on a new screen can be picked up from comfortable floor (reach.check_pickups): the ground spots of
content/ground-items.json on the new screens (where each lies: its "at", else its script tile; a script shared with an
original screen keeps the original's tiles) and the spawn_item / spawn_chest calls of the story files that make a new
screen.

    check_pickups.py --screens DIR [STORY.py ...]   the built maps (DIR: NNN-name.json and FILE.MAP) and the story
                                                    files (default: the everything recipe's); derive's maps step runs
                                                    this (recipe check "pickups")
    check_pickups.py --authored                     no disc: the committed map data with the foreground's collision
                                                    edits (tools/check_npc_routes.py authored_geometry), every story file
"""
import argparse
import ast
import glob
import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT / 'tools'), str(ROOT / 'tools' / 'maps')]
import dwmap
import reach
from dws import pickups

MOD = ROOT / 'story/mods/what-the-island-forgot'


def _literal(node):
    try:
        return ast.literal_eval(node)
    except ValueError:
        return None


def story_pickups(path):
    """(screen, items, chests, errors) of one story file: its new_screen(N) and the literal spawn_item / spawn_chest
    positions in it; screen None when the file makes no new screen."""
    tree = ast.parse(Path(path).read_text(), str(path))
    calls = [n for n in ast.walk(tree) if isinstance(n, ast.Call) and isinstance(n.func, ast.Name)]
    screens = [_literal(n.args[0]) for n in calls if n.func.id == 'new_screen' and n.args]
    if not screens:
        return None, [], [], []
    items, chests, errors = [], [], []
    for n in calls:
        if n.func.id not in ('spawn_item', 'spawn_chest'):
            continue
        kw = {k.arg: _literal(k.value) for k in n.keywords}
        where = f'{os.path.relpath(path, ROOT)}:{n.lineno}'
        at = kw.get('at')
        if not (isinstance(at, tuple) and len(at) == 2 and all(isinstance(v, int) for v in at)):
            errors.append(f'{where}: {n.func.id} needs a literal at=(x, z) for the pickup check'); continue
        if n.func.id == 'spawn_item':
            items.append((f'{where} spawn_item', reach.model_tile(*at)))
        else:
            chests.append((f'{where} spawn_chest', at, kw.get('facing', 0)))
    return screens[0], items, chests, errors


def built_maps(screens_dir):
    """{screen: (name, loader)} of the maps in a built screens folder."""
    out = {}
    for f in glob.glob(os.path.join(screens_dir, '*.json')):
        d = json.loads(Path(f).read_text())
        path = Path(screens_dir, d['file'] + '.MAP')
        if path.is_file():
            out[d['id']] = (d['file'], lambda p=path: dwmap.MapFile(p.read_bytes()))
    return out


def authored_maps():
    """{screen: (name, loader)} of every new screen a story file makes, from the committed data (no disc)."""
    import check_npc_routes as routes
    return {s['screen']: (Path(s['map']).stem, lambda s=s: routes.authored_geometry(s)) for s in routes.placements()}


def run(maps, sources, registry=pickups.REGISTRY, new_from=300):
    """-> (pickups checked, errors). maps: {screen: (name, loader)}; every registered spot of a screen >= new_from
    must have a map there."""
    data, _ = pickups.load_registry(registry)
    items, chests, errors = {}, {}, []
    for screen, spots in pickups.emitted(data).items():
        if screen < new_from:
            continue
        if screen not in maps:
            errors.append(f'screen {screen}: ground spots registered but no map to check them on'); continue
        items[screen] = [(f'screen {screen} ground spot {i}', t) for i, t in spots]
    for src in sources:
        if not str(src).endswith('.py'):
            continue
        screen, its, chs, errs = story_pickups(src)
        errors += errs
        if screen is None or not (its or chs):
            continue
        if screen not in maps:
            errors.append(f'{src}: screen {screen} has pickups but no map to check them on'); continue
        items.setdefault(screen, []).extend(its)
        chests.setdefault(screen, []).extend(chs)
    count = 0
    for screen in sorted(set(items) | set(chests)):
        name, load = maps[screen]
        try:
            m = load()
        except (AssertionError, OSError, KeyError, StopIteration) as e:
            errors.append(f'{name}: no geometry to check its pickups on ({e})'); continue
        errors += [f'{name}: {e}' for e in reach.check_pickups(m, items.get(screen, ()), chests.get(screen, ()))]
        count += len(items.get(screen, ())) + len(chests.get(screen, ()))
    return count, errors


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split('\n\n')[0])
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument('--screens', help='the built new screens: NNN-name.json and FILE.MAP')
    g.add_argument('--authored', action='store_true', help='the committed map data, every story file of the mod')
    ap.add_argument('--registry', default=str(pickups.REGISTRY))
    ap.add_argument('sources', nargs='*')
    a = ap.parse_args(argv)
    if a.authored:
        maps, sources = authored_maps(), a.sources or sorted(str(p) for p in MOD.rglob('*.py'))
    else:
        recipe = json.loads((ROOT / 'tools/derive/recipes/everything.json').read_text())
        maps, sources = built_maps(a.screens), a.sources or [str(ROOT / p) for p in recipe['story']['sources']]
    count, errors = run(maps, sources, a.registry)
    for e in errors:
        print(e)
    print(f'pickups: {count} on the new screens checked, {len(errors)} not comfortably reachable')
    return 1 if errors else 0


if __name__ == '__main__':
    sys.exit(main())
