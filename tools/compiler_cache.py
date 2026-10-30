#!/usr/bin/env python3
"""Docker-side C object cache: key the compiler's actual preprocessed input.

Called only by native_build.py's optional cache path. The preprocessing pass reads
all headers and expands all make defines; a hit restores both object and dependency
file. No make timestamp is trusted. Cache failures fall back to the real compiler.
"""
import hashlib
import json
import os
from pathlib import Path
import subprocess
import shlex
import sys
import tempfile


def sha(data):
    return hashlib.sha256(data).hexdigest()


def publish(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, name = tempfile.mkstemp(dir=path.parent, prefix='.tmp-')
    try:
        with os.fdopen(fd, 'wb') as f:
            f.write(data)
        os.replace(name, path)
    finally:
        if os.path.exists(name):
            os.unlink(name)


def main():
    compiler, *args = sys.argv[1:]
    if '-c' not in args or '-o' not in args or '-MF' not in args:
        return subprocess.call([compiler, *args])
    output = Path(args[args.index('-o')+1])
    dep = Path(args[args.index('-MF')+1])
    namespace = os.environ.get('DW_COMPILER_NAMESPACE')
    identity = json.dumps([os.environ['DW_COMPILER_IMAGE'], compiler, args, str(Path.cwd()),
                           namespace, sha(Path(__file__).read_bytes())], sort_keys=True).encode()
    base = Path(os.environ.get('DW_COMPILER_CACHE', '/compiler-cache'))
    direct = base / 'direct' / sha(identity)
    if namespace:
        try:
            record = json.loads(direct.read_bytes())
            previous = record['record']
            if sha(json.dumps(previous, sort_keys=True).encode()) != record['sha256']:
                raise ValueError('corrupt compiler dependency index')
            if all(sha(Path(p).read_bytes()) == h for p, h in previous['inputs']):
                folder = base / previous['entry'][:2] / previous['entry'][2:]
                meta = json.loads((folder / 'manifest.json').read_bytes())
                obj, deps = (folder / 'object').read_bytes(), (folder / 'deps').read_bytes()
                if sha(obj) == meta['object'] and sha(deps) == meta['deps']:
                    output.parent.mkdir(parents=True, exist_ok=True)
                    output.write_bytes(obj)
                    dep.write_bytes(deps)
                    return 0
        except (OSError, ValueError, KeyError, TypeError):
            pass
    prep = []
    i = 0
    while i < len(args):
        if args[i] in ('-o', '-MF', '-MT', '-MQ'):
            i += 2
            continue
        if args[i] in ('-MMD', '-MD', '-MP'):
            i += 1
            continue
        prep.append('-E' if args[i] == '-c' else args[i])
        i += 1
    p = subprocess.run([compiler, *prep, '-MMD', '-MP', '-MF', str(dep), '-MT', str(output)], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    if p.returncode:
        # Preserve the compiler's ordinary diagnostics and exit status.
        return subprocess.call([compiler, *args])
    if b'.incbin' in p.stdout or b'.include' in p.stdout:
        return subprocess.call([compiler, *args])
    try:
        rule = dep.read_text().replace(chr(92) + chr(10), '').split(':', 1)[1].split(chr(10), 1)[0]
        dependencies = [[p, sha(Path(p).read_bytes())] for p in shlex.split(rule)]
    except (OSError, ValueError, IndexError):
        return subprocess.call([compiler, *args])
    cache_key = sha(identity + b'\0' + p.stdout + json.dumps(dependencies).encode())
    folder = Path(os.environ.get('DW_COMPILER_CACHE', '/compiler-cache')) / cache_key[:2] / cache_key[2:]
    try:
        meta = json.loads((folder / 'manifest.json').read_bytes())
        obj, deps = (folder / 'object').read_bytes(), (folder / 'deps').read_bytes()
        if sha(obj) == meta['object'] and sha(deps) == meta['deps']:
            output.parent.mkdir(parents=True, exist_ok=True)
            output.write_bytes(obj)
            dep.write_bytes(deps)
            sys.stderr.buffer.write(p.stderr)
            return 0
    except (OSError, ValueError, KeyError, TypeError):
        pass
    code = subprocess.call([compiler, *args])
    if code:
        return code
    try:
        obj, deps = output.read_bytes(), dep.read_bytes()
        publish(folder / 'object', obj)
        publish(folder / 'deps', deps)
        publish(folder / 'manifest.json', json.dumps(dict(object=sha(obj), deps=sha(deps))).encode())
        if namespace:
            rule = deps.decode().replace(chr(92) + chr(10), '').split(':', 1)[1].split(chr(10), 1)[0]
            inputs = [[p, sha(Path(p).read_bytes())] for p in shlex.split(rule)]
            if inputs:
                record = dict(entry=cache_key, inputs=inputs)
                publish(direct, json.dumps(dict(record=record, sha256=sha(json.dumps(record, sort_keys=True).encode()))).encode())
    except OSError:
        pass
    return 0


if __name__ == '__main__':
    sys.exit(main())
