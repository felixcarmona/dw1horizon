"""Owned City roster, checked against recruit writes in every compiled story."""
import argparse
import json
from pathlib import Path
import struct
import re

ROOT = Path(__file__).resolve().parents[1]
ROSTER = ROOT / 'content/tables/city-residents.json'
# Geko Swamp sets Otamamon's defeat flag for Misty Trees; it never moves to File City.
STORY_SPECIES = {109}
LEVELS = {'rookie': 3, 'champion': 4, 'ultimate': 5, 'mega': 6}


def residents(content=None):
    species = {s['id']: s for p in (ROOT / 'content/species').glob('*.json')
               for s in [json.loads(p.read_text())]}
    if content is not None:
        species.update(content)
    rows = json.loads(ROSTER.read_text())
    ids = [r['id'] for r in rows]
    if len(set(ids)) != len(ids) or any(not 0 <= i < 1024 or i not in species for i in ids):
        raise ValueError('City roster: unique, defined species ids below 1024 required')
    if any(species[i]['level'] not in LEVELS for i in ids):
        raise ValueError('City roster: residents must be Rookie or higher')
    points = lambda i: 1 if i in (11, 39, 53) else LEVELS[species[i]['level']] - 2
    if sum(map(points, ids)) > 255:
        raise ValueError('City roster: prosperity exceeds its saved byte')
    return sorted(rows, key=lambda r: (LEVELS[species[r['id']]['level']], r['id']))


def city_cell(row, content=None):
    """A City roster cell on the disc: id, level << 12 and 0x8000 when hidden. The tab draws every cell in its
    level's colour each frame: 20 records past the 16-slot species cache would read the disc all the time."""
    species = {s['id']: s for p in (ROOT / 'content/species').glob('*.json') for s in [json.loads(p.read_text())]}
    species.update(content or {})
    return row['id'] | LEVELS[species[row['id']]['level']] << 12 | (0x8000 if row['hidden'] else 0)


def compiled_recruits(path):
    # Decode instructions, never search raw bytes: dialogue and dead padding can
    # contain the same bytes. Ordinary flags 312+ have unrelated meanings;
    # high species use the reserved recruit-bit operands of patch 0304.
    from tools.dws import bytecode, basebuild
    data = Path(path).read_bytes()
    # DG entry zero is unused disc residue; getScript(0) reads MAPHEAD instead.
    offsets = bytecode.container_entries(data)[1:] if bytecode.is_container(data) else [0, len(data)]
    ids = set()
    for lo, hi in zip(offsets, offsets[1:]):
        if lo == hi:
            continue
        script = data[lo:hi]
        lines, _ = basebuild.flow_text(script, str(path))
        for line in lines:
            match = re.match(r'\s*SET_TRIGGER (\d+)\b', line)
            if match:
                flag = int(match[1])
                if 200 <= flag < 312:
                    ids.add(flag - 200)
                elif 0x8070 <= flag < 0x8400:
                    ids.add(flag - 0x8000)
    return ids


def membership_bits():
    """The executable's 112 roster bits, generated only from the owned JSON."""
    data = bytearray(14)
    for row in residents():
        if row['id'] < 112:
            data[row['id'] // 8] |= 1 << (row['id'] % 8)
    return bytes(data)


def extra_header():
    """Exact-sized compiled list; no extra resident storage for the current roster."""
    ids = sorted(r['id'] for r in residents() if r['id'] >= 112)
    return ('/* Generated from content/tables/city-residents.json. */\n'
            f'#define CITY_RESIDENTS_EXTRA_COUNT {len(ids)}\n'
            'static const uint16_t CITY_RESIDENTS_EXTRA[] = {' +
            ', '.join(map(str, ids or [0])) + '};\n')


def write_extra_header(tree):
    path = Path(tree) / 'src/main/city_residents_extra.h'
    # Old patch series need no generated input.
    if path.exists():
        data = extra_header()
        if path.read_text() != data:
            path.write_text(data)


def verify(paths, original=False):
    """One pass (DG + MAPHEAD): original high flags are unrelated legacy writes."""
    expected = {r['id'] for r in residents() if not original or r['id'] < 59}
    species = {s['id']: s for p in (ROOT / 'content/species').glob('*.json')
               for s in [json.loads(p.read_text())]}
    actual = set()
    for path in paths:
        actual.update(i for i in compiled_recruits(path)
                      if i not in STORY_SPECIES and (not original or i < 59) and (i not in species or species[i]['level'] in LEVELS))
    if expected != actual:
        raise ValueError(f'City roster disagrees with {"original" if original else "extended"} compiled story: '
                         f'unreachable {sorted(expected - actual)}, unlisted {sorted(actual - expected)}')
    return len(expected)


def verify_archive(data):
    """Check the optional City block without changing the v2 species record ABI."""
    sector = struct.unpack_from('<I', data, 0x38)[0]
    if not sector:
        raise ValueError('City block missing')
    start = sector * 2048
    rows = residents()
    count = struct.unpack_from('<H', data, start)[0]
    ids = struct.unpack_from(f'<{count}H', data, start + 2)
    expected = tuple(city_cell(r) for r in rows)
    if ids != expected:
        raise ValueError('City block roster differs from owned data')
    for k, row in enumerate(rows):
        if row['id'] <= 61:
            continue
        offset = start + (1 + k // 7) * 2048 + k % 7 * 288
        icon = data[offset:offset + 288]
        if len(icon) != 288 or not any(icon[32:]) or not any(icon[2:32]):
            raise ValueError(f'City icon missing for species {row["id"]}')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--c-extra-header', type=Path, help='update a patched compiler tree before building')
    parser.add_argument('stories', nargs='*', type=Path, help='compiled DG.SCN or MAPHEAD.SCN')
    parser.add_argument('--original', action='store_true', help='check the original story (ids below 59)')
    args = parser.parse_args()
    if args.c_extra_header:
        write_extra_header(args.c_extra_header)
        return
    if not args.stories:
        parser.error('provide compiled stories or --c-extra-header')
    groups = {}
    for path in args.stories:
        groups.setdefault(path.parent, []).append(path)
    for folder, paths in groups.items():
        if len(paths) < 2:  # a pass is DG + MAPHEAD: a lone file is a build's intermediate, not a story
            continue
        original = args.original or 'base' in folder.parts
        print(f'City roster: {verify(paths, original)} residents match {folder} ({"original" if original else "extended"})')


if __name__ == '__main__':
    main()
