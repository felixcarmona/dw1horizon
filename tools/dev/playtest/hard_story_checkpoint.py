#!/usr/bin/env python3
"""Reach the real ending boss through its scene and stop at startBattle entry."""
import argparse
import hashlib
from pathlib import Path
import struct
import signal
import sys
import time

ROOT = Path(__file__).resolve().parents[3]
sys.path[:0] = [str(ROOT), str(ROOT / 'tools')]
from tools.dev.saves.releases import Emu
from tools.langpatch import elf_symbols


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('disc')
    parser.add_argument('--exe', required=True)
    parser.add_argument('--base', default='build/hard-proof/base.state')
    parser.add_argument('--out', type=Path, default=Path('build/hard-story'))
    parser.add_argument('--port', type=int, default=44382)
    args = parser.parse_args()
    args.out.mkdir(parents=True, exist_ok=True)
    e = Emu(args.disc, args.exe, args.port, str(args.out / 'emu'))
    for name, (address, _, _) in elf_symbols(args.exe + '.elf').items():
        e.table.setdefault(name, address)
    e.env['EMU_ARGS'] = '-interpreter -debugger -bios ' + str(ROOT / '.tools/emu/pcsx-redux-zip/squashfs-root/usr/share/pcsx-redux/resources/openbios.bin')
    def interrupted(number, frame):raise SystemExit(128 + number)
    signal.signal(signal.SIGTERM, interrupted)
    try:
        e.start(None)
        e.run('load', args.base)
        # Original final scene; its own code spawns and configures Machinedramon.
        e.gs('trigger', '50', '0')
        e.gs('trigger', '261', '0')
        e.run('lua', f"""
FP={{ready=false}}
FP.bp=PCSX.addBreakpoint({e.A('startBattle')},'Exec',4,'final-boss-entry',function()
 FP.ready=true;PCSX.pauseEmulator()
end)
return 'armed'
""")
        e.api('/api/v1/execution-flow?function=pause', data=b'')
        e.poke('TAMER_SUB_STATE', bytes([0]))
        e.poke('TARGET_MAP', struct.pack('<h', 225))
        e.poke('CURRENT_EXIT', bytes([0]))
        e.poke('TAMER_STATE', bytes([5]))
        e.api('/api/v1/execution-flow?function=start', data=b'')
        deadline = time.monotonic() + 900
        positioned = False
        while time.monotonic() < deadline:
            if e.run('lua', 'return FP.ready and 1 or 0').strip() == '1':
                assert e.peek('CURRENT_SCREEN', 'h') == 225
                e.run('lua', "FP.bp:remove();return 'removed'")
                e.run('save', str(args.out / 'entry.state'))
                (args.out / 'entry.sha256').write_text(hashlib.sha256(Path(args.exe).read_bytes()).hexdigest() + '\n')
                e.run('shot', str(args.out / 'entry.png'))
                print('Real final scene reached startBattle on screen 225', flush=True)
                return
            if not positioned and e.peek('CURRENT_SCREEN','h') == 225 and e.peek('TAMER_STATE','b') == 0:
                e.gs('move','50','-1350');positioned=True
            e.press('CONFIRM', 16)
            e.wait(.2)
        raise AssertionError('final scene did not reach its battle')
    finally:
        e.stop()


if __name__ == '__main__':
    main()
