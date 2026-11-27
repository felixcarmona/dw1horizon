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
try:
    from . import discformats
except ImportError:
    import discformats

import hashlib
import importlib.util
import json
import logging
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
PACKAGE_RECORD = '.verified-package.json'
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
                                        release=result.get('release'), how=result.get('how'),
                                        source_stamp=result.get('source_stamp'))
        self.save()

    def forget_disc(self, game):
        if self.data['discs'].pop(game, None) is not None:
            self.save()

    def remembered_discs(self):
        """{game: (entry, None) when the file is as it was, (entry, reason) when it moved or changed: reason
        'missing', 'changed' or 'convert' (a PBP needs extraction again)}. A changed entry is forgotten."""
        out = {}
        for game, e in list(self.data['discs'].items()):
            if game not in GAMES or not isinstance(e, dict):
                self.data['discs'].pop(game); continue
            out[game] = (e, file_changed(e))
            if out[game][1] in ('missing', 'changed'):
                self.data['discs'].pop(game)
        self.save()
        return out


def stamp(path):
    st = os.stat(path)
    return st.st_size, st.st_mtime_ns


def file_changed(entry):
    """None when the remembered image is still there with the same size and modification time, else why not."""
    try:
        if entry.get('source_stamp') is not None:
            if list(stamp(entry['path'])) != entry['source_stamp']:
                return 'changed'
            if not os.path.isfile(entry['image']):
                return 'convert'
        for key in ('path', 'image'):
            if not entry.get(key) or not os.path.isfile(entry[key]):
                return 'missing'
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


CONVERSIONS = discformats.ConversionCache()


def converted_image(path, progress=None, cancel=None):
    try:
        return CONVERSIONS.convert(path, cache_dir(), progress, cancel)
    except discformats.Cancelled:
        raise Problem('cancelled')
    except discformats.FormatError as e:
        if str(e).startswith('CHD not supported: '):
            raise Problem('app.chdUnsupported', reason=str(e).split(': ', 1)[1]) from e
        key = {'CHD space': 'app.chdSpace', 'CHD changed': 'app.changed',
               'PBP multi-disc': 'app.pbpMulti', 'PBP space': 'app.pbpSpace',
               'PBP changed': 'app.changed'}.get(str(e), 'app.pbpEncrypted')
        raise Problem(key, **({'path': path} if key == 'app.changed' else {})) from e


def identify(path, progress=None, cancel=None, converting=None):
    """What a file the player gave is -> {game, release, path, image, size, mtime_ns, sha1, how}: how 'redump' (the
    whole image is the release's dump) or 'files' (a source disc that is not the redump dump: the build checks every
    file it reads from it, as the command line does). Problem for anything that cannot be used."""
    if not os.path.isfile(path):
        raise Problem('app.missingFile')
    kind = discformats.sniff(path)
    if kind == 'archive':
        raise Problem('app.archive')
    if kind == 'ecm':
        raise Problem('app.convert', format='ECM')
    if kind in ('pbp', 'chd'):
        def tick(f):
            if converting:
                converting(path, f)
        source_stamp = list(stamp(path))
        try:
            image = converted_image(path, tick, cancel)
            result = identify(image, progress, cancel)
            if list(stamp(path)) != source_stamp:
                raise Problem('app.changed', path=path)
            return dict(result, path=path, source_stamp=source_stamp)
        except BaseException:
            CONVERSIONS.discard(path)
            raise
    image = cue_image(path) if kind == 'cue' else path
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


def sort_files(paths, progress=None, cancel=None, converting=None):
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
            r = identify(p, (lambda f, i=i: progress(i, len(paths), f)) if progress else None, cancel, converting)
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
                # Include implicit parent directories: Folder/a and folder/b also
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
            if name.endswith(('.unpacking', '.part', '.previous')) or not os.path.isfile(os.path.join(p, 'manifest.json')):
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
    previous = dest + '.previous'
    # Recover if the app stopped between the two directory renames.
    if not os.path.exists(dest) and os.path.isdir(previous):
        os.replace(previous, dest)
    cached = os.path.isfile(os.path.join(dest, 'manifest.json'))
    if not cached:
        shutil.rmtree(dest, ignore_errors=True)
    work = tempfile.mkdtemp(prefix='download-', dir=root)
    try:
        sums = download(a[CHECKSUMS_ASSET]['url'], os.path.join(work, CHECKSUMS_ASSET), cancel=cancel)
        with open(sums, encoding='utf-8') as f:
            checksums = json.load(f)
        if not isinstance(checksums, dict) or not isinstance(checksums.get('package'), dict):
            raise Problem('app.packageBad', detail='horizon-checksums.json has no package list')
        checksums = checksums['package']
        if cached:
            record = os.path.join(dest, PACKAGE_RECORD)
            try:
                with open(record, encoding='utf-8') as f:
                    verified = json.load(f)
            except (OSError, ValueError):
                # Older apps have no record. Hash their files once, including
                # files removed from the corrected release. Imports add bytecode.
                verified = {}
                for folder, dirs, files in os.walk(dest):
                    dirs[:] = [d for d in dirs if d != '__pycache__']
                    for filename in files:
                        path = os.path.join(folder, filename)
                        name = os.path.relpath(path, dest).replace(os.sep, '/')
                        if name == PACKAGE_RECORD:
                            continue
                        h = hashlib.sha256()
                        with open(path, 'rb') as f:
                            for b in iter(lambda: f.read(1 << 20), b''):
                                h.update(b)
                        verified[name] = h.hexdigest()
            if verified == checksums:
                with open(record, 'w', encoding='utf-8') as f:
                    json.dump(checksums, f, sort_keys=True)
                return package_info(dest)
            logging.getLogger(__name__).warning('Release %s package checksums changed; refreshing cache', release['tag'])
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
        staged = os.path.join(work, 'package')
        unpack_package(tar, staged, checksums)
        with open(os.path.join(staged, PACKAGE_RECORD), 'w', encoding='utf-8') as f:
            json.dump(checksums, f, sort_keys=True)
        if cached:
            shutil.rmtree(previous, ignore_errors=True)
            os.replace(dest, previous)
        try:
            os.replace(staged, dest)
        except BaseException:
            if cached:
                os.replace(previous, dest)
            raise
        shutil.rmtree(previous, ignore_errors=True)
    except Exception as e:
        if not cached or (isinstance(e, Problem) and e.key == 'cancelled'):
            raise
        logging.getLogger(__name__).warning('Release %s cache refresh failed; using cached package: %s',
                                           release['tag'], e)
        return package_info(dest)
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


def player_program():
    """The bundled Horizon Play program (docs/player.md), or None when this app was built without it."""
    if sys.platform == 'darwin' and getattr(sys, 'frozen', False):
        # the app is nested at Contents/Helpers (tools/patcher/app/build.py), signed on its own
        path = os.path.join(os.path.dirname(os.path.dirname(sys.executable)), 'Helpers', 'Horizon Play.app',
                            'Contents', 'MacOS', 'horizon-play')
    elif sys.platform == 'darwin':
        path = resource('player', 'Horizon Play.app', 'Contents', 'MacOS', 'horizon-play')
    else:
        path = resource('player', 'horizon-play.exe' if os.name == 'nt' else 'horizon-play')
    return path if os.path.isfile(path) else None


# The installers that put the built disc inside (docs/player.md): their empty templates are release assets, fetched
# when one is wanted (the Mac one is the bundled Horizon Play on a Mac).
TEMPLATES = dict(apk='Horizon-Play.apk', setup='Horizon-Setup.exe', mac='Horizon-Play-macOS.zip',
                 linux='Horizon-Play-Linux-x86_64.tar.gz')
TEMPLATE_KINDS = tuple(TEMPLATES)


def templates_root():
    return os.path.join(cache_dir(), 'templates')


def release_assets(tag, repo=None):
    """{name: {url, size, digest}} of the release `tag`: GitHub's API; when it refuses (its limit), the plain
    download addresses of the templates, which carry no size or digest (TLS and the exact size then decide)."""
    import urllib.error
    repo = repo or repository()
    try:
        with _open(f'https://api.github.com/repos/{repo}/releases/tags/{tag}', 'application/vnd.github+json') as r:
            return release_info(json.load(r))['assets']
    except urllib.error.HTTPError as e:
        if e.code == 404:
            return {}
        if e.code not in (403, 429):
            raise
    return {name: dict(url=f'https://github.com/{repo}/releases/download/{tag}/{name}', size=None, digest=None)
            for name in TEMPLATES.values()}


def _sha256(path):
    h = hashlib.sha256()
    with open(path, 'rb') as f:
        for b in iter(lambda: f.read(1 << 20), b''):
            h.update(b)
    return h.hexdigest()


def unzip_app(archive, dest):
    """A zip made by `ditto -c -k --keepParent` (or mac_app.zip_app) -> dest, keeping symlinks and execute bits."""
    import stat
    import zipfile
    shutil.rmtree(dest, ignore_errors=True)
    os.makedirs(dest)
    with zipfile.ZipFile(archive) as z:
        for info in z.infolist():
            name = info.filename.rstrip('/')
            if not _safe_name(name) or name.startswith('__MACOSX/'):
                if name.startswith('__MACOSX/'):
                    continue
                raise Problem('app.packageBad', detail=f'unsafe name {info.filename}')
            path = os.path.join(dest, *name.split('/'))
            mode = info.external_attr >> 16
            if info.is_dir():
                os.makedirs(path, exist_ok=True)
            elif stat.S_ISLNK(mode):
                os.makedirs(os.path.dirname(path), exist_ok=True)
                os.symlink(z.read(info).decode('utf-8'), path)
            else:
                os.makedirs(os.path.dirname(path), exist_ok=True)
                with z.open(info) as src, open(path, 'wb') as out:
                    shutil.copyfileobj(src, out)
                os.chmod(path, (mode & 0o777) or 0o644)
    apps = [n for n in os.listdir(dest) if n.endswith('.app')]
    if len(apps) != 1:
        raise Problem('app.packageBad', detail='the Mac template holds no single .app')
    return os.path.join(dest, apps[0])


def mac_app_template():
    """The Horizon Play .app the macOS patcher carries (the one with the program inside), or None."""
    if sys.platform != 'darwin':
        return None
    program = player_program()
    return os.path.dirname(os.path.dirname(os.path.dirname(program))) if program else None


def template(kind, tag, progress=None, cancel=None):
    """The empty template of an installer (`TEMPLATES`) from the release `tag` (the one whose package is in use) ->
    the file (the .app folder for 'mac'). Cached by tag in the settings folder and checked against the asset's
    SHA-256 when GitHub gives one (as the package is); the cache is used when offline. progress(done, total)."""
    import urllib.error
    if kind == 'mac' and mac_app_template():
        return mac_app_template()     # the bundled Horizon Play: the same thing
    if kind == 'linux' and sys.platform.startswith('linux') and player_program():
        return os.path.dirname(player_program())     # the Linux patcher carries the very bundle of the tarball
    name = TEMPLATES[kind]
    folder = os.path.join(templates_root(), re.sub(r'[^A-Za-z0-9._-]', '_', tag))
    dest = os.path.join(folder, name)
    record = dest + '.json'
    result = os.path.join(folder, 'Horizon Play-app') if kind == 'mac' else dest
    try:
        assets, failure = release_assets(tag), None
    except (urllib.error.URLError, OSError) as e:
        assets, failure = None, e
    cached = None
    try:
        with open(record, encoding='utf-8') as f:
            cached = json.load(f)
        if not os.path.isfile(dest) or os.path.getsize(dest) != cached['size']:
            cached = None
    except (OSError, ValueError, KeyError):
        cached = None
    asset = (assets or {}).get(name)
    if cached and asset:   # the release may have been corrected since
        if (asset.get('digest') or '').startswith('sha256:') and asset['digest'][7:] != cached['sha256']:
            cached = None
        elif asset.get('size') and asset['size'] != cached['size']:
            cached = None
    if not cached:
        if assets is None:
            raise Problem('app.templateOffline', name=name, error=getattr(failure, 'reason', None) or failure)
        if not asset:
            raise Problem('app.templateMissing', name=name, tag=tag)
        os.makedirs(folder, exist_ok=True)
        download(asset['url'], dest, progress, cancel, asset.get('size'))
        digest = _sha256(dest)
        if (asset.get('digest') or '').startswith('sha256:') and asset['digest'][7:] != digest:
            os.remove(dest)
            raise Problem('app.packageBad', detail='the download is not the release asset (SHA-256)')
        with open(record, 'w', encoding='utf-8') as f:
            json.dump(dict(sha256=digest, size=os.path.getsize(dest)), f)
        shutil.rmtree(result, ignore_errors=True)
    if kind != 'mac':
        return dest
    if not os.path.isdir(result):
        unzip_app(dest, result)
    return os.path.join(result, [n for n in os.listdir(result) if n.endswith('.app')][0])


def make(kind, cue, tag, progress=None, fetching=None, cancel=None, out_dir=None):
    """The installer of `kind` (apk, setup, mac, linux) with the built disc inside, in out_dir (default: next to the
    disc) -> its path. fetching(done, total) follows the template's download, progress(done, total) the build."""
    try:
        from . import apk, setup_exe, mac_app, linux_run
    except ImportError:
        import apk, setup_exe, mac_app, linux_run
    source = template(kind, tag, fetching, cancel)
    base = os.path.splitext(os.path.abspath(cue))[0]
    if out_dir:
        base = os.path.join(out_dir, os.path.basename(base))
    try:
        if kind == 'apk':
            image = cue_image(cue)
            total = 2 * os.path.getsize(image)   # read once for the zip, once for the signature
            done = [0]

            def tick(n):
                done[0] += n
                if progress:
                    progress(min(done[0], total), total)
            return apk.build(source, image, base + '.apk', None, tick)   # the shared key (apk.SHARED_KEY)
        if kind == 'setup':
            return setup_exe.build(source, cue, base + '-Setup.exe', progress)
        if kind == 'mac':   # a disk image on a Mac; elsewhere a zip (it cannot be signed or mounted here)
            return mac_app.build(source, cue, base + ('-Mac.dmg' if sys.platform == 'darwin' else '-Mac.zip'), progress)
        return linux_run.build(source, cue, base + '-Linux.run', progress)
    except (setup_exe.SetupError, mac_app.MacAppError, linux_run.LinuxRunError) as e:
        raise Problem('app.makeFailed', detail=str(e))


# ---------------------------------------------------------------- the built disc, kept for the next make button
def built_disc_dir():
    """The disc the patcher built last (about 900 MB), kept in the cache folder with what it was built from, so
    every make button after the first uses it as it is."""
    return os.path.join(cache_dir(), 'disc')


def disc_key(slots, package):
    """What a built disc depends on: each disc (path, size, modification time) and the package (folder, version)."""
    return dict(discs=sorted([g, r.get('path'), r.get('size'), r.get('mtime_ns')] for g, r in slots.items()),
                package=[package.get('folder'), package.get('version')])


def cached_disc(key):
    """{cue, bin, version} of the kept disc when it was built from `key` and its files are all there, else None."""
    try:
        with open(os.path.join(built_disc_dir(), 'built.json'), encoding='utf-8') as f:
            kept = json.load(f)
    except (OSError, ValueError):
        return None
    if kept.get('key') != json.loads(json.dumps(key)):
        return None
    files = {k: os.path.join(built_disc_dir(), kept.get(k) or '') for k in ('cue', 'bin')}
    if not all(os.path.isfile(v) for v in files.values()):
        return None
    return dict(files, version=kept.get('version'))


def forget_built_disc():
    """Empties the kept disc's folder (before a new build writes into it)."""
    shutil.rmtree(built_disc_dir(), ignore_errors=True)
    os.makedirs(built_disc_dir(), exist_ok=True)


def keep_built_disc(key, result, version):
    """Records the disc just built in built_disc_dir() as built from `key`."""
    with open(os.path.join(built_disc_dir(), 'built.json'), 'w', encoding='utf-8') as f:
        json.dump(dict(key=key, version=version, cue=os.path.basename(result['cue']),
                       bin=os.path.basename(result['bin'])), f)


def copy_disc(disc, out_dir, progress=None, cancel=None):
    """The kept disc's .cue and .bin -> out_dir (the .bin through a .part, renamed when whole) -> the copied .cue."""
    total = os.path.getsize(disc['bin'])
    done = 0
    dest = os.path.join(out_dir, os.path.basename(disc['bin']))
    with open(disc['bin'], 'rb') as src, open(dest + '.part', 'wb') as out:
        for chunk in iter(lambda: src.read(1 << 22), b''):
            if cancel is not None and cancel.is_set():
                out.close()
                os.remove(dest + '.part')
                raise Problem('cancelled')
            out.write(chunk)
            done += len(chunk)
            if progress:
                progress(done, total)
    os.replace(dest + '.part', dest)
    cue = os.path.join(out_dir, os.path.basename(disc['cue']))
    shutil.copyfile(disc['cue'], cue)
    return cue


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
