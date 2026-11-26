#!/usr/bin/env python3
"""The evolution's cancel, played in the emulator: an evolution the hours chose is stopped by holding the cancel button
before the new form shows, and nothing else stops one.

Each case starts an evolution of the Continue save's partner into TARGET with the game's own scene and holds or taps
the cancel button at a tick of the scene:

  hold:T     held from tick T until the scene ends or a second and a half passes: the partner stays what it was,
             the field is back, and no evolution is offered again
  tap:T      a short press at tick T: the ring empties, the partner evolves
  late:T     held from tick T at or past 0xcc (the silhouette changes size): too late, the partner evolves
  item:T     the evolution of an item (not cancellable), held from tick T: the partner evolves
  again:T    held from tick T (cancelled), then, with no state loaded in between, a second evolution of an item: it
             must play to the end (the scene's cancel state lives in main and outlives the overlay)

  evolution_cancel.py DISC.cue --exe EXE --out DIR [--target 26] [--cases hold:10,hold:60,hold:150,tap:60,late:210,item:60]
  evolution_cancel.py DISC.cue --exe EXE --out DIR --partner 3 --target 5 --video OUT.mp4
"""
import argparse
import json
import os
from pathlib import Path
import struct
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[3]
sys.path[:0] = [str(ROOT), str(ROOT / 'tools')]
from tools.dev.playtest.eggs import EggEmu, evolve
from tools.dev.playtest.qol import test_card
from tools.langpatch import elf_symbols

DEFAULT = 'hold:60,hold:150,tap:60,late:210,item:60,again:60'


def button(e):
    return 'CROSS' if e.peek('MOD_OPT_BUTTONS', 'i') != 0 else 'TRIANGLE'


def pad(e, name, down):
    e.run('lua', f'''
      local pad=PCSX.SIO0.slots[1].pads[1]
      local b=PCSX.CONSTS.PAD.BUTTON.{name}
      if {str(down).lower()} then pad.setOverride(b) else pad.clearOverride(b) end
    ''')


def start(e, target, cancellable):
    e.run('pause')
    e.poke('EVOLUTION_TARGET', struct.pack('<h', target))
    e.poke('HAS_USED_EVOITEM', b'\0' if cancellable else b'\1')
    e.poke('MOD_EVO_CANCEL', b'\1' if cancellable else b'\0')
    e.poke('TAMER_STATE', b'\6'); e.poke('TAMER_SUB_STATE', b'\0')
    e.poke('PARTNER_STATE', bytes([13])); e.poke('PARTNER_SUB_STATE', b'\0')
    e.run('resume')


def scene_tick(e, tick, limit=120, falls=0):
    """wait for the scene's own tick `tick`: the loader counts twice on the field first (the timer falls back twice;
    falls=2 once the scene is running)"""
    last = 0
    for _ in range(limit * 20):
        now = e.peek('EVO_SEQUENCE_DATA', 'i')
        if now < last:
            falls += 1
        last = now
        if falls >= 2 and now >= tick:
            return now
        if now == -1:
            return -1
        e.wait(.05)
    raise AssertionError('the scene never reached its tick')


def over(e, limit=90):
    for _ in range(limit * 4):
        if e.peek('PARTNER_STATE', 'b') == 1 and e.peek('EVOLUTION_TARGET', 'h') == -1:
            return True
        e.wait(.25)
    return False


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument('disc'); p.add_argument('--exe', required=True); p.add_argument('--out', required=True)
    p.add_argument('--target', type=int, default=26)
    p.add_argument('--cases', default=DEFAULT)
    p.add_argument('--partner', type=int, help='the partner becomes this species first (3 Agumon, with --target 5)')
    p.add_argument('--video', help='instead of the cases: record one cancel (a short press that empties, then a full hold)')
    p.add_argument('--japanese', action='store_true', help='JAPANESE CONTROLS: the cross cancels')
    p.add_argument('--port', type=int, default=int(os.environ.get('EMU_PORT', 39263)))
    a = p.parse_args(); out = Path(a.out).resolve(); out.mkdir(parents=True, exist_ok=True)
    e = EggEmu(a.disc, a.exe, a.port, str(out / 'emu'))
    e.ram_mb = 2
    e.env['EMU_ARGS'] = ''
    for name, (address, _, _) in elf_symbols(a.exe + '.elf').items():
        e.table.setdefault(name, address)
    results, ok = [], True
    try:
        e.start(test_card(out))
        error = e.continue_game()
        assert error == 0, f'Continue failed: {error}'
        e.wait(5); assert e.in_control()
        if a.japanese:
            e.poke('MOD_OPT_BUTTONS', struct.pack('<i', 1))
        if a.partner:
            evolve(e, a.partner); e.wait(3)
        e.run('save', str(out / 'start.state'))
        before = e.peek('PARTNER_ENTITY', 'i')
        name = button(e)
        if a.video:
            start(e, a.target, True)
            scene_tick(e, 0)
            rec = subprocess.Popen([sys.executable, str(ROOT / 'tools/dev/emulator.py'), 'record', a.video, '20'], env=e.env)
            scene_tick(e, 70, falls=2)
            pad(e, name, True); scene_tick(e, 79, falls=2); pad(e, name, False)
            scene_tick(e, 135, falls=2)
            pad(e, name, True); scene_tick(e, 9999, falls=2); pad(e, name, False)      # until the scene is over (-1)
            assert rec.wait() == 0
            assert over(e) and e.peek('PARTNER_ENTITY', 'i') == before
            return 0
        for case in a.cases.split(','):
            kind, tick = case.split(':'); tick = int(tick)
            e.run('load', str(out / 'start.state')); e.run('lua', 'PCSX.resumeEmulator()'); e.wait(1)
            start(e, a.target, kind != 'item')
            reached = scene_tick(e, tick)
            e.run('shot', str(out / f'{kind}-{tick}-0-before.png'))
            pad(e, name, True)
            if kind == 'tap':
                e.wait(.3)
                e.run('shot', str(out / f'{kind}-{tick}-1-held.png'))
            else:
                for i in range(6):
                    e.wait(.25)
                    e.run('shot', str(out / f'{kind}-{tick}-1-held{i}.png'))
            pad(e, name, False)
            e.run('shot', str(out / f'{kind}-{tick}-2-released.png'))
            done = over(e)
            e.wait(2)
            row = dict(case=case, reached=reached, over=done, species=e.peek('PARTNER_ENTITY', 'i'),
                       flag=e.peek('MOD_EVO_CANCEL', 'b'), control=e.in_control(),
                       wireframe=e.peek('PARTNER_WIREFRAME_TOTAL', 'i') if e.has('PARTNER_WIREFRAME_TOTAL') else None)
            if kind == 'again':
                row['first'] = dict(over=done, species=row['species'], flag=row['flag'])
                start(e, a.target, False)
                done = over(e)
                e.wait(2)
                row.update(over=done, species=e.peek('PARTNER_ENTITY', 'i'), flag=e.peek('MOD_EVO_CANCEL', 'b'),
                           control=e.in_control(), state=e.peek('PARTNER_STATE', 'b'))
            want = (before, 2) if kind == 'hold' else (a.target, 0)
            # an evolution that went through may leave the partner sleepy at once (its new hours): control is enough
            row['ok'] = (done or kind not in ('hold', 'again')) and row['control'] and (row['species'], row['flag']) == want
            e.run('shot', str(out / f'{kind}-{tick}-3-after.png'))
            if kind == 'hold':
                e.wait(8)      # the hours' check runs every tick: held, it must not start again
                row['quiet'] = e.peek('PARTNER_STATE', 'b') == 1 and e.peek('PARTNER_ENTITY', 'i') == before
                row['ok'] = row['ok'] and row['quiet']
            ok &= row['ok']
            results.append(row)
            print(json.dumps(row), flush=True)
    finally:
        (out / 'results.json').write_text(json.dumps(results, indent=1) + '\n')
        e.stop()
    return 0 if ok else 1


if __name__ == '__main__':
    sys.exit(main())
