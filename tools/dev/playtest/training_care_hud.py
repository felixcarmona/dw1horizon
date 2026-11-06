#!/usr/bin/env python3
"""Capture live five-session gym care gauges on original-2-MB PCSX-Redux.

The pad ends only the first animation. Every session cost and intermediate frame
then comes from the native gym state machine. Observer breakpoints pause after
GPU refreshes so screenshots contain the newly drawn readings, not stale frames.
Requires Pillow; run with the project virtual environment.
"""
import argparse
import json
import os
from pathlib import Path
import struct
import subprocess
import sys
import time
from PIL import Image

ROOT = Path(__file__).resolve().parents[3]
sys.path[:0] = [str(ROOT), str(ROOT / 'tools')]
from tools.dev.playtest.qol import ProofEmu
from tools.dev.playtest.training_evolution import call, await_value
from tools.langpatch import elf_symbols
from tools.dev.game_state import PARTNER_PARA_FIELDS


def settle(e, frames=6):
    e.run('lua', f'''GH_SETTLE={{n=0,done=false}}
      GH_SETTLE.l=PCSX.Events.createEventListener('GPU::Vsync',function()
        GH_SETTLE.n=GH_SETTLE.n+1
        if GH_SETTLE.n=={frames} then GH_SETTLE.done=true;GH_SETTLE.l:remove();PCSX.pauseEmulator() end
      end)
      PCSX.resumeEmulator()''')
    end = time.monotonic() + 30
    while time.monotonic() < end:
        if e.run('lua', 'return GH_SETTLE.done').strip() == 'true':
            return
        time.sleep(.1)
    raise AssertionError('no GPU refreshes')


def care(e):
    ram = e.ram()
    off = e.A('PARTNER_PARA') & 0x1fffff
    out = {}
    for name, fmt in PARTNER_PARA_FIELDS:
        out[name] = struct.unpack_from('<' + fmt, ram, off)[0]
        off += struct.calcsize('<' + fmt)
    return {k: out[k] for k in ('tiredness', 'foodLevel', 'poopLevel', 'condition', 'evoTimer', 'careMistakes')}


def observer(e, prefix):
    e.run('lua', f'''GH={{count=0,left=0,paused=false}}
      GH.bp=PCSX.addBreakpoint({e.A(prefix + '_modBlockNext')},'Exec',4,'gym-care-award',function()
        GH.count=GH.count+1;GH.left=5
      end)
      GH.v=PCSX.Events.createEventListener('GPU::Vsync',function()
        if GH.left>0 then
          GH.left=GH.left-1
          if GH.left==0 then GH.paused=true;PCSX.pauseEmulator() end
        end
      end)''')


def checkpoint(e, count):
    end = time.monotonic() + 90
    while time.monotonic() < end:
        if e.run('lua', 'return GH.paused').strip() == 'true':
            got = int(e.run('lua', 'return GH.count').strip())
            assert got == count, (got, count)
            return
        time.sleep(.1)
    raise AssertionError(f'no session {count} checkpoint')


def unobserve(e):
    e.run('lua', 'if GH then GH.bp:remove();GH.v:remove();GH=nil end')


def fixture(e, base, screen, prefix, food=310, gym="Hp"):
    e.run('load', str(base)); e.run('resume')
    assert e.warp(screen), f'warp {screen}'
    e.poke('TRN_LOADING_COMPLETE', b'\0')
    call(e, 'loadTrainingLibrary', screen)
    e.run('resume')
    await_value(e, 'TRN_LOADING_COMPLETE', 'b', lambda n: n == 0)
    e.run('pause')
    e.gs('set', 'gametime_running=0', 'hour=10', 'minute=0',
         'partner.para.condition=0', 'partner.para.tiredness=14',
         f'partner.para.foodLevel={food}', 'partner.para.poopLevel=42',
         'partner.para.energyLevel=500', 'partner.para.evoTimer=0',
         'partner.para.age=1', 'partner.para.remainingLifetime=1000',
         'partner.para.sleepyHour=23', 'partner.para.sleepyMinute=0',
         'partner.para.virusBar=0', 'partner.para.happiness=80',
         'partner.para.discipline=80', 'partner.para.careMistakes=0')
    e.poke('CURRENT_FRAME', struct.pack('<H', 12000))
    e.poke('LAST_HANDLED_FRAME', struct.pack('<H', 12000))
    e.poke('MOD_OPT_BARS', struct.pack('<i', 1))
    if gym == 'Brains':
        e.gs('set', 'partner.stats.brain=99')
    # Same pstat consumed by the real "Normal training x5" menu row.
    call(e, 'writePStat', 246, 2)
    call(e, prefix + '_setup' + gym + 'Training', screen)
    e.run('resume')
    state = 'TRAINING_STATE' if prefix == 'TRN' else 'MAIN_D_801353BD'
    await_value(e, state, 'b', lambda n: n == (3 if gym == 'Brains' else 2))
    e.run('pause')
    settle(e)


def capture(e, out, name, screen, prefix, count=5, cancel=False, food=310, gym="Hp"):
    fixture(e, out / 'boot.state', screen, prefix, food, gym)
    result = {'name': name, 'screen': screen, 'prefix': prefix, 'frames': []}
    def shot(session):
        path = out / f'{name}-{session}.png'
        e.run('shot', str(path))
        row = {'session': session, 'file': path.name, 'care': care(e),
               'font': e.peek('MOD_FONT', 'b'), 'fps_mode': e.peek('MOD_FPS_MODE_RUN', 'i'),
               'hour': e.peek('HOUR', 'h')}
        result['frames'].append(row)
        print(json.dumps(row), flush=True)
    shot(0)
    if name == 'TRN-five':
        e.poke('MOD_OPT_BARS', struct.pack('<i', 0)); settle(e)
        e.run('shot', str(out / 'TRN-OFF-training.png'))
        e.poke('MOD_OPT_BARS', struct.pack('<i', 1)); settle(e)
    observer(e, prefix)
    # Manual override avoids a pad helper waiting for refreshes while the observer pauses.
    btn = 'CROSS' if e.peek('MOD_OPT_BUTTONS', 'i') else 'TRIANGLE'
    e.api('/api/v1/lua/press?button=' + btn)
    e.run('resume')
    try:
        for session in range(1, count + 1):
            checkpoint(e, session)
            e.api('/api/v1/lua/release?button=' + btn)
            shot(session)
            if session != count:
                e.run('lua', 'GH.paused=false;PCSX.resumeEmulator()')
    finally:
        e.api('/api/v1/lua/release?button=' + btn)
    if cancel:
        # A fresh press after completed session 2; no third award is allowed.
        e.run('lua', 'GH.paused=false')
        e.api('/api/v1/lua/press?button=' + btn)
        settle(e, 9)
        e.api('/api/v1/lua/release?button=' + btn)
        assert int(e.run('lua', 'return GH.count').strip()) == count
        assert e.peek(prefix + '_MOD_QUIET', 'b') == 0
    elif count < 5:
        assert e.peek(prefix + '_MOD_QUIET', 'b') == 0, 'native need stop failed'
    else:
        assert e.peek(prefix + '_MOD_QUIET', 'b') == 0, 'five-session block did not finish'
    unobserve(e)
    settle(e, 24)
    e.run('shot', str(out / f'{name}-tally.png'))
    result['final'] = care(e)
    assert result['final']['evoTimer'] == count
    drop = 60 if prefix == 'TRN' else 61
    for row in result['frames'][1:]:
        n = row['session']; c = row['care']
        assert c['evoTimer'] == n
        assert row['hour'] == 10 + n
        assert c['tiredness'] == 14 + 8*n
        assert c['foodLevel'] == food - drop*n
        assert c['poopLevel'] == 42 - 6*n
        assert c['careMistakes'] == 0
    # Observe the native tally skip and normal return, rather than leaving a gym object behind.
    e.run('resume')
    for _ in range(80):
        e.press('CONFIRM', 8); e.wait(.15)
        if e.peek('TAMER_STATE', 'b') == 0:
            break
    else:
        raise AssertionError('training failed to restore field control')
    e.run('lua', f'''GH_LIFE={{n=0}};GH_LIFE.bp=PCSX.addBreakpoint({e.A(prefix + '_renderCareHUD')},'Exec',4,'gym-hud-lifetime',function() GH_LIFE.n=GH_LIFE.n+1 end)''')
    settle(e, 9)
    assert e.run('lua', 'return GH_LIFE.n').strip() == '0', 'gym HUD callback survived the gym object'
    e.run('lua', 'GH_LIFE.bp:remove();GH_LIFE=nil')
    return result


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('disc'); ap.add_argument('--exe', required=True)
    ap.add_argument('--card', required=True); ap.add_argument('--out', default='build/gym-hud/runtime')
    ap.add_argument('--port', type=int, default=41967)
    ap.add_argument('--boot-state', type=Path)
    a = ap.parse_args()
    out = Path(a.out).resolve(); out.mkdir(parents=True, exist_ok=True)
    display = next(n for n in range(190, 230) if not Path(f'/tmp/.X11-unix/X{n}').exists())
    log = (out / 'xvfb.log').open('w')
    xvfb = subprocess.Popen(['Xvfb', f':{display}', '-screen', '0', '1024x768x24', '-nolisten', 'tcp'], stdout=log, stderr=log)
    e = ProofEmu(a.disc, a.exe, a.port, str(out / 'emu'))
    e.env.update(EMU_ARGS='-interpreter -debugger', DISPLAY=f':{display}')
    for name, (address, _, _) in elf_symbols(a.exe + '.elf').items():
        e.table.setdefault(name, address)
    try:
        time.sleep(1)
        e.start(a.card)
        if a.boot_state:
            e.run('load', str(a.boot_state.resolve())); e.run('resume')
        else:
            assert e.continue_game() == 0
            e.wait(5)
        assert len(e.ram()) == 2097152
        assert e.in_control()
        assert e.peek('PARTNER_ENTITY', 'i') == 3, 'supply an Agumon card'
        e.run('save', str(out / 'boot.state'))
        rows = []
        for prefix, screen, font, rate in [('TRN',112,0,1),('TRN2',99,2,2)]:
            e.run('load', str(out / 'boot.state'))
            call(e, 'modSetFont', font); e.poke('MOD_FPS_MODE_RUN', struct.pack('<i',rate))
            e.run('save', str(out / 'boot.state'))
            rows.append(capture(e,out,prefix+'-five',screen,prefix))
        rows.append(capture(e,out,'TRN-cancel-two',112,'TRN',count=2,cancel=True))
        rows.append(capture(e,out,'TRN-hunger-stop',112,'TRN',count=2,food=110))
        rows.append(capture(e,out,'TRN-new-orders',112,'TRN',count=1,gym='Brains'))
        for run in rows[:2]:
            previous_toilet = -1
            for row in run['frames']:
                im = Image.open(out / row['file']).convert('RGB')
                assert im.size == (320,240)
                fills = []
                for y in (191,205,219):
                    fills.append(sum(abs(im.getpixel((x,y))[0]-im.getpixel((x,y))[1])>20 for x in range(289,307)))
                fatigue = row['care']['tiredness']
                want_fatigue = max(1,(fatigue*18+50)//100)
                food = max(0,min(180,row['care']['foodLevel']))
                want_food = max(1,(food*18+90)//180) if food else 0
                assert fills[0] == want_food, (row,fills,want_food)
                assert fills[2] == want_fatigue, (row,fills,want_fatigue)
                assert fills[1] >= previous_toilet, (row,fills)
                previous_toilet = fills[1]
                row['visible_fill_pixels'] = dict(zip(('hunger','toilet','tiredness'),fills))
        (out/'result.json').write_text(json.dumps({'ram_bytes':2097152,'runs':rows},indent=2)+'\n')
        print('PASS: 2 MB, both gym overlays, live five-session frames, cancel and native hunger stop',flush=True)
    finally:
        e.stop(); xvfb.terminate(); xvfb.wait(timeout=10); log.close()


if __name__ == '__main__':
    main()
