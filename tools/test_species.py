#!/usr/bin/env python3
"""Tests of tools/species.py lint (docs/mods/species.md): bad species files must be refused with the file, the
field, the value and why. Each case copies a good file of content/species into a scratch folder, breaks one thing
and runs lint on the folder (the 180 originals are there too, for the references).

  tools/test_species.py           (selftest: species-lint-tests)
"""
import collections, glob, json, os, shutil, sys, tempfile
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, 'tools'))
import species as S

SRC = os.environ.get('SPECIES_TEST_CONTENT', os.path.join(ROOT, 'content', 'species'))


def load(name):
    return json.load(open(glob.glob(os.path.join(SRC, name))[0]), object_pairs_hook=collections.OrderedDict)


def case(title, name, edit, expect, extra=None):
    """edit(d) breaks the file `name`; expect: a text every error line about it must contain one of."""
    os.makedirs(os.path.join(ROOT, 'build'), exist_ok=True)
    d = tempfile.mkdtemp(prefix='species-lint-', dir=os.path.join(ROOT, 'build'))
    try:
        for f in glob.glob(os.path.join(SRC, '*.json')):
            if int(os.path.basename(f).split('-')[0]) < S.NUM_ORIGINAL: shutil.copy(f, d)
        s = load(name); edit(s)
        out = os.path.join(d, os.path.basename(glob.glob(os.path.join(SRC, name))[0]))
        if not out.endswith(f'/{s["id"]}-' + os.path.basename(out).split('-', 1)[1]):
            out = os.path.join(d, f'{s["id"]}-x.json')
        for p in glob.glob(os.path.join(d, f'{s["id"]}-*.json')): os.remove(p)
        open(out, 'w').write(json.dumps(s, indent=1))
        for n, e in (extra or []):
            e2 = load(n); e(e2); open(os.path.join(d, f'{e2["id"]}-extra.json'), 'w').write(json.dumps(e2, indent=1))
        _, errs, _ = S.lint_content(d)
        hit = [e for e in errs if expect in e]
        ok = bool(hit)
        print(f'  {"ok  " if ok else "FAIL"} {title}: ' + (hit[0] if hit else f'no error with "{expect}" ({errs[:3]})'))
        return ok
    finally:
        shutil.rmtree(d)


def setp(path, value):
    def f(s):
        o = s
        for k in path[:-1]: o = o[k]
        o[path[-1]] = value
    return f


def model_case(title, name, mmd_edit, expect, kind='error', edit=None):
    """A good original partner whose model file is broken by mmd_edit(MMD) and linted with --files: expect is in an error
    (kind 'error') or a warning (kind 'warning')."""
    import mmd
    d = tempfile.mkdtemp(prefix='species-lint-', dir=os.path.join(ROOT, 'build'))
    try:
        for f in glob.glob(os.path.join(SRC, '*.json')):
            if int(os.path.basename(f).split('-')[0]) < S.NUM_ORIGINAL: shutil.copy(f, d)
        s = load(name)
        m = mmd.MMD.parse(open(S.originals().model_path(s['id']), 'rb').read(), s['model']['bones'])
        mmd_edit(m)
        mf = os.path.join(d, 'model.MMD'); open(mf, 'wb').write(m.build())
        s['model']['file'] = mf
        if edit: edit(s)
        out = glob.glob(os.path.join(d, f'{s["id"]}-*.json'))[0]
        open(out, 'w').write(json.dumps(s, indent=1))
        _, errs, warns = S.lint_content(d, True)
        hit = [e for e in (errs if kind == 'error' else warns) if expect in e and os.path.basename(out) in e]
        print(f'  {"ok  " if hit else "FAIL"} {title}: ' + (hit[0] if hit else f'no {kind} with "{expect}" ({(errs if kind == "error" else warns)[:3]})'))
        return bool(hit)
    finally:
        shutil.rmtree(d)


def drop_slot(*slots):
    def f(m):
        for x in slots: m.anims.table[x] = None
    return f


def cut_table(n):
    def f(m): del m.anims.table[n:]
    return f


CASES = [
    ('a partner with attribute none', '180-veemon.json', setp(['attribute'], 'none'), 'FLEE_CHANCES'),
    ('an unknown attribute', '180-veemon.json', setp(['attribute'], 'vacine'), 'attribute "vacine" is not one of'),
    ('a level out of range', '180-veemon.json', setp(['level'], 9), 'level = 9'),
    ('an element that does not exist', '180-veemon.json', setp(['specialties'], ['fire', 'wood', None]), 'specialties "wood"'),
    ('a technique name that does not exist', '180-veemon.json', setp(['techniques'], ['Fire Towr']), 'no technique "Fire Towr" (did you mean "Fire Tower"?)'),
    ('a shared technique name without its id', '180-veemon.json', setp(['techniques'], ['Bubble']), 'write "Bubble (113)"'),
    ('a technique id that does not exist', '180-veemon.json', setp(['techniques'], [200]), 'technique 200 does not exist'),
    ('a Fresh partner with a grown-up technique', '1-botamon.json', setp(['techniques'], ['Spit Fire']), 'bubble'),
    ('a drop item that does not exist', '180-veemon.json', setp(['drop'], {'item': 'Mega Meat', 'percent': 10}), 'no item "Mega Meat"'),
    ('a drop chance over 100 %', '180-veemon.json', setp(['drop'], {'item': 'Meat', 'percent': 150}), 'drop.percent = 150'),
    ('a favourite food that is not food', '180-veemon.json', setp(['partner', 'favorite_food'], 'Grey Claws'), 'partner.favorite_food = "Grey Claws"'),
    ('a sleep cycle that does not exist', '180-veemon.json', setp(['partner', 'sleep_cycle'], '25:00-01:00'), 'partner.sleep_cycle "25:00-01:00"'),
    ('a training type that does not exist', '180-veemon.json', setp(['partner', 'training_type'], 9), 'partner.training_type = 9'),
    ('a region that does not exist', '180-veemon.json', setp(['partner', 'favored_region'], 12), 'partner.favored_region = 12'),
    ('hunger hours out of order', '180-veemon.json', setp(['partner', 'hunger_hours'], [8, 4]), 'in increasing order'),
    ('an hour past 23', '180-veemon.json', setp(['partner', 'hunger_hours'], [4, 25]), 'hours of the day'),
    ('energy fed above the maximum', '180-veemon.json', setp(['partner', 'energy_fed'], 90), 'partner.energy_fed = 90'),
    ('a birth weight of 0', '180-veemon.json', setp(['partner', 'birth_weight'], 0), 'partner.birth_weight = 0'),
    ('a training animation that is not a technique slot', '180-veemon.json', setp(['partner', 'training'], {'animation': 70, 'hit_tick': 10}), 'partner.training.animation = 70'),
    ('a name longer than 19 characters', '180-veemon.json', setp(['name'], 'VeemonWithAVeryLongName'), 'at most 19 characters'),
    ('an unknown key', '180-veemon.json', setp(['favourite_food'], 'Meat'), 'unknown key favourite_food'),
    ('an unknown partner key', '180-veemon.json', setp(['partner', 'favourite_food'], 'Meat'), 'unknown key favourite_food'),
    ('a missing required key', '180-veemon.json', lambda s: s.pop('voice'), 'missing voice'),
    ('effects like a species without effect rows', '180-veemon.json', setp(['effects_like'], 200), 'effects_like = 200'),
    ('effects like a species that borrows itself', '180-veemon.json', setp(['effects_like'], 124), 'borrows its effects itself'),
    ('evolving from a species that does not exist', '180-veemon.json', setp(['evolution', 'from'], [999]), 'evolution.from = 999: no such species'),
    ('a voice chunk that does not exist', '180-veemon.json', setp(['voice'], 90), 'voice = 90'),
    ('battle music that does not exist', '180-veemon.json', setp(['battle_music'], 'boss-battle'), 'battle_music "boss-battle"'),
    ('an effect origin on a bone it does not have', '180-veemon.json', setp(['effect_origins'], [[3, 0, 0, 0, 40, 0, 0, 0]]), 'bone 40'),
    ('a skeleton bone whose parent does not exist', '180-veemon.json', lambda s: s['model']['skeleton'].__setitem__(5, [4, 99]), 'its parent must be another bone'),
    ('reincarnation stats on a Rookie', '180-veemon.json', setp(['reincarnation_stats'], {'hp': 1, 'mp': 1, 'offense': 1, 'defense': 1, 'speed': 1, 'brains': 1}), 'only a Fresh species'),
    ('two imports with one name', '181-puppetmon.json', setp(['name'], 'Veemon'), 'also the name of',
     [('180-veemon.json', lambda s: None)]),
    ('two files with one id', '181-puppetmon.json', lambda s: None, 'also the id of',
     [('181-puppetmon.json', lambda s: None)]),
    ('an effect origin fallback on a species of the executable\'s tables', '3-agumon.json',
     setp(['effect_origin_fallback'], [0, 0, 50, 0]), 'only a species carried by its DIGI.DAT record'),
    ('an effect fallback bone the skeleton does not have', '180-veemon.json', setp(['effect_origin_fallback'], [40, 0, 0, 0]),
     'effect_origin_fallback'),
]


# (title, file, edit of the model, text, extra) -- with --files, on Agumon's model (slots: docs/mods/species.md)
MODEL_CASES = [
    ('no toilet animation (slot 10)', '3-agumon.json', drop_slot(10), 'model.animation[0x0a]', {}),
    ('no eating animation (slot 8)', '3-agumon.json', drop_slot(8), 'model.animation[0x08]', {}),
    ('no faint animation (0x2B)', '3-agumon.json', drop_slot(0x2B), 'model.animation[0x2b]', {}),
    ('no victory pose (0x2A)', '3-agumon.json', drop_slot(0x2A), 'model.animation[0x2a]', {}),
    ('a table that ends before the battle slots', '3-agumon.json', cut_table(0x22), 'startAnimation would read past its table', {}),
    ('a technique whose slot is empty', '3-agumon.json', drop_slot(0x2E), 'technique 0', {}),
    ('no slow walk (3): a warning', '3-agumon.json', drop_slot(3), 'model.animation[0x03]', dict(kind='warning')),
    ('a slot only scripts start (5): a warning', '3-agumon.json', drop_slot(5), 'model.animation[0x05]', dict(kind='warning')),
    ('a gym clip that ends before the hit: a warning', '3-agumon.json', lambda m: None, 'the hit lands after it ended',
     dict(kind='warning', edit=setp(['partner', 'training'], {'animation': 51, 'hit_tick': 60}))),
    ('an empty gym slot: a warning', '3-agumon.json', drop_slot(51), 'the gym plays none', dict(kind='warning')),
    ('an aura row past the table', '3-agumon.json', lambda m: None, 'effects_like = 140', dict(edit=setp(['effects_like'], 140))),
    ('a technique that would never hit (no origin row, not a record species)', '3-agumon.json', lambda m: None,
     'the technique never hits', dict(edit=lambda s: s['techniques'].__setitem__(6, 'Hand of Fate'))),
]


def main():
    print('species lint: bad files are refused')
    good_errs = S.lint_content()[1]
    ok = not good_errs
    print(f'  {"ok  " if ok else "FAIL"} content/species itself: {len(good_errs)} errors' + (f' ({good_errs[:2]})' if good_errs else ''))
    results = [ok] + [case(*c) for c in CASES]
    if os.path.exists(os.path.join(ROOT, 'extracted', 'SLUS_010.32')):
        results += [model_case(*c[:4], **c[4]) for c in MODEL_CASES]
    else:
        print(f'  skip {len(MODEL_CASES)} model cases (they read the models of extracted/)')
    print(f'{sum(results)} of {len(results)} passed')
    sys.exit(0 if all(results) else 1)


if __name__ == '__main__':
    main()
