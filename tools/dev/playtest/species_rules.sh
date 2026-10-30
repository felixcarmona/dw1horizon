#!/usr/bin/env bash
# species_rules.sh: patch 0142 in the emulator (disc build/full.cue with content/tables/species-rules.json). modModelScale and modAnimatedTextureWidth are
# called for the species of the original game's special cases (Meteormon 113 drawn at 150 %, the 9 flame species and their strip widths) and for others,
# once with the tables the build wrote and once with them wiped in RAM (every row -1: no species is special, scale 0x1000, no animated texture).
set -u
cd "$(dirname "$0")/../../.."
export EMU_PORT=${EMU_PORT:-38142} EMU_ARGS="-interpreter -debugger"
DISC=${DISC:-build/full.cue}
mkdir -p build/savedrop; cp build/ids-saved.mcd build/savedrop/sr.mcd
tools/dev/emulator.py start $DISC --card build/savedrop/sr.mcd >/dev/null
tools/dev/emulator.py seq tools/dev/sequences/continue.seq >/dev/null; tools/dev/emulator.py wait 30 >/dev/null
tools/dev/emulator.py save build/savedrop/sr.state >/dev/null
python3 -u - <<'PY'
import os, re, struct, subprocess, sys, time
sys.path.insert(0, 'tools'); from tools.dev import symbols as dwsyms
T = dwsyms.table(os.environ.get('DW_SYMS', 'disc-full'))
def emu(*a): return subprocess.run([sys.executable, 'tools/dev/emulator.py', *a], capture_output=True, text=True).stdout
def poke(addr, fmt, *v): emu('poke', hex(addr), struct.pack(fmt, *v).hex())
def peek(addr, n): return bytes.fromhex(''.join(l.split(None, 1)[1].replace(' ', '') for l in emu('peek', hex(addr), str(n)).strip().split('\n')))
def ok(name, got, want): print(f'{"ok " if got == want else "BAD"} {name:62s} got {got} expected {want}', flush=True)
FLAMES = {9: 30, 133: 30, 104: 30, 21: 40, 106: 40, 143: 40, 101: 16, 69: 16, 127: 44}
OTHERS = [0, 3, 8, 10, 22, 70, 100, 112, 114, 128, 160, 179, 180, 200]
def calls(wiped):
    emu('load', 'build/savedrop/sr.state'); emu('lua', 'PCSX.pauseEmulator() return 1')
    if wiped:
        poke(T['MOD_MODEL_SCALE'], '<16h', *[-1] * 16); poke(T['MOD_ANIM_TEXTURE'], '<32h', *[-1] * 32)
    exprs = [f'modModelScale({t})' for t in [113] + OTHERS] + [f'modAnimatedTextureWidth({t})' for t in list(FLAMES) + [113] + OTHERS]
    p = subprocess.Popen([sys.executable, 'tools/dev/playtest/call_function.py', *exprs], env=dict(os.environ, CALLFN_PAUSE='1'), stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    time.sleep(2.0); emu('lua', 'PCSX.resumeEmulator() return 1'); out = p.communicate(timeout=300)[0]
    vals = [int(x) for x in re.findall(r'\) = (\d+)', out)]; assert len(vals) == len(exprs), out
    return dict(zip(exprs, vals))
rows = peek(T['MOD_MODEL_SCALE'], 32), peek(T['MOD_ANIM_TEXTURE'], 64)
ok('MOD_MODEL_SCALE as built: row 0 = (113, 150), the rest empty', struct.unpack('<2h', rows[0][:4]) + (set(struct.unpack('<14h', rows[0][4:])),), (113, 150, {-1}))
ok('MOD_ANIM_TEXTURE as built: the 9 flame rows', {(a, b) for a, b in struct.iter_unpack('<2h', rows[1][:36])} == set(FLAMES.items()) and set(struct.unpack('<14h', rows[1][36:])) == {-1}, True)
r = calls(0)
ok('Meteormon (113) is drawn at 150 % = 0x1800', r['modModelScale(113)'], 0x1800)
ok('other species are drawn at 100 % = 0x1000', {r[f'modModelScale({t})'] for t in OTHERS}, {0x1000})
for t, w in FLAMES.items(): ok(f'species {t}: animated texture strip {w} wide', r[f'modAnimatedTextureWidth({t})'], w)
ok('other species (and 113) have no animated texture', {r[f'modAnimatedTextureWidth({t})'] for t in [113] + OTHERS}, {0})
r = calls(1)
ok('tables wiped: Meteormon is 0x1000 too', {r[f'modModelScale({t})'] for t in [113] + OTHERS}, {0x1000})
ok('tables wiped: no animated texture', {r[f'modAnimatedTextureWidth({t})'] for t in list(FLAMES) + [113] + OTHERS}, {0})
PY
tools/dev/emulator.py stop >/dev/null
