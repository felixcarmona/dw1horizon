"""Verified, content-addressed artifacts for native developer builds.

Callers must use clean staging and disable existence-based output reuse.
An index is only a hint to an entry. Every dependency and every artifact is hashed
before reuse. No timestamp is a cache key. Entries and blobs are atomically
published; a missing/corrupt entry is a miss. Outputs are copied, never hardlinked.
"""
from contextlib import contextmanager
import hashlib
import json
import os
from pathlib import Path
import shutil
import sys
import tempfile

FORMAT = 2
_ACTIVE = None
_HOOKED = False
_STAT = os.stat
_LSTAT = os.lstat


def digest(path):
    h = hashlib.sha256()
    with open(path, 'rb') as f:
        for b in iter(lambda: f.read(1024 * 1024), b''):
            h.update(b)
    return h.hexdigest()


def encoded(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':')).encode()


def key(value):
    return hashlib.sha256(encoded(value)).hexdigest()


def atomic(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, name = tempfile.mkstemp(dir=path.parent, prefix='.tmp-')
    try:
        with os.fdopen(fd, 'wb') as f:
            f.write(data)
        os.replace(name, path)
    finally:
        if os.path.exists(name):
            os.unlink(name)


def state(path, kind):
    try:
        st = _STAT(path)
    except FileNotFoundError:
        return None
    if kind == 'file':
        return digest(path) if __import__('stat').S_ISREG(st.st_mode) else 'directory'
    if kind == 'names':
        return sorted(os.listdir(path))
    if __import__('stat').S_ISREG(st.st_mode):
        return ['file', digest(path), st.st_size, st.st_mode & 0o7777]
    return ['directory', st.st_mode & 0o7777]


class Capture:
    """Read preimages, directory membership, failed probes and actual writes.

    Audit callbacks run before I/O. Reads after our own writes are intermediates,
    not external dependencies; reads before an in-place write retain their preimage.
    Stat probes track presence/type, never mtime. Directory membership catches new
    glob matches and additions that were absent from the previous read manifest.
    """
    def __init__(self, writable):
        self.writable = Path(writable).absolute()
        self.dependencies = {}
        self.writes, self.deleted, self.dirty = set(), set(), set()
        self.directory_preimages = {}
        self.busy = False
        self.unsafe = False

    def path(self, path):
        if not isinstance(path, (str, bytes, os.PathLike)):
            return None
        return os.path.abspath(os.fsdecode(path))

    def read(self, path, kind):
        p = self.path(path)
        if p is None:
            return
        if '__pycache__' in Path(p).parts:
            import importlib.util
            try:
                source = importlib.util.source_from_cache(p)
                if _STAT(source):
                    p = source
            except (OSError, ValueError):
                pass
        ident = (p, kind)
        if p in self.dirty:
            if kind == 'names' and p in self.directory_preimages and self.directory_preimages[p] is not None:
                self.dependencies.setdefault(ident, self.directory_preimages[p])
            return
        if ident not in self.dependencies:
            try:
                self.dependencies[ident] = state(p, kind)
            except (OSError, ValueError):
                self.unsafe = True

    def write(self, path, deleted=False):
        p = self.path(path)
        if p is None:
            self.unsafe = True
            return
        if '__pycache__' in Path(p).parts:
            return
        if not Path(p).is_relative_to(self.writable):
            self.unsafe = True
            return
        parent = os.path.dirname(p)
        if parent not in self.directory_preimages and parent not in self.dirty:
            try:
                self.directory_preimages[parent] = state(parent, 'names')
            except OSError:
                self.unsafe = True
        # Missing probes of paths we subsequently create describe outputs.
        # Callers use clean staging; output existence is never a reuse rule.
        for kind in ('probe', 'file'):
            if self.dependencies.get((p, kind), 'not-recorded') is None:
                self.dependencies.pop((p, kind), None)
        self.dirty.add(p)
        if deleted:
            self.deleted.add(p)
        else:
            self.writes.add(p)
        # A newly-created child changes a directory listing within this call.
        parent = os.path.dirname(p)
        while Path(parent).is_relative_to(self.writable):
            self.dirty.add(parent)
            parent = os.path.dirname(parent)


def _at(path, directory=-1):
    if isinstance(path, int):
        return os.readlink(f'/proc/self/fd/{path}')
    if directory not in (-1, None) and not os.path.isabs(path):
        return os.path.join(os.readlink(f'/proc/self/fd/{directory}'), path)
    return path


def _audit(event, args):
    c = _ACTIVE
    if c is None or c.busy:
        return
    c.busy = True
    try:
        if event == 'open':
            if isinstance(args[0], int):
                return  # fdopen: the preceding os.open already recorded its path
            mode = args[1]
            flags = args[2]
            write = any(x in mode for x in 'wax+') if isinstance(mode, str) else bool(
                flags & (os.O_WRONLY | os.O_RDWR | os.O_CREAT | os.O_APPEND | os.O_TRUNC))
            if write:
                # Append/update modes consume the old bytes too.
                if ((isinstance(mode, str) and ('a' in mode or '+' in mode)) or
                        (not isinstance(mode, str) and not flags & os.O_TRUNC)):
                    c.read(args[0], 'file')
                c.write(args[0])
            else:
                c.read(args[0], 'file')
        elif event in ('os.listdir', 'os.scandir'):
            c.read(_at(args[0]) if args[0] is not None else '.', 'names')
        elif event in ('os.remove', 'os.rmdir'):
            c.write(_at(args[0], args[1]), deleted=True)
        elif event == 'os.rename':
            src, dst = _at(args[0], args[2]), _at(args[1], args[3])
            if os.path.isdir(src):
                for folder, dirs, files in os.walk(src):
                    c.read(folder, 'names')
                    for name in files:
                        old = os.path.join(folder, name)
                        c.read(old, 'file')
                        c.write(old, deleted=True)
                        c.write(os.path.join(dst, os.path.relpath(old, src)))
            else:
                c.read(src, 'file')
            c.write(src, deleted=True)
            c.write(dst)
        elif event in ('subprocess.Popen', 'os.system', 'os.exec', 'os.fork', 'os.symlink', 'os.link'):
            c.unsafe = True
        elif event == 'os.mkdir':
            path = _at(args[0], args[2])
            current = state(path, 'probe')
            absolute = c.path(path)
            if current is None:
                c.write(path)
            elif current[0] == 'directory' and Path(absolute).is_relative_to(c.writable):
                # makedirs(exist_ok=True) ensures an output namespace. Its
                # prior existence is not an input, but any subsequent listing
                # still depends on the pre-call names in that directory.
                if absolute not in c.dirty and absolute not in c.directory_preimages:
                    c.directory_preimages[absolute] = state(absolute, 'names')
                c.dependencies.pop((absolute, 'probe'), None)
                c.write(path)
    except OSError:
        c.unsafe = True
    finally:
        c.busy = False


def _stat(path, *args, **kwargs):
    c = _ACTIVE
    if c is not None and not c.busy and not args and not kwargs.get('dir_fd'):
        c.busy = True
        try:
            c.read(path, 'probe')
        finally:
            c.busy = False
    return _STAT(path, *args, **kwargs)


@contextmanager
def capturing(writable):
    global _ACTIVE, _HOOKED
    if _ACTIVE is not None:
        raise RuntimeError('nested build cache capture')
    if not _HOOKED:
        sys.addaudithook(_audit)
        _HOOKED = True
    c = Capture(writable)
    scratch = Path(writable) / '.cache-tmp'
    scratch.mkdir(parents=True, exist_ok=True)
    old_temp = tempfile.tempdir
    tempfile.tempdir = str(scratch)
    old_stat = os.stat
    os.stat = _stat
    _ACTIVE = c
    try:
        yield c
    finally:
        _ACTIVE = None
        os.stat = old_stat
        tempfile.tempdir = old_temp


class Cache:
    def __init__(self, root, writable):
        self.root = Path(root).absolute()
        self.writable = Path(writable).absolute()
        self.last_inputs = {}
        self.last_unsafe = False

    def output(self, name):
        p = Path(name)
        if not p.is_absolute() or not p.is_relative_to(self.writable) or '..' in p.parts:
            raise ValueError('cache output outside build directory')
        return p

    def blob(self, sha):
        if not isinstance(sha, str) or len(sha) != 64 or any(c not in '0123456789abcdef' for c in sha):
            raise ValueError('invalid cache digest')
        return self.root / 'blobs' / sha[:2] / sha[2:]

    def restore(self, identity):
        self.last_inputs = {}
        self.last_unsafe = False
        try:
            ids = json.loads((self.root / 'index' / key(identity)).read_bytes())
        except (OSError, ValueError):
            return None
        if not isinstance(ids, list):
            return None
        for entry in ids:
            try:
                meta = json.loads(self.blob(entry).read_bytes())
                if key(meta) != entry or meta['format'] != FORMAT or meta['identity'] != identity:
                    continue
                bad = [(p, kind) for p, kind, expected in meta['inputs'] if state(p, kind) != expected]
                if bad:
                    if os.environ.get('DW_CACHE_DEBUG'):
                        print(f'cache changed: {identity.get("name", identity.get("kind"))}: {bad[:3]}', flush=True)
                    continue
                outputs = [(self.output(p), self.blob(sha)) for p, sha in meta['outputs']]
                if any(digest(src) != sha for (_, sha), (_, src) in zip(meta['outputs'], outputs)):
                    continue
                deletes = [self.output(p) for p in meta['deleted']]
                directories = [self.output(p) for p in meta.get('directories', [])]
                for p in deletes:
                    if p.is_file() or p.is_symlink():
                        p.unlink()
                    elif p.is_dir():
                        shutil.rmtree(p)
                for p in directories:
                    p.mkdir(parents=True, exist_ok=True)
                for dst, src in outputs:
                    dst.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copyfile(src, dst)
                self.last_inputs = {(p, kind): value for p, kind, value in meta['inputs']}
                return meta['result']
            except (OSError, ValueError, TypeError, KeyError):
                continue
        return None

    def save(self, identity, capture, result):
        try:
            return self._save(identity, capture, result)
        except OSError as e:
            if os.environ.get('DW_CACHE_DEBUG'):
                print(f'cache not saved: {e}', flush=True)
            return False

    def _save(self, identity, capture, result):
        if capture.unsafe:
            if os.environ.get('DW_CACHE_DEBUG'):
                print(f'cache bypass: {identity.get("name", identity.get("kind"))}: writes outside build or unrecorded I/O', flush=True)
            return False
        if any(state(p, kind) != value for (p, kind), value in capture.dependencies.items()
               if p not in capture.dirty):
            return False  # an independent input changed during the call
        outputs = []
        for p in sorted(capture.writes):
            if not Path(p).is_file():
                continue
            sha = digest(p)
            target = self.blob(sha)
            # Replace a corrupt existing blob as well as filling a missing one.
            if not target.is_file() or digest(target) != sha:
                atomic(target, Path(p).read_bytes())
            outputs.append([p, sha])
        meta = dict(format=FORMAT, identity=identity,
                    inputs=[[p, k, v] for (p, k), v in sorted(capture.dependencies.items())],
                    outputs=outputs, directories=sorted(p for p in capture.writes if Path(p).is_dir()),
                    deleted=sorted(p for p in capture.deleted if not Path(p).exists()),
                    result=result)
        sha = key(meta)
        atomic(self.blob(sha), encoded(meta))
        index = self.root / 'index' / key(identity)
        try:
            previous = json.loads(index.read_bytes())
        except (OSError, ValueError):
            previous = []
        if not isinstance(previous, list):
            previous = []
        atomic(index, encoded([sha] + [s for s in previous if s != sha][:15]))
        return True

    def call(self, identity, fn):
        identity = json.loads(encoded(identity))
        hit = self.restore(identity)
        if hit is not None:
            return hit, True
        with capturing(self.writable) as capture:
            result = fn()
        self.last_inputs = capture.dependencies.copy()
        self.last_unsafe = capture.unsafe
        self.save(identity, capture, result)
        return result, False
