"""The Sanctuary keeper must satisfy the city hint library's speaker contract."""
from pathlib import Path
import re
import sys
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(ROOT / 'tools'))
from dws.build import compile_sources


@unittest.skipUnless((ROOT / 'extracted/SCN/DG.SCN').exists(), 'needs extracted/')
class KeeperHints(unittest.TestCase):
    def test_every_shared_hint_speaker_is_placed_by_the_caller(self):
        keeper = ROOT / 'story/mods/what-the-island-forgot/arcs/vault/melted-wall.py'
        library = ROOT / 'story/base/zones/libraries/s211/script.py'
        map_path = ROOT / 'build/what-the-island-forgot-maps/screens/VALT02.MAP'
        # This check compiles declarations and bytecode; map geometry is covered
        # by the disc build. It does not require generated map artwork.
        import os
        real_exists = os.path.exists
        with patch('os.path.exists', side_effect=lambda p: Path(p) == map_path or real_exists(p)):
            program = compile_sources([str(keeper), str(library)], exe='mods')
        placements = [p for p in program.b.placements if p[0] == 311]
        self.assertEqual(len(placements), 1)
        self.assertEqual(placements[0][1], 0)  # no additional actor or model
        speaker = placements[0][3].get('section', 5 + placements[0][1])
        owners = {int(m.group(1)) for event in program.b.scripts[211]['events']
                  for line in event[2] if (m := re.fullmatch(r'\s*SET_DIALOG_OWNER (\d+)', line))
                  and int(m.group(1)) < 200}
        self.assertTrue(owners)
        self.assertEqual(owners, {speaker})
        own_script = next(v for k, v in program.b.scripts.items() if k != 211)
        self.assertTrue(any(event[0] == speaker and '    JUMP_TO_FILE 211, 8' in event[2]
                            for event in own_script['events']))
