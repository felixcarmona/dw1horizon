#!/usr/bin/env python3
"""The emulator harness must boot past the intro movie and the first-start language picker (2026-11-03: every species
proof stalled there for want of the picker's `static` symbol), and must see every static the tests read."""

from pathlib import Path as _DevPath
import sys as _dev_sys
_dev_sys.path.insert(0, str(next(p for p in _DevPath(__file__).resolve().parents if (p / "tools").is_dir())))
import unittest
from unittest.mock import patch

from tools.dev import symbols as dwsyms
from tools.dev.playtest import species_proof as proof
from tools.dev.saves import releases


class FakeGame:
    """The title as the harness sees it: the movie (menu 0, ticks 0, picker pending) until START, then the picker over the
    title (ticks run), then the title menu once START answers the picker; a fresh start has no save so CONTINUE is not asked."""

    def __init__(self, has_picker_symbol=True):
        self.stage, self.pressed, self.symbols = 'movie', [], has_picker_symbol

    def has(self, name):
        return self.symbols or name != 'MOD_BOOT_LANGUAGE'

    def ram(self):
        return b''

    def peek(self, name, fmt, ram=None):
        if name == 'CURRENT_MENU': return 0
        if name == 'MAIN_MENU_TICKS': return 0 if self.stage == 'movie' else 50
        if name == 'MOD_BOOT_LANGUAGE': return 0 if self.stage == 'title' else 1
        if name == 'MENU_HIGHLIGHTS': return 1
        if name == 'MEMORY_CARD_ERROR': return 0
        raise KeyError(name)

    def press(self, button, frames=10):
        self.pressed.append(button)
        if button == 'START':
            self.stage = {'movie': 'picker', 'picker': 'title'}.get(self.stage, self.stage)

    def wait(self, seconds):
        pass    # (no real waiting in these tests)


def emu(game):
    e = releases.Emu.__new__(releases.Emu)
    for name in ('has', 'ram', 'peek', 'press', 'wait'):
        setattr(e, name, getattr(game, name))
    return e



class BootTests(unittest.TestCase):
    def test_start_ends_the_movie_and_answers_the_picker(self):
        game = FakeGame()
        self.assertTrue(emu(game).to_title())
        self.assertEqual(game.stage, 'title')
        self.assertEqual(set(game.pressed), {'START'})

    def test_a_picker_the_harness_cannot_see_is_not_reported_pending(self):
        self.assertFalse(emu(FakeGame(has_picker_symbol=False)).language_picker(b''))

    def test_continue_answers_the_picker_with_start_not_the_menu_arrows(self):
        game = FakeGame()
        e = emu(game)
        e.in_control = lambda *a: True
        e.continue_game()                      # (the fake never loads a save: it ends with the "never started" answer)
        self.assertEqual(game.stage, 'title')
        self.assertNotIn('UP', game.pressed)
        self.assertNotIn('DOWN', game.pressed)
        self.assertEqual(game.pressed[:2], ['START', 'START'])


class StaticSymbolsOfRealBuilds(unittest.TestCase):
    def test_every_build_that_has_the_picker_exposes_it(self):
        seen = 0
        for name, (exe, map_file) in list(dwsyms.CANDIDATES.items()):
            elf = map_file[:-len('.map')] if map_file else None
            try:
                with open(elf, 'rb') as stream: data = stream.read()
            except (OSError, TypeError):
                continue
            if b'MOD_BOOT_LANGUAGE\0' not in data: continue
            seen += 1
            self.assertIn('MOD_BOOT_LANGUAGE', dwsyms.table(name), name)
            self.assertIn('labCount', dwsyms.table(name), name)
        if not seen: self.skipTest('no build with the language picker is available')

    def test_species_proof_reads_statics_through_the_harness_table(self):
        class Table:
            def A(self, name): return {'labCount': 0x8013550C}[name]
        with patch.object(proof, 'EMU', Table()):
            self.assertEqual(proof.static_symbol('labCount'), 0x8013550C)


if __name__ == '__main__':
    unittest.main()
