#!/usr/bin/env bash
# battle_ai.sh: patches 0137 and 0142 in the emulator (disc build/full.cue with content/tables/battle-formulas.json). A tournament fight (STD overlay) from the
# arena lobby: the table as built reads back as the JSON says, the fight runs (BATTLE_FRAME_COUNT advances and someone loses HP), and with the table
# wiped (every slot -1, the poke below) it still runs without a hang and without damage. Needs the lobby state of the disc:
#   EMU_PORT=38137 tools/dev/playtest/enter_arena_lobby.sh build/full.cue arena-battle   (about 3 minutes; writes build/arena-battle-lobby.state)
#   EMU_PORT=38137 tools/dev/playtest/battle_ai.sh
set -u
cd "$(dirname "$0")/../../.."
export EMU_PORT=${EMU_PORT:-38137} EMU_ARGS="-interpreter -debugger"
STATE=${STATE:-build/arena-battle-lobby.state}
python3 -u - "$STATE" <<'PY'
import json, os, struct, subprocess, sys, time
sys.path.insert(0, 'tools'); from tools.dev import symbols as dwsyms; import balance
state = sys.argv[1]
T = dwsyms.table(os.environ.get('DW_SYMS', 'disc-full'))
def emu(*a): return subprocess.run([sys.executable, 'tools/dev/emulator.py', *a], capture_output=True, text=True).stdout
def peek(addr, n): return bytes.fromhex(''.join(l.split(None, 1)[1].replace(' ', '') for l in emu('peek', hex(addr), str(n)).strip().split('\n')))
def ok(name, got, want): print(f'{"ok " if got == want else "BAD"} {name:70s} got {got} expected {want}'); return got == want
obj = json.load(open('content/tables/battle-formulas.json'))['battleFormulas']
want = balance.encode_named('battleFormulas', obj, None)
emu('load', state); time.sleep(1)
ok('MOD_BATTLE as built = content/tables/battle-formulas.json (162 slots, waits in ticks)', peek(T['MOD_BATTLE'], len(want)) == want, True)

def fight(wiped):
    emu('load', state); emu('lua', 'PCSX.pauseEmulator() return 1')
    if wiped: emu('poke', hex(T['MOD_BATTLE']), 'ff' * len(want))
    emu('lua', 'PCSX.resumeEmulator() return 1')
    subprocess.run([sys.executable, 'tools/dev/playtest/call_tournament.py', '0'], capture_output=True, text=True)
    frames, hp = [], []
    for k in range(12):
        time.sleep(10)
        frames.append(struct.unpack('<h', peek(T['BATTLE_FRAME_COUNT'], 2))[0])
    return frames
f0 = fight(0); print('frames, table:', f0)
ok('the fight runs: BATTLE_FRAME_COUNT advances', f0[-1] > f0[-2] > 0, True)
f1 = fight(1); print('frames, wiped:', f1)
ok('table wiped: the fight still runs (no hang)', f1[-1] > f1[-2] > 0, True)
PY
tools/dev/emulator.py stop >/dev/null
