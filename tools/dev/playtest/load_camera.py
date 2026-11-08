#!/usr/bin/env python3
"""Hold a direction from Continue initialization on an original-2-MB disc.

The private card changes only fixture species, care, screen and positions. A
breakpoint starts pad input at initializeLoadedMap, before field control. The
original USA disc can be used as the control with --original (needs extracted/
and the pinned decomp's original symbols). No game camera state is injected.
"""
import argparse
import json
import os
from pathlib import Path
import struct
import sys
import time

ROOT = Path(__file__).resolve().parents[3]
sys.path[:0] = [str(ROOT), str(ROOT / 'tools')]
from tools.dev import memory_card as mcd, symbols
from tools.dev.saves.releases import Emu
from tools.dev.playtest.airdramon_timeout import native_card
from tools.langpatch import elf_symbols


def card_fixture(out, screen, position, species, original, quick, language):
    target = out / 'continue.mcd'
    native_card(ROOT / 'tools/dev/saves/corpus/20261027-d2796814.mcd', target,
                tamer_position=position, partner_type=species)
    card = mcd.Card(target)
    name = 'BASLUS-01032DMR0'
    data = bytearray(card.read(name))
    size = 0x2000 if len(data) >= 0x6000 else 0x1000
    options = bytearray(data[0x54:0x60])
    options[0] = 1  # Circle confirms in Horizon; vanilla retains its own controls.
    options[7] = language
    options[11] = quick
    data[0x54:0x60] = options
    for i, base in enumerate((0x200, 0x1100)):
        payload = bytearray(data[base:base + 0xf00])
        payload[0x49a:0x49e] = bytes([screen, 168, 0, 0])
        struct.pack_into('<3i', payload, 20, position[0]-200, position[1], position[2])
        if original:
            payload[0x4e4:0x500] = bytes(28)
        checksum = mcd.v1_checksum(payload) ^ (0 if original else 0xffffffff)
        struct.pack_into('<I', payload, 0x4fc, checksum)
        data[base:base + 0xf00] = payload
        off = 0x2000 + i*size
        head = bytearray(data[off:off + size])
        struct.pack_into('<I', head, 8, checksum)
        replacement = {1: struct.pack('<hh', screen, 168), 9: bytes(options)}
        records = [(tag, replacement.get(tag, value)) for tag, value in mcd.parse_records(head)]
        data[off:off + size] = mcd.build_extension(head, records, size)
    card.write(name, 0, data)
    return target


class Original(Emu):
    def __init__(self, disc, port, out):
        self.disc, self.exe, self.port = disc, str(ROOT/'extracted/SLUS_010.32'), port
        self.work = str(out/'emu')
        self.home = str(out/'emu/home')
        self.table = symbols.table('orig')
        self.env = dict(os.environ, EMU_PORT=str(port), EMU_HOME=self.home, DW_SYMS='orig')

    def peek(self, expr, fmt, ram=None):
        return super().peek(expr, 'B' if expr == 'CURRENT_SCREEN' else fmt, ram)


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('disc')
    p.add_argument('--exe')
    p.add_argument('--original', action='store_true')
    p.add_argument('--out', type=Path, required=True)
    p.add_argument('--port', type=int, default=42171)
    p.add_argument('--screen', type=int, default=112)
    p.add_argument('--position', type=int, nargs=3, default=[650, 0, 750])
    p.add_argument('--species', type=int, default=3)
    p.add_argument('--button', choices=['UP', 'DOWN', 'LEFT', 'RIGHT'], default='RIGHT')
    p.add_argument('--delay', type=int, default=0, help='logic ticks before holding the direction')
    p.add_argument('--ticks', type=int, default=240, help='logic ticks to hold; shorten near an exit')
    p.add_argument('--quick', type=int, choices=[0, 1], default=1)
    p.add_argument('--language', type=int, choices=range(8), default=0,
                   help='saved language id; 0 English, 2 Portuguese (2 MB languages only)')
    p.add_argument('--expect-stuck', action='store_true')
    args = p.parse_args()
    if not args.original and not args.exe:
        p.error('--exe is required unless --original is given')
    if not 0 <= args.screen <= 255 or args.delay < 0 or args.ticks < 1:
        p.error('use screen 0..255, a nonnegative delay and a positive hold duration')
    out = args.out.resolve()
    out.mkdir(parents=True, exist_ok=True)
    e = Original(args.disc, args.port, out) if args.original else Emu(args.disc, args.exe, args.port, str(out/'emu'))
    if not args.original:
        for name, (address, _, _) in elf_symbols(args.exe+'.elf').items():
            e.table.setdefault(name, address)
    e.env['EMU_ARGS'] = '-interpreter -debugger'
    card = card_fixture(out, args.screen, args.position, args.species, args.original,
                        args.quick, args.language)
    try:
        e.start(str(card))
        e.run('lua', f'''
LC={{ticks=0,loaded=false,done=false,bp={{}},ownership={{}},last=''}}
local pad=PCSX.SIO0.slots[1].pads[1]
local button=PCSX.CONSTS.PAD.BUTTON.{args.button}
local m=PCSX.getMemPtr()
local function u8(a) return tonumber(m[a%0x200000]) end
local function hook(a,f) LC.bp[#LC.bp+1]=PCSX.addBreakpoint(a,'Exec',4,'load-camera',f) end
hook({e.A('initializeLoadedMap')},function()
 LC.loaded=true
 if {args.delay}==0 then pad.setOverride(button) end
end)
hook({e.A('gameLoop')},function()
 if LC.loaded then
  LC.ticks=LC.ticks+1
  local owner=u8({e.A('CAMERA_FOLLOW_PLAYER')})..','..u8({e.A('CAMERA_HAS_TARGET')})..','..u8({e.A('CAMERA_UPDATE_TILES')})
  if owner~=LC.last then
   LC.ownership[#LC.ownership+1]=LC.ticks..','..owner;LC.last=owner
  end
  if LC.ticks=={args.delay} then pad.setOverride(button) end
  if LC.ticks=={args.delay+args.ticks} then
   pad.clearOverride(button);LC.done=true;PCSX.pauseEmulator()
  end
 end
end)
''')
        assert e.continue_game() == 0, 'Continue failed'
        deadline = time.monotonic() + 180
        while e.run('lua', 'return LC.done').strip() != 'true':
            assert time.monotonic() < deadline, 'field ticks stopped'
            time.sleep(.2)
        ram = e.ram()
        result = dict(original=args.original, screen=args.screen, button=args.button,
                      delay=args.delay, ticks=args.ticks, quick=args.quick, ram_bytes=len(ram))
        trace = e.run('lua', "return table.concat(LC.ownership,';')").strip()
        result['ownership_tick_follow_target_upload'] = [
            list(map(int, row.split(','))) for row in trace.split(';') if row]
        result['actual_screen'] = e.peek('CURRENT_SCREEN', 'h', ram)
        if not args.original:
            result['language'] = e.peek('MOD_LANG', 'i', ram)
        for name, fmt in [('CAMERA_FOLLOW_PLAYER', 'i'), ('CAMERA_HAS_TARGET', 'B'),
                          ('CAMERA_UPDATE_TILES', 'B'), ('DRAWING_OFFSET_X', 'i'),
                          ('DRAWING_OFFSET_Y', 'i'), ('TAMER_STATE', 'B'), ('GAME_STATE', 'B'),
                          ('TAMER_POSITION_DATA+0x78', '3i')]:
            result[name] = e.peek(name, fmt, ram)
        (out/'result.json').write_text(json.dumps(result, indent=2)+'\n')
        e.run('shot', str(out/'result.png'))
        e.run('save', str(out/'result.state'))
        print(json.dumps(result), flush=True)
        assert result['actual_screen'] == args.screen, 'the fixture walked onto another screen'
        if not args.original:
            assert result['language'] == args.language, 'the saved language did not load'
        stuck = result['CAMERA_FOLLOW_PLAYER'] != 1 or result['CAMERA_HAS_TARGET'] != 0
        assert stuck == args.expect_stuck, 'camera follow did not match expectation'
    finally:
        e.stop()


if __name__ == '__main__':
    main()
