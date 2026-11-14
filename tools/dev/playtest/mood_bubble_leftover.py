#!/usr/bin/env python3
"""A Monochromon-shop mood bubble must not outlive screen 49 (2 MB original PlayStation).

Player report (2026-11-12, v0.0.8): a solid 32x32 rectangle floated over a wild enemy's head after the shop
shift, and went away only with a reset. The bubble is world object 0x1b1 (renderMonochromonMoodBubble): a 32x32
sprite from texture page (640, 0) drawn over the entity of script id pstat 0xF7. Only mood 5 removes it, and
world objects survive map changes, so leaving the shop with a bubble up leaves it drawing over whatever
entity that script id names on the next screens, with the shop's texture gone from VRAM.

The case: warp to screen 49, raise the bubble as the shop scripts do (pstat 0xF7 = 0xFC (the partner), pstat 0xF8 = mood, call
createMonochromonMoodBubble), warp to screen 0 and wait a few frames. Passes when object 0x1b1 is no longer
in WORLD_OBJECTS; with --expect-bug it passes when it is still there (an unfixed disc).
Usage: mood_bubble_leftover.py DISC --exe EXE --out DIR [--expect-bug]
"""
import argparse
import hashlib
import json
from pathlib import Path
import struct
import sys

ROOT = Path(__file__).resolve().parents[3]
sys.path[:0] = [str(ROOT), str(ROOT / 'tools')]
from tools.dev.playtest.load_camera import card_fixture
from tools.dev.playtest.qol import ProofEmu
from tools.dev.playtest.training_evolution import call
from tools.langpatch import elf_symbols

OBJECT = 0x1b1
PLATE = 0x1fb3   # the shift's profit plate (modShopPlateAdd): it already removes itself off screen 49


def objects(e):
    """(objectId, render) of every live world object (WorldObject is 12 bytes)."""
    ram = e.ram()
    base = e.A('WORLD_OBJECTS') & 0x1fffff
    rows = []
    for i in range(128):
        oid, _, _tick, render = struct.unpack_from('<hhII', ram, base + i * 12)
        if oid != -1:
            rows.append((oid, render))
    return rows


def raise_bubble(e, mood):
    e.gs('pstat', '247', '252')  # 0xFC: the partner, always an entity; the shop uses its customers' script id
    e.gs('pstat', '248', str(mood))
    call(e, 'createMonochromonMoodBubble')
    e.run('resume')


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('disc', type=Path)
    p.add_argument('--exe', required=True, type=Path)
    p.add_argument('--out', required=True, type=Path)
    p.add_argument('--port', type=int, default=39611)
    p.add_argument('--expect-bug', action='store_true')
    p.add_argument('--battle', action='store_true', help='also start a wild fight on screen 0 and shoot it')
    a = p.parse_args()
    out = a.out.resolve(); out.mkdir(parents=True, exist_ok=True)
    e = ProofEmu(str(a.disc.resolve()), str(a.exe.resolve()), a.port, str(out / 'emu'))
    e.env['EMU_ARGS'] = '-interpreter -debugger'
    for name, (address, _, _) in elf_symbols(e.exe + '.elf').items():
        e.table.setdefault(name, address)
    result = dict(expect_bug=a.expect_bug, exe_sha256=hashlib.sha256(a.exe.read_bytes()).hexdigest())
    try:
        e.start(str(card_fixture(out, 168, [0, 0, 0], 3, False, 1, 0)))
        assert e.continue_game() == 0, 'Continue failed'
        e.gs('set', 'gametime_running=0', 'hour=10', 'minute=0')
        assert e.warp(49), 'screen 49 did not load'
        before = [o for o, _ in objects(e)]
        assert OBJECT not in before, 'the bubble is up before the test raised it'
        raise_bubble(e, 3)
        call(e, 'modShopPlateAdd')
        e.run('resume')
        e.wait(.5)
        on_shop = [o for o, _ in objects(e)]
        result['on_shop'] = [hex(o) for o in on_shop]
        assert OBJECT in on_shop, 'createMonochromonMoodBubble did not add the object'
        e.run('shot', str(out / 'shop-bubble.png'), check=False)
        assert e.warp(0), 'screen 0 did not load'
        e.wait(2)
        gone = OBJECT not in [o for o, _ in objects(e)]
        result['left_over'] = not gone
        assert PLATE not in [o for o, _ in objects(e)], 'the shift plate stayed up off screen 49'
        e.run('shot', str(out / 'forest-after.png'), check=False)
        assert gone == (not a.expect_bug), ('bubble left over' if not gone else 'bubble gone on an unfixed disc')
        if a.battle:
            # The customers' script id is one a wild Digimon has on other screens: point the stale bubble at slot 0.
            sid = e.peek('NPC_ENTITIES+101', 'B')  # NPCEntity.scriptId
            result['slot0_script_id'] = sid
            e.gs('pstat', '247', str(sid))
            e.gs('approach', '0', '150')
            for _ in range(80):
                if e.peek('GAME_STATE', 'B') == 1: break
                e.press('CONFIRM', 8)
                e.wait(.25)
            e.wait(5)
            result['battle'] = e.peek('GAME_STATE', 'B')
            e.run('shot', str(out / 'battle-after.png'), check=False)
            # What the sprite samples: 4-bit texture page (640, 0), mood 3 = u 96..127, v 0..31, CLUT row 486.
            vram = e.api('/api/v1/gpu/vram/raw')
            (out / 'vram.bin').write_bytes(vram)
            words = struct.unpack('<%dH' % (len(vram) // 2), vram)
            tex = [words[y * 1024 + 640 + 24 + x] for y in range(32) for x in range(8)]
            clut = [words[486 * 1024 + i] for i in range(16)]
            result['texture_nonzero_words'] = sum(1 for w in tex if w)
            result['clut'] = [hex(c) for c in clut]
        if a.battle:
            result['passed'] = True
            return
        # A shop that is entered again must still show its bubble.
        assert e.warp(49), 'screen 49 did not load again'
        raise_bubble(e, 4)
        e.wait(.5)
        assert OBJECT in [o for o, _ in objects(e)], 'the bubble no longer works on re-entering the shop'
        result['passed'] = True
    finally:
        (out / 'result.json').write_text(json.dumps(result, indent=2) + '\n')
        print(json.dumps(result), flush=True)
        e.stop()


if __name__ == '__main__':
    main()
