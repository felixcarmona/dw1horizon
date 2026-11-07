"""Content-addressed binary-delta computation; publication still checks every byte."""
import base64
import functools
import hashlib
import json
from pathlib import Path
import os
import sys
import tempfile
import zlib


@functools.lru_cache(maxsize=1)
def algorithm():
    import codecopy
    files = [Path(codecopy.__file__), Path(__file__), Path(sys.executable).resolve()]
    try:
        import bsdiff4
        files += [p for p in Path(bsdiff4.__file__).parent.rglob('*')
                  if p.is_file() and p.suffix in ('.py', '.so', '.pyd')]
    except ImportError:
        pass
    return [sys.version, sys.platform, [[p.name, hashlib.sha256(p.read_bytes()).hexdigest()] for p in sorted(files)]]


def delta(old, new, directory=None):
    import codecopy
    if not directory:
        return codecopy.make_delta(old, new)
    ident = dict(algorithm=algorithm(), old=hashlib.sha256(old).hexdigest(), new=hashlib.sha256(new).hexdigest())
    digest = hashlib.sha256(json.dumps(ident, sort_keys=True).encode()).hexdigest()
    path = Path(directory) / (digest + '.json.z')
    try:
        meta = json.loads(zlib.decompress(path.read_bytes()))
        raw = base64.b64decode(meta['data'], validate=True)
        if meta['identity'] == ident and hashlib.sha256(raw).hexdigest() == meta['sha256']:
            control, diff, extra = json.loads(raw)
            return control, bytes.fromhex(diff), bytes.fromhex(extra)
    except (OSError, ValueError, KeyError, TypeError, zlib.error):
        pass
    control, diff, extra = codecopy.make_delta(old, new)
    raw = json.dumps([control, diff.hex(), extra.hex()], separators=(',', ':')).encode()
    data = zlib.compress(json.dumps(dict(identity=ident, data=base64.b64encode(raw).decode(),
                                        sha256=hashlib.sha256(raw).hexdigest())).encode())
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, name = tempfile.mkstemp(dir=path.parent, prefix='.tmp-')
    try:
        with os.fdopen(fd, 'wb') as output:
            output.write(data)
        os.replace(name, path)
    finally:
        if os.path.exists(name):
            os.unlink(name)
    return control, diff, extra


def choose(args):
    """Pure worker: retain the original alternate-source tie-breaking rule."""
    old, target, candidate, directory = args
    control, diff, extra = delta(old, target, directory)
    alternate = False
    if extra and candidate is not None and len(candidate) >= len(target):
        other_control, other_diff, other_extra = delta(candidate, target, directory)
        if len(other_extra) < len(extra):
            alternate = True
            control, diff, extra = other_control, other_diff, other_extra
    return alternate, control, diff, extra
