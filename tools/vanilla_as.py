#!/usr/bin/env python3
"""The original-game species each new partner species turns into with OPTIONS' NEW DIGIMON off (docs/mods/options.md).

For every partner species without "vanilla": true, `vanilla_as` names a vanilla species of its level (an Ultimate for a
Mega, the original has none): from its nearest vanilla ancestor (its "from" parents, then theirs), the vanilla species of
that level reached down the vanilla rows, one that shares a specialty first; without a vanilla ancestor, a vanilla
species of the level that shares its first specialty. A species whose file already has `vanilla_as` keeps it.

  tools/vanilla_as.py           print the choices
  tools/vanilla_as.py --write   write them into content/species (only the files without one)
"""
import collections, os, re, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import species

LEVELS = ['fresh', 'in-training', 'rookie', 'champion', 'ultimate', 'mega']


def choose(allsp):
    part = {t: s for t, s in allsp.items() if 'partner' in s and s['level'] in LEVELS}
    van = {t for t, s in part.items() if s.get('vanilla')}
    lv = {t: LEVELS.index(s['level']) for t, s in part.items()}
    parents = collections.defaultdict(set)
    children = collections.defaultdict(list)
    for t, s in part.items():
        ev = s.get('evolution') or {}
        for p in ev.get('from') or []:
            if p in part: parents[t].add(p)
        for c in ev.get('to') or []:
            if c in part:
                parents[c].add(t)
                if t in van and c in van: children[t].append(c)
    spec = {t: [x for x in (s.get('specialties') or []) if x] for t, s in part.items()}

    def down(a, level, t):
        seen, todo, found = {a}, [a], []
        while todo:
            x = todo.pop(0)
            for c in children[x]:
                if c in seen or lv[c] > level: continue
                seen.add(c)
                (found if lv[c] == level else todo).append(c)
        shared = [c for c in found if set(spec[c]) & set(spec[t])]
        return (shared or found or [None])[0]

    out = {}
    for t in sorted(part):
        if t in van: continue
        if part[t].get('vanilla_as'):
            out[t] = part[t]['vanilla_as']; continue
        level = min(lv[t], LEVELS.index('ultimate'))
        pick, seen, todo = None, {t}, sorted(parents[t])
        while todo and pick is None:
            nxt = []
            for a in todo:
                if a in seen: continue
                seen.add(a)
                if a in van and lv[a] == level: pick = a; break
                if a in van and lv[a] < level:
                    pick = down(a, level, t)
                    if pick: break
                nxt += sorted(parents[a])
            todo = nxt
        if pick is None:
            same = sorted(v for v in van if lv[v] == level)
            first = spec[t][:1]
            pick = next((v for v in same if set(spec[v]) & set(first)), same[0] if same else None)
        out[t] = pick
    return out


def main():
    allsp = species.load_content()
    out = choose(allsp)
    for t, v in out.items():
        print(f'{t:4} {allsp[t]["name"]:20} {allsp[t]["level"]:11} -> {v:3} {allsp[v]["name"]}')
    if '--write' in sys.argv:
        n = 0
        for path in species.content_files():
            text = open(path).read()
            m = re.search(r'"id": (\d+),', text)
            t = int(m.group(1)) if m else -1
            if t not in out or '"vanilla_as"' in text: continue
            text, k = re.subn(r'(\n  "level": "[a-z-]+",\n)', r'\1  "vanilla_as": %d,\n' % out[t], text, count=1)
            if k: open(path, 'w').write(text); n += 1
        print(f'{n} files written', file=sys.stderr)


if __name__ == '__main__':
    main()
