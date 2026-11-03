"""The desktop app's self-test, for CI on the frozen app (no discs, no window unless --gui):

    Horizon Patcher --self-test [--package DIR | --download] [--gui] [--report FILE]

1. this Python (frozen or not, UTF-8 mode);
2. the app as Python: `-c CODE` (argv, UTF-8 output), `-m MODULE` whose module spawns multiprocessing workers (what
   tools/derive does on Windows and macOS), `SCRIPT.py`;
3. dwpatch.derive_run itself on a stand-in tools/derive (its Windows gate and job object, or its POSIX process
   group): the stand-in spawns workers and writes a manifest;
4. TLS: a certificate store that is not empty;
5. with a package (--package, or --download: the latest release, verified): every standard-library module its
   Python files import can be imported here; dwpatch info; check and apply_disc on a file that is not a disc give
   the player's message, not a crash; the real tools/derive starts and stops at its first missing disc file
   (not at a missing module);
6. --gui: the window is made and closed.
Exit 0 when everything passed; each check's line goes to stdout and to --report.
"""
import ast
import io
import json
import os
import shutil
import subprocess
import sys
import tempfile
import textwrap
import time

import desktop
import dwpatch as app_dwpatch                    # (the app's own copy: bundled, used for the stand-in derive run)

LINES = []
REPORT = None


def say(text):
    LINES.append(text)
    for stream in (sys.__stdout__, sys.stdout):
        try:
            if stream is not None:
                stream.write(text + '\n'); stream.flush()
                break
        except (OSError, ValueError, AttributeError):
            pass
    if REPORT:
        with open(REPORT, 'a', encoding='utf-8') as f:
            f.write(text + '\n')


def child(argv, cwd=None, stdin=None, timeout=120):
    env = dict(os.environ, PYTHONUTF8='1', PYTHONUNBUFFERED='1', PYTHONDONTWRITEBYTECODE='1')
    try:
        r = subprocess.run([sys.executable, *argv], cwd=cwd, env=env, input=stdin, stdout=subprocess.PIPE,
                           stderr=subprocess.STDOUT, timeout=timeout)
    except subprocess.TimeoutExpired as e:
        raise AssertionError(f'no answer in {timeout} s; its output: {(e.output or b"").decode("utf-8", "replace")}')
    return r.returncode, r.stdout.decode('utf-8', 'replace')


WORKER = '''
import multiprocessing, os, sys

def square(conn):
    n = conn.recv()
    conn.send((n * n, os.getpid()))
    conn.close()

def run(count):
    ctx = multiprocessing.get_context('spawn')
    out = []
    for n in range(count):
        mine, theirs = ctx.Pipe()
        p = ctx.Process(target=square, args=(theirs,), daemon=True)
        p.start(); theirs.close()
        mine.send(n)
        out.append(mine.recv()); p.join(30)
        if p.exitcode != 0: raise SystemExit(f'worker exit code {p.exitcode}')
    return out
'''

MAIN = '''
import json, os, sys
from {pkg} import work
results = work.run(3)
squares = [r[0] for r in results]
assert squares == [0, 1, 4], squares
assert all(pid != os.getpid() for _, pid in results)
print('spawned', json.dumps(dict(squares=squares, argv=sys.argv[1:], utf8=sys.flags.utf8_mode)), flush=True)
'''

DERIVE = '''
import json, os, sys
from tools.derive import work
squares = [r[0] for r in work.run(2)]
print('derive stand-in: workers', squares, flush=True)
a = sys.argv[1:]
out = a[a.index('--out') + 1]
os.makedirs(os.path.join(out, 'derived'), exist_ok=True)
with open(os.path.join(out, 'derived', 'manifest.json'), 'w') as f:
    json.dump(dict(files={}, steps={}, argv=a), f)
print('derive fake: 1 files, 0.1 s', flush=True)
'''


def check(name, fn):
    t0 = time.time()
    try:
        detail = fn()
    except BaseException as e:                 # noqa: every failure is reported
        import traceback
        say(f'FAIL {name}: {type(e).__name__}: {e}')
        say(textwrap.indent(traceback.format_exc(), '    '))
        return False
    say(f'ok   {name} ({time.time() - t0:.1f} s){": " + detail if detail else ""}')
    return True


def stdlib_imports(folder):
    names = set()
    for dp, _, fs in os.walk(folder):
        for f in fs:
            if not f.endswith('.py'):
                continue
            try:
                tree = ast.parse(open(os.path.join(dp, f), 'rb').read())
            except (SyntaxError, ValueError):
                continue
            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    names |= {a.name for a in node.names}
                elif isinstance(node, ast.ImportFrom) and node.module and not node.level:
                    names.add(node.module)
    top = set(sys.stdlib_module_names)
    platform_only = {'winreg', 'msvcrt', '_winapi', 'winsound', 'nt', 'posix', 'pwd', 'grp', 'fcntl', 'termios',
                     'resource', 'tty', 'pty', 'curses', 'readline', '_posixsubprocess', 'syslog', '_scproxy'}
    return sorted(n for n in names if n.split('.')[0] in top and n.split('.')[0] not in platform_only)


def main(argv):
    global REPORT
    package = None
    if '--report' in argv:
        REPORT = argv[argv.index('--report') + 1]
        open(REPORT, 'w').close()
    if sys.stdout is None:
        sys.stdout = io.StringIO()
    if sys.stderr is None:
        sys.stderr = io.StringIO()
    work = tempfile.mkdtemp(prefix='horizon-selftest-')
    ok = True
    try:
        import platform
        say(f'Horizon Patcher self-test: Python {sys.version.split()[0]} on {sys.platform} {platform.machine()}, '
            f'frozen={bool(getattr(sys, "frozen", False))}, utf8_mode={sys.flags.utf8_mode}, {sys.executable}')

        def utf8():
            assert sys.flags.utf8_mode or not getattr(sys, 'frozen', False), 'the frozen app must run in UTF-8 mode'
        ok &= check('UTF-8 mode', utf8)

        def c_code():
            code, out = child(['-c', 'import sys,json; print(json.dumps(sys.argv[1:]))', 'two words', 'ü'])
            assert code == 0 and json.loads(out.strip().splitlines()[-1]) == ['two words', 'ü'], (code, out)
        ok &= check('python -c', c_code)

        pkg = os.path.join(work, 'spaced folder', 'hpst')
        os.makedirs(pkg)
        open(os.path.join(pkg, '__init__.py'), 'w').close()
        open(os.path.join(pkg, 'work.py'), 'w').write(WORKER)
        open(os.path.join(pkg, '__main__.py'), 'w').write(MAIN.format(pkg='hpst'))

        def m_module():
            code, out = child(['-m', 'hpst', 'x y'], cwd=os.path.dirname(pkg))
            assert code == 0 and 'spawned' in out, (code, out)
            return out.strip().splitlines()[-1]
        ok &= check('python -m, spawning workers', m_module)

        def script():
            path = os.path.join(work, 'spaced folder', 'tool script.py')
            open(path, 'w').write('import sys; print("script", sys.argv[1:])')
            code, out = child([path, 'arg'])
            assert code == 0 and "script ['arg']" in out, (code, out)
        ok &= check('python SCRIPT.py', script)

        def derive_run():
            root = os.path.join(work, 'derive root with spaces')
            d = os.path.join(root, 'tools', 'derive')
            os.makedirs(os.path.join(d, 'recipes'))
            open(os.path.join(root, 'tools', '__init__.py'), 'w').close()
            open(os.path.join(d, '__init__.py'), 'w').close()
            open(os.path.join(d, 'work.py'), 'w').write(WORKER)
            open(os.path.join(d, '__main__.py'), 'w').write(DERIVE)
            json.dump({'environment': {'NAME': 'standin'}}, open(os.path.join(d, 'recipes', 'standin.json'), 'w'))
            buf = io.StringIO()
            saved = sys.stdout
            sys.stdout = buf
            import threading
            app_dwpatch.CANCEL = threading.Event()               # (a hang becomes a failure, its processes killed)
            timer = threading.Timer(180, app_dwpatch.CANCEL.set)
            timer.start()
            try:
                man, out = app_dwpatch.derive_run(root, 'standin', os.path.join(root, 'facts.json'), jobs=2,
                                                  log=os.path.join(work, 'derive.log'))
            finally:
                sys.stdout = saved
                timer.cancel()
                app_dwpatch.CANCEL = None
            log = open(os.path.join(work, 'derive.log'), encoding='utf-8').read()
            assert 'workers [0, 1]' in log and man['files'] == {}, log
            return ' '.join(log.split())[:120]
        ok &= check('dwpatch.derive_run on a stand-in derive', derive_run)

        def tls():
            n = desktop.ssl_context().cert_store_stats().get('x509_ca', 0)
            ctx = desktop.ssl_context()
            assert n or ctx.get_ca_certs() or os.name == 'nt', 'no CA certificates'
            return f'{n} CA certificates loaded'
        ok &= check('TLS certificates', tls)

        if '--download' in argv:
            os.environ['HORIZON_PATCHER_HOME'] = os.path.join(work, 'home')

            def download():
                nonlocal package
                latest = desktop.latest_release()
                package = desktop.install_release(latest)['folder']
                return f'{latest["tag"]}, every file checked against horizon-checksums.json'
            ok &= check('download the latest release', download)
        elif '--package' in argv:
            package = argv[argv.index('--package') + 1]

        if package:
            def imports():
                names = stdlib_imports(package)
                bad = []
                import importlib
                for n in names:
                    try:
                        importlib.import_module(n)
                    except ImportError as e:
                        bad.append(f'{n} ({e})')
                assert not bad, 'missing: ' + ', '.join(bad)
                return f'{len(names)} standard-library modules the package imports'
            ok &= check('the package\'s imports', imports)

            dw = load_any(package)

            def info():
                buf = io.StringIO(); saved = sys.stdout; sys.stdout = buf
                try:
                    code = dw.main(['info', '--release', package])
                finally:
                    sys.stdout = saved
                assert code == 0 and 'Takes:' in buf.getvalue(), buf.getvalue()
                return buf.getvalue().splitlines()[0]
            ok &= check('dwpatch info', info)

            fake = os.path.join(work, 'not a disc.bin')
            open(fake, 'wb').write(b'\0' * 4096)

            def check_fake():
                try:
                    dw.cmd_check(type('A', (), dict(disc=fake, release=package))())
                except dw.PatchError as e:
                    return str(e)[:100]
                raise AssertionError('a file that is not a disc was accepted')
            ok &= check('dwpatch check refuses a file that is not a disc', check_fake)

            def apply_fake():
                api = dw if hasattr(dw, 'apply_disc') else app_dwpatch
                try:
                    api.apply_disc(fake, dict(dcb=fake, dw2=fake, dw2003=fake),
                                   output=os.path.join(work, 'out'), release=package)
                except api.PatchError as e:
                    return ('package' if api is dw else 'app') + f' dwpatch: {str(e)[:100]}'
                raise AssertionError('apply took a file that is not a disc')
            ok &= check('apply_disc refuses it with the player\'s message', apply_fake)

            def real_derive():
                root = os.path.join(work, 'bundle')
                shutil.copytree(os.path.join(package, 'bundle'), root)
                buf = io.StringIO(); saved = sys.stdout; sys.stdout = buf
                try:
                    dw.derive_run(root, 'everything', os.path.join(root, 'exe-facts.json'), jobs=2,
                                  log=os.path.join(work, 'real-derive.log'))
                except dw.PatchError:
                    pass
                finally:
                    sys.stdout = saved
                log = open(os.path.join(work, 'real-derive.log'), encoding='utf-8').read()
                assert 'No module named' not in log and 'ModuleNotFoundError' not in log and log.strip(), log[-2000:]
                return ' '.join(log.split())[-120:]
            ok &= check('the package\'s tools/derive starts (and stops: no disc files)', real_derive)

        if '--gui' in argv:
            def gui():
                os.environ['HORIZON_PATCHER_HOME'] = os.path.join(work, 'gui-home')
                import tkinter as tk
                import gui as g
                root = tk.Tk()
                app = g.App.__new__(g.App)
                app.tk, app.root = tk, root
                app.set_icon()
                app.__init__(root, desktop.Config())
                for lang in g.LANGS:
                    app.lang_var.set(g.LANGS[lang]); app._language()
                    root.update()
                    missing = [k for k in json.load(open(desktop.resource('tools', 'patcher', 'app', 'i18n.json'),
                                                         encoding='utf-8'))['en'] if app.t(k) == k]
                    assert not missing, (lang, missing)
                root.destroy()
                return f'{len(g.LANGS)} languages'
            ok &= check('the window', gui)
    finally:
        shutil.rmtree(work, ignore_errors=True)
    say('PASSED' if ok else 'FAILED')
    return 0 if ok else 1


def load_any(folder):
    """The package's dwpatch even when it predates the desktop interface (an older release: info and check)."""
    try:
        return desktop.load_patcher(folder)
    except desktop.Problem:
        return sys.modules.get('dwpatch_old') or _load_plain(folder)


def _load_plain(folder):
    import importlib.util
    for name in desktop.SIBLINGS:
        sys.modules.pop(name, None)
    spec = importlib.util.spec_from_file_location('dwpatch_old', os.path.join(folder, 'dwpatch.py'))
    mod = importlib.util.module_from_spec(spec)
    sys.modules['dwpatch_old'] = mod
    spec.loader.exec_module(mod)
    return mod
