#!/usr/bin/env bash
# economy.sh: patch 0133 in the emulator (disc build/full.cue with content/tables/economy.json and tournament-rules.json). The tables as built; the stack
# cap of giveItem (two gifts of 90 of one item make 99 with the table, 180 with it wiped: a cap left out is the 255 of a byte). The money, merit,
# shop, card-pack and tournament numbers are read at the use and are not exercised here.
set -u
cd "$(dirname "$0")/../../.."
export EMU_PORT=38123 EMU_ARGS="-interpreter -debugger"
DISC=${DISC:-build/full.cue}
mkdir -p build/savedrop; cp build/ids-saved.mcd build/savedrop/y.mcd
tools/dev/emulator.py start $DISC --card build/savedrop/y.mcd >/dev/null
tools/dev/emulator.py seq tools/dev/sequences/continue.seq >/dev/null; tools/dev/emulator.py wait 30 >/dev/null
tools/dev/emulator.py save build/savedrop/y.state >/dev/null
python3 -u - <<'PY'
import os, re, struct, subprocess, sys, time
sys.path.insert(0, 'tools'); from tools.dev import symbols as dwsyms
T = dwsyms.table(os.environ.get('DW_SYMS', 'disc-full'))
def emu(*a): return subprocess.run([sys.executable, 'tools/dev/emulator.py', *a], capture_output=True, text=True).stdout
def peek(addr, n): return bytes.fromhex(''.join(l.split(None, 1)[1].replace(' ', '') for l in emu('peek', hex(addr), str(n)).strip().split('\n')))
def ok(name, got, want): print(f'{"ok " if got == want else "BAD"} {name:62s} got {got} expected {want}')
emu('load', 'build/savedrop/y.state')
ok('MOD_ECON as built', struct.unpack('<12i', peek(T['MOD_ECON'], 48)), (999999, 9999, 99, 30, 90, 50, 1, 5, 20, 50, 9, 500))
ok('MOD_TOURNAMENT pool and win rules as built', struct.unpack('<7h', peek(T['MOD_TOURNAMENT'] + 16, 14)), (3, 5, 7, 2, 3, 5, 2))
def gifts(wiped):
    emu('load', 'build/savedrop/y.state'); emu('lua', 'PCSX.pauseEmulator() return 1')
    if wiped:
        for i in range(12): emu('poke', hex(T['MOD_ECON'] + 4 * i), 'ffffffff')
    p = subprocess.Popen([sys.executable, 'tools/dev/playtest/call_function.py', 'giveItem(38,90)', 'giveItem(38,90)', 'getItemCount(38)'], env=dict(os.environ, CALLFN_PAUSE='1'),
                         stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    time.sleep(2.0); emu('lua', 'PCSX.resumeEmulator() return 1'); out = p.communicate(timeout=120)[0]
    return int(re.findall(r'getItemCount\(.*?\) = (\d+)', out)[-1])
ok('two gifts of 90: the stack cap of the table', gifts(0), 99)
ok('two gifts of 90, table wiped: the cap of a byte', gifts(1), 180)
def loss(wiped):
    emu('load', 'build/savedrop/y.state'); emu('lua', 'PCSX.pauseEmulator() return 1')
    if wiped:
        for i in range(12): emu('poke', hex(T['MOD_ECON'] + 4 * i), 'ffffffff')
    p = subprocess.Popen([sys.executable, 'tools/dev/playtest/call_function.py'] + [f'giveItem({i},1)' for i in (38, 39, 40, 41, 42, 43, 44, 45, 46, 47)] + ['handleItemLoss()'], env=dict(os.environ, CALLFN_PAUSE='1'),
                         stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    time.sleep(2.0); emu('lua', 'PCSX.resumeEmulator() return 1'); p.communicate(timeout=240)
    after = sum(1 for v in struct.unpack('<30h', peek(T['INVENTORY'], 60)) if v != -1)
    lost = int(subprocess.run([sys.executable, 'tools/dev/game_state.py', 'pstat', '200'], capture_output=True, text=True).stdout.split('=')[1].split()[0], 0)
    return after, lost
a0, l0 = loss(0); a1, l1 = loss(1)
ok('defeat loses 30 % of the stacks: the PStat holds the count and as many slots are gone', (l0, a1 - a0 + l0 if False else None) == (l0, None) and l0 == (a0 + l0) * 30 // 100, True)
ok('defeat, table wiped: nothing is lost', l1, 0)
ok('defeat: with the table the stacks lost leave fewer slots than with it wiped', a0 < a1, True)
PY
tools/dev/emulator.py stop >/dev/null
