"""Capped gains must not become unrestricted conversion edges."""
import copy
import json
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parent))
import economy_audit as E
from vending_audit import check_vending


class MojyamonEconomy(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.items = {d['id']: d for p in (E.ROOT / 'content/items').glob('*.json')
                     for d in [json.loads(p.read_text())]}
        cls.shops = json.loads((E.T / 'shops.json').read_text())
        cls.econ = json.loads((E.T / 'economy.json').read_text())['economy']

    def audit(self, **kw):
        return E.audit_mojyamon(kw.pop('shops', self.shops), self.items, 50, **kw)

    def test_reviewed_caps_and_separate_ceilings(self):
        result = self.audit()
        self.assertEqual([], result['fails'])
        self.assertEqual((6050, 2500), (result['daily_gross'], result['once_gross']))
        self.assertEqual(['daily'] * 8 + ['save'], [r['limit'] for r in result['rows']])
        self.assertEqual(50, result['worth'][44])
        self.assertEqual(50, result['worth'][0])

    def test_caps_cannot_be_removed_or_changed_to_daily_for_north_star(self):
        for row in E.MOJYAMON_GAIN_EXCEPTIONS:
            caps = dict(E.MOJYAMON_CAPS); caps.pop(row)
            self.assertTrue(self.audit(caps=caps)['fails'], row)
        caps = dict(E.MOJYAMON_CAPS); caps[8] = (0, 92, 'daily')
        self.assertTrue(self.audit(caps=caps)['fails'])

    def test_unreviewed_trade_and_uncapped_loop_are_rejected(self):
        shops = copy.deepcopy(self.shops)
        shops['mojyamonGives'][9], shops['mojyamonTakes'][9] = 0, 7
        self.assertTrue(self.audit(shops=shops)['fails'])
        shops['mojyamonGives'][0], shops['mojyamonTakes'][0] = 44, 92
        self.assertTrue(self.audit(shops=shops)['fails'])

    def test_daily_profit_does_not_inflate_vending_ev_but_uncapped_profit_does(self):
        names = {i: it['name'] for i, it in self.items.items()}
        result = self.audit()
        self.assertEqual([], check_vending(result['worth'], names, log=lambda _: None)[0])
        caps = dict(E.MOJYAMON_CAPS); caps.pop(6)
        unsafe = self.audit(caps=caps)
        self.assertEqual(150, unsafe['worth'][44])
        self.assertTrue(check_vending(unsafe['worth'], names, log=lambda _: None)[0])

    def test_cheapest_offers_and_travel_cost(self):
        prices = E.mojyamon_input_prices(self.items, self.econ)
        self.assertEqual((100, 90), prices[63])  # Cold Store, including baby discount.
        self.assertNotIn(67, prices)  # No Digiseabass shop: do not invent an 8000-bit offer.
        self.assertEqual((500, 450), prices[41])
        self.assertEqual((500, 450), prices[42])
        self.assertEqual((1000, 900), prices[48])
        self.assertEqual((51, 51), prices[44])
        self.assertEqual((300, 300), prices[39])
        sell = lambda i: self.items[i]['value'] // 2
        rows = self.audit()['rows']
        for baby, cost, net, after_travel in ((False, 3951, 2099, 599), (True, 3741, 2309, 809)):
            result = E.purchase_ceiling(rows, prices, sell, baby)
            self.assertEqual((cost, net, [67]), (result['cost'], result['net'], result['unsold']))
            self.assertEqual(after_travel, result['net'] - 1500)


if __name__ == '__main__':
    unittest.main()
