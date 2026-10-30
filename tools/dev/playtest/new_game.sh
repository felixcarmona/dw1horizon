#!/usr/bin/env bash
# new_game.sh: patch 0128 in the emulator (disc build/full.cue with content/tables/new-game.json). initializeDefaultSavegame builds the
# save of a new game: its money, start time, first partner's lifetime and age and lives must be the file's. initializeClockData sets the
# clock the game boots with. Patch 0143 adds the exit, the partner type and the card shop's first stock of that save. Then the table wiped in RAM (a build
# without the file): everything is 0. The starting partners and the first script (main.c) are run by tools/dev/playtest/new_game_start.sh.
set -u
cd "$(dirname "$0")/../../.."
export EMU_PORT=38118 EMU_ARGS="-interpreter -debugger"
DISC=${DISC:-build/full.cue}
mkdir -p build/savedrop; cp build/ids-saved.mcd build/savedrop/n.mcd
tools/dev/emulator.py start $DISC --card build/savedrop/n.mcd >/dev/null
tools/dev/emulator.py seq tools/dev/sequences/continue.seq >/dev/null; tools/dev/emulator.py wait 30 >/dev/null
tools/dev/emulator.py save build/savedrop/n.state >/dev/null
python3 - <<'PY'
import os, subprocess, struct, sys, time
sys.path.insert(0, 'tools'); from tools.dev import symbols as dwsyms
T = dwsyms.table(os.environ.get('DW_SYMS', 'disc-full'))
def emu(*a): return subprocess.run([sys.executable, 'tools/dev/emulator.py', *a], capture_output=True, text=True).stdout
def poke(addr, fmt, *v): emu('poke', hex(addr), struct.pack(fmt, *v).hex())
def peek(addr, n): return bytes.fromhex(''.join(l.split(None, 1)[1].replace(' ', '') for l in emu('peek', hex(addr), str(n)).strip().split('\n')))
def call(expr):
    p = subprocess.Popen([sys.executable, 'tools/dev/playtest/call_function.py', expr], env=dict(os.environ, CALLFN_PAUSE='1'), stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    time.sleep(2.0); emu('lua', 'PCSX.resumeEmulator() return 1'); p.communicate()
def ok(name, got, want): print(f'{"ok " if got == want else "BAD"} {name:50s} got {got} expected {want}')
NG = T['MOD_NEWGAME']; P0 = T['SAVE_FILE'] + 0x200                  # the header is 0x200 bytes, then the first payload
def payload():
    b = peek(P0, 0x500)
    return dict(money=struct.unpack_from('<i', b, 436)[0], year=b[464], day=struct.unpack_from('<h', b, 466)[0], hour=struct.unpack_from('<h', b, 468)[0],
                minute=struct.unpack_from('<h', b, 470)[0], frame=struct.unpack_from('<H', b, 460)[0], handled=struct.unpack_from('<H', b, 462)[0],
                lives=b[1167], life=struct.unpack_from('<h', b, 552)[0], age=struct.unpack_from('<h', b, 554)[0])
def fresh(wiped):
    emu('load', 'build/savedrop/n.state'); emu('lua', 'PCSX.pauseEmulator() return 1')
    if wiped:
        for i in range(20): poke(NG + 4 * i, '<i', -1)
    else:                                                          # values that are not the original's, to see they come from the table
        for i, v in enumerate((12345, 21, 30, 111, 7, 5, 222, 33, 44, 5, 6, 7, 78, 1234, 201, 202, 203, 204, 205, 206)): poke(NG + 4 * i, '<i', v)
emu('load', 'build/savedrop/n.state')
ok('the table as the build wrote it', struct.unpack('<20i', peek(NG, 80)), (50000, 8, 0, 288, 3, 3, 360, 50, 50, 3, 17, 204, 9, 114, 58, 59, 60, 61, 62, 63))
fresh(0); call('initializeDefaultSavegame()'); p = payload()
ok('money', p['money'], 12345); ok('start hour / minute', (p['hour'], p['minute']), (21, 30))
ok('clock frame = hour x 1200 + minute x 20', (p['frame'], p['handled']), (21 * 1200 + 30 * 20,) * 2)
ok('first partner: lifetime / age', (p['life'], p['age']), (111, 7)); ok('lives', p['lives'], 5)
# the exit, the partner type and the card shop's six values: the bytes that change when those slots change (everything else stays)
def raw(): return peek(P0, 0xF00)
emu('load', 'build/savedrop/n.state'); emu('lua', 'PCSX.pauseEmulator() return 1')
for i, v in enumerate((50000, 8, 0, 288, 3, 3, 360, 50, 50, 3, 17, 204, 9, 114, 58, 59, 60, 61, 62, 63)): poke(NG + 4 * i, '<i', v)
call('initializeDefaultSavegame()'); base = raw()
fresh(0); call('initializeDefaultSavegame()'); alt = raw()
diff = [i for i in range(len(base)) if base[i] != alt[i]]
exitpos = [i for i in diff if alt[i] == 78 and base[i] == 9]; typepos = struct.unpack_from('<i', alt, 440)[0]; cards = [i for i in diff if alt[i] in range(201, 207)]
ok('the exit of the empty save is startExit', (len(exitpos), struct.unpack_from('<i', base, 440)[0], typepos), (1, 114, 1234))
ok('the card shop script state: six bytes 58.. then 201..', (bytes(base[cards[0]:cards[0] + 6]), bytes(alt[cards[0]:cards[0] + 6]), len(cards)), (bytes(range(58, 64)), bytes(range(201, 207)), 6))
fresh(0); call('initializeClockData()')
H = lambda s, f: struct.unpack(f, peek(T[s], struct.calcsize(f)))[0]
ok('boot clock: hour / minute / frame', (H('HOUR', '<h'), H('MINUTE', '<h'), H('CURRENT_FRAME', '<H')), (21, 30, 21 * 1200 + 30 * 20))
fresh(1); call('initializeDefaultSavegame()'); p = payload()
ok('table wiped: money / hour / minute', (p['money'], p['hour'], p['minute']), (0, 0, 0))
ok('table wiped: lifetime / age / lives', (p['life'], p['age'], p['lives']), (0, 0, 0))
b = raw(); ok('table wiped: exit, partner type, card shop state', (b[exitpos[0]], struct.unpack_from('<i', b, 440)[0], bytes(b[cards[0]:cards[0] + 6])), (0, 0, bytes(6)))
PY
tools/dev/emulator.py stop >/dev/null
