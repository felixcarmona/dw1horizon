"""Private release staging with verified recording and incremental derive caches.

Stable, locked roots let the existing audited derive cache track absolute file
reads across cuts. Each invocation starts from a fresh copy of its supplied tree;
outputs are never accepted because they happen to exist. Player replay and the
isolated bundle verification do not enter this path.
"""
from contextlib import contextmanager
import fcntl
import hashlib
import json
import os
from pathlib import Path
import shutil
import sys

from tools.build_cache import atomic, digest, encoded, key


def environment(values):
    """Remove launcher/native staging metadata, preserving unknown build settings."""
    omitted = {'W', 'DW_PORTRAITS_CACHE', 'EMU_PORT', 'DW_SELFTEST_DERIVE', 'NAME', 'DERIVE_JOBS',
               'PWD', 'OLDPWD', 'SHLVL', '_', 'DBUS_SESSION_BUS_ADDRESS', 'XDG_SESSION_ID'}
    return {k: v for k, v in values.items()
            if k not in omitted and not k.startswith(('CODEX_', 'CLAUDE'))}


def files(root):
    return sorted(p for p in root.rglob('*') if p.is_file() and '__pycache__' not in p.parts)


def fingerprint(root, recipe, sources, environment):
    """Include every supplied file, source-disc byte, environment and runtime.

    The recording may read inputs outside its final opened-file list (imports,
    directory discovery, absent-file probes). Hash the entire clean input tree,
    not just the previous recording's positive open events.
    """
    from tools.derive.cache import runtime_sources
    return key(dict(format=2, recipe=recipe, root_mode=root.stat().st_mode & 0o7777,
                    tree=[[p.relative_to(root).as_posix(), digest(p), p.stat().st_mode & 0o7777] for p in files(root)],
                    directories=sorted([p.relative_to(root).as_posix(), p.stat().st_mode & 0o7777] for p in root.rglob('*')
                                       if p.is_dir() and '__pycache__' not in p.parts),
                    sources=sorted([game, digest(Path(image))] for game, image in
                                   (s.split('=', 1) for s in sources or [])),
                    environment=environment, runtime=[sys.version, sys.platform, runtime_sources()]))


def restore(snapshot, root):
    try:
        meta = json.loads((snapshot / 'manifest.json').read_bytes())
        inventory = {k: meta[k] for k in ('files', 'directories', 'root_mode')}
        if meta.get('format') != 3 or key(inventory) != meta['sha256']:
            return False
        def valid(rel, mode):
            p = Path(rel)
            return not p.is_absolute() and '..' not in p.parts and isinstance(mode, int) and 0 <= mode <= 0o7777
        if not valid('.', meta['root_mode']):
            return False
        for rel, mode in meta['directories']:
            if not valid(rel, mode):
                return False
        for rel, sha, mode in meta['files']:
            if not valid(rel, mode) or digest(snapshot / 'tree' / rel) != sha:
                return False
        for rel, mode in meta['directories']:
            (root / rel).mkdir(parents=True, exist_ok=True)
        for rel, sha, mode in meta['files']:
            dst = root / rel
            dst.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(snapshot / 'tree' / rel, dst)
            dst.chmod(mode)
        for rel, mode in reversed(meta['directories']):
            (root / rel).chmod(mode)
        root.chmod(meta['root_mode'])
        return True
    except (OSError, ValueError, KeyError, TypeError):
        return False


def save(snapshot, root):
    snapshot.mkdir(parents=True, exist_ok=True)
    entries = []
    for source in files(root):
        rel = source.relative_to(root).as_posix()
        sha = digest(source)
        atomic(snapshot / 'tree' / rel, source.read_bytes())
        entries.append([rel, sha, source.stat().st_mode & 0o7777])
    inventory = dict(files=entries, root_mode=root.stat().st_mode & 0o7777,
                     directories=sorted([p.relative_to(root).as_posix(), p.stat().st_mode & 0o7777]
                     for p in root.rglob('*') if p.is_dir() and '__pycache__' not in p.parts))
    atomic(snapshot / 'manifest.json', encoded(dict(format=3, **inventory, sha256=key(inventory))))


@contextmanager
def stage(directory, slot, supplied):
    """Hold a slot until its result is copied back; no consumer sees mutable data."""
    directory = Path(directory).resolve()
    slot = key(slot)
    directory.mkdir(parents=True, exist_ok=True)
    with (directory / (slot + '.lock')).open('a') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        root = directory / 'roots' / slot
        shutil.rmtree(root, ignore_errors=True)
        shutil.copytree(supplied, root, ignore=shutil.ignore_patterns('__pycache__', '*.pyc'))
        yield root
        # Preserve all intermediates needed by variant independence proofs.
        shutil.rmtree(supplied)
        shutil.copytree(root, supplied)
