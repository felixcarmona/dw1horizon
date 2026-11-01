#!/usr/bin/env python3
"""One verified native compile per language for tools/build-full.sh."""
import argparse
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import time

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from tools.build_cache import Cache, Capture, digest, key

ROOT = Path(__file__).resolve().parents[1]


def source_hashes(tree):
    """All compiler inputs, including generated linker sources and local C edits.

    Generated text headers and make-option headers are outputs, not seed inputs.
    The bank/padding and make arguments that generate them are keyed separately.
    """
    paths = []
    for folder in ('src', 'include', 'asm', 'mk', 'tools', 'text', 'config', 'external', 'bin'):
        paths.extend(p for p in (tree / folder).rglob('*') if p.is_file() and '__pycache__' not in p.parts
                     and '.git' not in p.parts)
    paths += [p for p in tree.iterdir() if p.is_file() and p.name != '.git'
              and p.name not in ('text-bank.json', 'text-bank-pad.json')]
    gen = tree / 'build/us/psx/generated'
    generated_headers = {'file_table_count.h', 'file_table_new.h', 'font_sel.h', 'fps.h',
                         'lang_base.h', 'lang_build.h', 'lang_files.h', 'partner_mmd_max.h', 'version_text.h'}
    paths += [p for p in gen.rglob('*') if p.is_file() and 'text' not in p.relative_to(gen).parts
              and p.name not in generated_headers and not p.name.endswith('.tmp')
              and not (p.name.startswith('undefined_') and p.suffix == '.ld')]
    paths += [p for p in (tree / 'text-bank.json', tree / 'text-bank-pad.json') if p.is_file()]
    return [[str(p.relative_to(tree)), digest(p)] for p in sorted(paths)]


def compile(tree, log, args, cache_dir=None, image=None):
    # Objects may be shared only from a compile with identical common inputs.
    # The bank and LANG_BUILD are deliberately changed between languages; make
    # regenerates those headers after bank copy, exactly as the original driver.
    from tools.sdk_messages import author
    from tools.city_residents import write_extra_header
    write_extra_header(tree)
    author(tree)
    hashes = source_hashes(tree)
    common = key(dict(inputs=[p for p in hashes if p[0] != 'text-bank.json'],
                      args=[a for a in args if not a.startswith('LANG_BUILD=')],
                      image=image, driver=digest(__file__)))
    stamp = tree / 'build/us/psx/gcc/verified-inputs.json'
    try:
        envelope = json.loads(stamp.read_text())
        verified = envelope['record']
        if key(verified) != envelope['sha256']:
            raise ValueError('corrupt verified native inputs')
        reusable = verified['common'] == common and all(digest(tree / p) == h for p, h in verified['objects'])
    except (OSError, ValueError, KeyError, TypeError):
        reusable = False
    gen = tree / 'build/us/psx/generated'
    if reusable:
        # Only verified contents justify object reuse. Normalize logical times
        # so a restored/future object mtime cannot hide a changed language header.
        tick = time.time_ns()
        for name, _ in verified['objects']:
            p = tree / name
            age = 3 if p.is_relative_to(gen) and p.suffix == '.h' else 2
            os.utime(p, ns=(tick - age * 1_000_000_000, tick - age * 1_000_000_000))
        os.utime(tree / 'text-bank.json', ns=(tick, tick))
    else:
        shutil.rmtree(tree / 'build/us/psx/gcc', ignore_errors=True)
        shutil.rmtree(gen / 'text', ignore_errors=True)
        for p in gen.glob('*.h'):
            p.unlink()
        for p in gen.glob('undefined_*.ld'):
            p.unlink()
    cmd = ['docker', 'run', '--rm', '--user', f'{os.getuid()}:{os.getgid()}', '-e', 'HOME=/tmp',
           '-v', f'{tree}:/work']
    if cache_dir:
        objects = Path(cache_dir) / 'compiler'
        objects.mkdir(parents=True, exist_ok=True)
        cmd += ['-v', f'{objects}:/compiler-cache',
                '-v', f'{ROOT / "tools/compiler_cache.py"}:/build-driver/compiler_cache.py:ro',
                '-e', f'DW_COMPILER_IMAGE={image}',
                '-e', 'DW_COMPILER_NAMESPACE=' + key([name for name, _ in source_hashes(tree)])]
    cmd += ['-w', '/work', image or 'dw-build', 'make',
           '-j' + os.environ.get('NATIVE_JOBS', '8'), 'TOOLCHAIN=gcc', *args]
    if cache_dir:
        cmd += ['CC=python3 /build-driver/compiler_cache.py mipsel-linux-gnu-gcc']
    with log.open('w') as f:
        p = subprocess.run(cmd, stdout=f, stderr=subprocess.STDOUT)
    if p.returncode:
        print('\n'.join(log.read_text().splitlines()[-30:]), file=sys.stderr)
        raise SystemExit(p.returncode)
    # Preserve hashes for every object, depfile and generated header. Copying
    # English into another language tree is safe only if these bytes still match.
    outputs = [p for p in (tree / 'build/us/psx/gcc').rglob('*') if p.is_file() and p != stamp]
    outputs += [p for p in gen.rglob('*') if p.is_file()]
    record = dict(common=common, objects=[[str(p.relative_to(tree)), digest(p)] for p in outputs])
    stamp.write_text(json.dumps(dict(record=record, sha256=key(record))))


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('tree', type=Path)
    p.add_argument('bank', type=Path)
    p.add_argument('padding')
    p.add_argument('log', type=Path)
    p.add_argument('make_args', nargs=argparse.REMAINDER)
    a = p.parse_args()
    tree = a.tree.resolve()
    shutil.copyfile(a.bank, tree / 'text-bank.json')
    if a.padding:
        shutil.copyfile(a.padding, tree / 'text-bank-pad.json')
    else:
        (tree / 'text-bank-pad.json').unlink(missing_ok=True)
    start = time.monotonic()
    cache_dir = os.environ.get('DW_BUILD_CACHE')
    image = subprocess.check_output(['docker', 'image', 'inspect', 'dw-build', '--format', '{{.Id}}'], text=True).strip()
    hit = False
    cache = None
    if cache_dir:
        cache = Cache(cache_dir, tree)
        identity = dict(kind='native', tree=str(tree), inputs=source_hashes(tree), args=a.make_args,
                        image=image, pin=subprocess.check_output(['git', 'rev-parse', 'HEAD:decomp'], cwd=ROOT, text=True).strip(),
                        patches=[[p.name, digest(p)] for p in sorted((ROOT / 'mods/patches').glob('*.patch'))],
                        driver=digest(__file__), object_driver=digest(ROOT / 'tools/compiler_cache.py'), cache_code=digest(ROOT / 'tools/build_cache.py'))
        hit = cache.restore(identity) is not None
    if hit:
        a.log.write_text('Verified content cache hit\n')
    else:
        compile(tree, a.log, a.make_args, cache_dir, image)
        if cache:
            cap = Capture(tree)
            cap.writes = {str(p) for base in ('build/us/psx/gcc', 'build/us/psx/generated')
                          for p in (tree / base).rglob('*') if p.is_file()}
            cache.save(identity, cap, {'compiled': True})
    print(f'native {tree.name}: {"hit" if hit else "compiled"}, {time.monotonic()-start:.2f} s', flush=True)


if __name__ == '__main__':
    main()
