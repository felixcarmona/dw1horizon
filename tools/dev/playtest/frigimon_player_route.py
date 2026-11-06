#!/usr/bin/env python3
"""Acquire illness through food or a disliked climate, then recruit Frigimon.

Inventory, care, species and initial location are fixtures. Food rolls, elapsed
climate exposure, rescue, conversation and recruitment run through the game.
No illness, recruitment success or random result is injected. Field triggers
dispatch the scenes; setup clears the rescue and recruit flags.
"""
import argparse
import json
from pathlib import Path
import struct
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parents[3]
sys.path[:0] = [str(ROOT), str(ROOT / 'tools')]
from tools.dev.playtest.food_sickness import emulator, fixture, setup_food, open_menu
from tools.dev.playtest.frigimon_recruitment import fixture_partner, dialogue
from tools.dev.playtest.birdramon_recruitment import field_card, bit
from tools.dev.playtest.training_evolution import call
from tools.dev.game_state import PARTNER_PARA_FIELDS


def para(e, key, ram):
    offset = 0
    for name, fmt in PARTNER_PARA_FIELDS:
        if name == key:
            return e.peek(f"PARTNER_PARA+{offset}", fmt, ram)
        offset += struct.calcsize("<" + fmt)
    raise KeyError(key)


def watch(e):
    e.run('lua', f'''
FRPLAYER={{bp={{}},food=0,returned=0,ending=0,rolls={{}}}}
local function hook(a,f) FRPLAYER.bp[#FRPLAYER.bp+1]=PCSX.addBreakpoint(a,'Exec',4,'frigimon-player',f) end
hook({e.A('handleItemSickness')},function()
 FRPLAYER.food=FRPLAYER.food+1
 FRPLAYER.rolls[#FRPLAYER.rolls+1]=PCSX.getRegisters().GPR.n.a0
end)
hook({e.A('handleFood')},function()
 local b;b=PCSX.addBreakpoint(PCSX.getRegisters().GPR.n.ra,'Exec',4,'food-return',function()
  FRPLAYER.returned=FRPLAYER.returned+1;b:remove()
 end)
end)
hook({e.A('tamerTickEnding')},function() FRPLAYER.ending=FRPLAYER.ending+1 end)
''')


def value(e, key):
    return int(e.run('lua', 'return FRPLAYER.' + key).strip())


def move(e, x, z):
    e.run('pause')
    e.gs('move', str(x), str(z))
    e.run('resume')


def food(e, out, route):
    setup_food(e, 1)
    e.gs('set', 'inventory.amounts=[30' + ',0' * 29 + ']')
    watch(e)
    attempts = []
    for attempt in range(30):
        e.gs('set', 'partner.para.energyLevel=0', 'partner.para.foodLevel=0')
        previous = value(e, 'food')
        open_menu(e, 'item' if route == 'inventory' else 'care', out / f'food-{attempt}.png')
        deadline = time.monotonic() + 150
        while value(e, 'returned') <= previous and time.monotonic() < deadline:
            e.wait(.3)
        assert value(e, 'food') == previous + 1, 'food effect not reached'
        assert value(e, 'returned') == previous + 1, 'food handler failed to return'
        sick = bool(e.peek('PARTNER_PARA', 'I') & 64)
        e.run('shot', str(out / f'food-{attempt}-effect.png'))
        if sick:
            e.press('CONFIRM', 12)
        assert e.in_control(), 'feeding did not return control'
        assert e.peek('INVENTORY+60', 'B') == 29 - attempt
        attempts.append(dict(attempt=attempt + 1, sick=sick))
        print('food', attempts[-1], flush=True)
        if sick:
            return dict(attempts=attempts, native_chance=int(e.run('lua', 'return FRPLAYER.rolls[1]').strip()))
    raise AssertionError('30 unforced food rolls did not cause illness')


def climate(e, out):
    assert e.warp(94)
    move(e, 0, -850)  # open snow, away from SnowGoblimon's talk radius
    assert e.in_control(), 'cold fixture entered an NPC conversation'
    e.run('pause')
    pos = e.peek('PARTNER_ENTITY+4', 'I')
    e.run('poke', hex(pos + 120), struct.pack('<3i', 200, 0, -850).hex())
    e.poke('PARTNER_ENTITY+0x10', struct.pack('<3i', 200 << 15, 0, -850 << 15))
    e.run('resume')
    e.gs('set', 'hour=7', 'minute=0', 'partner.para.evoTimer=0',
         'partner.para.remainingLifetime=1000', 'partner.para.condition=0',
         'partner.para.areaEffectTimer=0', 'partner.para.sicknessCounter=0',
         'partner.para.tiredness=0', 'partner.para.energyLevel=100',
         'partner.para.foodLevel=100', 'partner.para.poopLevel=10000',
         'partner.para.sleepyHour=22', 'partner.para.wakeupHour=7',
         'gametime_running=1')
    # MapTileData[35], LocalMapObjectInstance[188], camera and dimensions.
    assert e.peek('MAP_TILE_DATA+7098', 'b') == 2, 'fixture is not in a disliked climate'
    watch(e)
    observations = []
    deadline = time.monotonic() + 2400
    while time.monotonic() < deadline:
        ram = e.ram()
        condition = e.peek('PARTNER_PARA', 'I', ram)
        observations.append(dict(hour=e.peek('HOUR', 'h', ram), minute=e.peek('MINUTE', 'h', ram), condition=condition,
                                 area_timer=para(e, 'areaEffectTimer', ram),
                                 sickness_counter=para(e, 'sicknessCounter', ram),
                                 injury_timer=para(e, 'injuryTimer', ram)))
        print('climate', observations[-1], flush=True)
        assert value(e, 'food') == 0, 'food contaminated climate exposure'
        if condition & 64:
            e.run('shot', str(out / 'climate-sick.png'))
            if e.peek('TAMER_STATE', 'b') == 20:
                e.press('CONFIRM', 12)
            e.gs('set', 'gametime_running=0')
            assert e.in_control()
            return observations
        assert e.peek('GAME_STATE', 'H') == 0, 'unexpected transition while waiting'
        assert e.peek('IS_SCRIPT_PAUSED', 'i') == 1, 'NPC conversation interrupted climate exposure'
        e.wait(10)
    raise AssertionError('cold exposure did not cause illness')


def recruit(e, out):
    assert e.peek('PARTNER_PARA', 'I') & 64
    if e.peek('CURRENT_SCREEN', 'h') != 94:
        assert e.warp(94)
    # Position on the real section-51 strip; normal checkMapInteraction dispatches it.
    move(e, -1000, -550)
    dialogue(e, out, lambda: bit(e, 133) and e.peek('CURRENT_SCREEN', 'h') == 94, 'rescue', 360)
    assert e.in_control()
    assert not (e.peek('PARTNER_PARA', 'I') & (32 | 64)), 'rescue did not cure illness'
    assert not bit(e, 223), 'rescue prematurely recruited Frigimon'
    e.run('shot', str(out / 'rescued.png'))
    print('rescue cured partner; rescue flag set; recruit flag clear', flush=True)
    fixture_partner(e, 17)
    call(e, 'readPStat', 1)
    prosperity = int(e.run('lua', 'return TE_CALL.result').strip())
    e.run('resume')
    # The newly unlocked house-door strip runs section 52 and walks inside.
    move(e, -1100, 750)
    for _ in range(90):
        if e.peek('CURRENT_SCREEN', 'h') == 137 and e.in_control():
            break
        e.wait(.5)
    assert e.peek('CURRENT_SCREEN', 'h') == 137 and e.in_control(), 'house door did not open'
    e.gs('approach', '0', '100')
    print('entered house; talking to Frigimon', flush=True)
    # Real collision plus confirmation opens Frigimon's on_talk handler.
    dialogue(e, out, lambda: bit(e, 223), 'recruit', 360)
    e.wait(2)
    e.run('shot', str(out / 'recruit-announcement.png'))
    assert e.in_control()
    call(e, 'readPStat', 1)
    after = int(e.run('lua', 'return TE_CALL.result').strip())
    e.run('resume')
    assert after == prosperity + 2, (prosperity, after)
    return dict(rescued=True, cured=True, recruited=True, prosperity_before=prosperity, prosperity_after=after)


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('disc'); p.add_argument('--exe', required=True)
    p.add_argument('--out', type=Path, required=True); p.add_argument('--port', type=int, default=42620)
    p.add_argument('--route', choices=('inventory', 'care', 'climate'), required=True)
    a = p.parse_args(); out = a.out.resolve(); out.mkdir(parents=True, exist_ok=True)
    e = emulator(a.disc, a.exe, a.port, out); result = dict(route=a.route); recording = None
    try:
        e.start(field_card(str(ROOT / 'tools/dev/saves/corpus/20261027-d2796814.mcd'), str(out / 'fixture.mcd')))
        e.run('lua', f"PCSX.addBreakpoint({e.A('playMovie')},'Exec',4,'skip-intro',function() PCSX.getRegisters().GPR.n.a1=0 end)")
        assert e.continue_game() == 0
        assert len(e.ram()) == 0x200000
        result['flow'] = json.loads(e.api('/api/v1/execution-flow'))
        assert not result['flow']['8mb']
        call(e, 'modSetLanguage', 1); e.run('resume')
        for n in (133, 223):
            e.gs('trigger', str(n), '0')
        e.run('save', str(out / 'base.state'))
        fixture(e, out / 'base.state', 3)
        e.run('save', str(out / 'ready.state'))
        if a.route != 'climate':
            recording = subprocess.Popen([sys.executable, 'tools/dev/emulator.py', 'record', str(out / 'feeding.mp4'), '45', '10'], env=e.env)
        result['sickness'] = climate(e, out) if a.route == 'climate' else food(e, out, a.route)
        if recording:
            assert recording.wait(timeout=60) == 0; recording = None
        e.run('save', str(out / 'sick.state'))
        recording = subprocess.Popen([sys.executable, 'tools/dev/emulator.py', 'record', str(out / 'recruitment.mp4'), '240', '10'], env=e.env)
        result.update(recruit(e, out))
        assert value(e, 'ending') == 0, 'ending routine was entered'
        result.update(ending_calls=0, ram_bytes=len(e.ram()), returned_control=e.in_control())
        assert recording.wait(timeout=260) == 0; recording = None
        print(json.dumps(result), flush=True)
    except subprocess.CalledProcessError as exc:
        print(exc.stderr, flush=True)
        raise
    finally:
        if recording:
            recording.terminate(); recording.wait(timeout=10)
        (out / 'result.json').write_text(json.dumps(result, indent=2) + '\n')
        e.stop()


if __name__ == '__main__':
    main()
