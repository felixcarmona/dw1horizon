#!/usr/bin/env python3
"""Tests of tools/derive's unit workers (runner.run_units with --jobs above 1): a unit that fails stops the step at
once with that unit's error, and no worker is left running; units that succeed come back in order. Shared writers
run in recorded order even with reversed scheduling, while independent work can run beside them.

Each case runs a few units side by side, one of them failing (a SystemExit with a message, as species.py's "no model
file"; a StepError; any other exception; a worker that dies without a word), the others sleeping long: the failure must
come back within seconds, as the same error the one-process build gives, with every worker gone.

  tools/test_derive_units.py              fork and spawn workers (DERIVE_START), each case
  tools/test_derive_units.py fork|spawn   only one way
(selftest: derive-units)
"""
import multiprocessing, os, signal, sys, tempfile, time  # noqa: E401
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
from tools.derive import runner  # noqa: E402

LONG = 60           # what the other units sleep: far beyond the time a failure may take to come back
PROMPT = 15         # seconds a failure may take (a spawned worker imports numpy-free tools.derive only)


class Ctx:
    def __init__(self, jobs):
        self.jobs, self.record = jobs, False


def ok(i, secs=0.0):
    time.sleep(secs)
    return f'unit {i} ({os.getpid()})'


def sleep_long(i):
    time.sleep(LONG)
    return f'unit {i}'


def exit_message(path):
    raise SystemExit(f'{path}: no model file')


def step_error(what):
    raise runner.StepError(what)


def value_error(what):
    raise ValueError(what)


def die(code):
    os._exit(code)


def write_shared(folder, group, i):
    # The first writer waits for independent work: ordering a group must not serialize the whole step.
    if i == 0:
        until = time.monotonic() + PROMPT
        while not os.path.isfile(os.path.join(folder, 'independent')):
            if time.monotonic() > until:
                raise runner.StepError('independent unit could not run beside an ordered group')
            time.sleep(0.01)
        time.sleep(0.2)
    with open(os.path.join(folder, group + '-trace'), 'a') as f:
        f.write(str(i))
    with open(os.path.join(folder, group), 'w') as f:
        f.write(str(i))
    return str(i)


def independent(folder):
    with open(os.path.join(folder, 'independent'), 'w') as f:
        f.write('ready')
    return 'independent'


def ordered_writers(jobs):
    with tempfile.TemporaryDirectory(prefix='derive-order-') as folder:
        shared = [runner.Unit(f'{g}{i}', write_shared, (folder, g, i), order_group=g)
                  for i in range(3) for g in ('maps', 'other')]
        free = runner.Unit('independent', independent, (folder,))
        # With workers, reverse priority starts both waiting writers before the independent unit. It must still get
        # the third slot. In one process the signal must come first, since no work can overlap there.
        us = [free] + shared if jobs > 1 and not runner.strict() else shared + [free]
        before = os.environ.get('DERIVE_UNIT_ORDER')
        os.environ['DERIVE_UNIT_ORDER'] = 'reverse'
        try:
            done = runner.run_units(Ctx(jobs), us)
        finally:
            if before is None: os.environ.pop('DERIVE_UNIT_ORDER', None)
            else: os.environ['DERIVE_UNIT_ORDER'] = before
        good = [d.unit.name for d in done] == [u.name for u in us] and not kids()
        for group in ('maps', 'other'):
            with open(os.path.join(folder, group + '-trace')) as f:
                good &= f.read() == '012'
            with open(os.path.join(folder, group)) as f:
                good &= f.read() == '2'
        print(f'  {"ok  " if good else "FAIL"}  reversed scheduling, jobs={jobs}, strict={runner.strict()}: '
              'two ordered writer groups, independent work, last writer wins')
        return good


class Unpicklable(Exception):
    def __init__(self, a, b):          # (pickle calls Unpicklable(*args) with one argument: loading fails)
        super().__init__(f'{a} {b}')


def unpicklable(what):
    raise Unpicklable(what, 'x')


def units(bad):
    us = [runner.Unit('first', ok, (0, 0.2))]
    # A queued writer must not hide an independent failure behind the writer it waits for.
    us += [runner.Unit(f'long {i}', sleep_long, (i,), order_group='waiting') for i in range(1, 3)]
    us += [runner.Unit('bad', bad[0], bad[1])]
    us += [runner.Unit(f'long {i}', sleep_long, (i,)) for i in range(4, 7)]
    return us


def kids():
    return [p for p in multiprocessing.active_children()]


class Timeout(Exception):
    pass


def alarm(*_):
    raise Timeout()


def case(name, bad, expect_type, expect_text):
    signal.signal(signal.SIGALRM, alarm)
    signal.alarm(PROMPT * 4)
    t0 = time.perf_counter()
    got = None
    try:
        runner.run_units(Ctx(4), units(bad))
    except Timeout:
        got = 'hung'
    except BaseException as e:      # noqa: B902 (SystemExit is what is expected)
        got = e
    finally:
        signal.alarm(0)
    secs = time.perf_counter() - t0
    left = kids()
    good = isinstance(got, expect_type) and expect_text in str(got) and secs < PROMPT and not left
    print(f'  {"ok  " if good else "FAIL"}  {name}: {type(got).__name__ if got != "hung" else "hung"} '
          f'"{str(got)[:80]}" in {secs:.1f} s, {len(left)} workers left')
    for p in left:
        p.kill()
    return good


def run(method):
    os.environ['DERIVE_START'] = method
    print(f'{method}:')
    good = True
    # everything succeeds: the logs in the units' order
    t0 = time.perf_counter()
    done = runner.run_units(Ctx(4), [runner.Unit(f'u{i}', ok, (i, 0.3 - i * 0.05)) for i in range(6)])
    order = [d.out.split()[1] for d in done] == [str(i) for i in range(6)] and all(d.seconds >= 0 for d in done)
    print(f'  {"ok  " if order and not kids() else "FAIL"}  six units, in order, {time.perf_counter() - t0:.1f} s')
    good &= order and not kids()
    good &= ordered_writers(1)
    good &= ordered_writers(3)
    runner.set_strict(True)
    try:
        good &= ordered_writers(3)
    finally:
        runner.set_strict(False)
    good &= case('SystemExit with a message (species.py: no model file)',
                 (exit_message, ('content/species/180-veemon.json',)), SystemExit,
                 'content/species/180-veemon.json: no model file')
    good &= case('StepError', (step_error, ('a script failed',)), runner.StepError, 'a script failed')
    good &= case('another exception', (value_error, ('bad value',)), ValueError, 'bad value')
    good &= case('an exception that cannot be sent back', (unpicklable, ('odd',)), runner.StepError, 'odd x')
    good &= case('a worker that dies (os._exit)', (die, (3,)), runner.StepError, 'exit code 3')
    return good


def main():
    methods = sys.argv[1:] or ['fork', 'spawn']
    results = [run(m) for m in methods]
    sys.exit(0 if all(results) else 1)


if __name__ == '__main__':
    main()
