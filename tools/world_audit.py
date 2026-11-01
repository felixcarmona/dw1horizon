#!/usr/bin/env python3
"""Compare conditional world reachability using committed topology and story sources.

Writes ORIGINAL.json, HORIZON.json and findings.json under --out (default
build/world-audit). No disc or emulator is needed. See docs/mods/world-audit.md
for the abstraction, reviewed physical gates and its limitations.
"""
from __future__ import annotations

import argparse
import ast
from collections import deque
from dataclasses import asdict, dataclass
from functools import lru_cache
import json
from pathlib import Path
import re
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'tools'))
from dws.py import naming  # noqa: E402
from dws.minitoml import load_toml  # noqa: E402

MOD = Path('story/mods/what-the-island-forgot')
UNKNOWN = None


def read(path):
    return json.loads((ROOT / path).read_text())


def profile_state(profile):
    state = {}
    if profile.get('fresh'):
        names = load_toml(ROOT / 'story/names.toml')
        for value in names['flags'].values():
            state[value if isinstance(value, str) else value['name']] = False
        for p in (ROOT / 'story/base/zones').rglob('script.py'):
            state.update({s: False for s in re.findall(r'recruited\(Species\.\w+\)', p.read_text())})
    state.update(profile['state'])
    return state


def literal(node):
    try:
        return ast.literal_eval(node)
    except (ValueError, TypeError):
        return None


def both(a, b):
    if a == 'False' or b == 'False': return 'False'
    if a == 'True': return b
    if b == 'True' or a == b: return a
    return f'({a}) and ({b})'


def either(a, b):
    if a == 'True' or b == 'True': return 'True'
    if a == 'False': return b
    if b == 'False' or a == b: return a
    return f'({a}) or ({b})'


@lru_cache(maxsize=None)
def expression_tree(expression):
    tree = ast.parse(expression, mode='eval').body
    for n in ast.walk(tree):
        if isinstance(n, ast.expr): n.audit_text = ast.unparse(n)
    return tree


def possible(expression, state):
    """Three-valued evaluator: unknown tests retain both branches, never close a way."""
    def ev(n):
        text = n.audit_text
        if text in state:
            return state[text]
        if isinstance(n, ast.Constant):
            return n.value
        if isinstance(n, ast.UnaryOp) and isinstance(n.op, ast.Not):
            v = ev(n.operand)
            return None if v is None else not v
        if isinstance(n, ast.BoolOp):
            vs = [ev(v) for v in n.values]
            if isinstance(n.op, ast.And):
                return False if False in vs else (None if None in vs else True)
            return True if True in vs else (None if None in vs else False)
        if isinstance(n, ast.Compare) and len(n.ops) == 1:
            a, b = ev(n.left), ev(n.comparators[0])
            if a is None or b is None:
                return None
            op = n.ops[0]
            if isinstance(op, ast.Eq): return a == b
            if isinstance(op, ast.NotEq): return a != b
            if isinstance(op, ast.Lt): return a < b
            if isinstance(op, ast.LtE): return a <= b
            if isinstance(op, ast.Gt): return a > b
            if isinstance(op, ast.GtE): return a >= b
        return None
    return ev(expression_tree(expression)) is not False


@dataclass(frozen=True)
class Edge:
    source: int
    target: int
    entry: int
    condition: str
    evidence: str
    kind: str
    slot: int = -1
    effects: tuple = ()


class World:
    def __init__(self):
        self.members = {v: k for k, v in naming.screen_members().items()}
        self.dispatch = read('tools/data/world-dispatch.json')['maps']
        self.policy = read('tools/data/world-gates.json')
        self.names = {}
        self.script_screens = {}
        for p in sorted((ROOT / 'story/base/maphead').glob('screen*.dws')):
            for script, screen in re.findall(r'set_script\((\d+),\s*(\d+)\)', p.read_text()):
                self.script_screens.setdefault(int(script), set()).add(int(screen))
        self.physical = []
        for line_number, line in enumerate((ROOT / 'docs/reference/world.md').read_text().splitlines(), 1):
            cols = [x.strip() for x in line.split('|')]
            if len(cols) < 12 or not cols[1].isdigit():
                continue
            i = int(cols[1])
            if i > 254: continue
            self.names[i] = cols[3]
            active = self.dispatch.get(str(i), {}).get('exits', [])
            for slot, target, entry in re.findall(r'(\d+)→(\d+)\.(-?\d+)', cols[9]):
                if int(slot) in active:
                    self.physical.append(Edge(i, int(target), int(entry), 'True',
                                              f'docs/reference/world.md:{line_number}', 'map', int(slot)))
        self.modules = {}
        self.exports = {}
        self.sections = {}
        self.unresolved = []
        self.conditions = []
        for p in sorted((ROOT / 'story/base/maphead').glob('*.dws')):
            for line, text in enumerate(p.read_text().splitlines(), 1):
                if re.search(r'\b(if|unless)\s*\(', text):
                    self.conditions.append({'evidence': f'{p.relative_to(ROOT)}:{line}',
                                            'condition': text.strip(), 'syntax': 'DWS / MAPHEAD'})

    def screen_id(self, n):
        if isinstance(n, ast.Constant) and isinstance(n.value, int): return n.value
        if isinstance(n, ast.Attribute) and ast.unparse(n.value) == 'Screen':
            return self.members.get(n.attr)
        return None

    def index(self, paths):
        for p in paths:
            tree = ast.parse((ROOT / p).read_text())
            for n in ast.walk(tree):
                if isinstance(n, (ast.If, ast.While)):
                    self.conditions.append({'evidence': f'{p}:{n.lineno}', 'condition': ast.unparse(n.test)})
                elif isinstance(n, ast.keyword) and n.arg == 'when':
                    self.conditions.append({'evidence': f'{p}:{n.value.lineno}', 'condition': ast.unparse(n.value)})
                elif isinstance(n, ast.Call) and ast.unparse(n.func) == 'dws' and n.args and isinstance(n.args[0], ast.Constant):
                    for offset, text in enumerate(n.args[0].value.splitlines()):
                        if re.search(r'\b(if|unless)\s*\(', text):
                            self.conditions.append({'evidence': f'{p}:{n.lineno + offset}',
                                                    'condition': text.strip(), 'syntax': 'literal DWS'})
            env = {}
            for n in tree.body:
                if not isinstance(n, ast.Assign) or not isinstance(n.value, ast.Call): continue
                call = n.value
                name = ast.unparse(call.func)
                if name in ('screen', 'new_screen') and call.args:
                    sid = self.screen_id(call.args[0])
                    if sid is not None:
                        env[ast.unparse(n.targets[0])] = (sid, 'screen', 'True')
                elif name == 'script' and call.args:
                    homes = self.script_screens.get(literal(call.args[0]), set())
                    if len(homes) == 1:
                        env[ast.unparse(n.targets[0])] = (next(iter(homes)), 'screen', 'True')
                elif isinstance(call.func, ast.Attribute) and call.func.attr == 'npc':
                    owner = env.get(ast.unparse(call.func.value))
                    if owner:
                        cond = next((ast.unparse(k.value) for k in call.keywords if k.arg == 'when'), 'True')
                        env[ast.unparse(n.targets[0])] = (owner[0], 'npc', cond)
                elif name == 'entity':
                    homes = {v[0] for v in env.values() if v[1] == 'screen'}
                    if len(homes) == 1:
                        env[ast.unparse(n.targets[0])] = (next(iter(homes)), 'npc', 'True')
            self.modules[p] = (tree, env)
            script_match = re.search(r'/s(\d+)(?:-|/)', str(p))
            if script_match:
                lines = (ROOT / p).read_text().splitlines()
                for fn in tree.body:
                    if not isinstance(fn, ast.FunctionDef): continue
                    section = re.search(r'# section (\d+)', lines[fn.lineno - 1])
                    if section:
                        self.sections[int(script_match[1]), int(section[1])] = (p, fn)
            if str(p).startswith('story/base/zones/'):
                for member, sid in self.members.items():
                    if any(v[0] == sid for v in env.values()):
                        self.exports['dw.base.' + member] = env
        # Resolve imports without executing the story or its map recipes.
        for tree, env in self.modules.values():
            for n in tree.body:
                if isinstance(n, ast.ImportFrom) and n.module in self.exports:
                    for alias in n.names:
                        value = self.exports[n.module].get(alias.name)
                        if value: env[alias.asname or alias.name] = value
            # An NPC placed on an imported screen (`bridge.npc(...)`) can only be bound now that the import resolved.
            for n in tree.body:
                if (isinstance(n, ast.Assign) and isinstance(n.value, ast.Call)
                        and isinstance(n.value.func, ast.Attribute) and n.value.func.attr == 'npc'):
                    target = ast.unparse(n.targets[0])
                    owner = env.get(ast.unparse(n.value.func.value))
                    if owner and target not in env:
                        cond = next((ast.unparse(k.value) for k in n.value.keywords if k.arg == 'when'), 'True')
                        env[target] = (owner[0], 'npc', cond)

    def script_edges(self, paths):
        result = []
        for p in paths:
            tree, env = self.modules[p]
            functions = [n for n in tree.body if isinstance(n, ast.FunctionDef)]
            funcs = {n.name: n for n in functions if not n.decorator_list}
            for fn in functions:
                for dec in fn.decorator_list:
                    obj = dec.func if isinstance(dec, ast.Call) else dec
                    if not isinstance(obj, ast.Attribute) or not (obj.attr.startswith('on_') or obj.attr == 'section'): continue
                    owner = env.get(ast.unparse(obj.value))
                    if not owner: continue
                    source, owner_kind, npc_cond = owner
                    kind = 'section' if obj.attr == 'section' else obj.attr[3:]
                    slot = literal(dec.args[0]) if isinstance(dec, ast.Call) and dec.args else -1
                    if str(p).startswith('story/base/') and kind == 'step':
                        if slot not in self.dispatch.get(str(source), {}).get(kind, []): continue
                    guard = next((ast.unparse(k.value) for k in dec.keywords if k.arg == 'when'), 'True') if isinstance(dec, ast.Call) else 'True'
                    cond = both(guard, npc_cond)
                    self.walk(fn.body, cond, source, p, result, funcs, set(), kind, slot)
        # One DG script serves several original screen variants. Its tile/object
        # handlers run on each variant that exposes that dispatch number.
        expanded = []
        for e in result:
            homes = next((ss for ss in self.script_screens.values() if e.source in ss), {e.source})
            for source in sorted(homes):
                if e.evidence.startswith('story/base/') and e.kind == 'step' and e.slot not in self.dispatch.get(str(source), {}).get('step', []):
                    continue
                expanded.append(Edge(source, e.target, e.entry, e.condition, e.evidence, e.kind, e.slot, e.effects))
        return expanded

    def walk(self, body, condition, source, path, result, funcs, stack, kind, slot, effects=None):
        """Keep sequential return/warp semantics, both choices, and helper calls."""
        current = condition
        effects = {} if effects is None else effects
        for n in body:
            if current == 'False': break
            if isinstance(n, ast.If):
                test = ast.unparse(n.test)
                yc, nc = both(current, test), both(current, f'not ({test})')
                yes = self.walk(n.body, yc, source, path, result, funcs, stack, kind, slot, dict(effects))
                no = self.walk(n.orelse, nc, source, path, result, funcs, stack, kind, slot, dict(effects))
                if yes != yc or no != nc:
                    current = either(yes, no)
            elif isinstance(n, ast.Match):
                tails = [self.walk(c.body, current, source, path, result, funcs, stack, kind, slot, dict(effects)) for c in n.cases]
                if any(s != current for s in tails):
                    current = 'False'
                    for s in tails: current = either(current, s)
            elif isinstance(n, (ast.For, ast.While)):
                self.walk(n.body, current, source, path, result, funcs, stack, kind, slot, dict(effects))
            elif isinstance(n, (ast.Expr, ast.Return)):
                call = n.value
                if isinstance(call, ast.Call):
                    name = ast.unparse(call.func)
                    if name == 'warp':
                        target = self.screen_id(call.args[0])
                        entry = next((literal(k.value) for k in call.keywords if k.arg == 'entry'), 0)
                        if target is None:
                            self.unresolved.append(f'{path}:{n.lineno}: {ast.unparse(call)}')
                        else:
                            result.append(Edge(source, target, entry, current, f'{path}:{n.lineno}', kind, slot, tuple(effects.items())))
                        current = 'False'
                    elif name in funcs and name not in stack:
                        current = self.walk(funcs[name].body, current, source, path, result, funcs, stack | {name}, kind, slot, effects)
                    elif name == 'jump_to_script' and len(call.args) >= 2:
                        key = tuple(literal(a) for a in call.args[:2])
                        if key in self.sections and key not in stack:
                            target_path, fn = self.sections[key]
                            target_tree = self.modules[target_path][0]
                            helpers = {f.name: f for f in target_tree.body
                                       if isinstance(f, ast.FunctionDef) and not f.decorator_list}
                            self.walk(fn.body, current, source, target_path, result,
                                      helpers, stack | {key}, kind, slot, dict(effects))
                        elif key not in self.sections:
                            self.unresolved.append(f'{path}:{n.lineno}: {ast.unparse(call)}')
                        current = 'False'
                    elif isinstance(call.func, ast.Attribute) and call.func.attr in ('set', 'clear'):
                        value = literal(call.args[0]) if call.args else call.func.attr == 'set'
                        if value is not None: effects[ast.unparse(call.func.value)] = value
                    elif name in ('recruit', 'unrecruit') and call.args:
                        effects[f'recruited({ast.unparse(call.args[0])})'] = name == 'recruit'
                    elif name == 'dws' and call.args and isinstance(call.args[0], ast.Constant):
                        raw = call.args[0].value
                        # Literal DWS is retained as evidence; reviewed physical gate
                        # annotations below constrain cross-area legacy jumps.
                        for target, entry in re.findall(r'warp_to\(\s*(\d+)\s*,\s*(\d+)', raw):
                            result.append(Edge(source, int(target), int(entry), current,
                                               f'{path}:{n.lineno} (literal DWS)', 'literal', slot))
                        if raw.strip() == 'return;': current = 'False'
                if isinstance(n, ast.Return): return 'False'
        return current

    def gates(self, edges):
        out = []
        for e in edges:
            tests = [e.condition]
            for gate in self.policy['gates']:
                region = gate['screens']
                if e.target in region and e.source not in region and ('from' not in gate or e.source in gate['from']):
                    tests.append(gate['condition'])
            out.append(Edge(e.source, e.target, e.entry, ' and '.join(f'({t})' for t in tests), e.evidence, e.kind, e.slot, e.effects))
        return out

    def new_maps(self):
        out = []
        for p in sorted((ROOT / MOD / 'screens').glob('*.json')):
            screen = json.loads(p.read_text())
            i = screen['id']; self.names[i] = screen['caption']
            candidates = list((ROOT / MOD / 'maps').glob('*-data.json'))
            data = None
            for c in candidates:
                if c.stem == p.stem.split('-', 1)[1] + '-data': data = c; break
            if i == 311: data = ROOT / MOD / 'maps/wall-of-hearts-data.json'
            if i == 313: data = ROOT / MOD / 'maps/infinity-engine-data.json'
            if i == 301: data = ROOT / MOD / 'maps/rift-data.json'
            if i == 303: data = ROOT / MOD / 'maps/descent-data.json'
            if data is None and i not in (302, 366, 367, 368):
                self.unresolved.append(f'{p.relative_to(ROOT)}: no reviewed physical map source')
            if data:
                d = json.loads(data.read_text())
                for k, w in enumerate(d.get('warps', [])):
                    if w['targetMap'] >= 0 and 110 + k in d['collision']:
                        if i in (310, 311) and k == 0:
                            # wall-of-hearts.py overrides the old authoring JSON.
                            w = dict(w, targetMap=97, targetExit=0)
                        out.append(Edge(i, w['targetMap'], w['targetExit'], 'True', str(data.relative_to(ROOT)), 'map', k))
        # Recipe constants for added exits on original maps, and the hand-built Shaft.
        for p in sorted((ROOT / MOD / 'maps').glob('*.py')):
            t = p.read_text(); constants = {}
            for n in ast.parse(t).body:
                if isinstance(n, ast.Assign):
                    value = literal(n.value)
                    for target in n.targets:
                        if isinstance(target, ast.Name) and value is not None: constants[target.id] = value
            if 'TARGET' in constants:
                donor = re.search(r"src = extracted\('([^']+)'\)", t)
                if donor:
                    ids = [int(q.name.split('-', 1)[0]) for q in (ROOT / 'content/screens').glob('*.json')
                           if json.loads(q.read_text()).get('file') == donor[1]]
                    for i in ids:
                        target, entry = constants['TARGET']
                        # These recipes deliberately paint steps rather than exits.
                        if p.stem not in ('koda03-passage', 'koda07-mouth', 'chka01-trapdoor'):
                            out.append(Edge(i, target, entry, 'True', str(p.relative_to(ROOT)), 'map', constants.get('WARP', 1)))
        out += [Edge(302, 48, 1, 'True', str(MOD / 'maps/shaft.py'), 'map', 0),
                Edge(302, 300, 0, 'True', str(MOD / 'maps/shaft.py'), 'map', 1)]
        return out

    def graphs(self):
        base_paths = sorted(p.relative_to(ROOT) for p in (ROOT / 'story/base/zones').rglob('script.py'))
        mod_paths = sorted(p.relative_to(ROOT) for folder in ('arcs', 'district', 'city') for p in (ROOT / MOD / folder).rglob('*.py')) + [MOD / 'early-game.py']
        hooks = Path('story/base/maphead/hooks.py')
        self.index(base_paths + mod_paths + [hooks])
        base = self.physical + self.script_edges(base_paths)
        # The Auto Pilot's global return dispatcher. A wildcard is expanded to
        # the current source by reachable(); its original variant conditions
        # remain intact. Global TELEPORT's Birdramon bindings follow below.
        hook_tree = self.modules[hooks][0]
        for fn in hook_tree.body:
            if isinstance(fn, ast.FunctionDef) and fn.name == 'sec1245':
                self.walk(fn.body, 'has(Item.AutoPilot)', '*', hooks, base, {}, set(), 'return', -1)
        # C transport menu, original US table; destination flags are documented in world.md.
        for target, entry, flag, cost in [(38, 9, 221, 1000), (70, 9, 190, 1000), (79, 9, 188, 1500),
                                          (93, 9, 351, 2000), (119, 9, 147, 2500), (105, 0, 210, 2500)]:
            base.append(Edge(207, target, entry, f'recruited(Species.Birdramon) and trigger({flag}) and money >= {cost}',
                             'docs/reference/world.md:Birdramon transport', 'transport'))
        original = self.gates(base)
        horizon = list(original)
        horizon += self.new_maps() + self.script_edges(mod_paths)
        # Replacement collision tiles and variant aliases are part of the recipes.
        horizon = [e for e in horizon if not (e.kind == 'map' and (e.source, e.slot) in {(14, 0), (34, 2), (41, 1), (303, 0)})]
        horizon += [Edge(367, 14, 0, 'True', str(MOD / 'maps/stone-bridge.py'), 'map', 0),
                    Edge(367, 44, 0, 'True', str(MOD / 'maps/stone-bridge.py'), 'map', 1),
                    Edge(367, 34, 2, 'True', str(MOD / 'maps/stone-bridge.py'), 'map', 2)]
        # New variants use the existing screen's handlers and physical exits.
        for variant, old in [(366, 129), (368, 42)]:
            horizon += [Edge(variant, e.target, e.entry, e.condition, e.evidence, e.kind, e.slot, e.effects)
                        for e in list(horizon) if e.source == old]
        revised = []
        for e in horizon:
            condition = e.condition
            if e.source == 92 and e.target == 97 and e.kind == 'map':
                condition = either(condition, 'root3')
            if e.source in range(168, 180) and e.target in (142, 152, 309):
                # city-dock.py's earlier hooks return before all three menus.
                # ferry_elapsed_days is the output of its dated countdown,
                # not a new game flag or a persistent pstat.
                available = '(not whamon_hurt and (not seadramon_chased or ferry_elapsed_days >= 5)) or (whamon_hurt and ferry_elapsed_days >= 10)'
                condition = both(condition, available)
            revised.append(Edge(e.source, e.target, e.entry, condition, e.evidence, e.kind, e.slot, e.effects))
        represented = {e.evidence for e in revised}
        for path in mod_paths:
            for node in ast.walk(self.modules[path][0]):
                if isinstance(node, ast.Call) and ast.unparse(node.func) == 'warp':
                    evidence = f'{path}:{node.lineno}'
                    if evidence not in represented:
                        self.unresolved.append(evidence + ': authored warp has no graph edge')
        return original, revised

    def verify_maps(self, horizon, directory):
        """Check the committed model against recipes' actual physical exit output."""
        import dwmap
        modeled = {(e.source, e.slot, e.target, e.entry) for e in horizon if e.kind == 'map'}
        actual = set()
        checked = set()
        files = {p.stem: p for p in (ROOT / 'extracted/MAP').rglob('*.MAP')}
        for folder in ('screens', 'retouch'):
            files.update({p.stem: p for p in (directory / folder).glob('*.MAP')})
        for folder in (ROOT / 'content/screens', ROOT / MOD / 'screens'):
            for p in folder.glob('*.json'):
                d = json.loads(p.read_text())
                src = files.get(d.get('file'))
                if src is None: continue
                try: m = dwmap.MapFile(src.read_bytes())
                except (ValueError, IndexError): continue
                checked.add(d['id'])
                for slot, w in enumerate(m.warps):
                    if w['targetMap'] >= 0 and 110 + slot in m.collision:
                        actual.add((d['id'], slot, w['targetMap'], w['targetExit']))
        return {'checked': len(checked), 'unmodeled': sorted(actual - modeled),
                'absent': sorted(e for e in modeled - actual if e[0] in checked)}


def reachable(edges, state, starts=(109,)):
    # Developer menus are never a story route, including in partial frontiers
    # where every unrelated predicate would otherwise remain unknown.
    state = {**state, 'debug_mode': False, 'trigger(54)': False}
    adjacency = {}
    for e in edges:
        if any(key in state and state[key] != value for key, value in e.effects): continue
        if possible(e.condition, state): adjacency.setdefault(e.source, []).append(e)
    # Keep arrivals distinct: an exit onto the far side of a boss trigger must
    # not disappear into an earlier visit to the same screen's near side.
    paths = {s: [] for s in starts}
    queue = deque((s, -1, []) for s in starts)
    visited = {(s, -1) for s in starts}
    while queue:
        source, arrival, path = queue.popleft()
        for e in adjacency.get(source, []) + adjacency.get('*', []):
            if 'arrival_entry' in e.condition and not possible(e.condition, dict(state, arrival_entry=arrival)):
                continue
            node = (e.target, e.entry)
            if node in visited: continue
            if e.source == '*':
                e = Edge(source, e.target, e.entry, e.condition, e.evidence, e.kind, e.slot, e.effects)
            next_path = path + [e]
            paths.setdefault(e.target, next_path)
            visited.add(node); queue.append((e.target, e.entry, next_path))
    return paths


def audit(world, original, horizon):
    findings = []
    allow = read('tools/data/world-allowlist.json')
    for profile in world.policy['profiles']:
        state = profile_state(profile)
        before = reachable(original, state)
        after = reachable(horizon, state)
        for target in sorted(set(after) - set(before)):
            if target >= 255: continue
            allowed = next((a for a in allow if a['profile'] == profile['name'] and target in a['screens'] and a.get('reason')), None)
            findings.append(dict(profile=profile['name'], screen=target, name=world.names.get(target),
                                 allowed=bool(allowed), reason=allowed['reason'] if allowed else None,
                                 path=[asdict(e) for e in after[target]]))
    return findings


def baseline_changes(world, original):
    frozen = read('tools/data/world-baseline.json')['profiles']
    changes = []
    for profile in world.policy['profiles']:
        actual = set(reachable(original, profile_state(profile)))
        expected = set(frozen.get(profile['name'], []))
        if actual != expected or profile['name'] not in frozen:
            changes.append({'profile': profile['name'], 'added': sorted(actual - expected),
                            'removed': sorted(expected - actual)})
    return changes


def arc_audit(world, horizon):
    findings = []
    allow = read('tools/data/world-allowlist.json')
    for frontier in world.policy.get('arc_frontiers', []):
        paths = reachable(horizon, frontier['state'])
        for target in frontier['closed_screens']:
            if target not in paths: continue
            exception = next((a for a in allow if a['profile'] == frontier['name']
                              and target in a['screens'] and a.get('reason')), None)
            findings.append(dict(profile=frontier['name'], screen=target, name=world.names.get(target),
                                 allowed=bool(exception), reason=exception['reason'] if exception else None,
                                 path=[asdict(e) for e in paths[target]]))
    return findings


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--out', type=Path, default=Path('build/world-audit'))
    parser.add_argument('--built-maps', type=Path, help='also validate the model against built screens/ and retouch/')
    args = parser.parse_args()
    world = World(); original, horizon = world.graphs()
    findings = audit(world, original, horizon)
    arc_findings = arc_audit(world, horizon)
    drift = baseline_changes(world, original)
    args.out.mkdir(parents=True, exist_ok=True)
    for name, value in [('ORIGINAL', [asdict(e) for e in original]), ('HORIZON', [asdict(e) for e in horizon]),
                        ('findings', findings), ('conditions', world.conditions), ('unresolved', world.unresolved),
                        ('baseline-drift', drift), ('arc-findings', arc_findings)]:
        (args.out / (name + '.json')).write_text(json.dumps(value, indent=2) + '\n')
    failures = [f for f in findings if not f['allowed']]
    arc_failures = [f for f in arc_findings if not f['allowed']]
    map_errors = False
    if args.built_maps:
        comparison = world.verify_maps(horizon, args.built_maps)
        (args.out / 'map-coverage.json').write_text(json.dumps(comparison, indent=2) + '\n')
        map_errors = bool(comparison['unmodeled'] or comparison['absent'])
        print('physical map coverage:', comparison)
    for f in failures:
        print(f'{f["profile"]}: {f["screen"]} {f["name"]}: ' + ' -> '.join(map(str, [109] + [e['target'] for e in f['path']])))
    print(f'world audit: {len(original)} original edges, {len(horizon)} Horizon edges; {len(failures)} unreviewed reachability differences')
    for f in arc_failures:
        print(f'arc {f["profile"]}: {f["screen"]}: ' + ' -> '.join(map(str, [109] + [e['target'] for e in f['path']])))
    print(f'arc audit: {len(arc_failures)} unreviewed entries; {sum(f["allowed"] for f in arc_findings)} documented exceptions')
    if drift: print('original baseline changed:', drift)
    return bool(failures or arc_failures or world.unresolved or map_errors or drift)


if __name__ == '__main__':
    sys.exit(main())
