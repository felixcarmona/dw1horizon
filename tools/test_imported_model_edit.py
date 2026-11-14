"""Rejected model edits must leave the author's deltas and pins intact (temporary fixtures only)."""
import contextlib
import hashlib
import io
import json
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
import sys
from unittest.mock import Mock, patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from tools.models import edit as v


class ProviderPins(unittest.TestCase):
    def test_battle_repair_is_pinned_without_a_field_overlay(self):
        def species_file(out, sid, generate):
            base = Path(out).parent / 'imported-models'
            self.assertEqual((base / f'{sid}.MMD').read_bytes(), b'base model')
            final = Path(out).parent / 'battle.MMD'
            final.write_bytes(b'final battle model')
            return 'species.json', {'model': {'file': str(final)},
                                    'texture': {'file': str(base / f'{sid}.TIM')}}

        module = SimpleNamespace(species_file=species_file)
        spec = SimpleNamespace(loader=SimpleNamespace(exec_module=Mock()))
        with patch.object(v.importlib.util, 'spec_from_file_location', return_value=spec), \
                patch.object(v.importlib.util, 'module_from_spec', return_value=module), \
                patch.object(v, 'import_records', return_value={'289': {}}):
            actual = v.provider_pin(289, b'base model', b'texture')
        self.assertEqual(actual, [hashlib.sha1(b'final battle model').hexdigest(),
                                  hashlib.sha1(b'texture').hexdigest()])


class Put(unittest.TestCase):
    def test_rejected_field_overlay_preserves_deltas_and_manifest(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            row = dict(id=203, name='Veedramon')  # a gaits.py field overlay with reviewed source pins
            for kind, data in (('mmd', b'previous model'), ('tim', b'previous texture')):
                delta = v.modeldelta.encode(data, [b'source'])
                (root / (kind + '.mdelta')).write_bytes(delta)
                row[kind] = dict(delta=kind + '.mdelta', sources=[], delta_sha256=v.sha256(delta),
                                 sha256=v.sha256(data), size=len(data))
            manifest = root / 'models.json'
            manifest.write_text(json.dumps({'models': [row]}))
            edited = root / 'edited.MMD'
            edited.write_bytes(b'not a reviewed field model')
            before = {p.name: p.read_bytes() for p in root.iterdir()}
            a = SimpleNamespace(id='203', mmd=str(edited), tim=None, force=False,
                                games_dir=td, no_species_pins=False)
            with patch.object(v, 'ROOT', root), patch.object(v, 'MODELS', manifest), \
                    patch.object(v, 'provider', return_value=SimpleNamespace(keep=lambda: None)), \
                    patch.object(v, 'importing', side_effect=lambda _: contextlib.nullcontext()), \
                    patch.object(v, 'sources_of', return_value=[b'source']), \
                    patch.object(v, 'species_pins', return_value=(None, {'imports': {}})), \
                    contextlib.redirect_stdout(io.StringIO()):
                with self.assertRaisesRegex(ValueError, 'No reviewed field-acting profile'):
                    v.cmd_put(a)
            self.assertEqual(before, {p.name: p.read_bytes() for p in root.iterdir()})


class Repin(unittest.TestCase):
    """`edit.py repin` moves a species' reviewed-input pins and nothing else (the committed files, edited in memory)."""
    GAITS = v.ROOT / 'tools/models/field_animations/gaits.py'
    NEW, POST = 'a' * 64, 'b' * 64

    def test_profile_pin_moves_in_its_row_only(self):
        text = self.GAITS.read_text()
        old = json.loads(v.CHIBI_ROWS.read_text())['354']['source_sha256']
        moved = v.repin_profile(text, 354, old, self.NEW)
        changed = [(a, b) for a, b in zip(text.splitlines(), moved.splitlines()) if a != b]
        self.assertEqual(len(text.splitlines()), len(moved.splitlines()))
        self.assertEqual(len(changed), 1)
        self.assertTrue(changed[0][1].lstrip().startswith(f"354:dict(source='{self.NEW}'"))
        self.assertNotIn(old, moved)

    def test_profile_refuses_another_input_and_ignores_other_species(self):
        text = self.GAITS.read_text()
        with self.assertRaisesRegex(ValueError, 'not the current input'):
            v.repin_profile(text, 354, 'c' * 64, self.NEW)
        self.assertIsNone(v.repin_profile(text, 999, 'c' * 64, self.NEW))

    def test_chibi_row_moves_and_matches_the_new_input(self):
        rows = json.loads(v.CHIBI_ROWS.read_text())
        before = json.loads(json.dumps(rows))
        old = rows['354']['source_sha256']
        self.assertTrue(v.repin_chibi(rows, 354, old, self.NEW, self.POST))
        # chibi.build picks the one row whose source is the input
        self.assertEqual([sid for sid, row in rows.items() if row['source_sha256'] == self.NEW], ['354'])
        self.assertEqual(rows['354']['post_source_sha256'], self.POST)
        lines = [a != b for a, b in zip(json.dumps(before, indent=2).splitlines(), json.dumps(rows, indent=2).splitlines())]
        self.assertEqual(sum(lines), 2)
        with self.assertRaisesRegex(ValueError, 'not the current input'):
            v.repin_chibi(rows, 354, old, self.NEW, self.POST)
        self.assertFalse(v.repin_chibi(rows, 999, old, self.NEW, self.POST))

    def test_input_pinned_elsewhere_is_reported(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            (root / 'pins').mkdir()
            (root / 'pins' / 'moved.json').write_text('"' + 'd' * 64 + '"')
            (root / 'pins' / 'other.py').write_text("PIN = '" + 'd' * 64 + "'")
            with patch.object(v, 'ROOT', root), patch.object(v, 'PIN_FOLDERS', ('pins',)):
                stray = v.stray_pins({root / 'pins' / 'moved.json': '"' + self.NEW + '"'}, 'd' * 64)
        self.assertEqual(stray, ['pins/other.py'])


if __name__ == '__main__':
    unittest.main()
