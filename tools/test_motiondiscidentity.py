"""Asset-free alias/program identity checks; real ISO verification stays local."""
import unittest
from types import SimpleNamespace as N
from motiondiscidentity import changed_programs, program


class Animation:
    def __init__(self, body, tail=b''):
        self.body, self.tail = body, tail

    def build(self):
        return self.body+self.tail


def model(animations, table):
    return N(anims=N(anims=animations, table=table))


class IdentityTests(unittest.TestCase):
    def test_unconsumed_tail_does_not_change_consumed_program(self):
        source = Animation(b'program-END', b'unreferenced-stream')
        self.assertEqual(program(source), b'program-END')
        self.assertEqual(source.tail, b'unreferenced-stream')

    def test_repacking_and_parse_tail_changes_leave_slots_identical(self):
        a = model([Animation(b'a'), Animation(b'b')], [0, 1])
        b = model([Animation(b'b', b'unused'), Animation(b'a')], [1, 0])
        self.assertEqual(changed_programs(a, b), [])

    def test_alias_program_change_and_missing_slot_are_detected(self):
        a = model([Animation(b'a'), Animation(b'b')], [0, 1, None])
        b = model([Animation(b'a'), Animation(b'b')], [0, 0, 1])
        self.assertEqual(changed_programs(a, b), [1, 2])


if __name__ == '__main__':
    unittest.main()
