#!/usr/bin/env python3
"""Play Goblimon's real screen-36 script on an original-2-MB disc.

Seed foes at one HP, then let real attacks win. The flee case selects the
engine's flee command. Exercise first win, repeat win, flee and loss from one
field checkpoint. Observe the recruit write, jingle and narrator box in order.
"""
import argparse
import json
from pathlib import Path
import struct
import sys
import time

ROOT = Path(__file__).resolve().parents[3]
sys.path[:0] = [str(ROOT), str(ROOT / 'tools')]
from tools.dev.saves.releases import Emu
from tools.dev import memory_card as mcd
from tools.dev.playtest.airdramon_timeout import native_card
from tools.langpatch import elf_symbols


def site_card(source, target):
    """A private card at the real wild site, with both saved copies consistent."""
    native_card(source, target)
    card = mcd.Card(target)
    data = bytearray(card.read('BASLUS-01032DMR0'))
    size = 0x2000 if len(data) >= 0x6000 else 0x1000
    for i, base in enumerate((0x200, 0x1100)):
        payload = bytearray(data[base:base + 0xf00])
        payload[0x49a:0x49e] = bytes([36, 37, 0, 0])
        checksum = mcd.v1_checksum(payload) ^ 0xffffffff
        struct.pack_into('<I', payload, 0x4fc, checksum)
        data[base:base + 0xf00] = payload
        offset = 0x2000 + i * size
        head = bytearray(data[offset:offset + size])
        struct.pack_into('<I', head, 8, checksum)
        records = [(tag, struct.pack('<hh', 36, 37) if tag == 1 else value)
                   for tag, value in mcd.parse_records(head)]
        data[offset:offset + size] = mcd.build_extension(head, records, size)
    card.write('BASLUS-01032DMR0', 0, data)
    return target


def install(e, case):
    a = e.A
    data = Path(e.exe).with_name('BTL_REL.BIN').read_bytes()
    def loaded(name):
        words = struct.unpack_from('<8I', data, a(name) - a('btl_START'))
        return ' and '.join(f'u32({a(name)+4*i})=={word}' for i, word in enumerate(words))
    e.run('lua', f"""
if CR then for _, b in ipairs(CR.bp) do b:remove() end end
CR={{bp={{}},events={{}},entered=false,ended=false,scene=false,joined=false,jingle=false,seeded=false}}
local m=PCSX.getMemPtr()
local function u8(a) return tonumber(m[a-0x80000000]) end
local function u16(a) return u8(a)+256*u8(a+1) end
local function u32(a) return u16(a)+65536*u16(a+2) end
local function w8(a,v) m[a-0x80000000]=v%256 end
local function w16(a,v) w8(a,v);w8(a+1,math.floor(v/256)) end
local function hook(a,f) CR.bp[#CR.bp+1]=PCSX.addBreakpoint(a,'Exec',4,'city-test',f) end
local function event(s) CR.events[#CR.events+1]=s end
local function recruited() return math.floor(u8({a('SCRIPT_STATE')}+245+35)/1)%2==1 end
CR.wasRecruited=recruited()
hook({a('startBattle')},function() event('battle started') end)
hook({a('BTL_isBattleFinished')},function()
 if not ({loaded('BTL_isBattleFinished')}) then return end
 CR.entered=true
 local c=u32({a('COMBAT_DATA_PTR')})
 if c<0x80000000 then return end
 if '{case}'=='fled' then
  -- The command selected by the game's Run entry; handleCommands ticks it.
  w8(c+1614,1)
 elseif '{case}'=='lost' then
  if not CR.seeded then w16({a('PARTNER_ENTITY')}+76,1);CR.seeded=true;event('partner at one HP') end
 else
  do
   for i=1,u16({a('ENEMY_COUNT')}) do
    local slot=u8(c+1644+i)
    local entity=u32({a('ENTITY_TABLE')}+4*slot)
    if entity>=0x80000000 then
     if not CR.seeded then event('foe type '..u32(entity)) end
     if u16(entity+76)>1 then w16(entity+76,1) end
    end
   end
   if not CR.seeded then CR.seeded=true;event('foes at one HP') end
  end
 end
end)
hook({a('BTL_deinitializeCombat')},function()
 if not ({loaded('BTL_deinitializeCombat')}) then return end
 CR.ended=true;event('battle ended')
end)
hook({a('setTrigger')},function()
 if PCSX.getRegisters().GPR.n.a0==280 and not CR.wasRecruited then
  CR.joined=true;event('recruit flag; battle ended='..tostring(CR.ended))
 end
end)
hook({a('playSound')},function()
 local r=PCSX.getRegisters()
 if r.GPR.n.a0==8 and r.GPR.n.a1==11 and not CR.wasRecruited and recruited() then
  CR.jingle=true;event('join jingle')
 end
end)
hook({a('showTextbox')},function()
 local r=PCSX.getRegisters()
 if not CR.wasRecruited and recruited() and r.GPR.n.a1==255 then
  if not CR.joined then CR.joined=true;event('recruit flag observed; battle ended='..tostring(CR.ended)) end
  CR.scene=true;event('narrator join box')
 end
end)
-- Enter the real screen's real wild handler at a frame boundary. The field
-- still owns the NPC, battle selection and all postbattle script execution.
CR.call=0
hook({a('gameLoop')},function()
 local r=PCSX.getRegisters()
 if CR.call==1 then r.GPR.n.ra=CR.ra;CR.call=2;return end
 if CR.call==0 then
  CR.ra=r.GPR.n.ra;r.GPR.n.a0=36;r.GPR.n.a1=5;r.GPR.n.a2=0
  r.GPR.n.ra={a('gameLoop')};r.pc={a('callScriptSection')};CR.call=1
 end
end)
return 'installed'
""")


def state(e):
    ram = e.ram()
    flag = ram[e.A('SCRIPT_STATE') - 0x80000000 + 245 + 280 // 8] & (1 << (280 % 8))
    fields = e.run('lua', "return table.concat({tostring(CR.entered),tostring(CR.ended),tostring(CR.joined),tostring(CR.jingle),tostring(CR.scene)},',')").strip().split(',')
    result = dict(zip(('entered', 'ended', 'joined', 'jingle', 'scene'), [x == 'true' for x in fields]))
    result.update(flag=bool(flag), screen=e.peek('CURRENT_SCREEN', 'h', ram),
                  game=e.peek('GAME_STATE', 'H', ram),
                  paused=e.peek('IS_SCRIPT_PAUSED', 'i', ram),
                  outcome=ram[e.A('SCRIPT_STATE') - 0x80000000 + 345 + 255], ram_bytes=len(ram))
    return result


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('disc')
    p.add_argument('--exe', required=True)
    p.add_argument('--port', type=int, default=39153)
    p.add_argument('--out', type=Path, default=Path('build/city-recruitment-proof'))
    p.add_argument('--field-state', type=Path, help='reuse a field state from this exact disc and card')
    p.add_argument('--card', type=Path, default=ROOT / 'tools/dev/saves/corpus/20261027-d2796814.mcd')
    args = p.parse_args()
    out = args.out.resolve(); out.mkdir(parents=True, exist_ok=True)
    e = Emu(args.disc, args.exe, args.port, str(out / 'emu'))
    for name, (address, _, _) in elf_symbols(args.exe + '.elf').items():
        e.table.setdefault(name, address)
    e.env['EMU_ARGS'] = '-interpreter -debugger'
    results = {}
    try:
        card = site_card(args.card, out / 'native.mcd')
        e.start(card)
        e.run('lua', f"""CR_MOV=PCSX.addBreakpoint({e.A('playMovie')},'Exec',4,'city-skip-intro',function()
 PCSX.getRegisters().GPR.n.a1=0
end)""")
        if args.field_state:
            e.run('load', str(args.field_state.resolve())); e.run('lua', 'PCSX.resumeEmulator()')
        else:
            continued = e.continue_game()
            assert continued == 0, continued
            e.wait(8)
        e.poke('MOD_OPT_STORY', struct.pack('<i', 1))
        e.gs('set', 'partner.para.age=1', 'partner.para.evoTimer=0', 'partner.para.condition=0',
             'partner.para.foodLevel=100', 'partner.para.remainingLifetime=1000')
        e.gs('trigger', '280', '0')
        assert e.warp(36), 'warp to real wild site failed'
        e.wait(2)
        assert e.in_control(), 'not in control on screen 36'
        e.run('save', str(out / 'field.state'))
        print('booted and continued; real screen 36, original 2 MB', flush=True)
        for case in ('won', 'repeat', 'fled', 'lost'):
            checkpoint = out / ('repeat.state' if case == 'repeat' else 'field.state')
            e.run('load', str(checkpoint)); e.run('lua', 'PCSX.resumeEmulator()')
            e.gs('set', 'partner.stats.off=900', 'partner.stats.def=900',
                 'partner.stats.speed=900', 'partner.stats.brain=900',
                 'partner.para.discipline=100', 'gametime_running=0')
            if case == 'lost':
                e.gs('set', 'partner.stats.off=1', 'partner.stats.def=1', 'partner.stats.speed=1')
            e.gs('approach', '0')
            e.poke('TALKED_TO_ENTITY', bytes([2]))  # physical slot 2 = placed NPC 0
            install(e, case)
            deadline = time.monotonic() + 240
            while time.monotonic() < deadline:
                s = state(e)
                if case == 'won' and s['scene']:
                    e.wait(1.5)
                    e.run('shot', str(out / 'goblimon-joined.png'))
                    e.run('save', str(out / 'joined.state'))
                    break
                if case != 'won' and s['ended'] and s['game'] == 0 and s['paused'] == 1:
                    break
                if s['game'] != 1: e.press('CONFIRM', 6)
                e.wait(.35)
            else:
                raise AssertionError(f'{case}: battle did not finish: {s}')
            s = state(e)
            s['events'] = e.run('lua', "return table.concat(CR.events,'\\n')").strip().splitlines()
            results[case] = s
            (out / 'result.json').write_text(json.dumps(results, indent=2) + '\n')
            assert s['entered'] and s['ended'], s
            if case in ('won', 'repeat'): assert 'foe type 80' in s['events'], s
            if case == 'won':
                assert s['flag'] and s['joined'] and s['jingle'] and s['scene'] and s['outcome'] == 1, s
            else:
                assert s['flag'] == (case == 'repeat') and not s['joined'] and not s['scene'] and not s['jingle'], s
                assert s['outcome'] == {'repeat': 1, 'fled': 0, 'lost': 255}[case], s
            print(f'PASS {case}: {s}', flush=True)
            if case == 'won':
                e.press('CONFIRM', 8); e.wait(1)
                assert e.in_control(), 'join scene did not return control'
                assert e.warp(37) and e.warp(36), 'repeat encounter did not respawn'
                e.run('save', str(out / 'repeat.state'))
        print('PASS: first win joins visibly; repeat, flee and loss show no join scene', flush=True)
    except Exception:
        e.run('shot', str(out / 'failure.png'), check=False)
        raise
    finally:
        e.stop()


if __name__ == '__main__':
    main()
