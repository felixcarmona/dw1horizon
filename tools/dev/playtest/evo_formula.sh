#!/usr/bin/env bash
# evo_formula.sh: patch 0131 in the emulator (disc build/full.cue with content/tables/evolution-rules.json "evolutionFormula"). The requirement score
# (calculateRequirementScore: care mistakes, weight +-5, the stats, the bonus condition, the points a species needs) is called for the first 62
# targets with three hand-made partner states and compared with a Python copy of the original rule; callfn passes four arguments, so the fifth (the
# best candidate so far) is whatever is on the stack: only a score under the pass mark is compared exactly, a higher one may have been lowered to 0 or
# raised by one by the tie-break. Then the table wiped in RAM: no score reaches the pass mark and every answer is 0.
set -u
cd "$(dirname "$0")/../../.."
export EMU_PORT=38119 EMU_ARGS="-interpreter -debugger"
DISC=${DISC:-build/full.cue}
mkdir -p build/savedrop; cp build/ids-saved.mcd build/savedrop/v.mcd
tools/dev/emulator.py start $DISC --card build/savedrop/v.mcd >/dev/null
tools/dev/emulator.py seq tools/dev/sequences/continue.seq >/dev/null; tools/dev/emulator.py wait 30 >/dev/null
tools/dev/emulator.py save build/savedrop/v.state >/dev/null
python3 -u - <<'PY'
import os, re, struct, subprocess, sys, time
sys.path.insert(0, 'tools'); from tools.dev import symbols as dwsyms; import species as SP
T = dwsyms.table(os.environ.get('DW_SYMS', 'disc-full'))
def emu(*a): return subprocess.run([sys.executable, 'tools/dev/emulator.py', *a], capture_output=True, text=True).stdout
def poke(addr, fmt, *v): emu('poke', hex(addr), struct.pack(fmt, *v).hex())
def peek(addr, n): return bytes.fromhex(''.join(l.split(None, 1)[1].replace(' ', '') for l in emu('peek', hex(addr), str(n)).strip().split('\n')))
def gs(**kw): subprocess.run([sys.executable, 'tools/dev/game_state.py', 'set', *[f'{k}={v}' for k, v in kw.items()]], capture_output=True)
def ok(name, bad, total): print(f'{"ok " if not bad else "BAD"} {name:62s} {total - len(bad)} of {total}' + (f'  first: {bad[0]}' if bad else ''))
REQ, PARA, FORMULA = T['EVOLUTION_REQS'], T['DIGIMON_DATA'], T['MOD_EVO_FORMULA']
rows = {t: SP.unpack(SP.REQ_FIELDS, peek(REQ + 28 * t, 28)) for t in range(1, 63)}
level = {t: SP.unpack(SP.PARA_FIELDS, peek(PARA + 52 * t, 52))['level'] for t in range(1, 63)}
LV = {'none': 0, 'fresh': 1, 'in-training': 2, 'rookie': 3, 'champion': 4, 'ultimate': 5, 'mega': 6}
level = {t: (LV.get(v, v) if isinstance(v, str) else v) for t, v in level.items()}
STATES = [dict(hp=2000, mp=1500, off=150, de=120, speed=130, brain=100, weight=20, care=2, disc=60, happy=50, battles=10),
          dict(hp=6000, mp=5000, off=400, de=380, speed=390, brain=360, weight=35, care=0, disc=100, happy=100, battles=60),
          dict(hp=3200, mp=2800, off=210, de=190, speed=200, brain=170, weight=28, care=4, disc=30, happy=-20, battles=25)]
def expected(S, r, t, current):
    p = 0
    if S['care'] >= r['care']: p += 1
    if r['weight'] - 5 <= S['weight'] <= r['weight'] + 5: p += 1
    if level[t] == 3:
        st = [S['hp'] // 10, S['mp'] // 10, S['off'], S['de'], S['speed'], S['brain']]; req = [r['hp'], r['mp'], r['offense'], r['defense'], r['speed'], r['brain']]
        hi = max(i for i in range(6) if all(st[i] >= x for x in st))
        if req[hi] == 1: p += 1
    elif S['hp'] // 10 >= r['hp'] and S['mp'] // 10 >= r['mp'] and S['off'] >= r['offense'] and S['de'] >= r['defense'] and S['speed'] >= r['speed'] and S['brain'] >= r['brain']: p += 1
    bonus = (r['digimon'] != -1 and current == r['digimon']) or (r['discipline'] != -1 and S['disc'] >= r['discipline']) or \
            (r['happiness'] != -1 and S['happy'] >= r['happiness']) or (r['battles'] != -1 and S['battles'] >= r['battles']) or (r['techs'] != -1 and 0 >= r['techs'])
    return p + bool(bonus)
def scores(S, wiped):
    print('scores', S['hp'], 'wiped' if wiped else '', flush=True)
    emu('load', 'build/savedrop/v.state'); emu('lua', 'PCSX.pauseEmulator() return 1')
    if wiped:
        for i in range(31): poke(FORMULA + 2 * i, '<h', -1)
    gs(**{'partner.stats.hp': S['hp'], 'partner.stats.mp': S['mp'], 'partner.stats.off': S['off'], 'partner.stats.def': S['de'], 'partner.stats.speed': S['speed'],
          'partner.stats.brain': S['brain'], 'partner.para.weight': S['weight'], 'partner.para.careMistakes': S['care'], 'partner.para.discipline': S['disc'],
          'partner.para.happiness': S['happy'], 'partner.para.battles': S['battles']})
    p = subprocess.Popen([sys.executable, 'tools/dev/playtest/call_function.py'] + [f'calculateRequirementScore(3,{t},0,0,0)' for t in rows],
                         env=dict(os.environ, CALLFN_PAUSE='1'), stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    time.sleep(2.0); emu('lua', 'PCSX.resumeEmulator() return 1')
    try: out = p.communicate(timeout=150)[0]
    except subprocess.TimeoutExpired: p.kill(); out = p.communicate()[0]; print('callfn timed out', flush=True)
    r = [int(x) & 0xFF for x in re.findall(r'= (\d+)', out)]; print('  answers', len(r), flush=True)
    return r
exact = []; fuzzy = []; total = 0
for k, S in enumerate(STATES):
    got = scores(S, 0)
    for t, g in zip(rows, got):
        e = expected(S, rows[t], t, 3); total += 1
        if e < 3: exact += [] if g == e else [(k, t, g, e)]
        else: fuzzy += [] if g in (0, e, e + 1) else [(k, t, g, e)]
ok('the score under the pass mark equals the original rule', exact, total)
ok('the score at or over the pass mark is 0, the same or one more', fuzzy, total)
got = scores(STATES[1], 1)
ok('table wiped: every answer is 0', [(t, g) for t, g in zip(rows, got) if g != 0], len(got))
PY
tools/dev/emulator.py stop >/dev/null
