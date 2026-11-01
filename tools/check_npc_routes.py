#!/usr/bin/env python3
"""Audit authored NPC starting footprints against the engine's walking lattice.

No disc needed: use authored geometry, including foreground collision edits.
--maps MAPS additionally checks the generated geometry against those inputs.
Clock visibility and battle disappearance are enumerated; unrelated story flags
are conservatively independent. Accepted empty pockets have explicit bounds.
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
        key = ''.join(c for c in d['name'] if c.isalnum()).lower()
        species[key] = d['model']['radius']
        species[f"{key}{d['id']}"] = d['model']['radius']      # the enum's id-suffixed twin names (Species.Whamon146)
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
                              source=str(path.relative_to(ROOT)), npcs=[], when=[], wild=[], targets=[])
                names[stmt.targets[0].id] = record
                screens.append(record)
            elif isinstance(c.func, ast.Attribute) and c.func.attr == 'npc' and isinstance(c.func.value, ast.Name) and c.func.value.id in names:
                kw = {k.arg: k.value for k in c.keywords}
                kind = c.args[0].attr
                x, z = ast.literal_eval(kw['at'])
                names[c.func.value.id]['npcs'].append((kind, x, z, species[kind.lower()]))
                record = names[c.func.value.id]
                record['when'].append(ast.unparse(kw['when']) if 'when' in kw else 'True')
                record['wild'].append('hp' in kw)
        for fn in (n for n in tree.body if isinstance(n, ast.FunctionDef)):
            owners = {d.value.id for d in fn.decorator_list
                      for d in [d.func if isinstance(d, ast.Call) else d]
                      if isinstance(d, ast.Attribute) and isinstance(d.value, ast.Name)
                      and d.value.id in names}
            for owner in owners:
                for call in (n for n in ast.walk(fn) if isinstance(n, ast.Call)):
                    if not isinstance(call.func, ast.Name) or call.func.id not in ('spawn_chest', 'spawn_item'): continue
                    kw = {k.arg: k.value for k in call.keywords}
                    if 'at' not in kw: raise ValueError(f'{path.name}: pickup without literal at=')
                    x,z = ast.literal_eval(kw['at'])
                    facing = ast.literal_eval(kw['facing']) if 'facing' in kw else 0
                    names[owner]['targets'].append((call.func.id, x, z, facing))
        # A placement-only file keeps the donor script, including random items.
        # Files with events get an empty owned script (py/lower.py Module.lower).
        owns_script = any(isinstance(d.func if isinstance(d, ast.Call) else d, ast.Attribute)
                          and (d.func if isinstance(d, ast.Call) else d).attr in
                          ('on_enter', 'on_talk', 'on_step', 'on_use', 'on_section')
                          for fn in tree.body if isinstance(fn, ast.FunctionDef)
                          for d in fn.decorator_list)
        if not owns_script:
            for record in names.values():
                metadata = next((MOD / 'screens').glob(f"{record['screen']}-*.json"))
                script = json.loads(metadata.read_text())['maphead']['script']
                base = next((ROOT / 'story/base').rglob(f's{script:03d}-*/script.py'))
                donor = ast.parse(base.read_text())
                for fn in (n for n in donor.body if isinstance(n, ast.FunctionDef)):
                    if not any(isinstance(d,ast.Attribute) and d.attr == 'on_enter' for d in fn.decorator_list): continue
                    for call in (n for n in ast.walk(fn) if isinstance(n,ast.Call)
                                 and isinstance(n.func,ast.Name) and n.func.id == 'spawn_item'):
                        kw = {k.arg:k.value for k in call.keywords}
                        x,z = ast.literal_eval(kw['at'])
                        record['targets'].append(('spawn_item',x,z,0))
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


from itertools import product

def visible_states(s):
    """Clock conditions are exact; other predicates are shared symbolic booleans.

    Also cover disappearance after a wild battle. Treating unrelated story predicates
    independently is conservative: it can add states, never hide a possible blocker.
    """
    conditions = [ast.parse(v, mode='eval').body for v in s['when']]
    atoms = set()
    def evaluate(n, hour, values, collect=False):
        if isinstance(n, ast.BoolOp):
            vals = [evaluate(v, hour, values, collect) for v in n.values]
            return all(vals) if isinstance(n.op, ast.And) else any(vals)
        if isinstance(n, ast.UnaryOp) and isinstance(n.op, ast.Not):
            return not evaluate(n.operand, hour, values, collect)
        if isinstance(n, ast.Constant): return n.value
        if isinstance(n, ast.Compare) and ast.unparse(n.left) == 'clock.hour':
            left = hour
            for op, right in zip(n.ops, n.comparators):
                right = ast.literal_eval(right)
                ok = {ast.Lt: lambda: left < right, ast.LtE: lambda: left <= right,
                      ast.Gt: lambda: left > right, ast.GtE: lambda: left >= right,
                      ast.Eq: lambda: left == right, ast.NotEq: lambda: left != right}[type(op)]()
                if not ok: return False
                left = right
            return True
        key = ast.dump(n)
        if collect: atoms.add(key)
        return values.get(key, False)
    for n in conditions: evaluate(n, 12, {}, True)
    atoms = sorted(atoms)
    states = set()
    for hour in range(24):
        for bits in product((False, True), repeat=len(atoms)):
            values = dict(zip(atoms, bits))
            present = tuple(i for i,n in enumerate(conditions) if evaluate(n,hour,values))
            wild = [i for i in present if s['wild'][i]]
            for mask in product((False, True), repeat=len(wild)):
                removed = {i for i,beaten in zip(wild,mask) if beaten}
                states.add(tuple(i for i in present if i not in removed))
    return sorted(states)


def point_components(points, step):
    remaining = set(points); result = []
    while remaining:
        seed = remaining.pop(); part = {seed}; q = deque([seed])
        while q:
            x,z = q.popleft()
            for dx,dz in ((step,0),(-step,0),(0,step),(0,-step)):
                p = x+dx,z+dz
                if p in remaining: remaining.remove(p); part.add(p); q.append(p)
        result.append(part)
    return sorted(result, key=len, reverse=True)


def authored_geometry(s):
    """Read the same authored cells and foreground edits as the map recipes.

    Never import or run a rendering recipe: selftest needs no disc or artwork
    conversion. Fail closed for a new recipe whose geometry is not declarative.
    """
    recipes = json.loads((ROOT / 'tools/derive/recipes/everything.json').read_text())['maps']['steps']
    entry = next(e for e in recipes if 'screens/' + s['map'] in e.get('writes', []))
    tree = ast.parse((MOD / entry['script']).read_text())
    if entry['script'] == 'maps/galleries.py':
        records = [json.loads(p.read_text()) for p in (MOD / 'maps/author').rglob('*.json')]
        cfg = next(d for d in records if isinstance(d,dict) and d.get('file', '')+'.MAP' == s['map'])
        name = cfg['name']
        data = MOD / 'maps' / (name + '-data.json')
        folder = ('foreground-c' if 346 <= s['screen'] <= 357 else
                  'district-foreground' if 358 <= s['screen'] <= 365 else 'foreground')
        manifest = MOD / 'maps' / folder / ((str(s['screen']) if folder == 'foreground-c' else name) + '.json')
    else:
        files = {n.value for n in ast.walk(tree) if isinstance(n,ast.Constant)
                 and isinstance(n.value,str) and n.value.endswith('-data.json') and '\n' not in n.value}
        assert len(files) == 1, f"{s['screen']}: add a declarative geometry reader for {entry['script']}"
        data = MOD / 'maps' / files.pop()
        modules = {n.module for n in ast.walk(tree) if isinstance(n,ast.ImportFrom)}
        folder = 'foreground-depth-a' if 'foreground_depth_a' in modules else 'foreground'
        calls = [n for n in ast.walk(tree) if isinstance(n,ast.Call)
                 and isinstance(n.func,ast.Name) and n.func.id == 'apply_foreground']
        # A script that passes a variable builds its manifest name itself: no declarative manifest to read.
        literal = calls and isinstance(calls[0].args[1], ast.Constant)
        manifest = MOD / 'maps' / folder / (calls[0].args[1].value + '.json') if literal else None
    m = SimpleNamespace(**json.loads(data.read_text()))
    if manifest and manifest.exists():
        cfg = json.loads(manifest.read_text())
        for edit in cfg.get('collision', []):
            x,z = edit['tile']
            assert m.collision[z*100+x] == edit['before'], manifest.name
            m.collision[z*100+x] = edit['after']
        for edit in cfg.get('collision_tiles', []):
            x,z = edit['tile']
            assert m.collision[z*100+x] == edit['was'], manifest.name
            m.collision[z*100+x] = edit['value']
    return m


# Bounds of reviewed empty ground, not a blanket allowance by component size.
# See docs/npc-routes.md. Counts are ceilings on the 50-unit guard lattice.
# Interaction/arrival/exit checks still apply inside every accepted pocket.
EMPTY_POCKETS = {
    309: [((-2200, -440, 2200, 1300), 1544)],
    314: [((1870, 950, 2000, 1500), 24)],
    320: [((-700, -520, -650, -490), 4)],
    333: [((-1300, -940, -1150, -890), 8)],
    359: [((-740, -140, -450, 200), 42)],
    361: [((290, -840, 900, 0), 101)],
}


def accepted(screen, part, step):
    return any(len(part) <= limit * (50 // step)**2 and all(x0 <= x <= x1 and z0 <= z <= z1 for x,z in part)
               for (x0,z0,x1,z1),limit in EMPTY_POCKETS.get(screen, []))


def check_screen(s, m, step=50, closed_chests=False):
    """Subtract bodies from one walking flood per map, then split each state.

    Refine coarse failures at the engine tool's 10-unit lattice before rejecting.
    Exemptions never exempt a target or an arrival.
    """
    errors = []
    if closed_chests:
        m = SimpleNamespace(collision=list(m.collision), warps=m.warps)
        for kind,x,z,_ in s['targets']:
            if kind != 'spawn_chest': continue
            tx,tz = reach.col(x),reach.row(z)
            for row in range(tz-2,tz+2):
                for col in range(tx-2,tx+2):
                    m.collision[row*100+col] = 128
    starts = [(w['x'],w['z']) for w in m.warps if w['targetMap'] != -1 or w['x'] or w['z']]
    raw = reach.reach(m, starts, step=step, seed_policy='spawn_coordinates')
    baseline = point_components(raw, step)
    if not raw: return [f"{s['screen']}: no arrival ground"]
    for state in visible_states(s):
        npcs = [s['npcs'][i] for i in state]
        if not npcs: continue
        label = f"{s['screen']} {'+'.join(n[0] for n in npcs)}"
        free = {p for p in raw if not any(abs(p[0]-x)<=100+r and abs(p[1]-z)<=100+r for _,x,z,r in npcs)}
        for x,z in starts:
            if any(abs(x-nx)<=100+r and abs(z-nz)<=100+r for _,nx,nz,r in npcs):
                errors.append(f'{label}: arrival ({x},{z}) inside NPC')
        for bare in baseline:
            parts = point_components(bare & free, step)
            if not parts:
                errors.append(f'{label}: entire arrival component covered'); continue
            # Anchor at an actual arrival, rather than choosing the largest part:
            # the shore's usable beach is smaller than its empty wreck-side pocket.
            origin = min(starts, key=lambda a: min((a[0]-x)**2+(a[1]-z)**2 for x,z in bare))
            seed = min(bare, key=lambda p:(origin[0]-p[0])**2+(origin[1]-p[1])**2)
            connected = next((p for p in parts if seed in p), parts[0])
            for x,z in starts:
                point = min(bare, key=lambda p:(p[0]-x)**2+(p[1]-z)**2)
                if max(abs(point[0]-x),abs(point[1]-z)) <= step and point not in connected:
                    errors.append(f'{label}: arrival ({x},{z}) cut off')
            for part in parts:
                if part is connected: continue
                if not accepted(s['screen'], part, step):
                    errors.append(f'{label}: {len(part)} walking points cut off near {min(part)}')
            # Every authored exit/trigger tile that was usable remains usable.
            regions = {}
            for x,z in bare:
                tile = reach.col(x),reach.row(z)
                value = m.collision[tile[1]*100+tile[0]]
                if 110 <= value < 128 or 1 <= value < 100:
                    regions.setdefault(value,set()).add((x,z))
            for value,points in regions.items():
                if not points & connected: errors.append(f'{label}: exit/trigger {value} cut off')
            for kind,x,z,r in npcs:
                near = {p for p in bare if max(abs(p[0]-x),abs(p[1]-z))<=r+150}
                if near and not near & connected: errors.append(f'{label}: {kind} talk position cut off')
            for kind,x,z,facing in s['targets']:
                # Same chest interaction tiles as setImpassableSquare/openChest.
                tx,tz = reach.col(x),reach.row(z)
                dx,dz = ((0,0) if kind == 'spawn_item' else
                         {0:(0,4),2048:(0,-4),1024:(-4,0),3072:(4,0)}[facing])
                near = {p for p in bare if abs(reach.col(p[0])-tx-dx)<=1 and abs(reach.row(p[1])-tz-dz)<=1}
                if near and not near & connected:
                    # A wild enemy can guard a pickup without cutting the ground.
                    # Only accept a fully covered pickup zone, reachable after
                    # defeating the currently approachable wild enemies. Free
                    # but isolated ground (including exits) is never exempted.
                    if kind == 'spawn_item' and not near & free:
                        fixed = [s['npcs'][i] for i in state if not s['wild'][i]]
                        after = {p for p in bare if not any(abs(p[0]-nx)<=100+nr and abs(p[1]-nz)<=100+nr
                                                           for _,nx,nz,nr in fixed)}
                        parts_after = point_components(after, step)
                        joined = next((part for part in parts_after if seed in part), set())
                        if near & joined: continue
                    errors.append(f'{label}: {kind} at ({x},{z}) cut off')
    if errors and step == 50:
        return check_screen(s, m, step=10, closed_chests=False)
    return sorted(set(errors))


def guard(folder=None, screens=None):
    errors = []; count = states = 0
    for s in placements():
        if screens and s['screen'] not in screens: continue
        count += 1
        if not s['npcs']: continue
        m = authored_geometry(s)
        if folder is not None:
            path = folder / s['map']
            if not path.is_file():
                errors.append(f"{s['screen']}: missing generated {path.name}"); continue
            built = dwmap.MapFile(path.read_bytes())
            if list(built.collision) != list(m.collision):
                errors.append(f"{s['screen']}: authored/generated collision differs"); continue
            m = built
        states += len(visible_states(s))
        errors += check_screen(s, m)
        if any(t[0] == 'spawn_chest' for t in s['targets']):
            errors += check_screen(s, m, closed_chests=True)
    assert not errors, '\n'.join(errors)
    print(f'NPC routes: {count} new screens, {states} visibility/battle states; accepted empty pockets bounded')


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--audit', type=Path)
    p.add_argument('--maps', type=Path)
    p.add_argument('--step', type=int, default=50)
    p.add_argument('--screens', type=int, nargs='+')
    a = p.parse_args()
    if a.audit: audit(a.audit, a.step, a.screens)
    else:
        bone_field()
        guard(a.maps, a.screens)
