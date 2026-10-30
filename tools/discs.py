#!/usr/bin/env python3
"""Known Digimon World discs, identified by checksum (docs/reference/text-sources.md).

    python3 tools/discs.py identify DISC.bin|DISC.cue|DISC.iso|extracted-dir [...]
    python3 tools/discs.py list
    python3 tools/discs.py web-json web/data/discs.json [--recipe FILE]  # checksums and game languages

A disc is identified by the SHA-1 of its image (Redump dumps: one track, MODE2/2352) or, when the image is not
a known dump (another rip, a patched disc), by the SHA-1 of its key files read straight from the image's ISO 9660
file system: the executable, SCN/DG.SCN and SCN/MAPHEAD.SCN. The registry holds only checksums and facts about
the discs, never their content. Reads the image as data (no code of the disc runs)."""
import hashlib, os, struct, sys

RAW, DATA = 2352, 2048

# id: the text source name (text/<id>/), base: the disc whose layout (executable symbols, script numbering) it shares,
# decomp: the VERSION of decomp/ whose config/<v>/symbols.txt gives the executable's addresses.
DISCS = [
    dict(id='us', title='Digimon World (USA)', serial='SLUS-01032', lang='en', decomp='us', base='us',
         redump='http://redump.org/disc/14957/', size=381771936, crc32='e6fdd00e',
         sha1='5611645da66183e30d11fb6c11a2784ff47e1fdb',
         files={'SLUS_010.32': '31ec666b987d5b007dec40eecc4092d27ed9085b',
                'SCN/DG.SCN': '8cabf0e173a98366cb829ad0a387ec07f0b7e5f5',
                'SCN/MAPHEAD.SCN': '1154027dad3ec5908a63bc0bcbb4c3bea7df4a81'}),
    dict(id='jp', title='DigimonWorld (Japan)', serial='SLPS-01797', lang='ja', decomp='jp', base='jp',
         redump='http://redump.org/disc/55488/', size=381160416, crc32='e93fd3d3',
         sha1='abd99d1b09abe18d0ae3668d2f5087ef8e6e2960',
         files={'SLPS_017.97': 'd11336b31aeceec48267062676e9c3f0833ec13f',
                'SCN/DG.SCN': '9e0b120bbc61efe7a55dc8c6c388de7213fb5f1b',
                'SCN/MAPHEAD.SCN': '8c27fd3dee2bc02f31c3f6900308c338c6d69853'}),
    dict(id='jp-rev1', title='DigimonWorld (Japan) (Rev 1)', serial='SLPS-01797', lang='ja', decomp='jp_rev1',
         base='jp', redump='http://redump.org/disc/37502/', size=381162768, crc32='8dcabdbf',
         sha1='1d10389deee8c9849136623785c256071f2f9473',
         files={'SLPS_017.97': '82212496037146885e96573bd43aa3f0f4ccee8e',
                'SCN/DG.SCN': '7fcad6b30f3c34842e584d5e58e111854187bb6c',
                'SCN/MAPHEAD.SCN': '56641e5aaee30c1beb95842e991abca137f729dc'}),
    dict(id='es-fan', title='Digimon World, Spanish fan translation of the Japanese disc', serial='SLPS-01797',
         lang='es', decomp=None, base='jp', redump=None, size=381160416, crc32=None,
         sha1='ddfb99b4c2e958c231667d5194e364148b727a74',
         files={'SLPS_017.97': 'af1d2fb9039a93ad63c0f283ef60b36bddb16d59',
                'SCN/DG.SCN': 'eadad3045a9506d9d9cf4b4763ed01738c337f26',
                'SCN/MAPHEAD.SCN': '3eb419c801c0bcbe6cfbd3150c37c0145a49e011'}),
]
BY_SHA1 = {d['sha1']: d for d in DISCS}

# Other releases of Digimon World itself as base discs (redump): the same game data as the USA disc
# (tools/basedisc.py lays their files out as the USA dump). Supported since the build stopped reading the USA executable,
# overlays, scripts and text (the disc built from the Spanish one differs only in its two intro movies and the 7 bytes of
# FILE_OFFSET_TABLE that point at them; tested in an emulator; docs/patcher.md "Regional disc inputs"). game='us': they stand in for
# the USA disc.
DW1_RELEASES = [
    dict(game='us', id='dw1-eu', title='Digimon World (Europe)', serial='SLES-02914', boot='SLES_029.14',
         redump='http://redump.org/disc/4264/', size=387129792, crc32='028ae52b',
         sha1='9c2922445280309f3d9c62bb70b57d6ad6da015a', supported=True),
    dict(game='us', id='dw1-fr', title='Digimon World (France)', serial='SLES-03435', boot='SLES_034.35',
         redump='http://redump.org/disc/28228/', size=392482944, crc32='a4e783fe',
         sha1='adfaa62f6756d1e363c50bd414d60a45f1f864b2', supported=True),
    dict(game='us', id='dw1-de', title='Digimon World (Germany)', serial='SLES-03434', boot='SLES_034.34',
         redump='http://redump.org/disc/3059/', size=392485296, crc32='e8abaab4',
         sha1='408fa08bf1b8a72f421d6caa02f146cf43513133', supported=True),
    dict(game='us', id='dw1-es', title='Digimon World (Spain)', serial='SLES-03436', boot='SLES_034.36',
         redump='http://redump.org/disc/10761/', size=392490000, crc32='646fdc95',
         sha1='b90a8efa596771ad84f678d64786fcc5fdd65889', supported=True),
    dict(game='us', id='dw1-it', title='Digimon World (Italy)', serial='SLES-03437', boot='SLES_034.37',
         redump='http://redump.org/disc/46143/', size=392487648, crc32='8da5b1c4',
         sha1='1478a99829fe3c385d8b342ced861f1fa1be3188', supported=True),
    # The Japanese releases (the same dumps as DISCS jp and jp-rev1, which stay the text sources): Rev 1 carries the
    # USA game data but for baked text (menus, title, VS mode, five maps' signposts: made from its own images by
    # tools/localize) and the five signpost maps' wild Digimon, collision, a warp and two sprites (a patch). Rev 1 is
    # supported (built from it, the disc differs from the USA-based one only in its movies, the
    # FILE_OFFSET_TABLE bytes pointing at them and the localized files and their copies; tested in an emulator,
    # JAPANESE CONTROLS on by default, patch 0241). The first pressing differs further (5 models, the effects file,
    # 11 maps), so it is recognised but not a base (basedisc.py).
    dict(game='us', id='dw1-jp', title='DigimonWorld (Japan)', serial='SLPS-01797', boot='SLPS_017.97',
         redump='http://redump.org/disc/55488/', size=381160416, crc32='e93fd3d3',
         sha1='abd99d1b09abe18d0ae3668d2f5087ef8e6e2960', supported=False),
    dict(game='us', id='dw1-jp1', title='DigimonWorld (Japan) (Rev 1)', serial='SLPS-01797', boot='SLPS_017.97',
         redump='http://redump.org/disc/37502/', size=381162768, crc32='8dcabdbf',
         sha1='1d10389deee8c9849136623785c256071f2f9473', supported=True),
]

# The other games whose Digimon the everything disc imports (docs/patcher.md "Regional disc inputs").
# Redump dumps, checked against redump on 2026-10-25. How many species come from each: species_counts().
SOURCE_DISCS = [
    dict(id='dcb', title='Digimon Digital Card Battle (USA)', serial='SLUS-01328', boot='SLUS_013.28',
         redump='http://redump.org/disc/636/', size=215661936, crc32='2cd0aad9',
         sha1='b3945b3e76c1fcc554a7614e2b4211d974990105'),
    dict(id='dw2', title='Digimon World 2 (USA)', serial='SLUS-01193', boot='SLUS_011.93',
         redump='http://redump.org/disc/7304/', size=461993952, crc32='b0cd9681',
         sha1='d9cb009bc0006e901d8ab1365f764ab71da02115'),
    dict(id='dw2003', title='Digimon World 2003 (Europe)', serial='SLES-03936', boot='SLES_039.36',
         redump='http://redump.org/disc/3160/', size=692146560, crc32='007df18e',
         sha1='457cb233349ba841e03b33d8060f8fbcadd45cb3'),
]

# The importers' games (import-batches.json entry.game) by SOURCE_DISCS id.
IMPORT_GAMES = {'dcb': 'dcb', 'dw2': 'dw2', 'dw3': 'dw2003'}


def species_counts():
    """How many of the imported species each source disc gives: {SOURCE_DISCS id: count}, summing to the species of
    content/modeldelta/models.json (the runtime manifest: what the player's build makes). A species' game is the one
    its importer output comes from, the way tools/derive/importers makes it: the recipe of import-batches.json whose
    entry name is its source file's stem (the species may have been renamed since: Lighdramon's source is
    Raidramon.MMD), or, for the four early partner imports, the key of the spec the importer loads (`dcb`: a card
    model of Digital Card Battle, the mega WarGreymon included; `dw2`: a model of Digimon World 2)."""
    import json
    root = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..')
    base = os.path.join(root, 'content', 'modeldelta')
    models = json.load(open(os.path.join(base, 'models.json')))['models']
    by_entry = {}
    for r in json.load(open(os.path.join(base, 'import-batches.json')))['recipes']:
        by_entry.setdefault(r['entry']['name'], set()).add(r['entry']['game'])
    # the partner imports: the same specs tools/derive/importers/__init__.py partner() loads
    partners = {'Veemon': 'content/models/dcb-import/veemon.json', 'Puppetmon': 'content/models/dcb-import/puppetmon.json',
                'Kimeramon': 'content/models/dcb-import/kimeramon-dw2.json', 'WarGreymon': 'content/models/mega/wargreymon-dcb.json'}
    for name, spec in partners.items():
        keys = json.load(open(os.path.join(root, spec))).keys()
        by_entry.setdefault(name, set()).add('dw2' if 'dw2' in keys else 'dcb')
    counts = {d['id']: 0 for d in SOURCE_DISCS}
    for m in models:
        stems = {os.path.splitext(os.path.basename(s['path']))[0] for s in m['mmd']['sources'] + m['tim']['sources']}
        games = set().union(*(by_entry.get(s, set()) for s in stems))
        if len(games) != 1:
            raise ValueError(f"species {m['id']} {m['name']}: its game is not clear from {sorted(stems)} ({sorted(games)})")
        counts[IMPORT_GAMES[games.pop()]] += 1
    assert sum(counts.values()) == len(models), counts
    return counts

# Other releases of the source games (redump, 2026-10-25). Each needs its own reading of the disc (the DCB
# unpacker runs the game's routine at addresses of its executable; DW3's AAA archive may be laid out otherwise)
# and is supported once its models come out equal to the ones the version above gives (dw3-us: tools/dw3release.py).
# game: the SOURCE_DISCS id it stands in for.
SOURCE_VARIANTS = [
    dict(game='dcb', id='dcb-eu', title='Digimon Digital Card Battle (Europe)', serial='SLES-03900', boot='SLES_039.00',
         redump='http://redump.org/disc/7234/', size=215803056, crc32='84cfd91a',
         sha1='30d519490d14a042f52095c9f35b87fd19369ef6', supported=True),   # same models, own unpack routine (dcbrelease.py)
    # The USA Card Battle (2001) is the localisation of Digital Card Arena (2000), not of the Japanese Digital Card
    # Battle (1999, SLPS-02506, redump 1695): that earlier game shares none of the model files.
    dict(game='dcb', id='dcb-jp', title='DigimonWorld: Digital Card Arena (Japan)', serial='SLPS-03101',
         boot='SLPS_031.01', redump='http://redump.org/disc/1685/', size=278996592, crc32='0959e826',
         sha1='6ebf547972205b8cdd07d1014b0835bda0ce2b70', supported=True),   # same models, own unpack routine (dcbrelease.py)
    dict(game='dw2', id='dw2-jp', title='DigimonWorld 2 (Japan)', serial='SLPS-02844', boot='SLPS_028.44',
         redump='http://redump.org/disc/14276/', size=508918704, crc32='28e75fd5',
         sha1='d50dd1a95228deb4d928ed88b3f1386af1c0e64b', supported=True),   # recipe files as USA's (dw2release.py)
    # USA World 3 needs literal PAL model data in its historical normalization recipe.
    # Keep it identifiable but unsupported on the publication build path.
    dict(game='dw2003', id='dw3-us', title='Digimon World 3 (USA)', serial='SLUS-01436', boot='SLUS_014.36',
         redump='http://redump.org/disc/632/', size=647526768, crc32='e3d73a16',
         sha1='f0b022f9be53cbce14640abd8f01beaadcb35208', supported=False),
    dict(game='dw2003', id='dw3-jp', title='DigimonWorld 3: Aratanaru Bouken no Tobira (Japan)', serial='SLPS-03446',
         boot='SLPS_034.46', redump='http://redump.org/disc/19096/', size=690951744, crc32='b46f4f43',
         sha1='8594fb44f601da64087a8996ffd89ab26abb11ea', supported=True),   # recipe models as PAL's (dw3release.py)
]
BOOT = ('SLUS_010.32', 'SLPS_017.97')
KEY_FILES = BOOT + ('SCN/DG.SCN', 'SCN/MAPHEAD.SCN')


def sha1_file(path):
    h = hashlib.sha1()
    with open(path, 'rb') as f:
        for b in iter(lambda: f.read(1 << 22), b''):
            h.update(b)
    return h.hexdigest()


class Image:
    """Read-only ISO 9660 over a raw (2352) or cooked (2048) image."""
    def __init__(self, path):
        self.f = open(path, 'rb'); size = os.path.getsize(path)
        self.raw = size % RAW == 0 and self._sector_raw(16)[1:6] == b'CD001'
        if not self.raw and self._sector(16)[1:6] != b'CD001':
            raise ValueError(f'{path}: not an ISO 9660 image (MODE1/MODE2 2352 or 2048 bytes per sector)')

    def _sector_raw(self, lba):
        self.f.seek(lba * RAW); s = self.f.read(RAW)
        return s[24:24 + DATA] if s[15] == 2 else s[16:16 + DATA]

    def _sector(self, lba):
        if self.raw: return self._sector_raw(lba)
        self.f.seek(lba * DATA); return self.f.read(DATA)

    def read(self, lba, size):
        out = bytearray(); n = 0
        while len(out) < size:
            out += self._sector(lba + n); n += 1
        return bytes(out[:size])

    def find(self, path):
        pvd = self._sector(16); lba, size = struct.unpack_from('<I', pvd, 156 + 2)[0], struct.unpack_from('<I', pvd, 156 + 10)[0]
        for part in path.split('/'):
            d = self.read(lba, size); p = 0; hit = None
            while p < len(d):
                n = d[p]
                if n == 0:
                    p = (p // DATA + 1) * DATA; continue
                name = d[p + 33:p + 33 + d[p + 32]].decode('ascii', 'replace').split(';')[0]
                if name.upper() == part.upper():
                    hit = struct.unpack_from('<I', d, p + 2)[0], struct.unpack_from('<I', d, p + 10)[0]; break
                p += n
            if hit is None: return None
            lba, size = hit
        return self.read(lba, size)


def image_of(path):
    if path.lower().endswith('.cue'):
        for line in open(path, encoding='utf-8', errors='replace'):
            if line.strip().upper().startswith('FILE'):
                name = line.split('"')[1] if '"' in line else line.split()[1]
                return os.path.join(os.path.dirname(path), name)
        raise ValueError(f'{path}: no FILE line')
    return path


def key_hashes(path):
    """{file: sha1} of the key files of an image or an extracted directory (missing files are left out)."""
    out = {}
    if os.path.isdir(path):
        for k in KEY_FILES:
            p = os.path.join(path, k)
            if os.path.exists(p): out[k] = sha1_file(p)
        return out
    img = Image(path)
    for k in KEY_FILES:
        b = img.find(k)
        if b is not None: out[k] = hashlib.sha1(b).hexdigest()
    return out


def identify(path):
    """(disc or None, how, details). how: 'image' (a known dump), 'files' (all key files known), 'partial'."""
    p = image_of(path)
    if os.path.isfile(p):
        known = [d for d in DISCS if d['size'] == os.path.getsize(p)]
        if known:
            h = sha1_file(p)
            if h in BY_SHA1: return BY_SHA1[h], 'image', {'sha1': h}
    kh = key_hashes(p)
    best, score = None, 0
    for d in DISCS:
        s = sum(1 for k, v in kh.items() if d['files'].get(k) == v)
        if s > score: best, score = d, s
    if best and score == len(best['files']): return best, 'files', kh
    return best, 'partial' if best else 'unknown', kh


def release_files():
    """{disc or release id: {path on the disc: SHA-1}} of the files the import converters read, so the web page can
    check an image whose whole-image checksum cannot match redump (a 2048-byte .iso, a PBP, another rip) by the
    files that matter. From content/imports/releases/*.json (tools/dw2release.py, dw3release.py):
    dw3-*: 'recipes' {model code: PAL SHA-1} and, for patched releases, 'patches' {code: {from_sha1}} (the release's
    own file before the patch); dw2-*: 'recipes' {code: {path under AAA/4.AAA/MODEL: SHA-1}}, equal to the USA files.
    Any other <game>-<release>.json (a DCB list, later) is used as it is when it has 'files' {path on the disc:
    SHA-1}. Ids: the release that the recipes are made from is the SOURCE_DISCS id (dcb, dw2, dw2003), the others
    the SOURCE_VARIANTS id (dcb-eu, dw2-jp, dw3-us...)."""
    import glob, json
    rel_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                           'content', 'imports', 'releases')
    out = {}
    for p in sorted(glob.glob(os.path.join(rel_dir, '*.json'))):
        j = json.load(open(p))
        game, rel = os.path.basename(p)[:-5].split('-', 1)
        if game == 'dw3':
            pal_dir, own_dir = 'AAA/DAT/FIGHT/MODEL', {'us': 'AAA/DAT/MODEL'}.get(rel, 'AAA/DAT/FIGHT/MODEL')
            out['dw2003'] = {f'{pal_dir}/{c}.BIN': h for c, h in sorted(j['recipes'].items())}
            patches = j.get('patches', {})
            out[f'dw3-{rel}'] = {f'{own_dir}/{c}.BIN': patches[c]['from_sha1'] if c in patches else h
                                 for c, h in sorted(j['recipes'].items())}
        elif game == 'dw2':
            files = {f'AAA/4.AAA/MODEL/{f}': h for c in sorted(j['recipes']) for f, h in sorted(j['recipes'][c].items())}
            out['dw2'] = files                  # the check made them equal to the USA disc's
            out[f'dw2-{rel}'] = files
        elif 'files' in j:
            out[game if rel == 'us' and game == 'dcb' else f'{game}-{rel}'] = j['files']
    return out


def release_languages(recipe_path=None):
    """The languages the released disc plays in, in the game's own order: the everything recipe's LANGS (what the
    release is built with, tools/derive/recipes/everything.json), ordered as tools/languages.py CODES lists them
    when that module is there (else as the recipe writes them)."""
    import json
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    with open(recipe_path or os.path.join(root, 'tools', 'derive', 'recipes', 'everything.json')) as f:
        recipe = json.load(f)
    codes = [c for c in (recipe['environment'].get('LANGS') or 'en').split(',') if c]
    try:
        sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
        from languages import CODES
    except ImportError:
        return codes
    finally:
        sys.path.pop(0)
    unknown = [c for c in codes if c not in CODES]
    if unknown:
        raise ValueError(f'everything.json LANGS: {unknown} not in tools/languages.py CODES')
    return [c for c in CODES if c in codes]


def web_json(out, recipe_path=None):
    """The web patcher's disc list: the four discs it needs (Digimon World and the three source discs), and the other
    Digimon World discs it recognises (to say which disc was given instead of a bare mismatch). languages: the codes
    the released disc plays in (release_languages()), which the page names in its hero."""
    import json
    us = next(d for d in DISCS if d['id'] == 'us')
    counts = species_counts()      # species: how many imported species come from that disc
    pick = lambda d, *keys: {k: d[k] for k in keys if d.get(k) is not None}
    data = {
        'discs': [dict(pick(us, 'id', 'title', 'serial', 'redump', 'size', 'crc32', 'sha1'), boot='SLUS_010.32')]
                 + [dict(pick(d, 'id', 'title', 'serial', 'boot', 'redump', 'size', 'crc32', 'sha1'), species=counts[d['id']])
                    for d in SOURCE_DISCS],
        'variants': SOURCE_VARIANTS + DW1_RELEASES,
        'files': release_files(),
        'other': [dict(pick(d, 'id', 'title', 'serial', 'size', 'sha1'), boot=d['serial'].replace('-', '_')[:8] + '.'
                       + d['serial'][-2:]) for d in DISCS if d['id'] != 'us']
                 # versions with no registered dump: recognised by their boot file only
                 + [dict(id='jp-best', title='DigimonWorld (Japan, PlayStation the Best)', serial='SLPS-91712',
                         boot='SLPS_917.12')],
        'languages': release_languages(recipe_path),
    }
    os.makedirs(os.path.dirname(out) or '.', exist_ok=True)
    with open(out, 'w') as f:
        json.dump(data, f, indent=1); f.write('\n')
    print(f'{out}: {len(data["discs"])} discs, {len(data["variants"])} other releases of them, '
          f'{len(data["other"])} recognised others, languages {",".join(data["languages"])}')


def source_matrix():
    """Markdown from the same release catalog used by web-json and source extraction."""
    rows = ['# Supported disc releases', '', '<!-- Generated by python3 tools/discs.py source-matrix. -->', '',
            'Supply one supported release of each of the four games.', '',
            '| Game / release | Serial | Supported |', '|---|---|---|']
    for d in [DISCS[0], *DW1_RELEASES, *SOURCE_DISCS, *SOURCE_VARIANTS]:
        rows.append(f"| {d['title']} | {d['serial']} | {'Yes' if d.get('supported', True) else 'No'} |")
    rows += ['', 'USA World 3 is excluded: its historical normalization recipe contains literal PAL game bytes.',
             'Use European World 2003 or Japanese World 3 instead.', '']
    return '\n'.join(rows)


def main(argv):
    if argv == ['source-matrix']:
        print(source_matrix(), end=''); return 0
    if argv and argv[0] == 'web-json':
        import argparse
        parser = argparse.ArgumentParser(description='The web patcher\'s disc metadata')
        parser.add_argument('out')
        parser.add_argument('--recipe', help='recipe of the release being published (default: this checkout)')
        args = parser.parse_args(argv[1:])
        web_json(args.out, args.recipe); return 0
    if len(argv) >= 1 and argv[0] == 'list':
        for d in DISCS:
            print(f"{d['id']:8} {d['title']} [{d['serial']}] {d['lang']} sha1 {d['sha1']} {d['redump'] or ''}")
        return 0
    if len(argv) < 2 or argv[0] != 'identify':
        print(__doc__); return 2
    rc = 0
    for path in argv[1:]:
        try:
            d, how, info = identify(path)
        except (OSError, ValueError) as e:
            print(f'{path}: {e}'); rc = 1; continue
        if how in ('image', 'files'):
            print(f"{path}: {d['id']} ({d['title']}, {d['serial']}) by {'image checksum' if how == 'image' else 'key files'}")
        elif how == 'partial':
            same = [k for k, v in info.items() if d['files'].get(k) == v]
            print(f"{path}: unknown disc; closest is {d['id']} (same {', '.join(same)}); key files: {info}"); rc = 1
        else:
            print(f'{path}: unknown disc; key files: {info}'); rc = 1
    return rc


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
