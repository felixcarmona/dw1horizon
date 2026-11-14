"""The effect edits change only the random selector's allow-self operand and Deadly Bomb's throw."""
import struct
import unittest

from tools.derive.steps.effects import (CHUNK_SIZE, DEADLY_BOMB, LANDING, LANDING_HIT, LANDING_SOURCE, NIGHTMARE, SIZES,
                                       THROW, THROW_LEN, THROW_SOURCE, aim_deadly_bomb, aimed_throw, exclude_caster)


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



RET = b'\x0f\xcd'


def bomb_archive(block=THROW_SOURCE, landing=LANDING_SOURCE):
    """Chunk 74 whose start script is returns around the throw and the landing."""
    data = bytearray((DEADLY_BOMB + 1) * CHUNK_SIZE)
    base = DEADLY_BOMB * CHUNK_SIZE
    gap = (LANDING - THROW - THROW_LEN) // 2
    script = RET * (THROW // 2) + block + RET * gap + landing + RET * 8
    struct.pack_into('<2I', data, base, 0, len(script))
    data[base + 0x34:base + 0x34 + len(script)] = script
    return bytes(data)


class DeadlyBomb(unittest.TestCase):
    def test_only_the_throw_and_landing_change(self):
        source = bomb_archive()
        target = aim_deadly_bomb(source)
        head = DEADLY_BOMB * CHUNK_SIZE + 0x34
        throw, landing = head + THROW, head + LANDING
        self.assertEqual(len(source), len(target))
        self.assertEqual(source[:throw], target[:throw])
        self.assertEqual(target[throw:throw + THROW_LEN], aimed_throw())
        self.assertEqual(source[throw + THROW_LEN:landing], target[throw + THROW_LEN:landing])
        self.assertEqual(target[landing:landing + len(LANDING_HIT)], LANDING_HIT)
        self.assertEqual(source[landing + len(LANDING_HIT):], target[landing + len(LANDING_HIT):])

    def test_aimed_throw_is_whole_instructions(self):
        block, pc, subs = aimed_throw(), 0, []
        self.assertEqual(len(block), THROW_LEN)
        while pc < len(block):
            if block[pc] == 14:
                subs.append(block[pc + 1])
            pc += SIZES[block[pc]]
        self.assertEqual(pc, THROW_LEN)
        self.assertEqual(subs, [26, 14, 50, 72])   # copy from parent, target position, subtract, divide

    def test_unexpected_throw_fails(self):
        changed = bytearray(THROW_SOURCE)
        changed[-4] ^= 1
        sources = (bomb_archive(bytes(changed)), bomb_archive(landing=LANDING_HIT), aim_deadly_bomb(bomb_archive()), b'')
        for source in sources:
            with self.subTest(), self.assertRaises(ValueError):
                aim_deadly_bomb(source)

    def test_nightmare_edit_is_independent(self):
        size = max(NIGHTMARE, DEADLY_BOMB) + 1
        data = bytearray(size * CHUNK_SIZE)
        for chunk, source in ((NIGHTMARE, archive(SELECT)), (DEADLY_BOMB, bomb_archive())):
            data[chunk * CHUNK_SIZE:(chunk + 1) * CHUNK_SIZE] = source[chunk * CHUNK_SIZE:(chunk + 1) * CHUNK_SIZE]
        both = aim_deadly_bomb(exclude_caster(bytes(data)))
        self.assertEqual(both, exclude_caster(aim_deadly_bomb(bytes(data))))
        nightmare = slice(NIGHTMARE * CHUNK_SIZE, (NIGHTMARE + 1) * CHUNK_SIZE)
        self.assertEqual(both[nightmare], exclude_caster(bytes(data))[nightmare])


if __name__ == '__main__':
    unittest.main()
