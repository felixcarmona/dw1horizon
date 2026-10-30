"""Recorded package logs must still advance the player's progress display."""
import unittest

from tools.patcher import dwpatch


class Progress(unittest.TestCase):
    def test_completed_step_preserves_its_name_and_duration(self):
        for line in ('derive models (recorded): 11 files, 1.25 s', 'derive models: 11 files, 1.25 s'):
            match = dwpatch.STEP_DONE.match(line)
            self.assertIsNotNone(match)
            self.assertEqual(match.groups(), ('models', '1.25'))
        for line in ('derive: 1.25 s, manifest.json', 'derive: step models failed: bad input',
                     'unit models (1.25 s)', 'derive models: missing output'):
            self.assertIsNone(dwpatch.STEP_DONE.match(line))


if __name__ == '__main__':
    unittest.main()
