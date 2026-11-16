#!/usr/bin/env python3
"""Capture the actual Status profile and care panel on original 2 MB hardware.

Supply a matching disc and executable. Only fixture care values are changed;
the panel, labels, textures and icon come from that disc's ordinary rendering.
"""
import argparse
import os
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[3]
sys.path[:0] = [str(ROOT), str(ROOT / 'tools')]
from tools.dev.playtest.food_sickness import emulator
from tools.dev.playtest.birdramon_recruitment import field_card
from tools.dev.playtest.training_evolution import call
from tools.dev.playtest.status_portraits import await_status


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--disc', required=True)
    parser.add_argument('--exe', required=True)
    parser.add_argument('--language', choices=('en', 'es'), required=True)
    parser.add_argument('--out', type=Path, required=True)
    parser.add_argument('--port', type=int, default=42983)
    args = parser.parse_args()
    out = args.out.resolve()
    out.mkdir(parents=True, exist_ok=True)
    xvfb = None
    if not os.environ.get('DISPLAY'):
        xvfb = subprocess.Popen(['Xvfb', ':298', '-screen', '0', '1024x768x24', '-nolisten', 'tcp'],
                                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        os.environ['DISPLAY'] = ':298'
    e = emulator(str(Path(args.disc).resolve()), str(Path(args.exe).resolve()), args.port, out)
    try:
        card = field_card(ROOT / 'tools/dev/saves/corpus/20261027-d2796814.mcd', out / 'fixture.mcd')
        e.start(str(card))
        assert e.continue_game() == 0
        assert len(e.ram()) == 0x200000
        e.gs('set', 'gametime_running=0', 'partner.para.evoTimer=0',
             'partner.para.remainingLifetime=1000', 'partner.para.condition=0',
             'partner.para.happiness=84', 'partner.para.discipline=15',
             'partner.para.tiredness=0', 'partner.para.virusBar=0', 'partner.para.careMistakes=0')
        for _ in range(6):
            if e.peek('IS_IN_MENU', 'i'):
                break
            e.press('TRIANGLE', 12)
            e.wait(.3)
        assert e.peek('IS_IN_MENU', 'i')
        call(e, 'handleGameMenuSelection', 2)
        e.run('resume')
        await_status(e)
        e.wait(1)
        e.run('shot', str(out / f'status-{args.language}.png'))
        e.run('vram', str(out / f'status-{args.language}.vram'))
    finally:
        e.stop()
        if xvfb:
            xvfb.terminate()


if __name__ == '__main__':
    main()
