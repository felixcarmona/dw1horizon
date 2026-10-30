#!/usr/bin/env python3
"""Regressions for Python story constructs that used to silently lose information."""
import os
from types import SimpleNamespace
import unittest

from dws.alloc import Allocator
from dws.diag import DwsError
from dws.py import lower as PL
from dws.py.lower import PyError, lower_file


def lower(body):
    return lower_file('/tmp/story-safety.py', src='''from dw import *
room = screen(1)
bug = room.npc(Species.Kunemon, slot=1)
''' + body)[1]


class FunctionArguments(unittest.TestCase):
    def reward(self, call, signature='amount=10'):
        return lower(f'''def reward({signature}):
    give(bits=amount)
@bug.on_talk
def talk():
    {call}
''')

    def test_unknown_keyword_is_not_silently_discarded(self):
        with self.assertRaisesRegex(PyError, 'unexpected keyword.*amunt'):
            self.reward('reward(amunt=999)')

    def test_keyword_cannot_replace_positional_argument(self):
        with self.assertRaisesRegex(PyError, 'multiple values.*amount'):
            self.reward('reward(10, amount=999)')

    def test_duplicate_keyword_is_not_last_writer_wins(self):
        with self.assertRaisesRegex(PyError, 'multiple values.*amount'):
            self.reward('reward(amount=10, amount=999)')

    def test_unsupported_signatures_are_reported_at_definition(self):
        for signature in ('*, amount=10', 'amount, /', '*amount', '**amount'):
            with self.subTest(signature=signature):
                with self.assertRaisesRegex(PyError, 'plain parameters'):
                    self.reward('reward()', signature)

    def test_defaults_and_named_arguments_still_bind(self):
        for call, amount in [('reward()', 10), ('reward(20)', 20), ('reward(amount=30)', 30)]:
            with self.subTest(call=call):
                self.assertIn(f'give_bits({amount});', self.reward(call))


class AllocationHints(unittest.TestCase):
    def test_python_range_hint_uses_provenance_not_folder_name(self):
        for path, mapped in [('/tmp/custom-story-output/decl.dws', True),
                             ('/tmp/py-lowered-handwritten.dws', False)]:
            with self.subTest(path=path):
                path = os.path.abspath(path)
                if mapped: PL.LINEMAP[path] = (path, {1: 1}, '/tmp/source.py')
                try:
                    with self.assertRaises(DwsError) as caught:
                        Allocator().declare('var', 'save', 'test.counter', 21, False,
                                            SimpleNamespace(pos=(path, 1, 1)))
                    self.assertIn('[save]' if mapped else 'use `alias', caught.exception.hint)
                finally:
                    if mapped: PL.LINEMAP.pop(path)


class MatchBranches(unittest.TestCase):
    def test_guards_are_never_silently_dropped(self):
        examples = [
            ('choose(yes="Yes", no="No")', '"yes"', '', ''),
            ('pstat(7)', '0', '', '        case 1 | _:\n            give(bits=200)\n'),
            ('Quest1.stage', 'Quest1.OPEN', 'class Quest1(Quest):\n    OPEN = auto()\n    DONE = auto()\n', ''),
        ]
        for subject, pattern, prefix, suffix in examples:
            with self.subTest(subject=subject):
                with self.assertRaisesRegex(PyError, 'case.*takes no `if`'):
                    lower(prefix + f'''@bug.on_talk
def talk():
    match {subject}:
        case {pattern} if pstat(8) == 1:
            give(bits=100)
''' + suffix)

    def test_duplicate_menu_case_cannot_overwrite_first_branch(self):
        with self.assertRaisesRegex(PyError, 'answered above'):
            lower('''@bug.on_talk
def talk():
    match choose(yes="Yes", no="No"):
        case "yes":
            give(bits=100)
        case "yes":
            give(bits=200)
''')

    def test_distinct_menu_branches_are_preserved(self):
        code = lower('''@bug.on_talk
def talk():
    match choose(yes="Yes", no="No"):
        case "yes":
            give(bits=100)
        case "no" | _:
            give(bits=200)
''')
        self.assertIn('give_bits(100);', code)
        self.assertIn('"No" or cancel', code)
        self.assertIn('give_bits(200);', code)




if __name__ == '__main__':
    unittest.main()
