"""The web engine's Python side (runs in Pyodide in the page's workers, and natively in build_engine.py / record.py):
the player's disc to the build tree, and the disc writer, with the release's own dwpatch.py and isowriter.py.

  identify(rel, disc)                    -> (base key, title): the release's check of the player's disc (identify_base)
  extract(rel, disc, key, put, work)     every file of the manifest's `extract` list, from the player's disc as the USA
                                          one (BaseDisc.data), handed to put(usa path, bytes)
  write_disc(rel, disc, key, holes, out) the patched image (build_disc3) into `out`, an object with write(bytes)

The patcher runs its tools as processes (the localize tool of a base whose files carry baked text: jp1); a browser has
none, so run_tool runs one in this process (runpy, as tools/derive's runner does: argv, sys.path, the environment and
the working directory put back after it).
"""
import contextlib
import hashlib
import io
import json
import os
import runpy
import subprocess
import sys


def dwpatch(rel):
    if rel not in sys.path:
        sys.path.insert(0, rel)
    import dwpatch as P
    return P


def manifest(rel):
    with open(os.path.join(rel, 'manifest.json'), encoding='utf-8') as f:
        return json.load(f)


class _Done:
    def __init__(self, code, out=''):
        self.returncode, self.stdout = code, out


def run_tool(argv, env=None, **_):
    """subprocess.run([python, SCRIPT, args...]) in this process."""
    if len(argv) < 2 or not str(argv[1]).endswith('.py'):
        raise RuntimeError(f'no processes here: {argv}')
    script, args = str(argv[1]), [str(a) for a in argv[2:]]
    saved = sys.argv[:], sys.path[:], os.getcwd(), dict(os.environ), set(sys.modules)
    root = os.path.dirname(os.path.abspath(script))
    code = 0
    buf = io.StringIO()
    try:
        sys.argv = [script] + args
        sys.path.insert(0, root)
        if env:
            os.environ.clear(); os.environ.update({k: v for k, v in env.items() if k in ('PATH', 'HOME', 'LANG')})
        with contextlib.redirect_stdout(buf), contextlib.redirect_stderr(buf):
            try:
                runpy.run_path(script, run_name='__main__')
            except SystemExit as e:
                code = 0 if e.code in (None, 0) else 1
    finally:
        sys.argv[:], sys.path[:] = saved[0], saved[1]
        os.chdir(saved[2])
        os.environ.clear(); os.environ.update(saved[3])
        for name in [n for n in sys.modules if n not in saved[4]]:
            f = getattr(sys.modules[name], '__file__', None) or ''
            if f.startswith(root) or f.startswith(os.path.dirname(os.path.dirname(root))):
                del sys.modules[name]
    if code:
        print(buf.getvalue()[-3000:])
    return _Done(code, buf.getvalue())


def identify(rel, disc):
    P = dwpatch(rel)
    m = manifest(rel)
    key, path, _ = P.identify_base(disc, m['bases'])
    return key, m['bases'][key]['title']


def base_disc(rel, disc, key, work, source_discs=None):
    P = dwpatch(rel)
    m = manifest(rel)
    mp = m['bases'][key].get('mapping')
    mapping = None
    if mp:
        with open(os.path.join(rel, mp), encoding='utf-8') as f:
            mapping = json.load(f)
    os.makedirs(work, exist_ok=True)
    return P.BaseDisc(key, P.resolve_bin(disc), mapping, tool_root=os.path.join(rel, 'bundle'), work=work, source_discs=source_discs)


def extract(rel, disc, key, put, work, progress=None, source_discs=None):
    """The `extract` files of the release from the player's disc (by USA path) to put(path, bytes)."""
    P = dwpatch(rel)
    m = manifest(rel)
    base = base_disc(rel, disc, key, work, source_discs)
    saved = P.subprocess.run
    P.subprocess.run = run_tool                      # (the localize tool: in this process)
    try:
        n = len(m['extract'])
        for i, q in enumerate(m['extract']):
            put(q, base.data(q))
            if progress and (i % 25 == 0 or i == n - 1):
                progress(i + 1, n)
    finally:
        P.subprocess.run = saved
    return base


def check_holes(rel, key, read):
    """[disc path] of the holes whose bytes (read(disc path) -> bytes) are not the release's for this base."""
    m = manifest(rel)
    v = m['variants'][m['default']]
    bad = []
    for h in v['holes']:
        try:
            b = read(h['file'])
        except (OSError, KeyError):
            b = None
        if b is None or hashlib.sha1(b).hexdigest() != h.get('sha1_by_base', {}).get(key, h['sha1']):
            bad.append(h['file'])
    return bad


def write_disc(rel, disc, key, holes, out, work, localized=None, source_discs=None):
    """build_disc3 into `out` (stream: write(bytes)); holes {disc path: object with size, read() and [a:b]} ->
    (SHA-1 of the image, the release's SHA-1 for this base or None, size). localized: the folder the localize tool
    wrote at extract time (BaseDisc.localized reads it instead of running the tool again)."""
    P = dwpatch(rel)
    m = manifest(rel)
    v = m['variants'][m['default']]
    p = P.read_payload3(P.read_patch_file(rel, v))
    base = base_disc(rel, disc, key, work, source_discs)
    if localized:
        base._loc = localized
    by_id = {h['id']: holes[h['file']] for h in v['holes']}
    saved = P.subprocess.run
    P.subprocess.run = run_tool
    try:
        sha, pl = P.build_disc3(p, base, by_id, out, None, progress=False)
    finally:
        P.subprocess.run = saved
    want = v['outputs'].get(key, {}).get('sha1')
    return sha, want, pl.total * 2352
