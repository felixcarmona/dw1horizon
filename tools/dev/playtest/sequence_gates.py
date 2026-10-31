#!/usr/bin/env python3
"""Exercise the new connections on an already running original-2-MB test disc.

Boot/continue a disposable test card first. This changes RAM flags and positions.
EMU_PORT=39149 DW_SYMS=disc-NAME python3 tools/dev/playtest/sequence_gates.py \
    --mode base --confirm CIRCLE --out build/gates-proof-base
Use --mode fixed for blocked entries, both unlocks and inside-save retreats.
"""
import argparse
import json
from pathlib import Path
import struct
import sys
import time
from types import SimpleNamespace
from urllib.parse import quote

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))
from tools.dev import emulator as emu, symbols  # noqa: E402
from tools.dev.snapshot import wait_complete  # noqa: E402
from tools.maps import reach  # noqa: E402


class Probe:
    def __init__(self, args):
        self.args = args
        self.out = args.out
        self.out.mkdir(parents=True, exist_ok=True)
        self.build = emu.build()
        self.events = []
        self.pending_shot = None
        flow = json.loads(emu.api('/api/v1/execution-flow'))
        if flow['8mb']: raise RuntimeError('This proof requires original 2 MB RAM')
        self.flow = flow

    def address(self, expression):
        return symbols.resolve(expression, self.build) & 0x1fffff

    def ram(self):
        return emu.api('/api/v1/cpu/ram/raw')

    def get(self, ram, expression, fmt):
        return struct.unpack_from('<' + fmt, ram, self.address(expression))[0]

    def put(self, expression, data):
        emu.api(f'/api/v1/cpu/ram/raw?offset={self.address(expression)}&size={len(data)}', data=data)

    def flag(self, number, value):
        offset = self.address('SCRIPT_STATE+245') + number // 8
        b = self.ram()[offset]
        b = b | (1 << (number % 8)) if value else b & ~(1 << (number % 8))
        emu.api(f'/api/v1/cpu/ram/raw?offset={offset}&size=1', data=bytes([b]))

    def pause(self, paused):
        emu.api('/api/v1/execution-flow?function=' + ('pause' if paused else 'start'))

    def wait_control(self, screen=None, timeout=120):
        end = time.monotonic() + timeout
        while time.monotonic() < end:
            ram = self.ram()
            current = self.get(ram, 'CURRENT_SCREEN', 'h')
            if (screen is None or current == screen) and self.get(ram, 'IS_SCRIPT_PAUSED', 'I') == 1 and self.get(ram, 'TAMER_STATE', 'B') == 0:
                return ram
            if ram[self.address('ACTIVE_INSTRUCTION')] in (0x1a, 0x10):
                if self.pending_shot:
                    time.sleep(0.3)
                    (self.out / (self.pending_shot + '-message.png')).write_bytes(emu.api('/api/v1/screen/still'))
                    self.pending_shot = None
                emu.press(self.args.confirm, 12)
            time.sleep(0.25)
        raise RuntimeError(f'No control on screen {screen}; last screen {current}')

    def record(self, label):
        time.sleep(2)  # Let the transition fade finish before saving the still.
        ram = self.ram(); flags = {}
        for n in (50, 103, 106, 124, 185, 186, 224, 328):
            b = ram[self.address('SCRIPT_STATE+245') + n // 8]
            flags[str(n)] = bool(b & (1 << (n % 8)))
        row = dict(label=label, screen=self.get(ram, 'CURRENT_SCREEN', 'h'), flags=flags,
                   position=struct.unpack_from('<3i', ram, self.address('TAMER_POSITION_DATA+0x78')))
        self.events.append(row)
        (self.out / 'events.json').write_text(json.dumps(dict(flow=self.flow, events=self.events), indent=2) + '\n')
        (self.out / (label + '.png')).write_bytes(emu.api('/api/v1/screen/still'))
        print(json.dumps(row), flush=True)
        return row

    def setup(self):
        self.wait_control()
        self.pause(True)
        ram = self.ram(); off = self.address('SCRIPT_STATE+245')
        flags = bytearray(ram[off:off + 100])
        flags[50 // 8] &= ~(1 << (50 % 8))
        # Keep engine flags below 100. Reset original story and recruitment flags.
        for n in range(100, 787): flags[n // 8] &= ~(1 << (n % 8))
        for n in (203, 340, 362): flags[n // 8] |= 1 << (n % 8)
        self.put('SCRIPT_STATE+245', bytes(flags))
        self.put('SCRIPT_STATE+346', b'\x01')  # prosperity
        self.put('SCRIPT_STATE+361', b'\x00')  # p16, no Back Dimension portal
        self.put('IS_GAMETIME_RUNNING', b'\x00')
        self.pause(False)

    def warp_setup(self, screen, entry=0):
        self.pause(True)
        self.put('TAMER_SUB_STATE', b'\x00')
        self.put('TARGET_MAP', struct.pack('<h', screen))
        self.put('CURRENT_EXIT', bytes([entry]))
        self.put('TAMER_STATE', b'\x05\x00')
        self.pause(False)
        self.wait_control(screen)
        self.freeze_wild()

    def freeze_wild(self):
        # Freeze wild chase ranges for this exit test; retain their collision.
        for slot in range(8):
            self.put(f'MAP_DIGIMON_TABLE+{slot * 0xc4 + 0xb4}', b'\x00\x00')

    def touch_exit(self, target, *, blocked=False, label):
        ram = self.wait_control()
        source = self.get(ram, 'CURRENT_SCREEN', 'h')
        words = struct.unpack_from('<60h', ram, self.address('MAP_WARPS'))
        slot = next(k for k in range(10) if words[40 + k] == target)
        collision = list(ram[self.address('MAP_COLLISION_DATA'):self.address('MAP_COLLISION_DATA') + 10000])
        code = 110 + slot if 110 + slot in collision else 51
        x, _, z = struct.unpack_from('<3i', ram, self.address('TAMER_POSITION_DATA+0x78'))
        model = SimpleNamespace(collision=collision, warps=[])
        points = reach.reach(model, starts=[(x, z)], step=50, seed_policy='spawn_coordinates')
        goals = [(px, pz) for px, pz in points if collision[reach.row(pz) * 100 + reach.col(px)] == code]
        if not goals: raise RuntimeError(f'{source}: no reachable trigger for {target}')
        px, pz = min(goals, key=lambda p: (p[0] - x) ** 2 + (p[1] - z) ** 2)
        self.pause(True)
        loc = struct.pack('<3i', px, 0, pz)
        self.put('TAMER_POSITION_DATA+0x78', loc)
        self.put('STORED_TAMER_POS', loc)
        self.put('TAMER_ENTITY+0x10', struct.pack('<3i', px << 15, 0, pz << 15))
        self.pause(False)
        self.pending_shot = label if blocked else None
        emu.press('UP', 2)
        time.sleep(1)
        self.wait_control(source if blocked else target)
        self.freeze_wild()
        row = self.record(label)
        if row['screen'] != (source if blocked else target): raise AssertionError(row)
        if blocked and self.pending_shot: raise AssertionError('No blocking dialogue observed: ' + label)

    def run(self):
        self.setup()
        if self.args.mode == 'base':
            self.warp_setup(27)
            for target in (315, 337, 344, 345, 346, 347, 348, 354, 355, 356, 220):
                self.touch_exit(target, label=f'route-{target}')
            row = self.events[-1]
            assert not row['flags']['224'] and not row['flags']['328']
        else:
            for source, target in ((356, 220), (353, 165), (317, 78)):
                self.warp_setup(source)
                self.touch_exit(target, blocked=True, label=f'closed-{source}')
            # A save already inside the sewer must be able to leave both screens.
            self.warp_setup(220, 1)
            self.record('inside-sewer-before-reload')
            state_file = (self.out / 'inside-sewer.state').resolve()
            response = emu.api('/api/v1/lua/save?file=' + quote(str(state_file)), timeout=60)
            if not response.startswith(b'ok '): raise RuntimeError(response)
            wait_complete(state_file)
            emu.api('/api/v1/lua/load?file=' + quote(str(state_file)), timeout=60)
            self.wait_control(220)
            self.touch_exit(356, label='inside-sewer-to-drain')
            self.touch_exit(355, label='inside-drain-to-mine')
            for source, gate, retreat in ((165, 353, 352), (78, 317, 318)):
                self.warp_setup(source, 1)
                self.touch_exit(gate, label=f'inside-{source}-to-{gate}')
                self.touch_exit(retreat, label=f'inside-{gate}-retreat')
            # Neither original road: the legacy Seam escape stays open.
            self.warp_setup(335)
            self.touch_exit(34, label='legacy-seam-escape')
            # Original outdoor encounters can begin immediately after arrival.
            # Restore the stable fixture before the next independent case,
            # rather than trying to setup-warp while an ordinary battle runs.
            emu.api('/api/v1/lua/load?file=' + quote(str(state_file)), timeout=60)
            self.wait_control(220)
            self.flag(106, True)
            self.warp_setup(335)
            self.touch_exit(34, blocked=True, label='jungle-still-closed')
            self.touch_exit(334, label='retreat-to-seam')
            for flag in (224, 328):
                self.load_fixture(state_file)
                self.flag(flag, True)
                self.warp_setup(356)
                self.touch_exit(220, label=f'town-open-{flag}')
                self.flag(flag, False)
            for flag in (106, 103):
                for source, target in ((353, 165), (317, 78)):
                    self.load_fixture(state_file)
                    self.flag(flag, True)
                    self.warp_setup(source)
                    self.touch_exit(target, label=f'north-open-{source}-{flag}')
            self.load_fixture(state_file)
            self.flag(103, False); self.flag(106, True); self.flag(185, True)
            self.warp_setup(335)
            self.touch_exit(34, label='jungle-open')
        print('PASS', self.args.mode, flush=True)

    def load_fixture(self, state_file):
        # Each unlock is an independent case. Restore before setting its flag:
        # original arrivals can start encounters or story scenes immediately.
        emu.api('/api/v1/lua/load?file=' + quote(str(state_file)), timeout=60)
        self.wait_control(220)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--mode', choices=('base', 'fixed'), required=True)
    parser.add_argument('--confirm', choices=('CROSS', 'CIRCLE'), default='CROSS')
    parser.add_argument('--out', type=Path, required=True)
    Probe(parser.parse_args()).run()


if __name__ == '__main__':
    main()
