"""Patcher path and interrupted-write regressions, without game inputs."""
import contextlib
import io
from pathlib import Path
import sys
import tempfile
import types
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parent / 'patcher'))
import dwpatch as dw


class Paths(unittest.TestCase):
    def test_output_folder_alias_cannot_replace_original(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            source = root / 'Horizon.bin'
            source.write_bytes(b'original')
            alias = root / 'alias'
            try:
                alias.symlink_to(root, target_is_directory=True)
            except OSError:
                self.skipTest('directory symlinks unavailable')
            a = types.SimpleNamespace(variant=None, disc=str(source), output=str(alias), verbose=True)
            variant = dict(local={'builder': 'derive'}, output={'name': 'Horizon'})
            manifest = dict(default='everything', variants={'everything': variant}, python_min=[3, 10])
            with self.assertRaisesRegex(dw.PatchError, 'overwrite your original'):
                dw.cmd_apply3(a, td, manifest)
            self.assertEqual(source.read_bytes(), b'original')

    def test_utf8_cue_with_spaces_and_unicode(self):
        with tempfile.TemporaryDirectory() as td:
            folder = Path(td).joinpath(*(['long folder ' * 5] * 5))
            folder.mkdir(parents=True)
            image = folder / '日本語 disc.bin'
            image.write_bytes(b'original')
            cue = folder / 'disc.cue'
            for encoding in ('utf-8', 'utf-8-sig'):
                with self.subTest(encoding=encoding):
                    cue.write_text(f'FILE "{image.name}" BINARY\n', encoding=encoding)
                    self.assertEqual(dw.resolve_bin(str(cue)), str(image))

    def test_legacy_cue_and_malformed_file_line(self):
        with tempfile.TemporaryDirectory() as td:
            image = Path(td) / 'Français.bin'
            image.write_bytes(b'original')
            cue = Path(td) / 'disc.cue'
            cue.write_bytes(f'FILE "{image.name}" BINARY\n'.encode('latin-1'))
            self.assertEqual(dw.resolve_bin(str(cue)), str(image))
            for line in ('FILE', 'FILE "unterminated'):
                cue.write_text(line)
                with self.assertRaises(dw.PatchError):
                    dw.resolve_bin(str(cue))

    def test_interrupted_output_preserves_previous_disc_and_removes_partial(self):
        with tempfile.TemporaryDirectory() as td, contextlib.ExitStack() as stack:
            folder = Path(td)
            source = folder / 'original.bin'
            source.write_bytes(b'original')
            output = folder / 'Horizon.bin'
            output.write_bytes(b'previous complete disc')
            a = types.SimpleNamespace(variant=None, disc=str(source), output=td, verbose=True)
            variant = dict(local={'builder': 'derive'}, output={'name': 'Horizon'}, description='test', outputs={})
            manifest = dict(default='everything', variants={'everything': variant}, python_min=[3, 10],
                            version='test', commit='test', bases={'us': {'title': 'test'}})
            screen = types.SimpleNamespace(start=lambda *a: None, log=lambda *a: None)
            for name, value in (('SCREEN', None), ('Screen', lambda *a, **k: screen),
                                ('apply_phases', lambda *a: []), ('release_line', lambda *a: 'test'),
                                ('identify_base', lambda *a: ('us', str(source), {})),
                                ('read_patch_file', lambda *a: b''), ('read_payload3', lambda *a: {}),
                                ('BaseDisc', lambda *a, **k: None), ('local_holes3', lambda *a: {})):
                stack.enter_context(patch.object(dw, name, value))

            def interrupted(p, base, holes, path, expect):
                Path(path).write_bytes(b'partial disc')
                raise KeyboardInterrupt

            stack.enter_context(patch.object(dw, 'build_disc3', interrupted))
            with contextlib.redirect_stdout(io.StringIO()), self.assertRaises(KeyboardInterrupt):
                dw.cmd_apply3(a, td, manifest)
            self.assertEqual(output.read_bytes(), b'previous complete disc')
            self.assertEqual(source.read_bytes(), b'original')
            self.assertFalse(Path(str(output) + '.part').exists())
            self.assertEqual(list(folder.glob('*.part')), [])


if __name__ == '__main__':
    unittest.main()
