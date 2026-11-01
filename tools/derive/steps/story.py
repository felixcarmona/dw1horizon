"""The script text of the story, every copy the disc carries: DG.SCN and MAPHEAD.SCN compiled from story/base, the mods
and the dev-save script (build-full.sh 2b, :206-257), with story-owned music bindings applied to each MAPHEAD.

A pass is one `dws.py story-build` (tools/dws/basebuild.py) into a folder of build/NAME, as the bash ran them:
  .             the extended story (EXTRA_STORY, the mods' overrides, a developer's MAIN_STORY), paged for the executable's font
  orig          the same paged for the original font (ORIG: the executable has both fonts, FONT=b and DGORIG.SCN in its
                file table): DGORIG.SCN, MHORIG.SCN
  base          EXTENDED STORY's original story (ALT: a story mod and patch 0199): a developer's MAIN_STORY only, no mod, none of the
                mods' retouched maps: _G.SCN, _APHEAD.SCN
  base/orig     that one paged for the original font: _GORIG.SCN, _HORIG.SCN
and with LANGS=en,es the same four in Spanish (TEXT=es, STORY_LANG=es) in build/NAME/es (bash: build/NAME-es, made by a
second run of build-full.sh), whose files the plan names LE000-LE003 and _E000-_E003.

Every pass runs as a script (runner.run_script: its modules imported again, so nothing of one pass reaches the next)
with its settings given on its command line, none read from the environment (backend.configure: --screen-content,
--maps, --relayout, --pack-ascii, --text-zones). Each folder keeps the side files the bash reads afterwards: dws.log (its
MAPHEAD.SCN: and FILE: lines: the story's maps), and lang-es-story.log in build/NAME (the Spanish passes' output). The
story's maps (FILE:) are written in the passes' run folders (build/dws/run-*); the step copies those of the extended
story (.) into story-maps/<disc path> (they go on the disc: the plan step routes them) and those of the original story
(base) into base/story-maps/ (the storycopies and signs steps read them): map_files(ctx, v) lists either.

Units: each pass is one (units(ctx): its command line, folder, what it reads), set-bgm and the with-new-screens copy
included. derive build --jobs N runs independent passes side by side in N processes (runner.run_units;
one process, in order, is the reference, and always so with --strict or --record). Every pass
but the first lowers the mods' .py files into a folder of its own (DWS_LOWERED, build/py-lowered-passes/), as two passes
writing build/py-lowered at once could read each other's half-written files; the first keeps build/py-lowered (the
traces' source maps read it). The new screens' .MAP files are edited in place by every pass that compiles the mods;
their bytes are not required to match between compilations. Those passes share an order_group: the last writer in recorded
order wins, as in the one-process reference, regardless of scheduling priority or worker timing. The base passes with
the standard dev-save main source have no new maps and run independently; a custom main source is conservatively
ordered too, since it may place NPCs in new maps. backend.keep_orig makes each map's .orig once, whole; each pass starts
from that recipe map and writes a whole-file rename. Atomic writes alone do not choose the right last writer.

save.lock (rule): a story that names a new saved variable gets the next number of its mod's range, and the number is
appended to story/mods/<mod>/save.lock, which is committed. Only a developer build appends: build-full.sh runs derive
with --write-locks, as its bash passes did (the story writers rely on it). The player's build (no --write-locks: the
patcher; always with --strict: the browser) only reads the locks (dws --read-only-locks): a story whose new name is not
in its mod's lock stops there, since a number given on the player's machine would not be the one a saved game of
another build has. The same order_group also prevents a pass from reading a save.lock while another pass rewrites it.

With SCRN.DAT in the executable's file table the screens step (screens) takes each MAPHEAD on: this step leaves it, music set,
in FOLDER/with-new-screens/MAPHEAD.SCN as well, which that step reads.
"""
import contextlib
import filecmp
import os
import shutil
import sys

from .. import facts as executable_facts
from .. import runner
from tools.languages import translations

NAME = 'story'
DESCRIPTION = 'Story compilation'
AFTER = ('maps', 'retouch')   # (the story mod's maps: SCREEN_CONTENT, DWS_MAPS; build.sh makes them first)
FACTS = True
DEV_SAVE = 'tools/dws/examples/dev-save.dws'
# the environment the passes no longer read (each pass gets its settings on its command line): removed while they run,
# so a setting read behind the step's back shows up as a different disc
CLEAR = ('SCREEN_CONTENT', 'DWS_MAPS', 'DWS_RELAYOUT', 'SCNASM_PACK_ASCII', 'TEXT_ZONES', 'TEXT', 'STORY_MODS',
         'STORY_LANG', 'LANGS')


class Settings:
    """What build-full.sh works out for the story from the recipe (the environment) and the executable's facts."""
    def __init__(self, ctx):
        env, f = ctx.env, ctx.facts or {}
        self.text = env.get('TEXT') or 'us'
        self.languages = translations(env)
        self.lang_on = bool(self.languages)
        self.story_lang = env.get('STORY_LANG') or 'en'
        self.main = env.get('MAIN_STORY') or ''   # none on a player's disc: a developer's helper never ships
        self.extra = (env.get('EXTRA_STORY') or '').split()
        self.screens = [d for d in (env.get('SCREEN_CONTENT') or '').split(os.pathsep) if d]
        self.maps = env.get('DWS_MAPS') or ''
        self.mods = env.get('STORY_MODS') or 'all'
        # (build-full.sh exports both before the story: DWS_RELAYOUT=1 always, SCNASM_PACK_ASCII by PACK_ASCII and TEXT)
        self.relayout = env.get('DWS_RELAYOUT') == '1'
        self.pack = env.get('SCNASM_PACK_ASCII') == '1'
        self.zones = env.get('TEXT_ZONES') or ''
        self.es_zones = env.get('ES_ZONES') or self.zones
        mh = f.get('maphead_script_max')
        self.mh_max = 0x6800 if mh is None else mh                      # :197
        self.ground_pickup_max = f.get('ground_pickup_max') or 0
        self.glyphs = f.get('font_glyphs') or 0                         # :201
        self.exe_font = env.get('FONT') or f.get('makefile_font') or 'original'    # :203
        self.alt = bool(self.extra) and (env.get('STORY_ALT') or '1') == '1' and bool(f.get('mod_story_file'))   # :219
        self.scrn = bool(f.get('file_table_scrn'))                      # :275

    def exe(self, text, font):
        """STORY_EXE (:207): text, screens, or stable pickups require the mod executable."""
        if text == 'us' and not self.screens and not self.ground_pickup_max:
            return []
        return ['--exe', 'mods', '--imported-npcs', '--ground-pickup-max', str(self.ground_pickup_max),
                '--maphead-max', str(self.mh_max), '--font-glyphs', str(self.glyphs), '--exe-font', font]

    def orig(self, text, facts):
        """ORIG (:210): the story is paged for font b and the executable also reads a copy paged for the original font."""
        return bool(self.exe(text, self.exe_font)) and self.exe_font == 'b' and bool((facts or {}).get('file_table_dgorig'))

    def langs(self, ctx):
        """[(language, its folder, TEXT, STORY_LANG, TEXT_ZONES, pack)]: English, then the selected translations."""
        out = [('en', ctx.out, self.text, self.story_lang, self.zones, self.pack)]
        for lang in self.languages:
            zones = ctx.env.get(lang.upper().replace('-', '_') + '_ZONES') or self.zones
            out.append((lang, ctx.path(lang), lang, lang, zones, self.pack or ctx.env.get('PACK_ASCII') != '0'))
        return out

    def variants(self, text, facts):
        """The folders of one language's passes (relative to it): '', orig, base, base/orig."""
        o = self.orig(text, facts)
        return [''] + (['orig'] if o else []) + (['base'] + (['base/orig'] if o else []) if self.alt else [])


def pass_argv(s, v, text, lang, zones, pack, locks_read_only=True):
    """The story-build command line of the pass in folder v (build-full.sh :229-247)."""
    base = v.startswith('base')
    exe = s.exe(text, 'original' if v.endswith('orig') else s.exe_font)
    files = ([s.main] if s.main else []) + ([] if base else s.extra)
    return (['story-build'] + files + ['--text-source', text, '--lang', lang] + exe +
            ['--audio', 'story/core/audio.json', '--mods', 'none' if base else s.mods, '--screen-content', os.pathsep.join(s.screens),
             '--maps', '' if base else s.maps, '--relayout', '1' if s.relayout else '0',
             '--pack-ascii', '1' if pack else '0', '--text-zones', zones] +
            (['--read-only-locks'] if locks_read_only else []))


@contextlib.contextmanager
def tools(root, ctx=None):
    """tools/ importable for a direct call; the modules imported meanwhile are forgotten afterwards and, given a ctx
    that records, what they open is recorded (as runner.run_script does for a script; inside a unit, runner.run_units
    records around it)."""
    saved, path = set(sys.modules), sys.path[:]
    sys.path.insert(0, os.path.join(root, 'tools'))
    rec = ctx is not None and ctx.record
    if rec:
        runner._install_hook(); outer, runner._recording = runner._recording, (set(), set())
    try:
        yield
    except runner.StepError:
        raise
    except Exception as e:      # (a tool's own error: ScreenError, SoundError...)
        raise runner.StepError(f'{type(e).__name__}: {e}') from e
    finally:
        if rec:
            ctx.note_inputs(*runner._recording)
            runner._recording = outer
        sys.path[:] = path
        for n in [n for n in sys.modules if n not in saved]:
            if runner._repo_module(sys.modules[n]):
                del sys.modules[n]


def maphead_of(log):
    """The MAPHEAD.SCN the pass wrote (its `MAPHEAD.SCN: PATH` line), or None (the disc's)."""
    for line in log.splitlines():
        if line.startswith('MAPHEAD.SCN: '):
            return line[len('MAPHEAD.SCN: '):]
    return None


MAP_PASSES = ('', 'base')         # the English passes whose maps (FILE: lines) later steps read
MAPS = 'story-maps'


def log_files(path):
    """[(DEST, SRC)] of a story build's log (its FILE: lines)"""
    return [tuple(l[len('FILE: '):].split('=', 1)) for l in open(path).read().split('\n') if l.startswith('FILE: ')]


def map_files(ctx, v=''):
    """[DEST=SRC] of the story's maps of the English pass v ('' the extended story, 'base' the original), SRC the step's
    copy (story-maps/DEST), in the order of the pass's FILE: lines."""
    p = ctx.path(v, 'dws.log')
    if not os.path.isfile(p):
        raise SystemExit(f'derive: no {p} (the story step makes it first)')
    return [f'{d}={ctx.path(v, MAPS, d)}' for d, _ in log_files(p)]


def copy_maps(ctx, s):
    """The FILE: maps of the English passes into FOLDER/story-maps/<disc path> (a fresh folder each build)."""
    for v in MAP_PASSES:
        if v and v not in s.variants(s.text, ctx.facts):
            continue
        d = ctx.path(v, MAPS)
        if os.path.isdir(d):
            shutil.rmtree(d)
        for dest, src in log_files(ctx.path(v, 'dws.log')):
            os.makedirs(os.path.dirname(os.path.join(d, dest)), exist_ok=True)
            shutil.copyfile(src, os.path.join(d, dest))


def outputs(ctx):
    s = Settings(ctx)
    out = []
    for v in MAP_PASSES:   # (the extended story's maps go on the disc; the original story's are copied by storycopies)
        if (not v or v in s.variants(s.text, ctx.facts)) and os.path.isfile(ctx.path(v, 'dws.log')):
            out += [(os.path.join(v, MAPS, d), None if v else d) for d, _ in log_files(ctx.path(v, 'dws.log'))]
    for lang, root, text, *_ in s.langs(ctx):
        rel = os.path.relpath(root, ctx.out)
        for v in s.variants(text, ctx.facts):
            d = os.path.normpath(os.path.join(rel, v))
            out.append((os.path.join(d, 'DG.SCN'), disc_path(ctx, s, lang, v, 'DG.SCN')))
            out.append((os.path.join(d, 'MAPHEAD.SCN'), None if s.scrn else disc_path(ctx, s, lang, v, 'MAPHEAD.SCN')))
            if s.scrn:
                out.append((os.path.join(d, 'with-new-screens', 'MAPHEAD.SCN'), None))
    return out


ORIG_NAMES = {'DG.SCN': 'DGORIG.SCN', 'MAPHEAD.SCN': 'MHORIG.SCN', 'SCRN.DAT': 'SCRNORIG.DAT'}
BASE_NAMES = {('base', 'DG.SCN'): 'SCN/_G.SCN', ('base', 'MAPHEAD.SCN'): 'SCN/_APHEAD.SCN',
              ('base/orig', 'DG.SCN'): 'SCN/_GORIG.SCN', ('base/orig', 'MAPHEAD.SCN'): 'SCN/_HORIG.SCN'}


def disc_path(ctx, s, lang, v, f):
    """Where build-full.sh puts the file (:296-334), or None: the Spanish copies are named by the plan (LE000...), the
    original story's SCRN.DAT stays off the disc, and without EXTENDED STORY an *ORIG copy the same as its file too."""
    if lang != 'en':
        return None
    if v == '':
        return {'DG.SCN': 'SCN/DG.SCN', 'MAPHEAD.SCN': 'SCN/MAPHEAD.SCN', 'SCRN.DAT': 'SCRN.DAT'}[f]
    if v == 'orig':
        same = os.path.isfile(ctx.path(f)) and os.path.isfile(ctx.path('orig', f)) and \
            filecmp.cmp(ctx.path(f), ctx.path('orig', f), shallow=False)
        if f == 'SCRN.DAT' or not s.alt:   # (:308 SCRNORIG.DAT only when it differs; :325-326 the same without ALT)
            return None if same else ORIG_NAMES[f]
        return ORIG_NAMES[f]
    return BASE_NAMES.get((v, f))


def pass_name(lang, v):
    return f'{lang} {v or "."}'


def run_pass(root, d, argv, lowered, scrn, archive=None, facts=None):
    """One pass (a unit; in this process or a worker): dws.py story-build into folder d, its log in d/dws.log, the music
    set in its MAPHEAD (and the copy the screens step reads). -> its output; StepError if the story did not build."""
    os.makedirs(d, exist_ok=True)
    env = {k: None for k in CLEAR}
    env['DWS_LOWERED'] = lowered
    env['DW_MODEL_ARCHIVE'] = archive
    env['DW_EXE_FACTS'] = facts
    r = runner.run_script('tools/dws.py', argv + ['-o', os.path.join(d, 'DG.SCN')], env=env, check=False)
    with open(os.path.join(d, 'dws.log'), 'w') as f:
        f.write(r.out)
    head = f'$ tools/dws.py {" ".join(argv)} -o {os.path.join(d, "DG.SCN")}  ({r.seconds:.2f} s)\n'
    if r.code:
        raise runner.StepError(f'{head}exit {r.code}\n{r.out[-3000:]}')
    shutil.copyfile(maphead_of(r.out), os.path.join(d, 'MAPHEAD.SCN'))
    if scrn:
        os.makedirs(os.path.join(d, 'with-new-screens'), exist_ok=True)
        shutil.copyfile(os.path.join(d, 'MAPHEAD.SCN'), os.path.join(d, 'with-new-screens', 'MAPHEAD.SCN'))
    return head + r.out


def units(ctx):
    """The passes in recorded language order, then ., orig, base, base/orig within each language: each a runner.Unit."""
    # Native release replays read facts from the recorded bundle, whereas a
    # developer build captures them under derived/. Give workers the same
    # explicit snapshot in both cases; this side file never enters the disc.
    if ctx.facts is not None:
        executable_facts.save(ctx.facts, ctx.path('derived/exe-facts.json'))
    s = Settings(ctx)
    out, first = [], True
    for lang, root, text, story_lang, zones, pack in s.langs(ctx):
        for v in s.variants(text, ctx.facts):
            d = os.path.join(root, v)
            argv = pass_argv(s, v, text, story_lang, zones, pack, ctx.locks_read_only)
            # (the first pass lowers into build/py-lowered as a lone dws.py run does; the others into their own folder)
            lowered = None if first else os.path.join(ctx.root, 'build', 'py-lowered-passes',
                                                      f'{os.path.basename(ctx.out)}-{lang}-{v.replace("/", "-") or "ext"}')
            first = False
            base = v.startswith('base')
            inputs = (['story/base', 'tools', 'extracted/SCN', 'extracted/MAP', 'content/screens', 'content/species', 'content/tables/city-residents.json', 'text/us',
                       f'text/{text}'] + ([s.main] if s.main else []) + ([] if base else ['story/mods'] + s.extra) +
                      [f'step:maps ({p})' for p in s.screens] + ([] if base or not s.maps else [f'step:retouch ({s.maps})']))
            outs = [os.path.relpath(os.path.join(d, f), ctx.out) for f in ('DG.SCN', 'MAPHEAD.SCN', 'dws.log')]
            ordered = not base or s.main not in ('', DEV_SAVE)   # a custom main source can edit new maps even without mods
            out.append(runner.Unit(pass_name(lang, v), run_pass, (ctx.root, d, argv, lowered, s.scrn,
                        ctx.path('DIGI.DAT') if os.path.isfile(ctx.path('DIGI.DAT')) else None,
                        ctx.path('derived/exe-facts.json') if os.path.isfile(ctx.path('derived/exe-facts.json')) else None),
                        inputs, outs, order_group='story maps and locks' if ordered else None))
    return out


def build(ctx):
    ctx.run_units(units(ctx))
    finish(ctx)


def finish(ctx):
    """After the passes: their FILE: maps copied by disc path, the Spanish passes' log (build-full.sh's step 4b reads
    it: bash's second run's log)."""
    s = Settings(ctx)
    from tools.city_residents import verify
    # Enumerate the build's passes, not one hand-picked mod or language. This
    # runs after cache restores too, on the actual compiled stories on the disc.
    for unit in units(ctx):
        path = os.path.join(ctx.out, unit.outputs[0])
        original = unit.name.split(' ', 1)[1].startswith('base') or s.mods == 'none'
        verify([path, os.path.join(os.path.dirname(path), 'MAPHEAD.SCN')], original=original)
    copy_maps(ctx, s)
    if s.lang_on:
        with open(ctx.path('lang-es-story.log'), 'w') as f:
            f.write(''.join(open(os.path.join(ctx.out, u.outputs[2])).read() for u in units(ctx) if u.name.startswith('es ')))


def check(ctx):
    """The checks the Spanish run of build-full.sh made on its script text (the extended story's are build-full.sh's own):
    its MAPHEAD's music on the sound step's banks (sound.py spu-budget, :291) and each MAPHEAD within the executable's
    MAPHEAD_SCRIPT_BUFFER (:316-321; with SCRN.DAT the screens step's check, once the new screens are out)."""
    s = Settings(ctx)
    banks = ctx.path('sound')
    for lang, root, *_ in s.langs(ctx)[1:]:
        mh = os.path.join(root, 'with-new-screens' if s.scrn else '', 'MAPHEAD.SCN')
        if os.path.isdir(banks):
            r = ctx.run('tools/sound.py', ['spu-budget', '--vhb-dir', banks, '--maphead', mh], check=False)
            if r.code:
                raise SystemExit(f'{mh}: the music of its screens does not fit the SPU (sound.py spu-budget):\n'
                                 + '\n'.join(r.out.splitlines()[-3:]))
    if not s.scrn:
        check_size(ctx)


def check_size(ctx):
    s = Settings(ctx)
    for lang, root, text, *_ in s.langs(ctx)[1:]:
        for v in s.variants(text, ctx.facts):
            mh = os.path.join(root, v, 'MAPHEAD.SCN')
            if os.path.getsize(mh) > s.mh_max:
                raise SystemExit(f'{mh} is {os.path.getsize(mh)} bytes; the executable\'s MAPHEAD_SCRIPT_BUFFER holds {s.mh_max}')
