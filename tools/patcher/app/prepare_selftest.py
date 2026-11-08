"""Fetch and verify a tag's package for the frozen desktop self-test, including drafts."""
import argparse
import json
from pathlib import Path
import re
import subprocess
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import desktop


def prepare(tag, out, commit):
    if not re.fullmatch(r'v[0-9]+\.[0-9]+\.[0-9]+', tag):
        raise ValueError('expected a release tag')
    out = Path(out).resolve()
    out.mkdir(parents=True, exist_ok=True)
    # gh authenticates draft asset downloads; the public latest endpoint cannot.
    subprocess.run(['gh', 'release', 'download', tag, '--dir', str(out),
                    '--pattern', desktop.PACKAGE_ASSET, '--pattern', desktop.CHECKSUMS_ASSET], check=True)
    checksums = json.loads((out / desktop.CHECKSUMS_ASSET).read_text(encoding='utf-8'))['package']
    if not isinstance(checksums, dict) or not checksums:
        raise ValueError('missing package checksums')
    folder = desktop.unpack_package(str(out / desktop.PACKAGE_ASSET), str(out / 'package'), checksums)
    info = desktop.package_info(folder)
    if info['version'] != tag[1:] or info['commit'] != commit:
        raise ValueError('package version or commit differs from the checked-out tag')
    print(f"Self-test package: {tag}, commit {commit}, every file verified")
    return folder


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('tag')
    parser.add_argument('--out', default='build/desktop-selftest')
    args = parser.parse_args()
    commit = subprocess.check_output(['git', 'rev-parse', 'HEAD'], text=True).strip()
    prepare(args.tag, args.out, commit)


if __name__ == '__main__':
    main()
