#!/usr/bin/env python3
"""GPU packet area use of one technique in a tournament match (the STD overlay), 2 MB RAM, stock CPU.

Same monitor as infinity_portal.py (ordering-table writers, per-pass peak, --profile renderers) but the fight is
the Arena Lobby's tournament, started with call_tournament.py. The partner has one equipped technique.

  tools/dev/playtest/packet_tournament.py DISC --exe EXE --out DIR --species 115 --technique 25 [--cup 0] [--pad-packets N]

Prints `gpu {json}` like infinity_portal.py, so packet_sweep.py --tournament can drive it.
"""
import argparse
import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import infinity_portal as ip  # noqa: E402

ROOT = Path(__file__).resolve().parents[3]


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('disc')
    p.add_argument('--exe', required=True)
    p.add_argument('--out', type=Path, required=True)
    p.add_argument('--port', type=int, default=39811)
    p.add_argument('--species', type=int, default=407)
    p.add_argument('--technique', type=int)
    p.add_argument('--cup', type=int, default=0)
    p.add_argument('--offense', type=int, default=30)
    p.add_argument('--pad-packets', type=int, default=0)
    p.add_argument('--seconds', type=int, default=240, help='seconds of match to observe')
    p.add_argument('--timeout', type=int, default=900)
    a = p.parse_args()
    out = a.out.resolve()
    out.mkdir(parents=True, exist_ok=True)
    ip.OVERLAY = 'STD'
    e = ip.ProofEmu(a.disc, a.exe, a.port, str(out / 'emu'))
    e.expanded_ram = False
    e.env['EMU_ARGS'] = '-interpreter -debugger'
    for name, (addr, _, _) in ip.elf_symbols(a.exe + '.elf').items():
        e.table.setdefault(name, addr)
    try:
        e.start(str(ip.test_card(out)))
        assert e.continue_game() == 0, 'Continue failed'
        e.run('lua', f'''IP={{streamFailures=0,coldReads=0,bp={{}}}}''')
        ip.gpu_monitor(e, a.pad_packets, True)
        ip.prepare_fixture(e, a.species, 1, a.technique, a.offense, False)
        assert e.warp(208, 0), 'Arena Lobby did not load'
        e.wait(2)
        # startTournament as call_tournament.py does it: pstat 3 is the cup, and the next gameLoop entry calls it
        e.poke('SCRIPT_STATE+348', bytes([a.cup]))
        gl, st = e.A('gameLoop'), e.A('startTournament')
        e.run('lua', f"""
          CALLT={{phase=0,saved=0}}
          CALLT.bp=PCSX.addBreakpoint({gl},'Exec',4,'calltourn',function()
            local r=PCSX.getRegisters()
            if CALLT.phase==1 then r.GPR.n.ra=CALLT.saved; CALLT.phase=2; CALLT.bp:remove(); return end
            if CALLT.phase==0 then CALLT.saved=r.GPR.n.ra; r.GPR.n.ra={gl}; r.pc={st}; CALLT.phase=1 end
          end)""")
        end = time.monotonic() + a.timeout
        fight = None
        seen = False
        while time.monotonic() < end:
            state = e.peek('GAME_STATE', 'H')
            if state in (4, 5):
                seen = True
                fight = fight or time.monotonic()
                report = ip.gpu_report(e)
                assert report['violations'] == 0 and not report['strangers'], report
                e.press('CIRCLE', 8)
                if time.monotonic() - fight >= a.seconds:
                    break
            elif seen and state == 0:
                break
            else:
                e.press('CONFIRM', 8)
            e.wait(.4)
        else:
            raise AssertionError('the tournament did not run')
        assert seen, 'no tournament match'
        e.run('shot', str(out / 'match.png'))
        print('gpu', json.dumps(ip.gpu_report(e)), flush=True)
        print('PASS', flush=True)
    except BaseException:
        e.run('shot', str(out / 'failure.png'), check=False)
        try:
            print('gpu at failure', json.dumps(ip.gpu_report(e)), flush=True)
        except Exception as error:
            print('gpu report failed', error, flush=True)
        raise
    finally:
        e.stop()


if __name__ == '__main__':
    main()
