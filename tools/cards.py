"""Owned card metadata and the phase-B CARD2.ALL build interface.

CARDTAB.BIN is exactly one sector: 512 little-endian <HBB rows (species,
rarity, merit). Unassigned IDs have rarity 5 and never enter packs or medals.
"""
import json
from pathlib import Path
import shutil
import struct

ROOT = Path(__file__).resolve().parents[1]
LIMIT = 512
FIRST_NEW = 66
ENTRY_BYTES = 0x7000
MERIT = (100, 30, 10, 5, 1)


def species_id(value):
    if type(value) is int and 0 <= value < 1024:
        return value
    if isinstance(value, str):
        for path in sorted((ROOT / 'content/species').glob('*.json')):
            species = json.loads(path.read_text())
            if value.casefold() in (str(species['id']), species['name'].casefold()):
                return species['id']
    raise ValueError('card species must identify an engine species (ID 0..1023 or owned species name)')


def load(path=None, native=None):
    if native is None:
        native = json.loads((ROOT / 'content/tables/cards.json').read_text())['cards']
        # Use the same owned balance override as the executable-table writer.
        from tools import balance
        native = balance.load_overrides().get('cards', native)
    if len(native) != FIRST_NEW:
        raise ValueError('cards.json must retain its 66 original slots')
    rows = [dict(r) for r in native] + [dict(species=0, rarity=5, merit=0) for _ in range(LIMIT - FIRST_NEW)]
    authored = json.loads(Path(path or ROOT / 'content/cards/new.json').read_text())
    if isinstance(authored, dict):
        authored = authored['cards']
    if not isinstance(authored, list):
        raise ValueError('new.json must contain a cards array')
    keys, numbers = set(), set()
    for card in authored:
        if 'replaces' in card:   # new art for an original card: its row stays as the original table has it
            continue
        if not {'key', 'number', 'species', 'rarity', 'merit'} <= set(card):
            raise ValueError('new cards require key, number, species, rarity, merit')
        key, number, species, rarity = (card[k] for k in ('key', 'number', 'species', 'rarity'))
        if not isinstance(key, str) or not key or key in keys:
            raise ValueError('card keys must be nonempty and unique')
        if type(number) is not int or not FIRST_NEW <= number < LIMIT or number in numbers:
            raise ValueError('new card numbers must be unique IDs 66..511')
        species = species_id(species)
        if type(rarity) is not int or not 0 <= rarity < 5 or card['merit'] != MERIT[rarity]:
            raise ValueError('card rarity 0..4 requires merit 100/30/10/5/1 respectively')
        companions = card.get('with', [])
        if not isinstance(companions, list):
            raise ValueError('with must list companion species; it is artwork metadata')
        for companion in companions:
            species_id(companion)
        keys.add(key)
        numbers.add(number)
        rows[number] = dict(species=species, rarity=rarity, merit=card['merit'])
    if rows[0]['rarity'] != 5 or rows[65]['rarity'] != 5:
        raise ValueError('cards 0 and 65 must remain sentinels')
    for r in rows:
        if not 0 <= r['species'] < 65536 or not 0 <= r['rarity'] <= 5 or not 0 <= r['merit'] <= 255:
            raise ValueError('card metadata does not fit <HBB')
    if any(not any(r['rarity'] == rarity for r in rows) for rarity in range(5)):
        raise ValueError('each pack rarity needs at least one real card')
    return rows


def real_mask(rows):
    out = bytearray(LIMIT // 8)
    for i, r in enumerate(rows):
        if i not in (0, 65) and r['rarity'] < 5:
            out[i // 8] |= 1 << (i & 7)
    return bytes(out)


def authored_cards(path=None):
    authored = json.loads(Path(path or ROOT / 'content/cards/new.json').read_text())
    return authored['cards'] if isinstance(authored, dict) else authored


def replaced(path=None):
    return [c for c in authored_cards(path) if 'replaces' in c]


REPLACEMENT_LIMIT = 64


def replacement_entries(path=None):
    """Original ID -> CARD2 entry, after the highest authored new ID (holes retained)."""
    authored = authored_cards(path)
    first = max((c['number'] - FIRST_NEW + 1 for c in authored if 'replaces' not in c), default=0)
    originals = [c['replaces'] for c in authored if 'replaces' in c]
    if (len(originals) > REPLACEMENT_LIMIT or len(set(originals)) != len(originals) or
        any(type(n) is not int or not 1 <= n <= 64 for n in originals)):
        raise ValueError('replacement art requires up to 64 unique original IDs 1..64')
    if first + len(originals) > LIMIT - FIRST_NEW:
        raise ValueError('CARD2.ALL exceeds 446 entries including replacement art')
    return dict((n, first + i) for i, n in enumerate(originals))


def replacement_table(path=None):
    # Direct original-ID indexing also supports sparse, arbitrarily ordered rows.
    entries = replacement_entries(path)
    return [entries.get(n, 0xffff) for n in range(1, REPLACEMENT_LIMIT + 1)]


def compose_archives(out, path=None):
    """Compose CARD2.ALL from kept art; the disc's CARD.ALL is never modified."""
    from tools import cardmaker
    cards = authored_cards(path)
    replacements = replacement_entries(path)
    new = [c for c in cards if 'replaces' not in c]
    count = max([c['number'] - FIRST_NEW + 1 for c in new] +
                [entry + 1 for entry in replacements.values()], default=0)
    entries = bytearray(count * ENTRY_BYTES)
    for c in cards:
        number = c.get('replaces', c.get('number'))
        entry = replacements[number] if 'replaces' in c else number - FIRST_NEW
        tim = cardmaker.tim(c, number)
        if len(tim) != ENTRY_BYTES:
            raise ValueError(f"card {c['key']}: expected 0x7000 bytes")
        entries[entry * ENTRY_BYTES:(entry + 1) * ENTRY_BYTES] = tim
    (Path(out) / 'CARD2.ALL').write_bytes(entries)
    return len(new), len(replacements)


def build(out, art=None, path=None, native=None):
    rows = load(path, native)
    out = Path(out)
    out.mkdir(parents=True, exist_ok=True)
    (out / 'CARDTAB.BIN').write_bytes(b''.join(struct.pack('<HBB', r['species'], r['rarity'], r['merit']) for r in rows))
    ids = [i for i in range(FIRST_NEW, LIMIT) if rows[i]['rarity'] < 5]
    replacements = replacement_entries(path)
    entries = [i - FIRST_NEW for i in ids] + list(replacements.values())
    needed = max(entries, default=-1) + 1
    # Remove an output left by the former destructive archive composer.
    (out / 'CARD.ALL').unlink(missing_ok=True)
    target = out / 'CARD2.ALL'
    if art:
        size = Path(art).stat().st_size
        if size % ENTRY_BYTES or not needed * ENTRY_BYTES <= size <= (LIMIT - FIRST_NEW) * ENTRY_BYTES:
            raise ValueError(f'CARD2.ALL requires {needed}..446 entries of 0x7000 bytes')
        with Path(art).open('rb') as source:
            for entry in entries:
                source.seek(entry * ENTRY_BYTES)
                tim = source.read(544)
                if (struct.unpack_from('<II', tim) != (0x10, 9) or
                    struct.unpack_from('<I4H', tim, 8) != (524, 448, 511, 256, 1) or
                    struct.unpack_from('<I4H', tim, 532) != (27012, 576, 256, 75, 180)):
                    raise ValueError(f'CARD2.ALL entry {entry}: expected the CARD.ALL 150x180 8bpp TIM layout')
        shutil.copyfile(art, target)
    elif needed:
        compose_archives(out, path)
    else:
        target.write_bytes(b'')
    return rows
