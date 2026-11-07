#!/usr/bin/env python3
"""Make a reproducible memory-card fixture for the Factorial Town crash checks.

  python3 tools/dev/playtest/factorial_card.py INPUT.mcd OUTPUT.mcd \
      --partner 403 --scene guards

INPUT must contain an original, one-block Digimon World save. The result is a
memory-card save to Continue on each tested disc, never a cross-version emulator
state. No disc or save data is distributed with this tool.

On current builds, recruit Datamon and re-enter the remodeling room to make its
ordinary wild guards appear. An original one-block card cannot store that
extended-species recruitment bit.
"""
import argparse
from pathlib import Path
import shutil
import struct
import sys

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))
from tools.dev.memory_card import Card, decode_save, v1_checksum


def fixture(source, output, partner, scene):
    card = Card(source)
    saves = [f for f in card.files() if f['name'].startswith('BASLUS-01032DMR')]
    if len(saves) != 1:
        raise ValueError('input must contain exactly one USA game save')
    save = saves[0]
    data = bytearray(card.read(save['name']))
    decoded = decode_save(data)
    if len(data) != 0x2000 or any(not decoded[f'copy{k}']['checksum_ok'] for k in (0, 1)):
        raise ValueError('input must be a valid original one-block save')
    if Path(source).resolve() == Path(output).resolve():
        raise ValueError('output must differ from input')
    if not 0 < partner < 1024:
        raise ValueError('partner must be a species ID from 1 through 1023')
    screen, position = {
        'guards': (162, (1400, 0, -1000)),
        'gear': (157, (0, 0, -700)),
        'city': (168, (1400, 0, -3100)),
    }[scene]
    # English, imported species and extended story enabled; quick battles ON.
    # The header also bypasses the first-boot language picker.
    data[0x50:0x60] = bytes([ord('O'), 12, 1, 0, 0, 1, 20, 1, 1, 1, 1, 0, 1, 1, 0, 1])
    for base in (0x200, 0x1100):
        p = bytearray(data[base:base + 0xF00])
        struct.pack_into('<i', p, 0x1B4, 10000)
        struct.pack_into('<i', p, 0x1B8, partner)
        struct.pack_into('<hh', p, 0x1D4, 12, 20)
        struct.pack_into('<3i', p, 4, *position)
        struct.pack_into('<3i', p, 0x14, position[0] - 200, 0, position[2] + 150)
        p[0x49A:0x49E] = bytes([screen, 161, 0, 0])
        # Numemon recruited; factory reopened, history read, guards passed,
        # shutdown and Giromon completed; the Gear kept for Andromon.
        flags = {1: False, 211: True, 240: scene != 'gear', 328: True,
                 330: True, 332: True, 341: True, 342: True, 343: True,
                 344: True, 742: True, 743: scene != 'gear', 760: True,
                 761: False}
        for n, value in flags.items():
            a, mask = 0x290 + 245 + n // 8, 1 << (n % 8)
            p[a] = p[a] | mask if value else p[a] & ~mask
        p[0x40C] = 120  # Gear, retained after the archive reading.
        p[0x40C + 30] = 1
        p[0x467:0x47B] = b'Tamer\0'.ljust(20, b'\0')
        p[0x47B:0x48F] = b'Partner\0'.ljust(20, b'\0')
        # Trained partner: battles still run their loading, AI, techniques,
        # results and return-to-field paths, with enough HP to survive testing.
        struct.pack_into('<hhhh', p, 0x270, 999, 999, 999, 999)
        p[0x278:0x280] = bytes([0, 1, 2, 3, 0x2E, 0x2F, 0x30, 0x31])
        struct.pack_into('<hhhh', p, 0x280, 9999, 9999, 9999, 9999)
        struct.pack_into('<I', p, 0x1E0, 0)
        struct.pack_into('<I', p, 0x4FC, v1_checksum(p))
        data[base:base + 0xF00] = p
    Path(output).parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(source, output)
    Card(output).write(save['name'], 0, data)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('input', type=Path)
    parser.add_argument('output', type=Path)
    parser.add_argument('--partner', type=int, required=True)
    parser.add_argument('--scene', choices=('guards', 'gear', 'city'), required=True)
    args = parser.parse_args()
    fixture(args.input, args.output, args.partner, args.scene)


if __name__ == '__main__':
    main()
