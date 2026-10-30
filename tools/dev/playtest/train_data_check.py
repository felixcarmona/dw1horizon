#!/usr/bin/env python3
"""train_data_check.py OLD_COMMIT: patch 0134's data against the code it replaced. Reads the award functions, the session, the multiplier and the slot machine of
OLD_COMMIT (a commit of build/decomp-full before the patch) and compares every number with content/tables/training-gains.json and training.json."""

from pathlib import Path as _DevPath
import sys as _dev_sys
_DEV_ROOT = str(next(p for p in _DevPath(__file__).resolve().parents if (p / "tools").is_dir()))
_dev_sys.path.insert(0, _DEV_ROOT)
_dev_sys.path.insert(0, str(_DevPath(_DEV_ROOT) / "tools"))
import json, os, re, subprocess, sys
ROOT = _DEV_ROOT
old = sys.argv[1]
def src(path): return subprocess.run(['git', '-C', os.environ.get('DECOMP_WORKTREE', os.path.join(ROOT, 'build/decomp-full')), 'show', f'{old}:{path}'], capture_output=True, text=True, check=True).stdout
G = json.load(open(os.path.join(ROOT, 'content/tables/training-gains.json'))); T = json.load(open(os.path.join(ROOT, 'content/tables/training.json')))
bad = []; n = 0
def check(name, got, want):
    global n; n += 1
    if got != want: bad.append((name, got, want))
def body(s, header):
    for m in re.finditer(re.escape(header), s):                       # the definition: its first line does not end with ';' (a prototype's does)
        line = s[m.start():s.index('\n', m.start())]
        if not line.rstrip().endswith(';'):
            return s[m.start():s.index('\n}\n', m.start())]
    raise KeyError(header)
# which stat each variable of each award function is (STATS_GAINS index: hp mp off def spd brain)
STAT = ['hp', 'mp', 'off', 'def', 'spd', 'brain']
def parse(fn_body):
    """{slot or None: {var: value}} from `x = N;` lines at the top (a slot-less function) or inside `case N:` / `if (b == N) {` blocks, and the STATS_GAINS map var -> stat."""
    gains = {int(m.group(1)): m.group(2) for m in re.finditer(r'STATS_GAINS\[(\d)\] = (\w+);', fn_body)}
    varstat = {v: STAT[i] for i, v in gains.items() if v != '0'}
    head = fn_body[:fn_body.index('v = ')] if 'v = ' in fn_body else fn_body
    rows = {}
    cur = None
    for line in head.split('\n'):
        line = line.strip()
        m = re.match(r'case (\d+):', line)
        if m: cur = int(m.group(1)); rows.setdefault(cur, {}); continue
        m = re.match(r'if \(b == (\d+)\) \{', line)
        if m: cur = int(m.group(1)); rows.setdefault(cur, {}); continue
        m = re.match(r'(\w+) = (\d+);', line)
        if m and m.group(1) in ('x', 'y', 'hp', 'off', 'spd', 'mp', 'brains', 'tired', 'energy', 'happy'):
            rows.setdefault(cur, {})[m.group(1)] = int(m.group(2))
    return rows, varstat
def compare(setname, text, fns):
    jrows = G[setname]
    for gym, header in fns:
        rows, varstat = parse(body(text, header))
        for slot, vals in rows.items():
            if not vals or all(v == 0 for v in vals.values()): continue
            want = {varstat.get(k, k): v for k, v in vals.items() if k not in ('tired', 'energy', 'happy')}
            want = {('brain' if k == 'brains' else k): v for k, v in want.items()}
            got = [r for r in jrows if r['gym'] == gym and r['slot'] in (slot, 'any')]
            check(f'{setname} {gym} slot {slot}: a row', len(got) == 1, True)
            if got:
                r = got[0]
                check(f'{setname} {gym} slot {slot}: stats', {k: r[k] for k in STAT if k in r}, want)
                check(f'{setname} {gym} slot {slot}: costs', (r['tired'], r['energy'], r['happy']), (vals['tired'], vals['energy'], vals['happy']))
trn = src('src/trn/trn_reward.c')
compare('trainGain', trn, [('hp', 'void TRN_awardHpTrainingGains'), ('mp', 'void TRN_awardMpTrainingGains'), ('def', 'void TRN_awardDefenseTrainingGains'),
                           ('off', 'void TRN_awardOffenseTrainingGains'), ('spd', 'void TRN_awardSpeedTrainingGains'), ('brain', 'void TRN_awardBrainsTrainingGains')])
trn2 = src('src/trn2/trn2_reward.c')
compare('train2Gain', trn2, [('hp', 'void TRN2_awardHpTrainingGains'), ('mp', 'void TRN2_awardMpTrainingGains'), ('off', 'void TRN2_awardOffenseTrainingGains'),
                             ('spd', 'void TRN2_awardSpeedTrainingGains'), ('def', 'void TRN2_awardDefenseTrainingGains')])
# the session
def num(x): return int(x, 0)
for key, text, fn in (('trainRules', trn, 'void TRN_advanceTrainingTime'), ('train2Rules', src('src/trn2/trn2_hud.c'), 'void TRN2_advanceTrainingTime')):
    b = body(text, fn); r = G[key]
    check(f'{key} tiredPenaltyAt', r['session']['tiredPenaltyAt'], num(re.search(r'tiredness >= (0x[0-9a-f]+)', b).group(1)))
    check(f'{key} penalties', (r['session']['penaltyHappinessLoss'], r['session']['penaltyDisciplineLoss']), tuple(int(x) for x in re.findall(r'-= (\d+);\n\t\tPARTNER_PARA\.discipline -= (\d+);', b)[0]))
    check(f'{key} lifetimeBelowHappiness', r['session']['lifetimeBelowHappiness'], num(re.search(r'happiness < (0x[0-9a-f]+)', b).group(1)))
    check(f'{key} lifetimePerPoints', r['session']['lifetimePerPoints'], int(re.search(r'/ -(\d+)\)', b).group(1)))
    check(f'{key} starvationDrop', r['session']['starvationDrop'], num(re.search(r'starvationTimer -= (0x[0-9a-f]+);', b).group(1)))
    check(f'{key} foodDrop', r['session']['foodDrop'], num(re.search(r'foodLevel -= (0x[0-9a-f]+);', b).group(1)))
    check(f'{key} poopDrop', r['session']['poopDrop'], int(re.search(r'poopLevel -= (\d+);', b).group(1)))
for key, f in (('trainRules', 'src/trn/trn_slots.c'), ('train2Rules', 'src/trn2/trn2_slots.c')):
    p = [num(x) for x in re.findall(r'p->payout = (\w+);', src(f))]
    s = G[key]['slots']; check(f'{key} slot payouts', [s['jackpot'], s['match'], s['triple'], s['miss']], p)
exh = [x for x in re.findall(r'tiredness == (\d+)', trn)]; check('exhausted at', set(exh), {str(G['trainRules']['exhausted']['at'])})
b = body(trn, 'void TRN_awardBrainsTrainingGains')
check('order marks', [num(x) for x in re.findall(r'\(base < (0x[0-9a-f]+)\) && \(total >= \1\)', b)][:5], G['trainRules']['brains']['orderMarks'])
learn = re.search(r'else if \((.*?)\) \{ /\* MOD \(caps\)', b, re.S).group(1)
check('learn marks', [num(x) if x.startswith('0x') else int(x) for x in re.findall(r'base < (0x[0-9a-f]+|\d+)\)', learn)], G['trainRules']['brains']['learnMarks'])
# the multiplier of the second gym set (its original code, copied) against training.json "training2"
old_mult = body(src('src/trn2/trn2_hud.c'), 'int16_t TRN2_calculateTrainingMultiplier')
def original(tt, mode, lv, item):
    pref = {0: [10, 10, 9, 11], 1: [10, 9, 11, 10], 2: [10, 11, 10, 9], 3: [10, 10, 9, 11], 4: [10, 11, 10, 9], 5: [10, 9, 11, 10]}[mode]
    num = pref[tt] if tt < 4 else 8
    num *= 9 if lv in (1, 2) else 10 if lv == 3 else 11 if lv == 4 else 13 if lv == 6 else 12
    den = 100
    if item: num *= 11; den *= 10
    return (num * 10) // den
def new(tt, mode, lv, item):
    t = T['training2']; tt = min(tt, 4); lv = min(lv, 7)
    num = t['gainTenths'][mode][tt] * t['levelTenths'][lv]; den = 100
    for b2 in t['bonuses']:
        if b2['when'] == 'item' and item and mode in b2['modes']: num *= b2['multiply'][0]; den *= b2['multiply'][1]
    return (num * 10) // den
diff = [(tt, m, lv, it) for tt in range(8) for m in range(6) for lv in range(10) for it in (0, 1) if original(tt, m, lv, it) != new(tt, m, lv, it)]
check('the second gym multiplier over 960 cases', len(diff), 0)
print(f'{"ok " if not bad else "BAD"} {n - len(bad)} of {n} numbers of the training data equal the code they replaced')
for x in bad[:12]: print('   ', x)
sys.exit(1 if bad else 0)
