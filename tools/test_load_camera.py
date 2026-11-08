#!/usr/bin/env python3
"""Continue with pad input and verify that the tamer remains in the rendered view.

Unlike the ownership diagnostic, this checks the engine's projected actor bounds.
Use --expect-offscreen for the v0.0.7/main regression control, --original for the
vanilla control, or --state to inspect an existing checkpoint from the same disc.
All extra options are passed to tools/dev/playtest/load_camera.py.
"""
import argparse
import json
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT), str(ROOT/'tools')]
from tools.dev.playtest.load_camera import Original
from tools.dev.saves.releases import Emu
from tools.dev.playtest.training_evolution import call
from tools.langpatch import elf_symbols


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('disc')
    p.add_argument('--exe')
    p.add_argument('--original', action='store_true')
    p.add_argument('--out', type=Path, required=True)
    p.add_argument('--port', type=int, default=42181)
    p.add_argument('--state', type=Path)
    p.add_argument('--expect-offscreen', action='store_true')
    args, options = p.parse_known_args()
    if not args.original and not args.exe:
        p.error('--exe is required unless --original is given')
    out = args.out.resolve()
    out.mkdir(parents=True, exist_ok=True)
    if not args.state:
        cmd = [sys.executable, str(ROOT/'tools/dev/playtest/load_camera.py'), args.disc,
               '--out', str(out), '--port', str(args.port)]
        cmd += ['--original'] if args.original else ['--exe', args.exe]
        subprocess.run(cmd + options, check=True)
    state = (args.state or out/'result.state').resolve()
    e = Original(args.disc, args.port, out/'inspect') if args.original else Emu(
        args.disc, args.exe, args.port, str(out/'inspect'))
    if not args.original:
        for name, (address, _, _) in elf_symbols(args.exe+'.elf').items():
            e.table.setdefault(name, address)
    e.env['EMU_ARGS'] = '-interpreter -debugger'
    try:
        e.start(None)
        e.run('load', str(state))
        e.run('resume')
        assert len(e.ram()) == 2097152
        offscreen = call(e, 'entityIsOffScreen', e.A('TAMER_ENTITY'), 320, 240)
        result = dict(tamer_visible=offscreen == 0, ram_bytes=2097152)
        (out/'visibility.json').write_text(json.dumps(result, indent=2)+'\n')
        print(json.dumps(result), flush=True)
        assert result['tamer_visible'] != args.expect_offscreen, 'unexpected camera framing'
    finally:
        e.stop()


if __name__ == '__main__':
    main()
