"""Wait for a full PCSX-Redux protobuf save, including asynchronous file writes."""

from pathlib import Path as _DevPath
import sys as _dev_sys
_DEV_ROOT = str(next(p for p in _DevPath(__file__).resolve().parents if (p / "tools").is_dir()))
_dev_sys.path.insert(0, _DEV_ROOT)
_dev_sys.path.insert(0, str(_DevPath(_DEV_ROOT) / "tools"))
import hashlib
import time
from pathlib import Path


def protobuf_complete(data):
    """Check complete top-level fields needed by a full Redux snapshot."""
    def varint(pos):
        value = 0
        for shift in range(0, 70, 7):
            if pos >= len(data):
                raise ValueError('truncated protobuf varint')
            byte = data[pos]
            pos += 1
            value |= (byte & 127) << shift
            if byte < 128:
                return value, pos
        raise ValueError('invalid protobuf varint')

    pos, fields = 0, set()
    while pos < len(data):
        tag, pos = varint(pos)
        field, wire = tag >> 3, tag & 7
        if not field:
            raise ValueError('invalid protobuf field')
        fields.add(field)
        if wire == 0:
            _, pos = varint(pos)
        elif wire in (1, 5):
            pos += 8 if wire == 1 else 4
        elif wire == 2:
            length, pos = varint(pos)
            pos += length
        else:
            raise ValueError('unsupported protobuf wire type')
        if pos > len(data):
            raise ValueError('truncated protobuf field')
    if not {1, 3, 4, 5, 6, 7}.issubset(fields):
        raise ValueError('missing full snapshot components')
    if b'PCSX-Redux SaveState' not in data[:64]:
        raise ValueError('not a PCSX-Redux snapshot')
    return True


def wait_complete(path, timeout=30, interval=.1, stable_seconds=.3):
    """Return the final file pin only after complete, unchanged observations."""
    path = Path(path)
    deadline = time.monotonic() + timeout
    previous, since, last_error = None, None, 'save file not present'
    while time.monotonic() < deadline:
        try:
            before = path.stat()
            data = path.read_bytes()
            after = path.stat()
            if (before.st_size, before.st_mtime_ns, before.st_ino) != (
                    after.st_size, after.st_mtime_ns, after.st_ino):
                raise ValueError('save still changing while read')
            protobuf_complete(data)
            signature = (len(data), after.st_mtime_ns, after.st_ino,
                         hashlib.sha256(data).hexdigest())
            now = time.monotonic()
            if signature != previous:
                previous, since = signature, now
            elif now - since >= stable_seconds:
                return dict(bytes=len(data), sha256=signature[-1])
        except (OSError, ValueError) as error:
            previous, since = None, None
            last_error = str(error)
        time.sleep(interval)
    raise TimeoutError(f'save did not finish: {path}: {last_error}')
