"""Partial hits must preserve the ordinary runner's shared-writer ordering."""
from pathlib import Path
import hashlib
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from tools.derive import cache, runner
from tools.build_cache import Cache


SCREEN_CALLS = {}


def encode_screen(i, row, text, opts):
    SCREEN_CALLS[i] = SCREEN_CALLS.get(i, 0) + 1
    if opts.get('spawn'):
        import subprocess
        import sys
        subprocess.run([sys.executable, '-c', 'pass'], check=True)
    return Path(row['source']).read_bytes() + text.encode(), len(text)


def edit(source, shared):
    before = Path(shared).read_text()
    Path(shared).write_text(before + Path(source).read_text())
    return 'edited'


def run_pass(root, out, argv, lowered, scrn, archive=None, facts=None):
    import os
    import tempfile
    maps = Path(argv[argv.index('--screen-content')+1])
    if os.environ.get('DW_BUILD_CACHE'):
        assert '/cache-story/' in str(maps.absolute()), maps
    target = maps / 'MAP.MAP'
    orig = maps / 'MAP.MAP.orig'
    if not orig.exists():
        from tools.dws.backend import keep_orig
        keep_orig(str(target))
    value = Path(argv[argv.index('--text-source')+1]).read_bytes()
    fd, tmp = tempfile.mkstemp(dir=maps)
    with os.fdopen(fd, 'wb') as f:
        f.write(orig.read_bytes() + value)
    os.replace(tmp, target)
    return 'story pass'


class DeriveCacheTests(unittest.TestCase):
    def test_private_map_preimages_allow_cached_story_replay(self):
        import shutil
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            build = root / 'build'
            maps = build / 'maps'
            maps.mkdir(parents=True)
            source = maps / 'MAP.MAP'
            source.write_bytes(b'recipe map')
            text = root / 'text'
            text.write_bytes(b'first')
            private = build / 'cache-story/0'
            args = (str(root), str(build / 'archive'),
                    ['--screen-content', str(maps), '--maps', str(maps), '--text-source', str(text)],
                    None, False)
            store = Cache(root / 'cache', build)
            def compile_pass():
                return {'log': cache.isolated_story(run_pass, args, str(private), [str(maps)])}
            _, hit = store.call({'story': 'private map fixture'}, compile_pass)
            self.assertFalse(hit)
            self.assertFalse(store.last_unsafe)
            self.assertEqual((private / '0/MAP.MAP').read_bytes(), b'recipe mapfirst')
            self.assertEqual(source.read_bytes(), b'recipe map')
            shutil.rmtree(private)
            self.assertTrue(store.call({'story': 'private map fixture'}, compile_pass)[1])
            self.assertEqual((private / '0/MAP.MAP').read_bytes(), b'recipe mapfirst')
            text.write_bytes(b'changed')
            self.assertFalse(store.call({'story': 'private map fixture'}, compile_pass)[1])
            self.assertEqual((private / '0/MAP.MAP').read_bytes(), b'recipe mapchanged')
            self.assertEqual(source.read_bytes(), b'recipe map')

    def test_screen_pieces_keep_dependencies_on_hits_inside_an_archive_cache(self):
        import os
        root = Path(runner.ROOT)
        with tempfile.TemporaryDirectory(dir=root / 'build', prefix='screen-cache-') as tmp:
            folder = Path(tmp)
            sources = [folder / name for name in ('a', 'b')]
            for p, value in zip(sources, (b'A', b'B')):
                p.write_bytes(value)
            SCREEN_CALLS.clear()
            env = {'DW_BUILD_CACHE': str(folder / 'cache')}
            with patch.dict(os.environ, env):
                def piece(i):
                    return cache.screen_piece(encode_screen, (i, {'source': str(sources[i])}, str(i), {}), folder / 'pieces')[0]
                # Populate individual records before the enclosing archive.
                self.assertEqual(piece(0), b'A0')
                self.assertEqual(piece(1), b'B1')
                whole = Cache(folder / 'cache', folder)
                output = folder / 'archive'
                def archive():
                    output.write_bytes(piece(0) + piece(1))
                    return {'built': True}
                _, hit = whole.call({'archive': True}, archive)
                self.assertFalse(hit)
                self.assertEqual(SCREEN_CALLS, {0: 1, 1: 1})
                import shutil
                shutil.rmtree(folder / 'pieces')
                output.unlink()
                self.assertTrue(whole.call({'archive': True}, archive)[1])
                stamp = sources[0].stat()
                sources[0].write_bytes(b'C')
                os.utime(sources[0], ns=(stamp.st_atime_ns, stamp.st_mtime_ns))
                self.assertFalse(whole.call({'archive': True}, archive)[1])
                self.assertEqual(output.read_bytes(), b'C0B1')
                self.assertEqual(SCREEN_CALLS, {0: 2, 1: 1})
                # The child's blob is also checked when the whole archive hits.
                whole.blob(hashlib.sha256(b'B1').hexdigest()).write_bytes(b'bad')
                self.assertFalse(whole.call({'archive': True}, archive)[1])
                self.assertEqual(output.read_bytes(), b'C0B1')
                self.assertEqual(SCREEN_CALLS, {0: 2, 1: 2})

    def test_unsafe_screen_work_cannot_be_hidden_by_its_archive_cache(self):
        root = Path(runner.ROOT)
        with tempfile.TemporaryDirectory(dir=root / 'build', prefix='screen-unsafe-') as tmp:
            folder = Path(tmp)
            source = folder / 'source'
            source.write_bytes(b'A')
            SCREEN_CALLS.clear()
            with patch.dict('os.environ', {'DW_BUILD_CACHE': str(folder / 'cache')}):
                whole = Cache(folder / 'cache', folder)
                def archive():
                    cache.screen_piece(encode_screen, (0, {'source': str(source)}, '0', {'spawn': True}), folder / 'pieces')
                    return {'built': True}
                self.assertFalse(whole.call({'archive': True}, archive)[1])
                self.assertFalse(whole.call({'archive': True}, archive)[1])
                self.assertEqual(SCREEN_CALLS, {0: 2})

    def test_real_screen_archive_reuses_unchanged_records(self):
        from functools import wraps
        from tools import screens
        root = Path(runner.ROOT)
        with tempfile.TemporaryDirectory(dir=root / 'build', prefix='screen-records-') as tmp:
            folder = Path(tmp)
            rows = {i: {'id': i, 'file': f'TEST{i}', '_path': str(folder / f'{i}.json')}
                    for i in (255, 256)}
            text = '.section 255 sec255\n.section 256 sec256\nsec255:\nEND_SECTION\nsec256:\nEND_SECTION\n'
            maphead = screens.bytecode.assemble_script(text, 'maphead.scn.txt')[0]
            expected = screens.build(rows, maphead)
            encode = screens.encode_record
            calls = []
            @wraps(encode)
            def measured(*args):
                calls.append(args[0])
                return encode(*args)
            piece = cache.screen_piece
            def local_piece(fn, args, stage, code_inputs=None):
                return piece(fn, args, folder / 'pieces', code_inputs)
            with patch.dict('os.environ', {'DW_BUILD_CACHE': str(folder / 'cache')}), \
                    patch.object(screens, 'encode_record', measured), \
                    patch.object(cache, 'screen_piece', local_piece):
                self.assertEqual(screens.build(rows, maphead, cache_records=True), expected)
                self.assertEqual(calls, [255, 256])
                calls.clear()
                self.assertEqual(screens.build(rows, maphead, cache_records=True), expected)
                self.assertEqual(calls, [])
                rows[255]['caption'] = 'changed caption'
                self.assertEqual(screens.build(rows, maphead, cache_records=True), screens.build(rows, maphead))
                # The raw comparison calls both encoders after the cached one.
                self.assertEqual(calls, [255, 255, 256])

    def test_shared_writers_with_partial_hit(self):
        root = Path(runner.ROOT)
        (root / 'build').mkdir(exist_ok=True)
        with tempfile.TemporaryDirectory(dir=root / 'build', prefix='cache-order-') as tmp:
            folder = Path(tmp)
            source_a, source_b, shared = (folder / n for n in ('a', 'b', 'shared'))
            source_a.write_text('A'); source_b.write_text('B')
            ctx = SimpleNamespace(root=str(root), out=str(folder), env={'TEXT': 'ours'}, facts={},
                                  cache_facts=True, cache_step='story', locks_read_only=True,
                                  jobs=2, record=False)
            original = [runner.Unit(n, edit, (str(source), str(shared)), order_group='maps')
                        for n, source in [('a', source_a), ('b', source_b)]]
            with patch.dict('os.environ', {'DW_BUILD_CACHE': str(folder / 'cache')}):
                wrapped = cache.units(ctx, original)
                shared.write_text('seed')
                done = runner.run_units(ctx, wrapped)
                self.assertEqual(shared.read_text(), 'seedAB')
                self.assertTrue(all('cache miss' in d.out for d in done))
                shared.write_text('seed')
                done = runner.run_units(ctx, wrapped)
                self.assertEqual(shared.read_text(), 'seedAB')
                self.assertTrue(all('cache hit' in d.out for d in done))
                source_b.write_text('C')
                shared.write_text('seed')
                done = runner.run_units(ctx, wrapped)
                self.assertEqual(shared.read_text(), 'seedAC')
                self.assertIn('cache hit', done[0].out)
                self.assertIn('cache miss', done[1].out)

    def test_isolated_story_matches_serial_last_writer_and_atomic_maps(self):
        root = Path(runner.ROOT)
        with tempfile.TemporaryDirectory(dir=root / 'build', prefix='story-cache-') as tmp:
            folder = Path(tmp)
            maps = folder / 'maps'
            maps.mkdir()
            sources = [folder / n for n in ('en', 'es', 'ca')]
            for n, p in enumerate(sources):
                p.write_text(str(n))
            ctx = SimpleNamespace(root=str(root), out=str(folder / 'out'), env={'TEXT': 'ours'}, facts={},
                                  cache_facts=True, cache_step='story', locks_read_only=False,
                                  jobs=3, record=False)
            original = [runner.Unit(str(i), run_pass,
                        (str(root), str(folder / str(i)), ['--screen-content', str(maps.relative_to(root)),
                         '--maps', str(maps), '--text-source', str(source)], None, False),
                        order_group='story maps and locks') for i, source in enumerate(sources)]
            (maps / 'MAP.MAP').write_text('seed')
            runner.run_units(ctx, original)
            expected = (maps / 'MAP.MAP').read_bytes()
            with patch.dict('os.environ', {'DW_BUILD_CACHE': str(folder / 'cache'),
                                          'DERIVE_UNIT_ORDER': 'reverse'}):
                for attempt in range(2):
                    (maps / 'MAP.MAP').write_text('seed')
                    (maps / 'MAP.MAP.orig').unlink()
                    import shutil
                    shutil.rmtree(folder / 'out', ignore_errors=True)
                    done = cache.run_units(ctx, original)
                    self.assertEqual((maps / 'MAP.MAP').read_bytes(), expected)
                    self.assertTrue(all(('cache hit' if attempt else 'cache miss') in d.out for d in done))
                sources[1].write_text('changed middle pass')
                (maps / 'MAP.MAP').write_text('seed')
                (maps / 'MAP.MAP.orig').unlink()
                shutil.rmtree(folder / 'out')
                done = cache.run_units(ctx, original)
                self.assertIn('cache miss', done[1].out)
                self.assertIn('cache hit', done[2].out)
                self.assertEqual((maps / 'MAP.MAP').read_bytes(), expected)

    def test_runtime_key_does_not_depend_on_prior_imports(self):
        cache.runtime_sources.cache_clear()
        first = cache.runtime_sources()
        import email.mime.multipart
        cache.runtime_sources.cache_clear()
        self.assertEqual(first, cache.runtime_sources())

    def test_unknown_environment_is_keyed(self):
        ctx = SimpleNamespace(out='out', env={'FUTURE_BUILD_FLAG': 'one'}, facts={},
                              cache_facts=False, locks_read_only=True)
        before = cache.identity(ctx, 'unit')
        ctx.env['FUTURE_BUILD_FLAG'] = 'two'
        self.assertNotEqual(before, cache.identity(ctx, 'unit'))

    def test_separate_command_trace_ids_do_not_invalidate_artifacts(self):
        ctx = SimpleNamespace(out='out', env={'TEXT': 'ours', 'CODEX_TOOL_CALL_ID': 'first'},
                              facts={}, cache_facts=False, locks_read_only=True)
        before = cache.identity(ctx, 'unit')
        ctx.env['CODEX_TOOL_CALL_ID'] = 'next command'
        self.assertEqual(before, cache.identity(ctx, 'unit'))


class CodeInputs(unittest.TestCase):
    def test_test_changes_do_not_invalidate_builds_but_imported_helpers_do(self):
        import sys
        with tempfile.TemporaryDirectory() as td, patch.object(runner, 'ROOT', td):
            root = Path(td)
            (root / 'tools').mkdir()
            helper = root / 'tools' / 'helper.py'; helper.write_text('helper = 1')
            test = root / 'tools' / 'test_example.py'; test.write_text('test = 1')
            try:
                cache.tool_key.cache_clear()
                first = cache.tool_key()
                test.write_text('test = 2')
                cache.tool_key.cache_clear()
                self.assertEqual(first, cache.tool_key())
                helper.write_text('helper = 2')
                cache.tool_key.cache_clear()
                self.assertNotEqual(first, cache.tool_key())
                with patch.dict(sys.modules, {'example_test_helper': SimpleNamespace(__file__=str(test))}):
                    loaded = cache.loaded_test_code()
                    test.write_text('test = 3')
                    self.assertNotEqual(loaded, cache.loaded_test_code())
            finally:
                cache.tool_key.cache_clear()


class RecordedSteps(unittest.TestCase):
    def test_facts_are_keyed_for_recorded_fact_consumers(self):
        from tools.derive.__main__ import Ctx
        with tempfile.TemporaryDirectory() as td, \
                patch.object(cache, 'tool_key', return_value='tools'), \
                patch.object(cache, 'runtime_sources', return_value='runtime'):
            root = Path(td)
            output = root / 'build/result'
            calls = []
            def build(ctx):
                calls.append(1)
                output.write_text(str(ctx.facts['limit']))
            mod = SimpleNamespace(NAME='fixture', FACTS=True, build=build)
            for limit in (1, 1, 2):
                output.parent.mkdir(exist_ok=True)
                if output.exists(): output.unlink()
                ctx = Ctx(str(output.parent), {'limit': limit}, record=True)
                ctx.root = str(root)
                with ctx.calling():
                    cache.record_step(ctx, mod, str(root / 'cache'))
                self.assertEqual(output.read_text(), str(limit))
            self.assertEqual(len(calls), 2)

    def test_reuse_preserves_real_trace_and_tracks_absent_probes(self):
        import os
        import shutil
        from tools.derive.__main__ import Ctx
        with tempfile.TemporaryDirectory() as td, \
                patch.object(cache, 'tool_key', return_value='tools'), \
                patch.object(cache, 'runtime_sources', return_value='runtime'):
            root = Path(td)
            source = root / 'source'; source.write_bytes(b'original')
            missing = root / 'optional'
            stat_only = root / 'stat-only'; stat_only.write_bytes(b'probe only')
            output = root / 'build/everything/result'
            calls = []
            def build(ctx):
                calls.append(1)
                data = source.read_bytes()
                assert stat_only.exists()
                if missing.exists():
                    data += missing.read_bytes()
                output.parent.mkdir(parents=True, exist_ok=True)
                output.write_bytes(data)
            mod = SimpleNamespace(NAME='fixture', build=build)
            traces = []
            for i in range(3):
                shutil.rmtree(root / 'build', ignore_errors=True)
                if i == 2:
                    missing.write_bytes(b'new')
                ctx = Ctx(str(output.parent), None, record=True)
                ctx.root = str(root)
                with ctx.calling():
                    cache.record_step(ctx, mod, str(root / 'cache'))
                traces.append(ctx.inputs)
                self.assertEqual(output.read_bytes(), b'original' + (b'new' if i == 2 else b''))
            self.assertEqual(len(calls), 2)
            self.assertEqual(traces[0], traces[1])
            self.assertIn(str(source), traces[1])
            self.assertTrue(all(str(stat_only) not in trace for trace in traces))
            self.assertFalse(any(str(root / 'cache') in p for trace in traces for p in trace))


if __name__ == '__main__':
    unittest.main()
