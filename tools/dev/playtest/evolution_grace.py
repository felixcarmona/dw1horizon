#!/usr/bin/env python3
"""Prove due Rookie evolution during post-load death protection on 2 MB.

Setup loads real partner models and supplies eligible stats. The fixture uses
the engine's save-load grace setter to stage load/wake protection; target
selection and evolution then run in the field tick.
--before expects the original block, then clears only grace as a control.
"""
import argparse
import json
from pathlib import Path
import struct
import sys
import time

ROOT = Path(__file__).resolve().parents[3]
sys.path[:0] = [str(ROOT), str(ROOT / 'tools')]
from tools.dev.playtest.food_sickness import emulator, fixture
from tools.dev.playtest.birdramon_recruitment import field_card
from tools.dev.playtest.training_evolution import call


def eligibility(e, species):
    ptr = call(e, 'getEvolutionPath', species)
    path = struct.unpack_from('<11h', e.ram(), ptr - 0x80000000)[5:]
    qualified = []
    for target in path:
        if target < 0:
            continue
        req = (e.A('EVOLUTION_REQS') + 28 * target if target < 180
               else call(e, 'getSpeciesEvoReqs', target))
        flags = e.ram()[req - 0x80000000 + 26]
        met = call(e, 'evoRequirementsMet', species, target, (flags >> 4) & 1, flags & 1)
        if met.bit_count() >= 3 and call(e, 'modSpeciesAllowed', target):
            qualified.append(target)
    target = call(e, 'getNaturalEvolutionTarget', species)
    e.run('resume')
    return qualified, target


def watch(e):
    a = e.A
    e.run('lua', f'''
if EVOP then for _,b in ipairs(EVOP.bp) do b:remove() end end
EVOP={{bp={{}},calls=0,target=-1,applied=0}}
local function hook(a,f) local b=PCSX.addBreakpoint(a,'Exec',4,'evolution-grace-proof',f);EVOP.bp[#EVOP.bp+1]=b;return b end
hook({a('rollNaturalEvolutionTarget' if e.has('rollNaturalEvolutionTarget') else 'getNaturalEvolutionTarget')},function()
 EVOP.calls=EVOP.calls+1
 local b;b=hook(PCSX.getRegisters().GPR.n.ra,function() EVOP.target=PCSX.getRegisters().GPR.n.v0;b:remove() end)
end)
hook({a('EVL_applyEvolution')},function() EVOP.applied=EVOP.applied+1 end)
''')


def finish_evolution(e, target):
    for _ in range(100):
        ram = e.ram()
        if e.peek('PARTNER_ENTITY', 'i', ram) == target and e.peek('PARTNER_STATE', 'b', ram) == 1:
            e.poke('PAUSE_STATE', b'\0')
            for _ in range(6):
                if not e.peek('IS_IN_MENU', 'b'):
                    break
                e.press('CANCEL', 12)
                e.wait(.2)
            assert e.in_control() and not e.peek('IS_IN_MENU', 'b'), 'evolution did not restore field control'
            return
        if e.peek('MOD_EVO_SKIP', 'b') == 3:
            e.press('START', 8)
        elif e.peek('TAMER_STATE', 'b') == 20:
            e.press('CONFIRM', 8)
        e.poke('PAUSE_STATE', b'\0')
        e.wait(.25)
    raise AssertionError(f'natural evolution into {target} did not finish')


def case(e, state, out, species, enabled, before):
    fixture(e, state, species)
    e.poke('MOD_OPT_NEW_DIGIMON', struct.pack('<i', enabled))
    call(e, 'modApplySpeciesLevels')
    e.run('resume')
    # Load a clear field before staging the care state.
    assert e.warp(1), 'File City did not load'
    care, weight = {4: (0, 40), 285: (3, 20), 354: (0, 20), 433: (3, 25)}.get(species, (0, 30))
    e.gs('set', 'gametime_running=0', 'hour=10', 'minute=0', 'partner.para.age=6',
         'partner.para.evoTimer=71', 'partner.para.condition=0', 'partner.para.remainingLifetime=1000',
         'partner.para.tiredness=0', 'partner.para.foodLevel=1000', 'partner.para.energyLevel=100',
         'partner.para.poopLevel=100', 'partner.para.virusBar=0', f'partner.para.weight={weight}',
         f'partner.para.careMistakes={care}', 'partner.para.happiness=100', 'partner.para.discipline=100',
         'partner.para.battles=100', *[f'partner.stats.{s}={9000 if s in ("hp","mp") else 900}'
                                      for s in ('hp','mp','off','def','speed','brain')])
    # Arm the load/wake protection at the fixture's hour through its engine setter.
    call(e, 'setImmortalHour'); e.run('resume')
    qualified, target = eligibility(e, species)
    assert len(qualified) >= 2, f'{species}: fewer than two eligible targets: {qualified}'
    if species == 4:
        assert (238 if enabled else 24) in qualified, 'Dolphmon/Whamon active route was lost'
        assert (24 if enabled else 238) not in qualified, 'inactive mode target remained eligible'
    assert target != 0xffffffff and target in qualified, (species, qualified, target)
    assert e.peek('HAS_IMMORTAL_HOUR', 'i') == 1
    assert e.peek('IMMORTAL_HOUR', 'b') == e.peek('HOUR', 'h')
    watch(e)
    # The same load/wake grace must still prevent a zero-lifetime death.
    e.gs('set', 'partner.para.remainingLifetime=0', 'gametime_running=1')
    e.wait(2)
    assert e.peek('PARTNER_ENTITY','i') == species and e.peek('PARTNER_STATE','b') == 1, 'evolved before 72 hours'
    assert e.peek('IS_SCRIPT_PAUSED', 'i') == 1 and e.peek('TAMER_STATE', 'b') == 0, 'death protection was lost'
    e.gs('set', 'partner.para.remainingLifetime=1000', 'partner.para.evoTimer=114')
    label = f'{species}-new{enabled}'
    e.wait(3)
    calls = int(e.run('lua', 'return EVOP.calls').strip())
    if before:
        assert calls == 0 and e.peek('PARTNER_STATE','b') == 1, 'expected grace-hour evolution block'
        e.run('shot', str(out / (label + '-blocked.png')))
        # Identical eligible partner, clearing only protection, proves the gate.
        e.poke('HAS_IMMORTAL_HOUR', struct.pack('<i', 0))
    if not before:
        target = int(e.run('lua', 'return EVOP.target').strip()) & 0xffffffff
        assert target in qualified, ('non-qualifying evolution', target, qualified)
    finish_evolution(e, target)
    assert int(e.run('lua','return EVOP.applied').strip()) == 1
    e.gs('set', 'gametime_running=0')
    e.run('shot', str(out / (label + '-evolved.png')))
    result = dict(species=species, new_digimon=enabled, age=6, evo_timer=114,
                  qualified=qualified, chosen=target, blocked_by_grace=before,
                  natural_calls_during_grace=calls, death_protected_during_grace=True, final_species=e.peek('PARTNER_ENTITY','i'),
                  timer_after=e.gs('show','partner.para.evoTimer').strip())
    print(json.dumps(result), flush=True)
    return result


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('disc'); p.add_argument('--exe', required=True)
    p.add_argument('--out', type=Path, required=True); p.add_argument('--port',type=int,default=39343)
    p.add_argument('--species', default='3,180,285,354,433');p.add_argument('--before',action='store_true')
    p.add_argument('--mode-swaps',action='store_true',help='also check the current Dolphmon/Whamon mode routes')
    a=p.parse_args();out=a.out.resolve();out.mkdir(parents=True,exist_ok=True)
    e=emulator(a.disc,a.exe,a.port,out);results=[]
    try:
        card=field_card(str(ROOT/'tools/dev/saves/corpus/20261027-d2796814.mcd'),str(out/'fixture.mcd'))
        e.start(card);assert e.continue_game()==0
        e.gs('set','gametime_running=0');state=out/'base.state';e.run('save',str(state))
        assert len(e.ram())==0x200000
        species_list=list(map(int,a.species.split(','))) + ([4] if a.mode_swaps else [])
        for species in dict.fromkeys(species_list):
            results.append(case(e,state,out,species,1,a.before))
        for species in ((3, 4) if a.mode_swaps else (3,)):
            results.append(case(e,state,out,species,0,a.before))
    finally:
        (out/'result.json').write_text(json.dumps(dict(ram_bytes=0x200000,before=a.before,cases=results),indent=2)+'\n')
        e.stop()


if __name__=='__main__':
    main()
