#!/usr/bin/env python3
"""The game's tables as committed JSON, the source of truth of the build (docs/mods/data-sources.md).

Like content/species (tools/species.py), one folder per domain, complete: the build writes the executable's tables from
these files and never from the disc's values (all or none per domain: a folder that misses a file stops the build).

  content/techniques/<id>-<name>.json   MOVE_DATA row + MOVE_LEARN_CHANCES row (ids 0..121)
  content/items/<id>-<name>.json        ITEM_PARA row (+ the species an evolution item 71..114 gives) (ids 0..127)
  content/tables/<name>.json            type-factors, join-chances, tournaments, brain-training

An id without a file is a technique or an item the game does not have (the build starts from zero):
its row is empty (a technique: no power, learned nowhere; an item: no name, not dropped, not sold). What still names it
is an error of the lint (a species list, a new-game technique, brain training, a drop, a favourite food) or of
tools/missing_refs.py (the story's uses).

  tools/content.py extract [--force]      write the folders from the player's disc (refuses to overwrite edited files)
  tools/content.py lint                   check them (and what removed entries are still used by)
  tools/content.py fmt [--check]          canonical layout
  tools/content.py diff                   what the files change against the disc
"""
import argparse, collections, glob, json, os, re, sys
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, 'tools'))
import species as S

CONTENT = os.path.join(ROOT, 'content')
TECH_DIR, ITEM_DIR, TABLE_DIR, SCREEN_DIR = (os.path.join(CONTENT, d) for d in ('techniques', 'items', 'tables', 'screens'))
NUM_SCREENS = 255            # the original screens: MAP_ENTRIES rows (the files of 255 and up are SCRN.DAT records, tools/screens.py)
NUM_ALL_SCREENS = 1024       # include/dw/ids.h NUM_SCREENS
ELEMENTS = ['fire', 'battle', 'air', 'nature', 'ice', 'mech', 'filth']
NUM_TECHS, NUM_ITEMS, NUM_LEARN = 122, 128, 58
EVO_ITEM_FIRST, EVO_ITEM_LAST = 0x47, 0x72
TECH_KEYS = ['id', 'name', 'element', 'power', 'mpCost', 'distance', 'range', 'accuracy', 'status',
             'statusChance', 'iframes', 'unk3', 'unk4', 'unk5', 'learnChances']
ITEM_KEYS = ['id', 'name', 'value', 'meritValue', 'sortingValue', 'itemColor', 'droppable', 'unk',
             'evolution_target', 'effect']
TABLES = {'type-factors': 'typeFactors', 'join-chances': 'joinChances', 'tournaments': 'tournaments',
          'brain-training': 'brainTraining', 'doors': 'doors', 'toilets': 'toilets'}
# small tables of the executable, grouped by subject (balance.py SMALL_TABLES: symbol and element format of each key)
GROUPED = {'cards': ['cards', 'cardPrices'],
           'shops': ['shopMaps', 'arenaMaps', 'shopkeepers', 'recyclableItems', 'mojyamonGives', 'mojyamonTakes', 'birdraTransport'],
           'inventories': ['initialInventoryItems', 'initialInventoryAmounts', 'defaultInventoryItems', 'defaultInventoryAmounts'],
           'partner-rules': ['sleepPatterns', 'statLimits', 'babies', 'reincarnationBabies', 'healingValues', 'healEffectVariant'],
           'battle-rules': ['targetAttackerChance', 'statGainEnemyFactors', 'vsBattleCounts', 'concaveScreens'],
           'world': ['mapLights'],
           'fishing': ['fishKinds', 'fishBiteChance', 'fishBaitChances', 'fishingMaps'],
           'fishing-rules': ['fishingRules'],
           'curling': ['curlingRules', 'curlingWeights', 'curlingStartTypes', 'curlingRingPoints', 'curlingRings', 'curlingObstacleX'],
           'slot-machine': ['slotReels', 'slotAssist'],
           'effects': ['conditionFxOffsets', 'auraTypes'],
           'effect-donors': ['effectDonors'],
           'medals': ['medals'],
           'tamer-level': ['tamerLevel'],
           'care-rules': ['careRules'],
           'clock': ['clock'],
           'economy': ['economy'],
           'battle-formulas': ['battleFormulas'],
           'new-game': ['newGame'],
           'tournament-rules': ['tournamentRules', 'tournamentRemap', 'stdArena'],
           'daily-rules': ['dailyRules'],
           'daytime': ['daytime'],
           'species-rules': ['modelScale', 'animatedTexture'],
           'training': ['training', 'training2'],
           'training-gains': ['trainGain', 'train2Gain', 'trainRules', 'train2Rules'],
           'vs-unlock': ['vsUnlock'],
           'evolution-rules': ['evolutionTiming', 'evolutionFresh', 'evolutionUltimate', 'evolutionSpecial', 'evolutionRules', 'evolutionItemRules', 'evolutionFormula']}
# one value written to several copies of a table (the BTL, STD and VS overlays; TRN and TRN2)
COPIES = {'auraTypes': ['auraTypesStd', 'auraTypesVs'], 'slotReels': ['slotReelsb'], 'slotAssist': ['slotAssistb']}
SCREEN_KEYS = ['id', 'file', 'tims8', 'tims4', 'sound_bank', 'day_night', 'reads_digimon', 'flag20', 'doors', 'toilet',
               'caption', 'fileBytes']
EMPTY_SCREEN = {'file': '', 'tims8': 0, 'tims4': 0, 'flags': 0, 'doors': 0, 'toilet': 0, 'caption': 0}


def spot_maps(doc):
    return [str(r['map']) for r in doc['trainingScreens'] if r['map'] != -1]


def slug(name):
    return re.sub(r'[^a-z0-9]+', '-', name.lower()).strip('-') or 'unnamed'


def dumps(v, indent=0):
    """JSON with short lists and dicts on one line (as the species files)."""
    one = json.dumps(v, ensure_ascii=False)
    if len(one) + indent <= 110 or not isinstance(v, (dict, list)): return one
    pad = ' ' * (indent + 2)
    if isinstance(v, list): return '[\n' + ',\n'.join(pad + dumps(x, indent + 2) for x in v) + '\n' + ' ' * indent + ']'
    return '{\n' + ',\n'.join(f'{pad}{json.dumps(k)}: {dumps(x, indent + 2)}' for k, x in v.items()) + '\n' + ' ' * indent + '}'


def write(path, d):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    open(path, 'w').write(dumps(d) + '\n')


# ------------------------------------------------------------------------------------------------ disc -> files
def tech_file(i, row, name):
    d = collections.OrderedDict(id=i, name=name)
    sp = row['special']
    d['element'] = ELEMENTS[sp] if sp < len(ELEMENTS) else sp
    for k in TECH_KEYS[3:-1]: d[k] = row[k]
    if 'learnChances' in row: d['learnChances'] = row['learnChances']
    return d


def item_file(i, row, target):
    d = collections.OrderedDict(id=i, name=row['name'])
    for k in ITEM_KEYS[2:-2]: d[k] = row[k]
    if target is not None: d['evolution_target'] = target
    for f in glob.glob(os.path.join(ITEM_DIR, f'{i}-*.json')):         # what the item does is authored in the file, not in the executable: kept
        e = json.load(open(f)).get('effect')
        if e: d['effect'] = e
    return d


def from_doc(doc):
    """{path: file dict} of every file, from a balance document (balance.decode)."""
    N = S.names('techs'); out = {}
    for i in range(NUM_TECHS):
        name = N.get(i, f'Technique {i}')
        out[os.path.join(TECH_DIR, f'{i}-{slug(name)}.json')] = tech_file(i, doc['techniques'][str(i)], name)
    for i in range(NUM_ITEMS):
        row = doc['items'][str(i)]
        t = doc['evolutionItems'].get(str(i)) if EVO_ITEM_FIRST <= i <= EVO_ITEM_LAST else None
        out[os.path.join(ITEM_DIR, f'{i}-{slug(row["name"])}.json')] = item_file(i, row, t)
    for f, k in TABLES.items():
        if k == 'doors': v = {k: [[dict(zip(('model', 'x', 'y', 'z', 'rotation'), d)) for d in g] for g in doc[k]]}
        else: v = {k: doc[k]}
        out[os.path.join(TABLE_DIR, f'{f}.json')] = v
    import balance as B
    for f, keys in GROUPED.items():
        if any(k in B.RULE_KEYS for k in keys): continue          # rules: authored here, the C starts empty (docs/mods/data-sources.md)
        out[os.path.join(TABLE_DIR, f'{f}.json')] = collections.OrderedDict((k, doc[k]) for k in keys)
    for k, copies in COPIES.items():
        if any(doc[c] != doc[k] for c in copies): raise SystemExit(f'{k}: its copies {copies} differ: give them their own key')
    maps = spot_maps(doc)
    if any(doc[f'trainingSpots{m}'] != doc[f'trainingSpots{m}b'] for m in maps) or doc['trainingScreens'] != doc['trainingScreensb']:
        raise SystemExit('the training spots of TRN and TRN2 differ: give TRN2 its own key')
    out[os.path.join(TABLE_DIR, 'training-spots.json')] = collections.OrderedDict(
        spotScreens=[r['map'] for r in doc['trainingScreens']],
        trainingSpots=collections.OrderedDict((m, doc[f'trainingSpots{m}']) for m in maps))
    for i in range(NUM_SCREENS):
        e = doc['screens'][str(i)]
        out[os.path.join(SCREEN_DIR, f'{i}-{slug(e["file"]) or "none"}.json')] = screen_file(i, e)
    return out


def screen_file(i, e):
    """A MAP_ENTRIES row (map.h MapEntry) as a screen file: flags split (sound bank 0x1F, 0x20, one CLUT 0x40, placed
    Digimon read 0x80); the 10 name bytes only when what follows the name's NUL is not zeros."""
    fl = e['flags']
    d = collections.OrderedDict(id=i, file=e['file'], tims8=e['tims8'], tims4=e['tims4'], sound_bank=fl & 0x1F,
                                day_night=not fl & 0x40, reads_digimon=bool(fl & 0x80))
    if fl & 0x20: d['flag20'] = True
    d.update(doors=e['doors'], toilet=e['toilet'], caption=e['caption'])
    if bytes(e['fileBytes']) != e['file'].encode('latin-1').ljust(10, b'\0'): d['fileBytes'] = e['fileBytes']
    return d


# ------------------------------------------------------------------------------------------------ files -> document
def load_dir(d, n, what):
    files = sorted(glob.glob(os.path.join(d, '*.json')))
    if not files: return None
    rows = {}
    for p in files:
        x = json.load(open(p), object_pairs_hook=collections.OrderedDict); x['_path'] = p
        i = x.get('id')
        if not isinstance(i, int) or not 0 <= i < n: raise SystemExit(f'{p}: id must be 0..{n - 1}')
        if i in rows: raise SystemExit(f'{p}: id {i} is also {rows[i]["_path"]}')
        if not os.path.basename(p).startswith(f'{i}-'): raise SystemExit(f'{p}: the file name starts with its id ({i}-...)')
        rows[i] = x
    return rows


def load_techniques(): return load_dir(TECH_DIR, NUM_TECHS, 'techniques')
def load_screens(): return {i: x for i, x in (load_dir(SCREEN_DIR, NUM_ALL_SCREENS, 'screens') or {}).items() if i < NUM_SCREENS} or None
def load_items(): return load_dir(ITEM_DIR, NUM_ITEMS, 'items')


def load_tables():
    out = {}
    for f in list(TABLES) + list(GROUPED):
        p = os.path.join(TABLE_DIR, f'{f}.json')
        if os.path.exists(p): out.update({k: v for k, v in json.load(open(p)).items() if not k.startswith('_')})
    if not os.path.exists(os.path.join(TABLE_DIR, 'curling.json')):      # no file: no curling rules, no weights, no rings, no points (the C holds the originals, the build empties them)
        out.update(curlingRules={}, curlingWeights=[0] * 4, curlingStartTypes=[0] * 10, curlingRingPoints=[0] * 4,
                   curlingRings=[{'dx': 0, 'dz': 0, 'radius': 0} for _ in range(4)], curlingObstacleX=[0] * 3)
    p = os.path.join(TABLE_DIR, 'training-spots.json')
    if os.path.exists(p):
        d = json.load(open(p)); out['trainingSpots'] = d['trainingSpots']; out['spotScreens'] = d['spotScreens']
    return out


EMPTY_TECH = {'special': 0, 'power': 0, 'mpCost': 0, 'distance': 0, 'range': 0, 'accuracy': 0, 'status': 0,
              'statusChance': 0, 'iframes': 0, 'unk3': 0, 'unk4': 0, 'unk5': 0}
EMPTY_ITEM = {'name': '', 'value': 0, 'meritValue': 0, 'sortingValue': 0, 'itemColor': 0, 'droppable': 0, 'unk': 0}


def doc():
    """The part of a balance document the content folders give (balance.layered puts it over the disc's values). A domain
    whose folder has files starts from zero: an id without a file gets an empty row."""
    out = {}
    T = load_techniques()
    if T:
        out['techniques'] = {}
        for i in range(NUM_TECHS):
            if i not in T:
                r = dict(EMPTY_TECH)
                if i < NUM_LEARN: r['learnChances'] = [0, 0, 0]
                out['techniques'][str(i)] = r; continue
            x = T[i]
            bad = [k for k in x if not k.startswith('_') and k not in TECH_KEYS]
            if bad: raise SystemExit(f'{x["_path"]}: unknown key {", ".join(bad)} (keys: {", ".join(TECH_KEYS)})')
            el = x['element']
            r = {'special': ELEMENTS.index(el) if isinstance(el, str) else el}
            for k in TECH_KEYS[3:-1]: r[k] = x[k]
            if i < NUM_LEARN:
                lc = x.get('learnChances')
                if not (isinstance(lc, list) and len(lc) == 3): raise SystemExit(f'{x["_path"]}: learnChances: [main, second, third] (ids 0..{NUM_LEARN - 1})')
                r['learnChances'] = list(lc)
            elif 'learnChances' in x:
                raise SystemExit(f'{x["_path"]}: learnChances: only techniques 0..{NUM_LEARN - 1} are learned in battle')
            out['techniques'][str(i)] = r
    I = load_items()
    if I:
        out['items'] = {}; out['evolutionItems'] = {}; out['itemEffects'] = {}
        for i in range(NUM_ITEMS):
            evo = EVO_ITEM_FIRST <= i <= EVO_ITEM_LAST
            if i not in I:
                out['items'][str(i)] = dict(EMPTY_ITEM)
                if evo: out['evolutionItems'][str(i)] = 0
                continue
            x = I[i]
            bad = [k for k in x if not k.startswith('_') and k not in ITEM_KEYS]
            if bad: raise SystemExit(f'{x["_path"]}: unknown key {", ".join(bad)} (keys: {", ".join(ITEM_KEYS)})')
            if len(x['name'].encode('latin-1', 'replace')) > 19: raise SystemExit(f'{x["_path"]}: name: at most 19 characters')
            out['items'][str(i)] = {k: x[k] for k in ['name'] + ITEM_KEYS[2:-2]}
            if evo != ('evolution_target' in x):
                raise SystemExit(f'{x["_path"]}: evolution_target: {"required" if evo else "only"} for items {EVO_ITEM_FIRST}..{EVO_ITEM_LAST}')
            if evo: out['evolutionItems'][str(i)] = x['evolution_target']
            if x.get('effect'): out.setdefault('itemEffects', {})[str(i)] = x['effect']
    out.update(load_tables())
    if 'doors' in out:
        out['doors'] = [[[d['model'], d['x'], d['y'], d['z'], d['rotation']] for d in g] for g in out['doors']]
    for k, copies in COPIES.items():
        if k in out: out.update({c: out[k] for c in copies})
    ts = out.pop('trainingSpots', None)                  # by screen: written to TRN and TRN2 (same spots)
    scr = out.pop('spotScreens', None)
    if ts:
        if scr is None or [str(m) for m in scr[:len(ts)]] != list(ts) or any(m != -1 for m in scr[len(ts):]):
            raise SystemExit('content/tables/training-spots.json: "spotScreens" lists the screen of each spot list, in the order of '
                             '"trainingSpots", then -1 (the overlays point at their spot lists by position; at most 7 screens)')
        out['trainingScreens'] = out['trainingScreensb'] = [{'map': m} for m in scr]
        for m, spots in ts.items(): out[f'trainingSpots{m}'] = out[f'trainingSpots{m}b'] = spots
    SC = load_screens()
    if SC:
        out['screens'] = {}
        for i in range(NUM_SCREENS):
            x = SC.get(i)
            if x is None: out['screens'][str(i)] = dict(EMPTY_SCREEN, fileBytes=[0] * 10); continue
            bad = [k for k in x if not k.startswith('_') and k not in SCREEN_KEYS]
            if bad: raise SystemExit(f'{x["_path"]}: unknown key {", ".join(bad)} (keys: {", ".join(SCREEN_KEYS)})')
            fl = (x['sound_bank'] & 0x1F) | (0x20 if x.get('flag20') else 0) | (0 if x['day_night'] else 0x40) | \
                 (0x80 if x['reads_digimon'] else 0)
            out['screens'][str(i)] = {'file': x['file'], 'fileBytes': x.get('fileBytes'), 'tims8': x['tims8'],
                                      'tims4': x['tims4'], 'flags': fl, 'doors': x['doors'], 'toilet': x['toilet'],
                                      'caption': x['caption']}
    return out


# ------------------------------------------------------------------------------------------------ lint
def lint():
    """Errors: what still names a technique or an item that has no file (the game does not have it)."""
    errs = []
    T = load_techniques(); I = load_items(); tab = load_tables()
    gt = {i for i in range(NUM_TECHS) if T is not None and i not in T}
    gi = {i for i in range(NUM_ITEMS) if I is not None and i not in I}
    tn = S.names('techs')
    def item_id(name, where):
        try: return S.id_of('items', name, where)
        except SystemExit: return None
    for t, s in S.load_content().items():
        if s.get('techniques') is None: moves = []              # no techniques (an NPC-only species: sixteen 0s)
        else:
            try: moves = S.techniques_from_json(s['techniques'], s['_path'])
            except SystemExit: continue
        for j, m in enumerate(moves):
            if m in gt: errs.append(f'{s["_path"]}: techniques[{j}] {tn.get(m, m)} has no file in content/techniques: '
                                    f'replace it (the list position is the animation slot it plays)')
        ngt = s.get('new_game_technique')
        if ngt is not None:
            try:
                if S.id_of('techs', ngt, s['_path']) in gt: errs.append(f'{s["_path"]}: new_game_technique {ngt} has no file')
            except SystemExit: pass
        d = s.get('drop') or {}
        if d.get('item') is not None and d.get('percent') and item_id(d['item'], s['_path']) in gi:
            errs.append(f'{s["_path"]}: drop.item {d["item"]} has no file in content/items')
        ff = (s.get('partner') or {}).get('favorite_food')
        if ff is not None and item_id(ff, s['_path']) in gi:
            errs.append(f'{s["_path"]}: partner.favorite_food {ff} has no file in content/items')
    errs += slot_species_errors()
    # content/maps: every slot resolves (a species that exists, a stat its species' wild can give)
    maps = load_maps() or {}
    if maps:
        c = _map_ctx()
        for name, x in maps.items():
            for i, o in enumerate(x.get('digimon', [])):
                try:
                    if o.get('slot', i) != i: raise SystemExit(f'slot {o.get("slot")} at position {i}: slots are positional')
                    t = c['ids'].get(o.get('species')) if isinstance(o.get('species'), str) else None
                    if isinstance(o.get('species'), str) and t is not None and t < S.NUM_ORIGINAL and t not in c['sp']:
                        raise SystemExit(f'species {o["species"]} has no file (it does not exist): take it out of the map')
                    json_to_slot(i, o, c['wild'], c['ids'], f'{x["_path"]}: slot {i}')
                except SystemExit as e:
                    errs.append(f'{x["_path"]}: slot {i}: {e}' if not str(e).startswith(x['_path']) else str(e))
    for el, lst in (tab.get('brainTraining') or {}).get('techniques', {}).items():
        for m in lst:
            if m in gt: errs.append(f'content/tables/brain-training.json: brainTraining.techniques.{el} has {tn.get(m, m)}, '
                                    f'which has no file: replace it (8 per element, fixed)')
    return errs


# ------------------------------------------------------------------------------------------------ commands
def source_doc():
    """The values the files start from: the compiled executable of the mod when there is one (what the game holds now,
    the C patches included: the caps' stat limits...), else the disc's."""
    import balance as B
    exe = os.path.join(ROOT, 'build', 'decomp-int', 'build', 'us', 'psx', 'gcc')
    return B.decode(B.Exe(exe)) if os.path.exists(os.path.join(exe, 'SLUS_010.32')) else B.original_doc()


def cmd_extract(a):
    files = from_doc(source_doc())
    changed = [p for p, d in files.items() if os.path.exists(p) and json.load(open(p)) != json.loads(json.dumps(d))]
    if changed and not a.force:
        sys.exit(f'{len(changed)} file(s) differ from the disc (edits?): {", ".join(os.path.relpath(p, ROOT) for p in changed[:5])}; '
                 f'--force overwrites them')
    for p, d in files.items(): write(p, d)
    print(f'{len(files)} files: {NUM_TECHS} techniques, {NUM_ITEMS} items, {NUM_SCREENS} screens, '
          f'{len(TABLES) + len(GROUPED)} table files')


VIEW_SCREEN = re.compile(r'^(\w+)\s*=\s*screen\(([^)]*)\)', re.M)
VIEW_NPC = re.compile(r'\b(\w+)\.npc\(\s*Species\.(\w+)\s*,\s*slot\s*=\s*(\d+)')
VIEW_SPAWN = re.compile(r'\bspawn\(\s*Species\.(\w+)\s*,\s*slot\s*=\s*(\d+)')


def slot_species_errors():
    """A story that names, for a map slot, a species other than content/maps' (MAPHEAD's spawn(Species.X, slot=k) in
    maphead/hooks.py, a view's npc(Species.X, slot=k)): the engine's scriptSetDigimon then shows nobody, silently
    (overworld.c). -> [error]"""
    maps = load_maps()
    if maps is None: return []
    from dws import backend as BE, basebuild as BB
    from dws.py import naming as N
    c = _map_ctx(); scr = {v: k for k, v in N.screen_members().items()}
    def slot_type(screen, k):
        x = maps.get(BE.MAP_FILES.get(screen) or '')
        if x is None or k >= len(x['digimon']): return None
        sp = x['digimon'][k].get('species')
        return 255 if sp is None else (c['ids'].get(sp) if isinstance(sp, str) else sp)
    def check(screen, k, t, where):
        if screen not in BE.MAP_FILES: return []        # a MAPHEAD section of a screen the game has no map for (247..)
        have = slot_type(screen, k)
        if t != have:
            return [f'{where}: screen {screen} slot {k} is {c["sp"].get(t, {}).get("name", t)} here, but content/maps/'
                    f'{BE.MAP_FILES.get(screen)}.json has {"nothing" if have is None else c["sp"].get(have, {}).get("name", have)} '
                    f'(the game shows nobody)']
        return []
    errs = []; ids = c['ids']
    # MAPHEAD's setups (the story's source: maphead/hooks.py, `@screen(Screen.x).on_load` then spawn(Species.Y, slot=k))
    hooks = os.path.join(BB.BASE, 'maphead', 'hooks.py'); cur = []
    for i, line in enumerate(open(hooks, encoding='utf-8') if os.path.exists(hooks) else [], 1):
        if line.startswith('@'):
            m = re.match(r'@screen\(([^)]*)\)\.on_load', line)
            cur = [scr[x.strip().split('.')[-1]] for x in m.group(1).split(',') if x.strip().startswith('Screen.')] if m else []
        for m in VIEW_SPAWN.finditer(line.split('#', 1)[0]):
            for screen in cur: errs += check(screen, int(m.group(2)), ids.get(m.group(1)), f'{os.path.relpath(hooks, ROOT)}:{i}')
    for p in sorted(glob.glob(os.path.join(BB.BASE, 'zones', '*', '*', 'script.py'))):
        text = open(p, encoding='utf-8').read()
        screens = {v: [scr[x.strip().split('.')[-1]] for x in args.split(',') if x.strip().startswith('Screen.')]
                   for v, args in VIEW_SCREEN.findall(text)}
        for m in VIEW_NPC.finditer(text):
            line = text.count('\n', 0, m.start()) + 1
            for screen in screens.get(m.group(1), []):
                errs += check(screen, int(m.group(3)), ids.get(m.group(2)), f'{os.path.relpath(p, ROOT)}:{line}')
    return errs


def cmd_extract_maps(a):
    files, given = extract_maps()
    for p, d in files.items(): write(p, d)
    sp = S.load_content()
    for t, w in given.items():
        x = dict(sp[t]); x['wild'] = w; S.write_file(x['_path'], x)
    _MAP_CTX.clear()
    print(f'{len(files)} map files; "wild" set on {len(given)} species of the disc (their most common placed stats)')


def cmd_verify_maps(a):
    bad = []
    for name, rel in map_files().items():
        data = open(os.path.join(ROOT, 'extracted', rel), 'rb').read()
        if build_map(name, data) != data: bad.append(name)
    print(f'{len(map_files())} .MAP files rebuilt from the disc\'s assets + content/maps: {len(bad)} differ {bad[:8]}')
    if bad: sys.exit(1)


def cmd_lint(a):
    d = doc(); errs = lint()
    for e in errs: print('error:', e)
    n = sum(len(d.get(k, {})) for k in ('techniques', 'items'))
    print(f'content: {len(d.get("techniques", {}))} techniques, {len(d.get("items", {}))} items, '
          f'{len([k for k in TABLES.values() if k in d])} tables: {len(errs)} errors')
    if errs: sys.exit(1)


def cmd_fmt(a):
    bad = []
    for d in (TECH_DIR, ITEM_DIR, TABLE_DIR, SCREEN_DIR, MAPS_DIR):
        for p in sorted(glob.glob(os.path.join(d, '*.json'))):
            x = json.load(open(p), object_pairs_hook=collections.OrderedDict); want = dumps(x) + '\n'
            if open(p).read() != want:
                bad.append(p)
                if not a.check: open(p, 'w').write(want)
    print(f'{len(bad)} file(s) {"to rewrite" if a.check else "rewritten"}')
    if a.check and bad: sys.exit(1)


def cmd_diff(a):
    """What the files change, table by table, against the values they were made from (source_doc: the compiled mod
    executable, else the disc), compared as the bytes balance.py writes."""
    import balance as B
    exe_dir = os.path.join(ROOT, 'build', 'decomp-int', 'build', 'us', 'psx', 'gcc')
    exe = B.Exe(exe_dir if os.path.exists(os.path.join(exe_dir, 'SLUS_010.32')) else None)
    base = B.decode(exe); mine = B.merge(json.loads(json.dumps(base)), doc())
    a_enc, b_enc = B.encode(base, exe), B.encode(mine, exe); n = 0
    empty = []
    for t in a_enc:
        if a_enc[t] != b_enc[t]:
            if t in B.RULE_KEYS and not any(v != 0xFF for v in a_enc[t]): empty.append(t); continue    # the C starts empty
            print(f'{t}: {sum(x != y for x, y in zip(a_enc[t], b_enc[t]))} byte(s) differ'); n += 1
    if empty: print(f'rules the C starts empty and the build fills from the files: {", ".join(empty)}')
    print(f'{n} table(s) differ from {os.path.relpath(exe.folder, ROOT)}')


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest='cmd', required=True)
    p = sub.add_parser('extract'); p.add_argument('--force', action='store_true')
    sub.add_parser('lint'); sub.add_parser('diff'); sub.add_parser('extract-maps'); sub.add_parser('verify-maps')
    p = sub.add_parser('fmt'); p.add_argument('--check', action='store_true')
    a = ap.parse_args()
    {'extract': cmd_extract, 'lint': cmd_lint, 'fmt': cmd_fmt, 'diff': cmd_diff, 'extract-maps': cmd_extract_maps,
     'verify-maps': cmd_verify_maps}[a.cmd](a)



# ------------------------------------------------------------------------------------------------ maps (placed Digimon)
# content/maps/<NAME>.json: the Digimon placed in one .MAP (docs/mods/data-sources.md "Maps"), in slot order. The .MAP's
# assets (ground, collision, backgrounds, sprites, warps) stay the disc's; its Digimon list is written from the file (a
# .MAP without a file has none). A stat of a slot is its species' `wild` (nothing written), a delta on it ("+200", "-100")
# or a fixed number. What equals the usual value is left out (y 0, rotation x/z 0, script id 5 + slot, current HP/MP =
# HP/MP, unk2 0, unk1 1, flee y 0). A slot whose species is null is a placeholder (type 255: the engine copies it inertly).
MAPS_DIR = os.path.join(CONTENT, 'maps')
STAT_KEYS = ['hp', 'mp', 'off', 'def', 'speed', 'brain', 'bits']
NEVER_READ = {'YAKA22'}        # digimon_count 63 with no parseable list; the game never loads it (MAP_ENTRIES flags 0x44)


def map_files():
    """{NAME: path relative to extracted/} of every .MAP of the disc."""
    base = os.path.join(ROOT, 'extracted')
    return {os.path.basename(p)[:-4]: os.path.relpath(p, base) for p in sorted(glob.glob(os.path.join(base, 'MAP', '*', '*.MAP')))}


def _species_names():
    from dws.py import naming as N
    return N.enum_members('species')


def slot_to_json(i, d, wild, names):
    t = d['type']
    o = collections.OrderedDict(slot=i, species=None if t in (-1, 255) else names.get(t, t))
    o['at'] = [d['posX'], d['posZ']]
    if d['posY']: o['y'] = d['posY']
    o['facing'] = d['rotY']
    if d['rotX'] or d['rotZ']: o['rotation'] = [d['rotX'], d['rotY'], d['rotZ']]
    o['follow'] = d['followMode']; o['range'] = d['trackingRange']
    if d['scriptId'] != 5 + i: o['script'] = d['scriptId']
    if d['unk2']: o['unk2'] = d['unk2']
    o['charge'] = d['chargeMode']
    if d['unk1'] != 1: o['unk1'] = d['unk1']
    w = wild if o['species'] is not None else {}
    for k in STAT_KEYS:
        v = d[k]
        if k not in w: o[k] = v
        elif v != w[k]: o[k] = f'{v - w[k]:+d}'
    if d['currentHP'] != d['hp']: o['currentHP'] = d['currentHP']
    if d['currentMP'] != d['mp']: o['currentMP'] = d['currentMP']
    o['moves'] = [d[f'move{j}'] for j in range(4)]; o['prios'] = [d[f'prio{j}'] for j in range(4)]
    o['flee'] = [d['fleeX'], d['fleeZ']]
    if d['fleeY']: o['fleeY'] = d['fleeY']
    o['ai'] = list(d['aiSections']); o['path'] = [list(p) for p in d['waypoints']]
    return o


def json_to_slot(i, o, wild, ids, where):
    """The .MAP entry of a slot of a content/maps file."""
    sp = o.get('species')
    if sp is None: t = 255; w = {}
    else:
        t = ids.get(sp) if isinstance(sp, str) else sp
        if t is None: raise SystemExit(f'{where}: species {sp!r}: no such species (its file was deleted, or a typo)')
        w = wild(t)
    d = {'type': t, 'posX': o['at'][0], 'posY': o.get('y', 0), 'posZ': o['at'][1]}
    rot = o.get('rotation', [0, o['facing'], 0]); d['rotX'], d['rotY'], d['rotZ'] = rot
    d.update(followMode=o['follow'], trackingRange=o['range'], scriptId=o.get('script', 5 + i), unk2=o.get('unk2', 0),
             chargeMode=o['charge'], unk1=o.get('unk1', 1))
    for k in STAT_KEYS:
        v = o.get(k)
        if v is None:
            if sp is None: v = 0                        # a placeholder (no species): inert, its stats unused
            elif k not in w: raise SystemExit(f'{where}: {k}: its species has no "wild" {k}: give a number')
            else: v = w[k]
        elif isinstance(v, str):
            if k not in w: raise SystemExit(f'{where}: {k}: {v} is a delta, but its species has no "wild" {k}')
            v = w[k] + int(v)
        d[k] = v
    d['currentHP'] = o.get('currentHP', d['hp']); d['currentMP'] = o.get('currentMP', d['mp'])
    for j in range(4): d[f'move{j}'] = o['moves'][j]; d[f'prio{j}'] = o['prios'][j]
    d['fleeX'], d['fleeZ'] = o['flee']; d['fleeY'] = o.get('fleeY', 0)
    d['aiSections'] = list(o['ai']); d['waypoints'] = [list(p) for p in o['path']]
    return d


def load_maps():
    """{NAME: file dict} of content/maps (None when the folder has no file: the disc's lists)."""
    files = sorted(glob.glob(os.path.join(MAPS_DIR, '*.json')))
    if not files: return None
    return {os.path.basename(p)[:-5]: dict(json.load(open(p), object_pairs_hook=collections.OrderedDict), _path=p) for p in files}


_MAP_CTX = {}


def _map_ctx():
    if not _MAP_CTX:
        sp = S.load_content(); names = _species_names()
        _MAP_CTX.update(sp=sp, ids={v: k for k, v in names.items()},
                        wild=lambda t: {k: v for k, v in (sp.get(t, {}).get('wild') or {}).items() if k in STAT_KEYS})
    return _MAP_CTX


def build_map(name, data, maps=None):
    """The .MAP NAME (its disc bytes `data`) with its Digimon list from content/maps (none without a file). -> bytes"""
    import dwmap
    maps = load_maps() if maps is None else maps
    if maps is None or name in NEVER_READ: return data
    m = dwmap.MapFile(data); c = _map_ctx()
    x = maps.get(name)
    slots = x['digimon'] if x else []
    for i, o in enumerate(slots):
        if o.get('slot', i) != i: raise SystemExit(f'{x["_path"]}: slot {o.get("slot")} at position {i}: slots are positional '
                                                   f'(a deleted middle slot keeps its place with "species": null)')
    m.digimon = [json_to_slot(i, o, c['wild'], c['ids'], f'{x["_path"]}: slot {i}') for i, o in enumerate(slots)]
    m.digimon_count = len(m.digimon)
    return m.build()


def built_map_path(rel):
    """A .MAP as the game gets it before the story's own edits (content/maps over the disc's): the path the story
    compiler reads (tools/dws/backend.py), written under build/content-maps/ when it differs from the disc's."""
    src = os.path.join(ROOT, 'extracted', rel)
    data = open(src, 'rb').read(); new = build_map(os.path.basename(rel)[:-4], data)
    if new == data: return src
    dst = os.path.join(ROOT, 'build', 'content-maps', rel)
    os.makedirs(os.path.dirname(dst), exist_ok=True)
    if not os.path.exists(dst) or open(dst, 'rb').read() != new: open(dst, 'wb').write(new)
    return dst


def extract_maps():
    """content/maps from the disc, and the `wild` of every species of the disc placed on a map that has none (its most
    common placed stats: the fewest deltas). -> (map files, species files given a wild)"""
    import dwmap
    names = _species_names(); sp = S.load_content()
    lists = {}
    common = collections.defaultdict(collections.Counter)
    for name, rel in map_files().items():
        if name in NEVER_READ: continue
        m = dwmap.MapFile(open(os.path.join(ROOT, 'extracted', rel), 'rb').read())
        if not m.digimon: continue
        lists[name] = (rel, m.digimon)
        for d in m.digimon:
            if d['type'] not in (-1, 255): common[d['type']][tuple(d[k] for k in STAT_KEYS)] += 1
    given = {}
    for t, cnt in common.items():                     # a species of the disc: its most common placed stats (an import
        if t in sp and (t < S.NUM_ORIGINAL or 'wild' not in sp[t]):   # keeps its own role-made wild)
            w = dict(zip(STAT_KEYS, cnt.most_common(1)[0][0]))
            if (sp[t].get('wild') or {}) != w: given[t] = w
    wild = lambda t: given.get(t) or {k: v for k, v in (sp.get(t, {}).get('wild') or {}).items() if k in STAT_KEYS}
    out = {}
    for name, (rel, digis) in lists.items():
        out[os.path.join(MAPS_DIR, f'{name}.json')] = collections.OrderedDict(
            file=rel.replace(os.sep, '/'), digimon=[slot_to_json(i, d, wild(d['type']), names) for i, d in enumerate(digis)])
    return out, given


if __name__ == '__main__':
    main()
