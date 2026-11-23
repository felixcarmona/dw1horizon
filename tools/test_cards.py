"""The owned card table, archive contract, and file planner (no disc needed)."""
import json
from pathlib import Path
import struct
import tempfile
import unittest
from unittest.mock import patch

from tools import cards, newfiles
from tools.dev import memory_card


def authored(number=66, rarity=0):
    return {'key': f'card-{number}', 'number': number, 'species': 300, 'with': [301],
            'rarity': rarity, 'merit': cards.MERIT[rarity]}


def dummy_archive(path, count=446):
    """Valid 150x180 indexed TIMs, each with a distinct flat 15-bit colour."""
    with Path(path).open('wb') as f:
        for i in range(count):
            palette = struct.pack('<256H', *([0, i + 1] + [0] * 254))
            tim = struct.pack('<II', 0x10, 9)
            tim += struct.pack('<I4H', 524, 448, 511, 256, 1) + palette
            tim += struct.pack('<I4H', 27012, 576, 256, 75, 180) + bytes([1]) * 27000
            f.write(tim + bytes(cards.ENTRY_BYTES - len(tim)))


class CardContent(unittest.TestCase):
    def test_new_cards_option_translations(self):
        for lang in ('ours', 'es', 'pt-br', 'fr', 'de', 'it', 'ja', 'ca', 'zh-hans'):
            bank = json.loads((cards.ROOT / 'text' / lang / 'names.json').read_text())
            self.assertTrue(bank['main.MOD_OPT_STR_NEWCARDS'], lang)
        self.assertEqual(json.loads((cards.ROOT / 'text/es/names.json').read_text())[
            'main.MOD_OPT_STR_NEWCARDS'], 'CARTAS NUEVAS')

    def test_owned_table(self):
        rows = cards.load()
        self.assertEqual(len(rows), 512)
        self.assertEqual(sum(x.bit_count() for x in cards.real_mask(rows)), 64 + sum('replaces' not in c for c in cards.authored_cards()))
        self.assertEqual([rows[n]['rarity'] for n in (0, 65, 511)], [5, 5, 5])

    def test_archive_and_duplicate_species(self):
        with tempfile.TemporaryDirectory() as d:
            d = Path(d)
            config = d / 'new.json'
            config.write_text(json.dumps([authored(i, i % 5) for i in range(66, 512)]))
            art = d / 'input.all'
            dummy_archive(art)
            rows = cards.build(d / 'out', art, config)
            self.assertEqual(len((d / 'out/CARDTAB.BIN').read_bytes()), 2048)
            self.assertEqual(sum(x.bit_count() for x in cards.real_mask(rows)), 510)
            for n in (66, 255, 256, 511):
                self.assertEqual(struct.unpack_from('<HBB', (d / 'out/CARDTAB.BIN').read_bytes(), n * 4),
                                 (300, n % 5, cards.MERIT[n % 5]))
                with (d / 'out/CARD2.ALL').open('rb') as f:
                    f.seek((n - 66) * cards.ENTRY_BYTES + 22)
                    self.assertEqual(struct.unpack('<H', f.read(2))[0], n - 65)
            with patch.object(newfiles, 'disc_paths', return_value={}):
                files, names = newfiles.plan([], [f'CARD/CARD2.ALL={art}',
                    f'CARD/CARDTAB.BIN={d / "out/CARDTAB.BIN"}'], screen_dirs=None)
            self.assertEqual(names, ['CARD2.ALL', 'CARDTAB.BIN'])
            self.assertTrue(all(f[0] == '--add' for f in files))
            with art.open('r+b') as f:
                f.seek(540)  # TIM pixel rectangle width
                f.write(struct.pack('<H', 74))
            with self.assertRaises(ValueError):
                cards.build(d / 'bad-tim', art, config)
            art.write_bytes(bytes(cards.ENTRY_BYTES))
            with self.assertRaises(ValueError):
                cards.build(d / 'short', art, config)

    def test_replacement_archives(self):
        with tempfile.TemporaryDirectory() as d:
            d = Path(d)
            config = d / 'new.json'
            config.write_text(json.dumps([authored(66), authored(70)] +
                              [dict(key=f'art-{n}', replaces=n) for n in (26, 44)]))
            self.assertEqual(cards.replacement_entries(config), {26: 5, 44: 6})
            self.assertEqual(cards.replacement_table(config), [({26: 5, 44: 6}).get(n, 65535) for n in range(1, 65)])
            original = d / 'CARD.ALL'
            original.write_bytes(b'pristine disc art')
            out = d / 'out'
            out.mkdir()
            (out / 'CARD.ALL').write_bytes(b'stale destructive output')
            with patch('tools.cardmaker.tim', side_effect=lambda c, n: bytes([n]) * cards.ENTRY_BYTES):
                cards.build(out, path=config)
            self.assertEqual(original.read_bytes(), b'pristine disc art')
            self.assertFalse((out / 'CARD.ALL').exists())
            archive = (out / 'CARD2.ALL').read_bytes()
            self.assertEqual(len(archive), 7 * cards.ENTRY_BYTES)
            self.assertEqual([archive[i * cards.ENTRY_BYTES] for i in range(7)], [66, 0, 0, 0, 70, 26, 44])
            art = d / 'input.all'
            dummy_archive(art, 7)
            cards.build(out, art, config)
            dummy_archive(art, 5)  # Old archives lack the appended replacement art.
            with self.assertRaises(ValueError):
                cards.build(out, art, config)
            dummy_archive(art, 7)
            with art.open('r+b') as f:
                f.seek(6 * cards.ENTRY_BYTES + 540)
                f.write(struct.pack('<H', 74))
            with self.assertRaises(ValueError):
                cards.build(out, art, config)

    def test_replacement_limits(self):
        for rows in ([dict(key='bad', replaces=n) for n in (26, 26)],
                     [dict(key='bad', replaces=65)],
                     [authored(511), dict(key='overflow', replaces=26)]):
            with self.subTest(rows=rows), tempfile.TemporaryDirectory() as d:
                p = Path(d) / 'new.json'
                p.write_text(json.dumps(rows))
                with self.assertRaises(ValueError):
                    cards.replacement_entries(p)
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / 'new.json'
            p.write_text(json.dumps([authored(510), dict(key='last', replaces=64)]))
            self.assertEqual(cards.replacement_table(p), [65535] * 63 + [445])
        # The shipped cards keep the original art of every original card: no replacement rows.
        self.assertEqual(cards.replacement_entries(), {})
        self.assertEqual(cards.replacement_table(), [65535] * 64)

    def test_bad_metadata(self):
        for update in ({'number': 65}, {'number': 512}, {'species': 65536},
                       {'rarity': 5}, {'merit': 1}, {'with': '300'}):
            with self.subTest(update=update), tempfile.TemporaryDirectory() as d:
                p = Path(d) / 'new.json'
                p.write_text(json.dumps([dict(authored(), **update)]))
                with self.assertRaises(ValueError):
                    cards.load(p)

    def test_cardmaker_schema(self):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / 'new.json'
            card = authored()
            del card['with']
            card.update(species='Agumon', scene='authoring metadata', frame='red')
            p.write_text(json.dumps({'cards': [card]}))
            self.assertEqual(cards.load(p)[66]['species'], 3)

    def test_low_colour_art_palette(self):
        from tools import cardmaker
        image = cardmaker.Image.new('RGB', (16, 16), (248, 0, 0))
        pixels, clut = cardmaker.to_indexed(image)
        self.assertEqual(len(pixels), 256)
        self.assertEqual(len(clut), 256)
        self.assertEqual(clut[pixels[0]], 0x801f)

    def test_save_records_and_capacity(self):
        counts = bytearray(223)
        for number, amount in ((66, 9), (255, 4), (256, 7), (511, 8)):
            i, shift = (number - 66) // 2, (number & 1) * 4
            counts[i] |= amount << shift
        stock = struct.pack('<6H', 66, 255, 256, 511, 1, 0xffff)
        head = struct.pack('<4sHHi', b'DW4E', 4, 1120, 123)
        records = [(13, counts), (14, stock)]
        encoded = memory_card.build_extension(head, records, 1120)
        parsed = memory_card.parse_records(encoded)
        self.assertEqual(parsed, [(13, bytes(counts)), (14, stock)])
        decoded = memory_card.decode_records(parsed)
        self.assertEqual(decoded['cardCounts'], {66: 9, 255: 4, 256: 7, 511: 8})
        self.assertEqual(decoded['cardStock'], [66, 255, 256, 511, 1, 0xffff])
        self.assertEqual(1120 - (850 + 4 + 223 + 4 + 12), 27)


if __name__ == '__main__':
    unittest.main()
