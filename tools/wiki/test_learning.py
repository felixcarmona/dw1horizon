"""Encounter facts must follow the tagged maps, story and battle selection rules."""
import importlib.util
import json
from pathlib import Path
import sys
import unittest

sys.path.insert(0,str(Path(__file__).resolve().parent))
import learning
import model
from check import Spoilers


class LearningTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.data = model.load('v0.0.7')

    def test_native_attack_animation_and_spawn_hours(self):
        files = self.data['files']
        row = model.read_json(files,'content/maps/MAYO01.json')['digimon'][5]
        self.assertEqual(row['species'],'Dokunemon')
        self.assertEqual(row['moves'],[46,47,255,255])
        enemy = self.data['enemies'][74]
        self.assertEqual(enemy['techniques'][:2],['Poison Claw','Danger Sting'])
        for name in enemy['techniques'][:2]:
            ident = learning.resolve(name,self.data['techniques'])['id']
            source = next(r for r in self.data['learning_sources'][ident] if r['species']==74 and r['screen']==0)
            self.assertEqual(source['hours'],list(range(7))+list(range(19,24)))
            self.assertFalse(source['spoiler'])
        # Flarerizamon's Fire Tower is slot 47, not its whole species moveset.
        source = next(r for r in self.data['learning_sources'][0] if r['species']==69 and r['screen']==22)
        self.assertEqual(source['hours'],list(range(7,19)))
        self.assertFalse(source['spoiler'])

    def test_story_resident_and_lobby_spar_are_field_sources(self):
        rows = self.data['learning_sources'][2]
        candle = next(r for r in rows if r['species']==235 and r['screen']==125)
        self.assertEqual(candle['kind'],'scripted')
        self.assertTrue(candle['spoiler'])
        self.assertTrue(candle['conditional'])
        self.assertEqual(candle['guards'],['not recruited(Species.Candlemon)'])
        kotemon = [r for rows in self.data['learning_sources'].values() for r in rows if r['species']==351 and r['screen']==208]
        self.assertTrue(kotemon)
        self.assertTrue(all(r['hours']==list(range(20)) and r['spoiler'] for r in kotemon))
        # A noncombat citizen with the same kind of NPC declaration is absent.
        self.assertFalse(any(r['species']==66 and r['screen']==208 for rows in self.data['learning_sources'].values() for r in rows))

    def test_dynamic_boss_and_owned_moveset(self):
        self.assertTrue(any(r['species']==112 and r['screen']==143 and r['spoiler'] for r in self.data['learning_sources'][16]))
        # Sorcermon uses the owned default rather than its first three species moves.
        rows = [ident for ident,rows in self.data['learning_sources'].items() if any(r['species']==242 and r['screen']==323 for r in rows)]
        self.assertEqual(rows,[13,16,17])
        for ident in rows:
            row = next(r for r in self.data['learning_sources'][ident] if r['species']==242 and r['screen']==323)
            self.assertEqual(row['hours'],list(range(5,20)))
            self.assertTrue(row['spoiler'])  # undiscovered story area

    def test_selector_exclusions_and_zero_weight_exceptions(self):
        moves = self.data['techniques']
        enemy = dict(techniques=['Fire Tower','Muscle Charge','Counter','Pepper Breath'],wild=dict(mp=3000,brain=100,speed=100))
        placed = dict(moves=[46,47,48,49],prios=[0,0,0,100])
        self.assertEqual(learning.usable_moves(enemy,placed,moves),[(41,''),(45,'counter')])
        area = dict(enemy,techniques=['Red Inferno'])
        row = dict(moves=[46],prios=[0],unk1=0)
        self.assertEqual(learning.usable_moves(area,row,moves),[])
        self.assertEqual(learning.usable_moves(area,row,moves,True),[(3,'group')])
        self.assertEqual(learning.usable_moves(area,dict(row,unk1=1),moves,True),[])
        self.assertEqual(learning.usable_moves(area,dict(row,prios=[100],currentMP=0),moves,True),[])
        self.assertFalse(any(rows for ident,rows in self.data['learning_sources'].items() if ident>=58))

    def test_spawn_branch_rejoins_and_early_returns(self):
        import ast
        tree = ast.parse("if quest_flag:\n    unrelated()\nspawn()\nif clock.hour >= 7:\n    return\nspawn()")
        calls = []
        learning.spawn_paths(tree.body,lambda call,hours,conditional,guards: calls.append((learning.call_name(call.func),hours,conditional,guards)))
        spawns = [r for r in calls if r[0]=='spawn']
        self.assertEqual(spawns[0][1],frozenset(range(24)))
        self.assertFalse(spawns[0][2])
        self.assertEqual(spawns[1][1],frozenset(range(7)))
        self.assertFalse(spawns[1][2])

    def test_tagged_brains_order_weights_and_absent_alias(self):
        brain = self.data['brain_learning'][0]
        self.assertEqual(brain['positions'],[dict(element='fire',position=3,weights=[22,11,7])])
        self.assertEqual(brain['marks'],[150,250,350,450,550,650,750,800,850,900,950,999])
        self.assertEqual(brain['orders'],[100,200,300,400,500])
        self.assertEqual(self.data['brain_learning'][57]['via'],55)
        self.assertTrue(all(r['via']==57 for r in self.data['learning_sources'][55]))
        self.assertTrue(self.data['brain_learning'][55]['positions'])

    def test_map_mutation_changes_sources_without_main_data(self):
        files = dict(self.data['files'])
        data = model.read_json(files,'content/maps/MAYO01.json')
        for row in data['digimon']:
            if row['species']=='Dokunemon':row['moves']=[255]*4
        files['content/maps/MAYO01.json']=json.dumps(data).encode()
        result = learning.sources(files,list(self.data['enemies'].values()),self.data['techniques'],self.data['species'])
        poison = learning.resolve('Poison Claw',self.data['techniques'])['id']
        self.assertFalse(any(r['species']==74 and r['screen']==0 for r in result[poison]))
        self.assertTrue(any(r['species']==74 and r['screen']==0 for r in self.data['learning_sources'][poison]))
        files['tools/dws/backend.py']=b'unreviewed compiler'
        with self.assertRaisesRegex(ValueError,'placement defaults'):
            learning.sources(files,list(self.data['enemies'].values()),self.data['techniques'],self.data['species'])

    def test_render_all_locales_and_keep_sources_out_of_search(self):
        spec=importlib.util.spec_from_file_location('wiki_learning_pages',Path(__file__).with_name('build.py'))
        module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
        for lang in model.LANGS:
            articles=json.loads((model.ROOT/f'web/wiki/articles/{lang}.json').read_text())
            pages=module.Pages(Path('unused'),self.data,lang,articles)
            rendered={}
            pages.page=lambda path,title,body,*args:rendered.__setitem__(path,(body,args))
            pages.technique_pages()
            body,args=rendered['techniques/2-spit-fire/']
            parser=Spoilers();parser.feed(body)
            self.assertIn(pages.places[125],parser.hidden)
            self.assertNotIn(pages.places[125],parser.visible)
            self.assertIn(pages.places[22],parser.visible)
            self.assertNotIn(pages.places[125],json.dumps(args,ensure_ascii=False))
            self.assertFalse(parser.open_spoilers)
            self.assertIn(pages.strings['wiki.canLearn'],body)
            self.assertIn('id="learn"',body)
            self.assertIn(pages.strings['wiki.arenaNoLearning'],body)
            self.assertIn('55-horizontal-kick/',rendered['techniques/57-horizontal-kick/'][0])
            if lang=='es':
                self.assertIn('Dónde aprenderla',body)
                self.assertIn('Monte Panorama',body)


if __name__=='__main__':
    unittest.main()
