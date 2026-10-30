#!/usr/bin/env bash
# last_battle_music.sh: patch 0142 in the emulator (disc build/full.cue, battle-formulas.json music.lastBattleSpecies 115, lastBattleTrack 3).
# loadBattleData(entityId, count) (btl.c, the start of every story and wild fight) is called from the world with the first enemy of the fight
# (COMBAT_DATA_PTR->player.entityIds[1], the field the rule reads) being a stand-in entity of a chosen species, and the call of playMusic is caught
# (font and track). The enemy species 115 (Machinedramon) must play track 3 of font 0x21; any other plays its own track from SPECIES_BATTLE_MUSIC (1 or 2),
# a predefined (story) battle of another species plays 0; with MOD_BATTLE wiped (every slot -1) or only the two music slots wiped, species 115 plays like the others;
# lastBattleTrack changed to 2 / lastBattleSpecies changed to 70 follow the table. About 2 minutes.
#   tools/dev/playtest/last_battle_music.sh
set -u
cd "$(dirname "$0")/../../.."
export EMU_PORT=${EMU_PORT:-38202} EMU_ARGS="-interpreter -debugger"
DISC=${DISC:-build/full.cue}
mkdir -p build/savedrop; cp build/ids-saved.mcd build/savedrop/lm.mcd
tools/dev/emulator.py start $DISC --card build/savedrop/lm.mcd >/dev/null
tools/dev/emulator.py seq tools/dev/sequences/continue.seq >/dev/null; tools/dev/emulator.py seq 'until CURRENT_SCREEN 1 218 CROSS 40, wait 5' >/dev/null
tools/dev/emulator.py save build/savedrop/lm.state >/dev/null
python3 -u - <<'PY'
import json, os, struct, subprocess, sys, time
sys.path.insert(0, 'tools'); from tools.dev import symbols as dwsyms; import balance
T = dwsyms.table(os.environ.get('DW_SYMS', 'disc-full'))
def emu(*a): return subprocess.run([sys.executable, 'tools/dev/emulator.py', *a], capture_output=True, text=True).stdout
def poke(addr, fmt, *v): emu('poke', hex(addr), struct.pack(fmt, *v).hex())
def peek(addr, n): return bytes.fromhex(''.join(l.split(None, 1)[1].replace(' ', '') for l in emu('peek', hex(addr), str(n)).strip().split('\n')))
def ok(name, got, want): print(f'{"ok " if got == want else "BAD"} {name:84s} got {got} expected {want}', flush=True)
obj = json.load(open('content/tables/battle-formulas.json'))['battleFormulas']
names = list(balance.NAMED_RULES['battleFormulas']) if hasattr(balance, 'NAMED_RULES') else None
SLOT = {k: i for i, k in enumerate(['music.lastBattleSpecies', 'music.lastBattleTrack'])}
want = balance.encode_named('battleFormulas', obj, None)
n = len(want) // 2
# the two music slots are the last two of the table
SP, TR = T['MOD_BATTLE'] + 2 * (n - 2), T['MOD_BATTLE'] + 2 * (n - 1)
ENTITY_IDS = struct.unpack('<I', struct.pack('<I', T['COMBAT_DATA'] + 1644))[0]      # COMBAT_DATA.player.entityIds (1440 + 204)
ENEMY = 9
def play(species, wipe=None, predefined=0, set_=None):
    """wipe: 'all' | 'music' | None; set_: (species, track) to put into the two slots"""
    emu('load', 'build/savedrop/lm.state'); emu('lua', 'PCSX.pauseEmulator() return 1')
    if wipe == 'all': poke(T['MOD_BATTLE'], f'{n}h', *[-1] * n)
    if wipe == 'music': poke(SP, '<2h', -1, -1)
    if set_: poke(SP, '<2h', *set_)
    scratch = T['COMBAT_DATA'] + 0x40                              # unused outside a fight (the table1 of fighter 0): a stand-in entity whose only field read is its type (word 0)
    poke(scratch, '<I', species)
    poke(T['ENTITY_TABLE'] + 4 * ENEMY, '<I', scratch)            # entity 9: empty in the world
    poke(T['COMBAT_DATA'] + 1644, '4B', 1, ENEMY, 0, 0); poke(T['COMBAT_DATA_PTR'], '<I', T['COMBAT_DATA'])
    poke(T['IS_PREDEFINED_BATTLE'], 'B', predefined)
    poke(T['CURRENT_SEQ_TRACK'], '<2h', -1, -1)                    # font and track: what playMusic leaves
    # loadBattleData calls playMusic first and loadDynamicLibrary(BTL_REL) next: the emulator pauses there, with the track set
    emu('lua', f"""if LMBP then LMBP:remove() end
LMBP = PCSX.addBreakpoint({T['loadDynamicLibrary']}, 'Exec', 4, 'lm', function() PCSX.pauseEmulator() end) return 'armed'""")
    p = subprocess.Popen([sys.executable, 'tools/dev/playtest/call_function.py', 'loadBattleData(9, 1)'], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    time.sleep(2.0); emu('lua', 'PCSX.resumeEmulator() return 1')      # the arming needs the emulator to run; the call is made on the next frame
    for _ in range(60):
        time.sleep(0.5)
        if emu('status').find('"running":false') >= 0: break
    p.kill(); emu('lua', 'LMBP:remove() return 1')
    track, font = struct.unpack('<2h', peek(T['CURRENT_SEQ_TRACK'], 4))      # the two int16 are adjacent: track, then font
    return track if font == 0x21 else ('font', font, track)
rom = peek(T['SPECIES_BATTLE_MUSIC'], 200)
print('table as built: species 115 track', rom[115], '; samples', {s: rom[s] for s in (0, 3, 67, 70, 85, 100, 111)})
sp, tr = struct.unpack('<2h', peek(SP, 4))
ok('MOD_BATTLE music slots as built (115, 3)', (sp, tr), (115, 3))
others = [0, 3, 67, 70, 85, 100, 111, 114, 116]
ok('Machinedramon (115) as the first enemy: track 3', play(115), 3)
for s in others: ok(f'species {s} as the first enemy: its own track {rom[s]}', play(s), rom[s])
ok('Machinedramon in a predefined (story) fight: still track 3 (the rule comes first)', play(115, predefined=1), 3)
ok('species 70 in a predefined (story) fight: track 0', play(70, predefined=1), 0)
ok('whole MOD_BATTLE wiped: Machinedramon plays its own track', play(115, wipe='all'), rom[115])
ok('whole MOD_BATTLE wiped: species 70 its own track', play(70, wipe='all'), rom[70])
ok('music slots wiped: Machinedramon plays its own track', play(115, wipe='music'), rom[115])
ok('lastBattleTrack 2: Machinedramon plays 2', play(115, set_=(115, 2)), 2)
ok('lastBattleSpecies 70: species 70 plays track 3', play(70, set_=(70, 3)), 3)
ok('lastBattleSpecies 70: Machinedramon no longer special', play(115, set_=(70, 3)), rom[115])
PY
tools/dev/emulator.py stop >/dev/null
