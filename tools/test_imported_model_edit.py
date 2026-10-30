"""Rejected model edits must leave the author's deltas and pins intact (temporary fixtures only)."""
import contextlib
import io
import json
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
import sys
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from tools.models import edit as v


class Put(unittest.TestCase):
    def test_rejected_field_overlay_preserves_deltas_and_manifest(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            row = dict(id=180, name='Veemon')  # a field overlay with reviewed source pins
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
            a = SimpleNamespace(id='180', mmd=str(edited), tim=None, force=False,
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


if __name__ == '__main__':
    unittest.main()
