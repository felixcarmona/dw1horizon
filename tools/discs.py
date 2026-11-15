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
    dict(game='us', id='dw1-jp', title='DigimonWorld (Japan) (first pressing)', serial='SLPS-01797', boot='SLPS_017.97',
         redump='http://redump.org/disc/55488/', size=381160416, crc32='e93fd3d3',
         sha1='abd99d1b09abe18d0ae3668d2f5087ef8e6e2960', supported=False, soon=True),
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


def species_counts(root=None):
    """How many of the imported species each source disc gives: {SOURCE_DISCS id: count}, summing to the species of
    content/modeldelta/models.json (the runtime manifest: what the player's build makes). A species' game is the one
    its importer output comes from, the way tools/derive/importers makes it: the recipe of import-batches.json whose
    complete output path matches its source file (different games may reuse a filename), or, for the four early
    partner imports, the key of the spec the importer loads (`dcb`: a card
    model of Digital Card Battle, the mega WarGreymon included; `dw2`: a model of Digimon World 2)."""
    import json
    root = os.fspath(root) if root is not None else os.path.join(os.path.dirname(os.path.abspath(__file__)), '..')
    base = os.path.join(root, 'content', 'modeldelta')
    models = json.load(open(os.path.join(base, 'models.json')))['models']
    by_source = {}
    for r in json.load(open(os.path.join(base, 'import-batches.json')))['recipes']:
        for ext in ('MMD', 'TIM'):
            path = f"{r['out']}/{r['entry']['name']}.{ext}"
            by_source.setdefault(path, set()).add(r['entry']['game'])
    # the partner imports: the same specs tools/derive/importers/__init__.py partner() loads
    partners = {'build/dcb/Veemon': 'content/models/dcb-import/veemon.json',
                'build/dcb/Puppetmon': 'content/models/dcb-import/puppetmon.json',
                'build/dw2/Kimeramon': 'content/models/dcb-import/kimeramon-dw2.json',
                'build/models/WarGreymon': 'content/models/mega/wargreymon-dcb.json'}
    for name, spec in partners.items():
        keys = json.load(open(os.path.join(root, spec))).keys()
        for ext in ('MMD', 'TIM'):
            by_source.setdefault(name + '.' + ext, set()).add('dw2' if 'dw2' in keys else 'dcb')
    counts = {d['id']: 0 for d in SOURCE_DISCS}
    for m in models:
        sources = {s['path'] for s in m['mmd']['sources'] + m['tim']['sources']}
        games = set().union(*(by_source.get(s, set()) for s in sources))
        if len(games) != 1:
            raise ValueError(f"species {m['id']} {m['name']}: its game is not clear from {sorted(sources)} ({sorted(games)})")
        counts[IMPORT_GAMES[games.pop()]] += 1
    assert sum(counts.values()) == len(models), counts
    return counts

# Other releases of the source games (redump, 2026-10-25). Each needs its own reading of the disc (the DCB
# unpacker runs the game's routine at addresses of its executable; DW3's AAA archive may be laid out otherwise)
# and is supported once its models come out equal to the ones the version above gives, or once the species that differ
# have imports of their own (dw3-us: tools/dw3release.py, content/modeldelta/variants/).
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
    # USA World 3: its own files for 15 of the 57 recipe models (tools/dw3release.py; Renamon's bones read back in the
    # PAL order). 8 of them still come out as other imports (other meshes or animation keys): Antylamon, Chrysalimon,
    # Ebidramon, Growlmon, Kyubimon, MaloMyotismon, Renamon are made from the USA models with our edits carried onto
    # them (content/modeldelta/variants/dw3-us.json, tools/models/variants.py); the patched disc has checksums of its
    # own with it ("<base>+dw3-us", docs/patcher.md).
    dict(game='dw2003', id='dw3-us', title='Digimon World 3 (USA)', serial='SLUS-01436', boot='SLUS_014.36',
         redump='http://redump.org/disc/632/', size=647526768, crc32='e3d73a16',
         sha1='f0b022f9be53cbce14640abd8f01beaadcb35208', supported=True),   # its own imports (variants/dw3-us.json)
    dict(game='dw2003', id='dw3-jp', title='DigimonWorld 3: Aratanaru Bouken no Tobira (Japan)', serial='SLPS-03446',
         boot='SLPS_034.46', redump='http://redump.org/disc/19096/', size=690951744, crc32='b46f4f43',
         sha1='8594fb44f601da64087a8996ffd89ab26abb11ea', supported=True),   # recipe models as PAL's (dw3release.py)
]
# Releases the patchers recognise but cannot use, and what they say: "<title> isn't supported yet. Use <instead>
# instead. Support is coming in a future version." The list is every entry above with supported=False (soon=True: its
# support is planned, the message promises it), plus the reprints with no dump; the alternatives are the supported
# releases of the same slot. When a release becomes supported its message goes away by itself.
NO_DUMP = [dict(game='us', id='jp-best', title='DigimonWorld (Japan, PlayStation the Best)', serial='SLPS-91712',
                boot='SLPS_917.12')]


def instead(release):
    """Titles of the supported releases that can be used instead of `release` (one of its game's slot)."""
    game = release['game']
    if game == 'us':
        pool = [DISCS[0]] + DW1_RELEASES
    else:
        pool = [d for d in SOURCE_DISCS if d['id'] == game] + [v for v in SOURCE_VARIANTS if v['game'] == game]
    return [d['title'] for d in pool if d.get('supported', True)]


def unsupported():
    """The recognised releases no patcher accepts, each with 'instead' (titles) and 'soon'."""
    return [dict(d, instead=instead(d), soon=bool(d.get('soon')))
            for d in DW1_RELEASES + SOURCE_VARIANTS + NO_DUMP if not d.get('supported', True)]


def or_list(items):
    return items[0] if len(items) == 1 else ', '.join(items[:-1]) + ' or ' + items[-1]


def notice(release):
    """The English message for an unsupported release (the web and desktop patchers say it in every language:
    why.notYet / why.useInstead)."""
    text = f"{release['title']} isn't supported yet. " if release.get('soon') else f"{release['title']} can't be used. "
    text += f"Use {or_list(instead(release))} instead."
    return text + (' Support is coming in a future version.' if release.get('soon') else '')


def unsupported_match(boot, size=None, sha1=None):
    """The unsupported release a disc is, by its boot file and, where releases share one, its size or SHA-1; None
    when it is not one (or could be a supported one)."""
    same = [d for d in DW1_RELEASES + SOURCE_VARIANTS + NO_DUMP + [DISCS[0]] + SOURCE_DISCS if d.get('boot') == boot]
    if sha1:
        hit = [d for d in same if d.get('sha1') == sha1]
        same = hit or same
    if size is not None and len(same) > 1:
        same = [d for d in same if d.get('size') == size] or same
    if same and all(not d.get('supported', True) for d in same):
        return same[0]
    return None


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


# The DW2 effect files the species' own effects are converted from (content/battle/own-effects.json,
# tools/derive/steps/effects.py), equal on the USA and Japanese discs
DW2_EFFECT_FILES = {
    'AAA/4.AAA/EFFECT/EFFEWA/MEWA0200.BIN': '0b61553c992d492673b7cbc3d9772a94a944b3eb',
    'AAA/4.AAA/EFFECT/EFFEWA/AEWA0200.BIN': '223b421d4b99b568c73f02618c106f1665c9f678',
    'AAA/4.AAA/EFFECT/EFFEWD/MEWD0100.BIN': 'c4e54f49dc8ba2541a017abcb07eb771b3d1e8ff',
    'AAA/4.AAA/EFFECT/EFFEWD/AEWD0100.BIN': 'e089604f7241622820339c7ee5e63259d072d01c',
    'AAA/4.AAA/EFFECT/EFFEWA/MEWA0300.BIN': '8b99f7444497f908bfed72d11a10aff10192ca49',
    'AAA/4.AAA/EFFECT/EFFEWA/AEWA0300.BIN': '223b421d4b99b568c73f02618c106f1665c9f678',
    'AAA/4.AAA/EFFECT/EFFEWD/MEWD0200.BIN': '2717b373e34b262c216a9d12b3257d7a8467b5c2',
    'AAA/4.AAA/EFFECT/EFFEWD/AEWD0200.BIN': 'e089604f7241622820339c7ee5e63259d072d01c',
    'AAA/4.AAA/EFFECT/EFFESA/MESA2700.BIN': '36d088316ac3e0988babc09fba444780d5cdfccb',
    'AAA/4.AAA/EFFECT/EFFESA/AESA2700.BIN': '4d152f09de4c00c4a29ee58c0d50580ec3af1f02',
    'AAA/4.AAA/EFFECT/EFFESD/MESD0600.BIN': 'ee3da6aa1fd08408aeb7c2603812078b83eeeee1',
    'AAA/4.AAA/EFFECT/EFFESD/AESD0600.BIN': 'cdb1fb002fa2ca4b649e15d237bdae8cbc51a7cc',
    'AAA/4.AAA/EFFECT/EFFEBA/MEBA1800.BIN': '9aa6b876d82a84f98eb8949cef40489ab13f5e3d',
    'AAA/4.AAA/EFFECT/EFFEBA/AEBA1800.BIN': '15a9a70578f17546fb5e6a1979e50769aa2dd62d',
    'AAA/4.AAA/EFFECT/EFFEBA/MEBA1900.BIN': '005d16f41986b5e049035bf126c7fb74e75c6ca8',
    'AAA/4.AAA/EFFECT/EFFEBA/AEBA1900.BIN': 'bba0cc32d04d3d0267ebd3acec1137640169f072',
    'AAA/4.AAA/EFFECT/EFFESD/MESD0000.BIN': '606739cc876d4f568a663161dac672287cbf6287',
    'AAA/4.AAA/EFFECT/EFFESD/AESD0000.BIN': 'fce13b1cdd36ed3aa1c1e3338b27a17c80ac735e',
    'AAA/4.AAA/EFFECT/EFFEUA/MEUA3900.BIN': '1694749c2db44f523ecc54374b6fa1489ed5b74a',
    'AAA/4.AAA/EFFECT/EFFEUA/AEUA3900.BIN': '920c781a332ff50f046f1f2a526a27d31207cbd2',
    'AAA/4.AAA/EFFECT/EFFEUA/MEUA4000.BIN': '119dbcb155f281df69dab846ead65c92b7a1359b',
    'AAA/4.AAA/EFFECT/EFFEUA/AEUA4000.BIN': '1fd9833e877ed751e750049a17ad098fa81e2271',
    'AAA/4.AAA/EFFECT/EFFEUA/MEUA1400.BIN': 'efb5427a6b882ba851e9b806c209cd53866a7cb4',
    'AAA/4.AAA/EFFECT/EFFEUA/AEUA1400.BIN': 'c966e807badd6781c67aefec04b3a1fa4bbbacd5',
    'AAA/4.AAA/EFFECT/EFFEUA/MEUA1500.BIN': '3e81ee074af07e7746f5124b4fcb6584d23729e6',
    'AAA/4.AAA/EFFECT/EFFEUA/AEUA1500.BIN': 'a0745be4bb202b4f4d6654f1874a57dfb9da893e',
    'AAA/4.AAA/EFFECT/EFFESD/MESD1500.BIN': 'fcf5b95c7b15f7c746bc74eaa1b4f13ce2baf2f2',
    'AAA/4.AAA/EFFECT/EFFESD/AESD1500.BIN': 'fd862c774fe9ec070c6bb64b1448e905d8b6fe5b',
    'AAA/4.AAA/EFFECT/EFFESA/MESA0000.BIN': '133219031d9395263c07dae14222ee665a990d6d',
    'AAA/4.AAA/EFFECT/EFFESA/AESA0000.BIN': 'ed283c2a635515bed88faa3cd97a5663b754aad1',
    'AAA/4.AAA/EFFECT/EFFESA/MESA6000.BIN': '7b271d73aba059729d549451b4de2ed8f7d3fc96',
    'AAA/4.AAA/EFFECT/EFFESA/AESA6000.BIN': '0c7364f4bad2e647e07f140b5502469ea0f876c7',
    'AAA/4.AAA/EFFECT/EFFESA/MESA6100.BIN': '46031c34fa6584e5797cc53d32045531556b4157',
    'AAA/4.AAA/EFFECT/EFFESA/AESA6100.BIN': 'a7d429577f26f1b9efd85713523e5f6cb06b06d5',
    'AAA/4.AAA/EFFECT/EFFESD/MESD7400.BIN': '5c53e5720e1e83feec3b2d0151b9f60c3ad73c13',
    'AAA/4.AAA/EFFECT/EFFESD/AESD7400.BIN': '6821561e185801fbfe9854b47d113be805a3a563',
    'AAA/4.AAA/EFFECT/EFFESA/MESA4000.BIN': 'c070ddb4370c06a5c40158c5b829507a61a8d234',
    'AAA/4.AAA/EFFECT/EFFESA/AESA4000.BIN': '0d704357c022e7c58921bdb0cf7d81ef1ea19056',
    'AAA/4.AAA/EFFECT/EFFESA/MESA4100.BIN': '7c4a584ae7e65a0b4ebc76f8eae7c2dca6a9dead',
    'AAA/4.AAA/EFFECT/EFFESA/AESA4100.BIN': '39969c13f3418c529ec27d4bc42e63a4c71feedc',
    'AAA/4.AAA/EFFECT/EFFESD/MESD7100.BIN': '999c5d864b1f7b89c5239cf47bc67b12c9c4ea5b',
    'AAA/4.AAA/EFFECT/EFFESD/AESD7100.BIN': '6821561e185801fbfe9854b47d113be805a3a563',
    'AAA/4.AAA/EFFECT/EFFEFA/MEFA0900.BIN': 'c3b7fc5936367a7537d13e9305f792d7becadcc2',
    'AAA/4.AAA/EFFECT/EFFEFA/AEFA0900.BIN': '5553a1aea66a5165356e241ae2da8a9148c5de98',
    'AAA/4.AAA/EFFECT/EFFEFA/MEFA1000.BIN': 'a54b1f55ed4ff9bf699cf74e75b436ffbbecdc6d',
    'AAA/4.AAA/EFFECT/EFFEFA/AEFA1000.BIN': '74bba5fed657052a9f7ae4b41b0221258559b11d',
    'AAA/4.AAA/EFFECT/EFFEFD/MEFD0400.BIN': '6b66f61268740eab6f179a4d515abe9e66772d20',
    'AAA/4.AAA/EFFECT/EFFEFD/AEFD0400.BIN': 'eed2cf0262fda521f340b8baf9b65967c98f9b0e',
    'AAA/4.AAA/EFFECT/EFFEMA/MEMA4500.BIN': '2e9ea1f5304ef492f7f897bac4a9ab25d81f4065',
    'AAA/4.AAA/EFFECT/EFFEMA/AEMA4500.BIN': '61be8034ec4f1868f98429f33b30aa1083a83f88',
    'AAA/4.AAA/EFFECT/EFFEMA/MEMA4600.BIN': '6d66c298b7c5b335a88ced14ef22e6c63a2e19d1',
    'AAA/4.AAA/EFFECT/EFFEMA/AEMA4600.BIN': 'a7d429577f26f1b9efd85713523e5f6cb06b06d5',
    'AAA/4.AAA/EFFECT/EFFESA/MESA9100.BIN': '58322f7044427a3cfaff099822b3b5c0b87d6168',
    'AAA/4.AAA/EFFECT/EFFESA/AESA9100.BIN': 'b02e9f262995a152c98426934c04a1e10ac745cd',
    'AAA/4.AAA/EFFECT/EFFESA/MESA9200.BIN': '317813e9ff5f9ca2a0ece88353dc8c28be9c5fc9',
    'AAA/4.AAA/EFFECT/EFFESA/AESA9200.BIN': 'bae9e59e0d9cd0d2d75401e837209de5a3bb8be4',
    'AAA/4.AAA/EFFECT/EFFESA/MESA6200.BIN': '9c95ef23674ead8db7aceea644737d4fbdbb627c',
    'AAA/4.AAA/EFFECT/EFFESA/AESA6200.BIN': '9792e0cd7c8449f49a0ef84afcb0a6dcd99f1c09',
    'AAA/4.AAA/EFFECT/EFFESA/MESA6300.BIN': '3882f9c424cdcef63b355486d4a6a6a99fb28e04',
    'AAA/4.AAA/EFFECT/EFFESA/AESA6300.BIN': 'a7d429577f26f1b9efd85713523e5f6cb06b06d5',
    'AAA/4.AAA/EFFECT/EFFESD/MESD3800.BIN': '89d4114c76cbb9805f2379c17359f61e0589abd0',
    'AAA/4.AAA/EFFECT/EFFESD/AESD3800.BIN': 'f2423fe6605d27e398569dfb281b51fa9c83ec7b',
    'AAA/4.AAA/EFFECT/EFFEUA/MEUA2000.BIN': '6f27cc00632b741937476eacd13a4efcf9141468',
    'AAA/4.AAA/EFFECT/EFFEUA/AEUA2000.BIN': '7a9b5e5adfe67770843c4d7d661c855b27dc539a',
    'AAA/4.AAA/EFFECT/EFFEUA/MEUA2100.BIN': 'd898dbbee248bab15ec9b242e513979b06a76b5e',
    'AAA/4.AAA/EFFECT/EFFEUA/AEUA2100.BIN': 'a7d429577f26f1b9efd85713523e5f6cb06b06d5',
    'AAA/4.AAA/EFFECT/EFFEMA/MEMA6100.BIN': 'e35b67facb92489317444307358d3ea49cc70683',
    'AAA/4.AAA/EFFECT/EFFEMA/AEMA6100.BIN': '895441ccbef2da538a78aa325fb0dcefd3e65f50',
    'AAA/4.AAA/EFFECT/EFFEMA/MEMA6200.BIN': 'da17d79ceec2dd428faf3d1ff4a169032ab4175c',
    'AAA/4.AAA/EFFECT/EFFEMA/AEMA6200.BIN': '60206a5a78e3e2f0f509367d37fd005a88f958d0',
    'AAA/4.AAA/EFFECT/EFFESD/MESD3200.BIN': 'be5010f814100f42a164bfd72d3ac16131566af0',
    'AAA/4.AAA/EFFECT/EFFESD/AESD3200.BIN': 'b272d098828d964e0fd6837a8ae0ee0319a00d28',
    'AAA/4.AAA/EFFECT/EFFEUA/MEUA3100.BIN': '9a0269e8679e79dc41807fc4cf41085a50b4a9df',
    'AAA/4.AAA/EFFECT/EFFEUA/AEUA3100.BIN': '3120626371a56909674b9f4c4068e1e802a2fb48',
    'AAA/4.AAA/EFFECT/EFFEUA/MEUA3200.BIN': '4673715233679ea399658eb7bb733aeef56c6705',
    'AAA/4.AAA/EFFECT/EFFEUA/AEUA3200.BIN': '6e3795cf8763d2ed7614e2ce3b8498fa181cc299',
    'AAA/4.AAA/EFFECT/EFFESD/MESD7600.BIN': 'a5d0df37179d5c4a10f60cc163a9ff9f2c157174',
    'AAA/4.AAA/EFFECT/EFFESD/AESD7600.BIN': '71cd378e9cb036cd8816980c2a924628a9c59a29',
    'AAA/4.AAA/EFFECT/EFFEMA/MEMA3300.BIN': '62ddb1caaf4c9e5542b70b44b2daadd34da6b7ec',
    'AAA/4.AAA/EFFECT/EFFEMA/AEMA3300.BIN': '8dd946010e950178b3b1c615b1f83ba70e4177c9',
    'AAA/4.AAA/EFFECT/EFFEMA/MEMA3400.BIN': '078f5699bcbc2fd25366697b61710b38e837d0c8',
    'AAA/4.AAA/EFFECT/EFFEMA/AEMA3400.BIN': '64e6423bb8748d9934dfaa91fa29a73d4d9700c8',
    'AAA/4.AAA/EFFECT/EFFEBD/MEBD0000.BIN': '6e6ce5f46fd43bb0542e071b39ae67127bf385cf',
    'AAA/4.AAA/EFFECT/EFFEBD/AEBD0000.BIN': '2171f395f89698143f6bba4b27b43778445209c8',
    'AAA/4.AAA/EFFECT/EFFESA/MESA6800.BIN': '59432cbf98bd6bb84f4f06cd0cba738a9f7e742c',
    'AAA/4.AAA/EFFECT/EFFESA/AESA6800.BIN': '04997dd3fce0229052c782f36bff21b10040192b',
    'AAA/4.AAA/EFFECT/EFFESA/MESA6900.BIN': '8d5f1994b66a0d0f006de8f60f60d21c122bcc04',
    'AAA/4.AAA/EFFECT/EFFESA/AESA6900.BIN': 'a1f13ba8c2472d5eef40f9618f2010d59c98dee0',
    'AAA/4.AAA/EFFECT/EFFEUA/MEUA2800.BIN': '83672b8476d4e93a9c47148bdbd2587a4c58b50e',
    'AAA/4.AAA/EFFECT/EFFEUA/AEUA2800.BIN': '79e89f056672202721b60b14db986d94a0d08d05',
    'AAA/4.AAA/EFFECT/EFFEUA/MEUA2900.BIN': 'c3d80e1d0fbde68e41b47b3abe26252f03bf805f',
    'AAA/4.AAA/EFFECT/EFFEUA/AEUA2900.BIN': 'a7d429577f26f1b9efd85713523e5f6cb06b06d5',
    'AAA/4.AAA/EFFECT/EFFESD/MESD0200.BIN': 'f5568381b73eb31d1c11b40ce3d53e6756ab0cc0',
    'AAA/4.AAA/EFFECT/EFFESD/AESD0200.BIN': '905822e77d0a5a0bcbde7330388186e241eeb276',
    'AAA/4.AAA/EFFECT/EFFESA/MESA4800.BIN': 'fcc9b43d914ccc9695c3a4daa347792573b465fc',
    'AAA/4.AAA/EFFECT/EFFESA/AESA4800.BIN': 'ad7968418b336ad4f8b74ebecd5d575bd37cce08',
    'AAA/4.AAA/EFFECT/EFFESA/MESA4900.BIN': 'f942383cc50fa2c38bf115e8c2a9ab8888997e4a',
    'AAA/4.AAA/EFFECT/EFFESA/AESA4900.BIN': 'f2eaa4acf6a91034f52fad8cc0c12acdd89afb14',
    'AAA/4.AAA/EFFECT/EFFESA/MESA2600.BIN': '965724e229bcffafb8ad6630115ac4f6d884a025',
    'AAA/4.AAA/EFFECT/EFFESA/AESA2600.BIN': 'ea5e30e9df3331d9308a72052930c6a5b8ed8e9d',
    'AAA/4.AAA/EFFECT/EFFEWD/MEWD0300.BIN': 'e84ab1c7c20a45cb3884de2ec8e23daa1330fd70',
    'AAA/4.AAA/EFFECT/EFFEWD/AEWD0300.BIN': 'e089604f7241622820339c7ee5e63259d072d01c',
    'AAA/4.AAA/EFFECT/EFFEMA/MEMA4200.BIN': '5d51d75639202ab417e544f0fc1fb2ea012d88ea',
    'AAA/4.AAA/EFFECT/EFFEMA/AEMA4200.BIN': 'bc589ceea3de1a727c818cd0a7dda467b4f13fdf',
    'AAA/4.AAA/EFFECT/EFFEMA/MEMA4400.BIN': '0a6b19310e3cbc89e8088df38733357fd5ae096f',
    'AAA/4.AAA/EFFECT/EFFEMA/AEMA4400.BIN': 'a7d429577f26f1b9efd85713523e5f6cb06b06d5',
    'AAA/4.AAA/EFFECT/EFFEBA/MEBA0600.BIN': '94e42da34aa0e0190175a0eadf7b13951d447277',
    'AAA/4.AAA/EFFECT/EFFEBA/AEBA0600.BIN': '4acd6cb74b1cc1dfbd64a21f9f299a93db4f088d',
    'AAA/4.AAA/EFFECT/EFFEBA/MEBA0700.BIN': 'af4e1a06a411b9dc1c5f80f2a0d0728521920a95',
    'AAA/4.AAA/EFFECT/EFFEBA/AEBA0700.BIN': 'f122816d353959bf579d3dcc69697fe4bb605b82',
    'AAA/4.AAA/EFFECT/EFFESA/MESA4200.BIN': 'ab2544f14a90f1832306f0746e5ac220d280a82e',
    'AAA/4.AAA/EFFECT/EFFESA/AESA4200.BIN': '7b473ac409fe44ac9bfd4540a7008376f8b18076',
    'AAA/4.AAA/EFFECT/EFFESA/MESA4300.BIN': 'def90f5cf3bb94f17bdc23025bf081446644de46',
    'AAA/4.AAA/EFFECT/EFFESA/AESA4300.BIN': 'a7d429577f26f1b9efd85713523e5f6cb06b06d5',
    'AAA/4.AAA/EFFECT/EFFESA/MESA2900.BIN': '60bbf417a94bf134016fc707eee922e492f131ca',
    'AAA/4.AAA/EFFECT/EFFESA/AESA2900.BIN': '5d3394f2c57f518bfe4e1dcabc7ff011243bbf19',
    'AAA/4.AAA/EFFECT/EFFESA/MESA2500.BIN': 'b47b7a434b7eb8e97c7eea757d7d6b1e07469a57',
    'AAA/4.AAA/EFFECT/EFFESA/AESA2500.BIN': '4f15869beee7eb0206450e987d4bc6bdc7ad477c',
    'AAA/4.AAA/EFFECT/EFFESA/MESA7800.BIN': '416193dda0b3feedaafe7ef66b3974ff434c64a1',
    'AAA/4.AAA/EFFECT/EFFESA/AESA7800.BIN': 'af5d0f0d31c64d1207065bb94b26f3a464e372c9',
    'AAA/4.AAA/EFFECT/EFFESA/MESA7900.BIN': '5677e44d46b1619983185211d475924fffea6296',
    'AAA/4.AAA/EFFECT/EFFESA/AESA7900.BIN': 'a7d429577f26f1b9efd85713523e5f6cb06b06d5',
    'AAA/4.AAA/EFFECT/EFFEMA/MEMA3100.BIN': 'af3d7fe46ae641f70dbf52df6d53398cb107477e',
    'AAA/4.AAA/EFFECT/EFFEMA/AEMA3100.BIN': '5553a1aea66a5165356e241ae2da8a9148c5de98',
    'AAA/4.AAA/EFFECT/EFFEMA/MEMA3200.BIN': '0172c752fd9097cc7517472afb785393a8cf8749',
    'AAA/4.AAA/EFFECT/EFFEMA/AEMA3200.BIN': 'f4535e285bfee5c2c722d8e1f03fb5001ce231c4',
    'AAA/4.AAA/EFFECT/EFFESD/MESD3400.BIN': 'ade5bbcf2017ce1c2b0889ce10cdda0944fdc3ab',
    'AAA/4.AAA/EFFECT/EFFESD/AESD3400.BIN': 'b272d098828d964e0fd6837a8ae0ee0319a00d28',
    'AAA/4.AAA/EFFECT/EFFESA/MESA8700.BIN': 'e04016376ec42d8c65ebbe4b28da5d44c3015925',
    'AAA/4.AAA/EFFECT/EFFESA/AESA8700.BIN': '238252616e4db203d140042e86f676e6a230dae4',
    'AAA/4.AAA/EFFECT/EFFESA/MESA8800.BIN': 'd898dbbee248bab15ec9b242e513979b06a76b5e',
    'AAA/4.AAA/EFFECT/EFFESA/AESA8800.BIN': 'a7d429577f26f1b9efd85713523e5f6cb06b06d5',
    'AAA/4.AAA/EFFECT/EFFEBA/MEBA2400.BIN': '8ce16fe1b70394f136f403452ed7e90fae19ee99',
    'AAA/4.AAA/EFFECT/EFFEBA/AEBA2400.BIN': 'f39168d09c1e4430a9b30c26209c785230702e59',
    'AAA/4.AAA/EFFECT/EFFEBA/MEBA2500.BIN': 'ac83428d93008863ce7576aec23ca553c9ad7b1c',
    'AAA/4.AAA/EFFECT/EFFEBA/AEBA2500.BIN': '96b1e03d98a011388689d03ac6f4019bcf0b35cf',
    'AAA/4.AAA/EFFECT/EFFEMA/MEMA5300.BIN': '7f7cf4cdb3fc1f9285423e4e6408c9160b17c89e',
    'AAA/4.AAA/EFFECT/EFFEMA/AEMA5300.BIN': '9b6fd0a0130e006334f813475b7d77f286fda936',
    'AAA/4.AAA/EFFECT/EFFEMA/MEMA5400.BIN': 'f4fc478c1ab8d300ffbb799c335aa3bbe7b7637f',
    'AAA/4.AAA/EFFECT/EFFEMA/AEMA5400.BIN': 'e74bf4147682b621678d7c984d0564229175a1ea',
    'AAA/4.AAA/EFFECT/EFFESA/MESA6600.BIN': '519d33725754825430e37017d80bcd03887de1ba',
    'AAA/4.AAA/EFFECT/EFFESA/AESA6600.BIN': '065bcefcd2c06ffc30eb9adabb9411aef0daf1e3',
    'AAA/4.AAA/EFFECT/EFFESA/MESA6700.BIN': '59b861c03a3aa2034e150ae24a8fba0b3421e1f6',
    'AAA/4.AAA/EFFECT/EFFESA/AESA6700.BIN': 'a7d429577f26f1b9efd85713523e5f6cb06b06d5',
    'AAA/4.AAA/EFFECT/EFFEBA/MEBA0200.BIN': '5b0df51cad3b3578fd75383d4513bd7932f9eab7',
    'AAA/4.AAA/EFFECT/EFFEBA/AEBA0200.BIN': 'f4d75ef17b33fb891bf2bf7443ca8d78c3846211',
    'AAA/4.AAA/EFFECT/EFFEBA/MEBA0300.BIN': 'd91604856bee569fb33c4b55bb6d57465c7b664b',
    'AAA/4.AAA/EFFECT/EFFEBA/AEBA0300.BIN': '0bd8d7572bc4b8d66f29f4bf9cc16c582e7163bc',
    'AAA/4.AAA/EFFECT/EFFESD/MESD6800.BIN': 'aa07136cc0090e20ec09dae3329c0dbbe03b6a23',
    'AAA/4.AAA/EFFECT/EFFESD/AESD6800.BIN': '6821561e185801fbfe9854b47d113be805a3a563',
    'AAA/4.AAA/EFFECT/EFFESA/MESA2000.BIN': '5b92d3912749bba94acdbfe3915d577fde21096e',
    'AAA/4.AAA/EFFECT/EFFESA/AESA2000.BIN': '230aebd681f0529785e53374e64afdafde1b2d95',
    'AAA/4.AAA/EFFECT/EFFESD/MESD0400.BIN': '6cbbd4b65bcbacdc705fcf3e5c867c2165926507',
    'AAA/4.AAA/EFFECT/EFFESD/AESD0400.BIN': '905822e77d0a5a0bcbde7330388186e241eeb276',
    'AAA/4.AAA/EFFECT/EFFESA/MESA7200.BIN': 'd9819e1f77badd1d108784519cf86874ec5a04bd',
    'AAA/4.AAA/EFFECT/EFFESA/AESA7200.BIN': '68b78b0eae99bd5a6debee2a3f53e81d957aa880',
    'AAA/4.AAA/EFFECT/EFFESA/MESA7300.BIN': '6517fc5ee93a49461dc89786ccff842330707da0',
    'AAA/4.AAA/EFFECT/EFFESA/AESA7300.BIN': 'a7d429577f26f1b9efd85713523e5f6cb06b06d5',
    'AAA/4.AAA/EFFECT/EFFESA/MESA9300.BIN': 'b4f092d0afb2ef8d9aa587f4a39ebeb8c71ba26c',
    'AAA/4.AAA/EFFECT/EFFESA/AESA9300.BIN': 'e9af98d1f7145606e7912321d9d966cb326a6e4b',
    'AAA/4.AAA/EFFECT/EFFESA/MESA9400.BIN': '44516ecad67db2e54b072732b257e999003e4d44',
    'AAA/4.AAA/EFFECT/EFFESA/AESA9400.BIN': 'b8b46db338f0e0ef814ccb6a886169de978e2b3d',
}


# The DW2003 3D effect and sprite pack files the species' own effects are converted from (content/battle/own-effects.json "dw3",
# tools/derive/steps/effects.py), by name: equal on the European, USA and Japanese discs, in AAA/DAT/FIGHT/EFFECT
# (AAA/DAT/EFFECT on the USA disc)
DW3_EFFECT_FILES = {
    'E000COM1.BIN': '5534ae21bb8e77441e7b74af9a41f1c5b6a06b81',
    'E000COM3.BIN': '802f74f378bffbc351663ffeb59b90f32b32f906',
    'F000COM1.BIN': '434e9b71451dd91296c5375965498a7224db38a3',
    'F000COM3.BIN': '4fc480d910734b56a88c657dc37128e85aea32df',
    'MEFT0039.BIN': 'aa755f346627524fcd6f93068f96a62bd2370166',
    'MEFT0085.BIN': '60918c93f664c9785eae7730de758c164d34bba5',
    'MEFT0087.BIN': '1848667d8c4a8322d440ef54264a86863bb4f7e6',
    'MEFT0089.BIN': '948f7838af63802f176318f6bad05eab185fac49',
    'MEFT0091.BIN': 'f308eb007b8c4a2189acbe0a8c124da327f505b0',
    'MEFT0092.BIN': '552825aaf1d78da4fc2858890012e3e35c9fbf4a',
    'MEFT0093.BIN': 'b67773a88f4d90ab810437ef0845af07380efbc2',
    'MEFT0094.BIN': 'f6b1a6d725207d120aa38382202087b08480776d',
    'MEFT0095.BIN': 'a49bc1dbee659cb12c8d5c6a28d8ecc7f39da100',
    'MEFT0096.BIN': '968426fa628b6294fa66d2c92dde1df1a9ff4f2e',
    'MEFT0097.BIN': '5a0a37bc6e4898d9f3e7cb1dd2846b228e541cd9',
    'MEFT0100.BIN': '1f414c76afbe771929581a02e8f301adcb492767',
    'MEFT0102.BIN': 'c1cfe4c5b904df3b268a45d96143052463e146f4',
    'MEFT0324.BIN': '0715ed980ca5367513768c625281a50f90fa03e0',
    'MEFT0328.BIN': '723204db2701e459ac800ae759c5a0bed6dd76a1',
    'MEFT0332.BIN': '936dd6203c3638b49b503a3951327ccdc1c4df0b',
    'MEFT0333.BIN': '05d7a2726ba9252ae0a8d1a6b27d975f0960554b',
    'MEFT0335.BIN': '1c856b0ba8f7adc753b7af88f083d3d3707dfb78',
    'MEFT0346.BIN': 'fc86ad1def5237e90b0bf8d709e34676a602be73',
    'MEFT0349.BIN': 'b7096539326b7577c20a30e485242c734e7d9511',
    'MEFT0351.BIN': '871a05c329edeb18cacff78186bbb82f97f0be20',
    'MEFT0361.BIN': 'df25b37b2fa18538caaf155d734d260854bdaa5f',
    'MEFT0363.BIN': '9a828203f25811cae297931a968023cf4d7d440a',
    'MEFT0364.BIN': 'e4edfe4e3012d8871c7a309312b0dc76a7ff8bc9',
    'MEFT0370.BIN': 'bb38984492ffc4edf64bf252e7c83ee89b8a779c',
}
# the few that differ on one release: {release id: {name: SHA-1}} (the USA disc's Raidenmon sprite pack)
DW3_EFFECT_RELEASE_FILES = {
    'dw3-us': {'E438RIDN.BIN': '7f1e953081765bb94139cd3c08852d1c32a333fd'},
}
DW3_EFFECT_DIRS = {'dw2003': 'AAA/DAT/FIGHT/EFFECT', 'dw3-us': 'AAA/DAT/EFFECT', 'dw3-jp': 'AAA/DAT/FIGHT/EFFECT'}
# the shared packs' textures (F000COMn.BIN) sit one folder up, but on the USA disc
DW3_TEXTURE_DIRS = {'dw2003': 'AAA/DAT/FIGHT', 'dw3-us': 'AAA/DAT/EFFECT', 'dw3-jp': 'AAA/DAT/FIGHT'}


def release_files():
    """{disc or release id: {path on the disc: SHA-1}} of the files the import converters read, so the web page can
    check an image whose whole-image checksum cannot match redump (a 2048-byte .iso, a PBP, another rip) by the
    files that matter. From content/imports/releases/*.json (tools/dw2release.py, dw3release.py):
    dw3-*: 'recipes' {model code: PAL SHA-1} and, for a release with other files, 'own' {code: its SHA-1}; dw2-*: 'recipes' {code: {path under AAA/4.AAA/MODEL: SHA-1}}, equal to the USA files.
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
            own = j.get('own', {})
            out[f'dw3-{rel}'] = {f'{own_dir}/{c}.BIN': own.get(c, h) for c, h in sorted(j['recipes'].items())}
            for rid in ('dw2003', f'dw3-{rel}'):
                files = dict(DW3_EFFECT_FILES, **{n: h for n, h in DW3_EFFECT_RELEASE_FILES.get(rid, {}).items()
                                                   if n in DW3_EFFECT_FILES})
                out[rid].update({f'{(DW3_TEXTURE_DIRS if n.startswith("F000COM") else DW3_EFFECT_DIRS)[rid]}/{n}': h
                                 for n, h in sorted(files.items())})
        elif game == 'dw2':
            files = {f'AAA/4.AAA/MODEL/{f}': h for c in sorted(j['recipes']) for f, h in sorted(j['recipes'][c].items())}
            files.update(DW2_EFFECT_FILES)
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
        'variants': [dict(d, instead=instead(d)) if not d.get('supported', True) else d
                     for d in SOURCE_VARIANTS + DW1_RELEASES],
        'files': release_files(),
        'other': [dict(pick(d, 'id', 'title', 'serial', 'size', 'sha1'), boot=d['serial'].replace('-', '_')[:8] + '.'
                       + d['serial'][-2:]) for d in DISCS if d['id'] != 'us']
                 # versions with no registered dump: recognised by their boot file only
                 + [dict(pick(d, 'id', 'title', 'serial', 'boot'), supported=False, instead=instead(d))
                    for d in NO_DUMP],
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
    rows += ['', 'What the patchers say for a release they recognise but cannot use (`unsupported()`; the reasons are in',
             '[patcher.md](../patcher.md)):', '']
    rows += [f"- {d['title']} ({d['serial']}): {notice(d)}" for d in unsupported()]
    rows.append('')
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
