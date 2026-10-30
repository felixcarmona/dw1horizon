"""tools/derive: the files of the everything disc made from the player's game data, in one Python process
(tools/derive/README.md). Run from the repository root:

  python3 -m tools.derive facts --w DECOMP_TREE [-o FILE]   the tree's settings (exe-facts.json; default
                                                            OUT/derived/exe-facts.json with --out)
  python3 -m tools.derive build --out DIR [--recipe NAME] [--facts FILE | --w TREE] [--steps a,b] [--only DISC_PATH ...]
                                [--checks] [--strict] [--record] [--jobs N] [--write-locks]
        makes the steps derive owns (steps/__init__.py OWNED) into DIR at the paths build-full.sh used (DIR is its
        build/NAME), and DIR/derived/manifest.json (every derived file of the disc, the plan step's "plan").
        --recipe (recipes/NAME.json, recipe.py): a player's build: the recipe's environment, nothing of the machine's
        settings, and the story mod's maps too (into DIR-maps). --only: the smallest set of steps for those disc files.
        --checks: each step's checks too. --strict: no processes or threads (as in the browser). --record: every file
        each step opens goes in the manifest, and a read of a file only the USA disc has (needs-usa in
        mods/base-discs: the executable, the overlays, the scripts) stops the build. A step the story mod's build.sh
        makes (MOD_BUILD: maps, retouch) is made only with --recipe or when --steps or --only names it.
        --jobs N (default DERIVE_JOBS or 1): a step made of units (models' scripts, the imported_models overlays, story's
        passes, maps' and retouch's recipes, signs' passes: runner.run_units) runs them in N processes; one process
        is the reference, and strict mode and --record always run in one. --write-locks: a developer build
        (build-full.sh) appends a story's new saved names to its mod's save.lock; without it (the player's build, the
        patcher) and always with --strict the locks are only read and a new name stops the build (steps/story.py)
  python3 -m tools.derive units --out DIR [--recipe NAME] [--facts FILE | --w TREE] [--steps a,b] [--json]
        each step's units (what a worker runs: name, inputs, outputs), without making them; --json: one list
  python3 -m tools.derive unit --out DIR [--recipe NAME] [--facts FILE] --step NAME (--index N | --prepare | --finish | --build)
                               [--strict] [-v]
        a piece of a step made of units, here (what a Web Worker runs): one unit, or what the step does before its
        units (--prepare) or after them (--finish: and the step's manifest entry), or a whole step (--build, then
        --finish); a scheduler runs prepare, the units side by side, finish (one finish at a time)
  python3 -m tools.derive verify --out DIR [--sums DISC.sums]
        makes DIR's steps again in a scratch folder and compares every file with DIR's manifest (determinism); with
        --sums (tools sums.sh of a disc: "SHA-1  ./PATH") also every manifest file with that disc's
  python3 -m tools.derive recipe-env NAME --out DIR [--dev]
        the variables the story mod's build.sh hands tools/build-full.sh (EXTRA_STORY, SCREEN_CONTENT, DWS_MAPS,
        EXTRA_FILES), as shell `export` lines (recipe.py env)
  python3 -m tools.derive steps [--owned]
        the steps and their descriptions; --owned: only the owned names, one line
"""
import argparse
import contextlib
import json
import os
import shlex
import shutil
import sys
import tempfile
import time

from . import facts as F
from . import graph, manifest, recipe, runner
from . import steps as S
from . import crmath, pysum

ROOT = runner.ROOT
# the folders a step may read when the input recorder is on (the bundle's roots and the player's extracted files)
LIBS = tuple(sorted({os.path.join(p, '') for p in (sys.prefix, sys.base_prefix, sys.exec_prefix)}))
READ_ROOTS = ('tools', 'content', 'story', 'mods', 'extracted', 'decomp/config', 'text/ours', 'text/es', 'text/en.json',
              'text/es.json', 'docs/data')


def needs_usa():
    """The disc paths no other release has (needs-usa in any mods/base-discs mapping): a derived file must not read them."""
    out = set()
    for p in sorted(os.listdir(os.path.join(ROOT, 'mods', 'base-discs'))):
        if p.startswith('dw1-') and p.endswith('.json'):
            with open(os.path.join(ROOT, 'mods', 'base-discs', p)) as f:
                out |= {q for q, e in json.load(f)['files'].items() if e.get('how') == 'needs-usa'}
    return out


class Ctx:
    def __init__(self, out, facts, record=False, verbose=False, jobs=1, locks_read_only=True):
        self.root, self.out, self.facts = ROOT, os.path.abspath(out), facts
        self.jobs = jobs
        self.locks_read_only = locks_read_only   # (steps/story.py: the player's build never writes a mod's save.lock)
        self.developer = not locks_read_only      # a developer build (build-full.sh --write-locks): caches in build/
        self.env = dict(os.environ)
        self.record, self.verbose = record, verbose
        self.inputs, self.lines = set(), []

    def path(self, *p):
        return os.path.join(self.out, *p)

    def log(self, msg):
        self.lines.append(msg)
        if self.verbose:
            print(msg)

    def run(self, script, argv=(), env=None, check=True, cwd=None):
        r = runner.run_script(script, argv, env=env, cwd=cwd, record=self.record, check=check)
        self.lines.append(f'$ {script} {" ".join(map(str, argv))}  ({r.seconds:.2f} s)')
        self.lines.append(r.out.rstrip('\n'))
        if self.verbose and r.out:
            sys.stdout.write(r.out)
        if r.inputs:
            self.note_inputs(*r.inputs)
        return r

    def note_inputs(self, reads, writes=()):
        """What a script or unit read, without its own outputs (this build's folders, what it wrote itself: its scratch
        files), the interpreter's library and compiled caches."""
        mine = (self.out + os.sep, recipe.maps_out(self.out) + os.sep, *LIBS)
        self.inputs |= {p for p in reads if not p.startswith(mine) and p not in writes
                        and os.sep + '__pycache__' + os.sep not in p}

    def run_units(self, units):
        """A step's units (runner.Unit), one after another here or side by side (runner.run_units); their logs go in
        the step's log in the units' order."""
        if os.environ.get('DW_BUILD_CACHE') and not self.record and not runner.strict():
            from .cache import run_units
            done = run_units(self, units)
        else:
            done = runner.run_units(self, units)
        for d in done:
            mem = f', {d.maxrss // 1024} MB peak, in a process' if d.maxrss else ''
            self.lines.append(f'unit {d.unit.name}  ({d.seconds:.2f} s{mem})')
            if d.out:
                self.lines.append(d.out.rstrip('\n'))
                if self.verbose:
                    sys.stdout.write(d.out)
        return done

    @contextlib.contextmanager
    def calling(self):
        """Around the functions a step calls itself (not through run): with --record, what they open is its input too."""
        with runner.recorded(self.record) as rec:
            yield
        if rec:
            self.note_inputs(*rec)


def _facts(a, out, need=True):
    if getattr(a, 'facts', None):
        return F.load(a.facts)
    if getattr(a, 'w', None):
        return F.capture(os.path.abspath(a.w))
    p = os.path.join(out, 'derived', 'exe-facts.json')
    if os.path.isfile(p):
        return F.load(p)
    if need:
        raise SystemExit('derive: these steps read the executable\'s facts: --facts FILE or --w DECOMP_TREE '
                         '(derive facts makes the file)')
    return None


def _mods(a, ctx):
    mods = S.owned()
    if a.steps:
        want = a.steps.split(',')
        bad = [n for n in want if n not in S.OWNED]
        if bad:
            raise SystemExit(f'derive: not a step derive owns: {", ".join(bad)} (owned: {" ".join(S.OWNED)})')
        mods = [m for m in mods if m.NAME in want]
    elif not getattr(a, 'only', None) and not getattr(a, 'recipe', None):
        mods = [m for m in mods if not getattr(m, 'MOD_BUILD', False)]   # rule: the story mod's build.sh makes those
    if getattr(a, 'only', None):
        mods = graph.targets(ctx, a.only, mods)
    return graph.order(mods)


def build(a, out=None, quiet=False):
    out = os.path.abspath(out or a.out)
    jobs = getattr(a, 'jobs', None) or int(os.environ.get('DERIVE_JOBS') or 1)
    # rule: only a developer build writes the mods' save.lock (build-full.sh passes --write-locks); the player's path
    # (no --write-locks: the patcher; --strict: the browser's) only reads them
    _recipe_env(a, out)
    ctx = Ctx(out, None, record=a.record, verbose=a.verbose, jobs=1 if a.strict else jobs,
              locks_read_only=bool(a.strict or not getattr(a, 'write_locks', False)))
    if getattr(a, 'source_disc', None):
        from .importers.discs import extract_to
        with S.load('species').species_tools():
            for spec in a.source_disc:
                game, image = spec.split('=', 1)
                if game not in ('dcb', 'dw2', 'dw2003'):
                    raise ValueError(f'unknown source game: {game}')
                extract_to(game, image, ctx.path('source-games'))
    usa = needs_usa() if a.record else set()
    mods = _mods(a, ctx)
    ctx.facts = facts = _facts(a, out, need=any(getattr(m, 'FACTS', False) for m in mods))
    if a.strict:
        runner.set_strict(True)
    # rule: every derived byte is made with correctly rounded sin, cos, atan2 ... (crmath.py): the C libraries' differ
    # in the last bit between machines (glibc, Pyodide's musl), and a model script's keyframes with them; and with
    # 3.12's sum() of floats (pysum.py): 3.10 and 3.11 add without compensation, and the colour searches pick by it
    crmath.install(); pysum.install()
    os.makedirs(ctx.path('derived', 'logs'), exist_ok=True)
    m = manifest.load(out)
    if facts is not None:
        m['facts'] = facts
    total = time.perf_counter()
    for mod in mods:
        ctx.lines, ctx.inputs = [], set()
        t0 = time.perf_counter()
        try:
            with ctx.calling():      # (with --record: what the step's own code opens, besides its scripts and units)
                if os.environ.get('DW_BUILD_CACHE') and not a.strict:
                    from .cache import build_step
                    build_step(ctx, mod)
                else:
                    mod.build(ctx)
            if a.checks and hasattr(mod, 'check'):
                mod.check(ctx)
        except runner.StepError as e:
            raise SystemExit(f'derive: step {mod.NAME} failed: {e}')
        finally:
            with open(ctx.path('derived', 'logs', f'{mod.NAME}.log'), 'w') as f:
                f.write('\n'.join(ctx.lines) + '\n')
        secs = time.perf_counter() - t0
        inputs = None
        if a.record:
            inputs = sorted(os.path.relpath(p, ROOT) if p.startswith(ROOT + os.sep) else p for p in ctx.inputs)
            outside = [p for p in inputs if os.path.isabs(p) or not p.startswith(READ_ROOTS)]
            if outside:
                print(f'note: step {mod.NAME} read {len(outside)} files outside the bundle roots: {", ".join(outside[:5])}')
            # rule: no derived byte may come from a file only the USA disc has (the package serves every release)
            bad = [p for p in inputs if p.startswith('extracted/') and p[len('extracted/'):] in usa]
            if bad:
                raise SystemExit(f'derive: step {mod.NAME} read {", ".join(bad)}: needs-usa files (mods/base-discs), '
                                 'which no other release has')
        outs = mod.outputs(ctx)
        manifest.record(m, out, mod, outs, secs, inputs)
        if hasattr(mod, 'manifest_plan'):
            m['plan'] = mod.manifest_plan(ctx)
        if not quiet:
            print(f'derive {mod.NAME}: {len(outs)} files, {secs:.2f} s')
    manifest.save(m, out)
    if not quiet:
        print(f'derive: {time.perf_counter() - total:.2f} s, {manifest.path(out)}')
    runner.set_strict(False)
    crmath.uninstall(); crmath.clear(); pysum.uninstall()
    return m


def _recipe_env(a, out):
    if getattr(a, 'recipe', None):   # a player's build: the recipe's settings, not the machine's
        env = recipe.environment(recipe.load(a.recipe), out)
        os.environ.clear(); os.environ.update(env)


def units(a):
    """Each step's units (runner.Unit): what a worker would run, without running it (--json: one list for a scheduler,
    each unit with its step, index, name, inputs and outputs; a step without units is one entry with index None)."""
    out = os.path.abspath(a.out)
    _recipe_env(a, out)
    ctx = Ctx(out, None, locks_read_only=not a.write_locks)
    names = a.steps.split(',') if a.steps else list(S.OWNED)
    mods = [S.load(n) for n in names]
    ctx.facts = _facts(a, out, need=any(getattr(m, 'FACTS', False) for m in mods))
    rows = []
    for mod in mods:
        if not hasattr(mod, 'units'):
            rows.append({'step': mod.NAME, 'index': None, 'name': mod.NAME, 'after': list(mod.AFTER)})
            if not a.json:
                print(f'{mod.NAME}: one unit (the step)')
            continue
        try:
            us = mod.units(ctx)
        except SystemExit as e:
            rows.append({'step': mod.NAME, 'index': None, 'name': mod.NAME, 'after': list(mod.AFTER), 'unknown': str(e)})
            if not a.json:
                print(f'{mod.NAME}: units not known yet ({e})')
            continue
        rows += [{'step': mod.NAME, 'index': i, 'name': u.name, 'after': list(mod.AFTER), 'inputs': u.inputs,
                  'outputs': u.outputs, 'order_group': u.order_group} for i, u in enumerate(us)]
        if not a.json:
            print(f'{mod.NAME}: {len(us)} units')
            for u in us:
                print(f'  {u.name}\n    reads  {" ".join(u.inputs)}\n    writes {" ".join(u.outputs)}')
                if u.order_group is not None:
                    print(f'    ordered with  {u.order_group}')
    if a.json:
        json.dump(rows, sys.stdout, indent=1)
        print()


def unit(a):
    """A piece of a step made of units, here (what a Web Worker runs): --index N its units(ctx)[N]; --prepare what the
    step does before its units (the maps' folder and screen files, the spawn audit), --finish what it does after them
    (the story's maps by disc path) and the step's entry in the manifest; --build a whole step without the manifest
    (its --finish records it). A scheduler runs prepare, the units side by side (each after what its inputs name), then
    finish; a step without units --build then --finish. Only finish writes the manifest: one at a time."""
    out = os.path.abspath(a.out)
    _recipe_env(a, out)
    ctx = Ctx(out, None)
    mod = S.load(a.step)
    ctx.facts = _facts(a, out, need=getattr(mod, 'FACTS', False))
    if a.strict:
        runner.set_strict(True)
    crmath.install(); pysum.install()
    t0 = time.perf_counter()
    try:
        if a.prepare or a.finish or a.build:
            what = 'prepare' if a.prepare else 'finish' if a.finish else 'build'
            part = getattr(mod, what, None)
            if part and not (a.finish and not hasattr(mod, 'units')):   # (a whole step's finish only records it)
                with ctx.calling():
                    part(ctx)
            log = '\n'.join(ctx.lines)
        else:
            u = mod.units(ctx)[a.index]
            what = f'{a.index} {u.name}'
            log = u.fn(*u.args)
    finally:
        runner.set_strict(False)
        crmath.uninstall(); crmath.clear(); pysum.uninstall()
    secs = time.perf_counter() - t0
    if a.finish:
        m = manifest.load(out)
        if ctx.facts is not None:
            m['facts'] = ctx.facts
        manifest.record(m, out, mod, mod.outputs(ctx), secs, None)
        if hasattr(mod, 'manifest_plan'):
            m['plan'] = mod.manifest_plan(ctx)
        manifest.save(m, out)
    if a.verbose and log:
        sys.stdout.write(log if log.endswith('\n') else log + '\n')
    print(f'unit {a.step} {what}: {secs:.2f} s')


def verify(a):
    ref = manifest.load(os.path.abspath(a.out))
    if not ref['steps']:
        raise SystemExit(f'derive: {manifest.path(a.out)} lists no step')
    bad = 0
    if a.sums:
        disc = {}
        for line in open(a.sums):
            h, p = line.split(None, 1)
            disc[p.strip().removeprefix('./')] = h
        for d, e in ref['files'].items():
            if disc.get(d) != e['sha1']:
                bad += 1
                print(f'differs from the disc: {d} ({e["step"]}) {e["sha1"]} vs {disc.get(d, "missing")}')
        print(f'{len(ref["files"])} files against {a.sums}: {bad} differ')
    with tempfile.TemporaryDirectory(prefix='derive-verify-', dir=os.path.join(ROOT, 'build')) as t:
        f = None
        if ref.get('facts'):
            f = os.path.join(t, 'derived', 'exe-facts.json')
            F.save(ref['facts'], f)
        b = argparse.Namespace(facts=f, w=None, steps=','.join(ref['steps']), only=None, checks=False,
                               strict=a.strict, record=False, verbose=False, jobs=1)
        os.environ.pop('REUSE_MODELS', None)
        again = build(b, t, quiet=True)
        n = 0
        for d, e in ref['files'].items():
            g = again['files'].get(d)
            if not g or g['sha1'] != e['sha1']:
                n += 1
                print(f'not the same twice: {d} ({e["step"]})')
        print(f'{len(ref["files"])} files made again: {n} differ')
    if bad or n:
        sys.exit(1)


def main():
    p = argparse.ArgumentParser(prog='python3 -m tools.derive', description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = p.add_subparsers(dest='cmd', required=True)
    f = sub.add_parser('facts')
    f.add_argument('--w', required=True)
    f.add_argument('-o')
    f.add_argument('--out')
    f.add_argument('--heap-map', help='the ELF map of the heap check (default: the tree\'s; DW_HEAP_MAP)')
    b = sub.add_parser('build')
    b.add_argument('--out', required=True)
    b.add_argument('--recipe')
    b.add_argument('--source-disc', action='append', metavar='GAME=IMAGE',
                   help='source image: dcb, dw2 or dw2003; may be repeated')
    b.add_argument('--facts'); b.add_argument('--w')
    b.add_argument('--steps')
    b.add_argument('--only', nargs='+', metavar='DISC_PATH')
    b.add_argument('--checks', action='store_true')
    b.add_argument('--strict', action='store_true')
    b.add_argument('--record', action='store_true')
    b.add_argument('-v', '--verbose', action='store_true')
    b.add_argument('--jobs', type=int)
    b.add_argument('--write-locks', action='store_true')
    x = sub.add_parser('sources', help='extract and check the source games, without building models')
    x.add_argument('--out', required=True)
    x.add_argument('--source-disc', action='append', required=True, metavar='GAME=IMAGE')
    v = sub.add_parser('verify')
    v.add_argument('--out', required=True)
    v.add_argument('--sums')
    v.add_argument('--strict', action='store_true')
    u = sub.add_parser('units')
    u.add_argument('--out', required=True)
    u.add_argument('--facts'); u.add_argument('--w')
    u.add_argument('--steps')
    u.add_argument('--write-locks', action='store_true')
    u.add_argument('--recipe')
    u.add_argument('--json', action='store_true')
    n = sub.add_parser('unit')
    n.add_argument('--out', required=True)
    n.add_argument('--recipe')
    n.add_argument('--facts'); n.add_argument('--w')
    n.add_argument('--step', required=True)
    g = n.add_mutually_exclusive_group(required=True)
    g.add_argument('--index', type=int)
    g.add_argument('--prepare', action='store_true')
    g.add_argument('--finish', action='store_true')
    g.add_argument('--build', action='store_true')
    n.add_argument('--strict', action='store_true')
    n.add_argument('-v', '--verbose', action='store_true')
    r = sub.add_parser('recipe-env')
    r.add_argument('name')
    r.add_argument('--out', required=True)
    r.add_argument('--dev', action='store_true')
    s = sub.add_parser('steps')
    s.add_argument('--owned', action='store_true')
    a = p.parse_args()
    os.chdir(ROOT)
    if a.cmd == 'facts':
        o = a.o or (os.path.join(a.out, 'derived', 'exe-facts.json') if a.out else None)
        hm = a.heap_map or os.environ.get('DW_HEAP_MAP')
        facts = F.capture(os.path.abspath(a.w), hm)
        if o: F.save(facts, o)
        else: json.dump(facts, sys.stdout, indent=1, sort_keys=True); print()
    elif a.cmd == 'build':
        build(a)
    elif a.cmd == 'sources':
        from .importers.discs import extract_to
        with S.load('species').species_tools():
            for source in a.source_disc:
                game, image = source.split('=', 1)
                if game not in ('dcb', 'dw2', 'dw2003'):
                    raise ValueError(f'unknown source game: {game}')
                print(game, extract_to(game, image, a.out), 'files verified')
    elif a.cmd == 'units':
        units(a)
    elif a.cmd == 'unit':
        unit(a)
    elif a.cmd == 'verify':
        verify(a)
    elif a.cmd == 'recipe-env':
        for k, v in recipe.env(recipe.load(a.name), a.out, a.dev).items():
            print(f'export {k}={shlex.quote(v)}')
    elif a.cmd == 'steps':
        if a.owned:
            print(' '.join(S.OWNED))
            return
        for name in S.ALL:
            m = S.load(name)
            print(f'{name:16} {m.DESCRIPTION}')


if __name__ == '__main__':
    main()
