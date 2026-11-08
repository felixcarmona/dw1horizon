#!/usr/bin/env python3
"""Exercise real jukebox row recycling and title fitting in PCSX-Redux at 2 MB.

The fixture opens the native routine in the restaurant with all tracks unlocked.
Scroll calls use the game's cursor functions; no text or drawing code is mocked.
--state may supply a field snapshot made by exactly the same executable/disc.
"""
import argparse
import json
from pathlib import Path
import struct
import sys
import time

ROOT = Path(__file__).resolve().parents[3]
sys.path[:0] = [str(ROOT), str(ROOT/'tools')]
from tools.dev.playtest.qol import ProofEmu
from tools.dev.playtest.load_camera import card_fixture
from tools.dev.playtest.training_evolution import call
from tools.langpatch import elf_symbols


def batch(e, calls, gap=1):
    """Call at frame boundaries, leaving ordinary game ticks between requests."""
    queue = []
    for name, args in calls:
        args = list(args) + [0] * (4-len(args))
        queue.append('{' + ','.join(map(str, [e.A(name), *args])) + '}')
    gl = e.A('gameLoop')
    e.run('lua', f"""
      JQ={{q={{{','.join(queue)}}},out={{}},i=1,phase=0,wait=0,done=false}}
      JQ.bp=PCSX.addBreakpoint({gl},'Exec',4,'jukebox-queue',function()
        local r=PCSX.getRegisters()
        if JQ.phase==1 then
          JQ.out[#JQ.out+1]=tonumber(r.GPR.n.v0)
          r.GPR.n.ra=JQ.ra; JQ.phase=0; JQ.i=JQ.i+1; JQ.wait={gap}
          if JQ.i>#JQ.q then
            JQ.done=true;JQ.bp:remove();PCSX.pauseEmulator()
          end
          return
        end
        if JQ.wait>0 then JQ.wait=JQ.wait-1;return end
        local c=JQ.q[JQ.i]
        JQ.ra=r.GPR.n.ra
        r.GPR.n.a0=c[2];r.GPR.n.a1=c[3]==-1 and JQ.out[#JQ.out] or c[3]
        r.GPR.n.a2=c[4];r.GPR.n.a3=c[5]
        r.GPR.n.ra={gl};r.pc=c[1];JQ.phase=1
      end)
      PCSX.resumeEmulator()
    """)
    for _ in range(600):
        if e.run('lua', 'return JQ.done').strip() == 'true':
            return list(map(int, e.run('lua', "return table.concat(JQ.out,',')").strip().split(',')))
        time.sleep(.1)
    raise AssertionError('jukebox frame queue did not finish')


def capture(e, out, lang, font):
    call(e, 'modSetLanguage', lang)
    call(e, 'modSetFont', font)
    box = e.peek('ITEM_MENU_LEFT', 'I')
    # Start every tour with the same logical rows and physical row slots.
    start = bytes([0, 0] if lang in (0, 1) else [42, 5]).hex()
    e.run('poke', hex(box+9), start)
    e.run('poke', hex(box+13), start)
    e.run('poke', hex(box+24), '090a0b0c0d0e')
    call(e, 'updateItemMenuStrings', box, 9, 2)
    e.run('resume'); time.sleep(.5)
    widths = []
    ram = e.ram()
    titles = struct.unpack_from('<63I', ram, e.A('BGM_TRACK_NAMES') & 0x1fffff)
    requests = []
    for pointer in titles:
        requests += [('fitStringMode', [pointer, 176]), ('measureStringMode', [pointer, -1])]
    values = batch(e, requests, gap=0)
    for track, (mode, width) in enumerate(zip(values[::2], values[1::2])):
        widths.append(dict(track=track+1, mode=mode, pixels=width))
        assert width <= 176, (lang, font, track+1, width)
    batch(e, [('itemMenuCursorDown', [box, 2])] * (62 if lang in (0, 1) else 15), gap=8)
    e.run('resume')
    time.sleep(.5)
    ram = e.ram(); offset = box & 0x1fffff
    assert ram[offset+9:offset+11] == bytes([57, 5])
    name = f'jukebox-lang{lang}-font{font}'
    e.run('shot', str(out/(name+'.png')))
    e.run('save', str(out/(name+'.state')))
    (out/(name+'.json')).write_text(json.dumps(widths, indent=2)+'\n')
    print(f'PASS: language {lang}, font {font}: all 63 titles fit; scrolled to 58–63', flush=True)
    return dict(language=lang, font=font, widest=max(widths, key=lambda r:r['pixels']))


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--disc', required=True)
    ap.add_argument('--exe', required=True)
    ap.add_argument('--out', type=Path, required=True)
    ap.add_argument('--state', type=Path)
    ap.add_argument('--port', type=int, default=42282)
    ap.add_argument('--languages', default='0,1', help='non-Chinese language ids; Chinese needs its own 8 MB check')
    ap.add_argument('--chinese', action='store_true', help='separate Chinese-only 8 MB acceptance (its documented requirement)')
    a = ap.parse_args(); a.out = a.out.resolve(); a.out.mkdir(parents=True, exist_ok=True)
    e = ProofEmu(a.disc, a.exe, a.port, str(a.out/'emu'))
    for name, (address, _, _) in elf_symbols(e.exe+'.elf').items():
        e.table.setdefault(name, address)
    e.table['CURRENT_SCREEN'] = e.A('CURRENT_SCREEN_ID')
    e.env['EMU_ARGS'] = '-interpreter -debugger' + (' -8mb' if a.chinese else '')
    if a.chinese:
        e.ram = lambda: e.api('/api/v1/cpu/ram/raw')
    try:
        card = None if a.state else card_fixture(a.out, 215, (0, 0, 0), 3, False, 1, 0)
        e.start(None if card is None else str(card))
        if a.state:
            e.run('load', str(a.state.resolve())); e.run('resume'); time.sleep(1)
        else:
            assert e.continue_game() == 0
        assert len(e.ram()) == (0x800000 if a.chinese else 0x200000)
        time.sleep(1)
        e.poke('PAUSE_STATE', b'\0')
        if e.peek('CURRENT_SCREEN_ID', 'h') != 215:
            assert e.warp(215)
        print(f'Restaurant fixture loaded at {8 if a.chinese else 2} MB', flush=True)
        call(e, 'setTrigger', 50)
        call(e, 'writePStat', 254, 253)
        e.poke('SCRIPT_STATE_2', bytes(2)); e.poke('SCRIPT_TEXTBOX_MODE', b'\0')
        e.poke('SCRIPT_PARAM_1', b'\x09'); e.poke('ACTIVE_INSTRUCTION', b'\x64')
        e.poke('IS_SCRIPT_PAUSED', bytes(4))
        e.run('resume'); time.sleep(1); e.run('pause')
        e.poke('SCRIPT_STATE_2', b'\3\0'); e.poke('SCRIPT_TEXTBOX_MODE', b'\0')
        e.run('resume'); time.sleep(1)
        results = []
        for lang in ([8] if a.chinese else map(int, a.languages.split(','))):
            if lang == 8 and not a.chinese:
                raise ValueError('Chinese has its documented separate 8 MB requirement')
            for font in ((0,) if lang == 8 else (0, 1, 2)):
                results.append(capture(e, a.out, lang, font))
        (a.out/'result.json').write_text(json.dumps(results, indent=2)+'\n')
    finally:
        e.stop()


if __name__ == '__main__':
    main()
