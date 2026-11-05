"""Build data must remain authored when input executables or config folders change."""
from types import SimpleNamespace
import unittest
from unittest.mock import patch

import balance
import content
import tempfile
from pathlib import Path


class NativeDefaults(unittest.TestCase):
    def test_build_never_decodes_executable_numeric_defaults(self):
        exe = SimpleNamespace(compiled=False)
        with patch.object(balance, 'decode', side_effect=AssertionError('executable numeric read')), \
             patch.object(balance, 'c_rows', side_effect=AssertionError('compiled numeric read')):
            result = balance.built_layer(exe)
        self.assertEqual(result['species']['24']['para']['level'], 5)
        self.assertIn('evoReqs', result['species']['62'])

    def test_missing_resident_configuration_fails_closed(self):
        with patch.object(balance, 'native_species_defaults', return_value={}):
            with self.assertRaisesRegex(SystemExit, 'missing resident species'):
                balance.species_rows(SimpleNamespace(compiled=True))


class StoryScreenMetadata(unittest.TestCase):
    def test_owned_screen_changes_and_deletion_reach_compiler(self):
        from dws import backend as be
        import json
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            screens = root / 'content/screens'
            screens.mkdir(parents=True)
            tables = root / 'content/tables'
            tables.mkdir()
            (tables / 'story-screens.json').write_text(json.dumps({'nativeScreenIds': [0, 1]}))
            row = screens / '0-test.json'
            row.write_text(json.dumps({'id': 0, 'file': 'OWNED', 'sound_bank': 7,
                                       'day_night': False, 'reads_digimon': True, 'flag20': True}))
            # A reserved executable row is not implicitly visible to story code.
            (screens / '247-reserved.json').write_text(json.dumps({'id': 247, 'file': 'RESERVED'}))
            with patch.object(be, 'ROOT', directory), patch.object(content, 'SCREEN_DIR', str(screens)):
                self.assertEqual(be.native_screen_metadata(), ({0: 'OWNED'}, {0: 231}))
                row.unlink()
                self.assertEqual(be.native_screen_metadata(), ({}, {}))
                (tables / 'story-screens.json').unlink()
                with self.assertRaises(FileNotFoundError):
                    be.native_screen_metadata()

    def test_invalid_visibility_cannot_enable_extended_or_duplicate_ids(self):
        from dws import backend as be
        import json
        with tempfile.TemporaryDirectory() as directory:
            tables = Path(directory) / 'content/tables'
            tables.mkdir(parents=True)
            for ids in ([255], [0, 0], [True], '0'):
                with self.subTest(ids=ids), patch.object(be, 'ROOT', directory):
                    (tables / 'story-screens.json').write_text(json.dumps({'nativeScreenIds': ids}))
                    with self.assertRaises(ValueError):
                        be.native_screen_metadata()


class GeneratedStoryCache(unittest.TestCase):
    def test_missing_generated_index_never_disassembles_disc(self):
        from dws import backend as be
        with tempfile.TemporaryDirectory() as directory, \
             patch.object(be, 'DIS_CACHE', str(Path(directory) / 'generated')), \
             patch.object(be, 'dis', side_effect=AssertionError('disc script import')):
            with self.assertRaisesRegex(be.BackendError, 'missing generated story cache index'):
                be.ensure_dis()

    def test_ready_generated_cache_is_used_without_disc_import(self):
        from dws import backend as be
        with tempfile.TemporaryDirectory() as directory, \
             patch.object(be, 'DIS_CACHE', directory), \
             patch.object(be, 'dis', side_effect=AssertionError('disc script import')):
            (Path(directory) / 'dg.scn.lst').write_text('; owned generated cache\n')
            be.ensure_dis()


class EmptyDomains(unittest.TestCase):
    def test_empty_directories_remove_all_rows(self):
        with patch.object(content, 'load_techniques', return_value=None), \
             patch.object(content, 'load_items', return_value=None), \
             patch.object(content, 'load_screens', return_value=None):
            doc = content.doc()
        self.assertEqual(len(doc['techniques']), content.NUM_TECHS)
        self.assertEqual(len(doc['items']), content.NUM_ITEMS)
        self.assertEqual(len(doc['screens']), content.NUM_SCREENS)
        self.assertTrue(all(row['power'] == 0 for row in doc['techniques'].values()))
        self.assertTrue(all(row == content.EMPTY_ITEM for row in doc['items'].values()))
        self.assertTrue(all(row['fileBytes'] == [0] * 10 for row in doc['screens'].values()))


class EmptyMaps(unittest.TestCase):
    def test_empty_directory_clears_source_enemies(self):
        # The malformed, never-read map exception remains outside the gameplay parser.
        fake = SimpleNamespace(digimon=[{'type': 24}], digimon_count=1)
        fake.build = lambda: (fake.digimon_count, fake.digimon)
        with tempfile.TemporaryDirectory() as directory, \
             patch.object(content, 'MAPS_DIR', directory), \
             patch('dwmap.MapFile', return_value=fake):
            self.assertEqual(content.load_maps(), {})
            self.assertEqual(content.build_map('FOREST01', b'geometry and enemies'), (0, []))


class OwnedStory(unittest.TestCase):
    def test_missing_story_never_imports_disc(self):
        from dws import basebuild as story
        with tempfile.TemporaryDirectory() as directory, \
             patch.object(story, 'ensure_base', side_effect=AssertionError('disc import')):
            with self.assertRaisesRegex(story.DwsError, 'missing owned story source'):
                story._build([], str(Path(directory) / 'DG.SCN'), base=str(Path(directory) / 'missing'))

    def test_ready_story_does_not_refresh(self):
        from dws import basebuild as story
        with patch.object(story, 'ensure_base', side_effect=AssertionError('disc import')):
            story.require_base()

    def test_explicit_refresh_remains_an_authoring_operation(self):
        from dws import basebuild as story
        with patch.object(story, 'ensure_base') as imported:
            story.require_base(refresh=True, log=None)
            imported.assert_called_once_with(story.BASE, refresh=True, log=None)


if __name__ == '__main__':
    unittest.main()
