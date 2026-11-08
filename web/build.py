#!/usr/bin/env python3
"""Overlay website presentation and build the wiki from the selected release tag."""
import argparse
import importlib.util
from pathlib import Path
import shutil

ROOT = Path(__file__).resolve().parents[1]


def build(out, tag, presentation_ref=None):
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
    import sys
    wiki_tools = ROOT / 'tools/wiki'
    sys.path.insert(0, str(wiki_tools))
    spec = importlib.util.spec_from_file_location('horizon_wiki', wiki_tools / 'build.py')
    wiki = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(wiki)
    data = out / 'data'
    data.mkdir(parents=True, exist_ok=True)
    if not (data / 'discs.json').exists():
        shutil.copyfile(ROOT / 'web/data/discs.json', data / 'discs.json')
    shutil.copytree(ROOT / 'tools/guide/assets/font', out / 'media/font', dirs_exist_ok=True)
    wiki.build(out, tag, presentation_ref)
    return out


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--out', type=Path, required=True)
    parser.add_argument('--tag', required=True)
    parser.add_argument('--presentation-ref', help='commit supplying the page code (defaults to HEAD)')
    args = parser.parse_args()
    build(args.out, args.tag, args.presentation_ref)
