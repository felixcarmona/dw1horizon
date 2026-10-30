"""Retired package selections fail before a release directory or build is touched."""
import contextlib
import io
import json
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from tools.patcher import dwpatch as D


class ReleaseSelection(unittest.TestCase):
    def test_bundle_omits_only_unsupported_source_normalization(self):
        files = {name: name for name in (
            'content/imports/releases/dw3-us.json',
            'content/imports/releases/dw3-jp.json',
            'content/imports/releases/dw2-jp.json',
            'content/imports/releases/dcb-us.json',
            'tools/dw3release.py')}
        result = D.publication_bundle_files(files)
        self.assertEqual(set(files) - set(result),
                         {'content/imports/releases/dw3-us.json'})
        self.assertEqual(len(files), 5)

    def test_release_frontend_copies_the_repositories_actual_notices(self):
        with tempfile.TemporaryDirectory() as td:
            D.copy_release_frontend(td)
            out = Path(td)
            self.assertEqual((out / 'THIRD-PARTY.md').read_bytes(),
                             (Path(D.REPO) / 'THIRD-PARTY.md').read_bytes())
            self.assertEqual((out / 'dwpatch.py').read_bytes(), Path(D.__file__).read_bytes())
            self.assertTrue((out / 'isowriter.py').is_file())
            self.assertEqual((out / 'source-releases.md').read_bytes(),
                             (Path(D.REPO) / 'docs/data/source-releases.md').read_bytes())
            self.assertIn('(source-releases.md)', (out / 'README.md').read_text())
            self.assertNotIn('(../data/source-releases.md)', (out / 'README.md').read_text())

    def test_bundle_records_and_emits_without_the_retired_recipe(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            names = ['content/imports/releases/dw3-us.json',
                     'content/imports/releases/dw3-jp.json', 'tools/languages.py',
                     'tools/discs.py', 'tools/dw3release.py']
            for name in names:
                path = root / name
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text('{}')
            facts = root / 'facts.json'
            facts.write_text('{}')

            def record(cand, *args, **kwargs):
                self.assertFalse((Path(cand) / names[0]).exists())
                self.assertTrue((Path(cand) / names[1]).is_file())
                return {'steps': {}}, str(root / 'derived')

            listings = [SimpleNamespace(stdout='\n'.join(names)), SimpleNamespace(stdout='')]
            usa = SimpleNamespace(files={}, read=lambda name: self.fail(name))
            with patch.object(D, 'REPO', str(root)), \
                    patch.object(D.subprocess, 'run', side_effect=listings), \
                    patch.object(D, 'derive_run', side_effect=record), \
                    patch.object(D, 'derive_files', return_value={}), \
                    patch.object(D, 'needs_usa_paths', return_value=set()):
                bundle, extract, made = D.make_bundle_derive(
                    usa, str(root / 'work'), str(root / 'release'),
                    'everything', str(facts), source_discs=['dw2003=player.bin'])
            self.assertNotIn(names[0], bundle)
            self.assertIn(names[1], bundle)
            self.assertIn('tools/dw3release.py', bundle)
            self.assertFalse((root / 'release/bundle' / names[0]).exists())
            self.assertTrue((root / 'release/bundle' / names[1]).is_file())

    def args(self, **changes):
        fields=dict(format=3, holes='derive', recipe='everything', variant=['everything=unused.bin'],
                    source_disc=['dcb=cards.bin', 'dw2=world2.bin', 'dw2003=world3.bin'])
        fields.update(changes)
        return SimpleNamespace(**fields)

    def test_only_the_everything_derive_selection_reaches_the_save_gate(self):
        for changes in [dict(variant=['base=unused.bin']), dict(variant=['full=unused.bin']),
                        dict(variant=['everything=unused.bin', 'everything=other.bin']),
                        dict(variant=['everything=unused.bin,imports']), dict(format=2),
                        dict(holes='auto'), dict(holes='localbuild'), dict(recipe='other'),
                        dict(source_disc=[]), dict(source_disc=['dcb', 'dw2=b', 'dw2003=c']), dict(source_disc=['dcb=a', 'dcb=b', 'dw2=c'])]:
            with self.subTest(changes=changes), patch.object(D, 'save_check') as save, \
                    patch.object(D, 'cmd_make_release3') as build:
                with self.assertRaises(D.PatchError):
                    D.cmd_make_release(self.args(**changes))
                save.assert_not_called()
                build.assert_not_called()
        with patch.object(D, 'save_check') as save, patch.object(D, 'cmd_make_release3', return_value='built') as build:
            a = self.args(variant=['everything=unused.bin,map=linker.map,manifest=outputs.json'])
            self.assertEqual(D.cmd_make_release(a), 'built')
            save.assert_called_once_with(a)
            build.assert_called_once_with(a)

    def test_the_current_manifest_shape_is_readable(self):
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / 'manifest.json'
            m = dict(format=3, default='everything', source_discs=['dcb', 'dw2', 'dw2003'], variants={'everything': {'local': {'builder': 'derive'}}})
            path.write_text(json.dumps(m))
            self.assertEqual(D.load_release(td), m)
            for bad in [[], None, dict(m, variants=None), dict(m, variants=[]),
                        dict(m, variants={'everything': None}), dict(m, variants={'everything': {'local': []}}),
                        dict(m, source_discs=None), dict(m, source_discs=[{}]), dict(m, source_discs=[]), dict(m, format=2), dict(m, default='base'), dict(m, variants={'full': {}}),
                        dict(m, variants={'everything': {'local': {'builder': 'files'}}})]:
                path.write_text(json.dumps(bad))
                with self.assertRaises(D.PatchError):D.load_release(td)

    def test_retired_cli_options_are_rejected_by_the_parser(self):
        base=['make-release', '--original', 'unused.bin', '--variant', 'everything=unused.bin', '-o', 'unused']
        for flags in [['--holes', 'localbuild'], ['--holes', 'auto'], ['--format', '2'], ['--species-ram-mb', '8'], ['--repo', 'unused'], ['--holes-dir', 'unused']]:
            with self.subTest(flags=flags), contextlib.redirect_stderr(io.StringIO()), patch.object(D, 'cmd_make_release') as build:
                with self.assertRaises(SystemExit) as cm:D.main(base + flags)
                self.assertEqual(cm.exception.code, 2)
                build.assert_not_called()


if __name__ == '__main__':
    unittest.main()
