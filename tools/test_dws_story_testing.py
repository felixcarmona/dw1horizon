"""Pin static graph and trace audit semantics before moving the story harness."""
from pathlib import Path
import sys
import unittest
sys.path.insert(0, str(Path(__file__).resolve().parent))
from dws import bytecode as bytecode
from dws.testing import sweep
from dws.testing import random_audit
from dws.testing import dialogue
from dws.testing import city_equivalence as city


class StoryTesting(unittest.TestCase):
    def test_reordered_sections_keep_instruction_graph(self):
        source = '.section 1 start\n.section 2 other\nstart:\n SET_TRIGGER 200\n JUMP_TO other\nother:\n SET_TRIGGER 201\n END_SECTION\n'
        moved = '.section 1 start\n.section 2 other\nother:\n SET_TRIGGER 201\n END_SECTION\nstart:\n SET_TRIGGER 200\n JUMP_TO other\n'
        graphs = []
        for text in (source, moved):
            raw = bytecode.assemble_script(text, 'fixture', {'quiet': True})[0]
            graphs.append(sweep.cfg_signature(raw, sweep.first_offsets(raw)[1]))
        self.assertEqual(*graphs)

    def test_random_audit_drops_only_layout_and_repeated_owner(self):
        events = [dict(kind='I', op=op, raw=bytes([op, arg]), key='fixture')
                  for op, arg in [(0x16, 0), (0x1b, 4), (0x1b, 4), (0x24, 7), (0x1b, 5)]]
        got = random_audit.kept(events)
        self.assertEqual([(e['op'], e['raw'][1]) for e in got], [(0x1b, 4), (0x24, 7), (0x1b, 5)])

    def test_dialogue_extractor_keeps_non_text_bytes(self):
        self.assertEqual(dialogue.extract(b'\xff' + 'ＡＢ'.encode('shift_jis') + b'\0'), '{ff}AB{00}')

    def test_c_oracle_extracts_full_nested_definition(self):
        source = 'int check(int x);\nint check(int x)\n{ if(x) { return 1; } return 0; }\nint next(void) { return 0; }'
        self.assertEqual(city.function(source, 'check'), 'int check(int x)\n{ if(x) { return 1; } return 0; }')


if __name__ == '__main__':
    unittest.main()
