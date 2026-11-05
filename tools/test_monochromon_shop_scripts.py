"""Execute the authored literal shop blocks with the original byte-pstat rules."""
import ast
from collections import Counter
from pathlib import Path
import re
import unittest
from tools import monochromon_shop as model

ROOT = Path(__file__).resolve().parents[1]
SHOP = ROOT / 'story/base/zones/monochrome-shop/s049-49/script.py'


def blocks(path, name):
    fn = next(n for n in ast.parse(path.read_text()).body if isinstance(n, ast.FunctionDef) and n.name == name)
    return [ast.literal_eval(n.args[0]) for n in ast.walk(fn) if isinstance(n, ast.Call)
            and isinstance(n.func, ast.Name) and n.func.id == 'dws']


class LiteralVM:
    """Small test interpreter for ordinary IF, jump, pstat and menu instructions.

    UI/movement calls are observed or skipped. Arithmetic wraps to a byte, as on
    the original engine. The oracle never calls the model's outcome function.
    """
    def __init__(self, source, values=(), rolls=(), offers=()):
        self.p = Counter(dict(values)); self.rolls = iter(rolls); self.offers = iter(offers)
        self.lines = [x.strip() for x in source.splitlines() if x.strip()]
        self.labels = {x[:-1]: i for i,x in enumerate(self.lines) if x.endswith(':')}
        self.profit = 0; self.text = []; self.faces = []; self.menus = 0

    def run(self):
        pc = 0
        for _ in range(10000):
            if pc >= len(self.lines): return self
            line = self.lines[pc]; pc += 1
            if line.endswith(':'): continue
            m = re.fullmatch(r'unless \(p(\d+) (==|<=|>=) (\d+)\) goto (\w+);',line)
            if m:
                p,op,n,label = m.groups(); a,b = self.p[int(p)],int(n)
                if not {'==':a==b,'<=':a<=b,'>=':a>=b}[op]: pc=self.labels[label]
                continue
            m = re.fullmatch(r'goto (\w+);',line)
            if m: pc=self.labels[m[1]]; continue
            m = re.fullmatch(r'p(\d+) (=|\+=|-=) (p\d+|\d+);',line)
            if m:
                p,op,value=m.groups(); p=int(p)
                value=self.p[int(value[1:])] if value.startswith('p') else int(value)
                self.p[p]={'=':value,'+=':self.p[p]+value,'-=':self.p[p]-value}[op]%256
                continue
            m = re.fullmatch(r'store_random\(p(\d+), (\d+)\);',line)
            if m:
                value=next(self.rolls); assert 0<=value<=int(m[2]); self.p[int(m[1])]=value; continue
            if line.startswith('set_selection('):
                labels=line[14:line.index('text(')].rstrip(', ').split(', ')
                self.menus+=1
                offer=next(self.offers)
                if offer is not None: pc=self.labels[labels[offer+3]]
                continue
            m=re.fullmatch(r'show_textbox\(text\("([^"]+)"\)\);',line)
            if m: self.text.append(m[1]); continue
            if line=='call_routine(routine("shopvar_add"));':
                self.profit+=self.p[243]*256+self.p[244]; continue
            if line=='call_routine(routine("monochromon_mood_bubble"));':
                self.faces.append(self.p[248]); continue
            if line.startswith(('jump_to_file(', 'end_section(')): return self
            if line.startswith(('load_digimon(', 'set_digimon(', 'delay(', 'entity_walk_to(',
                                'wait_for_entity(', 'entity_look_at_entity(', 'set_dialog_owner(',
                                'set_textbox_size(', 'end_selection(', 'play_sound(',
                                'unload_entity(', 'unload_digimon(')): continue
            raise AssertionError('unhandled instruction: '+line)
        raise AssertionError('script failed to terminate')


class ShopScripts(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.customers=[blocks(ROOT/f'story/base/zones/libraries/s{s}/script.py','step0')[0] for s in range(199,203)]
        cls.dispatch=blocks(SHOP,'use2')[0]

    def test_all_budgets_items_and_offer_pairs_match_model(self):
        for s,source in enumerate(self.customers):
            lo,hi=model.RANGES[s]
            for x in range(lo,hi+1):
                for item in range(3):
                    for a in model.PRICES:
                        for b in model.PRICES:
                            # All optional face random rolls can be zero for this
                            # outcome proof; another test checks their likelihood.
                            vm=LiteralVM(source,[(116,item)], [x-lo,0], [a,b]).run()
                            expected=model.profit(model.outcome(a,b,x),item)
                            self.assertEqual(vm.profit,expected,(s,x,item,a,b))
                            self.assertEqual(vm.p[123],1)
                            self.assertEqual(vm.p[119],0)
                            self.assertEqual(vm.faces[-1],5)
                            sold=model.outcome(a,b,x) is not None
                            self.assertEqual('s199.sec51.u12' in vm.text,sold)
                            self.assertEqual('s199.sec51.u22' in vm.text,not sold)

    def test_face_probabilities_match_simulator(self):
        for s,source in enumerate(self.customers):
            lo,hi=model.RANGES[s]
            for index in range(hi-lo+1):
                # Species 0 uses a coin; species 1 uses four equiprobable values.
                draws=range(2) if s==0 else range(4) if s==1 else range(1)
                faces=[LiteralVM(source,[(116,0)], [index,r],[-3]).run().faces[0] for r in draws]
                self.assertAlmostEqual(faces.count(0)/len(faces),model.face_probability(s,index))

    def test_uniform_remaining_deck_and_rejected_random_indices(self):
        for a in range(9):
            for b in range(10):
                for c in range(4):
                    left=a+b+c
                    if not left: continue
                    outcomes=Counter()
                    served=20-left
                    for draw in range(served,20):
                        vm=LiteralVM(self.dispatch,[(113,a),(114,b),(115,c),(123,served)],
                                     [draw] if served==0 else [0,draw]).run()
                        outcomes[vm.p[116]]+=1
                        self.assertEqual(sum(vm.p[p] for p in (113,114,115)),left-1)
                        self.assertEqual(vm.p[123],served)
                    self.assertEqual([outcomes[i] for i in range(3)],[a,b,c])

    def test_cancel_reopens_without_drawing_budget_again(self):
        vm=LiteralVM(self.customers[0],[(116,0)],[1,0],[None,None,0]).run()
        self.assertEqual(vm.menus,3)
        self.assertEqual(vm.p[118],7)
        self.assertEqual(vm.profit,15)

    def test_recruit_guards_and_original_payout_tiers(self):
        # These entry guards protect both the counter and direct section jumps.
        tree=ast.parse(SHOP.read_text())
        for name in ('use1','use2'):
            fn=next(n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name==name)
            self.assertEqual(ast.unparse(fn.body[0].test),'recruited(Species.Monochromon)')
            self.assertIsInstance(fn.body[0].body[0],ast.Return)
        source=SHOP.read_text()
        self.assertIn('if engine.shop_hi <= 6:',source)
        self.assertIn('if engine.shop_hi <= 9:',source)
        self.assertEqual(re.findall(r'give\(bits=(\d+)\)',source),['500','1500','2000'])
        self.assertEqual(source.count('raw.add_minutes_to_date_at(date_year, 480)'),3)
        plate=(ROOT/'mods/patches/Lower-Monochromon-recruit-profit-target-to-2560-bits.patch').read_text()
        self.assertIn('#define MOD_SHOP_MIDDLE 1792',plate)
        self.assertIn('+#define MOD_SHOP_RECRUIT 2560',plate)


if __name__=='__main__': unittest.main()
