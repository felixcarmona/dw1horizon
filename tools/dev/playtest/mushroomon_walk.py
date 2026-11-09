#!/usr/bin/env python3
"""Pad-only Mushroomon route checks on original 2 MB RAM.

Boot with --new-game, then supply --tour JSON (the recorded-walk tour format).
The first seven quiz answers are A,B,A,A,A,A,A (Renamon). All world progress,
care, battles and gates must be played. No warps, state edits, clock freezes,
HP refills or partner repositioning are permitted. The emulator stays running.
"""
import argparse
import heapq
import json
import os
from pathlib import Path
import struct
import sys
import time

ROOT = Path(__file__).resolve().parents[3]
sys.path[:0] = [str(ROOT), str(ROOT / 'tools')]
from tools.dev.saves.releases import Emu
from tools.langpatch import elf_symbols
from tools.dev.playtest import new_game_partner


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('disc')
    p.add_argument('--exe', required=True)
    p.add_argument('--out', type=Path, default=Path('build/mushroomon-walk'))
    p.add_argument('--port', type=int, default=42831)
    p.add_argument('--new-game', action='store_true')
    p.add_argument('--tour', type=Path)
    p.add_argument('--escape-wilds', action='store_true', help='use Run in escapable battles (requires pyelftools)')
    args = p.parse_args()
    args.out.mkdir(parents=True, exist_ok=True)
    e = Emu(args.disc, args.exe, args.port, str(args.out / 'emu'))
    def read_ram():
        ram = e.api('/api/v1/cpu/ram/raw')
        if len(ram) != 0x200000:
            raise RuntimeError('pad-only run requires original 2 MB RAM')
        return ram
    e.ram = read_ram
    e.table.update({n: v[0] for n, v in elf_symbols(e.exe + '.elf').items()})

    def forbidden(*a, **kw):
        raise RuntimeError('pad-only run: state writes and partner repositioning are forbidden')
    e.poke = forbidden
    radii = {row['id']: row.get('model', {}).get('radius', 100)
             for path in (ROOT / 'content/species').glob('*.json')
             for row in [json.loads(path.read_text())]}
    questions = [n for n in e.table if n == 'question' or n.startswith('question.')]
    if len(questions) != 1:
        raise RuntimeError(f'expected one quiz question symbol, found {questions}')
    e.table['question'] = e.table[questions[0]]
    if args.new_game:
        e.start(None)
        menu_at = e.A('tickMainMenu') - 0x80000000
        offset = e.A('tickMainMenu') - e.A('menu_START')
        signature = Path(e.exe).with_name('MENU_REL.BIN').read_bytes()[offset:offset + 32]
        deadline = time.monotonic() + 240
        while time.monotonic() < deadline:
            ram = e.ram()
            if (ram[menu_at:menu_at + 32] == signature
                    and e.peek('CURRENT_MENU', 'i', ram) == 0
                    and e.peek('MAIN_MENU_TICKS', 'i', ram) > 3
                    and not e.language_picker(ram)):
                break
            e.press('START', 16)
            time.sleep(.5)
        else:
            raise RuntimeError('title timed out')
        original_press = e.press
        chosen = False
        movie_at = e.A('MOV_playMovie') - 0x80000000
        movie_offset = e.A('MOV_playMovie') - e.A('mov_START')
        movie_signature = Path(e.exe).with_name('MOV_REL.BIN').read_bytes()[movie_offset:movie_offset + 32]

        def press(button, frames=10):
            nonlocal chosen
            ram = e.ram()  # also asserts the RAM is exactly 2 MB
            if ram[movie_at:movie_at + 32] == movie_signature:
                original_press('START', 16)  # the game's normal movie skip
                return
            if (not chosen and e.peek('question', 'B', ram) == 1
                    and e.peek('SCRIPT_NEXT_STATE_2', 'H', ram) == 0x26
                    and e.peek('SCRIPT_TEXTBOX_MODE', 'B', ram) == 2):
                original_press('DOWN', 12)
                chosen = True
            original_press(button, frames)
        e.press = press
        result = new_game_partner.new_game(e, args.out, args.out)
        assert chosen and result['species'] == 354, result  # Renamon
        e.run('resume')
        print(json.dumps(result), flush=True)
    if args.tour:
        os.environ.update(e.env)
        from tools.dev.walk import tour
        from tools.dev import game_state
        game_state.poke = forbidden
        if args.escape_wilds:
            from tools.dev import memory_inspector as memory
            memory.ram = e.ram
            memory.poke = forbidden
            variables, types = memory.build_index()
            cursor, _ = memory.resolve_expr('COMBAT_DATA.player.hoveredCommand[0]', variables, types)
            e.table['walk_command_cursor'] = cursor
        pad_api = tour.emu.api
        def running_pad(path, *a, **kw):
            # R1 is the native run modifier (POLLED_INPUT bit 8); unlike
            # Triangle, pressing it before a direction cannot open a menu.
            direction = path.rsplit('=', 1)[-1] in ('UP', 'DOWN', 'LEFT', 'RIGHT')
            if direction and '/lua/press?' in path:
                pad_api('/api/v1/lua/press?button=R1')
            result = pad_api(path, *a, **kw)
            if direction and '/lua/release?' in path:
                pad_api('/api/v1/lua/release?button=R1')
            return result
        tour.emu.api = running_pad
        tour.move_partner_behind = lambda *a, **kw: None
        tour.freeze_clock = lambda: None
        ordinary_events = tour.handle_events
        def handle_events():
            ram = e.ram()
            if args.escape_wilds and e.peek('GAME_STATE', 'H', ram) == 1:
                target = 2 if e.peek('FLEE_DISABLED', 'B', ram) else 1
                if e.peek('walk_command_cursor', 'b', ram) != target:
                    e.press('LEFT', 10)
                else:
                    e.press('CONFIRM', 10)
                if target == 2:
                    e.press('SQUARE', 8)
                time.sleep(.3)
                return True
            if e.peek('GAME_STATE', 'H', ram) == 0 and e.peek('IS_IN_MENU', 'B', ram):
                e.press('CANCEL', 12)
                time.sleep(.3)
                return True
            if (e.peek('GAME_STATE', 'H', ram) == 0
                    and e.peek('TAMER_STATE', 'b', ram) == 10
                    and e.peek('IS_SCRIPT_PAUSED', 'i', ram) == 0):
                # Original story scenes can keep tamer state 10 while a textbox
                # waits. The general walker only handles wild state 6 dialogs.
                e.press('CONFIRM', 12)
                time.sleep(.3)
                return True
            return ordinary_events()
        tour.handle_events = handle_events
        class PadRoute(tour.Seg):
            def __init__(self, mapfile):
                self.m = tour.dwmap.MapFile(Path(mapfile).read_bytes())
                self.vp, self.bx, self.by, self.bz = tour.dwmap.camera_basis(self.m)
                ram = e.ram()
                # Native story events change collision at runtime (the farm,
                # tunnel dirt and city buildings). Read the real floor rather
                # than steering through an obstacle absent from the base map.
                self.m.collision = bytearray(e.raw('MAP_COLLISION_DATA', 10000, ram))
                x, _, z = e.peek('TAMER_POSITION_DATA+0x78', '3i', ram)
                footprints = []
                for address in e.peek('ENTITY_TABLE+8', '8I', ram):
                    at = address - 0x80000000
                    if not 0 <= at < len(ram) - 0x38 or not ram[at + 0x34]:
                        continue
                    species, position = struct.unpack_from('<II', ram, at)
                    position -= 0x80000000
                    if 0 <= position < len(ram) - 0x84:
                        nx, _, nz = struct.unpack_from('<3i', ram, position + 0x78)
                        footprints.append((nx, nz, radii.get(species, 100)))
                self.R = tour.reach.reach(self.m, [(x, z)],
                                         seed_policy='spawn_coordinates', footprints=footprints)

            def path(self, a, b):
                # Keep the existing reach.py lattice and pad steering. A* avoids
                # repeatedly flooding an entire large native map between steps.
                def snap(p):
                    q = (round(p[0] / 10) * 10, round(p[1] / 10) * 10)
                    if q in self.R:
                        return q
                    return min(self.R, key=lambda n: (n[0] - p[0]) ** 2 + (n[1] - p[1]) ** 2)
                start, goal = snap(a), snap(b)
                distance = lambda n: max(abs(n[0] - goal[0]), abs(n[1] - goal[1])) // 10
                queue = [(distance(start), 0, start)]
                costs, previous = {start: 0}, {start: None}
                while queue:
                    _, cost, point = heapq.heappop(queue)
                    if cost != costs[point]:
                        continue
                    if point == goal:
                        break
                    for dx, dz in ((10, 0), (-10, 0), (0, 10), (0, -10),
                                   (10, 10), (10, -10), (-10, 10), (-10, -10)):
                        nxt = (point[0] + dx, point[1] + dz)
                        if nxt in self.R and cost + 1 < costs.get(nxt, float('inf')):
                            costs[nxt], previous[nxt] = cost + 1, point
                            heapq.heappush(queue, (cost + 1 + distance(nxt), cost + 1, nxt))
                if goal not in previous:
                    raise RuntimeError('no physical route to waypoint')
                route, point = [], goal
                while point is not None:
                    route.append(point)
                    point = previous[point]
                return route[::-1][30::30] + [b]
        tour.Seg = PadRoute
        # Use one read-only RAM snapshot instead of spawning a state-reader for
        # every position sample. The existing pathfinder and pad steering remain.
        def state():
            ram = e.ram()
            x, _, z = e.peek('TAMER_POSITION_DATA+0x78', '3i', ram)
            return x, z, e.peek('CURRENT_SCREEN', 'h', ram)
        tour.state = state
        tour.sys.argv = [__file__, str(args.tour)]
        try:
            tour.main()
        finally:
            for button in ('UP', 'DOWN', 'LEFT', 'RIGHT', 'R1'):
                pad_api('/api/v1/lua/release?button=' + button)
    ram = e.ram()
    result = {n: e.peek(n, fmt, ram) for n, fmt in (
        ('CURRENT_SCREEN', 'h'), ('CURRENT_EXIT', 'b'), ('HOUR', 'h'),
        ('MINUTE', 'h'), ('GAME_STATE', 'H'), ('TAMER_STATE', 'b'))}
    (args.out / 'last.json').write_text(json.dumps(result, indent=2) + '\n')
    e.run('shot', str(args.out / 'last.png'))
    print(json.dumps(result), flush=True)


if __name__ == '__main__':
    main()
