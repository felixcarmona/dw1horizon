"""Stable daily pickup IDs. The registry is append-only save data, never a sorted/rebuilt numbering.

Only the bitset lives in RAM. IDs travel in the disc's script instructions, including copied
scripts on new screens. Original-executable builds keep the original instructions.
"""
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
REGISTRY = ROOT / 'content/ground-items.json'
SPAWN = re.compile(r'^(\s*)SPAWN_ITEM(?:16)?\s+([^,;]+),\s*(-?\d+),\s*(-?\d+)(\s*(?:;.*)?)$')


def load_registry(path=REGISTRY, limit=1024):
    data = json.loads(Path(path).read_text())
    if data['format'] != 1:
        raise ValueError('unknown ground pickup registry format')
    spots = {}
    ids = set()
    placed = set()
    for row in data['spots']:
        key = (row['screen'], *row['tile'])
        ident = row['id']
        if key in spots or ident in ids:
            raise ValueError(f'duplicate ground pickup ID or location: {row}')
        if not 0 <= ident < limit:
            raise ValueError(f'ground pickup ID {ident} exceeds target bitset bound {limit}')
        tile = row.get('at', row['tile'])
        if not (0 <= row['screen'] <= 32767 and all(0 <= t <= 99 for t in row['tile'])
                and len(tile) == 2 and all(isinstance(t, int) and 0 <= t <= 99 for t in tile)):
            raise ValueError(f'invalid ground pickup location: {row}')
        if (row['screen'], *tile) in placed:
            raise ValueError(f'two ground pickups lie on one tile: {row}')
        spots[key] = ident
        ids.add(ident)
        placed.add((row['screen'], *tile))
    return data, spots


def placements(data):
    """{(screen, script x, script y): (x, y)}: the tile a spawn really lies on, where a row's "at" moves it."""
    return {(r['screen'], *r['tile']): tuple(r['at']) for r in data['spots'] if 'at' in r}


def switched_off(data):
    """{(screen, script x, script y)}: spots a row marks "off": the shared script's spawn is not copied to that screen (its ID
    stays reserved)."""
    return {(r['screen'], *r['tile']) for r in data['spots'] if r.get('off')}


def emitted(data):
    """{screen: [(id, (x, y))]}: every registered spot that is not "off", where it lies on its screen (its "at", else its
    tile)."""
    out = {}
    for r in data['spots']:
        if r.get('off'):
            continue
        out.setdefault(r['screen'], []).append((r['id'], tuple(r.get('at', r['tile']))))
    return out


def script_screens(maphead):
    """Reachable SET_SCRIPT assignments, including shared code and screens above 255.

    Replaced MAPHEAD bodies remain in the file as dead tails. Scanning literal bytes or
    only the original 255 sections incorrectly assigns their borrowed scripts to new screens.
    """
    from dws import bytecode
    data = Path(maphead).read_bytes()
    _, sections, instructions, _, _ = bytecode.sweep(data)
    lengths = dict(instructions)
    pending = [offset for _, offset in sections]
    seen, scripts = set(), {}
    while pending:
        at = pending.pop()
        if at in seen or at not in lengths:
            continue
        seen.add(at)
        op = data[at]
        length, targets = bytecode.instr_length(data, at)
        if op in (0x74, 0x86, 0x9F):
            raise ValueError('ground pickups must be authored in a screen script, not MAPHEAD')
        if op == 0xFB:
            sid, screen = bytecode.u16(data, at + 2), bytecode.u16(data, at + 4)
            scripts.setdefault(sid, set()).add(screen)
        pending.extend(targets)
        if op not in (0x15, 0x16, 0x17, 0xFE, 0xFF):
            pending.append(at + length)
    return {sid: sorted(screens) for sid, screens in scripts.items()}


def rewrite_text(text, screens, spots, places=None, off=()):
    """SPAWN_ITEM x, y -> one SPAWN_ITEM_DAILY per screen running the script, with the spot's stable ID, at the tile the
    registry places it on that screen (places: placements(); a shared script's tile can be rock on another screen). A spot
    in off (switched_off()) is left out on that screen."""
    places = places or {}
    authored = {(key[0], *at): key for key, at in places.items()}
    out = []
    for line in text.splitlines():
        m = SPAWN.fullmatch(line)
        if m:
            if not screens:
                raise ValueError('ground pickup script has no authored screen')
            for screen in sorted(screens):
                key = (screen, int(m[3]), int(m[4]))
                # A screen's own handler may name the relocated floor tile directly.
                # Borrowed scripts still use the original registry key.
                if key not in spots:
                    key = authored.get(key, key)
                if key not in spots:
                    raise ValueError(f'ground pickup {key} has no stable ID; append it to content/ground-items.json')
                if key in off:
                    continue
                x, y = places.get(key, (int(m[3]), int(m[4])))
                out.append(f'{m[1]}SPAWN_ITEM_DAILY {m[2]}, {x}, {y}, {spots[key]}, {screen}{m[5]}')
            continue
        elif re.match(r'\s*SPAWN_ITEM(?:16)?\b', line):
            raise ValueError(f'cannot assign a ground pickup ID to: {line.strip()}')
        elif re.match(r'\s*SPAWN_ITEM_DAILY\b', line):
            fields = line.split(';', 1)[0].split(None, 1)[1].split(',')
            try:
                _, x, y, ident, screen = map(int, fields)
            except ValueError as e:
                raise ValueError(f'invalid authored daily pickup: {line.strip()}') from e
            if spots.get((screen, x, y)) != ident or screen not in screens:
                raise ValueError(f'daily pickup does not match its stable registry ID: {line.strip()}')
        out.append(line)
    return '\n'.join(out) + '\n'


def rewrite(work, maphead, limit, registry=REGISTRY):
    data, spots = load_registry(registry, limit)
    scripts = script_screens(maphead)
    count = 0
    for path in sorted(Path(work).glob('script_*.scn.txt')):
        text = path.read_text()
        if not re.search(r'^\s*SPAWN_ITEM(?:16|_DAILY)?\b', text, re.M):
            continue
        sid = int(re.search(r'script_(\d+)', path.name)[1])
        screens = scripts.get(sid, [])
        # Unused original scripts still carry their authored IDs, so their bytecode remains safe
        # if a later guarded setup selects them. The registry also pins that original mapping.
        if not screens:
            screens = data['script_screens'].get(str(sid), [])
        updated = rewrite_text(text, screens, spots, placements(data), switched_off(data))
        count += updated.count('SPAWN_ITEM_DAILY ')
        path.write_text(updated)
    return f'ground pickups: {count} spawns use stable IDs; {len(spots)}/{limit} locations registered'
