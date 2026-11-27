"""Put the player's patched disc inside Horizon Play for macOS (docs/player.md): one "Digimon World Horizon.app" that
starts the game with nothing to choose, wrapped in a disk image to drag into Applications (on a Mac) or a zip (anywhere
else). The disc never leaves the player's computer: the patcher writes this next to the disc it built.

    python3 tools/patcher/mac_app.py "Horizon Play.app" DISC.cue OUT.dmg|OUT.zip|OUT.app

The template is the Horizon Play .app the macOS patcher carries. It is copied with its symlinks and permissions, the
disc is added in Contents/Resources as "Digimon World Horizon.bin" and ".cue" (the player looks for that cue beside
itself when it is started with no disc), and Info.plist names the app "Digimon World Horizon" (the bundle id stays:
saves live in ~/Library/Application Support/Horizon/Horizon whatever the app is called). Adding files breaks the
bundle's seal, so on a Mac the copy is signed again ad hoc (`codesign --force --deep -s -`): it runs on the computer
that made it. That replaces the Developer ID signature and the notarization of the template, so a copy sent to another
Mac needs `xattr -cr "Digimon World Horizon.app"` or right-click, Open. Elsewhere (the zip made by this CLI on Linux
or Windows) nothing can be signed and the same applies. Standard library only, so it is frozen into the patcher.
"""
import os
import plistlib
import shutil
import stat
import subprocess
import sys
import tempfile
import zipfile

try:
    from . import setup_exe
except ImportError:
    import setup_exe

NAME = setup_exe.DISC_NAME
CHUNK = 1 << 20


class MacAppError(Exception):
    pass


def _copy(src_path, dst_path, tick):
    with open(src_path, 'rb') as src, open(dst_path, 'wb') as dst:
        while True:
            block = src.read(CHUNK)
            if not block:
                break
            dst.write(block)
            tick(len(block))


def build_app(template, cue, out, tick=lambda n: None):
    """OUT (a .app folder) = a copy of the TEMPLATE app with the disc of CUE inside. Returns True when it was signed."""
    plist_path = os.path.join(template, 'Contents', 'Info.plist')
    if not os.path.isfile(plist_path):
        raise MacAppError(f'{template}: not a Horizon Play .app (no Contents/Info.plist)')
    text, image = setup_exe.read_cue(cue)
    shutil.copytree(template, out, symlinks=True)
    res = os.path.join(out, 'Contents', 'Resources')
    os.makedirs(res, exist_ok=True)
    _copy(image, os.path.join(res, NAME + '.bin'), tick)
    with open(os.path.join(res, NAME + '.cue'), 'w', encoding='utf-8', newline='') as f:
        f.write(text)
    info = os.path.join(out, 'Contents', 'Info.plist')
    with open(info, 'rb') as f:
        plist = plistlib.load(f)
    plist['CFBundleName'] = plist['CFBundleDisplayName'] = NAME
    with open(info, 'wb') as f:
        plistlib.dump(plist, f)
    if sys.platform == 'darwin' and shutil.which('codesign'):
        # a patcher downloaded from the web is quarantined, and the copy would carry that mark: this app is made here
        subprocess.run(['xattr', '-dr', 'com.apple.quarantine', out], capture_output=True)
        r = subprocess.run(['codesign', '--force', '--deep', '--sign', '-', out], capture_output=True, text=True)
        if r.returncode:
            raise MacAppError('codesign: ' + (r.stderr.strip() or 'failed'))
        return True
    return False


def zip_app(app, out, tick=lambda n: None):
    """A zip of the app folder that keeps its symlinks and execute bits."""
    root = os.path.dirname(app)
    with zipfile.ZipFile(out, 'w', zipfile.ZIP_DEFLATED, compresslevel=3) as z:
        for folder, dirs, files in os.walk(app):
            for name in dirs + files:
                path = os.path.join(folder, name)
                arc = os.path.relpath(path, root).replace(os.sep, '/')
                st = os.lstat(path)
                if stat.S_ISLNK(st.st_mode):
                    info = zipfile.ZipInfo(arc)
                    info.create_system = 3
                    info.external_attr = (st.st_mode & 0xFFFF) << 16
                    z.writestr(info, os.readlink(path))
                elif stat.S_ISDIR(st.st_mode):
                    info = zipfile.ZipInfo(arc + '/')
                    info.create_system = 3
                    info.external_attr = (((stat.S_IFDIR | 0o755) if os.name == 'nt' else st.st_mode & 0xFFFF) << 16) | 0x10
                    z.writestr(info, b'')
                else:
                    info = zipfile.ZipInfo.from_file(path, arc)
                    info.create_system = 3
                    if os.name == 'nt':   # Windows keeps no execute bits: the program and its libraries get them back
                        runs = '/Contents/MacOS/' in arc or arc.endswith(('.dylib', '.so'))
                        info.external_attr = (stat.S_IFREG | (0o755 if runs else 0o644)) << 16
                    info.compress_type = zipfile.ZIP_DEFLATED
                    with open(path, 'rb') as src, z.open(info, 'w', force_zip64=True) as dst:
                        while True:
                            block = src.read(CHUNK)
                            if not block:
                                break
                            dst.write(block)
                            tick(len(block))


def hdiutil(args, size, tick):
    """Run hdiutil with -puppetstrings: its PERCENT:n lines move the bar through SIZE (compressing takes minutes)."""
    p = subprocess.Popen(['hdiutil'] + args[:1] + ['-puppetstrings'] + args[1:], stdout=subprocess.PIPE,
                         stderr=subprocess.STDOUT, text=True)
    shown, out = 0, []
    for line in p.stdout:
        if line.startswith('PERCENT:'):
            try:
                pct = float(line[8:])
            except ValueError:
                continue
            if 0 <= pct <= 100 and int(size * pct / 100) > shown:
                tick(int(size * pct / 100) - shown)
                shown = int(size * pct / 100)
        else:
            out.append(line)
    if p.wait():
        raise MacAppError('hdiutil: ' + (''.join(out).strip() or 'failed'))
    tick(size - shown)


def build(template, cue, out, progress=None):
    """Write OUT: a .dmg (Mac only), a .zip or a bare .app folder, chosen by its name. progress(done, total)."""
    out = os.path.abspath(out)
    kind = os.path.splitext(out)[1].lower()
    if kind not in ('.dmg', '.zip', '.app'):
        raise MacAppError('the output must end in .dmg, .zip or .app')
    if kind == '.dmg' and sys.platform != 'darwin':
        raise MacAppError('a .dmg can only be made on a Mac (hdiutil); make a .zip here')
    size = os.path.getsize(setup_exe.read_cue(cue)[1])
    total = size * (1 if kind == '.app' else 2)   # copying the disc in, then zipping or compressing it
    done = [0]

    def tick(n):
        done[0] += n
        if progress:
            progress(min(done[0], total), total)
    if kind == '.app':
        build_app(template, cue, out, tick)
        return out
    work = tempfile.mkdtemp(prefix='.hzmac-', dir=os.path.dirname(out))   # beside the output: the same disk
    try:
        stage = os.path.join(work, 'stage')
        os.mkdir(stage)
        app = os.path.join(stage, NAME + '.app')
        build_app(template, cue, app, tick)
        tmp = out + '.new'
        if kind == '.zip':
            zip_app(app, tmp, tick)
        else:
            os.symlink('/Applications', os.path.join(stage, 'Applications'))
            if os.path.exists(tmp):
                os.remove(tmp)
            hdiutil(['create', '-volname', NAME, '-srcfolder', stage, '-format', 'UDZO', '-ov', tmp], size, tick)
            if not os.path.exists(tmp) and os.path.exists(tmp + '.dmg'):   # hdiutil adds .dmg when it is missing
                tmp += '.dmg'
        os.replace(tmp, out)
    finally:
        shutil.rmtree(work, ignore_errors=True)
        for left in (out + '.new', out + '.new.dmg'):
            if os.path.exists(left):
                os.remove(left)
    return out


def main(argv=None):
    a = sys.argv[1:] if argv is None else argv
    if len(a) != 3:
        sys.exit(__doc__.split('\n\n')[0])
    last = [-1]

    def show(done, total):
        pct = done * 100 // total
        if pct != last[0]:
            last[0] = pct
            sys.stderr.write(f'\r{pct}%')
    try:
        build(a[0], a[1], a[2], show)
    except (MacAppError, setup_exe.SetupError) as e:
        sys.exit(str(e))
    sys.stderr.write('\n')
    print(a[2])


if __name__ == '__main__':
    main()
