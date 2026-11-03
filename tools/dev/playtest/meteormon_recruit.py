#!/usr/bin/env python3
"""Play Meteormon's talk and fight (screen 86, section 5) with a chosen partner and choice, on original 2 MB RAM.

Choice 0 is "Touch and check it!", choice 1 is "Smash it open!" (the partner walks to Meteormon and attacks). The fight is
shortened by setting the opponent's HP to 0. The run passes when the scene ends with trigger 313 set and the world gives
control back; it fails when the script stops moving for --stall seconds while the pad keeps confirming.

--nudge N reproduces the freeze: when the walk away is started again after it ended, Meteormon is left N units short
of the point, the step works out to 0 and `await` never ends (the original script hangs, MOVE_TO_DELTA stays 0, 0).
--fixed patches the loaded script in RAM with the one change the fixed script lowers to, for a disc built without it.
"""
from pathlib import Path
import argparse
import json
import struct
import sys
import time

ROOT = Path(__file__).resolve().parents[3]
sys.path[:0] = [str(ROOT), str(ROOT / 'tools')]
from tools.dev.saves.releases import Emu
from tools.dev.playtest.airdramon_timeout import native_card
from tools.langpatch import elf_symbols

METEORMON, TRIGGER = 113, 313


def snapshot(e):
    ram = e.ram()
    r = {n: e.peek(n, fmt, ram) for n, fmt in (
        ('ACTIVE_INSTRUCTION', 'B'), ('WAIT_FOR_ENTITY_ID', 'B'), ('SCRIPT_SECTION', 'H'), ('SCRIPT_POINTER', 'I'),
        ('CURRENT_SCREEN', 'h'), ('IS_SCRIPT_PAUSED', 'i'), ('GAME_STATE', 'H'), ('TAMER_STATE', 'B'))}
    for name in ('TAMER_ENTITY', 'PARTNER_ENTITY'):
        pos = e.peek(name + '+4', 'I', ram) - 0x80000000
        r[name] = dict(type=e.peek(name, 'i', ram), position=list(struct.unpack_from('<3i', ram, pos + 0x78)),
                       frame=e.peek(name + '+0x1c', 'h', ram), frames=e.peek(name + '+0x1e', 'h', ram),
                       animation=e.peek(name + '+0x2e', 'B', ram))
    r['trigger'] = bool(ram[e.A('SCRIPT_STATE') - 0x80000000 + 245 + TRIGGER // 8] & (1 << (TRIGGER % 8)))
    r['move'] = [e.peek(n, f, ram) for n, f in (('MOVE_TO_DELTA_X', 'i'), ('MOVE_TO_DELTA_Z', 'i'), ('PREVIOUS_CAMERA_POS_INITIALIZED', 'b'))]
    r['npcs'] = {}
    for i in range(2, 12):
        ent = e.peek(f'ENTITY_TABLE+{i * 4}', 'I', ram)
        if 0x80000000 <= ent < 0x801ffff0:
            r['npcs'][i] = (struct.unpack_from('<i', ram, ent - 0x80000000)[0], ent)
            if r['npcs'][i][0] == METEORMON:
                pd = struct.unpack_from('<I', ram, ent - 0x80000000 + 4)[0] - 0x80000000
                r['meteormon'] = [struct.unpack_from('<i', ram, pd + 0x78)[0], struct.unpack_from('<i', ram, pd + 0x80)[0], struct.unpack_from('<B', ram, ent - 0x80000000 + 0x2e)[0]]
    return r


def npc_position(e, snap):
    ram = e.ram()
    for i, (t, ent) in snap['npcs'].items():
        if t == METEORMON:
            pos = struct.unpack_from('<I', ram, ent - 0x80000000 + 4)[0] - 0x80000000
            return struct.unpack_from('<3i', ram, pos + 0x78), ent
    return None, None


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('disc')
    p.add_argument('--exe', required=True)
    p.add_argument('--card', default='tools/dev/saves/corpus/20261027-d2796814.mcd')
    p.add_argument('--partner', type=int, default=3)
    p.add_argument('--choice', type=int, default=1)
    p.add_argument('--port', type=int, default=40141)
    p.add_argument('--stall', type=int, default=60)
    p.add_argument('--out', type=Path, default=Path('build/meteormon-test'))
    p.add_argument('--lose', action='store_true', help='the partner is the one that falls in the fight')
    p.add_argument('--nudge', type=int, default=None, help='when a later entity_move_to starts, leave Meteormon this many units short of x=1 (the hang the loop can reach)')
    p.add_argument('--fixed', action='store_true', help='patch the loaded script in RAM with the fixed loop (the build of a disc with the fix is slow)')
    p.add_argument('--partner-only', action='store_true', help='stop after the walk and attack, before the fight')
    a = p.parse_args()
    a.out.mkdir(parents=True, exist_ok=True)
    card = native_card(a.card, a.out / 'test.mcd', tamer_position=(1500, 0, -1450), partner_type=a.partner)
    e = Emu(a.disc, a.exe, a.port, str(a.out / 'emu'))
    for name, (address, _, _) in elf_symbols(e.exe + '.elf').items():
        e.table.setdefault(name, address)
    e.env['EMU_ARGS'] = '-interpreter -debugger'
    def ram():
        data = e.api('/api/v1/cpu/ram/raw')
        assert len(data) == 0x200000, 'requires original 2 MB RAM'
        return data
    e.ram = ram
    result = dict(partner=a.partner, choice=a.choice, samples=[])
    try:
        e.start(card)
        assert e.continue_game() == 0, 'Continue failed'
        e.wait(8)
        assert e.in_control(), 'no field control'
        e.gs('set', 'gametime_running=0')
        e.gs('trigger', str(TRIGGER), '0')
        assert e.warp(86), 'warp to 86 failed'
        assert e.in_control(), 'no control after the warp'
        snap = snapshot(e)
        mpos, ment = npc_position(e, snap)
        print('meteormon', mpos, 'tamer', snap['TAMER_ENTITY'], 'partner', snap['PARTNER_ENTITY']['type'], flush=True)
        assert mpos, 'Meteormon is not on the screen'
        if a.nudge is not None:
            e.run('lua', f"""
if MN and MN.bp then MN.bp:remove() end
MN={{n=0}}
local m=PCSX.getMemPtr()
local function u8(x) return tonumber(m[x-0x80000000]) end
local function u32(x) return u8(x)+256*u8(x+1)+65536*u8(x+2)+16777216*u8(x+3) end
local function s32(x) local v=u32(x) if v>=2147483648 then v=v-4294967296 end return v end
local function w32(x,v) v=v%4294967296 for i=0,3 do m[x-0x80000000+i]=v%256 v=math.floor(v/256) end end
MN.bp=PCSX.addBreakpoint({e.A('tickEntityMoveTo')},'Exec',4,'mn-nudge',function()
  if u8({e.A('PREVIOUS_CAMERA_POS_INITIALIZED')})~=0 then return end
  local ent=u32({e.A('ENTITY_TABLE')}+8)
  if ent<0x80000000 then return end
  local pd=u32(ent+4)
  local x=s32(pd+0x78)
  if math.abs(x-1)<60 then MN.n=MN.n+1; w32(pd+0x78,1-{a.nudge}); w32(pd+0x80,-1050-{a.nudge}) end
end)
return 'ok'
""")
        # choose in the dialogue as the player would
        e.run('lua', f"""
if MT and MT.bp then MT.bp:remove() end
MT={{}}
local m=PCSX.getMemPtr()
local function w8(a,v) m[a-0x80000000]=v%256 end
local function w16(a,v) w8(a,v);w8(a+1,math.floor(v/256)) end
MT.bp=PCSX.addBreakpoint({e.A('tickSelectionDialogue')},'Exec',4,'mt-choice',function() w16({e.A('DIALOGUE_SELECTION')}+10,{a.choice}) end)
return 'ok'
""")
        # approach: stand below-right of him and push toward him while tapping confirm
        sx, sz = mpos[0], mpos[2]
        BUT = ['UP', 'DOWN', 'LEFT', 'RIGHT']
        def release_all():
            for b in BUT + ['CROSS', 'CIRCLE', 'TRIANGLE']:
                e.api(f'/api/v1/lua/release?button={b}')
        release_all()
        def pos():
            return snapshot(e)['TAMER_ENTITY']['position']
        def hold(btn, secs):
            e.api(f'/api/v1/lua/press?button={btn}')
            try:
                e.wait(secs)
            finally:
                e.api(f'/api/v1/lua/release?button={btn}')
        vec = dict(UP=(0, 1), DOWN=(0, -1), LEFT=(-1, 0), RIGHT=(1, 0))          # the pad on screen 86, measured
        def best(dx, dz):
            return max(BUT, key=lambda b: vec[b][0] * dx + vec[b][1] * dz)
        started = False
        for step in range(60):
            s = snapshot(e)
            if s['SCRIPT_SECTION'] == 5 and s['IS_SCRIPT_PAUSED'] != 1:
                started = True
                break
            assert s['CURRENT_SCREEN'] == 86, 'walked off the screen'
            px, _, pz = s['TAMER_ENTITY']['position']
            dx, dz = sx - px, sz - pz
            if s['IS_SCRIPT_PAUSED'] != 1:            # an event tile or a partner comment: confirm it away
                e.press('CONFIRM', 4); e.wait(.5); continue
            # first line up on the axis of the smaller gap, then walk into him
            along = best(0, 1 if dz > 0 else -1) if abs(dx) < 120 else best(1 if dx > 0 else -1, 0)
            hold(along, .25 if abs(dx) < 120 else .35)
            e.press('CONFIRM', 4)
            print('walk', along, (px, pz), '->', (sx, sz), s['SCRIPT_SECTION'], flush=True)
        if a.fixed:
            # the same single change the fixed script lowers to: the loop's jump goes back to its test, not to the walk
            # in front of it (the walk is an 8-byte instruction); the script is in RAM once the talk has started
            ram_ = e.ram()
            walk = bytes.fromhex('6c050100e6fb2800')
            end = bytes.fromhex('4c00fc051600')
            at, jump = ram_.find(walk), ram_.find(end)
            assert at >= 0 and jump >= 0 and ram_.find(walk, at + 1) < 0 and ram_.find(end, jump + 1) < 0, 'the loop is not in RAM exactly once'
            target = struct.unpack_from('<H', ram_, jump + 6)[0]
            e.run('poke', hex(0x80000000 + jump + 6), struct.pack('<H', target + 8).hex())
            print('patched the loop jump', hex(target), '->', hex(target + 8), flush=True)
        result['approach'] = [started, snapshot(e)]
        assert started, 'could not start the talk'
        last, same, battle_seen = None, 0, False
        t0 = time.time()
        for tick in range(2000):
            row = snapshot(e)
            row['t'] = round(time.time() - t0, 1)
            result['samples'].append(row)
            key = (row['SCRIPT_POINTER'], row['ACTIVE_INSTRUCTION'], row['GAME_STATE'], row['PARTNER_ENTITY']['animation'],
                   row['PARTNER_ENTITY']['frame'], tuple(row['PARTNER_ENTITY']['position']), tuple(row['TAMER_ENTITY']['position']),
                   row['TAMER_ENTITY']['frame'])
            same = same + 1 if key == last else 0
            last = key
            if tick % 8 == 0:
                print(row['t'], {k: row[k] for k in ('SCRIPT_SECTION', 'SCRIPT_POINTER', 'ACTIVE_INSTRUCTION', 'WAIT_FOR_ENTITY_ID', 'GAME_STATE', 'IS_SCRIPT_PAUSED')},
                      'partner', row['PARTNER_ENTITY']['animation'], row['PARTNER_ENTITY']['position'], 'met', row.get('meteormon'), 'mv', row['move'], flush=True)
            if row['GAME_STATE'] == 1:
                battle_seen = True
                ram_ = e.ram()
                for i in range(1 if a.lose else 2, 12):
                    ent = e.peek(f'ENTITY_TABLE+{i * 4}', 'I', ram_)
                    if not 0x80000000 <= ent < 0x801ffff0:
                        continue
                    kind = struct.unpack_from('<i', ram_, ent - 0x80000000)[0]
                    if (kind == a.partner) if a.lose else (kind == METEORMON):
                        e.run('poke', hex(ent + 76), '0000')
            if row['trigger'] and row['IS_SCRIPT_PAUSED'] == 1 and row['TAMER_STATE'] == 0:
                result['ok'] = True
                break
            if same >= a.stall * 2:
                result['stalled'] = True
                print('STALL', row, flush=True)
                break
            if row['GAME_STATE'] != 0:
                e.press(('SQUARE', 'CROSS', 'CIRCLE')[tick % 3], 6)     # FINISH!! wants SQUARE, the result panels CROSS
            else:
                e.press('CONFIRM', 4)
            e.wait(.4)
        result['battle_seen'] = battle_seen
        e.run('shot', str(a.out / 'final.png'), check=False)
        print('RESULT', 'OK' if result.get('ok') else 'STALLED' if result.get('stalled') else 'LIMIT', 'battle', battle_seen, flush=True)
    except BaseException as error:
        result['error'] = str(error)
        e.run('shot', str(a.out / 'failure.png'), check=False)
        raise
    finally:
        (a.out / 'result.json').write_text(json.dumps(result, indent=2, default=list) + '\n')
        e.stop()


if __name__ == '__main__':
    main()
