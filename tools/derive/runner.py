"""Runs one of our command-line scripts inside this process (tools/derive/README.md, "runner.py").

    run_script(path, argv, env=None, cwd=None, isolate=True, record=False, check=True)
        -> Result(out, seconds, inputs, code)

The script runs as `python3 PATH ARGV...` would run it: runpy.run_path with run_name '__main__', sys.argv set to
[PATH] + argv, the environment changed by `env` (a value None removes the variable) and the working directory `cwd`.
argv, the environment, the working directory, sys.path and sys.modules are saved before and put back after, whatever
happens. SystemExit with None or 0 is success; any other exit (a message, a code) raises StepError with the captured
output (check=False: returned in Result.code instead). Its stdout and stderr are captured (Result.out), not printed.

isolate: the modules the script imported from the repository (its own helpers, tools/*.py) are forgotten afterwards,
so the next script imports them again: two folders may both have a common.py, and a module that reads a setting at
import time (sound.py's SOUND_STAGING_MAX) reads this run's environment. Modules from outside the repository (the
standard library, numpy, Pillow) stay loaded.

strict (off by default; set_strict(True) or DERIVE_STRICT=1): subprocess, os.system, os.exec*, os.fork, threads and
multiprocessing raise, as they do in Pyodide (the browser's Python), so a script that would not run there fails here.

Input recorder (record=True): an audit hook records every file the script opens (Result.inputs: read paths, written
paths); sys.addaudithook cannot be removed, so it is installed once and only listens while a run asks for it.
"""
import contextlib
import io
import os
import runpy
import sys
import time

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


class StepError(Exception):
    pass


class Result:
    def __init__(self, out, seconds, inputs, code=0):
        self.out, self.seconds, self.inputs, self.code = out, seconds, inputs, code


# ------------------------------------------------------------------ the input recorder
_recording = None          # (reads, writes) while a run records, else None
_hooked = False


def _hook(event, args):
    if _recording is None or event != 'open':
        return
    path, mode = args[0], args[1]
    if not isinstance(path, (str, bytes)) or isinstance(path, bytes):
        return
    p = os.path.abspath(path)
    m = mode if isinstance(mode, str) else ''
    if not m and isinstance(args[2], int):          # os.open: flags
        w = args[2] & (os.O_WRONLY | os.O_RDWR | os.O_CREAT | os.O_APPEND | os.O_TRUNC)
        (_recording[1] if w else _recording[0]).add(p)
        return
    (_recording[1] if any(c in m for c in 'wax+') else _recording[0]).add(p)


def _install_hook():
    global _hooked
    if not _hooked:
        sys.addaudithook(_hook)
        _hooked = True


@contextlib.contextmanager
def recorded(on=True):
    """The input recorder around code a step runs itself: yields (reads, writes), filled when the block ends (None when
    off or when a run already records)."""
    global _recording
    if not on or _recording is not None:
        yield None
        return
    _install_hook()
    rec = _recording = (set(), set())
    try:
        yield rec
    finally:
        _recording = None


# ------------------------------------------------------------------ strict mode
_STRICT_OFF = {}           # (module, name) -> the original, while strict is on


def _forbidden(what):
    def f(*a, **k):
        raise StepError(f'{what} in a derive step (strict mode: the browser has no processes or threads)')
    return f


def set_strict(on):
    """Strict on: process and thread creation raise; off: everything as it was."""
    import subprocess, threading, multiprocessing  # noqa: E401
    targets = [(subprocess, 'Popen'), (subprocess, 'run'), (subprocess, 'call'), (subprocess, 'check_call'),
               (subprocess, 'check_output'), (os, 'system'), (os, 'popen'), (os, 'fork'), (os, 'execv'),
               (os, 'execve'), (os, 'execvp'), (os, 'execvpe'), (os, 'execl'), (os, 'execlp'), (os, 'spawnv'),
               (os, 'posix_spawn'), (threading.Thread, 'start'), (multiprocessing, 'Pool'),
               (multiprocessing, 'Process')]
    if on and not _STRICT_OFF:
        for mod, name in targets:
            if hasattr(mod, name):
                _STRICT_OFF[(mod, name)] = getattr(mod, name)
                setattr(mod, name, _forbidden(f'{getattr(mod, "__name__", mod)}.{name}'))
    elif not on and _STRICT_OFF:
        for (mod, name), orig in _STRICT_OFF.items():
            setattr(mod, name, orig)
        _STRICT_OFF.clear()


def strict():
    return bool(_STRICT_OFF)


# ------------------------------------------------------------------ one run
def _repo_module(m):
    f = getattr(m, '__file__', None)
    if not f:
        return False
    f = os.path.abspath(f)
    return f.startswith(ROOT + os.sep) and os.sep + '.venv' + os.sep not in f[len(ROOT):] and \
        not f.startswith(os.path.join(ROOT, 'tools', 'derive') + os.sep)


def run_script(path, argv=(), env=None, cwd=None, isolate=True, record=False, check=True):
    path = os.path.join(ROOT, path) if not os.path.isabs(path) else path
    saved_argv, saved_path, saved_cwd = sys.argv[:], sys.path[:], os.getcwd()
    saved_env = dict(os.environ)
    saved_mods = set(sys.modules) if isolate else None
    global _recording
    if record:
        _install_hook()
    outer = _recording               # (a run inside a recorded unit: run_units records around it, this run leaves it)
    buf = io.StringIO()
    t0 = time.perf_counter()
    ok, why = True, None
    try:
        sys.argv = [path] + [str(a) for a in argv]
        # python3 SCRIPT puts the script's folder first on sys.path
        sys.path.insert(0, os.path.dirname(path))
        for k, v in (env or {}).items():
            if v is None: os.environ.pop(k, None)
            else: os.environ[k] = str(v)
        os.chdir(cwd or ROOT)
        if record:
            _recording = (set(), set())
        with contextlib.redirect_stdout(buf), contextlib.redirect_stderr(buf):
            try:
                runpy.run_path(path, run_name='__main__')
            except SystemExit as e:
                if e.code not in (None, 0):
                    ok, why = False, e.code
            except Exception:
                import traceback
                traceback.print_exc(file=buf)
                ok, why = False, 'an exception'
    finally:
        inputs = _recording if record else None
        if record:
            _recording = outer
            if outer is not None:     # (the unit around it sees this run's files too)
                outer[0].update(inputs[0]); outer[1].update(inputs[1])
        sys.argv = saved_argv
        sys.path[:] = saved_path
        os.chdir(saved_cwd)
        os.environ.clear(); os.environ.update(saved_env)
        if isolate:
            for name in [n for n in sys.modules if n not in saved_mods]:
                if _repo_module(sys.modules[name]):
                    del sys.modules[name]
    secs = time.perf_counter() - t0
    if not ok and check:
        raise StepError(f'{os.path.relpath(path, ROOT)} {" ".join(map(str, argv))}: exit {why}\n{buf.getvalue()[-3000:]}')
    return Result(buf.getvalue(), secs, inputs, 0 if ok else why)


if os.environ.get('DERIVE_STRICT') == '1':
    set_strict(True)


# ------------------------------------------------------------------ units: a step's independent pieces
class Unit:
    """One piece of a step (tools/derive/README.md, "Units"). Independent pieces run side by side.
    Pieces that share mutable files must name the same order_group: they run in the recorded list's order, so the
    last writer in that order wins, regardless of worker timing. Different groups and ungrouped pieces may overlap.

      name      what the log and the timings call it (a story pass: 'es base/orig'; a map recipe: its script and screen)
      fn, args  a module-level function and its arguments (plain data: they go to another process, or a Web Worker,
                as they are); it returns its log text and raises StepError when it fails
      inputs    what it reads: repository paths (folders or files), 'extracted/...' for the player's files and
                'step:NAME' for an earlier step's outputs (what a worker must have before it starts)
      outputs   what it writes, under the build's folder
      order_group  optional name of a sequence within this step (shared maps, for example)
    """
    def __init__(self, name, fn, args=(), inputs=(), outputs=(), order_group=None):
        self.name, self.fn, self.args = name, fn, tuple(args)
        self.inputs, self.outputs = list(inputs), list(outputs)
        self.order_group = order_group


class Done:
    """What a unit gave: its log text, seconds, and the peak memory of the process that ran it (KiB; a worker's, when it
    ran in one, else None)."""
    def __init__(self, unit, out, seconds, maxrss=None):
        self.unit, self.out, self.seconds, self.maxrss = unit, out, seconds, maxrss


def _in_worker(fn, args):
    t0 = time.perf_counter()
    out = fn(*args)
    try:
        import resource
    except ImportError:            # (Windows: no peak memory in the log)
        return out, time.perf_counter() - t0, None
    return out, time.perf_counter() - t0, resource.getrusage(resource.RUSAGE_SELF).ru_maxrss


class WorkerTraceback(Exception):
    """The traceback of an exception raised in a unit's worker (the cause of the one raised here)."""


def _sendable(e):
    """The exception as it can go back to the build: itself when it survives pickling, else a StepError with its text."""
    import pickle
    try:
        pickle.loads(pickle.dumps(e))
        return e
    except Exception:
        return StepError(f'{type(e).__name__}: {e}')


def _worker(conn, once, spawned):
    """A unit worker: runs (fn, args) it receives and sends back ('ok', out, seconds, maxrss) or ('fail', exception,
    traceback text), whatever the unit raises (SystemExit too: a unit's sys.exit is its failure, not the worker's end).
    once: one unit and out (forked workers: a fresh process per unit); else until it receives None."""
    if spawned:
        _spawned()
    while True:
        try:
            task = conn.recv()
        except (EOFError, OSError):
            return
        if task is None:
            return
        try:
            res = ('ok',) + _in_worker(*task)
        except BaseException as e:      # noqa: B902
            import traceback
            res = ('fail', _sendable(e), traceback.format_exc())
        try:
            conn.send(res)
        except Exception as e:         # (a log text that cannot be pickled)
            conn.send(('fail', StepError(f'its result could not be sent back: {e}'), ''))
        if once:
            return


def _spawned():
    """A spawned worker's start: what a forked one inherits from the build (every derived byte is made with crmath's
    sin, cos ... and pysum's sum: __main__.build installs them around the steps)."""
    from . import crmath, pysum
    crmath.install(); pysum.install()


def start_method():
    """How unit workers start: forked on Linux (nothing is imported again); spawned elsewhere (Windows has no fork;
    macOS's system libraries are not safe to fork with threads). DERIVE_START=fork|spawn chooses (tests)."""
    m = os.environ.get('DERIVE_START') or ('fork' if sys.platform.startswith('linux') else 'spawn')
    if m not in ('fork', 'spawn'):
        raise StepError(f'DERIVE_START={m}: fork or spawn')
    return m


def run_units(ctx, units):
    """Runs a step's units -> [Done] in the units' order, whatever order they finished in.

    rule: one process is the reference. With ctx.jobs above 1 (derive build --jobs, DERIVE_JOBS), and neither strict mode
    (the browser has no processes) nor the input recorder (an audit hook sees only this process) on, they run side by
    side in up to ctx.jobs processes, a fresh one per unit (forked: nothing is imported again; its peak memory is the
    unit's, plus the pages it shares with this process; spawned and reused where fork is not safe: start_method); else
    one after another here, in order. Units in the same order_group always run in recorded order: each waits for its
    predecessor to finish before starting. The bytes are the same either way. A future web scheduler takes the same list and
    hands each unit to a Web Worker.

    rule: the first unit that fails stops the step: the other workers are stopped and the unit's error is raised here
    as it was raised there (a SystemExit with its message, a StepError, any exception with the worker's traceback as its
    cause), as soon as it comes, whatever the units before it in the list are doing; a worker that dies without a word
    (killed, out of memory, a crash in C) is a StepError naming the unit. No worker outlives the call."""
    todo = list(range(len(units)))
    # Test hook: reverse the scheduling priority, never the recorded order or a group's dependencies.
    order = os.environ.get('DERIVE_UNIT_ORDER', '')
    if order == 'reverse':
        todo.reverse()
    elif order:
        raise StepError(f'DERIVE_UNIT_ORDER={order}: reverse or unset')
    previous, last = {}, {}
    for i, u in enumerate(units):
        if u.order_group is not None:
            previous[i] = last.get(u.order_group)
            last[u.order_group] = i
    results = [None] * len(units)

    def ready():
        for k, i in enumerate(todo):
            before = previous.get(i)
            if before is None or results[before] is not None:
                return todo.pop(k)
        return None

    if ctx.jobs <= 1 or strict() or ctx.record or len(units) <= 1:
        global _recording
        while todo:
            i = ready()
            u = units[i]
            outer = _recording
            if ctx.record:
                _install_hook(); _recording = (set(), set())
            t0 = time.perf_counter()
            try:
                out = u.fn(*u.args)
            finally:
                if ctx.record:
                    ctx.note_inputs(*_recording)
                    _recording = outer
            results[i] = Done(u, out, time.perf_counter() - t0)
        return results
    import multiprocessing
    from multiprocessing.connection import wait
    method = start_method()
    mp = multiprocessing.get_context(method)
    once = method == 'fork'
    busy = {}                  # connection -> (process, unit index)
    idle = []                  # spawned workers waiting for a unit: (process, connection)
    procs = []
    try:
        while todo or busy:
            while todo and len(busy) < ctx.jobs:
                i = ready()
                if i is None:          # all remaining units wait for a writer still running
                    break
                if idle:
                    p, c = idle.pop()
                else:
                    c, theirs = mp.Pipe()
                    p = mp.Process(target=_worker, args=(theirs, once, not once), daemon=True)
                    p.start()
                    theirs.close()
                    procs.append(p)
                c.send((units[i].fn, units[i].args))
                busy[c] = (p, i)
            for c in wait(list(busy)):
                p, i = busy.pop(c)
                try:
                    res = c.recv()
                except (EOFError, OSError):
                    p.join(5)
                    raise StepError(f'unit {units[i].name}: its worker stopped without a result (exit code '
                                    f'{p.exitcode})') from None
                if res[0] == 'fail':
                    e, tb = res[1], res[2]
                    if isinstance(e, (SystemExit, StepError)) or not tb:
                        raise e
                    raise e from WorkerTraceback(f'unit {units[i].name}, in its worker:\n{tb}')
                results[i] = Done(units[i], *res[1:])
                if once:
                    c.close(); p.join()
                else:
                    idle.append((p, c))
        for p, c in idle:               # (spawned workers: no more units)
            c.send(None); c.close()
        for p, c in idle:
            p.join(10)
        return results
    finally:
        for p in procs:                 # (after a failure, the units still running are stopped)
            if p.is_alive():
                p.terminate()
        for p in procs:
            p.join(10)
            if p.is_alive():
                p.kill(); p.join()
