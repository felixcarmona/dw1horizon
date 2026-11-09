#!/usr/bin/env python3
"""Check a real wild victory, return-camera ownership and subsequent pad walking.

Boots a private native-Agumon card in original-2-MB PCSX-Redux. Fixture writes
select the screen, language, quick-battle option, care, stats and Spit Fire;
approach places the tamer beside the selected NPC. Dialogue, attacks, victory,
rewards and return pan run normally. Enemy HP and camera state are never written.
Use screen 0 for the repeatable forest encounter or 314 for Root Clearing.
"""
import argparse
import hashlib
import json
from pathlib import Path
import sys
import time

ROOT = Path(__file__).resolve().parents[3]
sys.path[:0] = [str(ROOT), str(ROOT / 'tools')]
from tools.dev.playtest.load_camera import card_fixture
from tools.dev.playtest.qol import ProofEmu
from tools.dev.playtest.training_evolution import call
from tools.langpatch import elf_symbols


def sample(e):
    ram = e.ram()
    row = {name: e.peek(name, fmt, ram) for name, fmt in (
        ('CURRENT_SCREEN', 'h'), ('GAME_STATE', 'B'), ('TAMER_STATE', 'B'),
        ('IS_SCRIPT_PAUSED', 'i'), ('CAMERA_FOLLOW_PLAYER', 'i'),
        ('CAMERA_HAS_TARGET', 'B'), ('CAMERA_REACHED_TARGET', 'b'),
        ('BATTLE_FRAME_COUNT', 'i'), ('PARTNER_PARA+0x54', 'h'),
        ('IS_IN_MENU', 'i'), ('FADE_PROTECTION', 'i'),
        ('DRAWING_OFFSET_X', 'i'), ('DRAWING_OFFSET_Y', 'i'))}
    row['position'] = e.peek('TAMER_POSITION_DATA+0x78', '3i', ram)
    row['animation_position'] = e.peek('TAMER_ENTITY+0x10', '3i', ram)
    row['boxes'] = [e.peek(f'UI_BOX_DATA+{36*i+16}', '2h', ram) for i in range(6)]
    row['ram_bytes'] = len(ram)
    flow = json.loads(e.api('/api/v1/execution-flow'))
    assert flow['running'] and not flow['8mb'] and len(ram) == 0x200000, flow
    return row


def free(row):
    return (row['GAME_STATE'] == 0 and row['TAMER_STATE'] == 0 and row['IS_SCRIPT_PAUSED'] == 1
            and row['IS_IN_MENU'] == 0 and row['FADE_PROTECTION'] == 0
            and not any(frame or state for frame, state in row['boxes']))


def check_walk(e, out, result):
    # State flags can become free while the last reward box still closes.
    for _ in range(60):
        row = sample(e)
        if free(row):
            break
        e.press('CONFIRM', 8)
        e.wait(.1)
    else:
        raise AssertionError('reward boxes did not release field control')
    result['returned'] = row
    e.run('save', str(out/'returned.state'))
    e.run('shot', str(out/'returned.png'))
    result['walks'] = []
    for button in ('LEFT', 'RIGHT'):
        before = sample(e)
        e.press(button, 24)
        after = sample(e)
        walk = dict(button=button, before=before, after=after)
        result['walks'].append(walk)
        assert free(after) and after['CURRENT_SCREEN'] == result['screen'], walk
        if after['position'] != before['position']:
            assert after['animation_position'] != before['animation_position'], 'tamer animation position stuck'
        offscreen = call(e, 'entityIsOffScreen', e.A('TAMER_ENTITY'), 320, 240)
        e.run('resume')
        walk['offscreen'] = offscreen
        assert offscreen == 0, 'walking tamer left the camera view'
    # Collision can legitimately block one direction at the arrival path.
    assert any(w['before']['position'] != w['after']['position'] for w in result['walks']), 'tamer did not move'
    e.run('shot', str(out/'walked.png'))
    result['ok'] = True


def run(args):
    out = args.out.resolve()
    out.mkdir(parents=True, exist_ok=True)
    e = ProofEmu(str(args.disc.resolve()), str(args.exe.resolve()), args.port, str(out/'emu'))
    e.env['EMU_ARGS'] = '-interpreter -debugger'
    for name, (address, _, _) in elf_symbols(e.exe + '.elf').items():
        e.table.setdefault(name, address)
    result = dict(screen=args.screen, language=args.language, quick=args.quick,
                  slot=args.slot, walk_only=args.walk_only,
                  disc_sha1=hashlib.sha1(args.disc.with_suffix('.bin').read_bytes()).hexdigest(),
                  exe_sha256=hashlib.sha256(args.exe.read_bytes()).hexdigest(), samples=[])
    try:
        # Continue uses a native screen; the ordinary map transition loads 314.
        e.start(str(card_fixture(out, 168, [0, 0, 0], 3, False, args.quick, args.language)))
        if args.state:
            e.run('load', str(args.state.resolve()))
            e.run('resume')
        else:
            assert e.continue_game() == 0, 'Continue failed'
        assert e.in_control()
        if args.walk_only:
            assert args.state, '--walk-only requires a field checkpoint'
            check_walk(e, out, result)
            return
        e.run('save', str(out/'boot.state'))
        print('Continue complete', flush=True)
        e.poke('MOD_OPT_QUICK_BATTLE', args.quick.to_bytes(4, 'little'))
        e.gs('set', 'gametime_running=0', 'hour=10', 'minute=0',
             'partner.para.condition=0', 'partner.para.age=1', 'partner.para.evoTimer=0',
             'partner.para.remainingLifetime=1000', 'partner.stats.hp=9999',
             'partner.stats.mp=9999', 'partner.stats.currentHP=9999',
             'partner.stats.currentMP=9999', 'partner.stats.off=999',
             'partner.stats.def=999', 'partner.stats.speed=999', 'partner.stats.brain=999',
             'partner.learned_moves=[4,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0]')
        if args.stay:
            assert args.state and e.peek('CURRENT_SCREEN', 'h') == args.screen, 'wrong field checkpoint'
        else:
            assert e.warp(args.screen), 'screen did not load'
        assert e.peek('MOD_LANG', 'i') == args.language, 'requested language absent'
        # Equipped moves contain animation slots, not technique IDs. Read the
        # built species mapping instead of assuming the order of its loadout.
        for animation in range(0x2e, 0x3e):
            technique = call(e, 'entityGetTechFromAnim', e.A('PARTNER_ENTITY'), animation)
            e.run('resume')
            if technique == 2:  # Spit Fire
                e.gs('set', f'partner.stats.moves=[{animation},255,255,53]')
                result['attack_animation'] = animation
                break
        else:
            raise AssertionError('native Agumon lacks Spit Fire')
        result['before'] = sample(e)
        e.run('save', str(out/'ready.state'))
        print('Encounter ready', result['before'], flush=True)
        # Keep the physical, animation and stored-location writes together.
        e.run('pause')
        try:
            result['approach'] = e.gs('approach', str(args.slot), '150').strip()
            result['approach_position'] = e.peek('TAMER_POSITION_DATA+0x78', '3i')
        finally:
            e.run('resume')
        started = False
        deadline = time.monotonic() + args.timeout
        while time.monotonic() < deadline:
            row = sample(e)
            result['samples'].append(row)
            if row['GAME_STATE'] != 0:
                started = True
            if started and free(row):
                result['returned'] = row
                break
            e.press('CONFIRM', 8)
            e.wait(.25)
        else:
            raise AssertionError('encounter did not return to free field control')
        assert result['returned']['PARTNER_PARA+0x54'] > result['before']['PARTNER_PARA+0x54'], 'no victory'
        assert row['CAMERA_FOLLOW_PLAYER'] == 1 and row['CAMERA_HAS_TARGET'] == 0, row
        check_walk(e, out, result)
    except BaseException as error:
        result['error'] = str(error)
        try:
            e.run('shot', str(out/'failure.png'))
            e.run('save', str(out/'failure.state'))
        except Exception:
            pass
        raise
    finally:
        (out/'result.json').write_text(json.dumps(result, indent=2)+'\n')
        print(json.dumps({k: v for k, v in result.items() if k != 'samples'}), flush=True)
        e.stop()


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('disc', type=Path)
    p.add_argument('--exe', required=True, type=Path)
    p.add_argument('--out', required=True, type=Path)
    p.add_argument('--screen', type=int, choices=(0, 314), default=314)
    p.add_argument('--slot', type=int, default=0)
    p.add_argument('--quick', type=int, choices=(0, 1), default=1)
    p.add_argument('--language', type=int, choices=range(8), default=0)
    p.add_argument('--port', type=int, default=39588)
    p.add_argument('--state', type=Path, help='field checkpoint from this exact disc')
    p.add_argument('--stay', action='store_true', help='fight another NPC without reloading the checkpoint screen')
    p.add_argument('--walk-only', action='store_true', help='recheck walking from a same-disc return checkpoint')
    p.add_argument('--timeout', type=float, default=300)
    run(p.parse_args())


if __name__ == '__main__':
    main()
