#!/usr/bin/env bash
# gym_award.sh: patch 0134 in the emulator (disc build/full.cue), the gym code that runs in the TRN overlay. In the first gym's screen (112) the training library is
# loaded and TRN_awardHpTrainingGains / TRN_awardOffenseTrainingGains / TRN_awardMpTrainingGains are called with known arguments: the stats gained (STATS_GAINS)
# and what the session costs (tiredness, energy, happiness) are compared with the rows of content/tables/training-gains.json, with the multiplier the game
# computes (TRN_calculateTrainingMultiplier). Then MOD_TRAIN_GAIN wiped in RAM: nothing is gained and nothing is spent.
set -u
cd "$(dirname "$0")/../../.."
export EMU_PORT=38125 EMU_ARGS="-interpreter -debugger"
DISC=${DISC:-build/full.cue}
mkdir -p build/savedrop; cp build/ids-saved.mcd build/savedrop/g.mcd
tools/dev/emulator.py start $DISC --card build/savedrop/g.mcd >/dev/null
tools/dev/emulator.py seq tools/dev/sequences/continue.seq >/dev/null; tools/dev/emulator.py wait 30 >/dev/null
tools/dev/emulator.py save build/savedrop/g.state >/dev/null
python3 -u - <<'PY'
import json, os, re, struct, subprocess, sys, time
sys.path.insert(0, 'tools'); from tools.dev import symbols as dwsyms
T = dwsyms.table(os.environ.get('DW_SYMS', 'disc-full'))
G = json.load(open('content/tables/training-gains.json'))['trainGain']
def emu(*a): return subprocess.run([sys.executable, 'tools/dev/emulator.py', *a], capture_output=True, text=True).stdout
def poke(addr, fmt, *v): emu('poke', hex(addr), struct.pack(fmt, *v).hex())
def peek(addr, n): return bytes.fromhex(''.join(l.split(None, 1)[1].replace(' ', '') for l in emu('peek', hex(addr), str(n)).strip().split('\n')))
def gs(**kw): subprocess.run([sys.executable, 'tools/dev/game_state.py', 'set', *[f'{k}={v}' for k, v in kw.items()]], capture_output=True)
def get(f): return int(subprocess.run([sys.executable, 'tools/dev/game_state.py', 'show', f], capture_output=True, text=True).stdout.strip().split()[-1], 0)
def ok(name, got, want): print(f'{"ok " if got == want else "BAD"} {name:66s} got {got} expected {want}', flush=True)
def callfn(*exprs):
    p = subprocess.Popen([sys.executable, 'tools/dev/playtest/call_function.py', *exprs], env=dict(os.environ, CALLFN_PAUSE='1'), stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    time.sleep(2.0); emu('lua', 'PCSX.resumeEmulator() return 1'); out = p.communicate(timeout=200)[0]; return out
def num(out, name): return int(re.findall(rf'{name}\(.*?\) = (-?\d+)', out)[-1])
IDX = {'hp': 0, 'mp': 1, 'off': 2, 'def': 3, 'spd': 4, 'brain': 5}
FN = {'hp': 'TRN_awardHpTrainingGains', 'mp': 'TRN_awardMpTrainingGains', 'off': 'TRN_awardOffenseTrainingGains', 'def': 'TRN_awardDefenseTrainingGains', 'spd': 'TRN_awardSpeedTrainingGains'}
def session(gym, slot, wiped):
    emu('load', 'build/savedrop/g.state'); emu('lua', 'PCSX.pauseEmulator() return 1')
    subprocess.run([sys.executable, 'tools/dev/game_state.py', 'warp', '112', '0'], capture_output=True)
    emu('lua', 'PCSX.resumeEmulator() return 1'); time.sleep(8)
    callfn('loadTrainingLibrary(112)'); emu('wait', '10')
    emu('lua', 'PCSX.pauseEmulator() return 1')
    if wiped:
        for i in range(16 * 11): poke(T['MOD_TRAIN_GAIN'] + 2 * i, '<h', -1)
    gs(**{'partner.para.tiredness': 0, 'partner.para.energyLevel': 900, 'partner.para.happiness': 50, 'partner.para.discipline': 50, 'partner.para.trainBoostFlag': 0})
    ty = get('partner.type')
    out = callfn(f'TRN_calculateTrainingMultiplier({ty},0,{slot})', f'{FN[gym]}({ty},{slot},10)')
    v = num(out, 'TRN_calculateTrainingMultiplier')
    return v, struct.unpack('<6h', peek(T['STATS_GAINS'], 12)), get('partner.para.tiredness'), get('partner.para.happiness')
for r in [r for r in G if r['gym'] in FN]:
    gym, slot = r['gym'], (0 if r['slot'] == 'any' else r['slot']); tag = f'gym {gym} slot {r["slot"]}'
    v, g, tired, happy = session(gym, slot, 0)
    want = [0] * 6
    for k, i in IDX.items(): want[i] = (r.get(k, 0) * v // 10) * 10 // 10
    ok(f'{tag}: stats gained = row x multiplier ({v})', list(g), want)
    ok(f'{tag}: tiredness +{r["tired"]}, happiness -{r["happy"]}', (tired, happy), (r['tired'], 50 - r['happy']))
    if slot == 0:
        v, g, tired, happy = session(gym, slot, 1)
        ok(f'{tag}, table wiped: nothing gained, nothing spent', (list(g), tired, happy), ([0] * 6, 0, 50))
PY
tools/dev/emulator.py stop >/dev/null
