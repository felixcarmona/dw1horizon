"""Guard the translated labels and money cap against the box's native crop."""
import json
from pathlib import Path
import unittest

ROOT=Path(__file__).resolve().parents[1]


def strings(value):
    if isinstance(value,str):yield value
    elif isinstance(value,list):
        for item in value:yield from strings(item)
    elif isinstance(value,dict):
        for item in value.values():yield from strings(item)


class ShopBalanceLayout(unittest.TestCase):
    def test_currency_words_fit_even_with_twelve_pixel_glyphs(self):
        for language in ('ours','es','pt-br','fr','de','it','ja','ca','zh-hans'):
            data=json.loads((ROOT/'text'/language/'dialogue/maphead.json').read_text())
            rows=[s for s in strings(data) if '{money}' in s or '{merit}' in s]
            self.assertEqual(len(rows),4,language)
            for row in rows:
                with self.subTest(language=language,row=row):
                    label,value=row.split()
                    self.assertIn(value,('{money}','{merit}'))
                    self.assertLessEqual(len(label)*12,72)
        economy=json.loads((ROOT/'content/tables/economy.json').read_text())['economy']
        self.assertLessEqual(len(str(economy['money']['cap']))*12,72)
        self.assertLessEqual(len(str(economy['merit']['cap']))*12,72)


if __name__=='__main__':unittest.main()
