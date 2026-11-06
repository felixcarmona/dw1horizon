"""The desktop patcher's logic without its window (docs/patcher.md, "The desktop app"; the window: gui.py).

- where the app keeps its settings and the release packages (per user);
- the four disc slots: which game a file is, checked against redump (the registry the web page uses,
  web/data/discs.json), remembered by path, size and modification time so a second launch does not hash again;
- the release package: the latest GitHub release's horizon-package.tar.gz, every file checked against the release's
  horizon-checksums.json before anything is kept, or a package file the player picks;
- the package's own dwpatch.py, loaded from the package folder: the app applies with the code of that release;
- python_shim(): a frozen app is its own Python for the processes dwpatch starts (`-m tools.derive`, `-c CODE`,
  `SCRIPT.py`).

Standard library only.
"""
import hashlib
import importlib.util
import json
import os
import re
import shutil
import ssl
import sys
import tarfile
import tempfile
import time
import urllib.request

APP_NAME = 'Horizon Patcher'
PACKAGE_ASSET = 'horizon-package.tar.gz'
CHECKSUMS_ASSET = 'horizon-checksums.json'
GAMES = ('us', 'dcb', 'dw2', 'dw2003')                 # the four slots, in the web page's order
GAME_NAMES = dict(us='Digimon World', dcb='Digimon Digital Card Battle', dw2='Digimon World 2',
                  dw2003='Digimon World 3 / 2003')
RAW, DATA = 2352, 2048

HERE = os.path.dirname(os.path.abspath(__file__))


def repository():
    """OWNER/NAME of the GitHub repository whose releases the app downloads: HORIZON_REPOSITORY, else the one the app
    was built from (build.py writes build-info.json from GITHUB_REPOSITORY), else this checkout's origin."""
    if os.environ.get('HORIZON_REPOSITORY'):
        return os.environ['HORIZON_REPOSITORY']
    try:
        with open(resource('tools', 'patcher', 'app', 'build-info.json'), encoding='utf-8') as f:
            return json.load(f)['repository']
    except (OSError, ValueError, KeyError):
        pass
    import subprocess
    try:
        url = subprocess.run(['git', 'remote', 'get-url', 'origin'], cwd=HERE, capture_output=True, text=True,
                             timeout=10).stdout.strip()
    except (OSError, subprocess.SubprocessError):
        url = ''
    m = re.search(r'github\.com[:/]([^/]+/[^/]+?)(?:\.git)?$', url)
    if not m:
        raise Problem('app.noRepository')
    return m[1]


def resource(*parts):
    """A data file of the app: next to this file in a checkout (REPO/...), under the frozen app's data folder."""
    base = getattr(sys, '_MEIPASS', None) or os.path.dirname(os.path.dirname(HERE))
    return os.path.join(base, *parts)


# ---------------------------------------------------------------- the user's folders
def config_dir():
    if os.environ.get('HORIZON_PATCHER_HOME'):
        return os.path.join(os.environ['HORIZON_PATCHER_HOME'], 'config')
    if os.name == 'nt':
        return os.path.join(os.environ.get('APPDATA') or os.path.expanduser('~'), APP_NAME)
    if sys.platform == 'darwin':
        return os.path.expanduser(f'~/Library/Application Support/{APP_NAME}')
    return os.path.join(os.environ.get('XDG_CONFIG_HOME') or os.path.expanduser('~/.config'), 'horizon-patcher')


def cache_dir():
    """The release packages (about 100 MB each): %LOCALAPPDATA% on Windows (not roaming)."""
    if os.environ.get('HORIZON_PATCHER_HOME'):
        return os.path.join(os.environ['HORIZON_PATCHER_HOME'], 'cache')
    if os.name == 'nt':
        return os.path.join(os.environ.get('LOCALAPPDATA') or os.environ.get('APPDATA') or os.path.expanduser('~'),
                            APP_NAME)
    if sys.platform == 'darwin':
        return os.path.expanduser(f'~/Library/Application Support/{APP_NAME}')
    return os.path.join(os.environ.get('XDG_CACHE_HOME') or os.path.expanduser('~/.cache'), 'horizon-patcher')


# ---------------------------------------------------------------- settings
class Config:
    """settings.json: {discs: {game: {path, size, mtime_ns, sha1, release, how}}, output, language, package}."""
    def __init__(self, path=None):
        self.path = path or os.path.join(config_dir(), 'settings.json')
        self.data = {}
        try:
            with open(self.path, encoding='utf-8') as f:
                data = json.load(f)
            if isinstance(data, dict):
                self.data = data
        except (OSError, ValueError):
            pass
        if not isinstance(self.data.get('discs'), dict):
            self.data['discs'] = {}

    def get(self, key, default=None):
        return self.data.get(key, default)

    def set(self, key, value):
        self.data[key] = value
        self.save()

    def save(self):
        os.makedirs(os.path.dirname(self.path), exist_ok=True)
        fd, tmp = tempfile.mkstemp(dir=os.path.dirname(self.path), prefix='.settings-', suffix='.json')
        with os.fdopen(fd, 'w', encoding='utf-8') as f:
            json.dump(self.data, f, indent=1, sort_keys=True)
        os.replace(tmp, self.path)

    def remember_disc(self, game, result):
        self.data['discs'][game] = dict(path=result['path'], image=result['image'], size=result['size'],
                                        mtime_ns=result['mtime_ns'], sha1=result.get('sha1'),
                                        release=result.get('release'), how=result.get('how'))
        self.save()

    def forget_disc(self, game):
        if self.data['discs'].pop(game, None) is not None:
            self.save()

    def remembered_discs(self):
        """{game: (entry, None) when the file is as it was, (entry, reason) when it moved or changed: reason
        'missing' or 'changed'}. A changed entry is forgotten."""
        out = {}
        for game, e in list(self.data['discs'].items()):
            if game not in GAMES or not isinstance(e, dict):
                self.data['discs'].pop(game); continue
            out[game] = (e, file_changed(e))
            if out[game][1]:
                self.data['discs'].pop(game)
        self.save()
        return out


def stamp(path):
    st = os.stat(path)
    return st.st_size, st.st_mtime_ns


def file_changed(entry):
    """None when the remembered image is still there with the same size and modification time, else why not."""
    for key in ('path', 'image'):
        if not entry.get(key) or not os.path.isfile(entry[key]):
            return 'missing'
    try:
        size, mtime = stamp(entry['image'])
    except OSError:
        return 'missing'
    if size != entry.get('size') or mtime != entry.get('mtime_ns'):
        return 'changed'
    return None


# ---------------------------------------------------------------- which disc a file is
_REGISTRY = None


def registry():
    """web/data/discs.json (tools/discs.py web-json): the discs, their other releases and the unsupported ones."""
    global _REGISTRY
    if _REGISTRY is None:
        with open(resource('web', 'data', 'discs.json'), encoding='utf-8') as f:
            _REGISTRY = json.load(f)
    return _REGISTRY


def candidates(boot):
    """[(game, release id, entry, supported)] of the known releases that boot `boot`."""
    reg, out = registry(), []
    for d in reg['discs']:
        if d.get('boot') == boot:
            out.append((d['id'], d['id'], d, True))
    for d in reg['variants']:
        if d.get('boot') == boot:
            out.append((d['game'], d['id'], d, d.get('supported', True)))
    for d in reg['other']:
        if d.get('boot') == boot:
            out.append(('us', d['id'], d, d['id'] == 'jp-rev1'))
    return out


class Problem(Exception):
    """A file that cannot be used: key, the message's key (web/i18n why.*, or the app's own), params for it."""
    def __init__(self, key, game=None, **params):
        super().__init__(key)
        self.key, self.game, self.params = key, game, params


def not_usable(game, entry):
    """The Problem of a release this app knows but cannot use: it names the supported releases of its slot
    (discs.json 'instead', tools/discs.py unsupported()); 'soon' says its support is planned."""
    if entry.get('instead'):
        return Problem('why.notYet' if entry.get('soon') else 'why.useInstead', game, release=entry['title'],
                       instead=list(entry['instead']))
    return Problem('why.unsupported', game, release=(game, entry['id']))


def cue_image(path):
    """The .bin a .cue names (it must name exactly one, and it must exist)."""
    with open(path, 'rb') as f:
        raw = f.read(1 << 16)
    try:
        text = raw.decode('utf-8-sig')
    except UnicodeDecodeError:
        text = raw.decode('latin-1')
    names = []
    for line in text.splitlines():
        m = re.match(r'^\s*FILE\s+(?:"([^"]+)"|(\S+))', line, re.I)
        if m:
            names.append(m[1] or m[2])
    if not names:
        raise Problem('why.notImage')
    if len(names) != 1:
        raise Problem('why.track')
    image = os.path.join(os.path.dirname(os.path.abspath(path)), names[0])
    if not os.path.isfile(image):
        raise Problem('why.cueOnly', file=names[0])
    return image


def boot_and_layout(image):
    """(boot file of SYSTEM.CNF or None, sector size 2352/2048 or None): read as data, nothing of the disc runs."""
    size = os.path.getsize(image)
    for sector, off in ((RAW, 24), (DATA, 0)):
        if size % sector or size < 17 * sector:
            continue
        with open(image, 'rb') as f:
            def data(lba):
                f.seek(lba * sector + off); return f.read(DATA)
            pvd = data(16)
            if pvd[1:6] != b'CD001':
                continue
            ext = int.from_bytes(pvd[158:162], 'little'); ln = int.from_bytes(pvd[166:170], 'little')
            for k in range(min(16, -(-ln // DATA))):
                d = data(ext + k); p = 0
                while p < DATA and d[p]:
                    rec = d[p:p + d[p]]; p += d[p]
                    if rec[33:33 + rec[32]].upper().startswith(b'SYSTEM.CNF'):
                        lba, n = int.from_bytes(rec[2:6], 'little'), int.from_bytes(rec[10:14], 'little')
                        for line in data(lba)[:n].decode('latin-1').splitlines():
                            if line.replace(' ', '').upper().startswith('BOOT='):
                                value = line.split('=', 1)[1].strip()          # cdrom:\\SLUS_010.32;1, cdrom:SLPS_031.01;1
                                return re.split(r'[\\:/]', value)[-1].split(';')[0].strip().upper(), sector
            return None, sector
    return None, None


def sha1_file(path, progress=None, cancel=None):
    h, done, size = hashlib.sha1(), 0, max(1, os.path.getsize(path))
    with open(path, 'rb') as f:
        while True:
            if cancel is not None and cancel.is_set():
                raise Problem('cancelled')
            b = f.read(1 << 22)
            if not b:
                break
            h.update(b); done += len(b)
            if progress: progress(done / size)
    return h.hexdigest()


ARCHIVES = {'.zip': 'zip', '.7z': '7z', '.rar': 'rar', '.gz': 'gz', '.xz': 'xz', '.bz2': 'bz2', '.tar': 'tar'}


def identify(path, progress=None, cancel=None):
    """What a file the player gave is -> {game, release, path, image, size, mtime_ns, sha1, how}: how 'redump' (the
    whole image is the release's dump) or 'files' (a source disc that is not the redump dump: the build checks every
    file it reads from it, as the command line does). Problem for anything that cannot be used."""
    low = path.lower()
    ext = os.path.splitext(low)[1]
    if ext == '.chd':
        raise Problem('why.chd')
    if ext in ARCHIVES or re.search(r'\.(part\d+\.rar|\d{3}|z\d\d)$', low):
        raise Problem('app.archive')
    if ext in ('.ecm', '.pbp'):
        raise Problem('app.convert', format=ext[1:].upper())
    if not os.path.isfile(path):
        raise Problem('app.missingFile')
    image = cue_image(path) if ext == '.cue' else path
    try:
        boot, sector = boot_and_layout(image)
    except OSError as e:
        raise Problem('why.unreadable', error=e.strerror or str(e))
    if not boot:
        raise Problem('why.notImage')
    cands = candidates(boot)
    if not cands:
        raise Problem('why.otherGame', serial=boot.replace('_', '-').replace('.', ''))
    game = cands[0][0]
    size, mtime = stamp(image)
    if game == 'us' and sector == DATA:
        raise Problem('why.isoDw1', game)
    supported = [c for c in cands if c[3]]
    if not supported:
        raise not_usable(game, cands[0][2])
    sized = [c for c in cands if c[2].get('size') == size]
    sha1 = sha1_file(image, progress, cancel)
    hit = next((c for c in cands if c[2].get('sha1') == sha1), None)
    result = dict(game=game, path=path, image=image, size=size, mtime_ns=mtime, sha1=sha1)
    if hit:
        if not hit[3]:
            if hit[1] == 'es-fan':
                raise Problem('why.fanTranslation', game)
            raise not_usable(game, hit[2])
        return dict(result, release=hit[1], how='redump')
    if game == 'us':
        raise Problem('why.badDump', game, game_release=(game, (sized or supported)[0][1]))
    return dict(result, release=supported[0][1], how='files')


def sort_files(paths, progress=None, cancel=None):
    """Many files at once, as the web page takes them: {game: result} (the last usable file of a game wins) and
    [(path, Problem)]. progress(i, n, fraction) while each is checked. The same image given twice counts once."""
    found, problems, seen = {}, [], set()
    paths = list(paths)
    for i, p in enumerate(paths):
        key = os.path.normcase(os.path.abspath(p))
        if key in seen:
            continue
        seen.add(key)
        try:
            r = identify(p, (lambda f, i=i: progress(i, len(paths), f)) if progress else None, cancel)
        except Problem as e:
            if e.key == 'cancelled':
                raise
            problems.append((p, e))
            continue
        found[r['game']] = r
    return found, problems


def source_disc_args(slots):
    """{game: image} for dwpatch: the three source games, by their .bin (a .cue is not an image to the importers)."""
    return {g: slots[g]['image'] for g in GAMES[1:]}


# ---------------------------------------------------------------- the network
def ssl_context():
    """TLS that verifies: the system's certificates; a frozen macOS app has no OpenSSL certificate folder, so the
    bundled certifi (build time only) or the system's /etc/ssl/cert.pem."""
    ctx = ssl.create_default_context()
    if ctx.cert_store_stats().get('x509_ca', 0) == 0:
        try:
            import certifi
            ctx.load_verify_locations(certifi.where())
        except (ImportError, OSError):
            if os.path.exists('/etc/ssl/cert.pem'):
                ctx.load_verify_locations('/etc/ssl/cert.pem')
    return ctx


def _open(url, accept=None, timeout=30):
    req = urllib.request.Request(url, headers={'User-Agent': APP_NAME,
                                               **({'Accept': accept} if accept else {})})
    return urllib.request.urlopen(req, timeout=timeout, context=ssl_context())


def latest_release(repo=None):
    """{tag, version, name, published, assets: {name: {url, size, digest}}} of the latest published release: GitHub's
    API; when it refuses (its limit for computers without an account: 60 requests an hour per address), the
    release page's own redirect, which gives the tag and the download addresses but no sizes or digests (the
    package's files are still checked against horizon-checksums.json)."""
    import urllib.error
    repo = repo or repository()
    try:
        with _open(f'https://api.github.com/repos/{repo}/releases/latest', 'application/vnd.github+json') as r:
            return release_info(json.load(r))
    except urllib.error.HTTPError as e:
        if e.code not in (403, 429):
            raise
    with _open(f'https://github.com/{repo}/releases/latest') as r:
        final = r.geturl()
    m = re.search(r'/releases/tag/([^/?#]+)$', final)
    if not m:
        raise Problem('app.noPackage', tag='latest')
    tag = urllib.request.unquote(m[1])
    return dict(tag=tag, version=tag.lstrip('v'), name=tag, published=None, assets={
        name: dict(url=f'https://github.com/{repo}/releases/download/{tag}/{name}', size=None, digest=None)
        for name in (PACKAGE_ASSET, CHECKSUMS_ASSET)})


def release_info(data):
    assets = {a['name']: dict(url=a['browser_download_url'], size=a.get('size'), digest=a.get('digest'))
              for a in data.get('assets', [])}
    tag = data['tag_name']
    return dict(tag=tag, version=tag.lstrip('v'), name=data.get('name') or tag, published=data.get('published_at'),
                assets=assets)


def version_key(v):
    m = re.match(r'^v?(\d+)\.(\d+)\.(\d+)', v or '')
    return tuple(int(x) for x in m.groups()) if m else (-1,)


def download(url, dest, progress=None, cancel=None, size=None):
    """url to the file dest (via dest.part); progress(done bytes, total or None)."""
    part = dest + '.part'
    with _open(url, timeout=60) as r, open(part, 'wb') as f:
        total = int(r.headers.get('Content-Length') or 0) or size
        done = 0
        while True:
            if cancel is not None and cancel.is_set():
                f.close(); os.remove(part)
                raise Problem('cancelled')
            b = r.read(1 << 20)
            if not b:
                break
            f.write(b); done += len(b)
            if progress: progress(done, total)
    if total and done != total:
        os.remove(part)
        raise Problem('app.downloadShort')
    os.replace(part, dest)
    return dest


# ---------------------------------------------------------------- packages
def _safe_name(name):
    parts = name.split('/')
    return (name and not name.startswith('/') and '\\' not in name and ':' not in parts[0]
            and all(p not in ('', '.', '..') for p in parts))


def unpack_package(archive, dest, checksums=None):
    """horizon-package.tar.gz into the new folder dest. checksums: {file: SHA-256} (horizon-checksums.json
    "package"): every file must be there with its checksum and nothing else; without them, the package file is
    taken as the player gave it (dwpatch still checks the patch and every file it builds). Only regular files and
    folders, no links, no path out of dest. Nothing is left in dest unless everything passed."""
    if os.path.exists(dest):
        raise FileExistsError(dest)
    tmp = dest + '.unpacking'
    shutil.rmtree(tmp, ignore_errors=True)
    os.makedirs(tmp)
    seen = {}
    paths = {}
    try:
        with tarfile.open(archive, 'r:*') as t:
            for m in t:
                name = m.name[2:] if m.name.startswith('./') else m.name
                name = name.rstrip('/')
                if not name or name == '.':
                    continue
                if not _safe_name(name):
                    raise Problem('app.packageBad', detail=f'unsafe path {m.name}')
                # Include implicit parent directories: Tools/a and tools/b also
                # collide when extracted onto a case-insensitive filesystem.
                parts = name.split('/')
                for i in range(1, len(parts) + 1):
                    path = '/'.join(parts[:i])
                    previous = paths.setdefault(path.casefold(), path)
                    if previous != path:
                        raise Problem('app.packageBad', detail=f'case-colliding paths: {previous}, {path}')
                target = os.path.join(tmp, *name.split('/'))
                if m.isdir():
                    os.makedirs(target, exist_ok=True); continue
                if not m.isreg():
                    raise Problem('app.packageBad', detail=f'{m.name} is not a regular file')
                if name in seen:
                    raise Problem('app.packageBad', detail=f'{name} twice')
                os.makedirs(os.path.dirname(target), exist_ok=True)
                h = hashlib.sha256()
                with t.extractfile(m) as src, open(target, 'wb') as out:
                    for b in iter(lambda: src.read(1 << 20), b''):
                        h.update(b); out.write(b)
                seen[name] = h.hexdigest()
        if checksums is not None:
            missing = sorted(set(checksums) - set(seen))
            extra = sorted(set(seen) - set(checksums))
            wrong = sorted(n for n in seen if n in checksums and checksums[n] != seen[n])
            if missing or extra or wrong:
                raise Problem('app.packageBad', detail='; '.join(
                    f'{w}: {", ".join(v[:5])}' for w, v in (('missing', missing), ('not in the release', extra),
                                                             ('different', wrong)) if v))
        if not os.path.isfile(os.path.join(tmp, 'manifest.json')) or not os.path.isfile(os.path.join(tmp, 'dwpatch.py')):
            raise Problem('app.packageBad', detail='no manifest.json or dwpatch.py')
        os.replace(tmp, dest)
    except BaseException:
        shutil.rmtree(tmp, ignore_errors=True)
        raise
    return dest


def package_info(folder):
    """{version, date, commit, folder} of an unpacked package (its manifest.json)."""
    with open(os.path.join(folder, 'manifest.json'), encoding='utf-8') as f:
        m = json.load(f)
    return dict(version=m.get('version'), date=m.get('date'), commit=m.get('commit'), folder=folder)


def packages_root():
    return os.path.join(cache_dir(), 'packages')


def cached_packages():
    """[package_info] of the packages kept, newest version first."""
    out = []
    root = packages_root()
    if os.path.isdir(root):
        for name in os.listdir(root):
            p = os.path.join(root, name)
            if name.endswith(('.unpacking', '.part')) or not os.path.isfile(os.path.join(p, 'manifest.json')):
                continue
            try:
                out.append(dict(package_info(p), name=name))
            except (OSError, ValueError):
                continue
    return sorted(out, key=lambda i: version_key(i['version'] or ''), reverse=True)


def install_release(release, progress=None, cancel=None, keep=2):
    """Download the release's package and checksums, verify, unpack into the cache -> package_info. Keeps the
    newest `keep` packages."""
    a = release['assets']
    if PACKAGE_ASSET not in a or CHECKSUMS_ASSET not in a:
        raise Problem('app.noPackage', tag=release['tag'])
    root = packages_root()
    os.makedirs(root, exist_ok=True)
    dest = os.path.join(root, re.sub(r'[^A-Za-z0-9._-]', '_', release['tag']))
    if os.path.isfile(os.path.join(dest, 'manifest.json')):
        return package_info(dest)
    shutil.rmtree(dest, ignore_errors=True)
    work = tempfile.mkdtemp(prefix='download-', dir=root)
    try:
        sums = download(a[CHECKSUMS_ASSET]['url'], os.path.join(work, CHECKSUMS_ASSET), cancel=cancel)
        with open(sums, encoding='utf-8') as f:
            checksums = json.load(f)
        if not isinstance(checksums, dict) or not isinstance(checksums.get('package'), dict):
            raise Problem('app.packageBad', detail='horizon-checksums.json has no package list')
        tar = download(a[PACKAGE_ASSET]['url'], os.path.join(work, PACKAGE_ASSET), progress, cancel,
                       a[PACKAGE_ASSET].get('size'))
        digest = a[PACKAGE_ASSET].get('digest') or ''
        if digest.startswith('sha256:'):
            h = hashlib.sha256()
            with open(tar, 'rb') as f:
                for b in iter(lambda: f.read(1 << 20), b''):
                    h.update(b)
            if h.hexdigest() != digest[7:]:
                raise Problem('app.packageBad', detail='the download is not the release asset (SHA-256)')
        unpack_package(tar, dest, checksums['package'])
    finally:
        shutil.rmtree(work, ignore_errors=True)
    prune(keep)
    return package_info(dest)


def install_file(archive, checksums_path=None):
    """A package file the player picked (offline): checked against a horizon-checksums.json next to it when there
    is one -> package_info."""
    sums = checksums_path or os.path.join(os.path.dirname(os.path.abspath(archive)), CHECKSUMS_ASSET)
    checksums = None
    if os.path.isfile(sums):
        with open(sums, encoding='utf-8') as f:
            checksums = json.load(f).get('package')
    root = packages_root()
    os.makedirs(root, exist_ok=True)
    h = hashlib.sha256()
    with open(archive, 'rb') as f:
        for b in iter(lambda: f.read(1 << 20), b''):
            h.update(b)
    dest = os.path.join(root, 'file-' + h.hexdigest()[:16])
    if not os.path.isfile(os.path.join(dest, 'manifest.json')):
        shutil.rmtree(dest, ignore_errors=True)
        unpack_package(archive, dest, checksums)
    return dict(package_info(dest), verified=checksums is not None)


def prune(keep=2):
    for info in cached_packages()[keep:]:
        shutil.rmtree(info['folder'], ignore_errors=True)


# ---------------------------------------------------------------- the package's patcher
SIBLINGS = ('dwpatch', 'isowriter', 'fontcopy')


def load_patcher(folder):
    """The package's own dwpatch.py as a module (its isowriter.py and fontcopy.py with it). Problem when the
    package's patcher predates the desktop interface (GUI_API)."""
    for name in SIBLINGS:
        sys.modules.pop(name, None)
    name = 'dwpatch'
    spec = importlib.util.spec_from_file_location(name, os.path.join(folder, 'dwpatch.py'))
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    try:
        spec.loader.exec_module(mod)
    except Exception:
        sys.modules.pop(name, None)
        raise
    if getattr(mod, 'GUI_API', 0) != 1 or not hasattr(mod, 'apply_disc'):
        raise Problem('app.packageOld', version=package_info(folder)['version'])
    return mod


# ---------------------------------------------------------------- space and folders
def free_bytes(folder):
    while folder and not os.path.isdir(folder):
        parent = os.path.dirname(folder)
        if parent == folder:
            break
        folder = parent
    try:
        return shutil.disk_usage(folder).free
    except OSError:
        return None


TEMP_NEED = 2 * 1024 ** 3                    # the build tree (about 700 MB) with room to spare
OUTPUT_NEED = 1024 ** 3                      # the patched .bin (about 400 MB) and its .part while it is written


def space_problems(output):
    out = []
    t = free_bytes(tempfile.gettempdir())
    if t is not None and t < TEMP_NEED:
        out.append(('app.spaceTemp', dict(folder=tempfile.gettempdir(), gb=f'{TEMP_NEED / 1024 ** 3:.0f}')))
    o = free_bytes(output)
    if o is not None and o < OUTPUT_NEED:
        out.append(('app.spaceOutput', dict(folder=output, gb=f'{OUTPUT_NEED / 1024 ** 3:.0f}')))
    return out


def default_output(base_path):
    """The command line's: a "patched" folder next to the player's Digimon World disc."""
    return os.path.join(os.path.dirname(os.path.abspath(base_path)), 'patched')


def open_folder(path):
    import subprocess
    if os.name == 'nt':
        os.startfile(path)                               # noqa: (Windows only)
    elif sys.platform == 'darwin':
        subprocess.Popen(['open', path])
    else:
        subprocess.Popen(['xdg-open', path])


def clock(s):
    s = int(s + 0.5)
    return f'{s // 3600}:{s // 60 % 60:02d}:{s % 60:02d}' if s >= 3600 else f'{s // 60}:{s % 60:02d}'


# ---------------------------------------------------------------- the frozen app as Python
def python_shim(argv=None):
    """A frozen app has no python executable: dwpatch starts sys.executable as Python (`-m tools.derive ...` on
    macOS and Linux, `-c GATE tools.derive ...` on Windows, `TOOL.py ...` for the Japanese disc's localize tool).
    When argv is one of those, run it as CPython would (sys.argv, sys.path[0], the __main__ module) and return the
    exit code; else None (the app's own start). multiprocessing.freeze_support() must have run before this."""
    argv = sys.argv[1:] if argv is None else argv
    if not argv or not getattr(sys, 'frozen', False) and not os.environ.get('HORIZON_SHIM_TEST'):
        return None
    flags = []
    while argv and argv[0] in ('-u', '-B', '-E', '-s', '-S', '-I', '-X'):
        flags.append(argv[0]); argv = argv[1:]
        if flags[-1] == '-X' and argv: argv = argv[1:]
    if not argv:
        return None
    first = argv[0]
    if first not in ('-c', '-m') and not (first.endswith('.py') and os.path.isfile(first)):
        return None
    if os.environ.get('PYTHONUNBUFFERED') or '-u' in flags:
        for s in (sys.stdout, sys.stderr):
            if s is not None:
                try: s.reconfigure(write_through=True)
                except (AttributeError, ValueError): pass
    for s in (sys.stdout, sys.stderr):                   # (dwpatch reads its children's output as UTF-8)
        if s is not None and os.environ.get('PYTHONUTF8') == '1':
            try: s.reconfigure(encoding='utf-8', errors='backslashreplace')
            except (AttributeError, ValueError): pass
    if sys.stderr is None and sys.stdout is not None:    # (a windowed child: its errors go where its output goes)
        sys.stderr = sys.stdout
    import runpy
    import types
    try:
        if first == '-c':
            if len(argv) < 2:
                return 2
            sys.argv = ['-c'] + argv[2:]
            # CPython puts '' (the current folder) first; the folder itself here: PyInstaller sets
            # multiprocessing.process.ORIGINAL_DIR to None, and a spawned worker would get None for that entry
            # (seen on Windows: derive's workers hung under the -c gate).
            sys.path.insert(0, os.getcwd())
            main = types.ModuleType('__main__')
            main.__builtins__ = __builtins__
            sys.modules['__main__'] = main
            exec(compile(argv[1], '<string>', 'exec'), main.__dict__)
        elif first == '-m':
            if len(argv) < 2:
                return 2
            sys.argv = [argv[1]] + argv[2:]
            sys.path.insert(0, os.getcwd())
            runpy.run_module(argv[1], run_name='__main__', alter_sys=True)
        else:
            script = os.path.abspath(first)
            sys.argv = [first] + argv[1:]
            sys.path.insert(0, os.path.dirname(script))
            runpy.run_path(script, run_name='__main__')
    except SystemExit as e:
        code = e.code
        if code is None:
            return 0
        if isinstance(code, int):
            return code
        print(code, file=sys.stderr)
        return 1
    except BaseException:
        import traceback
        traceback.print_exc()
        return 1
    finally:
        for s in (sys.stdout, sys.stderr):
            try:
                if s is not None: s.flush()
            except (OSError, ValueError):
                pass
    return 0
