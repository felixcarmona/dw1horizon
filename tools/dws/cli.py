"""Command line of tools/dws.py."""
import argparse, os, re, sys, json
from .diag import DwsError
from . import build as B


def opcode_set(prog):
    return ('original', 'wide-ID', 'story-state')[prog.required_opcode_level]


def exe_arg(p):
    p.add_argument('--exe', choices=('original', 'mods', 'species', 'story-state'), default='original',
                   help='target executable: original (default: original, accents stripped), mods (wide ids, '
                        'accents), species (mods + Digimon 180 and up) or story-state (the story-state engine: story flags and 32-bit variables, '
                        'docs/mods/story-state-engine.md)')
    p.add_argument('--ground-pickup-max', type=int, default=None, metavar='IDS',
                   help='target daily pickup bitset bound (default: target item.h; 0: legacy instructions; derive passes its executable fact)')
    p.add_argument('--maphead-max', type=lambda v: int(v, 0), default=None, metavar='BYTES',
                   help='MAPHEAD.SCN limit: the target executable\'s MAPHEAD_SCRIPT_BUFFER (default: 25000 for original, 0x8000 for the mod '
                        'executables; tools/build-full.sh passes its worktree\'s MAPHEAD_SCRIPT_MAX)')
    p.add_argument('--exe-dir', default=None, metavar='DIR',
                   help='the built executable of --exe mods, species or story-state (default build/decomp-mods, -int for species, -story-state/'
                        'build/us/psx/gcc): `disc` ships it, and the text may use the extra glyphs it has (docs/mods/font.md)')
    p.add_argument('--exe-font', choices=('original', 'a', 'b'), default=None,
                   help='the target executable\'s font (docs/mods/font.md "Fonts"; default: read from its build; '
                        'tools/build-full.sh passes the FONT it builds with): how wide a line is and how many characters a row holds')
    p.add_argument('--font-glyphs', type=int, default=None, metavar='N',
                   help='the target executable has the first N extra glyphs of tools/font/extra.txt (default: read from its '
                        'build; tools/build-full.sh passes its worktree\'s NUM_EXTRA_GLYPHS)')


def common(p):
    p.add_argument('files', nargs='+', help='story files: .py (the story language) and .dws; a mod\'s folder is all its sources (src/)')
    exe_arg(p)
    p.add_argument('--lang', default='en', metavar='LANG',
                   help='the language of the mods\' new lines: each mod\'s text/LANG.json (its translation, by the keys of its '
                        'text/en.json: `dws text sync MOD`); a line it lacks stays English and is listed (docs/mods/translating.md)')
    p.add_argument('--text', action='append', default=[], metavar='BANK.json', help='extra text bank (repeatable)')
    p.add_argument('--lock', help='story.lock: append-only flag/variable numbers')
    p.add_argument('--profile', choices=('original', 'extended-save'), default=None,
                   help='capacity profile: original (original executable pools; the default) or extended-save (16 384 flags, 1 024 variables: needs --exe story-state '
                        'to compile; `check` accepts it for any --exe)')
    p.add_argument('--update-lock', action='store_true', help='write new allocations into --lock')
    p.add_argument('-v', '--verbose', action='store_true', help='also the build\'s details (sections added for new slots, the '
                   'container\'s layout and size)')


NOISE = re.compile(r'^(script \d+ section \d+: (new \(\d+ lines\)|already there, used by the new slot)|warning: had to rearrange|'
                   r'note: DG\.SCN ends up at|  \S+: slot \d+ \u2192 \d+ sectors)')


def report_lines(report, verbose=False):
    """The build's report as lines; without -v, the details a writer need not read (a section the build adds or reuses for
    a new slot, the container's rearrangement and its size: build-disc.py pads it) are left out."""
    lines = [l for r in report for l in str(r).split('\n')]
    return lines if verbose else [l for l in lines if not NOISE.match(l)]


def mod_files(files):
    """A mod's folder given in place of files (`check story/mods/NAME`) is its sources: src/**/*.dws, then src/**/*.py."""
    import glob
    out = []
    for f in files:
        if not os.path.isdir(f): out.append(f); continue
        src = os.path.join(f, 'src') if os.path.isdir(os.path.join(f, 'src')) else f
        found = [sorted(glob.glob(os.path.join(src, '**', f'*.{x}'), recursive=True)) for x in ('dws', 'py')]
        if not found[0] + found[1]: raise DwsError(f'{f}: no .py or .dws sources (a mod keeps them in src/)', None)
        out += found[0] + found[1]
    return out


def front(a):
    B.BE.SRCMAP = bool(getattr(a, 'srcmap', None))
    a.given = list(a.files); a.files = mod_files(a.files)
    try:
        if a.profile is None: a.profile = 'extended-save' if a.exe == 'story-state' else 'original'
        if a.profile != 'original' and a.exe != 'story-state' and not (a.cmd == 'check' and not getattr(a, 'build', False)):
            sys.exit('error: --profile extended-save compiles only for the story-state engine: add --exe story-state (`check` without --build accepts it for any executable)')
        prog = B.compile_sources(a.files, a.exe, a.lang, a.text, a.lock, a.update_lock, a.profile)
    except B.DwsErrors as e:
        for w in e.warnings: print(w.render('warning'), file=sys.stderr)
        for x in e.errors: print(x.render(), file=sys.stderr)
        n = len(e.errors)
        sys.exit(f'{n} error{"s" if n != 1 else ""}')
    for w in prog.warn.render(): print(w, file=sys.stderr)
    return prog


def main(argv=None):
    ap = argparse.ArgumentParser(prog='dws.py', description='DWS: the Digimon World story language (docs/mods/dws.md)')
    sub = ap.add_subparsers(dest='cmd', required=True)
    for c, h in (('compile', 'compile to DG.SCN'), ('disc', 'compile and build build/NAME.bin'),
                 ('show', 'print the generated assembly'), ('check', 'parse, resolve, lint; with --build also assemble')):
        p = sub.add_parser(c, help=h); common(p)
        if c in ('compile', 'disc', 'check'): p.add_argument('-o', default=None if c == 'check' else os.path.join(B.ROOT, 'build/dws/DG.SCN'))
        if c == 'disc':
            p.add_argument('--text-source', default=os.environ.get('TEXT') or 'us', metavar='SOURCE',
                           help='whose text the game\'s own lines are (default: $TEXT, else us): us, ours or a disc\'s (text/SOURCE/); '
                                'not us, the disc is built from story/base as story-build does (docs/mods/translating.md, '
                                '"A mod in your language")')
        if c == 'disc': p.add_argument('--name', default='dws')
        if c in ('compile', 'disc'): p.add_argument('--srcmap', metavar='FILE.json', help='also write a source map: for each script, '
                                                    'the offset of every statement\'s first instruction -> file:line (for tracers and videos; not game data)')
        if c == 'check': p.add_argument('--build', action='store_true')
    p = sub.add_parser('check-spawns', help='check lowered placements against resolved map arrivals; --suggest prints reviewable diffs')
    common(p)
    p.set_defaults(exe='mods')
    p.add_argument('--screen-content', default='')
    p.add_argument('--maps', default='')
    p.add_argument('--margin', type=int, default=300)
    p.add_argument('--enforce-source', action='append', default=[], help='enforce these sources; additional coverage is advisory (repeatable)')
    p.add_argument('--json', help='write coverage and diagnostics')
    p.add_argument('--suggest', action='store_true', help='print source-positioned diffs; never write source files')
    p = sub.add_parser('fmt', help='canonical indentation and spacing'); p.add_argument('files', nargs='+')
    p.add_argument('--check', action='store_true', help='exit 1 if a file would change (no write)')
    p = sub.add_parser('text-extract', help="extract the dialogue of your own disc (extracted/SCN/) into text/us/dialogue.json")
    p.add_argument('-o'); p.add_argument('--lang', default='en')
    p = sub.add_parser('extract-text', add_help=False, help='the text of any known disc (us, jp, jp-rev1, es-fan) -> text/<source>/, US-keyed '
                       '(tools/dws/text/extract.py; --help there)')
    p.add_argument('rest', nargs=argparse.REMAINDER)
    p = sub.add_parser('text-keyed', help='print a script of the disc in the lossless keyed form')
    p.add_argument('script', help='script number (0-221) or "maphead"'); p.add_argument('-o')
    p = sub.add_parser('decompile', help='a script of the disc -> DWS in the port form (one statement per instruction)')
    p.add_argument('script', help='script number (0-221) or "maphead"'); p.add_argument('-o')
    p.add_argument('--readable', action='store_true', help='the beautifier: if/else, loops, choice, say, names; every section proven equivalent to the original')
    p = sub.add_parser('roundtrip', help='decompile every script and MAPHEAD, compile, compare with the disc bytes')
    p.add_argument('--keep', metavar='DIR', help='also write the generated .dws files here')
    p.add_argument('--layout', action='store_true', help='use the story/base directory layout (one file per section chunk) instead of one file per script')
    p = sub.add_parser('coverage', help='what the language can express without asm(): CSV + ranked missing constructs')
    p.add_argument('--out', default=None, help='directory of the CSV files (default build/story-analysis)')
    p = sub.add_parser('decompile-all', help='decompile the whole disc into the story/base layout (one file per section chunk)')
    p.add_argument('-o', default=None, help='output root (default story/base)')
    p.add_argument('--readable', action='store_true', help='the beautifier (readable events, each proven against the disc) instead of the port form')
    p.add_argument('--scripts', default=None, help='with --readable: only these script numbers, e.g. 2,3,178 (default all, plus MAPHEAD)')
    p = sub.add_parser('readable-coverage', help='run the beautifier over the whole disc: build/story-analysis/beautifier-coverage.csv and the numbers')
    p.add_argument('--out', default=None, help='directory of the CSV (default build/story-analysis)')
    p = sub.add_parser('names', help='derive pstat/trigger names from the decompilation headers (story/names.toml) and list the 30 most used unnamed ones')
    p.add_argument('--check', action='store_true', help='write nothing; fail if story/names.toml is not what the headers give')
    p = sub.add_parser('new', help='scaffold a zone, quest, npc or mod in the story/ tree')
    p.add_argument('kind', choices=('zone', 'quest', 'npc', 'mod')); p.add_argument('name', help='NAME, or ZONE/NAME for quest and npc')
    p.add_argument('--mod', help='put it in story/mods/MOD/src instead of story/base')
    p = sub.add_parser('city-extract', help='the original city rules (prosperity, File City top map, revival, start state, overlay maps) read out of the decompilation C -> a city { } declaration')
    p.add_argument('-o', help='write the declaration here (default story/base/city/city.dws)'); p.add_argument('--src', help='decomp/src directory (default: decomp/src, the unmodified main branch)')
    p.add_argument('--no-presence', action='store_true', help='skip the MAPHEAD presence rules (the slow part)')
    p = sub.add_parser('city-compile', help='a city { } declaration -> the table the story-state engine reads (and the built-in default header)')
    p.add_argument('file', nargs='?', default=None, help='default story/base/city/city.dws'); p.add_argument('--bin', help='write the table bytes')
    p.add_argument('--c-header', metavar='FILE', help='write the engine\'s built-in default table (city_default.h)')
    p = sub.add_parser('city-verify', help='compare the declarations with the original: the rules against the C they were read from, every NPC rule against the original MAPHEAD instructions on a grid of states')
    p.add_argument('files', nargs='*', help='declaration files or directories (default story/base/city/city.dws and story/base/city/presence/)')
    p = sub.add_parser('why', help='explain why an NPC (or a city rule) is or is not there for a given state')
    p.add_argument('what', help='an NPC (its name in a mod written in Python, or a species), or one of: top_map, revival, prosperity')
    p.add_argument('mods', nargs='*', help='where the mods written in Python are: mod folders or files (default: story/mods/*)')
    p.add_argument('--as', dest='as_', metavar='STATE', help='for a Python NPC: the state to evaluate its guards in, e.g. "Horn=ASKED, invited"')
    p.add_argument('--screen', type=int, help='restrict to this screen'); p.add_argument('--trigger', type=int, action='append', default=[], metavar='N', help='a trigger that is set (repeatable)')
    p.add_argument('--recruit', action='append', default=[], metavar='SPECIES', help='a recruited species (sets trigger 200 + type; repeatable)')
    p.add_argument('--pstat', action='append', default=[], metavar='N=V', help='a pstat value, e.g. 1=60 (prosperity)'); p.add_argument('--hour', type=int, default=9)
    p.add_argument('--day', type=int, default=0); p.add_argument('--random', action='append', default=[], metavar='K=V', help='the value the K-th random draw gives')
    p = sub.add_parser('story-build', help='the story of the game: story/base (made from your disc) + the mods\' overrides + SOURCES -> DG.SCN and MAPHEAD.SCN')
    p.add_argument('files', nargs='*', help='more sources compiled on top (dev-save, EXTRA_STORY; a mod\'s .py files or its folder)'); exe_arg(p)
    p.add_argument('-o', default=os.path.join(B.ROOT, 'build/story/DG.SCN'))
    p.add_argument('--lang', default='en', metavar='LANG', help='the language of the mods\' new lines (their text/LANG.json)')
    p.add_argument('--text', action='append', default=[], metavar='BANK.json'); p.add_argument('--lock'); p.add_argument('--update-lock', action='store_true')
    p.add_argument('--profile', choices=('original', 'extended-save'), default=None)
    p.add_argument('-v', '--verbose', action='store_true', help='also the build\'s details')
    p.add_argument('--audio', help='story audio resource manifest; apply bindings at their assembled instruction offsets')
    p.add_argument('--mods', default=os.environ.get('STORY_MODS'), help='whose overrides apply: all (default: every story/mods/<mod>/overrides), none, or a,b')
    p.add_argument('--refresh', action='store_true', help='make story/base again even if it is up to date')
    p.add_argument('--base', default=None, help='another folder in place of story/base (made there from your disc; for tool development)')
    p.add_argument('--text-source', default=os.environ.get('TEXT') or 'us', metavar='SOURCE',
                   help='whose text the story shows (default: $TEXT, else us): text/<source>/ over the US bank; a key it lacks '
                        'stays US English and is listed (text-fallback.txt beside -o). Needs --exe mods/species/story-state for accents')
    p.add_argument('--strict', action='store_true', help='fail when the text source lacks a key')
    p.add_argument('--from-dws', action='store_true', help='build the base from its generated DWS (story/base/**/script.dws) instead of its Python view (the default; the same bytes)')
    p.add_argument('--from-py', action='store_true', help=argparse.SUPPRESS)            # (the default since 2026-10-13)
    # the build's settings (backend.configure); not given, the environment's: tools/derive gives each story pass its own
    p.add_argument('--screen-content', metavar='DIR:DIR', help='more screen files (ids >= 255) beside content/screens '
                   '(default: $SCREEN_CONTENT)')
    p.add_argument('--maps', metavar='DIR:DIR', help='a mod\'s retouched maps the placements keep (default: $DWS_MAPS)')
    p.add_argument('--relayout', choices=('0', '1'), help='1: the disc is built with --relayout, DG.SCN may grow (default: $DWS_RELAYOUT)')
    p.add_argument('--pack-ascii', choices=('0', '1'), help='1: the texts store letters as one byte (patch 0145; default: '
                   '$SCNASM_PACK_ASCII)')
    p.add_argument('--text-zones', metavar='ZONE,...', help='a test build of only these zones of the text source (default: $TEXT_ZONES)')
    p.add_argument('--read-only-locks', action='store_true', help='the mods\' save.lock files are only read: a story that would '
                   'add a number to one stops (the player\'s build: tools/derive)')
    p = sub.add_parser('story-base', help='make story/base (the readable original story) from your disc, if missing or out of date')
    p.add_argument('--refresh', action='store_true'); p.add_argument('--base', default=None, help='another folder in place of story/base')
    p.add_argument('--check', action='store_true', help='make it again and prove its Python view: every view lowered and compared with the disc')
    p.add_argument('--reproduce', action='store_true', help='make it again in a scratch folder and compare it with the committed story/base, byte for byte (fails if they differ)')
    p = sub.add_parser('story-section', help='one event of story/base as a standalone file (to read, or to make a .patch with diff -u)')
    p.add_argument('script', help='script number or "maphead"'); p.add_argument('section', type=int); p.add_argument('-o')
    p = sub.add_parser('story-verify', help='two builds section by section (flowcmp): A_DG A_MAPHEAD B_DG B_MAPHEAD')
    p.add_argument('scn', nargs=4)
    p = sub.add_parser('text', help='`text sync [MOD...]`: the text banks of the mods written in Python (keys by the hash of the words); '
                       '`text review [ZONE...]`: every key with JP, US, ES and ours side by side (build/text-review/, local only); '
                       '`text review MOD`: a mod\'s lines, English beside each translation, with who says them and what is left to do')
    p.add_argument('action', choices=('sync', 'review')); p.add_argument('mods', nargs='*'); p.add_argument('-o', default=None)
    p = sub.add_parser('lower', help='the DWS of a story file in Python (.py)')
    p.add_argument('file')
    p = sub.add_parser('slots', help='a screen\'s NPC slots (species, base names, positions), the next free slot and its entries')
    p.add_argument('screen', help='a screen number or a Screen member name (jijimons_house)')
    p = sub.add_parser('types', help='the stub package typings/dw/ for Pylance/pyright (the Python story language)')
    p.add_argument('--check', action='store_true', help='only compare with the files there (exit 1 if one differs)')
    from .checks import heap
    heap.add_arguments(sub.add_parser('check-heap', help='check every setup against the actual executable and archive'))
    p = sub.add_parser('doctor', help='check the story/ layout (READMEs, names, file sizes, manifests)')
    p.add_argument('--root', default=None)
    a = ap.parse_args(argv)
    if a.cmd == 'check-heap':
        sys.exit(heap.run(a))
    B.BE.GROUND_PICKUP_MAX = getattr(a, 'ground_pickup_max', None) or 0
    B.BE.MAPHEAD_MAX_GIVEN = getattr(a, 'maphead_max', None)
    B.BE.EXE_DIR_GIVEN = getattr(a, 'exe_dir', None); B.BE.FONT_GLYPHS_GIVEN = getattr(a, 'font_glyphs', None)
    B.BE.FONT_NAME_GIVEN = getattr(a, 'exe_font', None)
    if getattr(a, 'exe', 'original') != 'original' and getattr(a, 'ground_pickup_max', None) is None:
        B.BE.GROUND_PICKUP_MAX = B.exe_ground_pickup_max(B.BE.exe_dir(a.exe))
    if a.cmd == 'check-spawns':
        from .checks import spawns
        a.files = mod_files(a.files)
        sys.exit(spawns.run(a))
    if a.cmd == 'story-build':
        flag = lambda v: None if v is None else v == '1'
        B.BE.configure(screen_dirs=None if a.screen_content is None else a.screen_content.split(':'),
                       maps=None if a.maps is None else a.maps.split(':'), relayout=flag(a.relayout),
                       pack_ascii=flag(a.pack_ascii), text_zones=a.text_zones, locks_read_only=a.read_only_locks)
    try:
        if a.cmd in ('compile', 'disc', 'show', 'check'): cmd_build(a)
        elif a.cmd == 'fmt': cmd_fmt(a)
        elif a.cmd == 'text-extract': cmd_extract(a)
        elif a.cmd == 'extract-text':
            sys.path.insert(0, os.path.join(B.ROOT, 'tools'))
            from dws.text import extract as TE
            sys.exit(TE.main(a.rest))
        elif a.cmd == 'text-keyed': cmd_keyed(a)
        elif a.cmd == 'decompile': cmd_decompile(a)
        elif a.cmd == 'roundtrip': cmd_roundtrip(a)
        elif a.cmd == 'coverage': cmd_coverage(a)
        elif a.cmd == 'decompile-all': cmd_decompile_all(a)
        elif a.cmd == 'readable-coverage':
            from . import readable
            readable.run_coverage(a.out)
        elif a.cmd == 'names':
            from . import names
            if a.check:
                cur = open(names.TOML, encoding='utf-8').read()
                sys.exit(0 if cur == names.generate(write=False) else 'story/names.toml is out of date: run `dws names`')
            names.generate()
            for r in names.todo(): pass
            print(os.path.relpath(names.TOML, B.ROOT), os.path.relpath(names.TODO, B.ROOT))
        elif a.cmd == 'lower':
            from .py import lower as PL
            m, sc, mh = PL.lower_file(a.file)
            seen = set(); out = []                    # the parts' import blocks once (the script imports the declarations shown above it)
            for part in (m.decl_text, sc, mh):
                for l in (part or '').splitlines():
                    if re.match(r'(import ".*";|module \w+;)$', l):
                        if l in seen or l.endswith('.decl.dws";') and m.decl_text: continue
                        seen.add(l)
                    out.append(l)
            sys.stdout.write('\n'.join(out) + '\n')
        elif a.cmd == 'text' and a.action == 'review' and a.mods and all(
                os.path.isdir(os.path.join(m, 'src')) or os.path.isdir(os.path.join(B.ROOT, 'story', 'mods', m, 'src')) for m in a.mods):
            from .py import textsync                  # a mod's lines (its folder, or its name in story/mods/)
            for m in a.mods:
                d = os.path.abspath(m.rstrip('/'))
                if os.path.isdir(os.path.join(d, 'src')): textsync.review(os.path.basename(d), os.path.dirname(d), a.o)
                else: textsync.review(m, None, a.o)
        elif a.cmd == 'text' and a.action == 'review':
            sys.path.insert(0, os.path.join(B.ROOT, 'tools'))
            from dws.text import review
            sys.exit(review.main(a.mods + (['-o', a.o] if a.o else [])))
        elif a.cmd == 'text':
            from .py import textsync
            have = textsync.mods_with_python(); todo = []
            for mod in a.mods:                        # a mod's name (story/mods/NAME), or its folder wherever it is
                d = os.path.abspath(mod.rstrip('/'))
                if os.path.sep in mod.rstrip('/') or os.path.isdir(mod):
                    if not textsync.mod_sources(os.path.basename(d), os.path.dirname(d)):
                        raise DwsError(f'{mod}: no mod written in Python here (src/*.py, or `sources` in its mod.toml)', None)
                    todo.append((os.path.basename(d), os.path.dirname(d))); continue
                if mod not in have: raise DwsError(f'no mod "{mod}" written in Python (story/mods/{mod}/src/*.py)',
                                                   None, 'the mods: ' + ', '.join(have))
                todo.append((mod, None))
            for mod, where in todo or [(m, None) for m in have]: textsync.sync(mod, mods=where)
        elif a.cmd == 'slots':
            from .py import slots
            sys.exit(slots.run(a.screen))
        elif a.cmd == 'types':
            from .py import stubs
            sys.exit(1 if stubs.write(check=a.check) and a.check else 0)
        elif a.cmd == 'new':
            from . import scaffold
            for f in scaffold.new(a.kind, a.name, a.mod): print(os.path.relpath(f, B.ROOT))
        elif a.cmd in ('city-extract', 'city-compile', 'city-verify', 'why'):
            from . import citycli
            sys.exit(citycli.run(a) or 0)
        elif a.cmd == 'doctor':
            from . import scaffold
            sys.exit(1 if scaffold.run_doctor(a.root) else 0)
        elif a.cmd.startswith('story-'):
            cmd_story(a)
    except DwsError as e:
        sys.exit(e.render())
    except B.BE.BackendError as e:
        sys.exit(B.backend_error(e).render())
    except (FileNotFoundError, ValueError) as e:
        sys.exit(f'error: {e}')


def cmd_build(a):
    if a.cmd == 'disc' and a.text_source != 'us': return cmd_disc_story(a)
    prog = front(a)
    if a.cmd == 'show':
        for sid, info in sorted(prog.b.scripts.items()):
            for sec, rep, code, ents, path in info['events']:
                print(f'; script {sid}, section {sec}{" (replace)" if rep else ""}')
                print('\n'.join(prog.b.gen_event(sec, rep, code, ents, path))); print()
            for name, code, path in info.get('shared', []):
                print(f'; script {sid}, shared {name}'); print('\n'.join(code)); print()
        for name, code, path in getattr(prog.b, 'mh_shared', []):
            print(f'; MAPHEAD, shared {name}'); print('\n'.join(code)); print()
        print_tables(prog); B.save_locks(); return
    if a.cmd == 'check' and not a.build:
        heap = []
        if prog.b.placements or prog.b.new_scripts or prog.b.city is not None:      # what only the back end knows: the screen's .MAP
            import tempfile                                                         # (slots, walls) and its heap: built and thrown away
            report, _ = B.assemble(prog, os.path.join(tempfile.mkdtemp(prefix='check-', dir=B.BE.RUN_ROOT), 'DG.SCN'), a.exe)
            heap = [r for r in report if ' heap: ' in r or r.startswith('note: screen')]
        n = sum(len(i['events']) for i in prog.b.scripts.values())
        names = ', '.join(os.path.basename(f.rstrip('/')) for f in a.given) if len(a.given) <= 3 else f'{len(a.given)} files'
        print(f'ok: {names}, {n} event{"s" if n != 1 else ""}' + (f', {opcode_set(prog)} instructions' if prog.required_opcode_level else ''))
        for r in prog.notes + heap: print(r)
        print_tables(prog); B.save_locks(); return
    out = getattr(a, 'o', None) or os.path.join(B.ROOT, 'build/dws/check-DG.SCN')
    report, run = B.assemble(prog, out, a.exe, srcmap=getattr(a, 'srcmap', None))
    for r in prog.notes + report_lines(report, a.verbose): print(r)
    print_tables(prog); print(f'DG.SCN: {out}  ({opcode_set(prog)} instructions)')
    if getattr(a, 'srcmap', None): print(f'source map: {a.srcmap}')
    if prog.b.maphead: print(f'MAPHEAD.SCN: {prog.b.maphead}')          # screens' setup with placed Digimon / new scripts
    for rel, path in prog.b.maps.items(): print(f'FILE: {rel}={path}')  # maps whose NPC table changed (build-disc.py --file)
    if a.cmd == 'disc': B.disc(prog, a.name, out, a.exe)
    B.save_locks()                                                      # (only a run that succeeded fills save.lock)


def cmd_disc_story(a):
    """`disc --text-source ours`: the game's own lines in a text source and the mods' in --lang: the story build (story/base
    in that source, the mods' .py files on top), then the disc."""
    from . import basebuild as BB
    files = mod_files(a.files)
    if a.exe != 'original' and B.BE.MAPHEAD_MAX_GIVEN is None:     # the MAPHEAD buffer of the executable the disc ships
        try: B.BE.MAPHEAD_MAX_GIVEN = B.exe_maphead_max(B.BE.exe_dir(a.exe))
        except (OSError, AttributeError): pass
    if a.profile is None: a.profile = 'extended-save' if a.exe == 'story-state' else 'original'
    try:
        prog, report, run, maphead = BB.build(files, a.o, a.exe, a.lang, a.text, a.lock, a.update_lock, a.profile, mods=[],
                                              text_source=a.text_source)
    except B.DwsErrors as e:
        for w in e.warnings: print(w.render('warning'), file=sys.stderr)
        for x in e.errors: print(x.render(), file=sys.stderr)
        sys.exit(f'{len(e.errors)} error(s)')
    for w in prog.warn.render(): print(w, file=sys.stderr)
    for r in prog.notes + report_lines(report, a.verbose): print(r)
    print_tables(prog); print(f'DG.SCN: {a.o}  ({opcode_set(prog)} instructions; the game\'s lines: {a.text_source}, the mods\': {a.lang})')
    if prog.b.maphead is None: prog.b.maphead = maphead
    B.disc(prog, a.name, a.o, a.exe)
    B.save_locks()


def cmd_story(a):
    from . import basebuild as BB
    if a.cmd == 'story-base':
        base = os.path.abspath(a.base) if a.base else BB.BASE
        if a.reproduce: sys.exit(1 if BB.reproduce(base) else 0)
        if not BB.ensure_base(base, refresh=a.refresh or a.check, check=a.check): print(f'{os.path.relpath(base, B.ROOT)} is up to date (made from this disc and these tools)')
        return
    if a.cmd == 'story-section':
        sid = 'maphead' if a.script == 'maphead' else int(a.script)
        BB.ensure_base(log=lambda m: print(m, file=sys.stderr))
        src, path = BB.event_source(BB.BASE, sid, a.section)
        if a.o: open(a.o, 'w', encoding='utf-8').write(src); print(a.o)
        else: sys.stdout.write(src)
        return
    if a.cmd == 'story-verify':
        sys.exit(1 if BB.verify(*a.scn) else 0)
    if a.profile is None: a.profile = 'extended-save' if a.exe == 'story-state' else 'original'
    try:
        prog, report, run, maphead = BB.build(mod_files(a.files), a.o, a.exe, a.lang, a.text, a.lock, a.update_lock, a.profile,
                                              mods=BB.parse_mods(a.mods), refresh=a.refresh,
                                              base=os.path.abspath(a.base) if a.base else BB.BASE, from_py=not a.from_dws,
                                              text_source=a.text_source, strict=a.strict)
    except B.DwsErrors as e:
        for w in e.warnings: print(w.render('warning'), file=sys.stderr)
        for x in e.errors: print(x.render(), file=sys.stderr)
        sys.exit(f'{len(e.errors)} error(s)')
    for w in prog.warn.render(): print(w, file=sys.stderr)
    for r in report_lines(report, a.verbose): print(r)
    if a.audio:
        from . import audio
        for line in audio.rewrite_maphead(maphead, maphead, a.audio):
            print(line)
    print_tables(prog); print(f'DG.SCN: {a.o}  ({opcode_set(prog)} instructions)')
    print(f'MAPHEAD.SCN: {maphead}')
    B.save_locks()
    for rel, path in prog.b.maps.items(): print(f'FILE: {rel}={path}')


def print_tables(prog):
    """The numbers the saved flags and variables got (scratch and scene variables are not saved: left out)."""
    saved = {q for (_, scope, _), q in prog.alloc.used.items() if scope == 'save'}
    print('allocation:', json.dumps({q: n for q, n in prog.alloc.table.items() if q in saved}))


def cmd_fmt(a):
    from .fmt import format_source
    bad = 0
    for f in a.files:
        src = open(f, encoding='utf-8').read(); new = format_source(src, f)
        if new != src:
            bad += 1
            if a.check: print(f'{f}: would be reformatted')
            else: open(f, 'w', encoding='utf-8').write(new); print(f'{f}: formatted')
    if a.check and bad: sys.exit(1)


def cmd_extract(a):
    from . import textx
    out = a.o or textx.BANK
    bank = textx.extract()
    textx.write_bank(bank, out, a.lang)
    print(f'{len(bank)} text keys (utterances and menu options) -> {os.path.relpath(out, B.ROOT)} '
          '(gitignored: the original text is never committed)')
    from . import textbank
    n = textbank.write_us_pages(bank)          # (committed: numbers only, what the single-page check of other sources needs)
    print(f'{n} page counts of the single-page lines -> {os.path.relpath(textbank.PAGES, B.ROOT)}')


def cmd_keyed(a):
    from . import textx
    src = textx.keyed_maphead() if a.script == 'maphead' else textx.keyed_script(int(a.script))
    if a.o: open(a.o, 'w', encoding='utf-8').write(src); print(a.o)
    else: sys.stdout.write(src)


def cmd_decompile(a):
    from . import decomp
    if a.readable: return cmd_decompile_readable(a)
    scripts, mh, _ = decomp.decompile_all()
    src = mh if a.script == 'maphead' else scripts.get(int(a.script))
    if src is None: raise FileNotFoundError(f'script {a.script} does not exist (DG.SCN has 0-221)')
    if a.o: open(a.o, 'w', encoding='utf-8').write(src); print(a.o)
    else: sys.stdout.write(src)


def cmd_decompile_readable(a):
    from . import readable, lift
    if a.script == 'maphead':
        scripts, mh = readable.disc_texts(); names = readable.make_names(mh)
        tmp = readable.prepare_tmp(names)
        lifted = lift.lift_script_text(mh, 'maphead', None, 'maphead', names, tmp)
        sid = None
    else:
        sid = int(a.script)
        res, _, names = readable.lift_disc(only={sid}, maphead=False)
        if sid not in res: raise FileNotFoundError(f'script {a.script} does not exist (DG.SCN has 0-221)')
        lifted = res[sid]
    base = os.path.dirname(os.path.abspath(a.o)) if a.o else None
    src, left = readable.script_source(sid, lifted, names, base=base)
    if a.o:
        open(a.o, 'w', encoding='utf-8').write(src); print(a.o)
    else: sys.stdout.write(src)


def cmd_roundtrip(a):
    from . import roundtrip
    roundtrip.run(a.keep, layout=a.layout)


def cmd_coverage(a):
    from . import coverage
    coverage.run(a.out)


def cmd_decompile_all(a):
    from . import layout
    out = a.o or os.path.join(B.ROOT, 'story', 'base')
    if a.readable:
        from . import readable
        only = {int(x) for x in a.scripts.split(',')} if a.scripts else None
        lifted, mhl, names = readable.lift_disc(only=only)
        stats = {}
        readable.write(out, lifted, mhl, names, stats)
        rs = readable.rows(lifted, mhl); sm = readable.summarize(rs)['all']
        print(f'{len(lifted)} scripts{" + MAPHEAD" if mhl else ""} -> {os.path.relpath(out, B.ROOT)}: {sm["readable"]} sections readable, {sm["shared-exit"]} with one shared exit, {sm["partial"]} partial, '
              f'{sm["literal"]} literal, {sm["port-only"]} left in the port form; {stats["proven_events"]} events proven again from the written files')
        return
    stats = {}
    index, mh = layout.write(out, stats=stats)
    print(f'{len(index)} scripts + MAPHEAD -> {os.path.relpath(out, B.ROOT)}: {stats.get("lifted", 0)} instructions as typed statements, '
          f'{stats.get("asm", 0)} as asm()')
    print('check it with: python3 tools/dws.py roundtrip --layout   (compile -> same bytes as the disc)')
