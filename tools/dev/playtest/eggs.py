#!/usr/bin/env python3
"""Prove the rebirth scene's eight eggs (patch 0334) on an original-2-MB disc.

Boots the release corpus card, ends the partner's life as the Cheats' Die of old age row does (lifetime 0, no
immortal hour), confirms the death dialogue up to the egg box and saves a state there. From it, per case: walks the
cursor (left/right through every egg, up/down between the rows), hatches the chosen egg and reads the partner's
species back once control returns in the world (keeping the name at Jijimon's prompt): the case fails unless it is the
egg's baby. --video records the first case's box and hatch.

--partner SPECIES evolves the partner if needed (a dying Mega); --trigger N sets a story flag before the death. With
--homecoming SPECIES (and the flag that makes a story's Jijimon's-house line recruit it, such as root2 727 for
SkullGreymon 26), the line must not run during the death (the species is still not recruited when control returns)
and must run at the next entry to the house.

  eggs.py DISC.cue --exe EXE --out DIR [--cases 4,5,6,7,0] [--video FILE.mp4] [--vanilla]
          [--partner 461] [--trigger 727 --homecoming 26]
"""
import argparse
import json
import os
import shutil
from pathlib import Path
import struct
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parents[3]
sys.path[:0] = [str(ROOT), str(ROOT / 'tools')]
from tools.dev.playtest.qol import ProofEmu, test_card
from tools.langpatch import elf_symbols

BABY = {0: 1, 1: 15, 2: 29, 3: 43, 4: 470, 5: 471, 6: 472, 7: 473}
BOX = 3                     # the egg box's UI box (doo2.c)
UIBOX = 0x24                # sizeof(UIBoxData); +0x12 its state


def box_open(e, ram=None):
    ram = ram or e.ram()
    return e.peek(f'UI_BOX_DATA+{BOX * UIBOX + 0x12}', 'h', ram) == 1 and e.peek('SEQ+0x3c', 'h', ram) == 0


def slot(e):
    return e.peek('SEQ+0x0e', 'h')


def reach_box(e, out):
    for i in range(240):
        if box_open(e):
            return i
        e.press('CONFIRM', 8)
        e.wait(1)
    e.run('shot', str(out / 'no-box.png'))
    raise AssertionError('the egg box never opened')


def move(e, button, want):
    before = slot(e)
    for _ in range(3):              # a harness press can drop: press again while the cursor has not moved
        e.press(button, 8)
        e.wait(.4)
        got = slot(e)
        if got != before:
            break
    assert got == want, (button, want, got)
    return got


def walk_all(e, out, count, shots=True):
    """right through every egg and back to 0, then down/up when there are two rows"""
    path = []
    for k in range(1, count + 1):
        path.append(move(e, 'RIGHT', k % count))
        if shots and k < count:
            e.run('shot', str(out / f'cursor-{k % count}.png'))
    path.append(move(e, 'LEFT', count - 1))
    path.append(move(e, 'RIGHT', 0))
    if count == 8:
        path.append(move(e, 'DOWN', 4))
        path.append(move(e, 'UP', 0))
    else:
        e.press('DOWN', 8); e.wait(.4)
        assert slot(e) == 0, 'down moved the cursor with four eggs'
    return path


def choose(e, target, count):
    while slot(e) != target:
        e.press('RIGHT', 8); e.wait(.3)
    e.run('shot', str(e.out / f'chosen-{target}.png'))
    e.press('CONFIRM', 8)


def evolve(e, species):
    """the partner becomes `species` through the game's own evolution (the model loader runs as for any evolution)"""
    if e.peek('PARTNER_ENTITY', 'i') == species:
        return species       # the corpus already has this Mega; avoid an artificial evolution into the same species
    e.run('pause')
    e.poke('EVOLUTION_TARGET', struct.pack('<h', species))
    e.poke('HAS_USED_EVOITEM', b'\1')
    e.poke('TAMER_STATE', b'\6')
    e.poke('TAMER_SUB_STATE', b'\0')
    e.poke('PARTNER_STATE', bytes([13]))
    e.poke('PARTNER_SUB_STATE', b'\0')
    e.run('resume')
    for _ in range(180):
        if e.peek('PARTNER_ENTITY', 'i') == species and e.peek('PARTNER_STATE', 'b') == 1:
            break
        e.press('START', 8)
        e.wait(.25)
    else:
        raise AssertionError(f'the partner did not become {species}')
    e.poke('PAUSE_STATE', b'\0')
    assert e.in_control()
    return species


def to_control(e, tries=60):
    """CONFIRM through the dialogue; at a choice (Jijimon's "Change the name / Keep it as it is", then "Rename it again /
    OK") the last option, so the name keyboard never opens"""
    for _ in range(tries):
        ram = e.ram()
        if e.peek('IS_SCRIPT_PAUSED', 'i', ram) == 1 and e.peek('TAMER_STATE', 'b', ram) == 0:
            return True
        if e.peek('ACTIVE_INSTRUCTION', 'B', ram) == 0x10:          # a choice is open
            e.wait(.5)
            last = e.peek('DIALOGUE_SELECTION+8', 'H') - 1
            for _ in range(8):
                if e.peek('DIALOGUE_SELECTION+10', 'H') == last:
                    break
                e.press('DOWN', 8); e.wait(.3)
        e.press('CONFIRM', 8); e.wait(1)
    return False


def recruited(e, species):
    out = e.gs('trigger', str(200 + species))                # (species below 112: trigger 200 + type)
    return out.split('=')[1].split()[0] == '1'


def hatch(e, out, target):
    """after the choice: the partner's species once the world gives control back"""
    t0 = time.time()
    for n in range(8):
        e.wait(3)
        e.run('shot', str(out / f'hatch-{target}-{n}.png'))
    ok = to_control(e)
    e.wait(2)
    e.run('shot', str(out / f'field-{target}.png'))
    return dict(control=ok, seconds=round(time.time() - t0))


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('disc'); p.add_argument('--exe', required=True);
    p.add_argument('--out', required=True)
    p.add_argument('--cases', default='4,5,6,7,0')
    p.add_argument('--video')
    p.add_argument('--box-state', help='start from this state at the open egg box')
    p.add_argument('--vanilla', action='store_true', help='NEW DIGIMON off: four eggs')
    p.add_argument('--prosperity', type=int, help='set pstat 1 before death (60 selects house 205)')
    p.add_argument('--partner', type=int,
                   help='use this partner species, evolving only if it differs (the dying Mega of a player report)')
    p.add_argument('--trigger', type=int, action='append', default=[],
                   help='set this trigger before the death (a story scene pending on entering the house, for one)')
    p.add_argument('--homecoming', type=int,
                   help="a species a story's Jijimon's-house line recruits (with its --trigger): not during the death, at the next entry")
    p.add_argument('--random', type=int, default=0,
                   help='then N deaths with no lives left (the random egg): the egg each one hatches')
    p.add_argument('--port', type=int, default=int(os.environ.get('EMU_PORT', 39251)))
    a = p.parse_args(); out = Path(a.out).resolve(); out.mkdir(parents=True, exist_ok=True)
    e = ProofEmu(a.disc, a.exe, a.port, str(out / 'emu'))
    e.out = out
    for name, (address, _, _) in elf_symbols(a.exe + '.elf').items():
        e.table.setdefault(name, address)
    e.table['SEQ'] = e.table['DOOA_REINCARNATION_SEQ']     # (the overlays link in the executable's ELF)
    results = {}
    try:
        e.start(test_card(out))
        if a.box_state:                 # a state saved at the open egg box by an earlier run of this disc
            shutil.copyfile(a.box_state, out / 'box.state')
            e.run('load', str(out / 'box.state'))
            e.run('lua', 'PCSX.resumeEmulator()')
            e.wait(1)
        else:
            error = e.continue_game()
            assert error == 0, f'Continue failed: {error}'
            e.wait(5); assert e.in_control()
            e.poke('MOD_OPT_NEW_DIGIMON', struct.pack('<i', 0 if a.vanilla else 1))
            if a.partner is not None:
                results['evolved_to'] = evolve(e, a.partner)
            for n in a.trigger:
                e.gs('trigger', str(n), '1')
            if a.prosperity is not None:
                e.gs('pstat', '1', str(a.prosperity))
            results['ram_bytes'] = len(e.ram())
            results['partner_before'] = e.peek('PARTNER_ENTITY', 'I')
            # Cheats' Die of old age (patch 0307): lifetime 0 and no immortal hour; the natural death runs at once
            e.gs('set', 'partner.para.remainingLifetime=0')
            e.poke('HAS_IMMORTAL_HOUR', b'\0')
            for _ in range(60):
                if e.peek('IS_NATURAL_DEATH', 'i') == 1:
                    break
                e.wait(.5)
            results['natural_death'] = e.peek('IS_NATURAL_DEATH', 'i') == 1
            assert results['natural_death'], 'old-age death did not start'
            results['confirms_to_box'] = reach_box(e, out)
            results['death_screen'] = e.peek('CURRENT_SCREEN', 'h')
            if a.prosperity is not None and a.prosperity >= 50:
                assert results['death_screen'] == 205, results['death_screen']
            e.wait(1)
            e.run('save', str(out / 'box.state'))
            e.run('shot', str(out / 'box.png'))
        count = 4 if a.vanilla else 8
        cases = [int(x) for x in a.cases.split(',')] if a.cases else []
        for i, c in enumerate(cases):
            if i:
                e.run('load', str(out / 'box.state')); e.wait(1)
            rec = None
            if a.video and i == 0:
                rec = subprocess.Popen([sys.executable, str(ROOT / 'tools/dev/emulator.py'), 'record', a.video, '75', '30'],
                                       env=e.env)
                e.wait(2)
            case = dict(walk=walk_all(e, out, count, shots=(i == 0)))
            choose(e, c, count)
            case.update(hatch(e, out, c))
            if rec:
                rec.wait()
            ram = e.ram()
            case['eggSlot'] = e.peek('SEQ+0x0e', 'h', ram)
            case['type'] = e.peek('PARTNER_ENTITY', 'I', ram)
            case['expected'] = BABY[c]
            case['stats'] = e.gs('show', 'partner.stats').strip()
            if a.homecoming is not None:
                case['recruited_after_death'] = recruited(e, a.homecoming)
            results[f'egg-{c}'] = case
            (out / 'result.json').write_text(json.dumps(results, indent=2) + '\n')
            print(c, case, flush=True)
            assert case['control'], f'egg {c}: no control after the hatch'
            assert case['type'] == BABY[c], f'egg {c}: the partner is {case["type"]}, not {BABY[c]}'
            if a.homecoming is not None:
                assert not case['recruited_after_death'], f'the homecoming line ran during the death ({a.homecoming} recruited)'
                if i == 0:                  # the next entry to the house is a homecoming: the line runs there
                    screen = e.peek('CURRENT_SCREEN', 'h')
                    # A pending homecoming owns the tamer until its dialogue ends, so warp's control poll can time out.
                    e.warp(screen)
                    assert to_control(e), 'no control after the homecoming'
                    assert e.peek('CURRENT_SCREEN', 'h') == screen, f'screen {screen} did not load again'
                    e.run('shot', str(out / 'homecoming.png'))
                    results['recruited_at_homecoming'] = recruited(e, a.homecoming)
                    (out / 'result.json').write_text(json.dumps(results, indent=2) + '\n')
                    assert results['recruited_at_homecoming'], 'the homecoming line did not run at the next entry'
        # the random egg: no lives left, DOOA_getSequenceState replaces the choice by rand() % eggCount()
        picks = []
        for n in range(a.random):
            e.run('load', str(out / 'box.state')); e.wait(1)
            e.poke('PARTNER_ENTITY+0x7c', b'\0')
            e.wait(.37 * n)              # a different frame each time: the emulator replays the state exactly
            e.press('CONFIRM', 8)
            for _ in range(40):
                e.wait(.5)
                ram = e.ram()
                if e.peek('SEQ+0x08', 'h', ram) >= 200:        # phase 200: the rebirth started, the slot is final
                    break
            picks.append(e.peek('SEQ+0x0e', 'h'))
            results['random'] = picks
            (out / 'result.json').write_text(json.dumps(results, indent=2) + '\n')
        if picks:
            assert all(0 <= k < count for k in picks), picks
            print('random', picks, flush=True)
    except BaseException as err:
        results['error'] = str(err)
        e.run('shot', str(out / 'failure.png'), check=False)
        e.run('save', str(out / 'failure.state'), check=False)
        raise
    finally:
        (out / 'result.json').write_text(json.dumps(results, indent=2) + '\n')
        e.stop()


if __name__ == '__main__':
    main()
