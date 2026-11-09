#!/usr/bin/env python3
"""Talk to reachable Mushroomon and win through the pad on original 2 MB RAM.

Attach after mushroomon_walk.py reaches screen 234 and its talking approach.
A partner boosted through the normal Cheats menu is allowed. This driver only
reads RAM, presses buttons and saves evidence; it never writes game state.
"""
import argparse
import json
from pathlib import Path
import struct
import shutil
import sys
import time

ROOT = Path(__file__).resolve().parents[3]
sys.path[:0] = [str(ROOT), str(ROOT / 'tools')]
from tools.dev.playtest.qol import ProofEmu
from tools.dev.playtest.birdramon_recruitment import free_heap
from tools.langpatch import elf_symbols


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('disc')
    p.add_argument('--exe', required=True)
    p.add_argument('--port', type=int, default=42833)
    p.add_argument('--out', type=Path, default=Path('build/mushroomon-proof'))
    args = p.parse_args()
    args.out.mkdir(parents=True, exist_ok=True)
    e = ProofEmu(args.disc, args.exe, args.port, str(args.out / 'emu'))
    e.table.update({n: v[0] for n, v in elf_symbols(e.exe + '.elf').items()})
    e.ram = lambda: e.api('/api/v1/cpu/ram/raw')

    def observe():
        ram = e.ram()
        assert len(ram) == 0x200000
        assert e.peek('CURRENT_SCREEN', 'h', ram) == 234
        actors = []
        for address in e.peek('ENTITY_TABLE+8', '8I', ram):
            offset = address - 0x80000000
            if not 0 <= offset <= len(ram) - 88:
                continue
            species = struct.unpack_from('<i', ram, offset)[0]
            if species == 263:
                actors.append(dict(species=species,
                                   max_hp=struct.unpack_from('<h', ram, offset + 72)[0],
                                   hp=struct.unpack_from('<h', ram, offset + 76)[0]))
        return dict(game_state=e.peek('GAME_STATE', 'H', ram),
                    tamer_state=e.peek('TAMER_STATE', 'b', ram),
                    in_menu=e.peek('IS_IN_MENU', 'B', ram),
                    script_paused=e.peek('IS_SCRIPT_PAUSED', 'i', ram),
                    script_pointer=e.peek('SCRIPT_POINTER', 'I', ram),
                    opcode=e.peek('ACTIVE_INSTRUCTION', 'B', ram),
                    recruited=bool(e.peek('SPECIES_RECRUITED_BITS+32', 'B', ram) & 128),
                    actors=actors)

    samples = []
    result = dict(ram_bytes=len(e.ram()), flow=json.loads(e.api('/api/v1/execution-flow')))
    assert not result['flow']['8mb']
    result['heap_before'] = free_heap(e, e.ram())
    initial = observe()
    assert not initial['recruited'] and initial['game_state'] == 0
    assert any(a['max_hp'] == a['hp'] == 1200 for a in initial['actors']), initial
    e.run('save', str(args.out / 'before-mushroomon-talk.state'))
    e.run('shot', str(args.out / 'mushroomon-found.png'))
    fight = False
    boxes = set()
    last_box = None
    end = time.monotonic() + 600
    try:
        while time.monotonic() < end:
            row = observe()
            samples.append(row)
            if row['game_state'] == 1 and not fight:
                assert any(a['max_hp'] == 1200 for a in row['actors'])
                fight = True
                e.wait(2)
                result['heap_in_fight'] = free_heap(e, e.ram())
                e.run('shot', str(args.out / 'mushroomon-fight.png'))
            if row['recruited']:
                assert fight, 'recruitment occurred without the real fight'
                e.wait(4)
                e.run('shot', str(args.out / 'mushroomon-recruited.png'))
                # send_to_city sets its saved bit after dismissing the join box.
                assert last_box is not None
                shutil.copyfile(last_box, args.out / 'mushroomon-joined.png')
                e.run('save', str(args.out / 'mushroomon-joined.state'))
                break
            if row['game_state'] == 0 and row['opcode'] == 0x1a and row['script_pointer'] not in boxes:
                boxes.add(row['script_pointer'])
                e.wait(1)
                last_box = args.out / f'mushroomon-dialogue-{len(boxes)}.png'
                e.run('shot', str(last_box))
            if row['game_state'] == 1:
                e.press('SQUARE', 12)  # native finisher when its meter is full
            e.press('CANCEL' if row['game_state'] == 0 and row['in_menu'] else 'CONFIRM', 12)
            e.wait(.6)
        else:
            raise RuntimeError('Mushroomon conversation/fight timed out')
        # Dismiss the join box and confirm the scene returns control.
        for _ in range(100):
            row = observe()
            if row['game_state'] == 0 and row['tamer_state'] == 0 and row['script_paused'] == 1:
                break
            e.press('CONFIRM', 12)
            e.wait(.5)
        else:
            raise RuntimeError('recruitment did not return field control')
        assert row['recruited']
        result.update(recruited=True, fought_1200_hp=True, returned_control=True)
        e.run('shot', str(args.out / 'after-mushroomon.png'))
    finally:
        result['samples'] = samples
        (args.out / 'recruitment.json').write_text(json.dumps(result, indent=2) + '\n')
    print(json.dumps({k: v for k, v in result.items() if k != 'samples'}))


if __name__ == '__main__':
    main()
