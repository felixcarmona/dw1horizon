#!/usr/bin/env python3
"""Freeze the desktop patcher with PyInstaller (docs/patcher.md, "The desktop app"; CI: .github/workflows/desktop.yml).

    python3 tools/patcher/app/build.py [--version X.Y.Z] [--universal2] [--codesign-identity ID --entitlements FILE]

Writes build/desktop/dist/Horizon Patcher/ (Windows, Linux: a folder with the program in it) or
build/desktop/dist/Horizon Patcher.app (macOS). A folder, not one file: every Python process the build starts (derive
and its workers) is this program again, and a one-file program would unpack itself to a temporary folder each time.

The whole standard library goes in, not only what the app imports: the release package's bundle (tools/derive and
the importers) runs in this Python and imports what it needs. Needs PyInstaller (and certifi on macOS: a frozen
macOS Python has no certificate folder) in the Python that runs this; nothing of it is a dependency of the repository.
"""
import argparse
import json
import os
import pkgutil
import re
import shutil
import subprocess
import sys
import warnings

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
APP = os.path.join(ROOT, 'tools', 'patcher', 'app')
NAME = 'Horizon Patcher'
BUNDLE_ID = 'com.dw1horizon.patcher'
PRODUCT = 'Digimon World: Horizon Patcher'
# Not frozen: development and test tooling, other front ends, and what the release bundle never imports.
SKIP = ('test', 'idlelib', 'turtledemo', 'lib2to3', 'ensurepip', 'pydoc_data', 'distutils', 'venv', 'tkinter.test',
        'unittest.test', 'ctypes.test', 'sqlite3.test', 'lib2to3', '__phello__', '_pyrepl', 'turtle')


def stdlib_modules():
    """Every importable standard-library module of this Python (packages with their submodules)."""
    names = set()
    for top in sorted(sys.stdlib_module_names):
        if top.startswith(SKIP) or top in SKIP or top.startswith('_test') or top == 'this' or top == 'antigravity':
            continue
        try:
            with warnings.catch_warnings():
                warnings.simplefilter('ignore')
                mod = __import__(top)
        except Exception:                  # (another platform's module, or one this Python was built without)
            continue
        names.add(top)
        for info in pkgutil.walk_packages(getattr(mod, '__path__', []) or [], top + '.'):
            n = info.name
            if any(part in ('test', 'tests', 'idle_test') for part in n.split('.')) or n.startswith(SKIP):
                continue
            names.add(n)
    return sorted(names)


def version():
    out = subprocess.run([sys.executable, os.path.join(ROOT, 'tools', 'version.py')], capture_output=True, text=True,
                         cwd=ROOT).stdout.split()
    return out[0] if out else '0.0.0'


def version_file(path, ver):
    """Windows VERSIONINFO: the product, the company, the release's version (SignPath's requirements)."""
    nums = [int(x) for x in re.findall(r'\d+', ver.split('-')[0].split('+')[0])[:3]] + [0, 0, 0, 0]
    t = tuple(nums[:4])
    text = f'''VSVersionInfo(
  ffi=FixedFileInfo(filevers={t}, prodvers={t}, mask=0x3f, flags=0x0, OS=0x40004, fileType=0x1, subtype=0x0,
                    date=(0, 0)),
  kids=[
    StringFileInfo([StringTable('040904B0', [
      StringStruct('CompanyName', 'Digimon World: Horizon project'),
      StringStruct('FileDescription', '{PRODUCT}'),
      StringStruct('FileVersion', '{ver}'),
      StringStruct('InternalName', '{NAME}'),
      StringStruct('LegalCopyright', 'Digimon World: Horizon contributors. A fan project, not affiliated with Bandai Namco.'),
      StringStruct('OriginalFilename', '{NAME}.exe'),
      StringStruct('ProductName', '{PRODUCT}'),
      StringStruct('ProductVersion', '{ver}')])]),
    VarFileInfo([VarStruct('Translation', [1033, 1200])])
  ]
)
'''
    with open(path, 'w', encoding='utf-8') as f:
        f.write(text)


def repository():
    """OWNER/NAME on GitHub: CI's GITHUB_REPOSITORY, else this checkout's origin (desktop.repository())."""
    if os.environ.get('GITHUB_REPOSITORY'):
        return os.environ['GITHUB_REPOSITORY']
    sys.path.insert(0, os.path.join(ROOT, 'tools', 'patcher'))
    import desktop
    return desktop.repository()


def spec(work, a, ver):
    icons = os.path.join(work, 'icons')
    subprocess.run([sys.executable, os.path.join(APP, 'make_icons.py'), icons], check=True)
    info = os.path.join(work, 'build-info.json')
    with open(info, 'w', encoding='utf-8') as f:
        json.dump(dict(repository=a.repository or repository(), version=ver), f)
    datas = [(info, 'tools/patcher/app'), (os.path.join(ROOT, 'web', 'i18n'), 'web/i18n'),
             (os.path.join(ROOT, 'web', 'data', 'discs.json'), 'web/data'),
             (os.path.join(APP, 'i18n.json'), 'tools/patcher/app'),
             (os.path.join(APP, 'make_icons.py'), 'tools/patcher/app'),
             (os.path.join(APP, 'platform_icons.py'), 'tools/patcher/app'),
             (os.path.join(ROOT, 'tools', 'patcher', 'android-key.json'), '.')]   # apk.SHARED_KEY, beside apk
    if a.player and sys.platform != 'darwin':      # Horizon Play (tools/player/build.py --out DIR); macOS: nest_player
        datas.append((os.path.abspath(a.player), 'player'))
    hidden = stdlib_modules() + ['desktop', 'selftest', 'dwpatch', 'make_icons', 'platform_icons', 'apk', 'setup_exe', 'mac_app', 'linux_run']
    if sys.platform == 'darwin':
        hidden.append('certifi')
    icon = None if sys.platform.startswith('linux') else os.path.join(icons, 'icon.ico' if os.name == 'nt' else 'icon.icns')
    vfile = os.path.join(work, 'version.txt')
    version_file(vfile, ver)
    mac = sys.platform == 'darwin'
    return f'''# Generated by tools/patcher/app/build.py: do not edit.
a = Analysis([{os.path.join(ROOT, 'tools', 'patcher', 'gui.py')!r}],
             pathex=[{os.path.join(ROOT, 'tools', 'patcher')!r}, {os.path.join(ROOT, 'tools', 'patcher', 'app')!r}],
             datas={datas!r}, hiddenimports={hidden!r},
             excludes=['test', 'idlelib', 'turtledemo', 'lib2to3', 'ensurepip', 'numpy', 'PIL'],
             noarchive=False)
pyz = PYZ(a.pure)
exe = EXE(pyz, a.scripts, [('X utf8=1', None, 'OPTION')], exclude_binaries=True, name={NAME!r},
          console=False, disable_windowed_traceback=True, icon={icon!r}, version={vfile if os.name == 'nt' else None!r},
          target_arch={('universal2' if a.universal2 else None)!r},
          codesign_identity={a.codesign_identity!r}, entitlements_file={a.entitlements!r},
          upx=False)
coll = COLLECT(exe, a.binaries, a.datas, name={NAME!r}, upx=False)
''' + (f'''app = BUNDLE(coll, name={NAME + '.app'!r}, icon={icon!r}, bundle_identifier={BUNDLE_ID!r},
             version={ver.split('-')[0]!r},
             info_plist={{'CFBundleDisplayName': {NAME!r}, 'CFBundleShortVersionString': {ver.split('-')[0]!r},
                         'CFBundleVersion': {ver!r}, 'NSHighResolutionCapable': True,
                         'LSMinimumSystemVersion': '11.0', 'NSHumanReadableCopyright': {PRODUCT!r}}})
''' if mac else '')


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__.split('\n')[0])
    p.add_argument('--version', help='the release version (default: tools/version.py)')
    p.add_argument('--universal2', action='store_true', help='macOS: one app for Apple silicon and Intel')
    p.add_argument('--codesign-identity', help='macOS: the Developer ID Application identity to sign with')
    p.add_argument('--entitlements', help='macOS: the entitlements of the hardened runtime')
    p.add_argument('--repository', help='OWNER/NAME whose releases the app downloads (default: GITHUB_REPOSITORY, '
                   'else the checkout\'s origin)')
    p.add_argument('--player', help='a Horizon Play folder (tools/player/build.py) to ship inside the app')
    p.add_argument('--out', default=os.path.join(ROOT, 'build', 'desktop'))
    a = p.parse_args(argv)
    ver = (a.version or version()).lstrip('v')
    work = os.path.abspath(a.out)
    os.makedirs(work, exist_ok=True)
    path = os.path.join(work, 'horizon-patcher.spec')
    with open(path, 'w', encoding='utf-8') as f:
        f.write(spec(work, a, ver))
    subprocess.run([sys.executable, '-m', 'PyInstaller', '--noconfirm', '--clean', '--log-level', 'WARN',
                    '--distpath', os.path.join(work, 'dist'), '--workpath', os.path.join(work, 'work'), path],
                   check=True, cwd=work)
    if a.player and sys.platform == 'darwin':
        nest_player(os.path.join(work, 'dist', NAME + '.app'), a)
    if sys.platform.startswith('linux'):
        linux_extras(os.path.join(work, 'dist', NAME), os.path.join(work, 'icons'))
    print(os.path.join(work, 'dist'))


def linux_extras(folder, icons):
    """Linux: a launcher and the icon beside the program. A .desktop file wants absolute paths; %k is the launcher's own
    location, so the Exec line starts the program from wherever the folder was unpacked (the icon is found by its
    name once the PNG is in a theme folder, or shown by the file manager from the file beside it)."""
    shutil.copy(os.path.join(icons, 'icon.png'), os.path.join(folder, 'horizon-patcher.png'))
    with open(os.path.join(folder, NAME + '.desktop'), 'w', encoding='utf-8', newline='\n') as f:
        f.write(f'''[Desktop Entry]
Type=Application
Name={PRODUCT}
Comment=Build Digimon World: Horizon from your own disc
Exec=sh -c 'cd "$(dirname "$(readlink -f "$1")")" && exec "./{NAME}"' sh %k
Icon=horizon-patcher
Terminal=false
Categories=Game;
''')
    os.chmod(os.path.join(folder, NAME + '.desktop'), 0o755)


def nest_player(app, a):
    """macOS: Horizon Play.app goes into Contents/Helpers by hand (PyInstaller's data copy mangles a nested bundle
    into __dot__app symlinks that codesign cannot follow), then the outer app is signed again without --deep so the
    nested app keeps its own signature (JIT entitlements). With no identity both are signed ad hoc."""
    src = os.path.join(os.path.abspath(a.player), 'Horizon Play.app')
    helpers = os.path.join(app, 'Contents', 'Helpers')
    os.makedirs(helpers, exist_ok=True)
    dst = os.path.join(helpers, 'Horizon Play.app')
    if os.path.exists(dst):
        shutil.rmtree(dst)
    shutil.copytree(src, dst, symlinks=True)
    sign = ['codesign', '--force']
    if a.codesign_identity:
        outer = sign + ['--timestamp', '--options', 'runtime', '--sign', a.codesign_identity]
        if a.entitlements:
            outer += ['--entitlements', a.entitlements]
    else:
        for code in (os.path.join(dst, 'Contents', 'Resources', 'swanstation_libretro.dylib'), dst):
            subprocess.run(sign + ['--sign', '-', code], check=True)
        outer = sign + ['--sign', '-']
    subprocess.run(outer + [app], check=True)


if __name__ == '__main__':
    main()
