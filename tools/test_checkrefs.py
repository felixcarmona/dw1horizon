#!/usr/bin/env python3
"""Reference checking still detects missing targets after resolving historical moves and release templates."""
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import checkrefs


class References(unittest.TestCase):
    def test_fragments_and_index_relative_paths(self):
        with tempfile.TemporaryDirectory() as root, patch.object(checkrefs, 'ROOT', root):
            Path(root, 'tools').mkdir()
            Path(root, 'guide.md').write_text('# Existing heading\n')
            Path(root, 'tools/README.md').write_text(
                '[good](../guide.md#existing-heading)\n'
                '[bad](../guide.md#missing)\n`obsolete.py`\n')
            bad, _ = checkrefs.check_file('tools/README.md', False)
            self.assertEqual(len(bad), 2)
            self.assertIn('fragment', bad[0][2])
            self.assertIn('obsolete.py', bad[1][2])
            Path(root, 'content/sound').mkdir(parents=True)
            Path(root, 'content/README.md').write_text('`sound/long-demo/`\n')
            self.assertTrue(checkrefs.check_file('content/README.md', False)[0])

    def test_relocated_evidence_requires_the_current_file(self):
        with tempfile.TemporaryDirectory() as root, patch.object(checkrefs, 'ROOT', root):
            target = Path(root, 'content/imports/specs/Monmon.json')
            target.parent.mkdir(parents=True)
            target.write_text('{}')
            old = 'mods/experimental/batch-import/specs/Monmon.json'
            self.assertTrue(checkrefs.exists(old))
            target.unlink()
            self.assertFalse(checkrefs.exists(old))
            self.assertFalse(checkrefs.exists(old.rsplit('/', 1)[0] + '/missing.json'))

    def test_release_template_does_not_hide_concrete_missing_files(self):
        with tempfile.TemporaryDirectory() as root, patch.object(checkrefs, 'ROOT', root):
            Path(root, 'mods/base-discs').mkdir(parents=True)
            missing = '/'.join(('mods', 'base-discs', 'dw1-missing.json'))
            Path(root, 'notes.md').write_text(f'`mods/base-discs/dw1-RELEASE.json`\n`{missing}`\n')
            bad, skipped = checkrefs.check_file('notes.md', False)
            self.assertEqual(bad, [('notes.md', 2, missing)])
            self.assertEqual(skipped, [('notes.md', 1, 'mods/base-discs/dw1-RELEASE.json')])


if __name__ == '__main__':
    unittest.main()
