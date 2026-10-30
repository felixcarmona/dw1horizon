#!/usr/bin/env python3
"""Release orchestration safety: no disc builds, browser or remote writes."""
import contextlib
import io
import json
import os
from pathlib import Path
import tempfile
import tarfile
import unittest
from unittest.mock import patch

import release


class ReleaseTests(unittest.TestCase):
    def test_dirty_tree_refused_before_any_command(self):
        with patch.object(release, 'git', return_value=' M README.md'), \
                patch.object(release.Run, 'cmd') as command, contextlib.redirect_stdout(io.StringIO()), \
                contextlib.redirect_stderr(io.StringIO()):
            self.assertEqual(release.main(['--dry-run']), 1)
            command.assert_not_called()

    def test_annotated_tag_must_match_head(self):
        info = dict(version='1.2.3', commit='head')
        with patch.object(release, 'clean'), patch('version.describe', return_value=info), \
                patch.object(release, 'git', side_effect=['tag', 'other']):
            with self.assertRaisesRegex(RuntimeError, 'exactly on'):
                release.identity('v1.2.3')
        with patch.object(release, 'clean'), patch('version.describe', return_value=info), \
                patch.object(release, 'git', return_value='commit'):
            with self.assertRaisesRegex(RuntimeError, 'annotated'):
                release.identity('v1.2.3')

    def test_complete_dry_run_has_no_mutations(self):
        with tempfile.TemporaryDirectory() as td:
            out = Path(td) / 'candidate'
            info = dict(version='0.0.0-dev.1+abcdef12', date='2026-10-28', commit='a' * 40)
            stdout = io.StringIO()
            with patch.object(release, 'identity', return_value=info), \
                    patch.object(release, 'git', side_effect=['/repo/.git', '160000 commit pin decomp']), \
                    patch.object(release.subprocess, 'Popen') as popen, \
                    contextlib.redirect_stdout(stdout):
                self.assertEqual(release.main(['--dry-run', '--out', str(out)]), 0)
                popen.assert_not_called()
            self.assertFalse(out.exists())
            text = stdout.getvalue()
            for step in ('make-release', 'jp1=', 'dw2003=',
                         'heapcheck.py', 'tools/dws.py story-build', 'selftest.sh',
                         'build-engine.sh', 'run.mjs', 'Standalone package apply'):
                self.assertIn(step, text)
            self.assertIn(f'ENGINE_WORK={out}/engine-work', text)
            self.assertNotIn('web/deploy.sh', text)
            self.assertIn('standalone-jp1', text)
            self.assertIn('-B -E -S', text)
            self.assertIn('venv --without-pip', text)
            self.assertIn('player-python', text)
            self.assertNotIn('git push', text)
            self.assertNotIn('gh release create', text)

    def test_deployment_requires_explicit_opt_in(self):
        with tempfile.TemporaryDirectory() as td:
            stdout = io.StringIO()
            with patch.object(release, 'identity', return_value={'version': '0.0.0-dev.1'}), \
                    patch.object(release, 'git', side_effect=['/repo/.git', '160000 commit pin decomp']), \
                    contextlib.redirect_stdout(stdout):
                self.assertEqual(release.main(['--dry-run', '--deploy', '--out', td]), 0)
            self.assertIn('web/deploy.sh', stdout.getvalue())

    def test_file_gate_failure_stops_before_build_or_deploy(self):
        with patch.object(release, 'identity', return_value={'commit': 'head'}), \
                patch.object(release.Run, 'cmd', side_effect=RuntimeError('save gate failed')) as cmd, \
                contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
            self.assertEqual(release.main(['--preflight-only']), 1)
            self.assertEqual(cmd.call_count, 1)
            self.assertIn('releases.py', str(cmd.call_args))

    def test_record_cache_invalidates_for_dynamic_graph_inputs(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            bundle = root / 'bundle'
            bundle.mkdir()
            source = bundle / 'recipe.json'
            source.write_text('first')
            (root / 'manifest.json').write_text(json.dumps({'bases': {'us': {}}, 'source_discs': ['dcb']}))
            first = release.record_key(root)
            # Packaging/version-only changes do not affect the derive graph.
            (root / 'literal.dwp').write_text('new executable')
            self.assertEqual(first, release.record_key(root))
            source.write_text('different reads, same nominal job names')
            self.assertNotEqual(first, release.record_key(root))

    def test_record_cache_tracks_extraction_mapping_and_reader_changes(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            (root / 'bundle').mkdir()
            (root / 'bundle/recipe.json').write_text('recipe')
            (root / 'bases').mkdir()
            mapping = root / 'bases/eu.json'
            mapping.write_text('regional mapping one')
            reader = root / 'dwpatch.py'
            reader.write_text('reader one')
            manifest = {'bases': {'us': {'sha1': 'input'}}, 'extract': ['ONE'],
                        'default': 'everything', 'variants': {'everything': {'local': {'recipe': 'everything'}}}}
            metadata = root / 'manifest.json'
            metadata.write_text(json.dumps(manifest))
            initial = release.record_key(root)
            # Tag/date and output pins change independently of extraction/derive.
            manifest.update(version='0.0.1', date='2026-10-29')
            manifest['variants']['everything']['outputs'] = {'us': {'sha1': 'new output'}}
            metadata.write_text(json.dumps(manifest))
            self.assertEqual(initial, release.record_key(root))
            mapping.write_text('regional mapping two')
            self.assertNotEqual(initial, release.record_key(root))
            mapping.write_text('regional mapping one')
            manifest['extract'] = ['ONE', 'TWO']
            metadata.write_text(json.dumps(manifest))
            self.assertNotEqual(initial, release.record_key(root))
            manifest['extract'] = ['ONE']
            metadata.write_text(json.dumps(manifest))
            reader.write_text('reader two')
            self.assertNotEqual(initial, release.record_key(root))
            reader.write_text('reader one')
            manifest['variants']['everything']['local']['recipe'] = 'other'
            metadata.write_text(json.dumps(manifest))
            self.assertNotEqual(initial, release.record_key(root))

    def test_selftest_environment_does_not_inherit_disc_settings(self):
        recipe = {'environment': {'TEXT': 'ours', 'LANGS': 'en,es', 'DW_HEAP_MAP': '/nonexistent'}}
        with patch.dict(release.os.environ, {'TEXT': 'ours', 'LANGS': 'en,es',
                        'DW_HEAP_MAP': '/nonexistent', 'DWS_RELAYOUT': '1',
                        'SCREEN_CONTENT': 'old-maps', 'W': 'private-decomp',
                        'HOME': '/tmp/player', 'PATH': '/bin'}, clear=True):
            self.assertEqual(release.offline_environment(recipe),
                             {'HOME': '/tmp/player', 'PATH': '/bin'})

    def test_archive_excludes_runtime_caches_and_keeps_player_files(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            package = root / 'package'
            for name in ('dwpatch.py', 'manifest.json', 'bundle/tools/derive.py',
                         '__pycache__/dwpatch.pyc', 'bundle/tools/__pycache__/derive.pyc', 'loose.pyc'):
                target = package / name
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_text('test fixture')
            archive = root / 'release.tar.gz'
            release.pack_release(package, archive)
            with tarfile.open(archive) as tar:
                names = {p.name for p in tar if p.isfile()}
            self.assertEqual(names, {'release-pkg/dwpatch.py', 'release-pkg/manifest.json',
                                     'release-pkg/bundle/tools/derive.py'})

    def test_notes_path_is_absolute_for_commands_run_from_checkout(self):
        with tempfile.TemporaryDirectory() as td:
            notes = Path(td) / 'notes.md'
            notes.write_text('Player notes')
            stdout = io.StringIO()
            previous = Path.cwd()
            try:
                os.chdir(td)
                with patch.object(release, 'identity', return_value={'version': '0.0.1'}), \
                        patch.object(release, 'git', side_effect=['/repo/.git', '160000 commit pin decomp']), \
                        contextlib.redirect_stdout(stdout):
                    self.assertEqual(release.main(['v0.0.1', '--publish', '--dry-run',
                                     '--notes-file', 'notes.md', '--out', str(Path(td) / 'candidate')]), 0)
            finally:
                os.chdir(previous)
            self.assertIn('--notes-file ' + str(notes), stdout.getvalue())

    def test_publish_requires_owner_tag_and_notes(self):
        with contextlib.redirect_stderr(io.StringIO()):
            with self.assertRaises(SystemExit) as err:
                release.main(['--publish', '--dry-run'])
            self.assertEqual(err.exception.code, 2)

    def test_reuse_routes_around_cold_build_and_requires_all_seal_inputs(self):
        with tempfile.TemporaryDirectory() as td:
            info = dict(commit='head', version='0.0.0-dev.1')
            with patch.object(release, 'identity', return_value=info), \
                    patch.object(release.Run, 'cmd') as command, \
                    patch('release_reuse.reuse') as reuse, \
                    patch.object(release, 'git') as git, \
                    contextlib.redirect_stdout(io.StringIO()):
                self.assertEqual(release.main(['--reuse-from', td, '--out', td + '/new']), 0)
                reuse.assert_called_once()
                git.assert_not_called()  # no decomp lookup or cold path
                self.assertEqual(command.call_count, len(release.FAST) + 1)
            with contextlib.redirect_stderr(io.StringIO()):
                with self.assertRaises(SystemExit):
                    release.main(['--prepare-reuse'])
                with self.assertRaises(SystemExit):
                    release.main(['--reuse-package', td])


if __name__ == '__main__':
    unittest.main()
