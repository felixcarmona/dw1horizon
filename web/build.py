#!/usr/bin/env python3
"""Overlay the website UI and generate /data/ from the selected release tag."""
import argparse
import importlib.util
from pathlib import Path
import shutil

ROOT = Path(__file__).resolve().parents[1]


def build(out, tag):
    # Keep the validated release engine, disc metadata and licenses in place.
    for name in ('index.html', 'style.css', 'favicon.svg', 'engine-sw.js', 'js', 'i18n', 'content', 'media'):
        source, dest = ROOT / 'web' / name, out / name
        if source.is_dir():
            if dest.exists():
                shutil.rmtree(dest)
            shutil.copytree(source, dest)
        else:
            dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(source, dest)
    spec = importlib.util.spec_from_file_location('player_guide', ROOT / 'tools/guide/build.py')
    guide = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(guide)
    data = out / 'data'
    data.mkdir(parents=True, exist_ok=True)
    if not (data / 'discs.json').exists():
        shutil.copyfile(ROOT / 'web/data/discs.json', data / 'discs.json')
    # /data/discs.json is the patcher's metadata; /data/ itself serves the guide.
    guide.build(data, tag)
    return out


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--out', type=Path, required=True)
    parser.add_argument('--tag', required=True)
    args = parser.parse_args()
    build(args.out, args.tag)
