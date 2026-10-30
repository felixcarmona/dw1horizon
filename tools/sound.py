#!/usr/bin/env python3
"""Music, sound effects and Digimon voices of Digimon World (USA): the .VHB banks.

Usage:
  sound.py list [FILE ...]                 every bank (chunk) of every .VHB: programs, tones,
                                           samples, sequences, and who uses it (font/track names,
                                           Digimon voices, map sound regions, screens)
  sound.py info FILE CHUNK                 one chunk in detail (every program, tone and sample)
  sound.py export FILE [CHUNK ...] -o DIR  samples to WAV (44.1 kHz = the pitch at the tone's root
                                           note, 'smpl' chunk with root and loop) and, for FAALL,
                                           every track to MIDI; plus a .json of each VAB header
  sound.py render FONT TRACK -o OUT.wav [--secs S] [--vhb FAALL.VHB]
                                           plays a FAALL track offline (approximate SPU: pitch,
                                           ADSR, loops, volume, pan; no reverb) to listen to it
  sound.py import-midi FONT TRACK IN.mid -o OUT.VHB [--vhb FAALL.VHB] [--loop] [--prog-map A=B,...]
                                           replaces one track of a music font with a MIDI file
  sound.py import-wav FILE CHUNK IN.wav -o OUT.VHB (--vag N | --program P [--keys LO-HI])
                    [--root NOTE] [--rate HZ] [--loop START[:END]] [--volume V]
                                           encodes a WAV to SPU ADPCM and replaces sample N (the
                                           tones that use it get the new root/loop), or adds it
                                           as a new tone of program P (a new program if P = ps)
  sound.py index FILE [-o OUT.VHB]         the chunk index of FAALL/VBALL/VLALL/ESALL; with -o writes the
                                           file in the indexed layout (index sector + packed chunks, any
                                           size and count) that the soundlimits executable reads
  sound.py add-font IN.mid [IN2.mid ...] --instruments FONT -o OUT.VHB [--vhb FAALL.VHB] [--loop]
                                           a NEW music font (34, 35...): the instruments of FONT and the
                                           MIDI files as tracks 0, 1...; indexed layout (soundlimits exe)
  sound.py set-bgm SCREEN FONT -o OUT.SCN [--maphead MAPHEAD.SCN]
                                           makes a screen play FONT (its MAPHEAD SET_BGM byte)
  sound.py spu-budget [--vhb-dir DIR] [--screens 0,13] [--partner TYPE] [--maphead MAPHEAD.SCN]
                                           SPU allocation of the soundlimits executable simulated on every
                                           screen, arriving from every other one (music and map region, a
                                           battle, the way back), with the .VHB files (and MAPHEAD.SCN) in
                                           DIR (default: the original ones)
  sound.py check FILE                      every limit the game imposes (header buffers, SPU slots,
                                           chunk strides, SEQ_BUFFER), for a modified .VHB
  sound.py roundtrip                       byte-exact: every .VHB parsed and rebuilt, every SEQ
                                           exported to MIDI and imported back (selftest)

FILE is a path or one of SS SL SB FAALL ESALL VBALL VLALL (from extracted/SOUND/VHB/).
CHUNK is the index inside the file (FAALL: font − 1; VBALL/VLALL: the sound id of
DIGIMON_VBALL/VLALL_SOUND_ID; ESALL: the MAP_SOUND_PARA region). FONT is 1..33 (0x21) on the original disc, 1..254 with the soundlimits executable.

Format reference and limits: docs/mods/sound.md.
"""
import argparse, json, math, os, struct, sys, wave

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
VHBDIR = os.path.join(ROOT, 'extracted/SOUND/VHB')
EXE = os.path.join(ROOT, 'extracted/SLUS_010.32')
SECTOR = 0x800
SPU_RATE = 44100

# Per file: how the chunks are laid out and what the game allows (sound.c, sound_async.c).
#   stride: fixed chunk size in sectors (chunk = id * stride), 'sector': each chunk starts at the
#   next sector (ESALL, with MAP_SOUND_PARA), None: one chunk, file not padded.
#   vhmax: RAM buffer the VAB header is memcpy'd into (VHB_HEADER_*), unchecked.
#   bank / slot: SsVabOpenHeadSticky address (VHB_SOUNDBUFFER_START) and the room up to the next one.
FILES = {
    'SS':    dict(stride=None, hdr=3, vhmax=0x1000, bank=0, spu=0x01010, slot=0x0E800 - 0x01010),
    'SL':    dict(stride=None, hdr=3, vhmax=0x1000, bank=1, spu=0x0E800, slot=0x1B800 - 0x0E800),
    'FAALL': dict(stride=39,   hdr=4, vhmax=0x2000, bank=2, spu=0x1B800, slot=0x2A000 - 0x1B800),
    'VLALL': dict(stride=15,   hdr=3, vhmax=0x1000, bank=3, spu=0x2A000, slot=0x31800 - 0x2A000),
    'VBALL': dict(stride=7,    hdr=3, vhmax=0x1000, bank=4, spu=0x31800, slot=0x2800),
    'ESALL': dict(stride='sector', hdr=3, vhmax=0x1800, bank=8, spu=0x3B800, slot=0x7B7C0 - 0x3B800),
    'SB':    dict(stride=None, hdr=3, vhmax=0x1800, bank=8, spu=0x3B800, slot=0x7B7C0 - 0x3B800),
}
SEQ_BUFFER_MAX = 0x5800        # SEQ_BUFFER (sound.c), memcpy without a check
# A chunk (a single-chunk file: all of it) is read in whole sectors into GENERAL_BUFFER (0x80010000) before its upload:
# it must end at or below the save extensions (SAVE_EXT_ADDR), which a game-clear save writes while the ending's bank
# loads. SOUND_STAGING_MAX in include/dw/memmap.h (patch 0096; tools/build-full.sh passes the executable's value in the
# environment); the original's largest, an ESALL chunk, is exactly 124 sectors.
STAGING_MAX = int(os.environ.get('SOUND_STAGING_MAX', '0x3E000'), 0)
SEQ_BUFFER_MOD = 0x8000        # soundlimits executable: SEQ_BUFFER_SIZE (include/dw/memmap.h), checked
VAB_MAX_PROGRAMS = 128
TONES_PER_PROGRAM = 16

# Executable tables (original SLUS_010.32: file offset = RAM - 0x80090000)
TBL = dict(VLALL=(0x80127EFC, 66), VBALL=(0x80127F40, 180), MAP_SOUND_PARA=(0x80127FF4, 22 * 4),
           ENEMY_MUSIC=(0x8012BAE4, 48))

# Jukebox (MAIN_D_801303B8) font/track pairs and BGM_TRACK_NAMES (script_common.c), US names.
JUKEBOX = [(1, 0), (1, 1), (2, 0), (2, 1), (3, 0), (3, 1), (4, 0), (4, 1), (5, 0), (6, 0), (6, 1), (7, 0),
           (8, 0), (9, 0), (10, 0), (10, 1), (11, 0), (11, 1), (11, 2), (12, 0), (12, 1), (13, 0), (13, 1),
           (14, 0), (14, 1), (15, 0), (15, 1), (15, 2), (16, 0), (17, 0), (18, 0), (19, 0), (19, 1), (20, 0),
           (20, 1), (21, 0), (21, 1), (22, 0), (22, 1), (23, 0), (24, 0), (24, 1), (25, 0), (25, 1), (26, 0),
           (27, 0), (27, 1), (28, 0), (28, 1), (29, 0), (29, 1), (29, 2), (30, 0), (30, 1), (30, 2), (30, 3),
           (30, 4), (31, 2), (32, 2), (33, 0), (33, 1), (33, 2), (33, 3)]
TRACK_NAMES = """Native Forest|Native Forest (night)|Tropical|Tropical (night)|Mt. Panorama|Mt. Panorama (night)|
Drill Tunnel|Ogre Fortress|Overdell Cemetery|Canyon|Ogremon no. 2|Everything Shop|Ogremon no. 3|Lava Cave|
Dark Aristocrat's Mansion|Underground Lab|Gear Savanna|Gear Savanna (night)|Leomon|Amida Forest|
Amida Forest (night)|Speedy Time Zone|Speedy Time Zone (night)|Glacial Time Zone|Glacial Time Zone (night)|
Freezeland|Freezeland (night)|Igloo|Curling|Sanctuary|Sanctuary Below|Gecko Swamp|Gecko Swamp (night)|
Misty Trees|Misty Trees (night)|WaruMonzaemon|Toy Town|Factorial|Factorial (night)|Sewer|Trash Mountain|
Trash Mountain (night)|Beatland|Beatland (night)|Secret Beach Cave|Mt. Infinity|Last Room|File City|
File City (night)|Tournament Opening|Tournament Progress|Tournament Championship|Partner's Entrance|
Opponent's Entrance|Arena Battle no. 1|Partner's Win|Partner's Loss|Arena Battle no. 2|Arena Battle no. 3|
Event Battle|Normal Battle|Normal Battle no. 2|Last Battle""".replace('\n', '').split('|')
TRACK_NAME = {ft: n for ft, n in zip(JUKEBOX, TRACK_NAMES)}
TRACK_NAME[(1, 0)] = 'Non Bewildering Forest'; TRACK_NAME[(1, 1)] = 'Non Bewildering Forest (night)'


class SoundError(Exception):
    pass


# ---------------------------------------------------------------------------------------------
# VAB: header (VH) + body (VB)
#   VabHdr 32 B · ProgAtr[128] 16 B · VagAtr[ps][16] 32 B · u16 vagSize[256] (bytes / 8) · body
VABHDR = struct.Struct('<4sIIIHHHHBBBBI')        # form ver id fsize res0 ps ts vs mvol pan attr1 attr2 res1
PROGATR = struct.Struct('<BBBBBBHII')            # tones mvol prior mode mpan res0 attr res1 res2
VAGATR = struct.Struct('<BBBBBbBBBBBBBBBBHHhh4h')  # prior mode vol pan center shift min max vibW vibT porW porT
#                                                  pbmin pbmax res1 res2 adsr1 adsr2 prog vag res[4]
PROG_F = 'tones mvol prior mode mpan res0 attr res1 res2'.split()
TONE_F = ('prior mode vol pan center shift min max vibW vibT porW porT pbmin pbmax res1 res2 '
          'adsr1 adsr2 prog vag r0 r1 r2 r3').split()
HDR_F = 'form ver id fsize res0 ps ts vs mvol pan attr1 attr2 res1'.split()


def vh_size(ps):
    return VABHDR.size + PROGATR.size * VAB_MAX_PROGRAMS + VAGATR.size * TONES_PER_PROGRAM * ps + 512


class Vab:
    def __init__(self, vh, vb):
        h = VABHDR.unpack_from(vh, 0)
        if h[0] != b'pBAV':
            raise SoundError('not a VAB header (pBAV)')
        self.hdr = dict(zip(HDR_F, h))
        ps = self.hdr['ps']
        if len(vh) != vh_size(ps):
            raise SoundError(f'VH size {len(vh):#x} != {vh_size(ps):#x} for {ps} programs')
        p = VABHDR.size
        self.progs = [dict(zip(PROG_F, PROGATR.unpack_from(vh, p + i * PROGATR.size))) for i in range(VAB_MAX_PROGRAMS)]
        p += PROGATR.size * VAB_MAX_PROGRAMS
        self.tones = [[dict(zip(TONE_F, VAGATR.unpack_from(vh, p + (k * 16 + i) * VAGATR.size)))
                       for i in range(TONES_PER_PROGRAM)] for k in range(ps)]
        p += VAGATR.size * TONES_PER_PROGRAM * ps
        self.sizes = list(struct.unpack_from('<256H', vh, p))
        self.vags = []; q = 0
        for i in range(1, self.hdr['vs'] + 1):
            n = self.sizes[i] * 8
            self.vags.append(vb[q:q + n]); q += n
        # 13 VBALL chunks list a 4th sample of size 0 and its size at entry 20 (left over by the
        # original tools): the bytes are in the body after sample 3, so sample 4 (address = sum of
        # the previous sizes) plays them. Kept as 'extra' so the body rebuilds unchanged.
        self.extra = vb[q:]
        if q + sum(self.sizes[self.hdr['vs'] + 1:]) * 8 != len(vb) or self.sizes[0]:
            raise SoundError(f'body {len(vb):#x} bytes does not match the VAG size table')

    def vh(self):
        h = dict(self.hdr)
        if getattr(self, 'touched', False):     # edited: recompute the counts and the total size
            h.update(ps=len(self.tones), vs=len(self.vags), ts=sum(1 for b in self.tones for t in b if t['vag']),
                     fsize=vh_size(len(self.tones)) + len(self.vb()))
        out = bytearray(VABHDR.pack(*[h[k] for k in HDR_F]))
        for pr in self.progs:
            out += PROGATR.pack(*[pr[k] for k in PROG_F])
        for blk in self.tones:
            for t in blk:
                out += VAGATR.pack(*[t[k] for k in TONE_F])
        sizes = list(self.sizes)
        if getattr(self, 'touched', False):
            n = len(self.vags)
            if any(sizes[self.hdr['vs'] + 1:n + 1]):
                raise SoundError('the VAG size table has stray entries where the new samples go')
            sizes[1:n + 1] = [len(v) // 8 for v in self.vags]
        out += struct.pack('<256H', *sizes)
        return bytes(out)

    def vb(self):
        return b''.join(self.vags) + self.extra

    def program_block(self, prog):
        """Index of the VagAtr block of a program. libsnd numbers the blocks in the order of the
        non-empty programs; every bank of this game has programs 0..ps-1 contiguous, which is
        also what startSound (tones + prog*16) assumes."""
        k = [i for i, pr in enumerate(self.progs) if pr['tones']]
        return k.index(prog) if prog in k else None

    def tones_of(self, prog):
        b = self.program_block(prog)
        return [] if b is None else [t for t in self.tones[b] if t['vag']]


# ---------------------------------------------------------------------------------------------
# .VHB container
class Chunk:
    """One VHB chunk: u32 header (vh, vb, [seq,] end) + VH + VB [+ SEQ block]."""

    def __init__(self, data, nhdr):
        w = struct.unpack_from(f'<{nhdr}I', data, 0)
        self.nhdr = nhdr
        if w[0] != 4 * nhdr:
            raise SoundError(f'chunk header: vh offset {w[0]:#x}, expected {4 * nhdr:#x}')
        vb_end = w[2]
        self.vab = Vab(data[w[0]:w[1]], data[w[1]:vb_end])
        self.seqs = None
        if nhdr == 4:
            if w[2] != w[1] + len(self.vab.vb()):
                raise SoundError('SEQ block does not follow the body')
            self.seqs = split_seq_block(data[w[2]:w[3]])
        self.size = w[-1]

    def build(self):
        vh = self.vab.vh(); vb = self.vab.vb()
        hl = 4 * self.nhdr
        w = [hl, hl + len(vh), hl + len(vh) + len(vb)]
        body = vh + vb
        if self.nhdr == 4:
            sb = join_seq_block(self.seqs)
            w.append(w[2] + len(sb)); body += sb
        return struct.pack(f'<{self.nhdr}I', *w) + body

    def seq_block(self):
        return join_seq_block(self.seqs) if self.seqs is not None else b''


def split_seq_block(b):
    """u32 offsets[n] (n = offsets[0] / 4) then n SEQs (each padded to 4 bytes)."""
    n = struct.unpack_from('<I', b, 0)[0] // 4
    offs = list(struct.unpack_from(f'<{n}I', b, 0)) + [len(b)]
    return [b[offs[i]:offs[i + 1]] for i in range(n)]


def join_seq_block(seqs):
    offs = []; p = 4 * len(seqs)
    for s in seqs:
        offs.append(p); p += len(s)
    return struct.pack(f'<{len(seqs)}I', *offs) + b''.join(seqs)


def file_kind(path):
    """The kind comes from the file name: FAALL.VHB, FAALL-mod.VHB, build/x.FAALL.vhb..."""
    import re
    toks = re.split(r'[^A-Z0-9]+', os.path.basename(path).upper())
    k = next((t for t in toks if t in FILES), None)
    if k is None:
        raise SoundError(f'{path}: unknown sound file (the name must contain one of {", ".join(FILES)})')
    return k


def resolve(name):
    if os.path.exists(name):
        return name
    p = os.path.join(VHBDIR, name.upper() + ('' if name.upper().endswith('.VHB') else '.VHB'))
    if os.path.exists(p):
        return p
    raise SoundError(f'{name}: no such file')


INDEX_MAGIC = b'SIDX'
INDEXED = ('FAALL', 'VBALL', 'VLALL', 'ESALL')   # files the soundlimits executable reads through an index


class VhbFile:
    """A .VHB file. Two layouts:
    - original: chunks at fixed strides (FAALL 39, VBALL 7, VLALL 15 sectors) or, in ESALL, each at
      the next sector (MAP_SOUND_PARA); what the original executable reads;
    - indexed (soundlimits executable, docs/mods/sound.md § 8): an index sector first
      ("SIDX", u16 count, u16 index sectors, count x {u16 sector, u16 sectors}) and the chunks packed
      at sector boundaries, so a chunk can have any size and the file any number of chunks."""

    def __init__(self, path):
        self.path = path; self.kind = file_kind(path); cfg = FILES[self.kind]
        data = open(path, 'rb').read(); self.orig_size = len(data)
        self.chunks = []; self.slots = []          # slot = bytes reserved for the chunk in the file
        self.indexed = data[:4] == INDEX_MAGIC
        if self.indexed:
            n, nsec = struct.unpack_from('<HH', data, 4)
            ent = [struct.unpack_from('<HH', data, 8 + 4 * i) for i in range(n)]
            for i, (sec, cnt) in enumerate(ent):
                c = Chunk(data[sec * SECTOR:(sec + cnt) * SECTOR], cfg['hdr'])
                if -(-c.size // SECTOR) != cnt:
                    raise SoundError(f'{self.kind} chunk {i}: index says {cnt} sectors, chunk needs {-(-c.size // SECTOR)}')
                self.chunks.append(c); self.slots.append(cnt * SECTOR)
            return
        p = 0
        while p < len(data):
            c = Chunk(data[p:], cfg['hdr'])
            if isinstance(cfg['stride'], int):
                slot = cfg['stride'] * SECTOR
            elif cfg['stride'] == 'sector':
                slot = (c.size + SECTOR - 1) // SECTOR * SECTOR
            else:
                slot = c.size
            pad = data[p + c.size:p + slot]
            if pad.strip(b'\0'):
                raise SoundError(f'{self.kind} chunk {len(self.chunks)}: non-zero padding')
            self.chunks.append(c); self.slots.append(slot); p += slot
        if p != len(data):
            raise SoundError(f'{path}: {len(data) - p} bytes after the last chunk')

    def to_indexed(self):
        if self.kind not in INDEXED:
            raise SoundError(f'{self.kind}.VHB is a single chunk; only {", ".join(INDEXED)} have an index')
        self.indexed = True

    def index(self):
        """[(sector, sectors)] of every chunk in the indexed layout."""
        nsec = -(-(8 + 4 * len(self.chunks)) // SECTOR); out = []; p = nsec
        for c in self.chunks:
            n = -(-len(c.build()) // SECTOR); out.append((p, n)); p += n
        return nsec, out

    def build(self):
        cfg = FILES[self.kind]; out = bytearray()
        if self.indexed:
            nsec, ent = self.index()
            if len(ent) > 0xFFFF or ent and ent[-1][0] + ent[-1][1] > 0xFFFF:
                raise SoundError(f'{self.kind}: the index holds u16 sectors (128 MB) and counts')
            out += INDEX_MAGIC + struct.pack('<HH', len(ent), nsec)
            for e in ent:
                out += struct.pack('<HH', *e)
            out += bytes(nsec * SECTOR - len(out))
            for c in self.chunks:
                b = c.build(); out += b + bytes(-len(b) % SECTOR)
            return bytes(out)
        for i, c in enumerate(self.chunks):
            b = c.build()
            if isinstance(cfg['stride'], int):
                slot = cfg['stride'] * SECTOR
                if len(b) > slot:
                    raise SoundError(f'{self.kind} chunk {i}: {len(b):#x} bytes > fixed stride {slot:#x} '
                                     f'({cfg["stride"]} sectors); the original executable reads chunk·{cfg["stride"]}; '
                                     f'convert the file with `sound.py index {self.kind} -o OUT` (soundlimits executable)')
            elif cfg['stride'] == 'sector':
                slot = (len(b) + SECTOR - 1) // SECTOR * SECTOR
            else:
                slot = len(b)
            out += b + bytes(slot - len(b))
        return bytes(out)


# ---------------------------------------------------------------------------------------------
# Usage tables from the executable: the USA one of extracted/ (a developer's listing: `list`, and `check` of an ESALL
# in the original, non-indexed layout). rule: the build's commands (check of an indexed file, spu-budget) do not open it;
# the voices of a species are in its file (content/species: voice, partner.voice).
def exe_tables():
    try:
        d = open(EXE, 'rb').read()
    except OSError:
        return None
    o = lambda a: a - 0x80090000
    t = {k: d[o(a):o(a) + n] for k, (a, n) in TBL.items()}
    t['MAP_SOUND_PARA'] = [struct.unpack_from('<HH', t['MAP_SOUND_PARA'], 4 * i) for i in range(22)]
    return t


def csv_rows(name):
    import csv
    p = os.path.join(ROOT, 'docs/data', name)
    return list(csv.DictReader(open(p))) if os.path.exists(p) else []


def digimon_names():
    import species                                  # content/species
    return {t: r['name'] for t, r in species.all_rows().items() if t < species.NUM_ORIGINAL}


def bgm_by_screen(maphead=None):
    """MAPHEAD.SCN: the section of each screen does SET_PSTAT p245 (override mode) and SET_BGM font. maphead: the
    build's (--maphead); without one the USA disc's (extracted/SCN/MAPHEAD.SCN, a developer's listing). A missing or
    unreadable file is an error, not an empty answer (spu-budget would check nothing)."""
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    from dws import bytecode as bytecode
    path = maphead or os.path.join(ROOT, 'extracted/SCN/MAPHEAD.SCN')
    if not os.path.exists(path):
        raise SoundError(f'no {path}: pass the MAPHEAD.SCN of the build (--maphead)')
    mh = open(path, 'rb').read()
    _, secs, _, _, _ = bytecode.sweep(mh)
    out = {}
    for sid, off in secs:
        if sid > 254:
            continue
        p = off; mode = None
        for _ in range(200):
            n, _t = bytecode.instr_length(mh, p)
            if n is None or mh[p] in (0xFE, 0xFF):
                break
            if mh[p] == 0x1E and mh[p + 2] == 245:
                mode = mh[p + 3]
            if mh[p] == 0x5D:
                out.setdefault(sid, []).append((mh[p + 1], mode))
            p += n
    return out


def music_override(font, mode):
    """handleMusicOverride (script_interp.c): PSTAT_245 → (font, track); track None = day/night."""
    fixed = {2: (6, 2), 3: (0xB, 2), 4: (0xF, 2), 5: (0x15, 0), 6: (0x15, 1), 7: (0x1A, 0), 8: (0x1A, 1),
             9: (0x1B, 0), 10: (0x1B, 1)}
    if mode in fixed:
        return fixed[mode]
    return (font, 0 if mode == 1 else None)


def usage(kind):
    """Who loads each chunk: {chunk: [text]}."""
    t = exe_tables(); names = digimon_names(); out = {}
    add = lambda i, s: out.setdefault(i, []).append(s)
    if kind == 'FAALL':
        for (f, tr), n in TRACK_NAME.items():
            add(f - 1, f'track {tr}: {n}')
        scr = bgm_by_screen(); maps = {int(r['id']): r['map_name'] for r in csv_rows('map_files.csv')}
        per = {}
        for sid, lst in scr.items():
            for font, mode in lst:
                if font == 0xFF:
                    continue
                f, tr = music_override(font, mode)
                per.setdefault(f - 1, []).append(f'{sid} {maps.get(sid, "")}'.strip())
        for i, l in per.items():
            add(i, f'screens ({len(l)}): ' + ', '.join(l[:6]) + (' …' if len(l) > 6 else ''))
        add(0x20, 'battles: track 3 vs Machinedramon, 0 scripted, ENEMY_MUSIC_MAPPING (1/2) otherwise')
    elif t and kind in ('VBALL', 'VLALL'):
        per = {}
        for typ, sid in enumerate(t[kind]):
            per.setdefault(sid, []).append(names.get(typ, f'#{typ}'))
        for sid, l in per.items():
            add(sid, ', '.join(dict.fromkeys(l)))
        if kind == 'VLALL':
            add(15, '(default for types outside 1..65)')
    elif t and kind == 'ESALL':
        para = t['MAP_SOUND_PARA']; maps = csv_rows('map_files.csv')
        for i, (sec, cnt) in enumerate(para):
            l = [r['map_name'] for r in maps if (int(r['flags']) & 0x1F) == i]
            add(i, f'MAP_SOUND_PARA[{i}] = sector {sec // 2:#x}, {cnt // 2} sectors; {len(l)} screens: '
                   + ', '.join(dict.fromkeys(l)))
    elif kind == 'SS':
        add(0, 'bank 0, loaded at boot: menus, text boxes, feeding (playSound(0, n))')
    elif kind == 'SL':
        add(0, 'bank 1, loaded at boot')
    elif kind == 'SB':
        add(0, 'bank 8 in battles (loadSB), replaces the map ESALL region')
    return out


# ---------------------------------------------------------------------------------------------
# SPU ADPCM
FILTERS = [(0, 0), (60, 0), (115, -52), (98, -55), (122, -60)]


def adpcm_decode(vag, with_loop=False):
    out = []; s1 = s2 = 0; loop = None; end = None
    for blk in range(len(vag) // 16):
        b = vag[blk * 16:blk * 16 + 16]
        shift = b[0] & 0xF; f = (b[0] >> 4) & 0x7; flags = b[1]
        if shift > 12:
            shift = 9          # what the SPU does with 13..15
        f0, f1 = FILTERS[f] if f < 5 else (0, 0)
        if flags & 4 and loop is None and blk > 0 and flags & 2:
            loop = len(out)
        for i in range(28):
            nib = (b[2 + i // 2] >> (4 * (i & 1))) & 0xF
            v = ((nib << 12) & 0xFFFF)
            if v & 0x8000:
                v -= 0x10000
            v = (v >> shift) + ((s1 * f0 + s2 * f1 + 32) >> 6)
            v = max(-32768, min(32767, v))
            out.append(v); s2 = s1; s1 = v
        if flags & 1:
            end = len(out)
            if not (flags & 2):
                break       # one-shot: the voice stops here
    return (out, loop, end) if with_loop else out


def adpcm_encode(samples, loop_start=None):
    """PCM s16 list → SPU ADPCM in the layout of the game's VAGs:
    a zero block, data blocks (first one flag 4 for one-shots / 2 for loops, loop start 6, last
    3 for loops / 1 for one-shots) and, for one-shots, a final silent block with flag 7."""
    n = (len(samples) + 27) // 28 * 28
    if loop_start is not None:
        # move the loop start to a block boundary
        loop_start = (loop_start // 28) * 28
    pcm = list(samples) + [0] * (n - len(samples))
    out = bytearray(16)
    s1 = s2 = 0
    nblocks = n // 28
    for bi in range(nblocks):
        blk = pcm[bi * 28:bi * 28 + 28]
        best = None
        for fi, (f0, f1) in enumerate(FILTERS):
            # ideal residual with the true signal to choose the shift
            p1, p2 = s1, s2; mx = 0
            for x in blk:
                r = x - ((p1 * f0 + p2 * f1 + 32) >> 6); mx = max(mx, abs(r)); p2 = p1; p1 = x
            sh0 = 12
            while sh0 > 0 and (mx >> (12 - sh0)) > 7:
                sh0 -= 1
            for sh in {max(0, sh0 - 1), sh0, min(12, sh0 + 1)}:
                p1, p2 = s1, s2; err = 0; nibs = []
                for x in blk:
                    pred = (p1 * f0 + p2 * f1 + 32) >> 6
                    r = x - pred
                    q = int(round(r * (1 << sh) / 4096.0))     # decoder: (nibble << 12) >> shift
                    q = max(-8, min(7, q))
                    v = (((q << 12) & 0xFFFF) - (0x10000 if q < 0 else 0)) >> sh
                    v = max(-32768, min(32767, v + pred))
                    err += (x - v) ** 2; nibs.append(q & 0xF); p2 = p1; p1 = v
                if best is None or err < best[0]:
                    best = (err, fi, sh, nibs, p1, p2)
                if err == 0:
                    break
        _, fi, sh, nibs, s1, s2 = best
        if loop_start is None:
            flags = 4 if bi == 0 else 0
            if bi == nblocks - 1:
                flags |= 1
        else:
            flags = 2
            if bi * 28 == loop_start:
                flags = 6
            if bi == nblocks - 1:
                flags = 3 if bi * 28 != loop_start else 7
        out += bytes([(fi << 4) | sh, flags]) + bytes(nibs[2 * i] | (nibs[2 * i + 1] << 4) for i in range(14))
    if loop_start is None:
        out += bytes([0, 7]) + b'\x77' * 14
    return bytes(out)


# ---------------------------------------------------------------------------------------------
# WAV
def write_wav(path, pcm, rate=SPU_RATE, root=60, fine=0, loop=None):
    data = struct.pack(f'<{len(pcm)}h', *pcm)
    fmt = struct.pack('<HHIIHH', 1, 1, rate, rate * 2, 2, 16)
    period = int(1e9 / rate)
    smpl = struct.pack('<IIIIIIIII', 0, 0, period, root, fine & 0xFFFFFFFF, 0, 0, 1 if loop else 0, 0)
    if loop:
        smpl += struct.pack('<IIIIII', 0, 0, loop[0], max(loop[0], loop[1] - 1), 0, 0)
    chunks = b'fmt ' + struct.pack('<I', len(fmt)) + fmt + b'smpl' + struct.pack('<I', len(smpl)) + smpl
    chunks += b'data' + struct.pack('<I', len(data)) + data
    open(path, 'wb').write(b'RIFF' + struct.pack('<I', 4 + len(chunks)) + b'WAVE' + chunks)


def read_wav(path):
    """→ (mono s16 list, rate, loop or None, root or None)"""
    d = open(path, 'rb').read()
    if d[:4] != b'RIFF' or d[8:12] != b'WAVE':
        raise SoundError(f'{path}: not a WAV file')
    p = 12; fmt = None; data = None; loop = None; root = None
    while p + 8 <= len(d):
        cid = d[p:p + 4]; n = struct.unpack_from('<I', d, p + 4)[0]; body = d[p + 8:p + 8 + n]
        if cid == b'fmt ':
            fmt = struct.unpack_from('<HHIIHH', body, 0)
        elif cid == b'data':
            data = body
        elif cid == b'smpl' and len(body) >= 36:
            root = struct.unpack_from('<I', body, 12)[0] + struct.unpack_from('<I', body, 16)[0] / 2 ** 32
            if struct.unpack_from('<I', body, 28)[0] and len(body) >= 60:
                s, e = struct.unpack_from('<II', body, 44)
                loop = (s, e + 1)
        p += 8 + n + (n & 1)
    if not fmt or data is None:
        raise SoundError(f'{path}: no fmt/data chunk')
    tag, ch, rate, _, align, bits = fmt
    if tag not in (1, 3, 0xFFFE):
        raise SoundError(f'{path}: unsupported WAV encoding {tag}')
    nfr = len(data) // align; pcm = []
    for i in range(nfr):
        acc = 0
        for c in range(ch):
            o = i * align + c * (bits // 8)
            if bits == 16:
                v = struct.unpack_from('<h', data, o)[0]
            elif bits == 8:
                v = (data[o] - 128) << 8
            elif bits == 24:
                v = int.from_bytes(data[o:o + 3], 'little', signed=True) >> 8
            elif bits == 32 and tag == 3:
                v = int(max(-1.0, min(1.0, struct.unpack_from('<f', data, o)[0])) * 32767)
            elif bits == 32:
                v = struct.unpack_from('<i', data, o)[0] >> 16
            else:
                raise SoundError(f'{path}: {bits}-bit samples not supported')
            acc += v
        pcm.append(int(acc / ch))
    return pcm, rate, loop, root


def resample(pcm, src, dst):
    if src == dst:
        return list(pcm)
    n = int(len(pcm) * dst / src); out = []
    for i in range(n):
        x = i * src / dst; j = int(x); f = x - j
        a = pcm[j] if j < len(pcm) else 0; b = pcm[j + 1] if j + 1 < len(pcm) else 0
        out.append(int(a + (b - a) * f))
    return out


# ---------------------------------------------------------------------------------------------
# SEQ (Sony sequence) <-> standard MIDI file
#   'pQES' · u32 version (BE, 1) · u16 resolution (BE, ticks per quarter) · u24 tempo (BE, µs per
#   quarter) · u8 u8 rhythm (always 01 04 here), then MIDI-like events: delta time (VLQ), status,
#   data, with running status. Differences from a MIDI track: meta events carry no length byte
#   (FF 51 t t t = tempo, FF 2F 00 = end), note-off is a note-on with velocity 0, loop points are
#   NRPN controllers (CC99 = 20 loop start + CC6 = count, CC99 = 30 loop end). Each SEQ in a FAALL
#   block is padded to 4 bytes with 0xCD (the filler of the original tools).
SEQ_HDR = 15
SEQ_PAD = 0xCD


def vlq(b, p):
    v = 0
    while True:
        c = b[p]; p += 1; v = (v << 7) | (c & 0x7F)
        if not c & 0x80:
            return v, p


def put_vlq(v):
    out = [v & 0x7F]; v >>= 7
    while v:
        out.append(0x80 | (v & 0x7F)); v >>= 7
    return bytes(reversed(out))


DLEN = {0x8: 2, 0x9: 2, 0xA: 2, 0xB: 2, 0xC: 1, 0xD: 1, 0xE: 2}
SEQ_META = {0x51: 3, 0x2F: 1}       # meta type → bytes that follow (no length byte in a SEQ)


def parse_events(b, p=0, seq=False):
    """Event stream → [(delta, status, data)], end offset. Meta events: status 0xFF,
    data = type byte + payload. seq=True: SEQ metas (no length); otherwise SMF."""
    ev = []; rs = None
    while p < len(b):
        start = p
        d, p = vlq(b, p)
        st = b[p]
        if st & 0x80:
            p += 1
            if st < 0xF0:
                rs = st
        else:
            if rs is None:
                raise SoundError(f'running status without a previous status at {start:#x}')
            st = rs
        if st == 0xFF:
            t = b[p]; p += 1
            if seq:
                if t not in SEQ_META:
                    raise SoundError(f'unknown SEQ meta event FF {t:02X} at {start:#x}')
                n = SEQ_META[t]
            else:
                n, p = vlq(b, p)
                rs = None          # SMF: meta events cancel running status
            data = bytes([t]) + b[p:p + n]; p += n
        elif st in (0xF0, 0xF7):
            n, p = vlq(b, p); data = b[p:p + n]; p += n
        else:
            n = DLEN[st >> 4]; data = b[p:p + n]; p += n
        ev.append((d, st, bytes(data)))
        if st == 0xFF and data[0] == 0x2F:
            return ev, p
    return ev, p


def encode_events(ev, seq=False):
    """[(delta, status, data)] → bytes, with running status (as the original SEQs: always,
    reset after a meta event)."""
    out = bytearray(); rs = None
    for d, st, data in ev:
        out += put_vlq(d)
        if st == 0xFF:
            out += bytes([0xFF, data[0]])
            if not seq:
                out += put_vlq(len(data) - 1)
            out += data[1:]; rs = None
        else:
            if st != rs:
                out.append(st); rs = st
            out += data
    return bytes(out)


class Seq:
    def __init__(self, raw):
        if raw[:4] != b'pQES':
            raise SoundError('not a SEQ (pQES)')
        self.version = struct.unpack_from('>I', raw, 4)[0]
        self.res = struct.unpack_from('>H', raw, 8)[0]
        self.tempo = int.from_bytes(raw[10:13], 'big')
        self.rhythm = raw[13:15]
        self.events, e = parse_events(raw, SEQ_HDR, seq=True)
        self.tail = raw[e:]

    @staticmethod
    def build(version, res, tempo, rhythm, events):
        raw = (b'pQES' + struct.pack('>IH', version, res) + tempo.to_bytes(3, 'big') + bytes(rhythm)
               + encode_events(events, seq=True))
        return raw + bytes([SEQ_PAD]) * (-len(raw) % 4)


def seq_to_midi(raw):
    """SEQ → format-0 MIDI file: header tempo and rhythm become the first two meta events."""
    s = Seq(raw)
    ev = [(0, 0xFF, b'\x51' + s.tempo.to_bytes(3, 'big')), (0, 0xFF, b'\x58' + s.rhythm + b'\x18\x08')]
    if s.version != 1:
        ev.append((0, 0xFF, b'\x7fSEQv' + struct.pack('>I', s.version)))
    # SEQ end 'FF 2F 00' → SMF 'FF 2F 00' (type, length 0)
    ev += [(d, st, b'\x2f' if st == 0xFF and data[0] == 0x2F else data) for d, st, data in s.events]
    trk = encode_events(ev)
    return b'MThd' + struct.pack('>IHHH', 6, 0, 1, s.res) + b'MTrk' + struct.pack('>I', len(trk)) + trk


def read_midi(d):
    if d[:4] != b'MThd':
        raise SoundError('not a MIDI file')
    hl, fmt, ntrk, div = struct.unpack_from('>IHHH', d, 4)
    if div & 0x8000:
        raise SoundError('SMPTE time division is not supported')
    p = 8 + hl; tracks = []
    while p + 8 <= len(d) and len(tracks) < ntrk:
        cid = d[p:p + 4]; n = struct.unpack_from('>I', d, p + 4)[0]
        if cid == b'MTrk':
            tracks.append(parse_events(d[p + 8:p + 8 + n])[0])
        p += 8 + n
    return fmt, div, tracks


SEQ_OK = {0x9, 0xB, 0xC, 0xE}          # what the game's sequences use (and libsnd plays)


def midi_to_seq(d, loop=False, prog_map=None):
    """Standard MIDI file (format 0 or 1) → SEQ. Tracks are merged in time order (stable),
    note-off becomes velocity 0, aftertouch/sysex/other metas are dropped; the first tempo
    at tick 0 goes to the header, later ones stay as FF 51. A file made by seq_to_midi comes
    back byte for byte."""
    fmt, div, tracks = read_midi(d)
    prog_map = prog_map or {}
    allev = []; eot = 0; version = 1; rhythm = b'\x01\x04'; tempo = None
    for ti, ev in enumerate(tracks):
        tick = 0
        for i, (dt, st, data) in enumerate(ev):
            tick += dt
            allev.append((tick, ti, i, st, data))
    allev.sort(key=lambda e: (e[0], e[1], e[2]))
    out = []; dropped = set()
    for tick, ti, i, st, data in allev:
        hi = st >> 4
        if st == 0xFF:
            t = data[0]
            if t == 0x2F:
                eot = max(eot, tick)
            elif t == 0x51:
                if tempo is None and tick == 0 and not out:
                    tempo = int.from_bytes(data[1:4], 'big')
                else:
                    out.append((tick, 0xFF, data[:4]))
            elif t == 0x58 and tick == 0 and not out:
                rhythm = data[1:3]
            elif t == 0x7F and data[1:5] == b'SEQv':
                version = struct.unpack('>I', data[5:9])[0]
            continue
        if hi == 0x8:
            st = 0x90 | (st & 0xF); data = bytes([data[0], 0])
        if hi == 0xC and data[0] in prog_map:
            data = bytes([prog_map[data[0]]])
        if (st >> 4) in SEQ_OK:
            out.append((tick, st, bytes(data)))
        else:
            dropped.add(f'{st:02X}')
    if dropped:
        print('note: dropped MIDI events the game does not play: ' + ' '.join(sorted(dropped)))
    if loop:
        first = next((t for t, st, dt in out if st >> 4 == 9 and dt[1]), 0)
        last = max([t for t, _, _ in out] + [eot])
        k = next(i for i, e in enumerate(out + [(1 << 62, 0, b'')]) if e[0] >= first and not (e[1] >> 4 in (0xB, 0xC, 0xE) and e[0] == first))
        out[k:k] = [(first, 0xB0, b'\x63\x14'), (first, 0xB0, b'\x06\x7f')]
        out.append((last, 0xB0, b'\x63\x1e'))
    ev = []; now = 0
    for tick, st, data in out:
        ev.append((tick - now, st, data)); now = tick
    ev.append((max(0, max(eot, now) - now), 0xFF, b'\x2f\x00'))
    if div > 0xFFFF:
        raise SoundError('resolution too large')
    return Seq.build(version, div, 500000 if tempo is None else tempo, rhythm, ev)


def seq_stats(raw):
    s = Seq(raw); progs = set(); chans = set(); notes = 0; tick = 0; poly = 0; on = {}; maxpoly = 0
    loop = []
    for d, st, data in s.events:
        tick += d
        if st >> 4 == 0xC:
            progs.add((st & 0xF, data[0]))
        if st >> 4 == 0x9:
            chans.add(st & 0xF)
            k = (st & 0xF, data[0])
            if data[1]:
                notes += 1; on[k] = on.get(k, 0) + 1
            elif on.get(k):
                on[k] -= 1
            maxpoly = max(maxpoly, sum(on.values()))
        if st >> 4 == 0xB and data[0] == 0x63:
            loop.append((data[1], tick))
    secs = tick / s.res * s.tempo / 1e6
    return dict(res=s.res, bpm=round(60e6 / s.tempo, 1), ticks=tick, secs=secs, notes=notes,
                channels=sorted(chans), programs=sorted(progs), poly=maxpoly, loop=loop)


# ---------------------------------------------------------------------------------------------
# Offline renderer (approximate SPU, for listening; no reverb, no voice limit)
def shift_semitones(shift):
    """libsnd SsPitchFromNote: (fine + shift) >> 3 (rounded toward zero) sixteenths of a semitone,
    ADDED to the note: a positive shift raises the pitch (the pitch table has 16 steps per semitone)."""
    return int(shift / 8) / 16.0


def tone_pitch(t):
    """The key at which a tone plays its sample at 44.1 kHz: center − shift/128 (libsnd adds the
    shift to the played note: calc = note − (center − 60) + shift/128)."""
    return t['center'] - shift_semitones(t['shift'])


def note_rate(t, note, bend=0.0):
    """libsnd: the sample plays at 44.1 kHz at key center − shift/128 (shift in 1/128 semitone,
    used in steps of 8)."""
    return SPU_RATE * 2 ** ((note + bend - tone_pitch(t)) / 12.0)


class Envelope:
    """SPU ADSR (adsr1/adsr2 of the tone), stepped at 44.1 kHz."""

    def __init__(self, a1, a2):
        self.a1, self.a2 = a1, a2; self.level = 0; self.phase = 'A'; self.wait = 0
        self.sl = ((a1 & 0xF) + 1) * 0x800

    def _params(self):
        a1, a2 = self.a1, self.a2
        if self.phase == 'A':
            return (a1 >> 10) & 0x1F, 7 - ((a1 >> 8) & 3), bool(a1 & 0x8000)
        if self.phase == 'D':
            return (a1 >> 4) & 0xF, -8, True
        if self.phase == 'S':
            dec = bool(a2 & 0x4000); st = (a2 >> 6) & 3
            return (a2 >> 8) & 0x1F, (-8 + st) if dec else (7 - st), bool(a2 & 0x8000)
        return a2 & 0x1F, -8, bool(a2 & 0x20)

    def tick(self, n):
        """Advance n SPU samples; returns the level (0..0x7FFF)."""
        for _ in range(n):
            if self.wait > 0:
                self.wait -= 1; continue
            shift, step, expo = self._params()
            inc = step << max(0, 11 - shift); cyc = 1 << max(0, shift - 11)
            if expo and step < 0:
                inc = inc * self.level >> 15
            if expo and step > 0 and self.level > 0x6000:
                cyc *= 4
            self.level = max(0, min(0x7FFF, self.level + inc)); self.wait = cyc - 1
            if self.phase == 'A' and self.level >= 0x7FFF:
                self.phase = 'D'
            elif self.phase == 'D' and self.level <= self.sl:
                self.phase = 'S'
        return self.level


def render(font, track, secs, vhb=None, rate=22050):
    f = VhbFile(resolve(vhb or 'FAALL')); c = f.chunks[font - 1]
    vab = c.vab; s = Seq(c.seqs[track])
    cache = {}

    def vag(i):
        if i not in cache:
            pcm, lp, end = adpcm_decode(vab.vags[i - 1], with_loop=True)
            cache[i] = ([x / 32768.0 for x in pcm], lp, end or len(pcm))
        return cache[i]

    # absolute ticks; repeat from the loop start (CC99 = 20) after the end (or CC99 = 30)
    events = []; tick = 0
    for d, st, data in s.events:
        tick += d; events.append((tick, st, data))
    loop_s = next((t for t, st, dt in events if st >> 4 == 0xB and dt[:2] == b'\x63\x14'), 0)
    loop_e = next((t for t, st, dt in events if st >> 4 == 0xB and dt[:2] == b'\x63\x1e'), events[-1][0])
    timeline = [e for e in events if e[0] <= loop_e]; base = loop_e
    body = [e for e in events if loop_s <= e[0] <= loop_e]
    while loop_e > loop_s and base / s.res * s.tempo / 1e6 < secs * 2:
        timeline += [(base + t - loop_s, st, dt) for t, st, dt in body]; base += loop_e - loop_s
    n = int(secs * rate); L = [0.0] * n; R = [0.0] * n
    ratio = SPU_RATE // rate if SPU_RATE % rate == 0 else 1
    chan = {ch: dict(prog=0, vol=127, pan=64, bend=0.0) for ch in range(16)}
    voices = []; tempo = s.tempo; now = 0.0; last = 0

    def run(v, until):
        a = v['pos']; b = min(n, int(until * rate))
        smp, lp, end = v['smp']; ph = v['ph']; step = v['rate'] / rate; env = v['env']
        for i in range(a, b):
            if v['off'] is not None and i >= v['off'] and env.phase != 'R':
                env.phase = 'R'; env.wait = 0
            lev = env.tick(ratio) / 32767.0
            if env.phase == 'R' and lev <= 0:
                v['dead'] = True; break
            j = int(ph)
            if j >= end:
                if lp is None:
                    v['dead'] = True; break
                ph = lp + (ph - end) % max(1, end - lp); j = int(ph)
            x = smp[j] * lev
            L[i] += x * v['gl']; R[i] += x * v['gr']
            ph += step
        v['ph'] = ph; v['pos'] = max(a, b)

    for t, st, data in timeline:
        now += (t - last) / s.res * tempo / 1e6; last = t
        if now >= secs:
            break
        hi = st >> 4; ch = st & 0xF; cs = chan[ch]
        for v in voices:
            run(v, now)
        voices = [v for v in voices if not v['dead']]
        if st == 0xFF:
            if data[0] == 0x51:
                tempo = int.from_bytes(data[1:4], 'big')
        elif hi == 0xC:
            cs['prog'] = data[0]
        elif hi == 0xB and data[0] == 7:
            cs['vol'] = data[1]
        elif hi == 0xB and data[0] == 10:
            cs['pan'] = data[1]
        elif hi == 0xE:
            cs['bend'] = ((data[1] << 7 | data[0]) - 8192) / 8192.0
        elif hi == 0x9 and data[1] == 0:
            for v in voices:
                if v['ch'] == ch and v['note'] == data[0] and v['off'] is None:
                    v['off'] = int(now * rate)
        elif hi == 0x9:
            note, vel = data
            pr = vab.progs[cs['prog']] if cs['prog'] < VAB_MAX_PROGRAMS else None
            for tn in vab.tones_of(cs['prog']):
                if tn['min'] <= note <= tn['max']:
                    rng = tn['pbmax'] if cs['bend'] >= 0 else tn['pbmin']
                    g = (vel / 127) * (cs['vol'] / 127) * (tn['vol'] / 127) * (pr['mvol'] / 127) * (0x50 / 127)
                    pan = max(0, min(127, tn['pan'] + cs['pan'] - 64 + (pr['mpan'] - 64)))
                    voices.append(dict(ch=ch, note=note, smp=vag(tn['vag']), rate=note_rate(tn, note, cs['bend'] * rng),
                                       gl=g * min(1, (127 - pan) / 64), gr=g * min(1, pan / 64), ph=0.0,
                                       pos=int(now * rate), off=None, env=Envelope(tn['adsr1'], tn['adsr2']), dead=False))
    for v in voices:
        run(v, secs)
    peak = max(1e-9, max(map(abs, L)), max(map(abs, R)))
    g = min(1.0, 0.9 / peak)
    return b''.join(struct.pack('<hh', int(l * g * 32767), int(r * g * 32767)) for l, r in zip(L, R)), rate


# ---------------------------------------------------------------------------------------------
# Limits
def check_chunk(kind, i, c, slot_bytes=None, indexed=False):
    cfg = FILES[kind]; errs = []; v = c.vab
    vh = len(v.vh()); body = len(v.vb())
    if vh > cfg['vhmax']:
        errs.append(f'VAB header {vh:#x} > {cfg["vhmax"]:#x} (VHB_HEADER buffer; ps ≤ '
                    f'{(cfg["vhmax"] - vh_size(0)) // 512})')
    if body > cfg['slot'] and not indexed:
        errs.append(f'body {body:#x} > SPU slot {cfg["slot"]:#x} of bank {cfg["bank"]} (from {cfg["spu"]:#x}; '
                    f'the soundlimits executable allocates SPU RAM per load: `sound.py index`, `spu-budget`)')
    elif body > SPU_REVERB_START - SPU_BANKS_START - 0xD130 - 0xCAE0:
        errs.append(f'body {body:#x} > what the SPU has besides SS and SL')
    if len(v.vags) > 254:
        errs.append(f'{len(v.vags)} samples > 254')
    for k, vg in enumerate(v.vags):
        if len(vg) % 16:
            errs.append(f'sample {k + 1}: size {len(vg)} not a multiple of 16')
        if len(vg) > 0x7FFF8:
            errs.append(f'sample {k + 1}: too large')
    for b, blk in enumerate(v.tones):
        for t in blk:
            if t['vag'] and t['vag'] > len(v.vags):
                errs.append(f'program block {b}: tone uses sample {t["vag"]} > vs {len(v.vags)}')
    if c.seqs is not None:
        sb = len(c.seq_block()); lim = SEQ_BUFFER_MOD if indexed else SEQ_BUFFER_MAX
        if sb > lim:
            errs.append(f'SEQ block {sb:#x} > SEQ_BUFFER {lim:#x}' + ('' if indexed else
                        f' (the soundlimits executable has {SEQ_BUFFER_MOD:#x}: `sound.py index`)'))
    staged = -(-len(c.build()) // SECTOR)
    if staged * SECTOR > STAGING_MAX:
        errs.append(f'chunk of {staged} sectors > the staging buffer\'s {STAGING_MAX // SECTOR} (GENERAL_BUFFER up to '
                    f'SAVE_EXT_ADDR, SOUND_STAGING_MAX in memmap.h)')
    if isinstance(cfg['stride'], int) and not indexed:
        cs = len(c.build())
        if cs > cfg['stride'] * SECTOR:
            errs.append(f'chunk {cs:#x} > stride {cfg["stride"]} sectors ({cfg["stride"] * SECTOR:#x})')
    return errs


def cmd_check(path):
    f = VhbFile(resolve(path)); bad = 0
    t = exe_tables() if f.kind == 'ESALL' and not f.indexed else None    # MAP_SOUND_PARA: the original layout only
    for i, c in enumerate(f.chunks):
        for e in check_chunk(f.kind, i, c, indexed=f.indexed):
            print(f'{f.kind} chunk {i}: {e}'); bad += 1
    if f.indexed:
        print(f'{f.kind}: indexed layout ({len(f.chunks)} chunks): needs the soundlimits executable')
    if f.kind == 'ESALL' and t and not f.indexed:
        p = 0
        for i, (c, slot) in enumerate(zip(f.chunks, f.slots)):
            sec, cnt = t['MAP_SOUND_PARA'][i] if i < 22 else (None, None)
            if sec is not None and (sec // 2 != p // SECTOR or cnt // 2 < (c.size + SECTOR - 1) // SECTOR):
                print(f'ESALL chunk {i}: at sector {p // SECTOR:#x}, {slot // SECTOR} sectors, but MAP_SOUND_PARA[{i}] '
                      f'says {sec // 2:#x}, {cnt // 2} (patch the table in the executable)'); bad += 1
            p += slot
    built = f.build()
    if len(built) != f.orig_size:
        print(f'{f.kind}: file size {len(built):#x} != {f.orig_size:#x}')
    orig = os.path.join(VHBDIR, f.kind + '.VHB')
    if os.path.exists(orig) and os.path.getsize(orig) != len(built):
        print(f'note: size differs from the original ({os.path.getsize(orig):#x}); build the disc with --relayout '
              f'(the game reads {f.kind}.VHB by its sector in FILE_OFFSET_TABLE)')
    print('ok' if not bad else f'{bad} problem(s)')
    return bad == 0


# ---------------------------------------------------------------------------------------------
# Commands
def cmd_list(files):
    for name in files or list(FILES):
        f = VhbFile(resolve(name)); u = usage(f.kind); cfg = FILES[f.kind]
        print(f'== {f.kind}.VHB  {f.orig_size:#x} bytes, {len(f.chunks)} chunks, bank {cfg["bank"]} '
              f'(SPU {cfg["spu"]:#x}, slot {cfg["slot"]:#x}), header buffer {cfg["vhmax"]:#x}'
              + (', indexed' if f.indexed else f', stride {cfg["stride"]} sectors' if isinstance(cfg['stride'], int) else ''))
        off = 0
        for i, (c, slot) in enumerate(zip(f.chunks, f.slots)):
            v = c.vab; body = len(v.vb())
            line = (f'  {i:3d} @{off:#08x} ps={len(v.tones)} tones={v.hdr["ts"]:2d} samples={len(v.vags):2d} '
                    f'body={body:#07x} ({100 * body / cfg["slot"]:3.0f}% of slot)')
            if c.seqs is not None:
                line += f' seq={len(c.seq_block()):#06x} tracks={len(c.seqs)}  font {i + 1:#04x}'
            print(line)
            for s in u.get(i, []):
                print('        ' + s)
            if c.seqs is not None:
                for k, sq in enumerate(c.seqs):
                    st = seq_stats(sq)
                    print(f'        seq {k}: {st["bpm"]} bpm, {st["secs"]:.0f} s, {st["notes"]} notes, '
                          f'channels {st["channels"]}, poly {st["poly"]}{", loop" if st["loop"] else ""}')
            off += slot


def cmd_info(name, idx):
    f = VhbFile(resolve(name)); c = f.chunks[idx]; v = c.vab
    print(json.dumps({k: v.hdr[k] for k in HDR_F if k != 'form'}))
    for p, pr in enumerate(v.progs):
        if not pr['tones']:
            continue
        print(f'program {p}: tones={pr["tones"]} mvol={pr["mvol"]} mpan={pr["mpan"]}')
        for t in v.tones_of(p):
            print(f'   keys {t["min"]:3d}-{t["max"]:3d} root {tone_pitch(t):g} (center {t["center"]} shift {t["shift"]:+d}) vol {t["vol"]} pan {t["pan"]} '
                  f'adsr {t["adsr1"]:04x}/{t["adsr2"]:04x} mode {t["mode"]} sample {t["vag"]}'
                  + (f'  (sound id {p * 16 + t["max"] - 60})' if f.kind in ('SS', 'SL', 'ESALL', 'SB') and 60 <= t['max'] < 76 else
                     f'  (sound id {t["max"]})' if f.kind in ('VBALL', 'VLALL') else ''))
    for k, vg in enumerate(v.vags):
        pcm, lp, end = adpcm_decode(vg, with_loop=True)
        print(f'sample {k + 1}: {len(vg)} bytes, {len(pcm)} samples ({len(pcm) / SPU_RATE:.2f} s at the root note)'
              + (f', loop from {lp}' if lp is not None else ''))
    if c.seqs:
        for k, sq in enumerate(c.seqs):
            print(f'seq {k}: {len(sq)} bytes', seq_stats(sq))


def tone_root(v, vagno):
    """(MIDI unity note, fraction above it) of the first tone that uses sample VAGNO."""
    for blk in v.tones:
        for t in blk:
            if t['vag'] == vagno:
                p = tone_pitch(t); n = math.floor(p)
                return n, p - n
    return 60, 0.0


def cmd_export(name, idxs, outdir):
    f = VhbFile(resolve(name)); os.makedirs(outdir, exist_ok=True)
    for i in (idxs or range(len(f.chunks))):
        c = f.chunks[i]; v = c.vab; base = os.path.join(outdir, f'{f.kind}_{i:02d}')
        hdr = dict(header={k: v.hdr[k] for k in HDR_F if k != 'form'},
                   programs={p: pr for p, pr in enumerate(v.progs) if pr['tones']},
                   tones=[[t for t in blk if t['vag']] for blk in v.tones])
        json.dump(hdr, open(base + '.json', 'w'), indent=1)
        vlist = list(v.vags)
        if v.extra and b'' in vlist:     # the 13 VBALL chunks whose last sample is listed with size 0
            vlist[vlist.index(b'')] = v.extra
        for k, vg in enumerate(vlist):
            if not vg:
                continue
            pcm, lp, end = adpcm_decode(vg, with_loop=True)
            if vg[:16] == bytes(16):        # the leading silent block import-wav adds back
                pcm = pcm[28:]; end = end and end - 28; lp = None if lp is None else lp - 28
            root, frac = tone_root(v, k + 1)
            write_wav(f'{base}_s{k + 1:02d}.wav', pcm, root=root, fine=int(frac * (1 << 32)),
                      loop=(lp, end) if lp is not None and end else None)
        if c.seqs:
            for k, sq in enumerate(c.seqs):
                nm = ''.join(ch if ch.isalnum() else '-' for ch in TRACK_NAME.get((i + 1, k), '')).strip('-')
                open(f'{base}_t{k}{"_" + nm if nm else ""}.mid', 'wb').write(seq_to_midi(sq))
        print(f'{base}: {len(v.vags)} samples' + (f', {len(c.seqs)} tracks' if c.seqs else ''))


def cmd_render(font, track, out, secs, vhb):
    data, rate = render(font, track, secs, vhb)
    w = wave.open(out, 'wb'); w.setnchannels(2); w.setsampwidth(2); w.setframerate(rate); w.writeframes(data); w.close()
    print(f'{out}: {secs} s of font {font:#x} track {track} ({TRACK_NAME.get((font, track), "?")})')


def cmd_import_midi(font, track, mid, out, vhb, loop, prog_map):
    f = VhbFile(resolve(vhb or 'FAALL'))
    if f.kind != 'FAALL':
        raise SoundError('import-midi works on FAALL.VHB (the only file with sequences)')
    if not 1 <= font <= len(f.chunks):
        raise SoundError(f'font must be 1..{len(f.chunks)} (the original executable accepts 1..0x21)')
    c = f.chunks[font - 1]
    if not 0 <= track <= len(c.seqs):
        raise SoundError(f'font {font:#x} has tracks 0..{len(c.seqs) - 1} (or {len(c.seqs)} to append one)')
    seq = midi_to_seq(open(mid, 'rb').read(), loop=loop, prog_map=prog_map)
    st = seq_stats(seq)
    for ch, p in st['programs']:
        if not c.vab.tones_of(p):
            print(f'warning: channel {ch} selects program {p}, which font {font:#x} does not have '
                  f'(it has {[i for i, pr in enumerate(c.vab.progs) if pr["tones"]]})')
    if st['poly'] > 14:
        print(f'warning: up to {st["poly"]} simultaneous notes; the SPU has 24 voices and the game\'s sound '
              'effects take channels 10-23')
    if track == len(c.seqs):
        c.seqs.append(seq)
    else:
        c.seqs[track] = seq
    errs = check_chunk('FAALL', font - 1, c, indexed=f.indexed)
    if errs:
        raise SoundError('; '.join(errs))
    open(out, 'wb').write(f.build())
    print(f'{out}: font {font:#x} track {track} ← {mid} ({st["notes"]} notes, {st["secs"]:.0f} s, '
          f'{len(seq)} bytes; SEQ block {len(c.seq_block()):#x}/{SEQ_BUFFER_MOD if f.indexed else SEQ_BUFFER_MAX:#x})')


def parse_note(s):
    if s is None:
        return None
    try:
        return int(s)
    except ValueError:
        names = {'C': 0, 'D': 2, 'E': 4, 'F': 5, 'G': 7, 'A': 9, 'B': 11}
        n = names[s[0].upper()]; r = s[1:]
        if r.startswith('#'):
            n += 1; r = r[1:]
        elif r.startswith('b'):
            n -= 1; r = r[1:]
        return n + 12 * (int(r) + 1)


def cmd_import_wav(name, idx, wavp, out, vagno, program, keys, root, rate, loop, volume):
    f = VhbFile(resolve(name)); c = f.chunks[idx]; v = c.vab
    pcm, wrate, wloop, wroot = read_wav(wavp)
    if rate and rate != wrate:
        if wloop:
            wloop = (int(wloop[0] * rate / wrate), int(wloop[1] * rate / wrate))
        pcm = resample(pcm, wrate, rate); wrate = rate
    if loop:
        a, _, b = loop.partition(':')
        wloop = (int(a), int(b) if b else len(pcm))
    if wloop:
        pcm = pcm[:wloop[1]]
    # The root is the key at which the WAV plays at its own pitch: center − shift/128 =
    # root − 12·log2(rate / 44100) (libsnd adds the shift to the note, in steps of 1/16 semitone;
    # center is rounded up so that the shift is ≥ 0: a negative one indexes before libsnd's pitch
    # table when the note is a multiple of 12 above center − 60). Effects and voices are
    # single-key tones (playSound keys 60 + id % 16, or the voice id), so with no --root and no
    # 'smpl' root each such tone gets its own key as the root and plays the WAV unchanged;
    # otherwise C4 = 60.
    given = parse_note(root) if root is not None else wroot
    root = given if given is not None else 60

    def tuning(r, delta=0.0):
        pitch = r - 12 * math.log2(wrate / SPU_RATE) + delta
        ce = int(math.ceil(pitch - 1e-9)); sh = int(round((ce - pitch) * 16)) * 8
        return (ce - 1, 0) if sh == 128 else (ce, sh)

    def key_root(t):
        return t['max'] if given is None and t['min'] == t['max'] else root
    center, shift = tuning(root)
    enc = adpcm_encode(pcm, loop_start=wloop[0] if wloop else None)
    v.touched = True
    if vagno is not None:
        if not 1 <= vagno <= len(v.vags):
            raise SoundError(f'sample must be 1..{len(v.vags)}')
        v.vags[vagno - 1] = enc; roots = []
        # Tones that share the sample keep their tuning relative to the first one (SS plays
        # sample 1 at five different pitches for ids 0, 1, 5, 6, 7): the first one gets the root.
        users = [t for blk in v.tones for t in blk if t['vag'] == vagno]
        ref = users[0] if users else None; ref_pitch = tone_pitch(ref) if ref else 0
        for t in users:
            delta = tone_pitch(t) - ref_pitch if t is not ref else 0.0
            t['center'], t['shift'] = tuning(key_root(ref), delta)
            roots.append(f'{key_root(ref) if t is ref else f"{delta:+g} st"} → center {t["center"]} shift {t["shift"]:+d}')
            if volume is not None:
                t['vol'] = volume
        what = f'sample {vagno}'
        tun = ', '.join(roots) or 'no tone uses it'
    else:
        if v.extra:
            raise SoundError('this chunk keeps the bytes of its last sample after a size-0 entry (sound.md § 1.2); '
                             'appending would shift them: replace a sample with --vag instead')
        lo, _, hi = (keys or f'{int(round(root))}-{int(round(root))}').partition('-')
        lo = parse_note(lo); hi = parse_note(hi or lo)
        if given is None and lo == hi:          # a new effect/voice id: plays unchanged at its key
            root = lo; center, shift = tuning(root)
        v.vags.append(enc); vagno = len(v.vags)
        nonempty = [i for i, pr in enumerate(v.progs) if pr['tones']]
        if program in nonempty:
            blk = v.tones[v.program_block(program)]
            slot = next((k for k, t in enumerate(blk) if not t['vag']), None)
            if slot is None:
                raise SoundError(f'program {program} already has 16 tones')
        elif program == len(nonempty) and nonempty == list(range(len(nonempty))):
            tmpl = v.progs[nonempty[-1]] if nonempty else None
            v.progs[program] = dict(tmpl or dict(zip(PROG_F, (0, 127, 255, 255, 64, 255, 0, 0xFFFFFFFF, 0xFFFFFFFF))))
            v.progs[program]['tones'] = 0
            blank = dict(zip(TONE_F, VAGATR.unpack(bytes(VAGATR.size))))
            v.tones.append([dict(blank) for _ in range(16)]); blk = v.tones[-1]; slot = 0
        else:
            raise SoundError(f'program must be an existing one ({nonempty}) or {len(nonempty)} (new)')
        tmpl = next((t for b in v.tones for t in b if t['vag']), None)
        t = blk[slot]
        if tmpl:
            t.update({k: tmpl[k] for k in ('prior', 'mode', 'pbmin', 'pbmax', 'r0', 'r1', 'r2', 'r3', 'res1', 'res2')})
        t.update(vol=volume if volume is not None else 127, pan=64, center=center, shift=shift, min=lo, max=hi,
                 adsr1=0x80FF, adsr2=0x5FC0 | (0x0D if wloop else 0x08), prog=program, vag=vagno)
        v.progs[program]['tones'] += 1
        tun = f'{root} → center {center} shift {shift:+d}'
        what = (f'new sample {vagno} as program {program} keys {lo}-{hi}'
                + (f' (sound id {program * 16 + hi - 60})' if f.kind in ('SS', 'SL', 'ESALL', 'SB') else
                   f' (sound id {hi})' if f.kind in ('VBALL', 'VLALL') else ''))
    errs = check_chunk(f.kind, idx, c, indexed=f.indexed)
    if errs:
        raise SoundError('; '.join(errs))
    data = f.build()
    open(out, 'wb').write(data)
    print(f'{out}: {f.kind} chunk {idx} {what} ← {wavp} ({len(pcm)} samples at {wrate} Hz = {len(enc)} bytes ADPCM, '
          f'root {tun}, body {len(v.vb()):#x}/{FILES[f.kind]["slot"]:#x})'
          + ('' if len(data) == f.orig_size else
             f'; file size {len(data):#x} < {f.orig_size:#x}: build-disc.py pads it back (original executable)'
             if len(data) < f.orig_size and FILES[f.kind]['stride'] is None else
             f'; file size changed to {len(data):#x}: build with --relayout'))


def cmd_add_font(mids, base, out, vhb, loop, prog_map):
    """A new music font: a copy of font BASE's instruments (VAB) with the MIDI files as its tracks,
    appended to FAALL (written in the indexed layout: the soundlimits executable)."""
    import copy
    f = VhbFile(resolve(vhb or 'FAALL'))
    if f.kind != 'FAALL':
        raise SoundError('add-font works on FAALL.VHB')
    if not 1 <= base <= len(f.chunks):
        raise SoundError(f'instrument font must be 1..{len(f.chunks)}')
    if len(f.chunks) >= 254:
        raise SoundError('254 fonts at most (SET_BGM takes a byte; 0xFF stops the music)')
    f.to_indexed()
    c = copy.deepcopy(f.chunks[base - 1]); c.seqs = []
    for mid in mids:
        seq = midi_to_seq(open(mid, 'rb').read(), loop=loop, prog_map=prog_map); st = seq_stats(seq)
        for ch, p in st['programs']:
            if not c.vab.tones_of(p):
                print(f'warning: {mid}: channel {ch} selects program {p}, which font {base:#x} does not have')
        if st['poly'] > 14:
            print(f'warning: {mid}: up to {st["poly"]} simultaneous notes (effects use voices 10-23)')
        c.seqs.append(seq)
        print(f'  track {len(c.seqs) - 1}: {mid}: {st["notes"]} notes, {st["secs"]:.0f} s, {len(seq)} bytes')
    font = len(f.chunks) + 1
    errs = check_chunk('FAALL', font - 1, c, indexed=True)
    if errs:
        raise SoundError('; '.join(errs))
    f.chunks.append(c)
    data = f.build(); open(out, 'wb').write(data)
    print(f'{out}: new font {font} ({font:#x}) with the instruments of font {base:#x}, {len(c.seqs)} track(s), '
          f'SEQ block {len(c.seq_block()):#x}/{SEQ_BUFFER_MOD:#x} (original limit {SEQ_BUFFER_MAX:#x}); '
          f'play it with SET_BGM {font:#x} (`sound.py set-bgm`); needs the soundlimits executable and --relayout')


def set_bgm(maphead, screen, font):
    """The MAPHEAD.SCN bytes `maphead` with the font of the first SET_BGM (5D xx) in screen's section changed.
    -> (bytes, the old font, the instruction's offset)"""
    if os.path.dirname(os.path.abspath(__file__)) not in sys.path: sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    from dws import bytecode as bytecode
    mh = bytearray(maphead)
    _, secs, _, _, _ = bytecode.sweep(bytes(mh)); d = dict(secs)
    if screen not in d:
        raise SoundError(f'MAPHEAD has no section {screen}')
    p = d[screen]
    for _ in range(400):
        n, _t = bytecode.instr_length(bytes(mh), p)
        if n is None or mh[p] in (0xFE, 0xFF):
            break
        if mh[p] == 0x5D:
            old = mh[p + 1]; mh[p + 1] = font & 0xFF
            return bytes(mh), old, p
        p += n
    raise SoundError(f'screen {screen}: no SET_BGM in its MAPHEAD section')


def cmd_set_bgm(screen, font, out, maphead):
    """Changes the font of the first SET_BGM (5D xx) in a screen's MAPHEAD section."""
    src = maphead or os.path.join(ROOT, 'extracted/SCN/MAPHEAD.SCN')
    data, old, p = set_bgm(open(src, 'rb').read(), screen, font)
    open(out, 'wb').write(data)
    print(f'{out}: screen {screen}: SET_BGM {old:#x} -> {font:#x} at {p:#x} (same size; '
          f'--file SCN/MAPHEAD.SCN={out})')


# ---------------------------------------------------------------------------------------------
# SPU allocation of the soundlimits executable (sound.c spuPlaceBank), for budget checks
SPU_BANKS_START, SPU_REVERB_START = 0x1010, 0x7B7C0
SPU_HOME = [0x1010, 0xE800, 0x1B800, 0x2A000, 0x31800, 0x34000, 0x36800, 0x39000, None]
BANK_NAMES = ['SS', 'SL', 'music', 'VLALL', 'VBALL0', 'VBALL1', 'VBALL2', 'VBALL3', 'ESALL/SB']


class SpuAlloc:
    """The allocator of sound.c, step for step: bank 8 as high as possible, the others in their
    original slot when free, else the lowest free space; evictions as in spuPlaceBank."""

    def __init__(self):
        self.addr = [0] * 9; self.size = [0] * 9; self.map_region = False; self.log = []

    def fits(self, bank, a, n):
        if n > SPU_REVERB_START - SPU_BANKS_START or a < SPU_BANKS_START or a > SPU_REVERB_START - n:
            return False
        return all(i == bank or not self.size[i] or not (a < self.addr[i] + self.size[i] and self.addr[i] < a + n)
                   for i in range(9))

    def find(self, bank, n):
        c = SPU_REVERB_START - n if bank == 8 else SPU_HOME[bank]
        if self.fits(bank, c, n):
            return c
        best = 0
        for i in [-1] + list(range(9)):
            if i >= 0 and not self.size[i]:
                continue
            if bank == 8:
                c = ((SPU_REVERB_START if i < 0 else self.addr[i]) - n) & ~15
                if self.fits(bank, c, n) and c > best: best = c
            else:
                c = SPU_BANKS_START if i < 0 else self.addr[i] + self.size[i]
                if self.fits(bank, c, n) and (best == 0 or c < best): best = c
        return best

    def place(self, bank, body, what='', map_region=None):
        n = max(16, (body + 15) & ~15); self.size[bank] = 0
        a = self.find(bank, n)
        if not a and bank != 8 and self.size[8] and self.map_region:
            self.size[8] = 0; self.map_region = False; self.log.append(f'evict map effects for {BANK_NAMES[bank]}')
            a = self.find(bank, n)
        if not a and bank == 8 and self.size[2] and self.addr[2] != SPU_HOME[2]:
            self.size[2] = 0; self.log.append('evict the overflowed music font for bank 8')
            a = self.find(bank, n)
        if bank == 8:
            self.map_region = bool(map_region)
        if not a:
            self.log.append(f'FAIL {BANK_NAMES[bank]} {what} {body:#x} bytes')
            return False
        self.addr[bank] = a; self.size[bank] = n
        return True

    def free_gaps(self):
        used = sorted((self.addr[i], self.addr[i] + self.size[i]) for i in range(9) if self.size[i])
        gaps = []; p = SPU_BANKS_START
        for a, e in used:
            if a > p: gaps.append((p, a - p))
            p = max(p, e)
        if SPU_REVERB_START > p: gaps.append((p, SPU_REVERB_START - p))
        return gaps


def chunk_body(c):
    """What spuPlaceBank allocates for a chunk: the body or VabHdr.fsize - header, whichever is larger."""
    vh = c.vab.vh(); fsize = struct.unpack_from('<I', vh, 12)[0]
    return max(len(c.vab.vb()), fsize - len(vh))


def cmd_spu_budget(vhb_dir, screens, partner, maphead):
    """Simulates the SPU allocation of the soundlimits executable on each screen S with the given (or
    the original) sound files, arriving from every other screen P: P's music and map region, then S's,
    a battle on S (SB, three enemy voice sets of the largest size, battle font 0x21) and the way back
    (S's region and music). Reports the smallest largest-free-block seen at each stage."""
    def load(k):
        p = os.path.join(vhb_dir, k + '.VHB') if vhb_dir and os.path.exists(os.path.join(vhb_dir, k + '.VHB')) else resolve(k)
        return VhbFile(p)
    F = {k: load(k) for k in FILES}
    body = {k: [chunk_body(c) for c in F[k].chunks] for k in FILES}
    maps = {int(r['id']): r for r in csv_rows('map_files.csv')}
    vl = body['VLALL']; vb = body['VBALL']
    if partner is None:
        pl, pb = max(vl), max(vb); pname = 'largest partner voices'
    else:                                          # the species file's voices (what the build writes into VLALL/VBALL)
        import species
        s = species.load_content().get(partner)
        if s is None: raise SoundError(f'no species {partner} in content/species')
        pl = vl[s.get('partner', {}).get('voice', 15)]; pb = vb[s['voice']]; pname = f'partner type {partner}'
    enemies = sorted(vb, reverse=True)[:3]
    mh = maphead or (os.path.join(vhb_dir, 'MAPHEAD.SCN') if vhb_dir and os.path.exists(os.path.join(vhb_dir, 'MAPHEAD.SCN')) else None)
    pairs = []                                     # (screen, font, region)
    for sid, lst in sorted(bgm_by_screen(mh).items()):
        if sid not in maps:
            continue
        for font in sorted({music_override(f, m)[0] for f, m in lst if f != 0xFF}):
            pairs.append((sid, font, int(maps[sid]['flags']) & 0x1F))
    nf, nr = len(body['FAALL']), len(body['ESALL'])
    pairs = [x for x in pairs if x[1] <= nf and x[2] < nr]
    preds = list({(f, r) for _, f, r in pairs})
    print(f'SPU budget ({pname}; enemies {", ".join(hex(e) for e in enemies)}; {len(preds)} arrival states); '
          f'sizes from {vhb_dir or "extracted/"}' + (f', music from {mh}' if mh else ''))
    big = lambda a: max((g[1] for g in a.free_gaps()), default=0)
    bad = 0
    for sid, font, region in pairs:
        if screens and sid not in screens:
            continue
        worst = [1 << 30] * 3; notes = set(); fail = set()
        for pf, pr in preds:
            a = SpuAlloc()
            a.place(0, body['SS'][0]); a.place(1, body['SL'][0]); a.place(3, pl); a.place(4, pb)
            a.place(2, body['FAALL'][pf - 1]); a.place(8, body['ESALL'][pr], map_region=True); a.log = []
            if font != pf: a.place(2, body['FAALL'][font - 1], f'font {font:#x}')
            if region != pr: a.place(8, body['ESALL'][region], f'region {region}', map_region=True)
            worst[0] = min(worst[0], big(a))
            a.place(8, body['SB'][0], 'SB')
            for k, e in enumerate(enemies):
                a.place(5 + k, e, 'enemy voices')
            a.place(2, body['FAALL'][0x20], 'battle font 0x21')
            worst[1] = min(worst[1], big(a))
            a.place(8, body['ESALL'][region], f'region {region}', map_region=True)
            a.place(2, body['FAALL'][font - 1], f'font {font:#x}')
            worst[2] = min(worst[2], big(a))
            for l in a.log:
                (fail if l.startswith('FAIL') else notes).add(l)
        bad += bool(fail)
        print(f'  {sid:3d} {maps[sid]["map_name"][:24]:24} font {font:#04x} region {region:2d}  largest free block: world '
              f'{worst[0] / 1024:6.1f} KB, battle {worst[1] / 1024:6.1f} KB, after {worst[2] / 1024:6.1f} KB'
              + (('  ' + '; '.join(sorted(fail | notes))) if fail or notes else ''))
    print(f'{bad} screen/font pair(s) with a bank that does not fit')
    return bad == 0


def cmd_index(name, out):
    f = VhbFile(resolve(name)); was = f.indexed; f.to_indexed()
    nsec, ent = f.index()
    print(f'{f.kind}.VHB: {len(ent)} chunks, index of {nsec} sector(s)' + ('' if was else ' (converted from the original layout)'))
    for i, (sec, n) in enumerate(ent):
        print(f'  {i:3d}  sector {sec:#06x}  {n:3d} sectors' + (f'  font {i + 1:#04x}' if f.kind == 'FAALL' else ''))
    if out:
        data = f.build(); open(out, 'wb').write(data)
        print(f'{out}: {len(data):#x} bytes (original {os.path.getsize(os.path.join(VHBDIR, f.kind + ".VHB")):#x}); '
              f'needs the soundlimits executable and a --relayout disc')


def cmd_roundtrip():
    nseq = 0; ok = True
    for k in FILES:
        p = os.path.join(VHBDIR, k + '.VHB'); d = open(p, 'rb').read()
        f = VhbFile(p); b = f.build()
        same = b == d
        ok &= same
        print(f'{k}.VHB: {len(f.chunks)} chunks, rebuild {"identical" if same else "DIFFERS"}')
        if k in INDEXED:     # original -> indexed -> parsed back: the same chunks
            f.to_indexed(); ix = f.build(); tmp = os.path.join(ROOT, 'build', f'.roundtrip.{k}.VHB')
            os.makedirs(os.path.dirname(tmp), exist_ok=True); open(tmp, 'wb').write(ix)
            g = VhbFile(tmp); os.remove(tmp)
            same = g.indexed and [c.build() for c in g.chunks] == [c.build() for c in f.chunks] and g.build() == ix
            ok &= same
            print(f'  indexed layout: {len(ix):#x} bytes, {"same chunks" if same else "DIFFERS"}')
        for i, c in enumerate(f.chunks):
            for e in check_chunk(k, i, c):
                print(f'  limit: chunk {i}: {e}'); ok = False
            for t, s in enumerate(c.seqs or []):
                m = seq_to_midi(s); back = midi_to_seq(m); nseq += 1
                if back != s:
                    print(f'  seq {i}.{t}: MIDI round trip differs'); ok = False
    print(f'{nseq} sequences through MIDI and back: {"all identical" if ok else "FAILED"}')
    # ADPCM encoder: decode and re-encode the samples of one music font (lossy, so measured)
    v = VhbFile(os.path.join(VHBDIR, 'FAALL.VHB')).chunks[0x1B].vab; same = 0; worst = 1e9
    for vg in v.vags:
        pcm, lp, end = adpcm_decode(vg, with_loop=True)
        enc = adpcm_encode(pcm[28:end], None if lp is None else lp - 28)
        same += enc == vg
        back = adpcm_decode(enc)
        sig = sum(x * x for x in pcm[:len(back)]); err = sum((a - b) ** 2 for a, b in zip(pcm, back))
        worst = min(worst, 10 * math.log10(sig / max(err, 1)))
    enc_ok = worst > 60 and same > 0
    print(f'ADPCM re-encode of font 0x1C: {same}/{len(v.vags)} samples byte-identical, worst SNR {worst:.0f} dB'
          + ('' if enc_ok else ' FAILED'))
    return ok and enc_ok


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sp = ap.add_subparsers(dest='cmd', required=True)
    a = sp.add_parser('list'); a.add_argument('files', nargs='*')
    a = sp.add_parser('info'); a.add_argument('file'); a.add_argument('chunk', type=lambda s: int(s, 0))
    a = sp.add_parser('export'); a.add_argument('file'); a.add_argument('chunks', nargs='*', type=lambda s: int(s, 0))
    a.add_argument('-o', '--out', required=True)
    a = sp.add_parser('render'); a.add_argument('font', type=lambda s: int(s, 0)); a.add_argument('track', type=int)
    a.add_argument('-o', '--out', required=True); a.add_argument('--secs', type=float, default=30); a.add_argument('--vhb')
    a = sp.add_parser('import-midi'); a.add_argument('font', type=lambda s: int(s, 0)); a.add_argument('track', type=int)
    a.add_argument('midi'); a.add_argument('-o', '--out', required=True); a.add_argument('--vhb')
    a.add_argument('--loop', action='store_true'); a.add_argument('--prog-map', default='')
    a = sp.add_parser('import-wav'); a.add_argument('file'); a.add_argument('chunk', type=lambda s: int(s, 0))
    a.add_argument('wav'); a.add_argument('-o', '--out', required=True)
    g = a.add_mutually_exclusive_group(required=True); g.add_argument('--vag', type=int); g.add_argument('--program', type=int)
    a.add_argument('--keys'); a.add_argument('--root'); a.add_argument('--rate', type=int); a.add_argument('--loop')
    a.add_argument('--volume', type=int)
    a = sp.add_parser('check'); a.add_argument('file')
    a = sp.add_parser('index'); a.add_argument('file'); a.add_argument('-o', '--out')
    a = sp.add_parser('spu-budget'); a.add_argument('--vhb-dir'); a.add_argument('--screens', default='')
    a.add_argument('--partner', type=int); a.add_argument('--maphead')
    a = sp.add_parser('add-font'); a.add_argument('midi', nargs='+'); a.add_argument('--instruments', required=True,
                                                                                  type=lambda s: int(s, 0))
    a.add_argument('-o', '--out', required=True); a.add_argument('--vhb'); a.add_argument('--loop', action='store_true')
    a.add_argument('--prog-map', default='')
    a = sp.add_parser('set-bgm'); a.add_argument('screen', type=int); a.add_argument('font', type=lambda s: int(s, 0))
    a.add_argument('-o', '--out', required=True); a.add_argument('--maphead')
    sp.add_parser('roundtrip')
    o = ap.parse_args()
    try:
        if o.cmd == 'list':
            cmd_list(o.files)
        elif o.cmd == 'info':
            cmd_info(o.file, o.chunk)
        elif o.cmd == 'export':
            cmd_export(o.file, o.chunks, o.out)
        elif o.cmd == 'render':
            cmd_render(o.font, o.track, o.out, o.secs, o.vhb)
        elif o.cmd == 'import-midi':
            pm = dict(tuple(int(x) for x in kv.split('=')) for kv in o.prog_map.split(',') if kv)
            cmd_import_midi(o.font, o.track, o.midi, o.out, o.vhb, o.loop, pm)
        elif o.cmd == 'import-wav':
            cmd_import_wav(o.file, o.chunk, o.wav, o.out, o.vag, o.program, o.keys, o.root, o.rate, o.loop, o.volume)
        elif o.cmd == 'add-font':
            pm = dict(tuple(int(x) for x in kv.split('=')) for kv in o.prog_map.split(',') if kv)
            cmd_add_font(o.midi, o.instruments, o.out, o.vhb, o.loop, pm)
        elif o.cmd == 'set-bgm':
            cmd_set_bgm(o.screen, o.font, o.out, o.maphead)
        elif o.cmd == 'spu-budget':
            scr = [int(x) for x in o.screens.split(',') if x]
            sys.exit(0 if cmd_spu_budget(o.vhb_dir, scr, o.partner, o.maphead) else 1)
        elif o.cmd == 'index':
            cmd_index(o.file, o.out)
        elif o.cmd == 'check':
            sys.exit(0 if cmd_check(o.file) else 1)
        elif o.cmd == 'roundtrip':
            sys.exit(0 if cmd_roundtrip() else 1)
    except SoundError as e:
        sys.exit(f'sound.py: {e}')


if __name__ == '__main__':
    main()
