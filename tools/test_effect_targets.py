"""The effect edit changes only the random selector's allow-self operand."""
import struct
import unittest

from tools.derive.steps.effects import CHUNK_SIZE, NIGHTMARE, exclude_caster


def archive(script):
    data = bytearray((NIGHTMARE + 1) * CHUNK_SIZE)
    base = NIGHTMARE * CHUNK_SIZE
    struct.pack_into('<2I', data, base, 0, len(script))
    data[base + 0x34:base + 0x34 + len(script)] = script
    return bytes(data)


SELECT = struct.pack('<4H', 0xcd0a, 1, 0, 0x4b0e)


class EffectTargets(unittest.TestCase):
    def test_only_allow_self_changes(self):
        source = archive(SELECT)
        target = exclude_caster(source)
        self.assertEqual(len(source), len(target))
        self.assertEqual([i for i, (a, b) in enumerate(zip(source, target)) if a != b],
                         [NIGHTMARE * CHUNK_SIZE + 0x36])

    def test_data_is_not_an_instruction(self):
        # The selector word inside an immediate operand must stay untouched.
        source = archive(SELECT + struct.pack('<3H', 0xcd0a, 0x4b0e, 0))
        target = exclude_caster(source)
        self.assertEqual(source[-CHUNK_SIZE + 0x3c:], target[-CHUNK_SIZE + 0x3c:])

    def test_unexpected_scripts_fail(self):
        for script in (SELECT * 2, b'\x0e\x4b', SELECT.replace(b'\x01\x00', b'\x00\x00'),
                       b'\xff\xff', SELECT + b'\x0a\xcd'):
            with self.subTest(script=script), self.assertRaises(ValueError):
                exclude_caster(archive(script))

    def test_truncated_archive_fails(self):
        with self.assertRaises(ValueError):
            exclude_caster(b'')


if __name__ == '__main__':
    unittest.main()
