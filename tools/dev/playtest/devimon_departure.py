#!/usr/bin/env python3
"""Play Devimon's post-battle departure on original 2 MB RAM.

The foe is seeded at one HP; the game wins with a real attack. At the last
post-battle page, the regression fixture varies only Devimon's position and
facing. His original flight clip and the real scene handler run unchanged.
Use --expect-stall on an unpatched disc; --natural omits the position fixture.
Checkpoints belong to their own disc and must never cross executable builds.
"""
import argparse
import json
from pathlib import Path
import struct
import sys
import time
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parents[3]
sys.path[:0] = [str(ROOT), str(ROOT / 'tools')]
from tools.dev.saves.releases import Emu
from tools.dev import memory_card as mcd
from tools.languages import CODES
from tools.dev.playtest.birdramon_recruitment import field_card, call_section, install, bit, free_heap
from tools.dev.playtest.partner_walk import WalkTest
from tools.dev.playtest.story_convergence import Run
from tools.langpatch import elf_symbols

FINAL_PAGE_NEXT = bytes.fromhex('56000a1c6c0a2eee29001400')


def final_page(e, ram):
    pointer = e.peek('SCRIPT_POINTER', 'I', ram) - 0x80000000
    return e.peek('ACTIVE_INSTRUCTION', 'B', ram) == 26 and ram[pointer:pointer + len(FINAL_PAGE_NEXT)] == FINAL_PAGE_NEXT



def catch_final_page(e):
    """Latch the short final page before a held confirm can skip host polling."""
    expected = '{' + ','.join(map(str, FINAL_PAGE_NEXT)) + '}'
    e.run('lua', f"""
if DVT then for _, b in ipairs(DVT.bp) do b:remove() end end
DVT={{bp={{}},returns={{}},captured=false}}
local m=PCSX.getMemPtr()
local expected={expected}
local function u8(a) return tonumber(m[a-0x80000000]) end
local function u32(a) return u8(a)+256*u8(a+1)+65536*u8(a+2)+16777216*u8(a+3) end
local function returned()
 if not BR.ended or u8({e.A('ACTIVE_INSTRUCTION')})~=26 then return true end
 local p=u32({e.A('SCRIPT_POINTER')})
 for i,v in ipairs(expected) do if u8(p+i-1)~=v then return true end end
 DVT.captured=true
 for _,b in ipairs(DVT.bp) do b:remove() end
 DVT.bp={{}}
 PCSX.pauseEmulator()
 return true
end
DVT.bp[1]=PCSX.addBreakpoint({e.A('showTextbox')},'Exec',4,'devimon-final-page',function()
 local ra=tonumber(PCSX.getRegisters().GPR.n.ra)
 if not DVT.returns[ra] then
  local b=PCSX.addBreakpoint(ra,'Exec',4,'devimon-page-return',returned)
  DVT.returns[ra]=b;DVT.bp[#DVT.bp+1]=b
 end
 return true
end)
""")


def snapshot(e):
    ram = e.ram()
    pd = e.peek('NPC_ENTITIES+524', 'I', ram)
    present = e.peek('ENTITY_TABLE+28', 'I', ram) != 0
    position = list(struct.unpack_from('<3i', ram, pd - 0x80000000 + 0x78)) if present else None
    return dict(ram_bytes=len(ram), partner=e.peek('PARTNER_ENTITY', 'I', ram),
                active=e.peek('ACTIVE_INSTRUCTION', 'B', ram), wait=e.peek('WAIT_FOR_ENTITY_ID', 'B', ram),
                paused=e.peek('IS_SCRIPT_PAUSED', 'i', ram), tamer=e.peek('TAMER_STATE', 'b', ram),
                beaten=bit(e, 321, ram), heap=free_heap(e, ram),
                movement=list(ram[e.A('SCRIPT_MOVEMENT') - 0x80000000 + 84:][:4]),
                delta=[e.peek('MOVE_TO_DELTA_X', 'h', ram), e.peek('MOVE_TO_DELTA_Z', 'h', ram)],
                devimon=position, devimon_present=present)


def fixture(e, walk):
    """A small positive remainder, with an ordinary diagonal facing."""
    e.run('lua', 'PCSX.pauseEmulator()')
    pd = e.peek('NPC_ENTITIES+524', 'I')
    e.run('poke', hex(pd + 0x72), struct.pack('<h', 512).hex())
    walk.calls([('setupEntityMatrix', (7,))])
    # setupEntityMatrix's call wrapper pauses after returning. Match both the
    # integer position and animation accumulator, as setEntityPosition does.
    e.run('poke', hex(pd + 0x78), struct.pack('<3i', -4543, 0, 22).hex())
    e.poke('NPC_ENTITIES+536', struct.pack('<3i', -4543 * 32768, 0, 22 * 32768))


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('disc')
    p.add_argument('--exe', required=True)
    p.add_argument('--port', type=int, default=42165)
    p.add_argument('--out', type=Path, default=Path('build/devimon-proof'))
    p.add_argument('--partners', type=int, nargs='+', default=[3, 62, 22])
    p.add_argument('--expect-stall', action='store_true')
    p.add_argument('--natural', action='store_true')
    p.add_argument('--language', choices=CODES, default='en')
    p.add_argument('--card', type=Path, default=ROOT / 'tools/dev/saves/corpus/20261027-d2796814.mcd')
    args = p.parse_args()
    out = args.out.resolve(); out.mkdir(parents=True, exist_ok=True)
    e = Emu(args.disc, args.exe, args.port, str(out / 'emu'))
    for name, (address, _, _) in elf_symbols(e.exe + '.elf').items():
        e.table.setdefault(name, address)
    e.env['EMU_ARGS'] = '-interpreter -debugger'
    walk = WalkTest(SimpleNamespace(out=out / 'calls', disc=e.disc, exe=e.exe, port=e.port)); walk.e = e
    r = Run(e, out)
    results = []
    try:
        card_path = field_card(args.card, out / 'native.mcd')
        if args.language != 'en':
            card = mcd.Card(card_path)
            data = bytearray(card.read('BASLUS-01032DMR0'))
            data[0x5b] = CODES.index(args.language)
            size = 0x2000 if len(data) >= 0x6000 else 0x1000
            for offset in (0x2000, 0x2000 + size):
                head = bytearray(data[offset:offset + size])
                records = []
                for tag, value in mcd.parse_records(head):
                    if tag == 9:
                        value = bytearray(value)
                        value[7] = CODES.index(args.language)
                    records.append((tag, value))
                data[offset:offset + size] = mcd.build_extension(head, records, size)
            card.write('BASLUS-01032DMR0', 0, data)
        e.start(card_path)
        e.run('lua', f"PCSX.addBreakpoint({e.A('playMovie')},'Exec',4,'devimon-skip-intro',function() PCSX.getRegisters().GPR.n.a1=0 end)")
        assert e.continue_game() == 0
        print('Continue loaded on original 2 MB', flush=True)
        e.wait(8)
        e.gs('set', 'gametime_running=0')
        e.run('save', str(out / 'field.state'))
        for partner in args.partners:
            e.run('load', str(out / 'field.state')); e.run('lua', 'PCSX.resumeEmulator()')
            if partner != 3:
                walk.switch(partner); e.run('lua', 'PCSX.resumeEmulator()')
            e.gs('set', 'partner.stats.off=999', 'partner.stats.movesPrio=[100,0,0,0]',
                 'partner.stats.moves=[46,255,255,255]', 'gametime_running=0')
            r.set(root2=False, mt_infinity_devimon_beaten=False)
            r.go(247)
            install(e, 'won')
            catch_final_page(e)
            call_section(e, 194, 53)
            print(f'{partner}: encounter started', flush=True)
            deadline = time.monotonic() + 300
            while not final_page(e, e.ram()):
                assert time.monotonic() < deadline, 'did not reach the final post-battle page'
                if e.peek('GAME_STATE', 'H') != 1:
                    e.press('CONFIRM', 6)
                e.wait(.5)
            e.run('lua', 'PCSX.resumeEmulator()')
            assert e.run('lua', 'return DVT.captured').strip() == 'true', 'final page was not latched'
            assert e.run('lua', 'return BR.ended').strip() == 'true', 'battle did not finish normally'
            # TextBoxTable.usedRows (4), then the first TextBoxData's
            # write/render counters (21..22) and registered flag (24).
            deadline = time.monotonic() + 60
            while True:
                ram = e.ram()
                counts = e.peek('TEXTBOX_DATA+21', '2B', ram)
                if e.peek('TEXTBOX_DATA+24', 'B', ram) == 1 and len(set(counts)) == 1:
                    break
                assert time.monotonic() < deadline, 'final page did not finish rendering'
                e.wait(.3)
            e.run('save', str(out / f'{partner}-final-page.state'))
            if not args.natural:
                fixture(e, walk)
            r.shot(f'{partner}-before')
            e.run('save', str(out / f'{partner}-before.state'))
            e.run('lua', 'PCSX.resumeEmulator()')
            deadline = time.monotonic() + 60
            # The final page can be parsed before its box is ready for input.
            while final_page(e, e.ram()):
                assert time.monotonic() < deadline, 'final page never accepted confirm'
                e.press('CONFIRM', 6); e.wait(.5)
            print(f'{partner}: final page closed', flush=True)
            start = e.peek('MOD_FPS_TICKS', 'I')
            deadline = time.monotonic() + 240
            while e.peek('MOD_FPS_TICKS', 'I') - start < 240:
                assert time.monotonic() < deadline, 'emulator tick deadline'
                e.wait(.4)
            end = snapshot(e)
            stalled = end['active'] == 74 and end['wait'] == 7 and end['movement'][0] == 8 and end['delta'] == [0, 0]
            complete = end['paused'] == 1 and end['tamer'] == 0 and end['beaten'] and not end['devimon_present']
            end.update(expected_stall=args.expect_stall, natural=args.natural, language=args.language, stalled=stalled, complete=complete)
            results.append(end)
            r.shot(f'{partner}-after')
            e.run('save', str(out / f'{partner}-after.state'))
            print(json.dumps(end), flush=True)
            assert stalled if args.expect_stall else complete, end
    finally:
        (out / 'result.json').write_text(json.dumps(results, indent=2) + '\n')
        e.stop()


if __name__ == '__main__':
    main()
