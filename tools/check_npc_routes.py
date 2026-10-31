#!/usr/bin/env python3
"""Audit authored stationary NPC footprints against the engine's walking lattice.

No disc needed for the Bone Field guard. --audit MAPS also scans every new screen
in the mod (all declared NPCs together is a conservative visibility state).
"""
import argparse
import ast
import json
from collections import deque
from pathlib import Path
from types import SimpleNamespace
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'tools'))
from maps import reach
import dwmap

MOD = ROOT / 'story/mods/what-the-island-forgot'


def placements():
    species = {}
    # A twin shares its partner's name and is what the field actually spawns.
    records = [json.loads(path.read_text()) for path in (ROOT / 'content/species').glob('*.json')]
    for d in sorted(records, key=lambda d: '_npc_original' in d):
        species[''.join(c for c in d['name'] if c.isalnum()).lower()] = d['model']['radius']
    screens = []
    for path in sorted(MOD.rglob('*.py')):
        tree = ast.parse(path.read_text())
        names = {}
        for stmt in tree.body:
            if not isinstance(stmt, ast.Assign) or not isinstance(stmt.value, ast.Call):
                continue
            c = stmt.value
            if isinstance(c.func, ast.Name) and c.func.id == 'new_screen':
                kw = {k.arg: k.value for k in c.keywords}
                record = dict(screen=ast.literal_eval(c.args[0]),
                              map=Path(ast.literal_eval(kw['map'])).name,
                              source=str(path.relative_to(ROOT)), npcs=[])
                names[stmt.targets[0].id] = record
                screens.append(record)
            elif isinstance(c.func, ast.Attribute) and c.func.attr == 'npc' and isinstance(c.func.value, ast.Name) and c.func.value.id in names:
                kw = {k.arg: k.value for k in c.keywords}
                kind = c.args[0].attr
                x, z = ast.literal_eval(kw['at'])
                names[c.func.value.id]['npcs'].append((kind, x, z, species[kind.lower()]))
    return screens


def bone_field(m=None):
    if m is None:
        m = SimpleNamespace(**json.loads((MOD / 'maps/bone-field-data.json').read_text()))
        # Match collision edits made by the final foreground recipe, without rendering.
        foreground = json.loads((MOD / 'maps/foreground-depth-a/BONE01.json').read_text())
        for edit in foreground['collision']:
            tx, tz = edit['tile']
            assert m.collision[tz*100+tx] == edit['before']
            m.collision[tz*100+tx] = edit['after']
    s = next(s for s in placements() if s['screen'] == 306)
    footprints = [n[1:] for n in s['npcs']]
    starts = [(w['x'], w['z']) for w in m.warps if w['targetMap'] != -1]
    # Both arrivals must share the chest, exits and a talkable side of each NPC.
    r = reach.reach(m, starts[:1], footprints=footprints)
    reverse = reach.reach(m, starts[1:2], footprints=footprints)
    assert reverse == r, 'BONE01: arrival reaches differ with guided NPCs'
    for p in starts + [(-900, 700)]:
        assert p in r, f"BONE01: {p} unreachable with guided NPCs ({len(r)} points)"
    raw = reach.reach(m, starts[:1])
    free = {p for p in raw if not any(abs(p[0]-x) <= 100+nr and abs(p[1]-z) <= 100+nr
                                    for x,z,nr in footprints)}
    assert free == r, f'BONE01: {len(free-r)} walking points stranded by guided NPCs'
    for kind, x, z, radius in s['npcs']:
        assert any(abs(px-x) <= radius+150 and abs(pz-z) <= radius+150 for px,pz in r), f'{kind} cannot be talked to'
    print(f'BONE01: guided NPCs, both arrivals/chest/talk positions connected, {len(r)} points')
    return r, s


def components(points, step=50):
    remaining = set(points)
    sizes = []
    while remaining:
        q = deque([remaining.pop()]); size = 0
        while q:
            x,z = q.popleft(); size += 1
            for dx,dz in ((step,0),(-step,0),(0,step),(0,-step)):
                p = x+dx,z+dz
                if p in remaining: remaining.remove(p); q.append(p)
        sizes.append(size)
    return sorted(sizes, reverse=True)


def audit(folder, step=50, screens=None):
    for s in placements():
        if not s['npcs'] or (screens and s['screen'] not in screens): continue
        path = folder / s['map']
        if not path.exists():
            print(f"MISSING {s['screen']} {path.name}"); continue
        m = dwmap.MapFile(path.read_bytes())
        raw = reach.reach(m, step=step, seed_policy="spawn_coordinates")
        print(s['screen'], 'BARE', components(raw, step))
        tests = [(n[0], [n[1:]]) for n in s['npcs']]
        if len(tests)>1: tests.append(('ALL', [n[1:] for n in s['npcs']]))
        for name, footprints in tests:
            free = {p for p in raw if not any(abs(p[0]-x)<=100+r and abs(p[1]-z)<=100+r for x,z,r in footprints)}
            sizes = components(free, step)
            print(s['screen'],name,'components',sizes,'at',footprints)


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--audit', type=Path)
    p.add_argument('--step', type=int, default=50)
    p.add_argument('--screens', type=int, nargs='+')
    a = p.parse_args()
    if a.audit: audit(a.audit, a.step, a.screens)
    else: bone_field()
