"""record.py TREE OUT.json: runs the everything build in TREE the way the web engine's workers run it (one job after
another in this one process: tools.derive's `unit` command, strict) and records, per job, what it opened, listed and
looked at (stat) and what it changed in the tree. build_engine.py turns that into each job's inputs (the files a worker
must have before the job starts) and the jobs' order (who wrote what the job reads).

TREE is a release's bundle with extracted/ written from the player's disc (build_engine.py makes it). The jobs:
  for each step in derive's order: a step made of units: prepare, the units (`derive units --json` asked once the step
  before it is done, as the engine does), finish; any other step: build, finish.

Every repository module is forgotten before each job (a worker that never ran the job before imports it afresh: what
a module opens when it is imported is that job's input too). Paths are relative to TREE; reads outside it (the
interpreter's library, temporary files) are left out.
"""
import contextlib
import hashlib
import io
import json
import os
import sys
import time

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
        if not w:
            REC['reads'].add(_abs(p))
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
            out[os.path.relpath(p, TREE)] = (st.st_size, st.st_mtime_ns)
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
    forget_modules()
    from tools.derive import __main__ as D        # noqa: (afresh: forget_modules)
    buf = io.StringIO()
    code = 0
    saved_env = dict(os.environ)
    REC = {'reads': set(), 'lists': set(), 'stats': set()}
    t0 = time.perf_counter()
    sys.argv = ['tools.derive'] + argv
    try:
        with contextlib.redirect_stdout(buf), contextlib.redirect_stderr(buf):
            try:
                D.main()
            except SystemExit as e:
                code = e.code or 0
    finally:
        rec, REC = REC, None
        os.chdir(TREE)
        os.environ.clear(); os.environ.update(saved_env)
    return code, buf.getvalue(), time.perf_counter() - t0, rec


def main():
    out_dir = os.path.join(TREE, 'build', 'everything')
    base = ['--recipe', 'everything', '--out', out_dir, '--facts', 'exe-facts.json']
    forget_modules()
    from tools.derive import steps as S, graph
    order = [m.NAME for m in graph.order(S.owned())]
    after = {n: list(S.load(n).AFTER) for n in order}
    unit_steps = {n for n in order if hasattr(S.load(n), 'units')}
    jobs = []
    before = snapshot()
    t_all = time.perf_counter()

    def job(step, part, argv, index=None, name=None):
        nonlocal before
        code, text, secs, rec = run(argv)
        now = snapshot()
        changed = sorted(p for p, v in now.items() if before.get(p) != v)
        removed = sorted(p for p in before if p not in now)
        listed = {}                       # each listed folder as it was before the job: its files and folders
        for d in sorted(rel_in_tree(rec['lists'])):
            pre = d + os.sep
            names = {p[len(pre):].split(os.sep, 1)[0] for p in before if p.startswith(pre)}
            if names or os.path.isdir(os.path.join(TREE, d)):
                listed[d] = sorted(names)
        j = dict(step=step, part=part, index=index, name=name or f'{step} {part}', argv=argv, seconds=round(secs, 2),
                 code=str(code), reads=sorted(rel_in_tree(rec['reads'])), stats=sorted(rel_in_tree(rec['stats'])),
                 lists=listed, existed=None, writes={p: sha1(p) for p in changed}, removes=removed)
        # what existed before the job (a read of a file the job made itself is not an input)
        cand = set(j['reads']) | set(j['stats']) | {os.path.join(d, f) for d, fs in listed.items() for f in fs}
        j['existed'] = sorted(p for p in cand if p in before)
        # looked at but not there before the job (a worker must not have them either)
        dirs = set()
        for p in before:
            while p:
                p = os.path.dirname(p)
                if p in dirs: break
                dirs.add(p)
        j['absent'] = sorted(p for p in rel_in_tree(rec['stats']) if p not in before and p not in dirs)
        jobs.append(j)
        before = now
        print(f'{time.perf_counter() - t_all:7.1f} s  {j["name"]}: {secs:.1f} s, exit {code}, {len(j["existed"])} inputs, '
              f'{len(changed)} written, {len(removed)} removed', flush=True)
        if j['code'] not in ('0', 'None'):
            print(text[-4000:])
            raise SystemExit(f'record: {j["name"]} failed')
        return text

    for s in order:
        if s in unit_steps:
            job(s, 'prepare', ['unit', *base, '--step', s, '--prepare', '--strict'])
            text = job(s, 'units', ['units', *base, '--steps', s, '--json'])
            units = json.loads(text[text.index('['):])
            for u in units:
                job(s, 'unit', ['unit', *base, '--step', s, '--index', str(u['index']), '--strict'], u['index'],
                    f'{s} {u["index"]} {u["name"]}')
        else:
            job(s, 'build', ['unit', *base, '--step', s, '--build', '--strict'])
        job(s, 'finish', ['unit', *base, '--step', s, '--finish', '--strict'])
    with open(os.path.join(out_dir, 'derived', 'manifest.json')) as f:
        man = json.load(f)
    json.dump({'tree': TREE, 'order': order, 'after': after, 'units': sorted(unit_steps), 'jobs': jobs,
               'manifest_files': {d: e['file'] for d, e in man['files'].items()},
               'seconds': round(time.perf_counter() - t_all, 1)}, open(OUT, 'w'), indent=0)
    print(f'record: {len(jobs)} jobs, {time.perf_counter() - t_all:.0f} s')


if __name__ == '__main__':
    main()
