"""Imported NPC masks and resident/cold animation accounting."""
import contextlib
import io
from pathlib import Path
import struct
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path[:0] = [str(Path(__file__).resolve().parent), str(Path(__file__).resolve().parents[1])]
import npcanims as n
from derive.facts import npc_keep


class ImportedNpcTests(unittest.TestCase):
    def test_script_slot_is_shared_by_imports_without_expanding_native_index(self):
        with tempfile.TemporaryDirectory() as work:
            root = Path(work)
            (root / 'map').write_bytes(b'map')
            (root / 'maphead.txt').write_text('sec207:\n SET_SCRIPT 12, 0\n')
            (root / 'script_12.scn.txt').write_text(' PLAY_ANIMATION 0, 21\n')
            actor = type('Map', (), {'digimon': [{'type': 184, 'scriptId': 0}]})()
            with patch.object(n.mb, 'MAPS', {207: {}}), \
                 patch.object(n.mb, 'map_path', return_value=str(root / 'map')), \
                 patch.object(n.dwmap, 'MapFile', return_value=actor), \
                 patch.object(n, 'ALWAYS', n.ALWAYS.copy()):
                keep, _, unresolved = n.audit(work, str(root / 'maphead.txt'))
            self.assertFalse(unresolved)
            self.assertIn(21, keep[184])
            self.assertIn(21, keep[471])
            self.assertNotIn(21, keep[1])
            output = root / 'keep.c'
            with patch.object(n, 'audit', return_value=(keep, {}, [])), \
                 patch('sys.argv', ['npcanims.py', 'gen', str(output)]), \
                 contextlib.redirect_stdout(io.StringIO()):
                n.main()
            text = output.read_text()
            self.assertIn('NPC_ANIM_KEEP_INDEX[180]', text)
            self.assertIn('NPC_ANIM_IMPORT_KEEP = ', text)
            self.assertEqual(npc_keep(text), [sorted(keep[t]) for t in range(1024)])

    def test_cold_entries_are_not_resident_stream_boundaries(self):
        # Four table entries: two resident streams, a cold marker and an alias.
        data = struct.pack('<6I', 0, 8, 16, 0x80050008, 20, 16) + b'abcdefgh'
        ta, offsets, sizes = n.mmd_slots(data)
        self.assertEqual(ta, 8)
        self.assertEqual(offsets, [16, 0x80050008, 20, 16])
        self.assertEqual(sizes, {16: 4, 20: 4})

    def test_older_target_does_not_claim_import_savings(self):
        with patch.object(n.mb, 'TARGET_FACTS', {'npc_anim_keep': [[]] * 180}), \
             patch.object(n.mb, 'model_data', return_value=struct.pack('<4I', 0, 8, 4, 0)):
            n.trimmed_size.cache_clear()
            self.assertEqual(n.trimmed_size(184), 16)
        n.trimmed_size.cache_clear()


if __name__ == '__main__':
    unittest.main()
