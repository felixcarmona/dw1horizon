"""Budget boundary, fixed-deck and information-policy regressions."""
import unittest
from itertools import product
import numpy as np
from tools import monochromon_shop as shop


class BudgetShopTests(unittest.TestCase):
    def test_every_offer_pair_and_budget(self):
        for a, b, x in product(shop.PRICES, shop.PRICES, range(-2, 6)):
            if a <= x:
                expected = a
            elif a in (x+1, x+2) and b < x:
                expected = b
            else:
                expected = None
            self.assertEqual(shop.outcome(a, b, x), expected, (a,b,x))
        self.assertIsNone(shop.outcome(2, 0, 0))  # annoyance prevents the old safe retry
        self.assertEqual(shop.outcome(2, -1, 0), -1)
        self.assertIsNone(shop.outcome(3, -3, 0))

    def test_original_profit_ladder(self):
        for item, multiplier in enumerate((1, 6, 20)):
            self.assertEqual([shop.profit(p, item) for p in shop.PRICES],
                             [multiplier*p for p in (0,5,10,15,20,25,30,35,40)])

    def test_hint_posterior_is_not_a_budget_lookup(self):
        for s in range(4):
            cs = shop.cells(s, True)
            self.assertAlmostEqual(sum(c[1] for c in cs), 1)
            for _, _, _, weights in cs:
                self.assertGreaterEqual(np.count_nonzero(weights), 2)
            probs = [shop.face_probability(s, i) for i in range(shop.RANGES[s][1]-shop.RANGES[s][0]+1)]
            self.assertEqual(probs, sorted(probs))

    def test_deck_and_thresholds(self):
        self.assertEqual(sum(shop.DECK), 20)
        self.assertEqual(shop.HALFWAY*2, shop.GOAL)
        self.assertEqual(shop.GOAL%256, 0)
        self.assertEqual(shop.MIDDLE%256, 0)
        # Even twenty maximum list-price sales cannot reach the goal.
        self.assertLess(sum(n*shop.profit(0,i) for i,n in enumerate(shop.DECK)), shop.GOAL)

    def test_small_deck_bellman_against_exhaustive_oracle(self):
        # One customer: maximize success separately for each observed species.
        goal = 150
        expected = 0
        for s, (lo, hi) in enumerate(shop.RANGES):
            best = max(sum(shop.profit(shop.outcome(a,b,x),1)>=goal for x in range(lo,hi+1))/(hi-lo+1)
                       for a,b in product(shop.PRICES,repeat=2))
            expected += shop.WEIGHTS[s]*best
        opt = shop.optimal(False,goal,(0,1,0))
        self.assertAlmostEqual(opt.chance,expected)
        self.assertGreaterEqual(shop.optimal(True,goal,(0,1,0)).chance,opt.chance)

    def test_fixed_table_convolution(self):
        table = ((4,2),(2,-1),(1,-1),(3,0))
        self.assertAlmostEqual(shop.fixed_probability(table), .4967265250407451)
        result = shop.simulate(4000,49,table=table)
        self.assertLess(abs(result['recruit_percent']-49.67),3)
        self.assertGreater(result['profit_share_percent'][0],5)


if __name__ == '__main__':
    unittest.main()
