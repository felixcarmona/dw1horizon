"""Every file the build puts on the disc beside the executable, and what the executable must be built with
(build-full.sh 4b, :392-523; tools/newfiles.py plan): which disc files are replaced (--file) or new (--add), the
Spanish copies' names (LANG_FILES), the overlays' Spanish copies (LANG_OVL), the new names FILE_OFFSET_TABLE lacks
(NEW_FILES) and the partner model buffer (PARTNER_MMD_MAX, the species step's).

The list is made in the bash's order (it decides the disc's layout: build-disc.py adds the new files in that order):
  DIGI.DAT; SCRN.DAT, SCRNORIG.DAT, DGORIG.SCN, MHORIG.SCN; EXTENDED STORY's _G.SCN, _APHEAD.SCN, _GORIG.SCN,
  _HORIG.SCN and its map copies (storycopies); with LANGS=en,es the Spanish copies LE000.. (the script text that differs
  from ours, then the translated textures, then the map signs, each with an English-sign copy when it has one) and the
  original story's copies of them (_E000..); the overlays' Spanish copies and LANGEN.BIN/LANGES.BIN (placeholders: their
  bytes come with the executable); the models of the disc's species; the title images; EXTRA_FILES; the new screens'
  map files. Then the disc's other derived files in build-disc's order: the sound banks, MAPHEAD.SCN, DG.SCN, the
  story's maps, the balance maps.

rule: the order of the map signs (a Spanish copy each, LEnnn by that order) is Python's sorted() of their disc paths
(the bash's `sort -u` followed the locale: en_US put MAP/MAP10 before MAP/MAP1; the numbering is
the same on every machine; the copies were renumbered once).

Writes lang/ (the copies), newfiles.txt (newfiles.py plan's lines, as the bash did), derived/disc.txt (every
--file/--add for build-disc.py, in order: the bash passes it whole), derived/plan.env (PARTNER_MMD_MAX, NEW_FILES,
LANG_FILES, LANG_OVL for make) and derived/plan.json (the manifest's "plan": the same and `authored`, the disc files
whose bytes we write: the executable, the overlays, their Spanish copies, LANGEN/LANGES.BIN; build-disc.py --derived
and dwpatch read it). Its outputs are its copies and the files of the list that no other step names with a disc path
(EXTRA_FILES, the new screens' maps, the imported models' files): the manifest then has every derived file of the
disc, and a file another step names must be the same bytes here (else the build stops).
"""
import filecmp
import hashlib
import json
import os
import shutil

from . import balance as BAL
from . import storycopies as SC
from . import story as ST

NAME = 'plan'
DESCRIPTION = 'Disc file and language layout'
AFTER = ('models', 'species', 'sound', 'title', 'story', 'screens', 'localize', 'signs', 'balance', 'storycopies')
FACTS = True
SOUND = ('FAALL', 'VBALL', 'VLALL', 'ESALL')
PLACEHOLDER = bytes(2048)    # an overlay's Spanish copy and LANGEN/LANGES.BIN until the executable is built


class Plan:
    """The bash's PLAN_IN (--file and --add in their order), LN, LANG_FILES and LANG_OVL."""
    def __init__(self, ctx):
        self.ctx, self.files, self.adds, self.ln, self.lang_files, self.lang_ovl = ctx, [], [], 0, [], []
        self.authored = []

    def file(self, dest, src):
        self.files.append(f'{dest}={src}')

    def add(self, dest, src):
        self.adds.append(f'{dest}={src}')

    def lang_copy(self, name, d, src=None, data=None, lang="es"):
        """the Spanish copy of the disc file NAME (DIR/LEnnn.EXT; a root file's in SCN/: the root directory is full, and
        the BIOS finds SYSTEM.CNF in its first sector only) -> its name"""
        from tools.languages import PREFIXES
        c = f'{PREFIXES[lang]}{self.ln:03d}.{name.rsplit(".", 1)[1]}'
        self.ln += 1
        dst = self.ctx.path('lang', c)
        if data is not None:
            with open(dst, 'wb') as f:
                f.write(data)
        else:
            shutil.copyfile(src, dst)
        self.add(f'{d or "SCN"}/{c}', dst)
        self.set_lang(name, lang, c)
        return c

    def set_lang(self, name, lang, copy):
        from tools.languages import COLUMNS
        rows = [i for i, row in enumerate(self.lang_files) if row.split(':')[0] == name]
        i = rows[0] if rows else len(self.lang_files)
        row = self.lang_files[i].split(':') if rows else [name, '-', '-']
        col = COLUMNS[lang]
        row += ['-'] * max(0, col + 1 - len(row))
        row[col] = copy
        if rows:
            self.lang_files[i] = ':'.join(row)
        else:
            self.lang_files.append(':'.join(row))

    def lang_of(self, name, col):
        """NAME's copy in LANG_FILES (col 1: Spanish, 2: English signs), or None"""
        got = [r.split(':')[col] for r in self.lang_files if r.split(':')[0] == name and len(r.split(':')) > col and r.split(':')[col] != '-']
        if len(got) > 1:
            raise SystemExit(f'derive plan: {name} has {len(got)} copies in LANG_FILES')
        return got[0] if got else None

    def story_lang(self, d, copy, src):
        """EXTENDED STORY's copy of the language copy COPY (_E004.SCN for LE004.SCN: the executable's rule)"""
        dst = self.ctx.path('lang', '_' + copy[1:])
        shutil.copyfile(src, dst)
        self.add(f'{d}/_{copy[1:]}', dst)


def same(a, b):
    return os.path.isfile(a) and os.path.isfile(b) and filecmp.cmp(a, b, shallow=False)


def lines(path):
    return [l for l in open(path).read().split('\n') if l]


def make(ctx):
    """-> (Plan, the disc list [(option, DEST, SRC)], NEW_FILES)"""
    s, f = ST.Settings(ctx), ctx.facts
    O, P = ctx.path, Plan(ctx)
    orig = s.orig(s.text, f)
    P.add('DIGI.DAT', O('DIGI.DAT'))
    if s.scrn:   # (:325-336)
        P.add('SCRN.DAT', O('SCRN.DAT'))
        if orig and not same(O('SCRN.DAT'), O('orig', 'SCRN.DAT')):
            P.add('SCRNORIG.DAT', O('orig', 'SCRN.DAT'))
    if orig:     # (:351-353; with the original story beside it every copy goes on the disc)
        for n, x in (('DGORIG.SCN', 'DG.SCN'), ('MHORIG.SCN', 'MAPHEAD.SCN')):
            if s.alt or not same(O(x), O('orig', x)):
                P.add(n, O('orig', x))
    if s.alt:    # (:359-361)
        P.add('SCN/_G.SCN', O('base', 'DG.SCN')); P.add('SCN/_APHEAD.SCN', O('base', 'MAPHEAD.SCN'))
        if orig:
            P.add('SCN/_GORIG.SCN', O('base', 'orig', 'DG.SCN')); P.add('SCN/_HORIG.SCN', O('base', 'orig', 'MAPHEAD.SCN'))
    copies = SC.rows(ctx)
    for dest, name, *_ in copies:            # (:411-415, dws/variants.py plan's --add lines)
        P.add(f'{os.path.dirname(dest)}/{name}', O(SC.OUT, name))
    story_copy = {dest for dest, *_ in copies}
    lang_ovl_files = []
    if s.lang_on:   # (:425-503)
        if os.path.isdir(O('lang')):
            shutil.rmtree(O('lang'))
        os.makedirs(O('lang'))
        from tools.languages import COLUMNS, PATCHES, selected
        for lang in s.languages:
            folder, column = O(lang), COLUMNS[lang]
            for n, d, x in (('DG.SCN', 'SCN', 'DG.SCN'), ('MAPHEAD.SCN', 'SCN', 'MAPHEAD.SCN'), ('SCRN.DAT', '', 'SCRN.DAT'),
                            ('DGORIG.SCN', '', 'orig/DG.SCN'), ('MHORIG.SCN', '', 'orig/MAPHEAD.SCN'),
                            ('SCRNORIG.DAT', '', 'orig/SCRN.DAT')):
                if os.path.isfile(os.path.join(folder, x)) and not same(O(x), os.path.join(folder, x)):
                    P.lang_copy(n, d, os.path.join(folder, x), lang=lang)
            if s.alt:   # (the original story's script text in Spanish, named after the extended story's Spanish copy)
                for n, x in (('DG.SCN', 'base/DG.SCN'), ('MAPHEAD.SCN', 'base/MAPHEAD.SCN'), ('DGORIG.SCN', 'base/orig/DG.SCN'),
                             ('MHORIG.SCN', 'base/orig/MAPHEAD.SCN')):
                    if os.path.isfile(os.path.join(folder, x)):
                        c = P.lang_of(n, column)
                        if not c:
                            raise SystemExit(f'{n} has no {lang} copy: the original story\'s Spanish one has no name')
                        P.story_lang('SCN', c, os.path.join(folder, x))
        for l in lines(O('lang-tex', 'files.txt')):     # the translated textures (the localize step)
            lang, p = l.split(' ', 1)
            if lang != 'en':
                P.lang_copy(os.path.basename(p), os.path.dirname(p), O('lang-tex', lang, p), lang=lang)
            else:
                P.file(p, O('lang-tex', 'en', p))
        # the map signs (the signs step): a Spanish copy and an English-sign copy each; rule: sorted() (the docstring)
        for p in sorted({l.split(' ', 1)[1] for l in lines(O('lang-signs', 'files.txt'))}):
            d, b = os.path.dirname(p), os.path.basename(p)
            for lang in selected(ctx.env):
                if lang in selected(ctx.env) and os.path.isfile(O('lang-signs', lang, p)):
                    P.lang_copy(b, d, O('lang-signs', lang, p), lang=lang)
        if s.alt:
            for l in lines(O('lang-signs-base', 'files.txt')):
                lang, p = l.split(' ', 1)
                if p not in story_copy:
                    continue                 # the same file in both stories: the row above serves both
                c = P.lang_of(os.path.basename(p), COLUMNS[lang])
                if not c:
                    raise SystemExit(f'{p}: the original story\'s {lang} signs have no extended story\'s copy to be named after')
                P.story_lang(os.path.dirname(p), c, O('lang-signs-base', lang, p))
        # placeholders: the overlays of the tree and SHOP_REL.BIN in the order of their names, MENU_REL.BIN last
        ovls = sorted({f'{o}_REL.BIN' for o in f['overlays']} | {'SHOP_REL.BIN'})
        for lang in s.languages:
            for b in ovls + (['MENU_REL.BIN'] if f.get('overlay_menu') else []):
                c = P.lang_copy(b, '', data=PLACEHOLDER, lang=lang)
                P.lang_ovl.append(f'{lang}:{b}:{c}')
                lang_ovl_files.append(f'SCN/{c}')
        for lang in selected(ctx.env):
            n = PATCHES[lang]
            with open(O('lang', n), 'wb') as fh:
                fh.write(PLACEHOLDER)
            P.add(f'SCN/{n}', O('lang', n))
            lang_ovl_files.append(f'SCN/{n}')
    from .species import species_tools
    with species_tools() as S:      # the models of the disc's species (species.py disc-files)
        for opt, dest, x in S.disc_files(O('species')):
            (P.file if opt == '--file' else P.add)(dest, S.resolve_path(x))
    for x in ('ETCNA/TITLE256.TIM', 'ETCNA/TITLE2.TIM'):
        P.file(x, O('title', x))
    for x in ctx.env.get('EXTRA_FILES', '').split():
        P.file(*x.split('=', 1))
    with ST.tools(ctx.root, ctx):
        import newfiles, screens
        try:
            disc, new = newfiles.plan(P.files, P.adds, s.screens, names=set(f['file_table']))
        except (newfiles.PlanError, screens.ScreenError) as e:
            raise SystemExit(f'newfiles.py: {e}')
    with open(O('newfiles.txt'), 'w') as fh:   # (the bash's newfiles.txt)
        fh.write(''.join(f'{o}\t{d}={x}\n' for o, d, x in disc) + 'NEW_FILES\t' + ' '.join(new) + '\n')
    if s.lang_on and not f.get('makefile_lang_files'):
        raise SystemExit('LANGS needs an executable with the language patch (LANG_FILES): the tree has none')
    if new and not f.get('makefile_new_files'):
        raise SystemExit(f'new file names ({" ".join(new)}) need an executable with patch 0147 (NEW_FILES): the tree has none')
    disc = list(disc)
    if f.get('overlay_menu'):   # patch 0209: a new file, in a folder (the root directory's first sector keeps SYSTEM.CNF)
        disc.append(('--add', 'SCN/MENU_REL.BIN', O('exe', 'MENU_REL.BIN')))
    disc += [('--file', f'SOUND/VHB/{k}.VHB', O('sound', f'{k}.VHB')) for k in SOUND]
    disc += [('--file', 'SCN/MAPHEAD.SCN', O('MAPHEAD.SCN')), ('--file', 'SCN/DG.SCN', O('DG.SCN'))]
    disc += [('--file', *x.split('=', 1)) for x in ST.map_files(ctx, '') + BAL.files(ctx, '')]
    authored = ['SLUS_010.32'] + sorted({f'{o}_REL.BIN' for o in f['overlays']} | {'SHOP_REL.BIN'}) + \
        (['SCN/MENU_REL.BIN'] if f.get('overlay_menu') else []) + lang_ovl_files
    return P, disc, new, authored


def final(disc):
    """{DEST: SRC} as build-disc.py makes the disc of the list (the last --file of a DEST wins)."""
    return {d: x for _, d, x in disc}


def build(ctx):
    P, disc, new, authored = make(ctx)
    pmm = open(ctx.path('derived', 'species.env')).read().strip().split('=', 1)[1]
    with open(ctx.path('derived', 'disc.txt'), 'w') as fh:
        fh.write(''.join(f'{o}\t{d}={x}\n' for o, d, x in disc))
    env = dict(PARTNER_MMD_MAX=pmm, NEW_FILES=' '.join(new), LANG_FILES=' '.join(P.lang_files),
               LANG_OVL=' '.join(P.lang_ovl))
    with open(ctx.path('derived', 'plan.env'), 'w') as fh:
        fh.write(''.join(f"{k}='{v}'\n" for k, v in env.items()))
    plan = dict(env, NEW_FILES=new, LANG_FILES=P.lang_files, LANG_OVL=P.lang_ovl, authored=authored)
    with open(ctx.path('derived', 'plan.json'), 'w') as fh:
        json.dump(plan, fh, indent=1)
        fh.write('\n')
    # every file of the list another step names must be that step's bytes (a step's disc paths are its own claim)
    claimed, bad = claims(ctx), []
    for d, x in final(disc).items():
        if d in claimed and d not in authored and _sha1(x) != _sha1(ctx.path(claimed[d][0])):
            bad.append(f'{d}: {x} is not step {claimed[d][1]}\'s {claimed[d][0]}')
    if bad:
        raise SystemExit('derive plan: the disc would get other bytes than the step that makes them:\n  ' + '\n  '.join(bad))
    ctx.log(f'{len(disc)} disc files ({sum(1 for o, *_ in disc if o == "--add")} new), {P.ln} language copies, '
            f'NEW_FILES={" ".join(new)}')


def _sha1(p):
    with open(p, 'rb') as f:
        return hashlib.sha1(f.read()).hexdigest()


def claims(ctx):
    """{disc path: (file under ctx.out, step)} of every other owned step's outputs."""
    from . import OWNED, load
    out = {}
    for n in OWNED:
        if n == NAME:
            continue
        for rel, d in load(n).outputs(ctx):
            if d:
                out[d] = (rel, n)
    return out


def manifest_plan(ctx):
    """the manifest's "plan" (derived/plan.json)"""
    p = ctx.path('derived', 'plan.json')
    return json.load(open(p)) if os.path.isfile(p) else {}


def outputs(ctx):
    p = ctx.path('derived', 'disc.txt')
    if not os.path.isfile(p):
        return []
    plan = manifest_plan(ctx)
    claimed = claims(ctx)
    out = []
    for d, x in final([l.split('\t', 1)[:1] + l.split('\t', 1)[1].split('=', 1) for l in lines(p)]).items():
        if d not in claimed and d not in plan.get('authored', ()):
            out.append((os.path.relpath(x, ctx.out), d))
    return out + [(os.path.join('derived', n), None) for n in ('disc.txt', 'plan.env', 'plan.json')] + \
        [('newfiles.txt', None)]
