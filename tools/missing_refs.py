#!/usr/bin/env python3
"""What still uses a species, an item or a technique that has no file (docs/mods/data-sources.md).

The build starts from zero: an id of the disc without a file in content/species, content/items or content/techniques is
something the game does not have (its rows are empty). The evolution lists drop it by themselves; what places or names it
has to go too, by hand, and the build stops while anything is left:
  - the .MAP files: a wild or NPC Digimon of such a species (dwmap.py edit --remove-digimon / --set-digimon);
  - the compiled story (story/base, story/core, the enabled mods): every `Species.X`, `Item.X`, `Tech.X` that spawns,
    recruits, gives, sells, teaches or fights it. A question (`recruited`, `has`, `knows`, `take`, `==`) is only noted:
    it answers "no" from then on.
An imported species may still borrow such a species' model, texture or effects (effects_like, model.from, texture.from):
those are disc assets by id, not the species.

  tools/missing_refs.py [--content DIR] [--mods all|none|a,b] [-v]     exit 1 when a use is left
"""
import argparse, glob, os, re, sys
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, 'tools'))
import species as S

REF = re.compile(r'\b(Species|Item|Tech)\.([A-Za-z_][A-Za-z0-9_]*)')
# a question about it (forever "no" once it cannot be had: harmless) rather than a use (spawn, give, learn, fight...)
CHECK_ONLY = re.compile(r'\b(?:recruited|has|knows|take)\(\s*(?:Species|Item|Tech)\.[A-Za-z_][A-Za-z0-9_]*[^)]*\)'
                        r'|[!=]=\s*(?:Species|Item|Tech)\.[A-Za-z_][A-Za-z0-9_]*')
ENUM = {'Species': 'species', 'Item': 'item', 'Tech': 'tech'}


def map_refs(removed, maps_dir=None):
    """The placed Digimon of content/maps (the .MAP lists the build writes) of a species without a file."""
    import content as C
    maps = C.load_maps() or {}
    from dws.py import naming as N
    ids = {v: k for k, v in N.enum_members('species').items()}
    out = []
    for name, x in sorted(maps.items()):
        for i, o in enumerate(x.get('digimon', [])):
            sp = o.get('species'); t = ids.get(sp) if isinstance(sp, str) else sp
            if t in removed: out.append((t, f'{os.path.relpath(x["_path"], ROOT)}: slot {i} ({sp})', False))
    return out


# the C tables of content/tables that name a species or an item: (file, key, kind, ids that mean "nothing")
TABLE_REFS = [('shops', 'recyclableItems', 'Item', ()), ('shops', 'mojyamonGives', 'Item', (0,)),
              ('shops', 'mojyamonTakes', 'Item', (0,)), ('shops', 'shopkeepers', 'Species', (255,)),
              ('inventories', 'initialInventoryItems', 'Item', (255,)), ('inventories', 'defaultInventoryItems', 'Item', (255,)),
              ('partner-rules', 'babies', 'Species', ()), ('partner-rules', 'reincarnationBabies', 'Species', ()),
              ('cards', 'cards', 'Species', ())]


def table_refs(removed):
    """The same, for the lists of content/tables (the recycler, Mojyamon's trades, the shopkeepers, the starting inventories,
    the babies, the card shop): [(kind, id, where, False)]."""
    import json
    out = []
    for f, key, kind, nothing in TABLE_REFS:
        p = os.path.join(ROOT, 'content', 'tables', f + '.json')
        if not os.path.exists(p): continue
        for i, v in enumerate(json.load(open(p)).get(key, [])):
            v = v['species'] if isinstance(v, dict) else v
            if v in removed.get(kind, ()) and v not in nothing:
                out.append((kind, v, f'content/tables/{f}.json: {key}[{i}]', False))
    return out


def story_sources(mods):
    """The story files the build compiles: story/base (a deleted script is simply not there), story/core, the enabled
    mods' sources."""
    from dws import basebuild as BB
    names = sorted(d for d in os.listdir(BB.MODS) if os.path.isdir(os.path.join(BB.MODS, d)))
    if mods in (None, 'all'): chosen = [m for m in names if BB.enabled(os.path.join(BB.MODS, m))]
    elif mods == 'none': chosen = []
    else: chosen = [m for m in mods.split(',') if m]
    files = sorted(glob.glob(os.path.join(BB.BASE, 'zones', '*', '*', 'script.py')))
    files += sorted(glob.glob(os.path.join(BB.BASE, 'maphead', '*.py')))
    files += sorted(glob.glob(os.path.join(BB.CORE, '*.dws')))
    for m in chosen:
        for ext in ('py', 'dws'):
            files += sorted(glob.glob(os.path.join(BB.MODS, m, '**', f'*.{ext}'), recursive=True))
    return files


def story_refs(removed, mods=None):
    """removed: {'Species': ids, 'Item': ids, 'Tech': ids} -> [(kind, id, where, question?)]"""
    from dws.py import naming as N
    by_name = {k: {v: i for i, v in N.enum_members(e).items()} for k, e in ENUM.items()}
    out = []
    for p in story_sources(mods):
        for i, line in enumerate(open(p, encoding='utf-8'), 1):
            code = line.split('#', 1)[0] if p.endswith('.py') else line.split('//', 1)[0]
            for m in REF.finditer(code):
                kind = m.group(1); t = by_name[kind].get(m.group(2))
                if t in removed.get(kind, ()):
                    check = any(c.start() <= m.start() < c.end() for c in CHECK_ONLY.finditer(code))
                    out.append((kind, t, f'{os.path.relpath(p, ROOT)}:{i}: {line.strip()[:100]}', check))
    return out


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--content', default=None, help='species folder (default content/species)')
    ap.add_argument('--mods', default=os.environ.get('STORY_MODS'), help='the story mods the build uses (default: all enabled)')
    ap.add_argument('-v', '--verbose', action='store_true', help='also list the questions (recruited, has, knows...)')
    a = ap.parse_args()
    import content as C
    from dws.py import naming as N
    sp = S.load_content(a.content); T = C.load_techniques() or {}; I = C.load_items() or {}
    names = {'Species': N.enum_members('species'), 'Item': N.enum_members('item'), 'Tech': N.enum_members('tech')}
    removed = {'Species': {t for t in range(S.NUM_ORIGINAL) if t not in sp} if any(t < S.NUM_ORIGINAL for t in sp) else set(),
               'Item': {i for i in range(C.NUM_ITEMS) if i not in I} if I else set(),
               'Tech': {i for i in range(C.NUM_TECHS) if i not in T} if T else set()}
    if not any(removed.values()):
        print('missing: nothing (every id has its file)'); return
    refs = [('Species', t, w, c) for t, w, c in map_refs(removed['Species'])] + table_refs(removed) + story_refs(removed, a.mods)
    print('without a file: ' + '; '.join(f'{k} ' + ', '.join(f'{i} {names[k].get(i, i)}' for i in sorted(v)) for k, v in removed.items() if v))
    checks = [r for r in refs if r[3]]; uses = [r for r in refs if not r[3]]
    if checks:
        print(f'note: {len(checks)} question(s) about one without a file (recruited, has, knows, take, ==) answer no '
              f'(-v lists them)')
        if a.verbose:
            for k, t, where, _ in checks: print(f'  {k} {names[k].get(t, t)} ({t}): {where}')
    if not uses:
        print('nothing in the maps or the story places, gives, spawns, teaches or fights them'); return
    for k, t, where, _ in uses: print(f'  {k} {names[k].get(t, t)} ({t}): {where}')
    sys.exit(f'{len(uses)} place(s) still use a species, item or technique that has no file: take them out too '
             f'(docs/mods/data-sources.md "Deleting")')


if __name__ == '__main__':
    main()
