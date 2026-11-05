"""Bound release workers by CPU and available memory; sample whole process trees."""
import contextlib
import os
from pathlib import Path
import threading
import time


def worker_count(requested, tasks, memory_mib=6144):
    if requested < 1 or memory_mib < 1:
        raise ValueError('worker count and memory budget must be positive')
    available = None
    try:
        values = dict(line.split(':', 1) for line in Path('/proc/meminfo').read_text().splitlines())
        available = int(values['MemAvailable'].split()[0]) // 1024
    except (OSError, ValueError, KeyError):
        pass
    # Leave headroom for the controller, payloads, file cache and emulator gates.
    memory_limit = max(1, (available - 8192) // memory_mib) if available is not None else 1
    return max(1, min(requested, tasks, os.cpu_count() or 1, memory_limit))


def tree_rss(pid):
    """Linux resident KiB, summed across the worker and its descendants."""
    parents, resident = {}, {}
    for path in Path('/proc').glob('[0-9]*/stat'):
        try:
            fields = path.read_text().rsplit(')', 1)[1].split()
            child = int(path.parent.name)
            parents[child] = int(fields[1])
            resident[child] = int(fields[21]) * os.sysconf('SC_PAGE_SIZE') // 1024
        except (OSError, ValueError, IndexError):
            continue
    selected = {pid}
    while True:
        found = {p for p, parent in parents.items() if parent in selected}
        if found <= selected:
            return sum(resident.get(p, 0) for p in selected)
        selected |= found


@contextlib.contextmanager
def measure(pid, report):
    stop = threading.Event()
    peak = [0]

    def sample():
        while not stop.is_set():
            peak[0] = max(peak[0], tree_rss(pid))
            stop.wait(.25)

    start = time.monotonic()
    thread = threading.Thread(target=sample, daemon=True)
    thread.start()
    try:
        yield
    finally:
        stop.set()
        thread.join()
        report(dict(seconds=round(time.monotonic() - start, 2), peak_rss_kib=peak[0]))


def ordered(tasks, width, on_error=lambda: None):
    """Compute independently, fail promptly, and return results in submission order."""
    from concurrent.futures import ThreadPoolExecutor, as_completed
    pool = ThreadPoolExecutor(width)
    futures = {}
    try:
        futures = {name: pool.submit(fn) for name, fn in tasks.items()}
        for future in as_completed(futures.values()):
            future.result()
        return {name: future.result() for name, future in futures.items()}
    except BaseException:
        on_error()
        for future in futures.values():
            future.cancel()
        raise
    finally:
        pool.shutdown(wait=True, cancel_futures=True)


class Metrics:
    """Private timing evidence; never put machine measurements in the package."""
    def __init__(self, path):
        self.path = Path(path)
        self.lock = threading.Lock()
        self.started = time.monotonic()
        self.rows = []

    def record(self, name, data):
        import json
        with self.lock:
            self.rows.append(dict(name=name, **data))
            self.path.parent.mkdir(parents=True, exist_ok=True)
            temp = self.path.with_suffix('.tmp')
            temp.write_text(json.dumps(dict(seconds=round(time.monotonic() - self.started, 2),
                                            phases=self.rows), indent=2) + '\n')
            os.replace(temp, self.path)
