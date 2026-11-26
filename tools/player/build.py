"""Build Horizon Play for this computer (docs/player.md): the host program, the SwanStation core and the OpenBIOS
image, assembled into one folder.

    python tools/player/build.py --out build/player/bundle [--openbios openbios.bin] [--jobs N]

The core and OpenBIOS come from their own repositories at the pinned commits below, built from source. OpenBIOS needs
a MIPS cross compiler (mipsel-linux-gnu-gcc, Linux); elsewhere pass an image built on Linux with --openbios.
Needs git, CMake 3.16+ and a C/C++ compiler. Standard library only.
"""
import argparse
import os
import platform
import shutil
import subprocess
import sys

SWANSTATION = ('https://github.com/libretro/swanstation', '631f0fb31b809e0f889d7c551fe695788e39c1d3')
NUGGET = ('https://github.com/pcsx-redux/nugget', 'c51f16e6ca6eb074be9f6a47de9a797da94701d0')   # OpenBIOS
HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(os.path.dirname(HERE))


def run(cmd, cwd=None, env=None):
    print('+', ' '.join(cmd), flush=True)
    subprocess.run(cmd, cwd=cwd, env=env, check=True)


def checkout(url, commit, where, submodules=False):
    """A source tree at exactly `commit` (fetched shallow; kept between builds)."""
    if not os.path.isdir(os.path.join(where, '.git')):
        os.makedirs(where, exist_ok=True)
        run(['git', 'init', '-q'], cwd=where)
        run(['git', 'remote', 'add', 'origin', url], cwd=where)
    head = subprocess.run(['git', 'rev-parse', 'HEAD'], cwd=where, capture_output=True, text=True).stdout.strip()
    if head != commit:
        run(['git', 'fetch', '-q', '--depth', '1', 'origin', commit], cwd=where)
        run(['git', 'checkout', '-q', '--force', commit], cwd=where)
    if submodules:
        run(['git', 'submodule', 'update', '-q', '--init', '--recursive', '--depth', '1'], cwd=where)
    return where


def cmake(src, build, jobs, *extra):
    args = ['cmake', '-S', src, '-B', build, '-DCMAKE_BUILD_TYPE=Release', *extra]
    if sys.platform == 'darwin':
        args.append('-DCMAKE_OSX_DEPLOYMENT_TARGET=11.0')
    elif sys.platform == 'win32':
        args += ['-A', 'x64']
    run(args)
    run(['cmake', '--build', build, '--config', 'Release', '--parallel', str(jobs)])


def find(root, names):
    for d, _, files in os.walk(root):
        for f in files:
            if f in names:
                return os.path.join(d, f)
    raise SystemExit(f'not built: {names} under {root}')


def core_name():
    return {'win32': 'swanstation_libretro.dll', 'darwin': 'swanstation_libretro.dylib'}.get(
        sys.platform, 'swanstation_libretro.so')


def build_openbios(work, jobs):
    if not shutil.which('mipsel-linux-gnu-gcc'):
        raise SystemExit('OpenBIOS needs mipsel-linux-gnu-gcc (apt install gcc-mipsel-linux-gnu g++-mipsel-linux-gnu); '
                         'or pass --openbios with an image built elsewhere')
    src = checkout(*NUGGET, os.path.join(work, 'nugget'), submodules=True)
    # OPENBIOS_SHELL=shell: the image built with the newer default shell (shello) leaves the screen black
    run(['make', '-C', os.path.join(src, 'openbios'), f'-j{jobs}', 'PREFIX=mipsel-linux-gnu',
         'FORMAT=elf32-tradlittlemips', 'OPENBIOS_SHELL=shell'])
    return os.path.join(src, 'openbios', 'openbios.bin')


def main():
    ap = argparse.ArgumentParser(description=__doc__.split('\n')[0])
    ap.add_argument('--out', default=os.path.join(REPO, 'build', 'player', 'bundle'))
    ap.add_argument('--work', default=os.path.join(REPO, 'build', 'player', 'work'))
    ap.add_argument('--openbios', help='an OpenBIOS image to use instead of building it')
    ap.add_argument('--jobs', type=int, default=os.cpu_count() or 4)
    ap.add_argument('--skip-core', action='store_true', help='reuse the core already in --out')
    ap.add_argument('--openbios-only', metavar='PATH', help='only build OpenBIOS and copy it to PATH')
    ap.add_argument('--universal2', action='store_true', help='macOS: Apple silicon and Intel in one bundle')
    a = ap.parse_args()
    work, out = os.path.abspath(a.work), os.path.abspath(a.out)
    os.makedirs(work, exist_ok=True)

    bios = a.openbios or build_openbios(work, a.jobs)
    if a.openbios_only:
        shutil.copy2(bios, a.openbios_only)
        lic = os.path.join(work, 'nugget', 'LICENSE')
        if os.path.exists(lic):
            shutil.copy2(lic, os.path.join(os.path.dirname(os.path.abspath(a.openbios_only)), 'OpenBIOS-MIT.txt'))
        return

    # the host
    host_build = os.path.join(work, 'host')
    cmake(HERE, host_build, a.jobs, *(['-DCMAKE_OSX_ARCHITECTURES=arm64;x86_64'] if a.universal2 else []))

    # the core (one build per architecture for a universal2 bundle: its recompiler is chosen at configure time)
    core_lib = None
    if not a.skip_core:
        sw = checkout(*SWANSTATION, os.path.join(work, 'swanstation'))
        if a.universal2:
            parts = []
            for arch in ('arm64', 'x86_64'):
                b = os.path.join(work, f'swanstation-build-{arch}')
                cmake(sw, b, a.jobs, f'-DCMAKE_OSX_ARCHITECTURES={arch}')
                parts.append(find(b, {core_name()}))
            core_lib = os.path.join(work, core_name())
            run(['lipo', '-create', '-output', core_lib, *parts])
        else:
            cmake(sw, os.path.join(work, 'swanstation-build'), a.jobs)
            core_lib = find(os.path.join(work, 'swanstation-build'), {core_name()})

    # the folder: program, core, BIOS, licences
    if sys.platform == 'darwin':
        app = os.path.join(out, 'Horizon Play.app')
        if os.path.exists(app):
            shutil.rmtree(app)
        os.makedirs(out, exist_ok=True)
        shutil.copytree(os.path.join(host_build, 'horizon-play.app'), app, symlinks=True)
        place = os.path.join(app, 'Contents', 'Resources')    # SDL_GetBasePath() of a bundle
    else:
        os.makedirs(out, exist_ok=True)
        exe = 'horizon-play.exe' if sys.platform == 'win32' else 'horizon-play'
        shutil.copy2(find(host_build, {exe}), os.path.join(out, exe))
        place = out
    os.makedirs(os.path.join(place, 'system'), exist_ok=True)
    if core_lib:
        shutil.copy2(core_lib, os.path.join(place, core_name()))
    shutil.copy2(bios, os.path.join(place, 'system', 'openbios.bin'))

    lic = os.path.join(out, 'licenses')
    os.makedirs(lic, exist_ok=True)
    shutil.copy2(os.path.join(HERE, 'NOTICE.txt'), os.path.join(out, 'NOTICE.txt'))
    sw_src = os.path.join(work, 'swanstation')
    for name in ('LICENSE', 'COPYING', 'LICENSE.txt'):
        if os.path.exists(os.path.join(sw_src, name)):
            shutil.copy2(os.path.join(sw_src, name), os.path.join(lic, 'SwanStation-GPL-3.0.txt'))
            break
    nug = os.path.join(work, 'nugget', 'LICENSE')
    if not os.path.exists(nug) and a.openbios:
        nug = os.path.join(os.path.dirname(os.path.abspath(a.openbios)), 'OpenBIOS-MIT.txt')
    if os.path.exists(nug):
        shutil.copy2(nug, os.path.join(lic, 'OpenBIOS-MIT.txt'))
    sdl = find(os.path.join(host_build, '_deps'), {'LICENSE.txt'})
    shutil.copy2(sdl, os.path.join(lic, 'SDL2-zlib.txt'))
    shutil.copy2(os.path.join(REPO, 'LICENSE'), os.path.join(lic, 'Horizon-MIT.txt'))
    print(f'Horizon Play ({platform.system()} {platform.machine()}): {out}')


if __name__ == '__main__':
    main()
