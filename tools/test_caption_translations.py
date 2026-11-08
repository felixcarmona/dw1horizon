"""Caption banks must cover every screen and survive the on-disc encoding."""
import unittest
from pathlib import Path
import tempfile
from unittest.mock import patch

from tools import screens
from tools.languages import CODES
from tools.localize import captions


class CaptionTranslations(unittest.TestCase):
    def test_authored_captions_reach_screen_files(self):
        # Exercise the build entry point, not just localize(): v0.0.7 wrote
        # authored English captions straight into SCRN.DAT in every language.
        folders = sorted((captions.ROOT / 'story/mods').glob('*/screens'))
        source = screens.load(folders)
        script = ''.join(f'.section {ident} sec{ident}\nsec{ident}:\nEND_SECTION\n'
                         for ident in sorted(source))
        maphead = screens.bytecode.assemble_script(script, 'caption-test')[0]
        baseline = None
        with tempfile.TemporaryDirectory() as directory:
            directory = Path(directory)
            original = directory / 'MAPHEAD.SCN'
            original.write_bytes(maphead)
            for language in CODES:
                with self.subTest(language=language):
                    output = directory / 'SCRN.DAT'
                    screens.build_files(str(original), str(directory / 'resident.scn'),
                                        str(output), folders, language=language,
                                        log=lambda _: None)
                    data = output.read_bytes()
                    records = {row['id']: row for row in screens.records(data)}
                    bank = captions.names(language)
                    for ident, row in source.items():
                        caption = row.get('caption', 0)
                        if isinstance(caption, str):
                            key = captions.caption_key(caption)
                            expected = captions.encode(bank[key], language)
                            self.assertEqual(records[ident]['caption_text'].encode('latin-1'), expected,
                                             (language, ident, key))
                    self.assertEqual(records[314]['caption_text'].encode('latin-1'), captions.encode(
                        bank['screen.caption.root_clearing'], language))
                    # Localization must leave screen setup and scripts intact.
                    for ident in source:
                        start = screens.RECORD_SIZE * (1 + ident - screens.NUM_ORIGINAL_SCREENS)
                        data = data[:start + 0x5c] + bytes(36) + data[start + 0x80:]
                    if baseline is None:
                        baseline = data
                    self.assertEqual(data, baseline)

    def test_complete_inventory(self):
        self.assertGreater(captions.audit(), 60)

    def test_missing_translation_stops_build(self):
        record = {302: {'id': 302, 'caption': 'The Shaft'}}
        original = captions.names
        def missing(language, root=captions.ROOT):
            bank = original(language, root).copy()
            if language == 'pt-br':
                del bank['screen.caption.the_shaft']
            return bank
        with patch.object(captions, 'names', missing):
            with self.assertRaisesRegex(ValueError, 'pt-br: screen 302 lacks'):
                captions.localize(record, 'pt-br')

    def test_native_english_placeholder_stops_audit(self):
        original = captions.names
        def untranslated(language, root=captions.ROOT):
            bank = original(language, root).copy()
            if language == 'pt-br':
                bank['main.STR_MAP_NAME_FILE_CITY'] = 'File City'
            return bank
        with patch.object(captions, 'names', untranslated):
            with self.assertRaisesRegex(ValueError, 'untranslated native captions'):
                captions.audit()

    def test_shared_area_uses_existing_translation(self):
        self.assertEqual(captions.caption_key('File City'), 'main.STR_MAP_NAME_FILE_CITY')
        row = captions.localize({360: {'caption': 'File City'}}, 'pt-br')[360]
        self.assertEqual(bytes(row['_caption_bytes']), captions.encode('Cidade Arquivo', 'pt-br'))

    def test_english_placeholder_is_not_a_translation(self):
        original = captions.names
        def untranslated(language, root=captions.ROOT):
            bank = original(language, root).copy()
            if language == 'pt-br':
                bank['screen.caption.the_shaft'] = 'The Shaft'
            return bank
        with patch.object(captions, 'names', untranslated):
            with self.assertRaisesRegex(ValueError, 'still English'):
                captions.localize({302: {'caption': 'The Shaft'}}, 'pt-br')

    def test_record_keeps_script_and_layout_in_every_language(self):
        code = '.section 302 sec302\nsec302:\nEND_SECTION\n'
        maphead = screens.bytecode.assemble_script(code, 'maphead.scn.txt')[0]
        source = {302: {'id': 302, 'file': 'SHFT01', 'caption': 'The Shaft', '_path': 'caption-test'}}
        records = []
        offset = screens.RECORD_SIZE * (1 + 302 - screens.NUM_ORIGINAL_SCREENS)
        for language in CODES:
            dat, _, _, _ = screens.build(captions.localize(source, language), maphead)
            record = dat[offset:offset + screens.RECORD_SIZE]
            value = captions.names(language)['screen.caption.the_shaft']
            self.assertEqual(record[0x5c:0x80], captions.encode(value, language).ljust(36, b'\0'))
            records.append(record[:0x5c] + record[0x80:])
        self.assertTrue(all(record == records[0] for record in records))

    def test_stale_executable_font_stops_build(self):
        from tools import fontgen
        value = captions.names('ja')['screen.caption.the_shaft']
        required = max(fontgen.code_to_index(captions.font_codes('ja')[c]) for c in value)
        with self.assertRaisesRegex(ValueError, 'missing from the executable font'):
            captions.localize({302: {'caption': 'The Shaft'}}, 'ja', font_glyphs=required)
        captions.localize({302: {'caption': 'The Shaft'}}, 'ja', font_glyphs=required + 1)

    def test_accents_are_font_codes_and_overflow_is_rejected(self):
        from tools import fontgen
        self.assertEqual(captions.encode('Poço', 'pt-br'), b'Po' + fontgen.extra_map()['ç'][0].to_bytes(2, 'big') + b'o')
        with self.assertRaisesRegex(ValueError, 'limit is 35'):
            captions.encode('X' * 36, 'en')
        with self.assertRaisesRegex(ValueError, 'missing from the font'):
            captions.encode('\U0001f43e', 'en')


if __name__ == '__main__':
    unittest.main()
