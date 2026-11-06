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


class SaveTransitionTests(unittest.TestCase):
    def test_warp_pauses_memory_writes_and_resumes_after_an_error(self):
        from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
        from threading import Thread
        from urllib.parse import parse_qs, urlsplit
        from tools.dev.saves.releases import Emu

        class Flow(BaseHTTPRequestHandler):
            def log_message(self, *args):
                pass

            def do_GET(self):
                self.send_response(200)
                self.end_headers()
                self.wfile.write(json.dumps({'running': self.server.running}).encode())

            def do_POST(self):
                function = parse_qs(urlsplit(self.path).query)['function'][0]
                self.server.running = function == 'start'
                self.send_response(200)
                self.end_headers()

        with ThreadingHTTPServer(('127.0.0.1', 0), Flow) as server:
            server.running = True
            thread = Thread(target=server.serve_forever, kwargs={'poll_interval': .01})
            thread.start()
            try:
                for fail in (False, True):
                    with self.subTest(write_failure=fail):
                        emu = Emu.__new__(Emu)
                        emu.port = server.server_port
                        emu.wait = lambda seconds: None
                        emu.ram = lambda: b'RAM'
                        emu.peek = lambda name, fmt, ram: 218 if name == 'CURRENT_SCREEN' else 0
                        def write(name, data):
                            self.assertFalse(server.running, 'memory write raced a running field frame')
                            if fail:
                                raise RuntimeError('write failed')
                        emu.poke = write
                        if fail:
                            with self.assertRaisesRegex(RuntimeError, 'write failed'):
                                emu.warp(218)
                        else:
                            self.assertTrue(emu.warp(218))
                        self.assertTrue(server.running)
            finally:
                server.shutdown()
                thread.join()


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
            groups = []
            original = release.Run.cmds
            def capture(run, jobs, *args, **kwargs):
                groups.append(jobs)
                return original(run, jobs, *args, **kwargs)
            with patch.object(release.Run, 'cmds', new=capture), \
                    patch.object(release, 'identity', return_value=info), \
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
            replay = next(group for group in groups if 'engine' in group)
            self.assertEqual(set(replay), {'us', 'jp1', 'eu+dw3-us', 'engine'})
            self.assertEqual(replay['engine'][2]['ENGINE_WORK'], str(out / 'engine-work'))
            self.assertTrue(Path(replay['engine'][0][0]).is_absolute())
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

    def test_record_cache_covers_environment_modes_inventory_and_source_bytes(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            (root/'bundle').mkdir()
            (root/'bundle/input').write_bytes(b'data')
            (root/'manifest.json').write_text(json.dumps({'bases': {'us': {}}}))
            disc = root/'source.bin'
            disc.write_bytes(b'source one')
            def key(env=None):
                return release.record_key(root, env or {'SETTING': 'one'}, [('source', disc)])
            previous = key()
            self.assertNotEqual(previous, key({'SETTING': 'two'}))
            self.assertEqual(previous, key({'SETTING': 'one', 'NAME': 'another-native-build'}))
            (root/'bundle/empty').mkdir()
            self.assertNotEqual(previous, key()); previous = key()
            (root/'bundle/input').chmod(0o600)
            self.assertNotEqual(previous, key()); previous = key()
            (root/'bundle/empty').chmod(0o700)
            self.assertNotEqual(previous, key()); previous = key()
            old = disc.stat()
            disc.write_bytes(b'source two')
            os.utime(disc, ns=(old.st_atime_ns, old.st_mtime_ns))
            self.assertNotEqual(previous, key())

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



class ParallelCommands(unittest.TestCase):
    def test_all_run_at_once_with_their_logs(self):
        with tempfile.TemporaryDirectory() as td:
            td = Path(td)
            runs = {k: (['sh', '-c', f'sleep 1; echo {k}'], td / f'{k}.log') for k in ('a', 'b', 'c')}
            r = release.Run(False, td)
            with contextlib.redirect_stdout(io.StringIO()):
                start = release.time.monotonic()
                r.cmds(runs)
                self.assertLess(release.time.monotonic() - start, 2.9)
            for k in runs:
                self.assertEqual((td / f'{k}.log').read_text().strip(), k)

    def test_a_failure_stops_the_others(self):
        with tempfile.TemporaryDirectory() as td:
            td = Path(td)
            runs = {'slow': (['sh', '-c', f'sleep 30; touch {td}/late'], td / 'slow.log'),
                    'bad': (['sh', '-c', 'echo broken; exit 3'], td / 'bad.log')}
            out = io.StringIO()
            with contextlib.redirect_stdout(out), self.assertRaises(RuntimeError):
                release.Run(False, td).cmds(runs)
            self.assertIn('broken', out.getvalue())
            self.assertFalse((td / 'late').exists())

if __name__ == '__main__':
    unittest.main()
