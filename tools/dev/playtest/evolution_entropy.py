#!/usr/bin/env python3
"""Replay ONE 2 MB field savestate with twelve human-scale pad timing patterns.

The card, stats and requirement fixtures come from evolution_random.py. Only the
last evolution hour and clock enable are written after each input sequence. No
RNG, root counter, entropy pool or target is written. Lua breakpoints observe the
actual C timer reads and pool updates. Two no-input replays check determinism.
"""
import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path
import sys
import time

ROOT = Path(__file__).resolve().parents[3]
sys.path[:0] = [str(ROOT), str(ROOT / 'tools')]
from tools.dev.playtest.evolution_random import card_fixture, continue_from_title, watch, timer_read_site
from tools.dev.playtest.food_sickness import emulator
from tools.dev.playtest.training_evolution import call
from tools.dev.playtest.evolution_grace import finish_evolution


def observe(e):
    watch(e)
    hooks = []
    for function in ('mixEvolutionInput', 'chooseQualifiedEvolution'):
        site, reg0, reg2 = timer_read_site(e, function)
        hooks.append(f'''
          hook({site},function()
            local r=PCSX.getRegisters().GPR.n
            local m=PCSX.getMemPtr();local p={e.A('Vcount') & 0x1fffff}
            local refresh=m[p]+256*m[p+1]+65536*m[p+2]+16777216*m[p+3]
            ET.reads[#ET.reads+1]={{timer0=r.{reg0},timer2=r.{reg2},
              refresh=refresh,at_roll=RP.active}}
            if not RP.active then ET.presses=ET.presses+1 end
          end)
        ''')
    e.run('lua', '''
      ET={bp={},reads={},presses=0}
      local function hook(a,f)
        local b=PCSX.addBreakpoint(a,'Exec',4,'evolution-entropy-proof',f)
        ET.bp[#ET.bp+1]=b;return b
      end
    ''' + '\n'.join(hooks))


def inputs(e, trial):
    # Replay at exact refresh offsets so identical-input controls can be repeated.
    pattern = [] if trial is None else [(18 + trial * 7, 'L2'),
                (120 + trial * 3, 'L2'), (200 + trial * 2, 'L2')]
    if trial == 1:
        pattern = [(19, 'L2'), (120, 'L2'), (200, 'L2')]
    starts = ';'.join(f"if S.n=={at} then pad.setOverride(B.{key}) end;"
                      f"if S.n=={at+24} then pad.clearOverride(B.{key}) end"
                      for at, key in pattern)
    e.run('lua', f'''
      S={{n=0,done=false}}
      local pad=PCSX.SIO0.slots[1].pads[1];local B=PCSX.CONSTS.PAD.BUTTON
      S.listener=PCSX.Events.createEventListener('GPU::Vsync',function()
        S.n=S.n+1;{starts}
        if S.n==260 then S.done=true;S.listener:remove();PCSX.pauseEmulator() end
      end)
      PCSX.resumeEmulator()
    ''')
    deadline = time.monotonic() + 45
    while e.run('lua', 'return S.done').strip() != 'true':
        assert time.monotonic() < deadline, 'input sequence did not finish'
        e.wait(.1)
    return pattern


def roll(e):
    e.gs('set', 'partner.para.evoTimer=72', 'gametime_running=1')
    e.run('resume')
    deadline = time.monotonic() + 45
    while e.run('lua', 'return RP.done').strip() != 'true':
        assert time.monotonic() < deadline, 'natural evolution did not roll'
        e.wait(.1)
    row = {k: int(e.run('lua', 'return RP.' + k).strip())
           for k in ('chosen', 'raw', 'refresh')}
    row['pool'] = e.peek('evolutionEntropy', 'I')
    row['transitions'] = int(e.run('lua', 'return ET.presses').strip())
    raw = e.run('lua', "local rows={};for _,v in ipairs(ET.reads) do rows[#rows+1]=string.format('%d,%d,%d,%d',v.timer0,v.timer2,v.refresh,v.at_roll and 1 or 0) end;return table.concat(rows,';')")
    row['timer_reads'] = [dict(zip(('timer0', 'timer2', 'refresh', 'at_roll'),
                                  map(int, part.split(',')))) for part in raw.strip().split(';')]
    e.run('lua', 'for _,b in ipairs(ET.bp) do b:remove() end')
    assert row['chosen'] in (234, 222), row
    assert row['timer_reads'] and row['timer_reads'][-1]['at_roll'], row
    assert all(0 <= r[k] <= 65535 for r in row['timer_reads']
               for k in ('timer0', 'timer2')), row
    return row


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('disc'); p.add_argument('--exe', required=True)
    p.add_argument('--out', type=Path, required=True)
    p.add_argument('--port', type=int, default=39454)
    p.add_argument('--state', type=Path, help='reuse a compatible idle field checkpoint')
    a = p.parse_args(); out = a.out.resolve(); out.mkdir(parents=True, exist_ok=True)
    card = out / 'salamon.mcd'; digest = card_fixture(card)
    e = emulator(a.disc, a.exe, a.port, out)
    rows, controls = [], []
    state_digest = None
    try:
        e.start(str(card))
        if a.state:
            state = a.state.resolve()
            e.run('pause'); e.run('load', str(state))
            # Save states contain code: reject a checkpoint from another build.
            from tools.xref import Elf
            from tools.langpatch import elf_symbols
            elf = Elf(e.exe + '.elf'); symbols = elf_symbols(e.exe + '.elf')
            ram = e.ram()
            for function in ('mixEvolutionInput', 'chooseQualifiedEvolution', 'pollInput'):
                start, size, _ = symbols[function]
                section = next(s for s in elf.sh if s['addr'] <= start < s['addr'] + s['size'])
                at = section['off'] + start - section['addr']
                assert ram[start & 0x1fffff:(start & 0x1fffff) + size] == elf.d[at:at + size], function
            assert e.peek('PARTNER_ENTITY', 'i', ram) == 221
            assert e.peek('IS_GAMETIME_RUNNING', 'b', ram) == 0
        else:
            e.to_title(); continue_from_title(e)
            e.run('pause')
            e.gs('set', 'gametime_running=0')
            assert call(e, 'getNaturalEvolutionTarget', 221) == 234
            # An immediate checkpoint can retain card/SIO work that suppresses pad polls.
            e.run('resume'); e.wait(12); e.run('pause')
            state = out / 'one-field.state'; e.run('save', str(state))
        assert len(e.ram()) == 0x200000
        assert not json.loads(e.api('/api/v1/execution-flow'))['8mb']
        state_digest = hashlib.sha256(state.read_bytes()).hexdigest()
        for trial in [None, None, *range(12)]:
            e.run('pause')
            e.run('load', str(state))
            initial_pool = e.peek('evolutionEntropy', 'I')
            observe(e)
            started = time.monotonic()
            pattern = inputs(e, trial)
            elapsed = time.monotonic() - started
            row = roll(e)
            row.update(trial=trial, pattern=pattern, initial_pool=initial_pool)
            if trial is None:
                controls.append(row)
                # The no-input path has no pool updates and must replay exactly.
                assert row['transitions'] == 0 and row['pool'] == initial_pool
                print('CONTROL', json.dumps(row), flush=True)
                continue
            row['wait_wall_seconds'] = round(elapsed, 3)
            assert row['transitions'] == 6, row
            assert row['pool'] != initial_pool, row
            e.run('resume'); finish_evolution(e, row['chosen'])
            e.gs('set', 'gametime_running=0'); e.wait(.3)
            row['final_species'] = e.peek('PARTNER_ENTITY', 'i')
            assert row['final_species'] == row['chosen']
            e.run('shot', str(out / f'evolution-{trial+1}.png'))
            rows.append(row); print('TRIAL', json.dumps(row), flush=True)
            assert hashlib.sha256(Path(e.card_out()).read_bytes()).hexdigest() == digest
        # Redux can restore timer 0's sub-cycle phase a few ticks apart.
        # Check the unchanged RAM pool and RNG; retain the actual timer reads.
        assert all(controls[0][key] == controls[1][key]
                   for key in ('raw', 'refresh', 'pool', 'transitions', 'initial_pool')), controls
        assert len({r['pool'] for r in rows}) == 12
        distribution = Counter(r['chosen'] for r in rows)
        assert len(distribution) == 2, distribution
        assert len({v['timer2'] for r in rows for v in r['timer_reads']}) > 12
        assert hashlib.sha256(state.read_bytes()).hexdigest() == state_digest
        assert e.warp(207), 'screen 207 failed on original 2 MB'
        e.run('shot', str(out / 'screen-207.png'))
        print('PASS: one unchanged savestate, 12 timings, completed evolutions:', dict(distribution), flush=True)
    finally:
        (out / 'result.json').write_text(json.dumps(dict(ram_bytes=0x200000,
            card_sha256=digest, checkpoint_sha256=state_digest, controls=controls, cases=rows,
            distribution=dict(Counter(r['chosen'] for r in rows))), indent=2) + '\n')
        e.stop()


if __name__ == '__main__':
    main()
