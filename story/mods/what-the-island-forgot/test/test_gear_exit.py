"""Run the compiled Robot House floor guard against the original greeting."""
from itertools import product
from pathlib import Path
from types import SimpleNamespace
import sys
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(ROOT / 'tools'))
from dws import build, bytecode, presence

BASE = ROOT / 'story/base/zones/robot-house/s140-146/script.py'
QUEST = ROOT / 'story/mods/what-the-island-forgot/arcs/gear/robot-house.py'
LANGUAGES = ('en', 'es', 'ca', 'de', 'fr', 'it', 'ja', 'pt-br', 'zh-hans')


def event(program, section):
    return next(e[2] for e in program.b.scripts[140]['events'] if e[0] == section)


def floor_program(prefix, original):
    # Section 5 is a marker for reaching Tinmon's actual conversation. The floor's
    # movement and branch instructions are the real compiler output, unmodified.
    source = '\n'.join(['.section 51 start', 'start:', *prefix, *original,
                        '    END_SECTION', 'sec5:', '    SET_TRIGGER 1',
                        '    END_SECTION'])
    bytecode.assemble_script(source, 'Robot House floor', {'quiet': True})
    return presence.Program(source)


def run(program, triggers):
    state = SimpleNamespace(p={}, triggers=triggers, stats={})
    with patch.object(presence, 'program', return_value=program):
        return presence.run_original(51, state)[1]


class GearExit(unittest.TestCase):
    def test_pending_scan_releases_floor_in_every_language(self):
        for language in LANGUAGES:
            base = build.compile_sources([str(BASE)], 'mods', lang=language, text_source='ours')
            quest = build.compile_sources([str(QUEST)], 'mods', lang=language, text_source='ours')
            original = floor_program([], event(base, 51))
            fixed = floor_program(event(quest, 51), event(base, 51))
            # Include old saves with a pending scan, both completion states and
            # the original prerequisites. No new saved flags are needed.
            for pending, scanned, toys_done, waru_done in product((False, True), repeat=4):
                triggers = {flag for flag, on in ((742, pending), (743, scanned),
                                                 (350, toys_done), (270, waru_done)) if on}
                with self.subTest(language=language, triggers=triggers):
                    before = run(original, triggers)
                    after = run(fixed, triggers)
                    self.assertEqual('SET_TRIGGER 1' in before, waru_done and not toys_done)
                    if pending and not scanned:
                        self.assertEqual(after, [])  # no pull-back, turn, delay or talk
                    else:
                        self.assertEqual(after, before)  # homecoming remains available

    def test_choices_and_direct_reminder_keep_language_independent_control_flow(self):
        expected = None
        for language in LANGUAGES:
            quest = build.compile_sources([str(QUEST)], 'mods', lang=language, text_source='ours')
            # Translation changes the number of text pages; compare every
            # control instruction, including the ordered menu targets and flags.
            control = [line for line in event(quest, 5)
                       if not line.lstrip().startswith('"') and line.strip() != 'SHOW_TEXTBOX']
            if expected is None:
                expected = control
            with self.subTest(language=language):
                self.assertEqual(control, expected)
                self.assertIn('    SET_TRIGGER 742', control)
                self.assertIn('    JUMP_TO sec5', control)  # give it to the Toys
                self.assertTrue(any('trigger 742, and item 120 >= 1, and not trigger 743' in s
                                    for s in control))  # direct reminder remains


if __name__ == '__main__':
    unittest.main()
