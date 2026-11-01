#!/usr/bin/env python3
"""Play the Motor-broken Birdramon recruit, loss retry and legacy save on 2 MB.

Foes are held at one HP for real attacks to win. No battle outcome or recruit
flag is injected. Each case restores a field checkpoint from the same disc.
"""
import argparse
import json
from pathlib import Path
import socket
import struct
import sys
import time

ROOT = Path(__file__).resolve().parents[3]
sys.path[:0] = [str(ROOT), str(ROOT / 'tools')]
from tools.dev.saves.releases import Emu
from tools.dev import memory_card as mcd
from tools.dev.playtest.airdramon_timeout import native_card
from tools.langpatch import elf_symbols


def field_card(source, target):
    """Start off the city door trigger, whose repeated handler prevents idle."""
    native_card(source, target)
    card = mcd.Card(target)
    data = bytearray(card.read('BASLUS-01032DMR0'))
    size = 0x2000 if len(data) >= 0x6000 else 0x1000
    for i, base in enumerate((0x200, 0x1100)):
        payload = bytearray(data[base:base + 0xf00])
        struct.pack_into('<3i', payload, 4, 1500, 0, -1450)
        struct.pack_into('<3i', payload, 20, 1200, 0, -1400)
        checksum = mcd.v1_checksum(payload) ^ 0xffffffff
        struct.pack_into('<I', payload, 0x4fc, checksum)
        data[base:base + 0xf00] = payload
        offset = 0x2000 + i * size
        head = bytearray(data[offset:offset + size])
        struct.pack_into('<I', head, 8, checksum)
        data[offset:offset + size] = mcd.build_extension(head, mcd.parse_records(head), size)
    card.write('BASLUS-01032DMR0', 0, data)
    return target


def bit(e, n, ram=None):
    ram = ram or e.ram()
    return bool(ram[e.A('SCRIPT_STATE') - 0x80000000 + 245 + n // 8] & (1 << (n % 8)))


def free_heap(e, ram):
    pointer = e.peek('_freep', 'I', ram)
    blocks = {}
    while pointer not in blocks:
        assert 0x80000000 <= pointer < 0x80200000
        following, units = struct.unpack_from('<II', ram, pointer - 0x80000000)
        blocks[pointer] = units * 8
        assert len(blocks) < 4096
        pointer = following
    return dict(free=sum(blocks.values()), largest=max(blocks.values()))


def install(e, case):
    a = e.A
    data = Path(e.exe).with_name('BTL_REL.BIN').read_bytes()
    def loaded(name):
        words = struct.unpack_from('<8I', data, a(name) - a('btl_START'))
        return ' and '.join(f'u32({a(name)+4*i})=={word}' for i, word in enumerate(words))
    e.run('lua', f"""
if BR then for _, b in ipairs(BR.bp) do b:remove() end end
BR={{bp={{}},events={{}},entered=false,ended=false,scene=false,joined=false,jingle=false,seeded=false}}
local m=PCSX.getMemPtr()
local function u8(a) return tonumber(m[a-0x80000000]) end
local function u16(a) return u8(a)+256*u8(a+1) end
local function u32(a) return u16(a)+65536*u16(a+2) end
local function w8(a,v) m[a-0x80000000]=v%256 end
local function w16(a,v) w8(a,v);w8(a+1,math.floor(v/256)) end
local function hook(a,f) BR.bp[#BR.bp+1]=PCSX.addBreakpoint(a,'Exec',4,'birdramon-test',f) end
local function event(s) BR.events[#BR.events+1]=s end
local function recruited() return math.floor(u8({a('SCRIPT_STATE')}+245+27)/32)%2==1 end
BR.wasRecruited=recruited()
hook({a('startBattle')},function() event('battle started') end)
hook({a('BTL_isBattleFinished')},function()
 if not ({loaded('BTL_isBattleFinished')}) then return end
 BR.entered=true
 local c=u32({a('COMBAT_DATA_PTR')})
 if c<0x80000000 then return end
 if '{case}'=='lost' then
  if not BR.seeded then w16({a('PARTNER_ENTITY')}+76,1);BR.seeded=true;event('partner at one HP') end
 else
  do
   for i=1,u16({a('ENEMY_COUNT')}) do
    local slot=u8(c+1644+i)
    local entity=u32({a('ENTITY_TABLE')}+4*slot)
    if entity>=0x80000000 then
     if not BR.seeded then event('foe type '..u32(entity)) end
     if u16(entity+76)>1 then w16(entity+76,1) end
    end
   end
   if not BR.seeded then BR.seeded=true;event('foes at one HP') end
  end
 end
end)
hook({a('BTL_deinitializeCombat')},function()
 if not ({loaded('BTL_deinitializeCombat')}) then return end
 BR.ended=true;event('battle ended')
end)
hook({a('setTrigger')},function()
 if PCSX.getRegisters().GPR.n.a0==221 and not BR.wasRecruited then
  BR.joined=true;event('recruit flag; battle ended='..tostring(BR.ended))
 end
end)
hook({a('playSound')},function()
 local r=PCSX.getRegisters()
 if r.GPR.n.a0==8 and r.GPR.n.a1==11 and not BR.wasRecruited and recruited() then
  BR.jingle=true;event('join jingle')
 end
end)
hook({a('writePStat')},function()
 local r=PCSX.getRegisters()
 if r.GPR.n.a0==1 and recruited() and BR.reward==nil then
  BR.reward=r.GPR.n.a1;event('prosperity after reward '..BR.reward)
 end
end)
hook({a('showTextbox')},function()
 local r=PCSX.getRegisters()
 if not BR.wasRecruited and recruited() and r.GPR.n.a1==255 then
  if not BR.joined then BR.joined=true;event('recruit flag observed; battle ended='..tostring(BR.ended)) end
  BR.scene=true;event('narrator join box')
 end
end)
return 'installed'
""")


def call_section(e, script, section, param=0):
    """Enter a real handler at a frame boundary, as the map trigger does."""
    e.run('lua', f"""
BR_ROUTE={{}}
BR_ROUTE.bp=PCSX.addBreakpoint({e.A('gameLoop')},'Exec',4,'bird-route',function()
 local r=PCSX.getRegisters()
 if BR_ROUTE.ra then r.GPR.n.ra=BR_ROUTE.ra;BR_ROUTE.bp:remove();return end
 BR_ROUTE.ra=r.GPR.n.ra;r.GPR.n.a0={script};r.GPR.n.a1={section};r.GPR.n.a2={param}
 r.GPR.n.ra={e.A('gameLoop')};r.pc={e.A('callScriptSection')}
end)
""")


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('disc'); p.add_argument('--exe', required=True)
    p.add_argument('--port', type=int, default=42139)
    p.add_argument('--out', type=Path, default=Path('build/birdramon-proof'))
    p.add_argument('--card', type=Path, default=ROOT / 'tools/dev/saves/corpus/20261027-d2796814.mcd')
    args = p.parse_args()
    with socket.socket() as probe:
        probe.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        probe.bind(('127.0.0.1', args.port))
    out = args.out.resolve(); out.mkdir(parents=True, exist_ok=True)
    e = Emu(args.disc, args.exe, args.port, str(out / 'emu'))
    for name, (address, _, _) in elf_symbols(args.exe + '.elf').items():
        e.table.setdefault(name, address)
    e.env['EMU_ARGS'] = '-interpreter -debugger'
    results = {}
    try:
        e.start(field_card(args.card, out / 'native.mcd'))
        e.run('lua', f"""BR_MOV=PCSX.addBreakpoint({e.A('playMovie')},'Exec',4,'bird-skip-intro',function()
 PCSX.getRegisters().GPR.n.a1=0
end)""")
        assert e.continue_game() == 0, 'Continue failed'
        e.wait(8); assert e.in_control()
        print('PASS boot and Continue on original 2 MB', flush=True)
        e.poke('MOD_OPT_STORY', struct.pack('<i', 1))
        e.gs('set', 'partner.para.age=1', 'partner.para.evoTimer=0', 'partner.para.condition=0',
             'partner.para.foodLevel=100', 'partner.para.remainingLifetime=1000', 'gametime_running=0')
        e.run('save', str(out / 'field.state'))
        for case in ('won', 'legacy', 'lost'):
            e.run('load', str(out / 'field.state')); e.run('lua', 'PCSX.resumeEmulator()')
            for n, v in ((719, 1), (727, 0), (730, 0), (748, 0), (721, int(case == 'legacy')), (221, 0), (235, 1),
                         (220, 0), (214, 0), (225, 0), (246, 0), (87, 0), (88, 0), (354, 0)):
                e.gs('trigger', str(n), str(v))
            e.gs('pstat', '1', '48' if case == 'won' else '10')
            e.gs('set', 'partner.stats.off=900', 'partner.stats.def=900', 'partner.stats.speed=900',
                 'partner.stats.brain=900', 'partner.para.discipline=100',
                 'partner.stats.currentHP=9000', 'partner.stats.currentMP=9000')
            if case == 'lost':
                e.gs('set', 'partner.stats.off=1', 'partner.stats.def=1', 'partner.stats.speed=1')
            assert e.warp(39), 'bridge did not load'
            e.wait(2)
            print('bridge loaded:', case, flush=True)
            e.run('shot', str(out / f'{case}-bridge.png'))
            bridge_ram = e.ram()
            bridge_species = [e.peek('NPC_ENTITIES+' + str(slot * 104), 'i', bridge_ram) for slot in (1, 2)]
            assert bridge_species == [80, 21], bridge_species
            bridge_heap = free_heap(e, bridge_ram)
            assert bridge_heap['free'] > 0
            install(e, 'lost' if case == 'lost' else 'won')
            # `approach` stood the tamer inside Birdramon's collision box (and a position poke leaves the camera behind, so
            # the NPC is off screen and cannot be touched). Enter the real talk handler the way checkMapInteraction does:
            # TALKED_TO_ENTITY = entity slot 4 (NPC slot 2), callScriptSection(screen, scriptId 7, 1).
            e.poke('TALKED_TO_ENTITY', bytes([4]))
            call_section(e, 39, 7, 1)
            deadline = time.monotonic() + 240
            while time.monotonic() < deadline:
                ram = e.ram(); game = e.peek('GAME_STATE', 'H', ram)
                flags = e.run('lua', "return tostring(BR.ended)..','..tostring(BR.scene)").strip()
                if case != 'lost' and flags == 'true,true':
                    e.wait(1); e.run('shot', str(out / f'{case}-joined.png'))
                    results[case] = dict(recruited=bit(e, 221), old_flag=bit(e, 721),
                        prosperity=ram[e.A('SCRIPT_STATE') - 0x80000000 + 346], ram_bytes=len(ram))
                    break
                if case == 'lost' and flags.startswith('true,') and game == 0 and e.peek('TAMER_STATE', 'b', ram) == 0:
                    assert not bit(e, 221, ram)
                    results[case] = dict(recruited=False, ram_bytes=len(ram))
                    break
                if game != 1: e.press('CONFIRM', 6)
                e.wait(.35)
            else: raise AssertionError(f'{case}: fight/scene did not finish')
            results[case].update(bridge_species=bridge_species, bridge_heap=bridge_heap)
            results[case]['events'] = e.run('lua', "return table.concat(BR.events,'\\n')").strip().splitlines()
            print('result', case, json.dumps(results[case]), flush=True)
            if case != 'lost':
                assert e.run('lua', 'return BR.jingle').strip() == 'true'
                assert 'foe type 21' in results[case]['events']
                assert results[case]['old_flag'] == (case == 'legacy')
                e.press('CONFIRM', 8); e.wait(2); assert e.in_control()
                results[case]['reward_prosperity'] = e.ram()[e.A('SCRIPT_STATE') - 0x80000000 + 346]   # the extended pass writes it without writePStat
                assert results[case]['reward_prosperity'] == (50 if case == 'won' else 12)
                results[case]['city'] = e.peek('CURRENT_SCREEN', 'h')
                assert results[case]['city'] == (177 if case == 'won' else 171)
                e.run('shot', str(out / f'{case}-city.png'))
                # Original Birdra Transport, first unlocked destination: Great Canyon.
                e.gs('move', '1507', '-2574')
                call_section(e, 162, 53)  # City's real Birdra Transport doorway
                for _ in range(45):
                    if e.peek('CURRENT_SCREEN', 'h') == 207: break
                    e.wait(.5)
                else: raise AssertionError('city doorway did not reach Birdra Transport')
                assert e.in_control()
                e.gs('set', 'money=99999')
                e.poke('TALKED_TO_ENTITY', bytes([2]))
                call_section(e, 167, 81)  # original counter use trigger
                for _ in range(20):
                    # The menu id differs from the first harness's guess and CONFIRM takes its first row (Great Canyon):
                    # reaching screen 38 here is the taxi working.
                    if e.peek('CURRENT_MENU', 'i') == 10 or e.peek('CURRENT_SCREEN', 'h') == 38: break
                    e.press('CONFIRM', 6); e.wait(.5)
                else:
                    r = e.ram(); print('transport state', {k: e.peek(k, f, r) for k, f in (('CURRENT_SCREEN', 'h'), ('CURRENT_MENU', 'i'), ('ACTIVE_INSTRUCTION', 'B'), ('SCRIPT_SECTION', 'H'), ('IS_SCRIPT_PAUSED', 'i'), ('TAMER_STATE', 'b'))}, flush=True)
                    e.run('shot', str(out / f'{case}-transport-fail.png'))
                    raise AssertionError('Birdra Transport menu did not open')
                e.run('shot', str(out / f'{case}-transport.png'))
                for _ in range(30):
                    e.press('CONFIRM', 6); e.wait(.5)
                    if e.peek('CURRENT_SCREEN', 'h') == 38: break
                else: raise AssertionError('Birdra Transport did not reach Great Canyon')
                assert e.in_control()
                results[case]['transport_destination'] = 38
                # The nest must stay fallen even after recruitment.
                e.warp(129, 0)
                if e.peek('CURRENT_SCREEN', 'h') == 129:
                    call_section(e, 124, 52)  # real elevator arrival section
                for _ in range(30):
                    if e.peek('CURRENT_SCREEN', 'h') == 366: break
                    e.press('CONFIRM', 6); e.wait(.5)
                else: raise AssertionError('nest did not stay fallen')
                e.in_control()
                results[case]['nest'] = 366
                (out / 'result.json').write_text(json.dumps(results, indent=2) + '\n')
                if case == 'won':
                    # Only Birdramon can rescue this state. Play the actual summit
                    # scene and its battle; the normal reward tail proves rescue.
                    for n, v in ((748, 1), (50, 0), (256, 0), (206, 0), (212, 0), (207, 0)):
                        e.gs('trigger', str(n), str(v))
                    e.gs('set', 'partner.stats.currentHP=9000', 'partner.stats.currentMP=9000')
                    e.warp(225)
                    assert e.peek('CURRENT_SCREEN', 'h') == 225
                    if e.peek('IS_SCRIPT_PAUSED', 'i') == 1:
                        call_section(e, 184, 51)
                    deadline = time.monotonic() + 480
                    seen_rescue = False
                    while time.monotonic() < deadline:
                        ram = e.ram()
                        pointer = e.peek('TEXTBOX_LINES_PTR', 'I', ram) - 0x80000000
                        if 0 <= pointer < len(ram) - 0x800:
                            lines = ram[pointer:pointer + 0x800]
                            # The renderer uses single-byte ASCII mixed with control codes.
                            if b'Birdramon!' in lines or 'Birdramon!' in lines.decode('utf-16le', errors='ignore'):
                                if not seen_rescue:
                                    e.run('shot', str(out / 'summit-birdramon.png'))
                                    seen_rescue = True
                        if bit(e, 50, ram) and bit(e, 206, ram) and bit(e, 212, ram):
                            assert bit(e, 207, ram) and not bit(e, 748, ram) and bit(e, 221, ram) and not bit(e, 220, ram)   # Airdramon joins all the same
                            results[case]['summit_rescued'] = True
                            results[case]['summit_rescue_text_seen'] = seen_rescue
                            break
                        if e.peek('GAME_STATE', 'H', ram) != 1: e.press('CONFIRM', 6)
                        e.wait(.35)
                    else: raise AssertionError('Birdramon summit rescue did not reach original reward tail')
            else:
                assert e.warp(39)
                ram = e.ram()
                assert e.peek('NPC_ENTITIES+208', 'i', ram) == 21
                results[case]['waiting_after_loss'] = True
            (out / 'result.json').write_text(json.dumps(results, indent=2) + '\n')
            print('PASS', case, results[case], flush=True)
    except Exception:
        e.run('shot', str(out / 'failure.png'), check=False)
        raise
    finally:
        e.stop()


if __name__ == '__main__':
    main()
