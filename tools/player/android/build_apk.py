"""Build Horizon Play for Android (docs/player.md): one APK for arm64 phones and handhelds.

    python3 tools/player/android/build_apk.py --out Horizon-Play.apk [--openbios openbios.bin]

Needs ANDROID_HOME (platform android-35, build-tools 35.0.0) and an NDK (ANDROID_NDK_HOME, or the newest under
ANDROID_HOME/ndk), a JDK 17, CMake and Ninja; OpenBIOS needs mipsel-linux-gnu-gcc unless --openbios is given. No Gradle:
the APK is put together with the SDK's own tools (aapt2, javac, d8, zipalign, apksigner).

Signing: HORIZON_KEYSTORE (a .jks/.p12 file), HORIZON_KEYSTORE_PASS and HORIZON_KEY_ALIAS sign a release that installs
over the previous one. Without them a throwaway key is made, and that APK cannot update one signed with another key.
"""
import argparse
import glob
import importlib.util
import os
import re
import shutil
import subprocess
import sys
import zipfile

HERE = os.path.dirname(os.path.abspath(__file__))
PLAYER = os.path.dirname(HERE)
REPO = os.path.dirname(os.path.dirname(PLAYER))


def _load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


player_build = _load('player_build', os.path.join(PLAYER, 'build.py'))      # the pinned sources
make_icons = _load('make_icons', os.path.join(REPO, 'tools', 'patcher', 'app', 'make_icons.py'))

ABI, MIN_SDK, TARGET_SDK, BUILD_TOOLS = 'arm64-v8a', 24, 35, '35.0.0'
ICONS = {'mdpi': 48, 'hdpi': 72, 'xhdpi': 96, 'xxhdpi': 144, 'xxxhdpi': 192}
run = player_build.run


def sdk_paths():
    sdk = os.environ.get('ANDROID_HOME') or os.environ.get('ANDROID_SDK_ROOT')
    if not sdk:
        raise SystemExit('set ANDROID_HOME to the Android SDK')
    ndk = os.environ.get('ANDROID_NDK_HOME') or os.environ.get('ANDROID_NDK_LATEST_HOME')
    if not ndk:
        found = sorted(glob.glob(os.path.join(sdk, 'ndk', '*')))
        if not found:
            raise SystemExit('no NDK: set ANDROID_NDK_HOME')
        ndk = found[-1]
    tools = os.path.join(sdk, 'build-tools', BUILD_TOOLS)
    jar = os.path.join(sdk, 'platforms', f'android-{TARGET_SDK}', 'android.jar')
    for p in (tools, jar):
        if not os.path.exists(p):
            raise SystemExit(f'missing {p} (sdkmanager "build-tools;{BUILD_TOOLS}" "platforms;android-{TARGET_SDK}")')
    return ndk, tools, jar


def origin_repository():
    """OWNER/NAME of this checkout's GitHub origin, or None."""
    try:
        url = subprocess.run(['git', 'remote', 'get-url', 'origin'], cwd=REPO, capture_output=True, text=True,
                             timeout=10).stdout.strip()
    except (OSError, subprocess.SubprocessError):
        return None
    m = re.search(r'github\.com[:/]([^/]+/[^/]+?)(?:\.git)?$', url)
    return m.group(1) if m else None


def ndk_cmake(ndk, src, build, jobs, *extra):
    run(['cmake', '-S', src, '-B', build, '-G', 'Ninja', '-DCMAKE_BUILD_TYPE=Release',
         f'-DCMAKE_TOOLCHAIN_FILE={ndk}/build/cmake/android.toolchain.cmake', f'-DANDROID_ABI={ABI}',
         f'-DANDROID_PLATFORM=android-{MIN_SDK}', '-DCMAKE_SHARED_LINKER_FLAGS=-Wl,-z,max-page-size=16384', *extra])
    run(['cmake', '--build', build, '--parallel', str(jobs)])


def version_code(ver):
    """X.Y.Z[-dev.N]: later builds get larger codes, so each one installs over the one before."""
    m = re.match(r'(\d+)\.(\d+)\.(\d+)(?:-dev\.(\d+))?', ver)
    x, y, z, n = (int(g or 0) for g in m.groups()) if m else (0, 0, 0, 0)
    return ((x * 100 + y) * 100 + z) * 1000 + min(n, 999)


def main():
    ap = argparse.ArgumentParser(description=__doc__.split('\n')[0])
    ap.add_argument('--out', default=os.path.join(REPO, 'build', 'player', 'Horizon-Play.apk'))
    ap.add_argument('--work', default=os.path.join(REPO, 'build', 'player', 'android'))
    ap.add_argument('--openbios', help='an OpenBIOS image to use instead of building it')
    ap.add_argument('--version', help='the version name (default: tools/version.py)')
    ap.add_argument('--repository', help='OWNER/NAME whose GitHub releases the app checks for a newer version '
                    '(default: GITHUB_REPOSITORY, else the checkout\'s origin; none: no check)')
    ap.add_argument('--jobs', type=int, default=os.cpu_count() or 4)
    a = ap.parse_args()
    ndk, tools, jar = sdk_paths()
    work, out = os.path.abspath(a.work), os.path.abspath(a.out)
    os.makedirs(work, exist_ok=True)
    ver = a.version or (subprocess.run([sys.executable, os.path.join(REPO, 'tools', 'version.py'), 'version'],
                                       capture_output=True, text=True).stdout.strip() or '0.0.0')
    ver = ver.lstrip('v')

    # native: the core, the host (libmain.so) and SDL (libSDL2.so)
    bios = a.openbios or player_build.build_openbios(work, a.jobs)
    sw = player_build.checkout(*player_build.SWANSTATION, os.path.join(work, 'swanstation'))
    ndk_cmake(ndk, sw, os.path.join(work, 'core'), a.jobs)
    core = player_build.find(os.path.join(work, 'core'), {'swanstation_libretro_android.so'})
    host = os.path.join(work, 'host')
    ndk_cmake(ndk, PLAYER, host, a.jobs, f'-DHORIZON_VERSION={ver}')
    libs = {'libmain.so': player_build.find(host, {'libmain.so'}),
            'libSDL2.so': player_build.find(host, {'libSDL2.so'}),
            # the package manager only installs lib*.so; the host dlopens this name
            'libswanstation_libretro_android.so': core}
    strip = glob.glob(os.path.join(ndk, 'toolchains', 'llvm', 'prebuilt', '*', 'bin', 'llvm-strip'))[0]

    # resources: ours, the launcher icon, the licences as assets
    stage = os.path.join(work, 'stage')
    shutil.rmtree(stage, ignore_errors=True)
    res, assets = os.path.join(stage, 'res'), os.path.join(stage, 'assets')
    shutil.copytree(os.path.join(HERE, 'res'), res)
    for dpi, size in ICONS.items():
        os.makedirs(os.path.join(res, f'mipmap-{dpi}'))
        with open(os.path.join(res, f'mipmap-{dpi}', 'ic_launcher.png'), 'wb') as f:
            f.write(make_icons.png(size))
    os.makedirs(os.path.join(assets, 'licenses'))
    shutil.copy2(bios, os.path.join(assets, 'openbios.bin'))
    shutil.copy2(os.path.join(PLAYER, 'NOTICE.txt'), os.path.join(assets, 'NOTICE.txt'))
    repo = a.repository or os.environ.get('GITHUB_REPOSITORY') or origin_repository()
    if repo:   # HorizonActivity.checkVersion: a newer release is shown in the menu
        with open(os.path.join(assets, 'releases.txt'), 'w') as f:
            f.write(repo + '\n')
    licences = {'SwanStation-GPL-3.0.txt': os.path.join(sw, 'LICENSE'),
                'OpenBIOS-MIT.txt': os.path.join(work, 'nugget', 'LICENSE') if not a.openbios else
                os.path.join(os.path.dirname(os.path.abspath(a.openbios)), 'OpenBIOS-MIT.txt'),
                'SDL2-zlib.txt': player_build.find(os.path.join(host, '_deps'), {'LICENSE.txt'}),
                'Horizon-MIT.txt': os.path.join(REPO, 'LICENSE')}
    for name, path in licences.items():
        if os.path.exists(path):
            shutil.copy2(path, os.path.join(assets, 'licenses', name))
        else:
            print(f'warning: no {name} ({path})')

    aapt2 = os.path.join(tools, 'aapt2')
    flat = os.path.join(stage, 'res.zip')
    run([aapt2, 'compile', '--dir', res, '-o', flat])
    gen, base = os.path.join(stage, 'gen'), os.path.join(stage, 'base.apk')
    run([aapt2, 'link', '-I', jar, '--manifest', os.path.join(HERE, 'AndroidManifest.xml'), '-A', assets,
         '--min-sdk-version', str(MIN_SDK), '--target-sdk-version', str(TARGET_SDK),
         '--version-code', str(version_code(ver)), '--version-name', ver, '--java', gen, '-o', base, flat])

    # Java: SDL's own activity classes from the SDL source CMake fetched (they match libSDL2.so), then ours
    sdl_java = os.path.join(host, '_deps', 'sdl2-src', 'android-project', 'app', 'src', 'main', 'java')
    sources = [os.path.join(d, f) for root in (sdl_java, os.path.join(HERE, 'java'), gen)
               for d, _, fs in os.walk(root) for f in fs if f.endswith('.java')]
    classes = os.path.join(stage, 'classes')
    run(['javac', '-nowarn', '-Xlint:-options', '-source', '8', '-target', '8', '-encoding', 'UTF-8',
         # core-lambda-stubs: the java.lang.invoke classes lambdas compile against (d8 desugars them)
         '-bootclasspath', os.pathsep.join([jar, os.path.join(tools, 'core-lambda-stubs.jar')]),
         '-classpath', jar, '-d', classes, *sources])
    class_files = [os.path.join(d, f) for d, _, fs in os.walk(classes) for f in fs if f.endswith('.class')]
    dex = os.path.join(stage, 'dex')
    os.makedirs(dex)
    run([os.path.join(tools, 'd8'), '--release', '--min-api', str(MIN_SDK), '--lib', jar, '--output', dex,
         *class_files])

    # the APK: resources + dex + native libraries, aligned and signed
    unsigned = os.path.join(stage, 'unsigned.apk')
    shutil.copy2(base, unsigned)
    with zipfile.ZipFile(unsigned, 'a', zipfile.ZIP_DEFLATED) as z:
        z.write(os.path.join(dex, 'classes.dex'), 'classes.dex')
        for name, path in libs.items():
            stripped = os.path.join(stage, name)
            run([strip, '--strip-unneeded', '-o', stripped, path])
            z.write(stripped, f'lib/{ABI}/{name}')
    aligned = os.path.join(stage, 'aligned.apk')
    run([os.path.join(tools, 'zipalign'), '-f', '-P', '16', '4', unsigned, aligned])

    ks, pw, alias = (os.environ.get(k) for k in ('HORIZON_KEYSTORE', 'HORIZON_KEYSTORE_PASS', 'HORIZON_KEY_ALIAS'))
    if not ks:
        print('warning: no HORIZON_KEYSTORE: signed with a throwaway key (it cannot update an APK signed otherwise)')
        ks, pw, alias = os.path.join(work, 'throwaway.p12'), 'horizon', 'horizon'
        if not os.path.exists(ks):
            run(['keytool', '-genkeypair', '-keystore', ks, '-storetype', 'PKCS12', '-storepass', pw, '-alias', alias,
                 '-keyalg', 'RSA', '-keysize', '2048', '-validity', '10000', '-dname', 'CN=Horizon Play'])
    os.makedirs(os.path.dirname(out), exist_ok=True)
    run([os.path.join(tools, 'apksigner'), 'sign', '--ks', ks, '--ks-pass', 'env:HORIZON_APK_PASS',
         '--ks-key-alias', alias, '--out', out, aligned], env=dict(os.environ, HORIZON_APK_PASS=pw))
    run([os.path.join(tools, 'apksigner'), 'verify', out])
    print(f'Horizon Play {ver} for Android: {out} ({os.path.getsize(out) // 1024} KB)')


if __name__ == '__main__':
    main()
