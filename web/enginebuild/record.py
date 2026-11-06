"""Record the derive graph with bounded, isolated unit workers.

Prepare and finish barriers follow recipe order. Independent units run against
private copies of the prepared tree, then merge in canonical order. Every unit
imports repository modules afresh, including their input reads. Conflicting
writes or sibling dependencies fail the recording; there is no fallback.

The graph uses stable temporary names and estimates. Measured times, RSS and
per-worker diagnostics stay outside it. --sequential supplies the same protocol
with one worker for focused debugging and byte comparisons.
"""
import argparse
import contextlib
import hashlib
import io
import json
import os
import sys
import time
import tempfile
import traceback
from pathlib import Path

import record_parallel as parallel

TREE = os.path.abspath(sys.argv[1])
OUT = os.path.abspath(sys.argv[2])
sys.path.insert(0, TREE)
os.chdir(TREE)
os.environ['PYTHONDONTWRITEBYTECODE'] = '1'
sys.dont_write_bytecode = True

REC = None          # while a job runs: {'reads': set, 'lists': set, 'stats': set} of absolute paths
IMPORT_MODULES = ('_frozen_importlib', '_frozen_importlib_external', 'importlib._bootstrap',
                  'importlib._bootstrap_external', 'zipimport')


def _abs(p):
    if isinstance(p, bytes):
        p = os.fsdecode(p)
    return os.path.abspath(p)


def _hook(ev, args):
    if REC is None:
        return
    if ev == 'open':
        p, mode, flags = args[0], args[1], args[2]
        if not isinstance(p, (str, bytes)):
            return
        if isinstance(mode, str) and mode:
            w = any(c in mode for c in 'wax+')
        else:
            w = isinstance(flags, int) and bool(flags & (os.O_WRONLY | os.O_RDWR | os.O_CREAT | os.O_APPEND | os.O_TRUNC))
        REC['writes' if w else 'reads'].add(_abs(p))
    elif ev == 'os.rename':
        REC['writes'].add(_abs(args[1]))
    elif ev in ('os.listdir', 'os.scandir'):
        p = args[0]
        if isinstance(p, int):
            return
        f = sys._getframe(1)
        while f is not None:                 # the import system's directory caches are not the job's listings
            if f.f_globals.get('__name__') in IMPORT_MODULES:
                return
            f = f.f_back
        REC['lists'].add(_abs('.' if p is None else p))


sys.addaudithook(_hook)
_stat, _lstat = os.stat, os.lstat


def _wrap(fn):
    def stat(p, *a, **k):
        if REC is not None and not isinstance(p, int) and k.get('dir_fd') is None:
            try:
                REC['stats'].add(_abs(os.fspath(p)))
            except TypeError:
                pass
        return fn(p, *a, **k)
    return stat


os.stat, os.lstat = _wrap(_stat), _wrap(_lstat)


def snapshot():
    """{relative path: (size, mtime_ns)} of every file of the tree."""
    out = {}
    for dp, dns, fns in os.walk(TREE):
        dns[:] = [d for d in dns if d != '__pycache__']
        for f in fns:
            p = os.path.join(dp, f)
            st = _lstat(p)
            out[os.path.relpath(p, TREE)] = (st.st_size, st.st_mtime_ns, st.st_mode)
    return out


def sha1(rel):
    h = hashlib.sha1()
    with open(os.path.join(TREE, rel), 'rb') as f:
        for b in iter(lambda: f.read(1 << 20), b''):
            h.update(b)
    return h.hexdigest()


def forget_modules():
    for name, m in list(sys.modules.items()):
        f = getattr(m, '__file__', None)
        if f and os.path.abspath(f).startswith(TREE + os.sep):
            del sys.modules[name]


def rel_in_tree(paths):
    out = set()
    for p in paths:
        if p.startswith(TREE + os.sep) and os.sep + '__pycache__' + os.sep not in p:
            out.add(os.path.relpath(p, TREE))
    return out


def run(argv):
    """tools.derive's command line here, as a worker runs it -> (exit code, output, seconds, record)."""
    global REC
    buf = io.StringIO()
    code = 0
    saved_env = dict(os.environ)
    REC = {'reads': set(), 'writes': set(), 'lists': set(), 'stats': set()}
    t0 = time.perf_counter()
    sys.argv = ['tools.derive'] + argv
    try:
        with contextlib.redirect_stdout(buf), contextlib.redirect_stderr(buf):
            try:
                forget_modules()
                from tools.derive import __main__ as D
                D.main()
            except SystemExit as e:
                code = e.code or 0
            except Exception:
                code = 'exception'
                traceback.print_exc()
    finally:
        rec, REC = REC, None
        os.chdir(TREE)
        os.environ.clear(); os.environ.update(saved_env)
    return code, buf.getvalue(), time.perf_counter() - t0, rec


def execute(spec):
    before = snapshot()
    before_dirs = {os.path.relpath(p, TREE) for p, _, _ in os.walk(TREE)}
    # Deterministic private temporary names keep graph paths stable. Creation
    # still uses tempfile's exclusive filesystem operations.
    tempfile.gettempdir()  # initialize its process-local probe before the deterministic sequence
    candidate_names = tempfile._get_candidate_names
    seed = int(hashlib.sha256(spec['name'].encode()).hexdigest()[:6], 16) << 8
    names = (f'{(seed + i) % 2**32:08x}' for i in range(2**24))
    tempfile._get_candidate_names = lambda: names
    try:
        code, text, secs, rec = run([a.replace('{ROOT}', TREE) for a in spec['argv']])
    finally:
        tempfile._get_candidate_names = candidate_names
    now = snapshot()
    changed = sorted({p for p, v in now.items() if before.get(p) != v}
                     | (rel_in_tree(rec['writes']) & now.keys()))
    removed = sorted(p for p in before if p not in now)
    listed = {}
    for d in sorted(rel_in_tree(rec['lists'])):
        prefix = d + os.sep
        children = {p[len(prefix):].split(os.sep, 1)[0] for p in before if p.startswith(prefix)}
        if children or d in before_dirs:
            listed[d] = sorted(children)
    job = dict(spec, seconds=parallel.estimate(spec), code=str(code),
               reads=sorted(rel_in_tree(rec['reads'])), stats=sorted(rel_in_tree(rec['stats'])),
               lists=listed, writes={p: sha1(p) for p in changed}, removes=removed)
    candidates = set(job['reads']) | set(job['stats']) | {os.path.join(d, f) for d, fs in listed.items() for f in fs}
    job['existed'] = sorted(p for p in candidates if p in before)
    job['absent'] = sorted(p for p in rel_in_tree(rec['stats']) if p not in before and p not in before_dirs)
    logs = Path(os.environ['RECORD_LOGS'])
    logs.mkdir(parents=True, exist_ok=True)
    log = logs / (f"{spec['step']}-{spec['part']}-{spec['index']}.log")
    log.write_text(text)
    timing = dict(name=spec['name'], seconds=round(secs, 3), log=str(log), code=str(code))
    print(f"{spec['name']}: {secs:.2f} s, exit {code}; {log}", flush=True)
    return dict(graph=job, timing=timing, log=str(log))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('tree')
    ap.add_argument('out')
    ap.add_argument('--jobs', type=int, default=8)
    ap.add_argument('--worker-memory-mib', type=int, default=3072)
    ap.add_argument('--logs')
    ap.add_argument('--unit-batch')
    ap.add_argument('--sequential', action='store_true', help='debugging reference; never an automatic fallback')
    a = ap.parse_args()
    if a.jobs < 1 or a.worker_memory_mib < 1:
        ap.error('jobs and worker memory must be positive')
    if a.unit_batch:
        parallel.batch(a.unit_batch, execute)
        return
    os.environ['RECORD_LOGS'] = str(Path(a.logs or (OUT + '.logs')).resolve())
    logs = Path(os.environ['RECORD_LOGS'])
    logs.mkdir(parents=True, exist_ok=True)
    base = ['--recipe', 'everything', '--out', '{ROOT}/build/everything', '--facts', 'exe-facts.json']
    forget_modules()
    from tools.derive import steps as S, graph
    order = [m.NAME for m in graph.order(S.owned())]
    after = {n: list(S.load(n).AFTER) for n in order}
    unit_steps = {n for n in order if hasattr(S.load(n), 'units')}
    jobs, timings = [], []
    started = time.perf_counter()

    def spec(step, part, argv, index=None, name=None):
        return dict(step=step, part=part, argv=argv, index=index, name=name or f'{step} {part}')

    def add(result):
        jobs.append(result['graph'])
        timings.append(result['timing'])
        (logs / 'timings.json').write_text(json.dumps(dict(seconds=time.perf_counter()-started, jobs=timings), indent=2))
        if result['graph']['code'] not in ('0', 'None'):
            raise RuntimeError(f"recording failed: {result['graph']['name']}; see {result['log']}")
        return Path(result['log']).read_text()

    for step in order:
        args = ['unit', *base, '--step', step]
        if step in unit_steps:
            add(execute(spec(step, 'prepare', args + ['--prepare', '--strict'])))
            text = add(execute(spec(step, 'units', ['units', *base, '--steps', step, '--json'])))
            found = json.loads(text[text.index('['):])
            specs = [spec(step, 'unit', args + ['--index', str(u['index']), '--strict'], u['index'],
                          f"{step} {u['index']} {u['name']}") for u in found]
            if specs:
                for result in parallel.units(Path(TREE), specs, Path(OUT + '.workers'),
                                              1 if a.sequential else a.jobs, a.worker_memory_mib):
                    add(result)
        else:
            add(execute(spec(step, 'build', args + ['--build', '--strict'])))
        add(execute(spec(step, 'finish', args + ['--finish', '--strict'])))
    with open(os.path.join(TREE, 'build/everything/derived/manifest.json')) as file:
        manifest = json.load(file)
    record = dict(tree='{ROOT}', order=order, after=after, units=sorted(unit_steps), jobs=jobs,
                  manifest_files={d: e['file'].replace(TREE, '{ROOT}') for d, e in manifest['files'].items()})
    Path(OUT).write_text(parallel.graph_record(record))
    print(f'record: {len(jobs)} jobs, {time.perf_counter() - started:.0f} s', flush=True)


if __name__ == '__main__':
    main()
