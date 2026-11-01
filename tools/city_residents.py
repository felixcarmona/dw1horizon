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
    if len(set(ids)) != len(ids) or any(not 0 <= i < 112 for i in ids):
        raise ValueError('City roster: unique ids below 112 required')
    if any(species[i]['level'] not in LEVELS for i in ids):
        raise ValueError('City roster: residents must be Rookie or higher')
    points = lambda i: 1 if i in (11, 39, 53) else LEVELS[species[i]['level']] - 2
    if sum(map(points, ids)) > 255:
        raise ValueError('City roster: prosperity exceeds its saved byte')
    return sorted(rows, key=lambda r: (LEVELS[species[r['id']]['level']], r['id']))


def compiled_recruits(path):
    # Decode instructions, never search raw bytes: dialogue and dead padding can
    # contain the same bytes. Flags 312+ have unrelated meanings; the compiler's
    # b_recruit rejects species 112+ before emitting those ambiguous flag writes.
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
    return ids


def membership_bits():
    """The executable's 112 roster bits, generated only from the owned JSON."""
    data = bytearray(14)
    for row in residents():
        data[row['id'] // 8] |= 1 << (row['id'] % 8)
    return bytes(data)


def verify(paths, original=False):
    """One pass (DG + MAPHEAD): original high flags are unrelated legacy writes."""
    expected = {r['id'] for r in residents() if not original or r['id'] < 59}
    species = {s['id']: s for p in (ROOT / 'content/species').glob('*.json')
               for s in [json.loads(p.read_text())]}
    actual = set()
    for path in paths:
        actual.update(i for i in compiled_recruits(path)
                      if i not in STORY_SPECIES and (not original or i < 59) and species[i]['level'] in LEVELS)
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
    expected = tuple(r['id'] | (0x8000 if r['hidden'] else 0) for r in rows)
    if ids != expected:
        raise ValueError('City block roster differs from owned data')
    for k, row in enumerate(rows):
        if row['id'] <= 61:
            continue
        offset = start + (1 + k // 12) * 2048 + k % 12 * 160
        icon = data[offset:offset + 160]
        if len(icon) != 160 or not any(icon[32:]) or not any(icon[2:32]):
            raise ValueError(f'City icon missing for species {row["id"]}')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('stories', nargs='+', type=Path, help='compiled DG.SCN or MAPHEAD.SCN')
    parser.add_argument('--original', action='store_true', help='check the original story (ids below 59)')
    args = parser.parse_args()
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
