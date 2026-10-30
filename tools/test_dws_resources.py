"""Pin story audio byte placement and actual-target heap CLI behavior before moves."""
import contextlib
import io
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parent))
from dws import bytecode as bytecode
from dws.checks import heap


class StoryResources(unittest.TestCase):
    def test_music_replaces_first_instruction_without_reordering(self):
        source = '.section 218 house\n.section 13 jungle\nhouse:\n SET_BGM 4\n SET_BGM 5\n END_SECTION\njungle:\n SET_BGM 6\n END_SECTION\n'
        data = bytecode.assemble_script(source, 'fixture', {'quiet': True})[0]
        sections = dict(bytecode.sweep(data)[1])
        expected = bytearray(data)
        expected[sections[218] + 1] = 0x22
        expected[sections[13] + 1] = 0x23
        with tempfile.TemporaryDirectory() as tmp:
            src, out = Path(tmp) / 'input', Path(tmp) / 'output'
            src.write_bytes(data)
            from dws import audio
            lines = audio.rewrite_maphead(src, out, Path(__file__).resolve().parents[1] / 'story/core/audio.json')
            self.assertEqual(out.read_bytes(), bytes(expected))
            self.assertEqual(len(lines), 2)
            self.assertIn('screen 218: SET_BGM 0x4 -> 0x22', lines[0])
            self.assertIn('screen 13: SET_BGM 0x6 -> 0x23', lines[1])

    def test_audio_intermediates_keep_the_bank_identity_required_by_the_codec(self):
        from dws import audio
        import sound
        for command in audio.bank_commands('output', 'scratch'):
            if command[0] == 'import-wav':
                self.assertEqual(sound.file_kind(command[1]), 'FAALL')

    def test_heap_checks_unique_setup_sections_and_counts_negative_margin(self):
        def disassemble(argv, **kwargs):
            (Path(argv[-1]) / 'maphead.scn.txt').write_text('.section 218 x\n.section 13 y\n.section 13 z\n.section 1237 t\n')
        def budget(screen, **kwargs):
            return dict(screen=screen, margin=-1 if screen == 13 else 0,
                        peak=100, worst=['fixture'], paths=[])
        with patch.object(sys, 'argv', ['heap', 'MAPHEAD.SCN', '--map', 'target.map',
                                      '--archive', 'DIGI.DAT', '--facts', 'facts.json']), \
             patch.object(heap.subprocess, 'run', side_effect=disassemble), \
             patch.object(heap.membudget, 'configure') as configure, \
             patch.object(heap.membudget, 'screen_budget', side_effect=budget) as check, \
             patch.object(heap.membudget, 'TRIMMED', False), \
             contextlib.redirect_stdout(io.StringIO()) as output:
            self.assertTrue(heap.main())
            self.assertEqual([c.args[0] for c in check.call_args_list], [13, 218])
            self.assertEqual(configure.call_args.kwargs['heap_map'], 'target.map')
            self.assertTrue(heap.membudget.TRIMMED)
            self.assertIn('2 screen setups checked', output.getvalue())
            self.assertIn('1 do not fit', output.getvalue())


if __name__ == '__main__':
    unittest.main()
