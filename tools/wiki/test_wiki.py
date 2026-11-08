"""Release separation, changing facts, translations and search spoiler regressions."""
import copy
import importlib.util
import json
from pathlib import Path
import sys
import unittest

sys.path.insert(0,str(Path(__file__).resolve().parent))
import model


class WikiTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.data=model.load('v0.0.7')

    def test_release_facts_do_not_use_main(self):
        self.assertEqual(self.data['commit'],'5861f8c8fb7ea3ffc54fba0d47d4b7582ba91baf')
        self.assertEqual(self.data['facts']['save_blocks'],2)
        self.assertIsNone(self.data['facts']['hard'])
        self.assertIsNotNone(model.load('origin/main')['facts']['hard'])

    def test_new_single_block_patch_changes_the_fact(self):
        files=dict(self.data['files'])
        files['mods/patches/series']+=b'\nwiki-save-fixture.patch\n'
        files['mods/patches/wiki-save-fixture.patch']=b'+++ b/src/main/main_menu.c\n+#define SAVE_BLOCKS 1\n+status = MemCardCreateFile(MEMORY_CARD_ID, SAVE_FILE_NAME, SAVE_BLOCKS);\n'
        self.assertEqual(model.save_blocks(files),1)
        files['mods/patches/wiki-save-fixture.patch']=b'+status = MemCardCreateFile(MEMORY_CARD_ID, SAVE_FILE_NAME, unreviewed());\n'
        with self.assertRaises((ValueError,KeyError)):model.save_blocks(files)

    def test_full_routes_and_empty_move_slots(self):
        species={s['id']:s for s in self.data['species']}
        self.assertEqual(species[3]['specialties'],['fire','battle'])
        self.assertEqual(species[3]['slots'],['fire',None,'battle'])
        self.assertEqual(len(species[3]['to']),6)
        self.assertTrue(all(3 in species[i]['parents'] for i in species[3]['to']))
        self.assertEqual(next(m['chance'] for m in species[3]['moves'] if m['id']==43),14)
        self.assertEqual(next(m['baseMP'] for m in self.data['techniques'] if m['id']==59),0)

    def test_later_single_block_article_uses_the_new_fact(self):
        spec=importlib.util.spec_from_file_location('wiki_articles',Path(__file__).with_name('build.py'))
        module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
        data=dict(self.data,facts=dict(self.data['facts'],save_blocks=1))
        articles=json.loads((model.ROOT/'web/wiki/articles/en.json').read_text())
        pages=module.Pages(Path('unused'),data,'en',articles)
        rendered={}
        pages.page=lambda path,title,body,*args:rendered.__setitem__(path,body)
        pages.article_pages()
        self.assertIn('1 free block',rendered['guides/memory-cards/'])
        self.assertNotIn('2 free blocks',rendered['guides/memory-cards/'])
        self.assertNotIn('1 free blocks',rendered['guides/memory-cards/'])

    def test_size_gates_reject_oversize_output(self):
        import tempfile
        from unittest.mock import patch
        spec=importlib.util.spec_from_file_location('wiki_budget',Path(__file__).with_name('build.py'))
        module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);(root/'wiki/en').mkdir(parents=True)
            (root/'wiki/en/search-index.json').write_text('[]')
            with patch.object(module,'SITE_LIMIT',1):
                with self.assertRaises(ValueError):module.budget(root)
            with patch.object(module,'INDEX_LIMIT',1):
                with self.assertRaises(ValueError):module.budget(root)
            with patch.object(module,'WIKI_LIMIT',1):
                with self.assertRaises(ValueError):module.budget(root)

    def test_quiz_tables_use_the_tagged_localized_dialogue(self):
        import html
        import re
        spec=importlib.util.spec_from_file_location('wiki_pages',Path(__file__).with_name('build.py'))
        module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
        for lang in model.LANGS:
            articles=json.loads((model.ROOT/f'web/wiki/articles/{lang}.json').read_text())
            pages=module.Pages(Path('unused'),self.data,lang,articles)
            block=pages.fact_block('new-game-quiz')
            self.assertEqual(block.count('<tr>'),68)
            dialogue=json.loads(self.data['files'][f'text/{lang}.json'])
            expected=' '.join(re.sub(r'\{[^}]+\}','',x).strip() for x in dialogue['name.quiz.q1.question'][1:])
            self.assertIn(html.escape(expected),block)

    def test_food_names_follow_the_release_language(self):
        spec=importlib.util.spec_from_file_location('wiki_food',Path(__file__).with_name('build.py'))
        module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
        articles=json.loads((model.ROOT/'web/wiki/articles/es.json').read_text())
        pages=module.Pages(Path('unused'),self.data,'es',articles)
        self.assertEqual(pages.item_names['meat'],'Carne')
        self.assertEqual(pages.item_names['sirloin'],'Solomillo')

    def test_no_pictures_by_default_and_owned_asset_hook(self):
        from unittest.mock import patch
        spec=importlib.util.spec_from_file_location('wiki_art_policy',Path(__file__).with_name('build.py'))
        module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
        self.assertEqual(module.owned_icons(),{})
        articles=json.loads((model.ROOT/'web/wiki/articles/en.json').read_text())
        pages=module.Pages(Path('unused'),self.data,'en',articles)
        species=next(s for s in self.data['species'] if s['id']==3)
        self.assertNotIn('<img',pages.card(species))
        self.assertNotIn('<img',pages.tree(species))
        with patch.object(module,'owned_icons',return_value={'3':'agumon.svg'}):
            enabled=module.Pages(Path('unused'),self.data,'en',articles)
            self.assertIn('/wiki/assets/owned-icons/agumon.svg',enabled.image(species))
        self.assertFalse(any(path.startswith('content/icons/') for path in self.data['files']))

    def test_runtime_translated_moves_items_places_and_missing_name_fallback(self):
        spec=importlib.util.spec_from_file_location('wiki_locale_names',Path(__file__).with_name('build.py'))
        module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
        for lang in model.LANGS:
            articles=json.loads((model.ROOT/f'web/wiki/articles/{lang}.json').read_text())
            pages=module.Pages(Path('unused'),self.data,lang,articles)
            names=model.localized_names(self.data['files'],lang)
            for move in self.data['techniques']:
                self.assertEqual(pages.move_name(move),names.get('main.MOVE_NAMES.'+str(move['id']),move['name']))
            self.assertTrue(all(str(s['partner'].get('favorite_food','')).casefold() in pages.item_names for s in self.data['species']))
            if lang=='es':
                self.assertEqual(pages.move_name(pages.moves[2]),'Escupefuego')
                self.assertEqual(pages.move_name(pages.moves[59]),'Aliento Picante')
                self.assertEqual(pages.item_names['meat'],'Carne')
                self.assertEqual(pages.item_names['digimushrm'],names['main.ITEM_NAMES.44'])
                self.assertEqual(pages.item_names['sm.recovery'],'Cura pequeña')
                self.assertEqual(pages.places[109],'Bosque Indígena')
                rendered={}
                pages.page=lambda path,title,body,*args:rendered.__setitem__(path,body)
                pages.species_pages()
                self.assertIn('>Escupefuego</a>',rendered['digimon/3-agumon/'])
                self.assertIn('>Aliento Picante</a>',rendered['digimon/3-agumon/'])
                self.assertIn('Dónde reclutar',rendered['digimon/3-agumon/'])
        files=dict(self.data['files']);files['text/es/names.json']=b'{}'
        self.assertEqual(model.localized_names(files,'es')['main.MOVE_NAMES.2'],'Spit Fire')
        self.assertEqual(model.localized_names(files,'en')['main.MOVE_NAMES.59'],'Pepper Breath')
        public=next(r for r in self.data['recruits'] if r['id']==3)
        secret=next(r for r in self.data['recruits'] if r['id']==6)
        self.assertFalse(public['hidden']);self.assertTrue(secret['hidden'])

    def test_twenty_articles_and_nine_reviewed_translations(self):
        import hashlib
        root=model.ROOT/'web/wiki/articles'
        review=json.loads((root/'review.json').read_text())
        for lang in model.LANGS:
            source=(root/f'{lang}.json').read_bytes()
            self.assertEqual(review['locales'][lang],hashlib.sha256(source).hexdigest())
            articles=json.loads(source)
            self.assertEqual(len(articles),20)
            self.assertTrue(all(len(a['paragraphs'])>=3 for a in articles.values()))
            self.assertIn('{save_blocks}',articles['memory-cards']['paragraphs'][0])
    def test_bakemon_dialogue_comes_from_each_snapshot_and_language(self):
        main=model.load('origin/main')
        for lang in model.LANGS:
            old=model.bakemon_dialogue(self.data['files'],lang)
            new=model.bakemon_dialogue(main['files'],lang)
            self.assertFalse(old['readable'])
            self.assertTrue(new['readable'])
            self.assertEqual([r['answer_key'] for r in new['rows']],['s035.sec5.m0.o0','s035.sec5.m1.o0','s035.sec5.m2.o1'])
            self.assertEqual(new['rows'][0]['question_key'],'s035.sec5.u8')
            self.assertNotEqual(old['rows'][0]['question'],new['rows'][0]['question'])
        files=dict(main['files']);script='story/base/zones/overdell-cemetery/s035-35/script.dws'
        files[script]=files[script].replace(b's035.sec5.u8',b's035.sec5.tmp').replace(b's035.sec5.u9',b's035.sec5.u8').replace(b's035.sec5.tmp',b's035.sec5.u9')
        self.assertEqual(model.bakemon_dialogue(files,'en')['rows'][0]['question_key'],'s035.sec5.u9')
        files=dict(main['files']);files['text/es/dialogue/overdell-cemetery.json']=b'{}'
        with self.assertRaises(ValueError):model.bakemon_dialogue(files,'es')


if __name__=='__main__':unittest.main()
