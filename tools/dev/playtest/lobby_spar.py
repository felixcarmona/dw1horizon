#!/usr/bin/env python3
"""The Arena Lobby spar with Fugamon absent (recruit trigger 289 clear, Hyogamon's 272 set, hour 10) on original 2 MB
RAM: talk to Hyogamon, spar, win (the foe's HP is held at 1), walk out by the door tile (step trigger 1) and require File City with
control. Unguarded, the story's leave() on the absent Fugamon freed an undefined entity (free3 called from removeEntity).

  xvfb-run -a python3 tools/dev/playtest/lobby_spar.py DISC --exe EXE --card CARD [--out DIR] [--port N]
"""
from pathlib import Path
import argparse
import struct
import sys
import time

ROOT = next(p for p in Path(__file__).resolve().parents if (p / 'tools').is_dir())
sys.path[:0] = [str(ROOT), str(ROOT / 'tools')]
from tools.dev.playtest.engine_room_shore import Run


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('disc'); ap.add_argument('--exe', required=True); ap.add_argument('--card', required=True)
    ap.add_argument('--out', default='build/lobby-spar'); ap.add_argument('--port', type=int, default=44240)
    ap.add_argument('--fugamon', action='store_true', help='Fugamon present (control case)')
    a = ap.parse_args(); r = Run(a); e = r.e
    try:
        r.boot()
        e.gs('trigger', '272', '1'); e.gs('trigger', '289', '1' if a.fugamon else '0')
        assert e.warp(208), 'lobby did not load'; e.wait(3)
        r.note(step='lobby', fugamon=a.fugamon, **r.state()); r.shot('21-lobby')
        r.battle_fixture()
        r.place(300, 250); r.hold('RIGHT', 120); time.sleep(1)
        r.note(step='at Hyogamon', **r.state()); r.shot('22-at-hyogamon')
        e.press('CONFIRM', 6); time.sleep(1.5)
        t0 = time.monotonic(); asked = False; won = False; battle = False
        while time.monotonic() - t0 < 300:
            s = r.state()
            battle = battle or s['gs'] == 1
            if s['op'] == 0x10 and not asked:
                time.sleep(.8); r.shot('23-spar-question'); e.press('CONFIRM', 6); asked = True; time.sleep(1); continue
            if asked and battle and s['screen'] == 208 and r.control():
                won = True; break
            e.press('CONFIRM', 6); time.sleep(.5)
        assert asked, 'Hyogamon never offered the spar'
        r.note(step='battle seen', battle=battle)
        assert won, 'no control back in the lobby after the spar: ' + str(r.state())
        r.note(step='after spar', **r.state()); r.shot('24-after-spar')
        ram = e.ram(); off = e.A('MAP_COLLISION_DATA') & 0x1fffff; col = ram[off:off + 10000]
        idx = next(i for i, v in enumerate(col) if v == 52)      # step trigger 1: the lobby's door (script 52)
        r.place((idx % 100 - 50) * 100 + 50, (50 - idx // 100) * 100 - 50)
        t0 = time.monotonic()
        while time.monotonic() - t0 < 120:
            s = r.state()
            if s['screen'] != 208 and r.control(): break
            e.press('CONFIRM', 6); time.sleep(.6)
        s = r.state(); r.note(step='outside', **s); r.shot('25-outside')
        assert s['screen'] != 208 and r.control(), 'did not reach another screen with control: ' + str(s)
        r.note(result='PASS lobby spar', fugamon=a.fugamon)
    except BaseException as error:
        r.note(result='FAIL', error=str(error)); e.run('shot', str(r.out / 'failure.png'), check=False); raise
    finally:
        e.stop()


if __name__ == '__main__':
    main()
