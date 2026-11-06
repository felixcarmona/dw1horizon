#!/usr/bin/env python3
"""Capture independent and simultaneous field conditions on original 2 MB RAM.

Uses the supplied disc's own executable and a fresh card boot. Care bits and
inventory are deterministic fixtures; rendering and care availability run live.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import struct
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parents[3]
sys.path[:0] = [str(ROOT), str(ROOT / 'tools')]
from tools.dev.playtest.food_sickness import emulator
from tools.dev.playtest.birdramon_recruitment import field_card
from tools.dev.playtest.training_evolution import call
from tools.dev.playtest.quick_care import place_partner, position, wait
from tools.dev.playtest.care_badge_pixels import capture as capture_badge_pixels


def snapshot(e):
    ram = e.ram()
    fields = {'badge': ('MOD_RING_BADGE', 'i'),
              'from': ('MOD_RING_FROM', '8i'), 'to': ('MOD_RING_TO', '8i'),
              'shown': ('MOD_RING_SHOWN', '5i'), 'phase': ('MOD_RING_T', 'i'),
              'mode': ('MOD_STATUS_BUBBLES', 'i'), 'partner_state': ('PARTNER_STATE', 'b'),
              'care_rows': ('feedCount', 'i'), 'condition': ('PARTNER_PARA', 'I')}
    return {key: e.peek(name, fmt, ram) for key, (name, fmt) in fields.items()}


def setup(e, condition, items, scold=0, hp=2000, mp=2000):
    e.run('pause')
    try:
        e.gs('set', 'gametime_running=1', f'partner.para.condition={condition}',
             'partner.para.evoTimer=0', 'partner.para.remainingLifetime=1000',
             'partner.stats.hp=2000', 'partner.stats.mp=2000',
             f'partner.stats.currentHP={hp}', f'partner.stats.currentMP={mp}',
             'hour=12', 'minute=0', 'partner.para.starvationTimer=180',
             f'partner.para.foodLevel={0 if condition & 4 else 180}',
             f'partner.para.poopLevel={0 if condition & 8 else 48}',
             f'partner.para.tiredness={80 if condition & 2 else 0}',
             f'partner.para.sleepyHour={11 if condition & 1 else 23}',
             f'partner.para.wakeupHour={20 if condition & 1 else 8}',
             'partner.para.tirednessSleepTimer=-10000',
             'partner.para.happiness=50', 'partner.para.poopingTimer=2000',
             'partner.para.sicknessTimer=0', 'partner.para.injuryTimer=0')
        e.poke('INVENTORY', struct.pack('<30h', *(items + [-1] * (30-len(items)))))
        e.poke('INVENTORY+60', bytes([10] * len(items) + [0] * (30-len(items))))
        e.poke('INVENTORY+120', bytes([30]))
        e.poke('ITEM_SCOLD_FLAG', bytes([scold]))
    finally:
        e.run('resume')
    e.wait(2)


def expected_bubbles(condition, values):
    return condition.bit_count() + sum(
        values.get(resource,2000)*10 < 6000 for resource in ('hp','mp'))


def care_contract(e, base, out):
    """An actionable current need owns the badge, independent of distance/facing."""
    result = {}
    for name, cond, items, values, available in [
        ('hungry-unrelated-items', 4, [32,14,0,4], {}, False),
        ('toilet-no-potty', 8, [38,14], {}, False),
        ('hp-no-recovery', 0, [38], {'hp':500}, False),
        ('mp-no-recovery', 0, [38], {'mp':500}, False),
        ('several-needs-no-items', 77, [], {}, True),
        ('hungry-zero-food-quantity', 4, [38], {}, False),
    ]:
        e.run('load', str(base)); e.run('resume')
        setup(e, cond, items, **values)
        if name == 'hungry-zero-food-quantity':
            e.poke('INVENTORY+60', b'\0'); e.wait(.5)
        got = snapshot(e)
        assert got['condition'] == cond
        assert bool(got['badge']) == available, (name, got)
        assert sum(s != 0x10000 for s in got['from']) == expected_bubbles(cond,values)
        result[name] = got
        e.run('shot', str(out/f'{name}.png'))
    for name, far in [('far-facing-away', True), ('near-facing-away', False)]:
        e.run('load', str(base)); e.run('resume'); setup(e, 4, [38])
        x, y, z = position(e, 'TAMER_ENTITY')
        e.run('pause')
        place_partner(e, x + (4000 if far else 100), y, z + (4000 if far else 0))
        e.poke('TAMER_POSITION_DATA+0x72', struct.pack('<h', 0x400))
        e.run('resume'); e.wait(.5)
        p = position(e, 'PARTNER_ENTITY'); t = position(e, 'TAMER_ENTITY')
        distance = round(((p[0]-t[0])**2 + (p[2]-t[2])**2)**.5)
        if far:
            assert distance > 3000, distance
        got = snapshot(e)
        assert got['badge'] == 4 and got['care_rows'] == 1, (name, got)
        e.press('SQUARE', 8); wait(e, 'feedState', 1)
        assert e.peek('INVENTORY+60', 'B') == 10
        e.run('shot', str(out/f'care-{name}.png'))
        result[name] = {'distance': distance, 'square_opened': True,
                        'opening_consumed': False, 'before': got}
        e.press('CANCEL', 8); wait(e, 'TAMER_STATE', 0, 'b')
    return result


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--disc', required=True); p.add_argument('--exe', required=True)
    p.add_argument('--out', type=Path, required=True)
    p.add_argument('--port', type=int, default=41981)
    p.add_argument('--resume', action='store_true')
    p.add_argument('--video', action='store_true')
    p.add_argument('--square', action='store_true', help='verify the current Square shortcut')
    p.add_argument('--pixels', action='store_true', help='record GPU quad offsets at a shared root/clock fixture')
    a = p.parse_args(); out = a.out.resolve(); out.mkdir(parents=True, exist_ok=True)
    result = {'exe_sha256': hashlib.sha256(Path(a.exe).read_bytes()).hexdigest(), 'cases': {}}
    if a.resume:
        previous = json.loads((out/'result.json').read_text())
        assert previous['exe_sha256'] == result['exe_sha256'], 'checkpoint belongs to another executable'
    e = emulator(str(Path(a.disc).resolve()), str(Path(a.exe).resolve()), a.port, out/'emu')
    display = None
    if not os.environ.get('DISPLAY'):
        display = subprocess.Popen(['Xvfb', ':297', '-screen', '0', '1024x768x24', '-nolisten', 'tcp'],
                                   stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        e.env['DISPLAY'] = ':297'; time.sleep(.5)
    try:
        card = field_card(ROOT/'tools/dev/saves/corpus/20261027-d2796814.mcd', out/'field.mcd')
        e.start(str(card))
        if a.resume:
            e.wait(2); e.run('load', str(out/'field.state')); e.run('resume')
        else:
            assert e.continue_game() == 0
            assert e.in_control()
            e.gs('set', 'gametime_running=0', 'partner.para.evoTimer=0',
                 'partner.para.remainingLifetime=1000')
            e.poke('MOD_OPT_STORY', struct.pack('<i', 0))
        if e.peek('CURRENT_SCREEN', 'h') != 171:
            assert e.warp(171); assert e.in_control()
        # The old care shortcut also requires proximity and facing. Give both
        # versions that same ordinary near-partner view for the comparison.
        ram = e.ram()
        ptr = e.peek('TAMER_ENTITY+4', 'I', ram)
        x, y, z = struct.unpack_from('<3i', ram, ptr-0x80000000+0x78)
        ptr = e.peek('PARTNER_ENTITY+4', 'I', ram)
        e.run('pause')
        e.run('poke', hex(ptr+0x78), struct.pack('<3i', x+100, y, z).hex())
        e.poke('PARTNER_ENTITY+0x10', struct.pack('<3i', (x+100)<<15, y<<15, z<<15))
        e.poke('TAMER_POSITION_DATA+0x72', struct.pack('<h', 0xc00))
        e.run('resume'); e.wait(.5)
        e.run('save', str(out/'field.state'))
        result['ram_bytes'] = len(e.ram()); assert result['ram_bytes'] == 0x200000
        result['ram_probe'] = call(e, 'modProbeRam'); e.run('resume')
        assert result['ram_probe'] == 0
        assert e.peek('PARTNER_ENTITY', 'i') == 3
        for name, cond, items, kw in [
            ('healthy', 0, [38,32,14,0,4], {}),
            ('hungry', 4, [38,32,14], {}),
            ('sleepy', 1, [38,32,14], {}),
            ('toilet', 8, [38,32,14], {}),
            ('sick', 64, [38,32,14], {}),
            ('combined', 77, [38,32,14], {}),
            ('all-six', 111, [38,32,14], {}),
            ('hungry-no-food', 4, [], {}),
            ('sick-no-medicine', 64, [], {}),
            ('sleepy-no-items', 1, [], {}),
            ('hp-short', 0, [0], {'hp':500}),
            ('mp-short', 0, [4], {'mp':500}),
            ('scold', 0, [], {'scold':1}),
        ]:
            e.run('load', str(out/'field.state')); e.run('resume')
            setup(e, cond, items, **kw)
            result['cases'][name] = snapshot(e)
            assert result['cases'][name]['condition'] == cond
            assert sum(s != 0x10000 for s in result['cases'][name]['from']) == expected_bubbles(cond,kw)
            available = name not in ('healthy', 'hungry-no-food', 'sick-no-medicine')
            assert bool(result['cases'][name]['badge']) == available, name
            if a.pixels:
                result['cases'][name]['badge_pixels'] = capture_badge_pixels(
                    e, out/f'{name}.png', available)
            else:
                e.run('shot', str(out/f'{name}.png'))
            (out/'result.json').write_text(json.dumps(result, indent=2)+'\n')
            print(name, result['cases'][name], flush=True)
        if a.square:
            result['care_contract'] = care_contract(e, out/'field.state', out)
        # Keep the permanent care HUD visible with the combined conditions.
        setup(e, 77, [38,32,14])
        if a.video:
            e.run('record', str(out/'combined.mp4'), '6', '30')
        if a.square:
            e.press('SQUARE', 8); e.wait(1)
            assert e.peek('feedState', 'i') == 1
            assert e.peek('INVENTORY+60', '3B') == [10,10,10]
            e.run('shot', str(out/'square-care-menu.png'))
            result['square_opened_without_consuming_items'] = True
            e.press('CANCEL', 8); e.wait(1)
        e.run('shot', str(out/'combined-hud.png'))
        result['hud'] = snapshot(e)
    finally:
        (out/'result.json').write_text(json.dumps(result, indent=2)+'\n')
        e.stop()
        if display:
            display.terminate(); display.wait(timeout=10)


if __name__ == '__main__':
    main()
