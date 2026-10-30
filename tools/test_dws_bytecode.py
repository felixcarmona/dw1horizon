"""Characterize the story binary API independently of its module location."""
from pathlib import Path
import sys
import unittest
from unittest.mock import patch
sys.path.insert(0, str(Path(__file__).resolve().parent))
from dws import bytecode as B


class Bytecode(unittest.TestCase):
    def test_wide_screen_and_reachable_instruction_targets(self):
        source = '.section 17 start\n.section 314 other\nstart:\n SET_SCRIPT 18, 17\n JUMP_TO done\nother:\n SET_SCRIPT 18, 314\ndone:\n END_SECTION\n'
        data = B.assemble_script(source, 'fixture', {'quiet': True})[0]
        _, sections, instructions, _, _ = B.sweep(data)
        self.assertEqual([sid for sid, _ in sections], [17, 314])
        addresses = dict(instructions)
        for address in addresses:
            size, targets = B.instr_length(data, address)
            self.assertGreater(size, 0)
            self.assertTrue(all(target in addresses for target in targets))
        self.assertEqual(B.u16(data, sections[1][1] + 4), 314)

    def test_cached_disassembly_rebuilds_when_codec_identity_changes(self):
        import tempfile
        from dws import backend
        with tempfile.TemporaryDirectory() as tmp:
            cache = str(Path(tmp) / 'cache')
            def disassemble(source, target):
                Path(target).mkdir()
                (Path(target) / 'dg.scn.lst').write_text('fixture')
            with patch.object(backend, 'DIS_CACHE', cache), \
                 patch.object(backend, 'DIS_DEFAULT', cache), \
                 patch.object(backend, 'dis', side_effect=disassemble) as dis, \
                 patch.object(backend.bytecode, 'source_digest', side_effect=['first', 'first', 'second']):
                backend.ensure_dis()
                backend.ensure_dis()
                backend.ensure_dis()
            self.assertEqual(dis.call_count, 2)

    def test_box_policy_participates_in_the_codec_cache_identity(self):
        before = B.source_digest()
        read = Path.read_bytes
        def changed(path):
            data = read(path)
            return data + b'\n# changed box policy' if path.name == 'profiles.py' else data
        with patch.object(Path, 'read_bytes', changed):
            self.assertNotEqual(B.source_digest(), before)

    def test_original_disc_roundtrip_is_exact(self):
        import tempfile
        for name in ('DG.SCN', 'MAPHEAD.SCN'):
            path = Path(__file__).resolve().parents[1] / 'extracted/SCN' / name
            if not path.is_file():
                self.skipTest('requires the original disc extraction')
            with tempfile.TemporaryDirectory() as tmp:
                folder = Path(tmp) / 'text'
                B.dis(str(path), str(folder))
                source = folder if name == 'DG.SCN' else folder / 'maphead.scn.txt'
                out = Path(tmp) / name
                B.asm(str(source), str(out))
                self.assertEqual(out.read_bytes(), path.read_bytes())


if __name__ == '__main__':
    unittest.main()
