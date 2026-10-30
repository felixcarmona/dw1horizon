#!/usr/bin/env python3
"""Animation slots each Digimon type can play as an NPC (a model loaded into the heap).

Usage:
  npcanims.py report [--dg DG.SCN|DIR] [--maphead MAPHEAD.SCN]   per type: kept/dropped slots and bytes
  npcanims.py gen OUT.c [--dg ...] [--maphead ...]                writes the keep table for the mod
                                                                   executable (src/main/npc_anim_keep.c)

--dg is a DG.SCN (disassembled here) or a folder of its scripts already as assembly, script_NNN.scn.txt: the
story build's (tools/build-full.sh gives $O/story/dis, the scripts of story/base compiled from the sources, so the
audit reads nothing of the disc's DG.SCN). With a folder, the screens that load each script come from --maphead
(rule: the first SET_SCRIPT in the section of a screen < 255, as tools/dws/bytecode/__main__.py writes them in a disassembly's header).

NPC models (loadMMD class 0, malloc3) keep only these animation slots; the
others are dropped when the model loads (src/main/npc_anim_trim.c, memreclaim
branch). Partner and tamer models are never trimmed. A slot is kept:

- for every type: 0-4 (idle, alternative idle, walk, 3, run: map AI and the
  scripts' walk modes), 0x13 (battle "senile" status, any fighter), 0x1C-0x20
  (curling opponent kar.c, training partner trn_brain.c, and the gestures the
  scripts play on most NPCs), and 0x21 and up (battle: idle, hit, knocked
  down, reactions, techniques 0x2E+i) because every NPC can be fought
  (wild battles, scripted battles, tournament, VS);
- per type: every slot a script plays (PLAY_ANIMATION, ENTITY_WALK_TO* walk
  modes) on an actor that resolves to that type. A script's actor is an NPC
  scriptId; it is resolved through the screens that load the script (MAPHEAD
  SET_SCRIPT), the .MAP Digimon entries (type, scriptId) of those screens and
  the SET_DIGIMON (type, slot) overrides in MAPHEAD and in the script itself;
- for every type: any slot played on an actor that cannot be resolved (a
  screen with no extracted .MAP, an actor with no entry);
- type 0 (BOYS.MMD, the tamer's model) keeps everything.

A dropped slot points to a one-frame stub (the idle's first pose) instead of
0, so a scene that plays an animation this audit missed shows the NPC still
for a frame and goes on (no wait on an animation that never ends).
Scripts added by mods (DWS scripts) must rerun `gen` with their DG.SCN/MAPHEAD.SCN.
"""
import argparse, collections, functools, glob, os, re, struct, sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, 'tools'))
import dwmap; import membudget as mb; from dws import bytecode as bytecode

CACHE = os.path.join(ROOT, 'build/npcanims')
NUM_TYPES = 180
MAX_SLOTS = 64
ALWAYS = set(range(0, 5)) | {0x13} | set(range(0x1C, 0x21)) | set(range(0x21, MAX_SLOTS))
FULL = {0}      # types never trimmed: 0 is the tamer's model (BOYS), also used for other boys


def disassemble(path, name):
    out = os.path.join(CACHE, name)
    stamp = os.path.join(out, '.src')
    key = f'{os.path.abspath(path)} {os.path.getmtime(path)}'
    if not (os.path.exists(stamp) and open(stamp).read() == key):
        os.makedirs(out, exist_ok=True)
        for f in glob.glob(os.path.join(out, '*')): os.remove(f)
        r = bytecode.dis(path, out)
        if r.returncode: sys.exit(f'bytecode dis {path}: {r.stderr.strip()}')
        open(stamp, 'w').write(key)
    return out


def mmd_slots(d):
    """(table offset, slot offsets (0 = none), {offset: size}) of an MMD."""
    ta = struct.unpack_from('<I', d, 4)[0]
    offs, first, i = [], None, 0
    while first is None or 4 * i < first:
        o = struct.unpack_from('<I', d, ta + 4 * i)[0]
        if o and (first is None or o < first): first = o
        offs.append(o); i += 1
    offs = offs[:first // 4]
    starts = sorted(set(o for o in offs if o))
    size = {s: (starts[j + 1] if j + 1 < len(starts) else len(d) - ta) - s for j, s in enumerate(starts)}
    return ta, offs, size


def script_screens(mhtxt):
    """{script: [screen]} from a MAPHEAD's assembly: the first SET_SCRIPT of each screen's section (screens < 255; the
    later ones have their section in SCRN.DAT), the rule bytecode.screens_by_script applies to a DG.SCN's header."""
    out, cur = {}, None
    for line in mhtxt.split('\n'):
        m = re.match(r'sec(\d+):', line)
        if m: cur = int(m.group(1)) if int(m.group(1)) <= 254 else None; continue
        m = re.match(r'\s*SET_SCRIPT\s+(\d+),', line)
        if m and cur is not None: out.setdefault(int(m.group(1)), []).append(cur); cur = None
    return out


def audit(dg, maphead):
    mhtxt = open(maphead if maphead.endswith('.txt') else os.path.join(disassemble(maphead, 'maphead'), 'maphead.scn.txt'),
                 encoding='utf-8').read()
    loads = script_screens(mhtxt) if os.path.isdir(dg) else None
    dgdir = dg if os.path.isdir(dg) else disassemble(dg, 'dg')
    slots = {}
    for scr in mb.MAPS:
        p = mb.map_path(scr)
        if p: slots[scr] = [(d['type'], d['scriptId']) for d in dwmap.MapFile(open(p, 'rb').read()).digimon]
    sets, cur = collections.defaultdict(set), None
    for line in mhtxt.split('\n'):
        m = re.match(r'sec(\d+):', line)
        if m: cur = int(m.group(1)); continue
        m = re.match(r'\s*SET_DIGIMON\s+(\d+),\s*(\d+)', line)
        if m and cur is not None: sets[cur].add((int(m.group(1)), int(m.group(2))))
    per_type = collections.defaultdict(set)
    unresolved = []
    for f in sorted(glob.glob(os.path.join(dgdir, 'script_*.scn.txt'))):
        txt = open(f, encoding='utf-8', errors='replace').read()
        sid = int(re.search(r'script_(\d+)', f).group(1))
        if loads is not None:
            # rule: a screen the game's map list does not have (239-254: a MAPHEAD section, no .MAP; docs/data/map_files.csv)
            # holds no Digimon, so its SET_SCRIPT resolves no actor (a DG.SCN's header lists them with no name, which the
            # parsing below skips: the two inputs give the same table)
            screens = sorted(s for s in loads.get(sid, []) if s in mb.MAPS)
        else:
            m = re.search(r'screens that load it[^:]*: (.*)', txt)
            screens = [int(x) for x in re.findall(r'(?:^|, )(\d+) ', m.group(1))] if m else []
        local = {(int(a), int(b)) for a, b in re.findall(r'SET_DIGIMON\s+(\d+),\s*(\d+)', txt)}

        def types_of(actor):
            out = set()
            for s in screens:
                if s not in slots: return None              # no .MAP: cannot resolve
                for k, (t, sc) in enumerate(slots[s]):
                    if sc == actor:
                        out.add(t)
                        out |= {tt for tt, kk in sets[s] | local if kk == k}
            return out or None

        for line in txt.split('\n'):
            hits = []
            m = re.match(r'\s*PLAY_ANIMATION\s+(\w+),\s*(\w+)', line)
            if m: hits.append((m.group(1), m.group(2), False))
            m = re.match(r'\s*(ENTITY_WALK_TO(?:_WITH_CAMERA)?|ENTITY_WALK_TO_ENTITY(?:_WITH_CAMERA)?)\s+(.*?)\s*(?:;|$)', line)
            if m:
                a = [x.strip() for x in m.group(2).split(',')]
                hits.append((a[0], a[1] if 'ENTITY_WALK_TO_ENTITY' in m.group(1) else a[3], True))
            for actor, val, walk in hits:
                if actor in ('TAMER', 'PARTNER'): continue
                if not val.isdigit():
                    unresolved.append((sid, line.strip(), 'slot not a constant')); ALWAYS.update(range(MAX_SLOTS)); continue
                slot = (int(val) + 1) * 2 if walk else int(val)
                ts = types_of(int(actor)) if actor.isdigit() else None
                if ts is None:
                    unresolved.append((sid, line.strip())); ALWAYS.add(slot)
                else:
                    for t in ts: per_type[t].add(slot)
    keep = {t: set(range(MAX_SLOTS)) if t in FULL else ALWAYS | per_type.get(t, set()) for t in range(NUM_TYPES)}
    return keep, per_type, unresolved


_keep_cache = None


@functools.lru_cache(None)
def trimmed_size(t):
    """Bytes NPC model type t keeps after trimNpcModel (npc_anim_trim.c): the file minus the
    dropped animations plus the one-frame stub; the file size if it is not worth it."""
    global _keep_cache
    if t >= NUM_TYPES: return mb.mmd_size(t)
    try: d = mb.model_data(t)
    except FileNotFoundError: return mb.mmd_size(t)
    if _keep_cache is None and not mb.TARGET_FACTS.get('npc_anim_keep'):
        _keep_cache = audit(os.path.join(ROOT, 'extracted/SCN/DG.SCN'), os.path.join(ROOT, 'extracted/SCN/MAPHEAD.SCN'))[0]
    ta, offs, size = mmd_slots(d)
    target = mb.TARGET_FACTS.get('npc_anim_keep')
    keep = target[t] if target else _keep_cache[t]
    kept = {o for i, o in enumerate(offs) if o and i in keep}
    dropped = sum(size[o] for o in set(size) - kept)
    bones = int(mb.DIGI[t]['bone_count']) if t in mb.DIGI else 0
    scale = struct.unpack_from('<H', d, ta + offs[0])[0] & 0x8000
    stub = ((bones - 1) * (9 if scale else 6) + 2) * 2
    return len(d) if dropped < stub + 16 else len(d) - dropped + stub


def savings(keep):
    rows = []
    for t in range(NUM_TYPES):
        p, name = mb.model_file(t)
        if not os.path.exists(p): continue
        d = open(p, 'rb').read()
        ta, offs, size = mmd_slots(d)
        kept = {o for i, o in enumerate(offs) if o and i in keep[t]}
        dropped = set(size) - kept
        rows.append(dict(type=t, name=mb.digi_name(t), file=name, size=len(d), slots=len(offs),
                         dropped_slots=[i for i, o in enumerate(offs) if o and o not in kept],
                         saved=sum(size[o] for o in dropped)))
    return rows


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('cmd', choices=['report', 'gen']); ap.add_argument('out', nargs='?')
    ap.add_argument('--dg', default=os.path.join(ROOT, 'extracted/SCN/DG.SCN'))
    ap.add_argument('--maphead', default=os.path.join(ROOT, 'extracted/SCN/MAPHEAD.SCN'))
    a = ap.parse_args()
    keep, per_type, unresolved = audit(a.dg, a.maphead)
    if a.cmd == 'report':
        rows = savings(keep)
        tot = sum(r['size'] for r in rows); sav = sum(r['saved'] for r in rows)
        print(f'always kept: {sorted(ALWAYS)}')
        print(f'unresolved script actors (slot kept for every type): {len(unresolved)}')
        for u in unresolved: print('  ', u)
        print(f'{len(rows)} models, {tot} bytes, {sav} bytes of animations dropped ({100 * sav / tot:.1f}%)')
        for r in sorted(rows, key=lambda r: -r['saved']):
            extra = sorted(per_type.get(r['type'], set()) - ALWAYS)
            print(f"{r['type']:3} {r['name']:16} {r['file']:5} {r['size']:6} -{r['saved']:6}  dropped {r['dropped_slots']}"
                  f"  script-only kept {extra}")
        return
    masks = [sum(1 << s for s in keep[t] if s < MAX_SLOTS) for t in range(NUM_TYPES)]
    distinct = sorted(set(masks), key=masks.index)
    lines = ['/*', ' * MOD (memreclaim): animation slots each Digimon type keeps when it is', ' * loaded as an NPC (heap model).',
             ' * GENERATED by tools/npcanims.py gen from DG.SCN, MAPHEAD.SCN and the .MAP',
             ' * files; do not edit (see that tool for the rules). Slot s is bit s % 32',
             ' * of word s / 32 of NPC_ANIM_KEEP_MASKS[NPC_ANIM_KEEP_INDEX[type]].',
             ' */', '#include <dw/types.h>', '',
             f'const uint32_t NPC_ANIM_KEEP_MASKS[{len(distinct)}][2] = {{']
    for m in distinct:
        lines.append(f'\t{{ 0x{m & 0xFFFFFFFF:08X}, 0x{m >> 32:08X} }},')
    lines += ['};', '', f'const uint8_t NPC_ANIM_KEEP_INDEX[{NUM_TYPES}] = {{']
    for t in range(0, NUM_TYPES, 10):
        lines.append('\t' + ', '.join(f'{distinct.index(masks[u]):2}' for u in range(t, min(t + 10, NUM_TYPES))) +
                     f',  /* {t}-{min(t + 9, NUM_TYPES - 1)} */')
    lines.append('};')
    open(a.out, 'w').write('\n'.join(lines) + '\n')
    print(f'{a.out}: {NUM_TYPES} types, {len(unresolved)} unresolved actors')


if __name__ == '__main__':
    main()
