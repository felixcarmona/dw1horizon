#!/usr/bin/env python3
"""Review Baby II chart lists and a natural moved-route evolution on 2 MB.

Fixture writes mark the reviewed species raised and install Nyaromon's model.
The tested Nyaromon -> Veemon transition uses the real picker and field tick;
its target and evolution state are never forced. Artifacts remain under --out.
"""
import argparse
import json
from pathlib import Path
import struct
import sys
import signal

ROOT = Path(__file__).resolve().parents[3]
sys.path[:0] = [str(ROOT), str(ROOT / 'tools')]
import evo_tree
from tools.dev.playtest.qol import ProofEmu, test_card, press_value
from tools.dev.playtest.training_evolution import call, await_value
from tools.langpatch import elf_symbols


def chart(e, out):
    e.poke('SPECIES_RAISED_BITS', b'\xff' * 128)
    for t in (1, 2, 3, 16, 17, 18, 57, 80, 84):
        e.gs('trigger', str(0x200 + t), '1')
    call(e, 'tamerSetState', 1)
    e.poke('IS_IN_MENU', struct.pack('<i', 1))
    call(e, 'addGameMenu')
    e.run('resume')
    await_value(e, 'TRIANGLE_MENU_STATE', 'i', lambda n: n == -1)
    call(e, 'handleGameMenuSelection', 3)
    e.run('resume')
    await_value(e, 'MENU_STATE', 'b', lambda n: n == 1)
    press_value(e, 'RIGHT', 'PLAYER_MENU_STATE', 1, 'b')
    await_value(e, 'MENU_STATE', 'b', lambda n: n == 1)
    for _ in range(5):
        if e.peek('CHART_TAB', 'b') == 0:
            break
        e.press('L1')
    assert e.peek('CHART_TAB', 'b') == 0
    press_value(e, 'CONFIRM', 'MENU_STATE', 2, 'b')
    press_value(e, 'CONFIRM', 'MENU_STATE', 3, 'b')
    results = {}
    for name, species in [('koromon', 2), ('nyaromon', 476)]:
        call(e, 'chartDetailGoto', species)
        e.run('resume')
        e.wait(1)
        ram = e.ram()
        count = e.peek('CHART_TO_N', 'b', ram)
        targets = e.peek('CHART_TO_IDS', '24h', ram)[:count]
        assert count == 6 and e.peek('CHART_TO_TOP', 'b', ram) == 0
        results[name] = targets
        e.run('shot', str(out / f'{name}-chart.png'))
        # Six boxes stay on page one even when moving beyond the last box.
        e.poke('CHART_CURSOR_SIDE', b'\1')
        e.poke('CHART_CURSOR_J', b'\5')
        e.press('DOWN')
        assert e.peek('CHART_TO_TOP', 'b') == 0
    assert set(results['koromon']) == {3, 17, 80, 84, 235, 433}
    assert set(results['nyaromon']) == {221, 236, 353, 354, 351, 180}
    call(e, 'chartDetailGoto', 16); e.run('resume')
    assert e.peek('CHART_TO_IDS', '24h').index(17) == 2
    call(e, 'chartDetailMoveCursor', 1, 2); e.run('resume')
    e.poke('MOD_OPT_EVO_GUIDE', struct.pack('<i', 1))
    for _ in range(8):
        e.press('SQUARE', 8)
        if e.peek('CHART_POPUP', 'b') == 1:
            break
        e.wait(.2)
    else:
        raise AssertionError('requirements popup did not open')
    e.wait(1)
    e.run('shot', str(out / 'tsunomon-gabumon-requirements.png'))
    print('ok: Koromon and Nyaromon show all six targets on one page', flush=True)
    return results


def moved_evolution(e, out, base):
    e.run('load', str(base)); e.run('pause')
    # Fixture evolution installs the correct model and raising data.
    for name, fmt, value in [('EVOLUTION_TARGET', 'h', 476), ('HAS_USED_EVOITEM', 'B', 1),
                             ('TAMER_STATE', 'B', 6), ('TAMER_SUB_STATE', 'B', 0),
                             ('PARTNER_STATE', 'B', 13), ('PARTNER_SUB_STATE', 'B', 0)]:
        e.poke(name, struct.pack('<' + fmt, value))
    e.run('resume')
    for _ in range(180):
        ram = e.ram()
        if e.peek('PARTNER_ENTITY', 'i', ram) == 476 and e.peek('PARTNER_STATE', 'b', ram) == 1:
            break
        e.wait(.25)
    else:
        raise AssertionError('Nyaromon fixture did not load')
    e.poke('PAUSE_STATE', b'\0')
    e.wait(1)
    e.run('pause')
    sp, _, _ = evo_tree.load()
    kids, reqs, levels = evo_tree.model(sp)
    witness = evo_tree.rookie_witness(476, 180, kids, reqs, levels, sp)
    assert witness
    vals = witness['stats']
    fields = dict(zip(('hp', 'mp', 'off', 'def', 'speed', 'brain'),
                      [v * (10 if i < 2 else 1) for i, v in enumerate(vals)]))
    fields.update(currentHP=fields['hp'], currentMP=fields['mp'])
    e.gs('set', 'gametime_running=0', 'hour=10', 'minute=0',
         'partner.para.condition=0', 'partner.para.age=24', 'partner.para.evoTimer=24',
         'partner.para.remainingLifetime=1000', 'partner.para.battles=0',
         'partner.para.discipline=50', 'partner.para.happiness=50',
         f'partner.para.careMistakes={witness["care"]}',
         f'partner.para.weight={witness["weight"]}',
         *[f'partner.stats.{k}={v}' for k, v in fields.items()])
    e.poke('HAS_USED_EVOITEM', b'\0')
    e.poke('TAMER_STATE', b'\0')
    # Clear raised history so this is the ordinary stat/weight selection.
    e.poke('SPECIES_RAISED_BITS', b'\0' * 128)
    selected = call(e, 'getNaturalEvolutionTarget', 476)
    assert selected == 180, f'picker chose {selected}'
    e.run('shot', str(out / 'nyaromon-before.png'))
    e.gs('set', 'gametime_running=1')
    e.run('resume')
    for _ in range(240):
        ram = e.ram()
        if e.peek('PARTNER_ENTITY', 'i', ram) == 180 and e.peek('PARTNER_STATE', 'b', ram) == 1:
            break
        e.wait(.25)
    else:
        raise AssertionError('field tick did not evolve Nyaromon to Veemon')
    e.wait(1)
    e.run('shot', str(out / 'veemon-after.png'))
    print('ok: natural picker and field tick evolved Nyaromon -> Veemon', flush=True)
    return dict(witness=witness, selected=selected, actual=e.peek('PARTNER_ENTITY', 'i'))


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('disc'); p.add_argument('--exe', required=True)
    p.add_argument('--port', type=int, default=39263)
    p.add_argument('--out', default='build/baby-rookie-evidence/emulator')
    p.add_argument('--boot-state', type=Path, help='field checkpoint from this exact disc')
    p.add_argument('--case', choices=('all', 'chart', 'evolution'), default='all')
    a = p.parse_args()
    out = Path(a.out).resolve(); out.mkdir(parents=True, exist_ok=True)
    e = ProofEmu(a.disc, a.exe, a.port, str(out / 'emu'))
    e.env['EMU_ARGS'] = '-interpreter -debugger'
    for name, (address, _, _) in elf_symbols(a.exe + '.elf').items():
        e.table.setdefault(name, address)
    signal.signal(signal.SIGTERM, lambda *_: sys.exit(143))
    try:
        e.start(test_card(out))
        if a.boot_state:
            e.run('load', str(a.boot_state.resolve())); e.run('resume'); e.wait(1)
        else:
            assert e.continue_game() == 0, 'Continue failed'
        e.poke('PAUSE_STATE', b'\0')
        assert e.warp(0), 'File City fixture did not load'
        assert e.in_control(), 'no field control in File City'
        e.wait(2)
        assert len(e.ram()) == 2 * 1024 * 1024
        flow = json.loads(e.api('/api/v1/execution-flow'))
        assert not flow['8mb'], 'requires original 2 MB mode'
        assert e.peek('MOD_OPT_NEW_DIGIMON', 'i') == 1, 'test card must enable NEW DIGIMON'
        e.gs('set', 'gametime_running=0')
        base = out / 'boot.state'; e.run('save', str(base))
        results = {'ram_bytes': len(e.ram()), 'expanded_ram': flow['8mb']}
        if a.case != 'evolution':
            results['chart'] = chart(e, out)
        if a.case != 'chart':
            results['evolution'] = moved_evolution(e, out, base)
        e.run('load', str(base)); e.run('pause')
        # Verify runtime table selection and explicit mode swaps both ways.
        e.poke('SPECIES_RAISED_BITS', b'\0' * 128)
        for t in (17, 18, 57):
            e.gs('trigger', str(0x200 + t), '0')
        e.gs('set', 'gametime_running=0', 'partner.para.careMistakes=0',
             'partner.para.battles=0', 'partner.para.weight=26',
             'partner.stats.hp=100', 'partner.stats.mp=100',
             'partner.stats.off=10', 'partner.stats.def=30',
             'partner.stats.speed=10', 'partner.stats.brain=10')
        weights = {}
        for mode in (0, 1):
            e.poke('MOD_OPT_NEW_DIGIMON', struct.pack('<i', mode))
            call(e, 'modApplySpeciesLevels')
            weights[str(mode)] = call(e, 'evoTargetWeight', 16, 17)
            assert weights[str(mode)] == (26 if mode else 15)
            path = e.peek('EVOLUTION_PATHS', '682h')
            assert (17 in path[15 * 11 + 5:16 * 11]) == bool(mode)
            assert (16 in path[16 * 11:16 * 11 + 5]) == bool(mode)
        assert call(e, 'getNaturalEvolutionTarget', 16) == 17
        e.gs('set', 'partner.para.weight=15')
        assert call(e, 'getNaturalEvolutionTarget', 16) == 57
        assert call(e, 'getNaturalEvolutionTarget', 2) == 17
        results['mode_weights'] = weights
        (out / f'results-{a.case}.json').write_text(json.dumps(results, indent=2) + '\n')
        print('ok: runtime mode-specific weights and native paths', flush=True)
    finally:
        e.stop()


if __name__ == '__main__':
    main()
