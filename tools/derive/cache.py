"""Opt-in native driver cache. The browser/player and releases remain uncached.

Only the native dev driver sets DW_BUILD_CACHE. Preparation, finish, manifests and
checks still run. Shared story writes are published in their original order.
"""
import functools
import os
from pathlib import Path
import sys

from tools.build_cache import Cache, digest, key
from . import runner


@functools.lru_cache(maxsize=1)
def tool_key():
    root = Path(runner.ROOT)
    # Modules imported before recording are still code inputs. Conservatively hash
    # all tool sources, including transitive helpers, rather than infer imports.
    paths = [p for p in (root / 'tools').rglob('*') if p.is_file()
             and '__pycache__' not in p.parts and p.suffix in ('.py', '.sh', '.json', '.lua')]
    paths += [p for p in (root / 'content').rglob('*.py') if '__pycache__' not in p.parts]
    return key([[str(p.relative_to(root)), digest(p)] for p in sorted(paths)])


@functools.lru_cache(maxsize=256)
def declared_code(inputs):
    paths = set()
    for name in inputs:
        if name.startswith('step:'):
            continue
        p = Path(runner.ROOT) / name
        if p.is_file() and p.suffix in ('.py', '.sh', '.lua'):
            paths.add(p)
    return key([[str(p), digest(p)] for p in sorted(paths)])


@functools.lru_cache(maxsize=1)
def runtime_sources():
    # Import history depends on which previous steps hit the cache. Fingerprint
    # the interpreter installation, not the currently-loaded module set.
    import sysconfig
    root = Path(runner.ROOT)
    paths = {Path(sys.executable).resolve()}
    directories = {Path(sysconfig.get_path('stdlib')).resolve()}
    for value in sys.path:
        if not value:
            continue
        p = Path(value).resolve()
        if p.is_file() and not p.is_relative_to(root):
            paths.add(p)
        elif p.is_dir() and (not p.is_relative_to(root) or '.venv' in p.parts):
            directories.add(p)
    # Avoid walking a nested installation root twice.
    bases = [p for p in directories if not any(p != q and p.is_relative_to(q) for q in directories)]
    for base in bases:
        paths.update(p for p in base.rglob('*') if p.is_file() and '__pycache__' not in p.parts
                     and p.suffix in ('.py', '.so', '.pyd', '.zip'))
    return key([[str(p), digest(p)] for p in sorted(paths)])


def identity(ctx, name, args=()):
    # Job count and cache location cannot change output bytes; everything else in
    # the recipe/environment remains part of the key, even unknown future flags.
    ignored = {'DW_BUILD_CACHE', 'DW_CACHE_DIR', 'DERIVE_JOBS', 'DERIVE_ARGS', 'DERIVE_START',
               'DERIVE_UNIT_ORDER', 'DW_CACHE_DEBUG', 'CODEX_TOOL_CALL_ID', '_', 'SHLVL'}
    return dict(kind='derive', name=name, args=args, out=ctx.out, tools=tool_key(),
                python=[sys.version, sys.executable, sys.platform, runtime_sources()],
                environment={k: v for k, v in ctx.env.items() if k not in ignored},
                facts=ctx.facts if getattr(ctx, 'cache_facts', False) else None,
                read_only=ctx.locks_read_only)


def run_unit(cache_dir, writable, ident, fn, args):
    cache = Cache(cache_dir, writable)
    result, hit = cache.call(ident, lambda: {'log': fn(*args)})
    return ('cache hit\n' if hit else 'cache miss\n') + (result['log'] or '')


def screen_piece(fn, args, stage, code_inputs=None):
    """Cache one compiled screen record; preserve its dependencies in the archive cache.

    Parsed screen data, script text and assembler options are explicit arguments.
    Any additional file reads are captured, including when the surrounding archive
    is rebuilt using a previously cached record.
    """
    from types import SimpleNamespace
    from tools import build_cache
    ctx = SimpleNamespace(out=str(stage), env=dict(os.environ), cache_facts=False,
                          locks_read_only=True)
    ident = identity(ctx, f'screen/{args[0]}', [fn.__module__, fn.__name__, args, code_inputs])
    path = Path(stage) / key(ident) / 'record.bin'
    cache = Cache(os.environ['DW_BUILD_CACHE'], Path(runner.ROOT) / 'build')
    parent = build_cache._ACTIVE
    # The child owns its capture and cache I/O; the parent inherits its actual
    # dependencies and output, rather than depending on cache-index files.
    build_cache._ACTIVE = None
    try:
        def compile_record():
            data, size = fn(*args)
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(data)
            return {'size': size}
        result, _ = cache.call(ident, compile_record)
    finally:
        build_cache._ACTIVE = parent
    if parent is not None:
        parent.unsafe |= cache.last_unsafe
        for (p, kind), value in cache.last_inputs.items():
            if p not in parent.dirty:
                parent.dependencies.setdefault((p, kind), value)
        # As in the audit callback, bookkeeping must not record its own directory
        # probes: these are generated namespaces, removed before the next build.
        busy = parent.busy
        parent.busy = True
        try:
            parent.write(path)
        finally:
            parent.busy = busy
    return path.read_bytes(), result['size']


def units(ctx, original):
    directory = os.environ.get('DW_BUILD_CACHE')
    if not directory or runner.strict() or ctx.record:
        return original
    out = []
    for u in original:
        fn, args, group = u.fn, u.args, u.order_group
        if ctx.cache_step == 'story' and fn.__name__ == 'run_pass':
            roots = story_roots(u, Path(ctx.root) / 'build')
            folder = str(Path(ctx.out) / 'cache-story' / str(len(out)))
            fn, args, group = isolated_story, (fn, args, folder, roots), None
        ident = identity(ctx, f'{ctx.cache_step}/{u.name}',
                         [u.fn.__module__, u.fn.__name__, u.args, declared_code(tuple(u.inputs))])
        out.append(runner.Unit(u.name, run_unit,
                              (directory, os.path.join(ctx.root, 'build'), ident, fn, args),
                              u.inputs, u.outputs, order_group=group))
    return out


def build_step(ctx, mod):
    ctx.cache_step = mod.NAME
    ctx.cache_facts = getattr(mod, 'FACTS', False)
    directory = os.environ.get('DW_BUILD_CACHE')
    if not directory or runner.strict() or ctx.record or hasattr(mod, 'units') or mod.NAME == 'plan':
        mod.build(ctx)
        return
    # A plan records output names from multiple steps and is inexpensive. Always
    # regenerate it; the ordinary manifest gate rehashes every disc-bound output.
    def build():
        mod.build(ctx)
        return {'lines': ctx.lines[:]}
    result, hit = Cache(directory, os.path.join(ctx.root, 'build')).call(identity(ctx, mod.NAME), build)
    if hit:
        ctx.lines[:] = ['cache hit'] + result['lines']
    else:
        ctx.lines.insert(0, 'cache miss')


def isolated_story(fn, args, folder, roots):
    """Compute against private recipe maps; publish shared writes later in pass order.

    Every story pass already starts from .MAP.orig. The expensive compilation can
    overlap when each pass sees its own recipe maps. Only the final publication of
    actual map writes needs the runner's recorded order.
    """
    import json
    import shutil
    from tools import build_cache
    folder = Path(folder)
    folder.mkdir(parents=True, exist_ok=True)
    replacements = {}
    for i, original in enumerate(roots):
        private = folder / str(i)
        shutil.rmtree(private, ignore_errors=True)
        shutil.copytree(original, private)
        replacements[original] = str(private)
    args = list(args)
    argv = list(args[2])
    for flag in ('--screen-content', '--maps'):
        i = argv.index(flag) + 1
        argv[i] = os.pathsep.join(replacements.get(str(Path(p).absolute()), p) if p else p
                           for p in argv[i].split(os.pathsep))
    if folder.name != '0' and '--read-only-locks' not in argv:
        argv.append('--read-only-locks')
    args[2] = argv
    active = build_cache._ACTIVE
    before = active.writes.copy()
    active.writes.clear()
    old_run_root = os.environ.get('DWS_RUN_ROOT')
    os.environ['DWS_RUN_ROOT'] = str(folder / 'runs')
    (folder / 'runs').mkdir(exist_ok=True)
    try:
        log = fn(*args)
    finally:
        if old_run_root is None:
            os.environ.pop('DWS_RUN_ROOT', None)
        else:
            os.environ['DWS_RUN_ROOT'] = old_run_root
        actual = active.writes.copy()
        active.writes.update(before)
    replay = []
    for original, private in replacements.items():
        for path in sorted(actual):
            p = Path(path)
            if p.is_relative_to(private) and p.is_file():
                replay.append([str(Path(original) / p.relative_to(private)), str(p)])
    (folder / 'replay.json').write_text(json.dumps(replay))
    return log


def story_roots(unit, writable):
    argv = unit.args[2]
    paths = []
    for flag in ('--screen-content', '--maps'):
        for value in argv[argv.index(flag)+1].split(os.pathsep):
            if value and Path(value).absolute().is_relative_to(writable):
                paths.append(str(Path(value).absolute()))
    return sorted(set(paths))


def replay_story(ctx, done):
    if not os.environ.get('DW_BUILD_CACHE') or ctx.cache_step != 'story' or ctx.record or runner.strict():
        return
    import json
    import shutil
    for i, _ in enumerate(done):
        manifest = Path(ctx.out) / 'cache-story' / str(i) / 'replay.json'
        if manifest.exists():
            for dst, src in json.loads(manifest.read_text()):
                # Cache metadata is validated, and this small replay manifest must
                # also stay within this checkout's generated build files.
                for p in (Path(dst), Path(src)):
                    if not p.is_absolute() or '..' in p.parts or not p.is_relative_to(Path(ctx.root) / 'build'):
                        raise runner.StepError('story cache replay outside build directory')
                Path(dst).parent.mkdir(parents=True, exist_ok=True)
                shutil.copyfile(src, dst)


def run_units(ctx, original):
    wrapped = units(ctx, original)
    if (os.environ.get('DW_BUILD_CACHE') and ctx.cache_step == 'story' and wrapped
            and not ctx.record and not runner.strict()):
        # The first extended English pass allocates any new saved names. All
        # followers read those locks and compute on independent recipe maps.
        done = runner.run_units(ctx, wrapped[:1])
        done += runner.run_units(ctx, wrapped[1:])
    else:
        done = runner.run_units(ctx, wrapped)
    replay_story(ctx, done)
    return done
