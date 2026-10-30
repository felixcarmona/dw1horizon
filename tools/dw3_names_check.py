#!/usr/bin/env python3
"""Checks every DW2003 import's name against the game's own tables (docs/reference/imported-species.md).

A DW2003 model code is M<number><4 letters>. digimon_profiles.toml lists the playable Digimon (`value0` = the
model number); esdignam.toml (English names) starts with a blank, so profile k is named strings[k + 1].
For each import (`"game": "dw3"` in mods/experimental/batch-import/*.json) whose model number is in the
profiles, the name must be the official one or a known alias. Fails on a mismatch (a guessed name, like the
"Gokuwmon" that was GranKuwagamon). Numbers not in the profiles (no official name here) are not checked.
Skips (exit 0) when $DW3_ROOT (default: digimonworld2003 next to this repository) is absent.

  tools/dw3_names_check.py
"""
import glob, json, os, re, sys
import tomllib

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..')
DW3 = os.environ.get('DW3_ROOT', os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), 'digimonworld2003'))
PROFILES = os.path.join(DW3, 'ref/ddw3/data/digimon_profiles.toml')
NAMES = os.path.join(DW3, 'ref/ddw3/lang_file/dw2003/eng/esdignam.toml')
# our name -> the game's English name, where we use a different spelling on purpose
ALIASES = {'Grizzlymon': 'Grizzmon', 'Bearmon': 'Kumamon', 'BlackWarGreymon': 'BK WarGreymon'}


def main():
    if not (os.path.exists(PROFILES) and os.path.exists(NAMES)):
        print('skip: DW2003 reference not found (%s)' % DW3)
        return 0
    with open(PROFILES, 'rb') as f:
        profiles = tomllib.load(f)['profiles']
    with open(NAMES, 'rb') as f:
        names = tomllib.load(f)['strings']
    official = {p['value0']: names[k + 1] for k, p in enumerate(profiles)}
    bad = checked = 0
    for path in sorted(glob.glob(os.path.join(ROOT, 'mods/experimental/batch-import/*.json'))):
        with open(path) as f:
            doc = json.load(f)
        for entry in doc.get('digimon', []):
            if entry.get('game') != 'dw3':
                continue
            m = re.match(r'M(\d+)', entry['model'])
            want = official.get(int(m.group(1)))
            if want is None:
                continue
            checked += 1
            if ALIASES.get(entry['name'], entry['name']) != want:
                bad += 1
                print('MISMATCH %s: %s is %s, the game names it %s' % (os.path.basename(path), entry['model'], entry['name'], want))
    print('%d DW2003 imports checked against the official names, %d mismatches' % (checked, bad))
    return 1 if bad else 0


if __name__ == '__main__':
    sys.exit(main())
