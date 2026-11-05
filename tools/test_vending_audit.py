"""Regression checks for resale, bonus, bag filtering and daily-stock exploits."""
import unittest
from pathlib import Path

from vending_audit import ROOT, check_vending, item_ids, run_handler


class VendingEconomy(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        import json
        cls.items = {d['id']: d for p in (ROOT / 'content/items').glob('*.json')
                     for d in [json.loads(p.read_text())]}
        cls.worth = {i: d['value'] // 2 if d['droppable'] else 0 for i, d in cls.items.items()}
        cls.names = {i: d['name'] for i, d in cls.items.items()}
        cls.sources = {sid: next((ROOT / 'story/base/zones').glob(f'*/s{sid:03d}-*/script.py')).read_text()
                       for sid in (9, 12, 71, 78)}

    def failures(self, sid=None, before=None, after=None, worth=None):
        sources = dict(self.sources)
        if sid:
            self.assertIn(before, sources[sid])
            sources[sid] = sources[sid].replace(before, after)
        return check_vending(worth or self.worth, self.names, sources, log=lambda _: None)[0]

    def test_current_machines(self):
        self.assertEqual([], self.failures())

    def test_exact_slot_odds_and_bonus(self):
        from collections import Counter
        awards = Counter()
        for roll in range(100):
            paid, got, _, _ = run_handler(self.sources[12], ('yes',), roll)
            self.assertEqual(1000, paid)
            awards.update(got)
        self.assertEqual({0: 10, 1: 10, 2: 10, 4: 10, 5: 10, 6: 10,
                          8: 10, 9: 10, 11: 5, 15: 5, 16: 5, 17: 5}, awards)
        self.assertEqual(9, sum(run_handler(self.sources[71], ('a',), r)[1][7]
                                for r in range(100)))

    def test_cheap_mushroom_resale_is_rejected(self):
        self.assertTrue(self.failures(9, '51', '20'))

    def test_bonus_can_make_an_otherwise_safe_price_exploitable(self):
        self.assertTrue(self.failures(71, '118', '70'))

    def test_higher_trade_chain_exit_is_rejected(self):
        worth = dict(self.worth)
        worth[44] = 200
        self.assertTrue(self.failures(worth=worth))

    def test_slot_expectation_is_checked(self):
        self.assertTrue(self.failures(12, '1000', '400'))

    def test_free_rerolls_with_a_full_bag_are_rejected(self):
        source = self.sources[12]
        altered = source.replace('    take(bits=1000)\n', '')
        altered = altered.replace('        narrator.say(t81.vend_get',
                                  '        take(bits=1000)\n        narrator.say(t81.vend_get')
        sources = dict(self.sources)
        sources[12] = altered
        self.assertTrue(check_vending(self.worth, self.names, sources, log=lambda _: None)[0])

    def test_missing_daily_stock_write_is_rejected(self):
        self.assertTrue(self.failures(9, 'engine.vending_happy_sold.set()', 'pass'))

    def test_new_vending_fed_recipe_requires_review(self):
        import tempfile
        from unittest.mock import patch
        import vending_audit
        item_ids()  # Resolve the real enum before installing the miniature story tree.
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            script = root / 'story/base/zones/example/script.py'
            script.parent.mkdir(parents=True)
            script.write_text('def trade():\n    take(Item.Meat)\n    give(Item.Restore)\n')
            with patch.object(vending_audit, 'ROOT', root):
                self.assertTrue(vending_audit.conversion_changes({38}))

    def test_daily_stocks_are_independent_and_survive_a_new_handler(self):
        source = self.sources[9]
        bought = run_handler(source, ('b',), 99)
        self.assertEqual((1500, {69: 1}, {798}), bought[:3])
        self.assertEqual((0, {}, {798}), run_handler(source, ('b',), 99, flags=bought[2])[:3])
        self.assertEqual((1000, {45: 1}, {798, 799}),
                         run_handler(source, ('more', 'a'), 99, flags=bought[2])[:3])
        self.assertEqual((1500, {69: 1}, {798}), run_handler(source, ('b',), 99, flags=())[:3])


if __name__ == '__main__':
    unittest.main()
