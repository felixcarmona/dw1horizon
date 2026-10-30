#!/usr/bin/env python3
"""Measure the story layer of Digimon World from the disassembly of DG.SCN and MAPHEAD.SCN.

Input : build/scn-dis/script_NNN.scn.txt and maphead.scn.txt (python3 tools/dws/bytecode/__init__.py dis ...)
Output: CSV files in build/story-analysis/ (read by tools/dws/testing/branches.py; docs/reference/story-engine.md).
Run   : python3 tools/story_analysis.py
"""
import sys as _sys
if __name__ == '__main__' and _sys.argv[1:2] in (['-h'], ['--help']): print(__doc__); _sys.exit(0)
import csv, glob, os, re, collections, json, sys
ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
DIS = os.path.join(ROOT, 'build', 'scn-dis')
OUT = os.path.join(ROOT, 'build', 'story-analysis')
os.makedirs(OUT, exist_ok=True)

INS = re.compile(r'^    ([A-Z][A-Z_0-9]*)\b(.*)$')
LAB = re.compile(r'^([A-Za-z_][A-Za-z_0-9]*):')
SEC = re.compile(r'^\.section (\d+) (\S+)')
TXT = re.compile(r'^\s{8}"(.*)"\s*$')

MOTION = {'ENTITY_WALK_TO','ENTITY_WALK_TO_WITH_CAMERA','ENTITY_WALK_TO_ENTITY','ENTITY_WALK_TO_ENTITY_WITH_CAMERA',
          'ENTITY_MOVE_TO','ENTITY_MOVE_TO_WITH_CAMERA','ENTITY_MOVE_TO_ENTITY','ENTITY_MOVE_TO_AXIS',
          'ENTITY_MOVE_TO_AXIS_WITH_CAMERA','MOVE_CAMERA_TO','MOVE_CAMERA_TO_ENTITY','ENTITY_SET_ROTATION',
          'ENTITY_LOOK_AT_ENTITY','PLAY_ANIMATION','MOVE_OBJECT_TO','ROTATE_3D_OBJECT','MOVE_BOULDER',
          'SPAWN_SPRITE_AT_ENTITY','SPAWN_SPRITE_AT_LOCATION'}
CATEGORY = {}
def cat(name, ops):
    for o in ops.split():
        CATEGORY[o] = name
cat('flow', 'JUMP_TO JUMP_AND_LINK JUMP_RETURN JUMP_TO_FILE JUMP_TO_FILE_AND_LINK SWITCH IF END_SECTION END_SCRIPT DATA SET_SCRIPT SECTION_ON_EXIT')
cat('dialogue', 'SHOW_TEXTBOX SET_DIALOG_OWNER SET_SELECTION END_SELECTION SET_TEXTBOX_SIZE SET_TEXTBOX_MODE SET_TEXTBOX_ORIGIN FADEOUT_HUD')
cat('state', 'SET_TRIGGER UNSET_TRIGGER SET_PSTAT ADD_TO_PSTAT REDUCE_PSTAT COPY_PSTAT STORE_RANDOM STORE_MAP_ID STORE_DIGIMON_TYPE STORE_DIGIMON_VALUE STORE_DATE')
cat('inventory', 'GIVE_ITEM REMOVE_ITEM SET_INVENTORY_SIZE ADD_MONEY REDUCE_MONEY GIVE_CARD TAKE_CARD SET_MERIT ADD_MERIT REDUCE_MERIT LEARN_MOVE')
cat('partner', 'SET_STAT ADD_STAT REDUCE_STAT REMOVE_CONDITION DEAL_DAMAGE CALL_DIGIMON_ROUTINE')
cat('clock', 'ADVANCE_TO_DATE_AT ADD_MINUTES_TO_DATE_AT ADD_MINUTES_TO_DATE_AT_2 COMPARE_DATE DELAY')
cat('entities', 'LOAD_DIGIMON SET_DIGIMON UNLOAD_ENTITY UNLOAD_DIGIMON SET_AUTOTALK WAIT_FOR_ENTITY RESET_ENTITY_ORIGIN')
cat('motion/camera', ' '.join(sorted(MOTION - {'PLAY_ANIMATION'})) + ' PLAY_ANIMATION')
cat('world objects', 'SET_OBJ_VISIBILITY SPAWN_ITEM SPAWN_CHEST SPAWN_BOULDER DESPAWN_BOULDER SET_RECT_IMPASSABLE')
cat('screen change', 'WARP_TO TELEPORT')
cat('audio', 'PLAY_SOUND SET_BGM STOP_BGM')
cat('battle', 'START_BATTLE')
cat('engine routine', 'CALL_ROUTINE')

def parse(path):
    sections = {}          # id -> label
    cur = None
    rows = []              # (section_label, op, args, text_lines)
    for line in open(path, encoding='utf-8'):
        line = line.rstrip('\n')
        m = SEC.match(line)
        if m:
            sections[m.group(2)] = int(m.group(1)); continue
        m = LAB.match(line)
        if m:
            if m.group(1) in sections: cur = m.group(1)
            continue
        m = TXT.match(line)
        if m and rows:
            rows[-1][3].append(m.group(1)); continue
        m = INS.match(line)
        if m:
            args = m.group(2).split(';')[0].strip()
            rows.append([cur, m.group(1), args, []])
    return sections, rows

def header(path):
    screens = ''
    size = 0
    for line in open(path, encoding='utf-8'):
        if line.startswith('; screens that load it'):
            screens = line.split(':', 1)[1].strip()
        if line.startswith('; useful content'):
            size = int(re.search(r'(\d+) bytes', line).group(1))
        if not line.startswith(';') : break
    return screens, size

def conds(args):
    """List the conditions of an IF line."""
    out = []
    for c in args.split(', '):
        c = c.strip()
        if c.startswith('then ') or c.startswith('else '): continue
        out.append(c)
    return out

scripts = {}
files = sorted(glob.glob(os.path.join(DIS, 'script_*.scn.txt'))) + [os.path.join(DIS, 'maphead.scn.txt')]
for f in files:
    name = os.path.basename(f)
    sid = 'MH' if name.startswith('maphead') else int(re.search(r'(\d+)', name).group(1))
    if sid == 0: continue            # entry 0 is an unused copy of MAPHEAD.SCN
    secs, rows = parse(f)
    scr, size = header(f)
    scripts[sid] = dict(secs=secs, rows=rows, screens=scr, size=size)

# ---- 1. opcode usage -------------------------------------------------------
cnt_dg = collections.Counter(); cnt_mh = collections.Counter(); users = collections.defaultdict(set)
for sid, s in scripts.items():
    for sec, op, args, tx in s['rows']:
        (cnt_mh if sid == 'MH' else cnt_dg)[op] += 1
        users[op].add(sid)
with open(os.path.join(OUT, 'opcode-usage.csv'), 'w', newline='') as fh:
    w = csv.writer(fh); w.writerow(['opcode', 'category', 'count_DG_SCN', 'count_MAPHEAD', 'total', 'scripts_using'])
    for op in sorted(set(cnt_dg) | set(cnt_mh), key=lambda o: -(cnt_dg[o] + cnt_mh[o])):
        w.writerow([op, CATEGORY.get(op, '?'), cnt_dg[op], cnt_mh[op], cnt_dg[op] + cnt_mh[op], len(users[op])])

# ---- IF conditions ---------------------------------------------------------
kinds = collections.Counter()
for sid, s in scripts.items():
    for sec, op, args, tx in s['rows']:
        if op != 'IF': continue
        for c in conds(args):
            c = re.sub(r'^(and|or) ', '', c); neg = c.startswith('not ')
            c = re.sub(r'^not ', '', c)
            k = c.split()[0]
            if re.match(r'p\d+$', k): k = 'pstat compare'
            if k == 'stat': k = 'stat ' + c.split()[1]
            kinds[('not ' if neg else '') + k if k in ('trigger', 'move', 'cond') else k] += 1
with open(os.path.join(OUT, 'if-conditions.csv'), 'w', newline='') as fh:
    w = csv.writer(fh); w.writerow(['condition', 'count'])
    for k, v in kinds.most_common(): w.writerow([k, v])

# ---- 2. per script table ---------------------------------------------------
tot = collections.Counter()
with open(os.path.join(OUT, 'scripts.csv'), 'w', newline='') as fh:
    w = csv.writer(fh)
    w.writerow(['script', 'bytes', 'sections', 'instructions', 'text_lines', 'text_boxes', 'selections', 'battles',
                'warps', 'trigger_writes', 'trigger_reads', 'motion_cmds', 'routines', 'screens'])
    for sid, s in scripts.items():
        rows = s['rows']; c = collections.Counter(r[1] for r in rows)
        tl = sum(len(r[3]) for r in rows)
        trw = c['SET_TRIGGER'] + c['UNSET_TRIGGER']
        trr = sum(1 for r in rows if r[1] == 'IF' for x in conds(r[2]) if 'trigger' in x)
        mo = sum(c[o] for o in MOTION)
        w.writerow([sid, s['size'], len(s['secs']), len(rows), tl, c['SHOW_TEXTBOX'], c['SET_SELECTION'], c['START_BATTLE'],
                    c['WARP_TO'], trw, trr, mo, c['CALL_ROUTINE'], s['screens']])
        tot['instr'] += len(rows); tot['text'] += tl; tot['secs'] += len(s['secs'])

# ---- 3. triggers -----------------------------------------------------------
sets = collections.defaultdict(set); clears = collections.defaultdict(set); reads = collections.defaultdict(set)
edges = collections.Counter()
sec_reads = collections.defaultdict(set); sec_sets = collections.defaultdict(set)
for sid, s in scripts.items():
    inv = {v: k for k, v in s['secs'].items()}
    for sec, op, args, tx in s['rows']:
        secid = s['secs'].get(sec, -1)
        where = f'{sid}:{secid}'
        if op == 'SET_TRIGGER':
            t = int(args); sets[t].add(where); sec_sets[(sid, secid)].add(t)
        elif op == 'UNSET_TRIGGER':
            t = int(args); clears[t].add(where)
        elif op == 'SPAWN_CHEST':
            t = int(args.split(',')[-1]); sets[t].add(where + '(chest)')
        elif op == 'IF':
            for c in conds(args):
                m = re.search(r'trigger (\d+)', c)
                if m:
                    t = int(m.group(1)); reads[t].add(where); sec_reads[(sid, secid)].add(t)

def trig_meaning(t):
    if t == 0: return 'GIVE_ITEM did not fit'
    if t <= 4: return 'engine flag (battle/shop)'
    if 5 <= t <= 14: return 'Mojyamon trades'
    if 15 <= t <= 36: return 'cup won (15 + cup id)'
    if 37 <= t <= 41: return 'tournament registration / reminders'
    if t in (44, 49): return 'engine flag (cutscene no-turn / uncancellable selection)'
    if t == 50: return 'game beaten once'
    if 200 <= t <= 312: return 'Digimon type %d recruited/beaten (200+type)' % (t - 200)
    if 364 <= t <= 382: return 'medal %d' % (t - 364)
    if 384 <= t <= 511: return 'shop stock: item %d' % (t - 384)
    if 512 <= t <= 574: return 'Digimon type %d ever raised (C)' % (t - 512)
    if 650 <= t <= 716: return 'chest opened'
    if 717 <= t <= 799: return 'free block (our quests)'
    return ''
with open(os.path.join(OUT, 'trigger-usage.csv'), 'w', newline='') as fh:
    w = csv.writer(fh); w.writerow(['trigger', 'meaning', 'set_by', 'cleared_by', 'read_by'])
    for t in range(800):
        if sets[t] or clears[t] or reads[t]:
            w.writerow([t, trig_meaning(t), ' '.join(sorted(sets[t])), ' '.join(sorted(clears[t])), ' '.join(sorted(reads[t]))])

edge_rows = []

# ---- 4. pstat usage --------------------------------------------------------
ps_w = collections.Counter(); ps_r = collections.Counter()
for sid, s in scripts.items():
    for sec, op, args, tx in s['rows']:
        if op in ('SET_PSTAT', 'ADD_TO_PSTAT', 'REDUCE_PSTAT', 'STORE_RANDOM'):
            m = re.match(r'p(\d+)', args); ps_w[int(m.group(1))] += 1
        if op == 'IF':
            for c in conds(args):
                m = re.search(r'\bp(\d+) [=!<>]', c)
                if m: ps_r[int(m.group(1))] += 1
        if op == 'SWITCH':
            m = re.match(r'p(\d+)', args); ps_r[int(m.group(1))] += 1
with open(os.path.join(OUT, 'pstat-usage.csv'), 'w', newline='') as fh:
    w = csv.writer(fh); w.writerow(['pstat', 'saved_to_card', 'writes', 'reads'])
    for p in sorted(set(ps_w) | set(ps_r)):
        w.writerow([p, 'yes' if p < 35 else 'no', ps_w[p], ps_r[p]])

# ---- 5. cutscenes ----------------------------------------------------------
cut_rows = []
for sid, s in scripts.items():
    bysec = collections.defaultdict(list)
    for r in s['rows']: bysec[r[0]].append(r)
    for lab, rs in bysec.items():
        c = collections.Counter(r[1] for r in rs)
        motion = sum(c[o] for o in MOTION)
        cam = c['MOVE_CAMERA_TO'] + c['MOVE_CAMERA_TO_ENTITY'] + c['ENTITY_WALK_TO_WITH_CAMERA'] + c['ENTITY_MOVE_TO_WITH_CAMERA'] + c['ENTITY_MOVE_TO_AXIS_WITH_CAMERA'] + c['ENTITY_WALK_TO_ENTITY_WITH_CAMERA']
        walk = sum(c[o] for o in MOTION if 'WALK' in o or 'MOVE_TO' in o and 'CAMERA_TO' not in o)
        ntext = c['SHOW_TEXTBOX']
        first = next((r[3][0] for r in rs if r[3]), '')
        starts44 = any(r[1] == 'SET_TRIGGER' and r[2] == '44' for r in rs)
        if motion >= 8 or (walk >= 2 and starts44) or (cam >= 2 and walk >= 1):
            ops = collections.Counter(r[1] for r in rs if r[1] not in ('SHOW_TEXTBOX', 'SET_DIALOG_OWNER', 'END_SECTION', 'JUMP_TO', 'IF'))
            kind = 'menu-driven (shop/food/training)' if (c['SET_SELECTION'] >= 2 and c['ADD_STAT'] + c['REDUCE_MONEY'] + c['GIVE_ITEM'] >= 10) else ('boss/battle scene' if c['START_BATTLE'] else 'cutscene')
            cut_rows.append([kind, sid, s['secs'].get(lab, -1), s['screens'][:40], len(rs), ntext, walk, cam, c['WAIT_FOR_ENTITY'], c['FADEOUT_HUD'] + c['CALL_ROUTINE'],
                             c['START_BATTLE'], c['WARP_TO'], 'Y' if starts44 else '', first[:50],
                             ' '.join(f'{o}x{n}' for o, n in ops.most_common(8))])
cut_rows.sort(key=lambda r: -r[4])
with open(os.path.join(OUT, 'cutscenes.csv'), 'w', newline='') as fh:
    w = csv.writer(fh); w.writerow(['kind', 'script', 'section', 'screens', 'instructions', 'text_boxes', 'walks', 'camera', 'waits', 'fades+routines',
                                     'battles', 'warps', 'trigger44', 'first_line', 'top_commands'])
    w.writerows(cut_rows)

# ---- 6. C routines used (CALL_ROUTINE n) -----------------------------------
rt = collections.Counter(); rtw = collections.defaultdict(set)
for sid, s in scripts.items():
    for sec, op, args, tx in s['rows']:
        if op == 'CALL_ROUTINE':
            rt[int(args, 0)] += 1; rtw[int(args, 0)].add(sid)
with open(os.path.join(OUT, 'call-routines.csv'), 'w', newline='') as fh:
    w = csv.writer(fh); w.writerow(['routine', 'hex', 'count', 'scripts'])
    for r, n in sorted(rt.items()): w.writerow([r, hex(r), n, ' '.join(map(str, sorted(rtw[r], key=str)))])

# ---- 7. date/clock use, battles, items -------------------------------------
print('scripts', len(scripts) - 1, 'sections(DG+MH)', tot['secs'], 'instructions', tot['instr'], 'text lines', tot['text'])
print('triggers used by scripts', len([t for t in range(800) if sets[t] or clears[t] or reads[t]]), 'cutscene candidates', len(cut_rows), '')

# ---- 8. script-to-script calls (JUMP_TO_FILE) and script users -------------
calls = collections.defaultdict(set)
for sid, s in scripts.items():
    for sec, op, args, tx in s['rows']:
        if op in ('JUMP_TO_FILE', 'JUMP_TO_FILE_AND_LINK'):
            a = [x.strip() for x in args.split(',')]
            calls[(sid, int(a[0]))].add(int(a[1]))
with open(os.path.join(OUT, 'script-calls.csv'), 'w', newline='') as fh:
    w = csv.writer(fh); w.writerow(['from_script', 'to_script', 'sections_called'])
    for (a, b), secs in sorted(calls.items(), key=lambda x: (str(x[0][0]), x[0][1])): w.writerow([a, b, ' '.join(map(str, sorted(secs)))])

# ---- 9. cross-script trigger gates (the quest graph at area level) ---------
ENGINE = set(range(0, 5)) | {44, 49}
gates = collections.defaultdict(set)
for t in range(800):
    if t in ENGINE or 650 <= t <= 716 or 512 <= t <= 574: continue
    sa = {w.split(':')[0] for w in sets[t] if '(chest)' not in w}
    ra = {w.split(':')[0] for w in reads[t]}
    for a in sa:
        for b in ra:
            if a != b: gates[(a, b)].add(t)
def zone(sid):
    scr = scripts[int(sid)]['screens'] if str(sid).isdigit() else ''
    names = []
    for part in scr.split(', '):
        m = re.match(r'\d+ (.*)', part)
        if m and m.group(1) not in names: names.append(m.group(1))
    return names[0] if names else 'script ' + str(sid)
with open(os.path.join(OUT, 'gates.csv'), 'w', newline='') as fh:
    w = csv.writer(fh); w.writerow(['set_in_script', 'zone_of_setter', 'read_in_script', 'zone_of_reader', 'triggers'])
    for (a, b), ts in sorted(gates.items(), key=lambda x: (str(x[0][0]), str(x[0][1]))):
        if a == 'MH' or b == 'MH' or True:
            w.writerow([a, zone(a) if a != 'MH' else 'MAPHEAD', b, zone(b) if b != 'MH' else 'MAPHEAD', ' '.join(map(str, sorted(ts)))])

# ---- 10. recruits: who sets 200+type ---------------------------------------
digi = {}
sys.path.insert(0, os.path.join(ROOT, 'tools')); import species   # content/species
for t, r in species.all_rows().items():
    digi[t] = (r['name'], r['level'])
with open(os.path.join(OUT, 'recruits.csv'), 'w', newline='') as fh:
    w = csv.writer(fh); w.writerow(['trigger', 'digimon_id', 'digimon', 'level', 'set_by', 'read_by'])
    for t in range(200, 313):
        d = t - 200
        w.writerow([t, d, digi.get(d, ('?', ''))[0], digi.get(d, ('?', ''))[1], ' '.join(sorted(sets[t])), ' '.join(sorted(reads[t]))])

# ---- 11. zone-level gate graph (Mermaid) ------------------------------------
zone_edges = collections.defaultdict(set)
for (a, b), ts in gates.items():
    if a == 'MH' or b == 'MH': continue
    za, zb = zone(a), zone(b)
    if za == zb: continue
    story = [t for t in ts if not (200 <= t <= 312 or 364 <= t <= 511 or 15 <= t <= 36)]
    for t in story: zone_edges[(za, zb)].add(t)
ids = {}
def nid(z):
    return ids.setdefault(z, 'z%d' % len(ids))
with open(os.path.join(OUT, 'zone-gates.mmd'), 'w') as fh:
    fh.write('%% generated by analyze.py: an edge A -> B means a script of zone A sets a trigger that a script of zone B reads\n')
    fh.write('flowchart LR\n')
    for (za, zb), ts in sorted(zone_edges.items()):
        fh.write('  %s["%s"] -->|%s| %s["%s"]\n' % (nid(za), za, ','.join(map(str, sorted(ts))), nid(zb), zb))
