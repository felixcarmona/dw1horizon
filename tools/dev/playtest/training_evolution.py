#!/usr/bin/env python3
"""Exercise x5 evolution stops on a built disc in an original-2-MB PCSX-Redux.

Uses real partner models, the HP gym state machine and triangle to end its first
animation. Pokes care/stats only to isolate evolution from other stop reasons.
Artifacts and screenshots stay under --out. No disc rules or targets are changed.
"""
import argparse
from pathlib import Path
import struct
import sys
import time

ROOT = Path(__file__).resolve().parents[3]
sys.path[:0] = [str(ROOT), str(ROOT / 'tools')]
from tools.langpatch import elf_symbols
from tools.dev.playtest.qol import ProofEmu, test_card


def call(e, name, *args):
    """Call at gameLoop, then pause at its return before the next game tick."""
    gl = e.A('gameLoop')
    observe = ''
    if name in ('getNaturalEvolutionTarget', 'modTrainStopReason'):
        observe = f"TE_CALL.rngbp=PCSX.addBreakpoint({e.A('randomLimit')},'Exec',4,'preview-random',function() if TE_CALL.phase==1 then TE_CALL.rng=TE_CALL.rng+1 end end)"
    regs = '\n'.join(f'r.GPR.n.a{i}={v & 0xffffffff}' for i, v in enumerate(args))
    e.run('lua', f'''
      local function care()
        local m=PCSX.getMemPtr(); local t={{}}
        for i=0,131 do t[#t+1]=string.char(m[{e.A('PARTNER_PARA') & 0x1fffff}+i]) end
        return table.concat(t)
      end
      TE_CALL={{done=false,phase=0,rng=0,diff=''}}
      {observe}
      TE_CALL.bp=PCSX.addBreakpoint({gl},'Exec',4,'training-proof',function()
        local r=PCSX.getRegisters()
        if TE_CALL.phase==0 then
          TE_CALL.ra=r.GPR.n.ra; TE_CALL.care=care()
          {regs}
          r.GPR.n.ra={gl}; r.pc={e.A(name)}; TE_CALL.phase=1
        else
          local after=care(); local diff={{}}
          for i=1,132 do if TE_CALL.care:byte(i)~=after:byte(i) then diff[#diff+1]=tostring(i-1) end end
          TE_CALL.diff=table.concat(diff,',')
          TE_CALL.result=r.GPR.n.v0; r.GPR.n.ra=TE_CALL.ra
          TE_CALL.done=true; TE_CALL.bp:remove()
          if TE_CALL.rngbp then TE_CALL.rngbp:remove() end
          PCSX.pauseEmulator()
        end
      end)
      PCSX.resumeEmulator()
    ''')
    for _ in range(300):
        if e.run('lua', 'return TE_CALL.done').strip() == 'true':
            assert e.run('lua', 'return TE_CALL.rng').strip() == '0', f'{name} rolled randomness'
            if observe:
                diff = e.run('lua', 'return TE_CALL.diff').strip()
                assert not diff, f'{name} changed care bytes {diff}'
            return int(e.run('lua', 'return TE_CALL.result').strip()) & 0xffffffff
        time.sleep(.1)
    raise AssertionError(f'{name} did not return')


def await_value(e, symbol, fmt, predicate, seconds=90):
    end = time.monotonic() + seconds
    while time.monotonic() < end:
        value = e.peek(symbol, fmt)
        if predicate(value):
            return value
        time.sleep(.25)
    raise AssertionError(f'{symbol} stayed at {value}')


def prepare(e, base, species, timer, strong):
    e.run('load', str(base))
    # Stage a fixture evolution so the game's loader installs the matching model.
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
        raise AssertionError(f'fixture model {species} did not load')
    e.poke('PAUSE_STATE', b'\0')
    assert e.warp(112), 'HP gym did not load'
    e.wait(2)
    e.poke('TRN_LOADING_COMPLETE', b'\0')
    call(e, 'loadTrainingLibrary', 112)
    e.run('resume')
    await_value(e, 'TRN_LOADING_COMPLETE', 'b', lambda n: n == 0)
    e.run('pause')
    e.gs('set', 'gametime_running=0', 'hour=10', 'minute=0',
         f'partner.para.evoTimer={timer}', 'partner.para.condition=0',
         'partner.para.remainingLifetime=1000', 'partner.para.tiredness=0',
         'partner.para.foodLevel=1000', 'partner.para.poopLevel=100',
         'partner.para.energyLevel=100', 'partner.para.sleepyHour=23',
         'partner.para.sleepyMinute=0', 'partner.para.virusBar=0',
         f'partner.para.careMistakes={0 if strong else 100}',
         f'partner.para.weight={30 if strong else 1}',
         f'partner.para.happiness={100 if strong else 0}',
         f'partner.para.discipline={100 if strong else 0}', 'partner.para.battles=0',
         *[f'partner.stats.{s}={9000 if strong and s in ("hp", "mp") else 900 if strong else 1}'
           for s in ('hp', 'mp', 'off', 'def', 'speed', 'brain')])
    e.poke('CURRENT_FRAME', struct.pack('<H', 12000))
    e.poke('LAST_HANDLED_FRAME', struct.pack('<H', 12000))
    e.poke('PARTNER_ENTITY+0x58', bytes([255 if strong else 0]) * 16)
    e.poke('EVOLUTION_TARGET', struct.pack('<h', -1))
    assert e.peek('PARTNER_ENTITY', 'i') == species, 'fixture changed species during warp'


def block(e, out, label, timer, count, expected_target):
    # The setup reads the same x5 flag as the real menu.
    call(e, 'writePStat', 246, 2)
    call(e, 'TRN_setupHpTraining', 112)
    e.run('lua', 'PCSX.resumeEmulator()')
    await_value(e, 'TRAINING_STATE', 'b', lambda n: n == 2)
    e.press('TRIANGLE', 10)
    await_value(e, 'TRAINING_STATE', 'b', lambda n: n == 3)
    e.run('pause')
    got = e.peek('PARTNER_PARA+0x56', 'h') - timer
    assert got == count, f'{label}: {got}/5 sessions, expected {count}/5'
    shot = out / f'{label}-stats.png'
    e.run('shot', str(shot))
    e.run('shot', str(out / f'{label}-paused.png'))
    assert shot.read_bytes() == (out / f'{label}-paused.png').read_bytes(), 'pause was not stable'
    print(f'ok {label}: {got}/5 sessions, evoTimer {timer} -> {timer + got}', flush=True)
    e.run('resume')
    # Close the stats box and let the real field tick take the decision.
    for _ in range(100):
        e.press('CONFIRM', 8)
        e.wait(.3)
        if e.peek('TAMER_STATE', 'b') == 0:
            break
    else:
        raise AssertionError(f'{label}: training did not return field control')
    if expected_target != -1:
        e.gs('set', 'gametime_running=1')
        for _ in range(180):
            if e.peek('PARTNER_ENTITY', 'i') == expected_target and e.peek('PARTNER_STATE', 'b') == 1:
                break
            e.press('START', 8)
            e.wait(.25)
        else:
            raise AssertionError(f'{label}: did not evolve to {expected_target}')
        e.run('shot', str(out / f'{label}-evolved.png'))
        print(f'ok {label}: field tick really evolved to {expected_target}', flush=True)


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('disc'); p.add_argument('--exe', required=True)
    p.add_argument('--out', default='build/training-evolution')
    p.add_argument('--boot-state', type=Path, help='control checkpoint from this exact disc')
    p.add_argument('--port', type=int, default=39186)
    a = p.parse_args()
    out = Path(a.out).resolve(); out.mkdir(parents=True, exist_ok=True)
    e = ProofEmu(a.disc, a.exe, a.port, str(out / 'emu'))
    e.env['EMU_ARGS'] = '-interpreter -debugger'
    for name, (address, _, _) in elf_symbols(a.exe + '.elf').items():
        e.table.setdefault(name, address)
    try:
        e.start(test_card(out))
        if a.boot_state:
            e.run('load', str(a.boot_state.resolve())); e.run('resume')
        else:
            assert e.continue_game() == 0, 'Continue failed'
            e.wait(5)
        assert len(e.ram()) == 2 * 1024 * 1024
        assert e.in_control(), 'no field control'
        e.gs('set', 'gametime_running=0')
        base = out / 'boot.state'; e.run('save', str(base))
        for label, species, timer, strong, count in (
            ('champion-no-target', 227, 143, False, 5),
            ('rookie-no-target', 3, 80, False, 5),
            ('rookie-qualified', 3, 71, True, 1),
            ('rookie-fallback', 3, 95, False, 1),
        ):
            prepare(e, base, species, timer, strong)
            e.poke('PARTNER_PARA+0x56', struct.pack('<h', timer + 1))
            target = call(e, 'getNaturalEvolutionTarget', species)
            target = target - 0x100000000 if target >= 0x80000000 else target
            assert (target != -1) == (count == 1), f'{label}: fixture target {target}'
            assert call(e, 'getNaturalEvolutionTarget', species) == target & 0xffffffff
            e.poke('PARTNER_PARA+0x56', struct.pack('<h', timer))
            block(e, out, label, timer, count, target)

        prepare(e, base, 1, 6, False)
        for _ in range(2):
            assert call(e, 'getNaturalEvolutionTarget', 1) == 2
            assert call(e, 'modTrainStopReason', 600, 70) == 6
            assert e.peek('PARTNER_PARA+0x56', 'h') == 6, 'Fresh preview reset its timer'
        for timer, reason in ((5, 0), (7, 6)):
            e.poke('PARTNER_PARA+0x56', struct.pack('<h', timer))
            assert call(e, 'modTrainStopReason', 600, 70) == reason
        print('ok Fresh: previews preserve timer; below/at/past due checks pass', flush=True)

        prepare(e, base, 54, 48, True)
        assert call(e, 'getNaturalEvolutionTarget', 54) == 115
        assert call(e, 'modTrainStopReason', 600, 70) == 6
        e.poke('PARTNER_PARA+0x56', struct.pack('<h', 49))
        assert call(e, 'getNaturalEvolutionTarget', 54) == 115
        assert call(e, 'modTrainStopReason', 600, 70) == 0
        print('ok Ultimate: Machinedramon pair; stop only at the due hour', flush=True)
    finally:
        e.stop()


if __name__ == '__main__':
    main()
