"""Isolated recorder workers and deterministic graph serialization (stdlib only)."""
from concurrent.futures import ThreadPoolExecutor, as_completed
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import shutil
import stat
import subprocess
import sys
import threading
import time

import record_groups

# Stable estimates, independent of scheduling and machine load. Actual durations
# belong in the private timings sidecar, never in the recorded dependency graph.
ESTIMATES = {'imports': 6, 'maps': 12, 'models': 8, 'retouch': 5,
             'story': 70, 'signs': 510, 'screens': 75, 'localize': 100}


def estimate(spec):
    if spec['part'] in ('prepare', 'units', 'finish'):
        return 1
    if spec['step'] == 'signs' and '/' in spec['name']:
        return 64
    if spec['step'] == 'story' and 'base' in spec['name']:
        return 20
    return ESTIMATES.get(spec['step'], 5)


def inventory(tree, hashes=False):
    files, dirs = {}, {}
    for parent, names, leaves in os.walk(tree):
        names[:] = sorted(n for n in names if n != '__pycache__')
        dirs[os.path.relpath(parent, tree)] = stat.S_IMODE(os.stat(parent).st_mode)
        for name in names + leaves:
            path = Path(parent) / name
            if path.is_symlink():
                raise RuntimeError(f'recorder input must not be a symlink: {path}')
        for name in sorted(leaves):
            path = Path(parent) / name
            s = path.stat()
            value = (s.st_size, s.st_mtime_ns, stat.S_IMODE(s.st_mode))
            files[str(path.relative_to(tree))] = value + ((digest(path),) if hashes else ())
    return files, dirs


def copy_file(source, target, old_root, new_root):
    """Ordinary private copies: a builder may edit an input in place."""
    target = Path(target)
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source, target)
    # Logs passed between stages can name generated maps by absolute path.
    raw = target.read_bytes()
    if os.fsencode(old_root) in raw:
        try:
            text = raw.decode('utf-8')
        except UnicodeDecodeError:
            raise RuntimeError(f'absolute recorder path in binary output: {source}')
        if '\0' in text:
            raise RuntimeError(f'absolute recorder path in binary output: {source}')
        target.write_text(text.replace(str(old_root), str(new_root)))
        shutil.copystat(source, target)


def restore(master, tree, before, dirs, changed):
    """Return a worker to the prepared step, including missing/empty folders."""
    now, current_dirs = inventory(tree)
    for name in now.keys() - before.keys():
        (tree / name).unlink()
    for name in sorted(current_dirs.keys() - dirs.keys(), key=lambda p: (p.count(os.sep), p), reverse=True):
        (tree / name).rmdir()
    for name in sorted(dirs):
        (tree / name).mkdir(parents=True, exist_ok=True)
    for name in changed:
        if name in before:
            copy_file(master / name, tree / name, master, tree)
    for name in sorted(dirs, key=lambda p: p.count(os.sep), reverse=True):
        (tree / name).chmod(dirs[name])


def mirror(master, tree, state):
    before, dirs = inventory(master, hashes=True)
    previous = json.loads(state.read_text()) if state.exists() else {}
    tree.mkdir(parents=True, exist_ok=True)
    now, current_dirs = inventory(tree)
    changed = {name for name, value in before.items() if previous.get(name) != list(value) or name not in now}
    restore(master, tree, before, dirs, changed)
    state.write_text(json.dumps(before, sort_keys=True))
    return before, dirs


def digest(path):
    h = hashlib.sha256()
    with open(path, 'rb') as stream:
        for chunk in iter(lambda: stream.read(1 << 20), b''):
            h.update(chunk)
    return h.hexdigest()


def batch(request, execute):
    """Each subprocess owns a private tree; every unit starts from the same snapshot."""
    request = json.loads(Path(request).read_text())
    master, tree, folder = map(Path, (request['master'], request['tree'], request['folder']))
    before, dirs = mirror(master, tree, folder / 'sync.json')
    results = []
    try:
        for group in request['groups']:
            dirty = set()
            for spec in group:
                result = execute(spec)
                artifact = folder / (spec['step'] + '-unit-' + str(spec['index']))
                artifact.mkdir(exist_ok=True)
                result['artifact'] = str(artifact)
                for name in result['graph']['writes']:
                    copy_file(tree / name, artifact / name, tree, master)
                results.append(result)
                dirty |= set(result['graph']['writes']) | set(result['graph']['removes'])
                (folder / 'results.json').write_text(json.dumps(results))
                if result['graph']['code'] not in ('0', 'None'):
                    raise RuntimeError(f"record unit failed: {spec['name']}; see {result['log']}")
            restore(master, tree, before, dirs, dirty)
    finally:
        (folder / 'results.json').write_text(json.dumps(results))


def units(master, specs, folder, requested, memory_mib):
    """Compute in bounded subprocesses; merge only after every worker passes."""
    # The shipped bundle intentionally omits release-only scheduling tools.
    # Load this recorder's scheduler without importing the bundle's tools package.
    scheduler_path = Path(__file__).resolve().parents[2] / 'tools/patcher/release_workers.py'
    spec = importlib.util.spec_from_file_location('engine_release_workers', scheduler_path)
    scheduler = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(scheduler)
    measure, worker_count = scheduler.measure, scheduler.worker_count
    tasks = record_groups.groups(specs)
    width = worker_count(requested, len(tasks), memory_mib)
    print(f'record {specs[0]["step"]}: {len(specs)} units, {width} workers, {memory_mib} MiB/worker', flush=True)
    folder = Path(folder)
    folder.mkdir(parents=True, exist_ok=True)
    children, lock = [], threading.Lock()
    stop = threading.Event()

    def worker(index):
        home = folder / ('worker-' + str(index))
        home.mkdir(exist_ok=True)
        (home / 'tree').mkdir(exist_ok=True)
        req = home / 'request.json'
        req.write_text(json.dumps(dict(master=str(master), tree=str(home / 'tree'), folder=str(home),
                                       groups=tasks[index::width])))
        logs = Path(os.environ['RECORD_LOGS']) / ('worker-' + str(index))
        logs.mkdir(parents=True, exist_ok=True)
        log = logs / (specs[0]['step'] + '.log')
        with log.open('w') as stream:
            with lock:
                if stop.is_set():
                    raise RuntimeError('recording canceled after another worker failed')
                process = subprocess.Popen([sys.executable, str(Path(__file__).with_name('record.py')),
                    str(home / 'tree'), str(home / 'unused.json'), '--unit-batch', str(req)],
                    stdout=stream, stderr=subprocess.STDOUT,
                    env=dict(os.environ, PYTHONDONTWRITEBYTECODE='1', RECORD_LOGS=str(logs)))
                children.append(process)
            metrics = {}
            with measure(process.pid, metrics.update):
                code = process.wait()
        (logs / (specs[0]['step'] + '.timing.json')).write_text(json.dumps(metrics))
        if code:
            raise RuntimeError(f'record worker {index} exited {code}: {log}')
        return json.loads((home / 'results.json').read_text())

    pool = ThreadPoolExecutor(width)
    futures = []
    try:
        futures = [pool.submit(worker, i) for i in range(width)]
        for future in as_completed(futures):
            future.result()
        results = {r['graph']['index']: r for future in futures for r in future.result()}
    except BaseException:
        with lock:
            stop.set()
            for child in children:
                if child.poll() is None:
                    child.terminate()
        for future in futures:
            future.cancel()
        raise
    finally:
        pool.shutdown(wait=True, cancel_futures=True)
    ordered = [results[s['index']] for s in specs]
    record_groups.validate_reads([r['graph'] for r in ordered])
    operations = record_groups.merge_operations(ordered, digest)
    # All computation and conflict validation completes before the master changes.
    for name, source in sorted(operations.items()):
        target = master / name
        if source is None:
            target.unlink(missing_ok=True)
        else:
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source, target)
    return ordered


def graph_record(record):
    """Keep elapsed times, private roots and unconsumed artifact hashes out of the graph."""
    shared = {}
    for job in record['jobs']:
        if job['part'] == 'unit':
            for name in job['writes']:
                shared.setdefault((job['step'], name), []).append(job)
    for job in record['jobs']:
        job['writes'] = {name: value if len(shared.get((job['step'], name), [])) > 1 else None
                         for name, value in sorted(job['writes'].items())}
    record['tree'] = '{ROOT}'
    record['seconds'] = sum(j['seconds'] for j in record['jobs'])
    return json.dumps(record, sort_keys=True, indent=0) + '\n'
