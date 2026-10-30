#!/usr/bin/env bash
# evo_apply.sh: patch 0131 in the emulator, the part that runs in the EVL overlay (disc build/full.cue). Real evolutions: the partner gets known stats, weight,
# care mistakes, battles and lifetime, EVOLUTION_TARGET is set and the partner state 13 (evolving) plays the whole sequence (EVL_applyEvolution). Each stat
# is compared with the original rule (a stat past the target's gain grows by gain/10, below it meets it halfway; the species that scale take brains% of it;
# weight, care mistakes and battles reset; Ultimate adds 96 hours of life). Then the table wiped in RAM: no formula, so the stats stay (the reset of weight, mistakes and battles is also resetPartnerPara's, so it stays).
set -u
cd "$(dirname "$0")/../../.."
export EMU_PORT=38124 EMU_ARGS="-interpreter -debugger"
DISC=${DISC:-build/full.cue}
mkdir -p build/savedrop; cp build/ids-saved.mcd build/savedrop/x.mcd
tools/dev/emulator.py start $DISC --card build/savedrop/x.mcd >/dev/null
tools/dev/emulator.py seq tools/dev/sequences/continue.seq >/dev/null; tools/dev/emulator.py wait 30 >/dev/null
tools/dev/emulator.py save build/savedrop/x.state >/dev/null
python3 - <<'PY'
import subprocess, struct, sys, os, time, re
sys.path.insert(0, 'tools'); from tools.dev import symbols as dwsyms; import species
T = dwsyms.table(os.environ.get('DW_SYMS', 'disc-full')); O = species.originals()
def emu(*a): return subprocess.run([sys.executable, 'tools/dev/emulator.py', *a], capture_output=True, text=True).stdout
def poke(addr, fmt, *v): emu('poke', hex(addr), struct.pack(fmt, *v).hex())
def peek(addr, n): return bytes.fromhex(emu('peek', hex(addr), str(n)).strip().split('\n')[-1].split('  ', 1)[1].replace(' ', ''))
def gs(**kw): subprocess.run([sys.executable, 'tools/dev/game_state.py', 'set', *[f'{k}={v}' for k, v in kw.items()]], capture_output=True)
def get(f): return int(subprocess.run([sys.executable, 'tools/dev/game_state.py', 'show', f], capture_output=True, text=True).stdout.strip().split()[-1], 0)
def ok(name, got, want): print(f'{"ok " if got == want else "BAD"} {name:62s} got {got} expected {want}', flush=True)
def callfn(*exprs, pause=True):
    p = subprocess.Popen([sys.executable, 'tools/dev/playtest/call_function.py', *exprs], env=dict(os.environ, **({'CALLFN_PAUSE': '1'} if pause else {})), stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    time.sleep(2.0)
    if pause: emu('lua', 'PCSX.resumeEmulator() return 1')
    return p.communicate(timeout=200)[0]
FORMULA = T['MOD_EVO_FORMULA']
PRE = dict(hp=500, mp=300, off=100, de=80, speed=70, brain=60)
def level(t): return O.rec[t]['para']['level']
def run(t, wiped):
    emu('load', 'build/savedrop/x.state'); emu('lua', 'PCSX.pauseEmulator() return 1')
    if wiped:
        for i in range(31): poke(FORMULA + 2 * i, '<h', -1)
    gs(**{'partner.stats.hp': PRE['hp'], 'partner.stats.mp': PRE['mp'], 'partner.stats.off': PRE['off'], 'partner.stats.def': PRE['de'], 'partner.stats.speed': PRE['speed'],
          'partner.stats.brain': PRE['brain'], 'partner.para.weight': 77, 'partner.para.careMistakes': 3, 'partner.para.battles': 9, 'partner.para.remainingLifetime': 1000})
    ptr = T['EVOLUTION_STATS_GAINS'] + 14 * t
    emu('lua', 'PCSX.pauseEmulator() return 1')
    g = struct.unpack('<7h', peek(ptr, 14))
    poke(T['HAS_USED_EVOITEM'], 'B', 0); poke(T['EVOLUTION_TARGET'], '<h', t); poke(T['PARTNER_STATE'], 'b', 13)
    emu('lua', 'PCSX.resumeEmulator() return 1')
    t0 = time.time(); seen = False
    while time.time() - t0 < 420:
        time.sleep(3); st = struct.unpack('b', peek(T['PARTNER_STATE'], 1))[0]
        if st == 13: seen = True
        if seen and st != 13: break
    time.sleep(2)
    return g, dict(type=get('partner.type'), hp=get('partner.stats.hp'), mp=get('partner.stats.mp'), off=get('partner.stats.off'), de=get('partner.stats.def'),
                   speed=get('partner.stats.speed'), brain=get('partner.stats.brain'), weight=get('partner.para.weight'), care=get('partner.para.careMistakes'),
                   battles=get('partner.para.battles'), life=get('partner.para.remainingLifetime'))
def blend(stat, gain): return stat + gain // 10 if stat >= gain else (gain + stat) // 2
for t in (5, 12, 6, 2):
    g, r = run(t, 0)
    scales = t in (11, 39, 53, 6) or level(t) < 3
    if scales: want = [PRE[k] * g[5] // 10 for k in ('hp', 'mp', 'off', 'de', 'speed', 'brain')]
    else: want = [blend(PRE[k], x) for k, x in zip(('hp', 'mp', 'off', 'de', 'speed', 'brain'), g[:6])]
    ok(f'evolution into {t} (level {level(t)}, {"scaled" if scales else "blended"}): the six stats', [r[k] for k in ('hp', 'mp', 'off', 'de', 'speed', 'brain')], want)
    ok(f'evolution into {t}: became {g[6]}', r['type'], g[6])
    ok(f'evolution into {t}: weight, care mistakes, battles reset', (r['care'], r['battles']), (0, 0))
    ok(f'evolution into {t}: lifetime{" +96" if level(t) == 5 else " unchanged"}', r['life'] - 1000 >= (96 - 8 if level(t) == 5 else -8) and r['life'] - 1000 <= (96 if level(t) == 5 else 0), True)
g, r = run(12, 1)
ok('table wiped: the stats stay', [r[k] for k in ('hp', 'mp', 'off', 'de', 'speed', 'brain')], [PRE[k] for k in ('hp', 'mp', 'off', 'de', 'speed', 'brain')])
ok('table wiped: they still reset (resetPartnerPara does it too, original code)', (r['care'], r['battles']), (0, 0))
ok('table wiped: the game is still running (partner state)', struct.unpack('b', peek(T['PARTNER_STATE'], 1))[0] != 13, True)
PY
tools/dev/emulator.py stop >/dev/null
