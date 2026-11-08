#!/usr/bin/env python3
"""Compare normal and x5 HP training, observing every native award at 2 MB.

Only fixture care/stats and the menu's selection flag are set. The first animation
is skipped with the native cancel button; awards, accumulation, tally and field
return run through the unchanged gym state machine.
"""
import argparse
import json
from pathlib import Path
import struct
import sys
import time

ROOT = Path(__file__).resolve().parents[3]
sys.path[:0] = [str(ROOT), str(ROOT / 'tools')]
from tools.dev.playtest.qol import ProofEmu, test_card
from tools.dev.playtest.training_care_hud import fixture, settle, care
from tools.dev.playtest.frigimon_recruitment import fixture_partner
from tools.langpatch import elf_symbols


def stats(e):
    ram = e.ram()
    base = e.A('PARTNER_ENTITY') & 0x1fffff
    return [struct.unpack_from('<h', ram, base + off)[0]
            for off in (0x48, 0x4a, 0x38, 0x3a, 0x3c, 0x3e)]


def six(e, symbol):
    return list(e.peek(symbol, '6h'))


def wait_flag(e, name):
    end = time.monotonic() + 90
    while time.monotonic() < end:
        if e.run('lua', f'return GG.{name}').strip() == 'true':
            return
        time.sleep(.1)
    raise AssertionError(f'no gym breakpoint: {name}')


def run(e, out, prefix, screen, sessions):
    fixture(e, out/'boot.state', screen, prefix, sessions=sessions)
    e.gs('set', 'partner.stats.hp=1000', 'partner.stats.mp=1000',
         'partner.stats.currentHP=1000', 'partner.stats.currentMP=1000',
         'partner.stats.off=100', 'partner.stats.def=100',
         'partner.stats.speed=100', 'partner.stats.brain=100')
    before = stats(e)
    label = f'{prefix}-x{sessions}'
    e.run('shot', str(out/f'{label}-before.png'))
    # Entry observes the award's actual gain; return observes its application.
    e.run('lua', f'''GG={{entry=false,returned=false,count=0}}
      GG.bp=PCSX.addBreakpoint({e.A(prefix+'_modBlockNext')},'Exec',4,'gym-gain-entry',function()
        GG.count=GG.count+1;GG.entry=true;GG.returned=false
        local ret=PCSX.getRegisters().GPR.n.ra
        GG.ret=PCSX.addBreakpoint(ret,'Exec',4,'gym-gain-return',function()
          GG.ret:remove();GG.returned=true;PCSX.pauseEmulator()
        end)
        PCSX.pauseEmulator()
      end)''')
    button = 'CROSS' if e.peek('MOD_OPT_BUTTONS', 'i') else 'TRIANGLE'
    e.api('/api/v1/lua/press?button='+button)
    e.run('resume')
    awards = []
    total = [0]*6
    try:
        for n in range(1, sessions+1):
            wait_flag(e, 'entry')
            e.api('/api/v1/lua/release?button='+button)
            assert int(e.run('lua', 'return GG.count').strip()) == n
            initial = six(e, 'INITIAL_COMBAT_STATS')
            gain = six(e, 'STATS_GAINS')
            assert initial == [a+b for a,b in zip(before,total)], (label,n,initial,total)
            assert gain[0] > 0, (label,n,gain)
            total = [a+b for a,b in zip(total,gain)]
            e.run('lua', 'GG.entry=false;PCSX.resumeEmulator()')
            wait_flag(e, 'returned')
            applied = stats(e)
            pending = six(e, 'STATS_GAINS')
            if n < sessions:
                assert applied == [a+b for a,b in zip(before,total)], (label,n,applied,total)
                assert pending == [0]*6
            else:
                # The final box rewinds the base for its animated aggregate tally.
                assert [a+b for a,b in zip(six(e,'INITIAL_COMBAT_STATS'),pending)] == [a+b for a,b in zip(before,total)]
            row = dict(session=n,initial=initial,gain=gain,partner_after_return=applied,
                       pending_tally=pending,care=care(e))
            awards.append(row)
            print(json.dumps(dict(run=label,**row)),flush=True)
            settle(e,6)
            e.run('shot',str(out/f'{label}-session-{n}.png'))
            if n < sessions:
                e.run('resume')
        assert e.peek(prefix+'_MOD_QUIET','b') == 0
    finally:
        e.api('/api/v1/lua/release?button='+button)
        e.run('lua','GG.bp:remove();if GG.ret then GG.ret:remove() end')
    e.run('resume')
    # Finish the native aggregate tally with a single fresh confirm press.
    for _ in range(200):
        if e.peek('UI_BOX_DATA+54','h') == 1:
            e.run('pause')
            e.run('shot', str(out/f'{label}-tally.png'))
            e.run('resume')
            e.press('CONFIRM',12)
            break
        e.wait(.1)
    for _ in range(300):
        if e.peek('TAMER_STATE','b') == 0:
            break
        e.wait(.1)
    else:
        raise AssertionError(f'{label}: field control did not return')
    e.run('pause')
    after = stats(e)
    assert after == [a+b for a,b in zip(before,total)], (label,after,total)
    assert care(e)['evoTimer'] == sessions
    e.run('shot',str(out/f'{label}-after.png'))
    return dict(label=label,screen=screen,before=before,awards=awards,total=total,after=after)


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('disc');p.add_argument('--exe',required=True)
    p.add_argument('--out',type=Path,required=True);p.add_argument('--port',type=int,default=39717)
    p.add_argument('--boot-state',type=Path,help='same-image field state for a repeat run')
    a=p.parse_args();out=a.out.resolve();out.mkdir(parents=True,exist_ok=True)
    e=ProofEmu(a.disc,a.exe,a.port,str(out/'emu'))
    e.env['EMU_ARGS']='-interpreter -debugger'
    for name,(address,_,_) in elf_symbols(a.exe+'.elf').items():e.table.setdefault(name,address)
    try:
        e.start(test_card(out))
        if a.boot_state:
            e.run('load',str(a.boot_state.resolve()));e.run('resume')
            assert e.in_control()
        else:
            assert e.continue_game()==0
        assert len(e.ram())==2097152
        if e.peek('PARTNER_ENTITY','i') != 3:
            fixture_partner(e, 3)
        e.run('save',str(out/'boot.state'))
        runs=[]
        for prefix,screen in [('TRN',112),('TRN2',99)]:
            single=run(e,out,prefix,screen,1)
            five=run(e,out,prefix,screen,5)
            assert five['awards'][0]['gain']==single['total']
            assert five['total']==[v*5 for v in single['total']], (single,five)
            runs.extend([single,five])
        (out/'result.json').write_text(json.dumps(dict(ok=True,ram_bytes=2097152,
             stat_order=['hp','mp','off','def','speed','brain'],runs=runs),indent=2)+'\n')
        print('PASS: single versus x5, every award accumulates, both gyms, 2 MB',flush=True)
    finally:
        e.stop()


if __name__=='__main__':main()
