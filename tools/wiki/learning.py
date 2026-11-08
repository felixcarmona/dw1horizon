"""Release-only encounter extraction. Never import/execute the working story compiler.

Native MAP rows use animation slots, not technique IDs. The Python story is the
build input; its declarations, battle calls and MAPHEAD spawn branches supply
encounters. The recipe supplies the active mod files in compiler order.
"""
import ast
import json
import re


def member(name):
    return re.sub(r'[^A-Za-z0-9]', '', name)


def call_name(node):
    return node.id if isinstance(node, ast.Name) else node.attr if isinstance(node, ast.Attribute) else ''


def keywords(call):
    return {k.arg: k.value for k in call.keywords}


def literal(node, default=None):
    try:
        return ast.literal_eval(node)
    except (ValueError, TypeError):
        return default


def time_test(node, hour):
    """Three-valued evaluation: unknown quest/random tests never become true facts."""
    if isinstance(node, ast.Constant):
        return node.value
    if isinstance(node, ast.Name) and node.id == 'date_hour':
        return hour
    if isinstance(node, ast.Attribute) and ast.unparse(node) == 'clock.hour':
        return hour
    if isinstance(node, ast.UnaryOp) and isinstance(node.op, ast.Not):
        value = time_test(node.operand, hour)
        return None if value is None else not value
    if isinstance(node, ast.BoolOp):
        values = [time_test(n, hour) for n in node.values]
        if isinstance(node.op, ast.And):
            return False if False in values else None if None in values else True
        return True if True in values else None if None in values else False
    if isinstance(node, ast.Compare):
        values = [time_test(n, hour) for n in [node.left, *node.comparators]]
        if None in values:
            return None
        ops = {ast.Lt: lambda a,b:a<b, ast.LtE:lambda a,b:a<=b,
               ast.Gt:lambda a,b:a>b, ast.GtE:lambda a,b:a>=b,
               ast.Eq:lambda a,b:a==b, ast.NotEq:lambda a,b:a!=b}
        return all(ops[type(op)](a,b) for op,a,b in zip(node.ops,values,values[1:]))
    return None


def spawn_paths(body, visit, hours=frozenset(range(24)), conditional=False, guards=()):
    """Follow branches and early returns; visit each spawn with its possible hours."""
    states = [(hours, conditional, guards)]
    for node in body:
        next_states = []
        for active, guarded, predicates in states:
            if not active:
                continue
            if isinstance(node, ast.Return):
                continue
            if isinstance(node, ast.If):
                yes = frozenset(h for h in active if time_test(node.test,h) is not False)
                no = frozenset(h for h in active if time_test(node.test,h) is not True)
                unknown = any(time_test(node.test,h) is None for h in active)
                expression = ast.unparse(node.test)
                yes_guards = predicates + (expression,) if unknown else predicates
                no_guards = predicates + ('not ('+expression+')',) if unknown else predicates
                yes_states = spawn_paths(node.body,visit,yes,guarded or unknown,yes_guards)
                no_states = spawn_paths(node.orelse,visit,no,guarded or unknown,no_guards)
                if not any(isinstance(n,ast.Return) for branch in [node.body,node.orelse] for stmt in branch for n in ast.walk(stmt)):
                    # Both arms rejoin: an unrelated flag must not restrict later spawns.
                    next_states.append((active,guarded,predicates))
                else:
                    next_states += yes_states + no_states
                continue
            if isinstance(node, ast.Expr) and isinstance(node.value, ast.Call):
                visit(node.value, active, guarded, predicates)
            next_states.append((active, guarded, predicates))
        states = next_states
    return states


def usable_moves(species, placement, techniques, group=False, group_bonus=20):
    """BTL_isMoveUsable / BTL_selectEnemyMove, including zero-weight exceptions.

    Counter is reactive, never selected. Buffs gain priority over time; area
    attacks can gain priority with another living enemy. Finishers and innate
    attacks (IDs >=58) never enter battleMoveLearning's normal-move bitset.
    """
    def stat(key):
        base = species.get('wild', {}).get(key, 0)
        value = placement.get(key, base)
        return base + int(value) if isinstance(value,str) else value
    mp = placement.get('currentMP', stat('mp'))
    result = []
    for anim, weight in zip(placement.get('moves', []), placement.get('prios', [])):
        if anim == 255:
            continue
        slot = anim - 46
        names = species.get('techniques') or []
        if not 0 <= slot < len(names):
            continue  # Runtime species rows pad unused animation slots with 255.
        if names[slot] is None:
            continue
        move = resolve(names[slot], techniques)
        ident = move['id']
        if ident >= 58 or mp < move['mpCost'] * 3:
            continue
        reactive = ident == 45 and stat('speed') > 0
        buff = move['range'] == 4 and stat('brain') >= 0
        area = move['range'] == 3 and group and placement.get('unk1', 1) == 0 and group_bonus > 0
        if reactive or ident != 45 and (weight > 0 or buff or area):
            result.append((ident, 'counter' if reactive else 'group' if not weight and area else ''))
    return result


def resolve(name, techniques):
    # Same ID-qualified aliases as tools/guide/build.py.
    match = re.search(r' \((\d+)\)$', name)
    if match:
        return next(t for t in techniques if t['id'] == int(match[1]))
    matches = [t for t in techniques if t['name'] == name]
    if len(matches) != 1:
        raise ValueError('Ambiguous enemy technique: ' + name)
    return matches[0]



def shared_aliases(files):
    row = next(line for line in files['docs/reference/partner.md'].decode().splitlines() if line.startswith('| `learnedMoves[2]`'))
    pairs = re.findall(r'(0x[0-9A-Fa-f]+) and (0x[0-9A-Fa-f]+)', row)
    if len(pairs)!=2 or '(both are set)' not in row:
        raise ValueError('Review changed shared technique unlock bits')
    result = {}
    for a,b in pairs:
        a,b = int(a,16),int(b,16)
        result[a],result[b] = b,a
    return result


def sources(files, all_species, techniques, partner_rows):
    compiler = files['tools/dws/backend.py'].decode()
    for needle in ('for k in range(3)', '(40, 30, 30, 0)', "'currentMP': 500", "e['move3'] = 255"):
        if needle not in compiler:
            raise ValueError('Review changed enemy placement defaults: ' + needle)
    combat = files['docs/reference/combat.md'].decode()
    if 'no bits, items, stat gains or learning in the arena' not in combat:
        raise ValueError('Review changed arena learning behavior')
    species = {s['id']:s for s in all_species}
    enums = {}
    for s in sorted(all_species,key=lambda s:s['id']):
        enums.setdefault(member(s['name']),s)
    enums.update({member(s['name'])+str(s['id']):s for s in all_species})
    def sp(node):
        if isinstance(node, ast.Attribute) and isinstance(node.value, ast.Name) and node.value.id == 'Species':
            return enums[node.attr]
        return None
    screens = {s['id']:s for p,v in files.items() if p.startswith(('content/screens/', 'story/mods/what-the-island-forgot/screens/')) and p.endswith('.json') for s in [json.loads(v)]}
    maps = {p.rsplit('/',1)[-1][:-5].casefold():json.loads(v) for p,v in files.items() if p.startswith('content/maps/') and p.endswith('.json')}
    hooks_src = files['story/base/maphead/hooks.py'].decode()
    hooks = ast.parse(hooks_src)
    screen_ids = {}
    setups = {}
    for fn in hooks.body:
        if not isinstance(fn, ast.FunctionDef):
            continue
        for dec in fn.decorator_list:
            if isinstance(dec, ast.Attribute) and dec.attr == 'on_load' and isinstance(dec.value, ast.Call):
                name = getattr(dec.value.args[0], 'attr', None)
                line = hooks_src.splitlines()[fn.lineno-1]
                ident = int(re.search(r'# section (\d+)', line)[1])
                if name is not None: screen_ids[name] = ident
                setups[ident] = fn
    def screen_arg(node):
        if isinstance(node, ast.Constant) and isinstance(node.value,int):
            return node.value
        if isinstance(node, ast.Attribute) and node.attr in screen_ids:
            return screen_ids[node.attr]
        raise ValueError('Unreviewed encounter screen: ' + ast.unparse(node))
    def map_row(screen,slot):
        data = screens.get(screen)
        rows = maps.get(data['file'].casefold(),{}).get('digimon',[]) if data else []
        return next((dict(r,unk1=r.get('unk1',1)) for r in rows if r['slot']==slot), None)

    # Symbols are local to each base script. Mods import specific dw.base modules.
    modules = {}
    battles = {}  # (screen, slot): wild/scripted
    def battle_calls(tree, env):
        found = {}
        for fn in [n for n in ast.walk(tree) if isinstance(n,ast.FunctionDef)]:
            context = []
            if isinstance(fn,ast.FunctionDef):
                for dec in fn.decorator_list:
                    dec = dec.func if isinstance(dec,ast.Call) else dec
                    if isinstance(dec,ast.Attribute) and isinstance(dec.value,ast.Name) and dec.attr=='on_talk':
                        context.append(dec.value.id)
            for call in ast.walk(fn):
                if not isinstance(call,ast.Call) or call_name(call.func) not in ('fight','recruitable'):
                    continue
                kind = 'wild' if call_name(call.func)=='recruitable' or not call.args and not any(isinstance(n,ast.Call) and call_name(n.func) in ('send_to_city','recruit') for n in ast.walk(fn)) else 'scripted'
                names = [n.id for n in call.args if isinstance(n,ast.Name)] or context
                for name in names:
                    for record in env.get(name,[]):
                        if isinstance(record,dict) and 'species' in record:
                            found[name] = kind
                            battles[(record['screen'],record['slot'])] = kind
        for call in ast.walk(tree):
            if not isinstance(call,ast.Call) or call_name(call.func)!='dws' or not call.args: continue
            raw = literal(call.args[0], '')
            for foes in re.findall(r'battle\(foes:\s*\[([^]]+)\]', raw):
                for name in foes.split(','):
                    for record in env.get(name.strip(),[]):
                        if isinstance(record,dict) and 'species' in record:
                            found[name.strip()] = 'scripted'
                            battles[(record['screen'],record['slot'])] = 'scripted'
        return found

    scene_spawns = []
    def dynamic_spawns(tree, env, path):
        for fn in [n for n in ast.walk(tree) if isinstance(n,ast.FunctionDef)]:
            calls = [n for n in ast.walk(fn) if isinstance(n,ast.Call) and n.args]
            if not any(call_name(n.func)=='spawn' or call_name(n.func)=='dws' and 'set_digimon(' in literal(n.args[0],'') for n in calls):
                continue
            homes = set()
            for dec in fn.decorator_list:
                dec = dec.func if isinstance(dec,ast.Call) else dec
                if isinstance(dec,ast.Attribute) and isinstance(dec.value,ast.Name):
                    for v in env.get(dec.value.id,[]):
                        homes.add(v['screen'] if isinstance(v,dict) else v)
            if not homes:
                homes = {v for values in env.values() for v in values if isinstance(v,int)}
            def visit(call,hours,conditional,guards):
                if not call.args: return
                placements = []
                if call_name(call.func)=='spawn':
                    enemy = sp(call.args[0]); slot=literal(keywords(call).get('slot'))
                    if enemy and slot is not None: placements.append((enemy,slot))
                elif call_name(call.func)=='dws':
                    raw = literal(call.args[0], '')
                    for name,slot in re.findall(r'set_digimon\(species\("([^"]+)"\),\s*(\d+)',raw):
                        placements.append((enums[member(name)],int(slot)))
                for enemy,slot in placements:
                    for ident in homes:
                        row=map_row(ident,slot)
                        if row and (ident,slot) in battles:
                            scene_spawns.append(dict(screen=ident,slot=slot,species=enemy['id'],row=row,
                                                     hours=hours,conditional=True,guards=list(guards),
                                                     event=fn.name,kind='scripted',source=path))
            spawn_paths(fn.body,visit)

    for path,raw in sorted(files.items()):
        if not path.startswith('story/base/zones/') or not path.endswith('/script.py'):
            continue
        tree = ast.parse(raw.decode()); env = {}
        for node in tree.body:
            if not isinstance(node,ast.Assign) or not isinstance(node.targets[0],ast.Name) or not isinstance(node.value,ast.Call):
                continue
            name,call = node.targets[0].id,node.value
            if call_name(call.func)=='script':
                script_id = literal(call.args[0])
                env[name] = [i for i,fn in setups.items() if any(isinstance(n,ast.Call) and call_name(n.func)=='use_script' and n.args and literal(n.args[0])==script_id for n in ast.walk(fn))]
            elif call_name(call.func)=='screen':
                env[name] = [screen_arg(a) for a in call.args]
            elif isinstance(call.func,ast.Attribute) and call.func.attr=='npc' and isinstance(call.func.value,ast.Name):
                s = sp(call.args[0]); slot = literal(keywords(call).get('slot'))
                if slot is not None:
                    env[name] = [dict(screen=i,slot=slot,species=s['id'] if s else None) for i in env[call.func.value.id]]
        battle_calls(tree,env)
        dynamic_spawns(tree,env,path)
        # dw.base.<screen enum> exports the complete script's symbols.
        for value in env.values():
            if value and isinstance(value[0],int):
                for ident in value:
                    for enum,sid in screen_ids.items():
                        if sid==ident: modules[enum] = env

    encounters = list(scene_spawns)
    for ident,fn in setups.items():
        def visit(call,hours,conditional,guards):
            if call_name(call.func) != 'spawn' or not call.args:
                return
            s = sp(call.args[0]); slot = literal(keywords(call).get('slot'))
            if s is None or slot is None or not hours:
                return
            kind = battles.get((ident,slot))
            row = map_row(ident,slot)
            if kind and row:
                encounters.append(dict(screen=ident,slot=slot,species=s['id'],row=row,
                                       hours=hours,conditional=conditional,guards=list(guards),kind=kind,source='story/base/maphead/hooks.py'))
        spawn_paths(fn.body,visit)

    # Apply owned placements in exactly the release build recipe's order.
    recipe = json.loads(files['tools/derive/recipes/everything.json'])
    defaults = json.loads(files['content/battle/enemy-movesets.json'])
    placed = {}
    next_slots = {}
    for ident,data in screens.items():
        rows = maps.get(data['file'].casefold(),{}).get('digimon',[])
        placed[ident] = [dict(r, _sid=enums[r['species']]['id']) for r in rows]
        next_slots[ident] = len(rows)
    def absolute_template(row):
        base = species[row['_sid']].get('wild',{}) if '_sid' in row else {}
        result = dict(row)
        for key in ('mp','brain','speed'):
            value = row.get(key,base.get(key,100 if key!='mp' else 500))
            result[key] = base.get(key,0)+int(value) if isinstance(value,str) else value
        result['currentMP'] = row.get('currentMP',result['mp'])
        return result
    for path in recipe['story']['sources']:
        if not path.endswith('.py'):
            if re.search(r'\bplace\s*\(',files[path].decode()):
                raise ValueError('Review DWS enemy placements: '+path)
            continue  # active DWS files replace events, not placements
        tree = ast.parse(files[path].decode()); env = {}; added = []
        for node in tree.body:
            if isinstance(node,ast.ImportFrom) and node.module and node.module.startswith('dw.base.'):
                base = modules.get(node.module.split('.')[-1],{})
                for alias in node.names:
                    if alias.name=='*': env.update(base)
                    elif alias.name in base: env[alias.asname or alias.name] = base[alias.name]
            if not isinstance(node,ast.Assign) or not isinstance(node.targets[0],ast.Name) or not isinstance(node.value,ast.Call):
                continue
            name,call = node.targets[0].id,node.value; kw = keywords(call)
            if call_name(call.func) in ('screen','new_screen'):
                env[name] = [screen_arg(a) for a in call.args]
            elif isinstance(call.func,ast.Attribute) and call.func.attr=='npc' and isinstance(call.func.value,ast.Name):
                s = sp(call.args[0])
                if s is None: continue
                records = []
                for ident in env[call.func.value.id]:
                    slot = literal(kw.get('slot'),next_slots.get(ident,0))
                    next_slots[ident] = max(next_slots.get(ident,0),slot+1)
                    records.append(dict(screen=ident,slot=slot,species=s['id']))
                env[name] = records
                added.append((name,records,kw,False))
            elif call_name(call.func)=='take_over' and call.args and isinstance(call.args[0],ast.Name):
                records = [dict(r) for r in env.get(call.args[0].id,[])]
                if not records:
                    raise ValueError('Unresolved enemy takeover: '+path+'/'+name)
                if 'species' in kw:
                    for r in records: r['species'] = sp(kw['species'])['id']
                env[name] = records
                added.append((name,records,kw,True))
        fighters = battle_calls(tree,env)
        start = len(scene_spawns)
        dynamic_spawns(tree,env,path)
        encounters.extend(scene_spawns[start:])
        talked = set()
        for fn in ast.walk(tree):
            if isinstance(fn,ast.FunctionDef):
                for dec in fn.decorator_list:
                    dec = dec.func if isinstance(dec,ast.Call) else dec
                    if isinstance(dec,ast.Attribute) and dec.attr=='on_talk' and isinstance(dec.value,ast.Name):
                        talked.add(dec.value.id)
        for name,records,kw,taken in added:
            # A custom talk without any battle (shops, citizens, rewards) is not an enemy.
            noncombat = (name in talked or literal(kw.get('still')) is True) and name not in fighters
            for record in records:
                ident,sid = record['screen'],record['species']; s=species[sid]
                if not s.get('techniques'): continue
                original = map_row(ident,record['slot']) if taken else None
                if taken:
                    encounters = [e for e in encounters if (e['screen'],e['slot']) != (ident,record['slot'])]
                templates = placed.get(ident,[])
                like = kw.get('behaves_like')
                if isinstance(like,ast.Name) and env.get(like.id):
                    template = templates[env[like.id][0]['slot']]
                else:
                    template = next((r for r in templates if any(a in (1,2) for a in r.get('ai',[]))),templates[-1] if templates else {})
                row = absolute_template(original or template)
                row.setdefault('unk1',1 if template else 0)
                for key in ('mp','brain','speed'):
                    if key in kw: row[key] = literal(kw[key])
                if 'mp' in kw: row['currentMP'] = row['mp']
                if not taken or 'species' in kw:
                    default = defaults.get(str(sid))
                    row['moves'] = [46+s['techniques'].index(m) if m else 255 for m in default['moves']] if default else [46+k if k<len(s['techniques']) else 255 for k in range(3)]+[255]
                    row['prios'] = default['weights'] if default else row.get('prios',[40,30,30,0])
                    if not default and not any(row['prios'][:min(3,len(s['techniques']))]):
                        row['prios'] = [40,30,30,0]
                row['_sid'] = sid
                placed.setdefault(ident,[]).append(row)
                if noncombat: continue
                hours = frozenset(range(24)); conditional=False
                if 'when' in kw:
                    hours = frozenset(h for h in hours if time_test(kw['when'],h) is not False)
                    conditional = any(time_test(kw['when'],h) is None for h in hours)
                if not hours: continue
                encounters.append(dict(**record,row=row,hours=hours,conditional=conditional,
                                       kind=fighters.get(name,'wild'),guards=[ast.unparse(kw['when'])] if 'when' in kw else [],source=path))

    special = {s['id'] for s in partner_rows if s['spoiler']}
    result = {t['id']:[] for t in techniques}
    group_bonus = json.loads(files['content/tables/battle-formulas.json'])['battleFormulas']['ai']['enemyGroupMoveWeight']
    for e in encounters:
        # A second enemy must have an overlapping spawn window on this screen.
        group = any(o is not e and o['screen']==e['screen'] and o['slot']!=e['slot'] and o['hours'] & e['hours'] for o in encounters)
        for move,condition in usable_moves(species[e['species']],e['row'],techniques,group,group_bonus):
            row = {k:e[k] for k in ('species','screen','kind','conditional','guards','source')}
            row.update(hours=sorted(e['hours']),condition=condition,
                       spoiler=e['kind']=='scripted' or e['screen']>=300 or e['species'] in special)
            if row not in result[move]: result[move].append(row)
    # Slot duplicates are irrelevant to the player; merge identical availability.
    for ident,rows in result.items():
        result[ident] = sorted(rows,key=lambda r:(r['spoiler'],species[r['species']]['name'],r['screen'],r['hours']))
    direct = {ident:list(rows) for ident,rows in result.items()}
    for ident,other in shared_aliases(files).items():
        result[ident] += [dict(row,via=other) for row in direct[other]]
    return result


def brains(files, techniques, partners):
    table = json.loads(files['content/tables/brain-training.json'])['brainTraining']
    gains = json.loads(files['content/tables/training-gains.json'])
    rules = gains['trainRules']['brains']
    if rules != gains['train2Rules']['brains']:
        raise ValueError('Review differing Brains gym learning rules')
    result = {}
    for move in techniques:
        positions = []
        for element,order in table['techniques'].items():
            if move['id'] not in order: continue
            k = order.index(move['id'])
            weights = table['weights'][k]
            possible = any(element in s['slots'] and weights[s['slots'].index(element)] > 0
                           and any(m['id']==move['id'] for m in s['moves']) for s in partners)
            if possible: positions.append(dict(element=element,position=k+1,weights=weights))
        result[move['id']] = dict(marks=rules['learnMarks'],orders=rules['orderMarks'],positions=positions)
    for ident,other in shared_aliases(files).items():
        if not result[ident]['positions'] and result[other]['positions']:
            result[ident] = dict(result[other],via=other)
    return result
