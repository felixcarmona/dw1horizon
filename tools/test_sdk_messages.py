"""Authored diagnostics preserve assembly slots, signatures and repeatability."""
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from tools import sdk_messages


class SdkMessagesTests(unittest.TestCase):
    def test_slots_keep_size_format_and_device_paths(self):
        spec = {'sample': [dict(text='Our %d\n', size=25)]}
        with tempfile.TemporaryDirectory() as td:
            root = Path(td); policy = root / 'tools/patcher'; policy.mkdir(parents=True)
            (policy / 'sdk-messages.json').write_text(json.dumps(spec))
            asm = root / 'asm/us/main/data/psyq'; asm.mkdir(parents=True)
            path = asm / 'sample.rodata.s'
            path.write_text('.asciz "Test diagnostic for %d!\\n"\n.align 2\n.asciz "bu00:"\n.asciz ""\n')
            with patch.object(sdk_messages, 'ROOT', root):
                self.assertEqual(sdk_messages.author(root), 1)
                first = path.read_bytes()
                self.assertIn(b'.space 17, 0', first)
                self.assertIn(b'bu00:', first)
                self.assertEqual(sdk_messages.author(root), 0)
                self.assertEqual(path.read_bytes(), first)

    def test_voice_reset_is_muted_and_keeps_the_register_record_shape(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td); policy = root / 'tools/patcher'; policy.mkdir(parents=True)
            (policy / 'sdk-messages.json').write_text('{}')
            asm = root / 'asm/us/main/data/psyq'; asm.mkdir(parents=True)
            path = asm / 'libsnd.data.s'
            path.write_text('dlabel_section voice_on\n' + '    .short 0x1234\n'*8 +
                            'enddlabel_section voice_on\ndlabel_section next_label\n')
            with patch.object(sdk_messages, 'ROOT', root):
                self.assertEqual(sdk_messages.author(root), 1)
                first = path.read_bytes()
                self.assertEqual(first.count(b'.short 0x0000'), 8)
                self.assertTrue(first.endswith(b'dlabel_section next_label\n'))
                self.assertEqual(sdk_messages.author(root), 0)
                self.assertEqual(path.read_bytes(), first)

    def test_changed_format_or_slot_is_rejected(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td); policy = root / 'tools/patcher'; policy.mkdir(parents=True)
            (policy / 'sdk-messages.json').write_text(json.dumps({'sample': [dict(text='New %s', size=8)]}))
            asm = root / 'asm/us/main/data/psyq'; asm.mkdir(parents=True)
            path = asm / 'sample.rodata.s'; path.write_text('.asciz "Old %d!"\n')
            with patch.object(sdk_messages, 'ROOT', root), self.assertRaisesRegex(ValueError, 'format'):
                sdk_messages.author(root)
            self.assertEqual(path.read_text(), '.asciz "Old %d!"\n')


if __name__ == '__main__':
    unittest.main()
