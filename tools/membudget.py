#!/usr/bin/env python3
"""Memory budget report: main RAM (malloc3 heap, fixed buffers, stack), VRAM and SPU RAM.

Usage:
  membudget.py live [--json] [--vram]     report for what the running emulator shows now
                                          (tools/dev/emulator.py, EMU_PORT); original or GCC builds
  membudget.py sweep [--state S] [--out CSV] [--screens A-B,C] [--hours 12,20] [--chain]
                                          warps through every screen from a save state
                                          (default build/states/u.state, File City) and writes
                                          docs/data/memory-budget.csv; one row per screen and hour
  membudget.py estimate SCREEN [--hour H] [--maphead MAPHEAD.scn.txt]
                                          static: models MAPHEAD loads on SCREEN (no emulator),
                                          compared with the free heap the sweep measured there
  membudget.py vram-map SCREEN            static VRAM occupancy of a screen in the world

The heap is Psy-Q's malloc3 (InitHeap3/malloc3/free3, libapi): K&R blocks
{u32 next, u32 size in 8-byte units including the header}, a circular free list
sorted by address that `_freep` points into, and a size-0 sentinel at the end of the
heap. malloc3 carves from the top of the first free block that fits. Allocated blocks
keep their size at +4, so the heap can be walked block by block from its base
((_end & ~15) + 16, initializeHeap in main.c) to the sentinel.

`screen_budget(screen, hour=None, maphead_text=None)` is the importable static check
(for tools/dws/backend.py): it returns the heap the screen's MAPHEAD setup needs on its
worst path and how much the sweep says is available there.
"""

from pathlib import Path as _DevPath
import sys as _dev_sys
_dev_sys.path.insert(0, str(next(p for p in _DevPath(__file__).resolve().parents if (p / "tools").is_dir())))
import csv, glob, json, os, re, struct, subprocess, sys, time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, 'tools'))
from functools import lru_cache
from tools.dev import symbols as dwsyms

CSV_OUT = os.path.join(ROOT, 'docs/data/memory-budget.csv')
CACHE = os.path.join(ROOT, 'build/membudget')
WIDE_ID_BUILDS = {'mods'}               # 16-bit screen ids (the wide-ids patches)

POS_DATA = 0x88                         # sizeof(PositionData)
MOMENTUM = 0x52                         # sizeof(MomentumData)
TEMP_TIM = 0x4800                       # loadDigimonTexture's malloc3
HEAP_FOR_NPCS = 0x30388                 # original executable: whole heap (0x30390) minus the sentinel; the
                                        # sweep found nothing else resident in it on world screens
ENTITY_MAX = 10
TFS_HEADER, TFS_SLOT, TFS_RING_SLOTS = 0x1000, 0x4800, 8   # include/dw/memmap.h (memreclaim builds)
MC = 0x1C                               # sizeof(ModelComponent)

# fixed buffer capacities of the original executable (the patch series' ids work)
CAP = {'PARTNER_MODEL_BUFFER': 0x18800,     # PARTNER_MMD_MAX=0x20000 for the scale build (memmap.h): configure()
       'TAMER_MODEL_BUFFER': 0xE000, 'MAPHEAD_SCRIPT_BUFFER': 0x61A8,
       'MAP_SCRIPT_BUFFER': 0x4000, 'SEQ_BUFFER': 0x5800, 'TFS': 0x78800, 'EFE_HEAP': 0x41000}

# SPU banks (sound.c VHB_SOUNDBUFFER_START, VHB_HEADER_*); bank 8 ends where the reverb starts
SPU_BANKS = [('SS', 'VHB_HEADER_SS', 0x1000), ('SL', 'VHB_HEADER_SL', 0x1000),
             ('FAALL', 'VHB_HEADER_FAALL', 0x2000), ('VLALL', 'VHB_HEADER_VLALL', 0x1000),
             ('VBALL0', 'VHB_HEADER_VBALL_0', 0x1000), ('VBALL1', 'VHB_HEADER_VBALL_1', 0x1000),
             ('VBALL2', 'VHB_HEADER_VBALL_2', 0x1000), ('VBALL3', 'VHB_HEADER_VBALL_3', 0x1000),
             ('ESALL/SB', 'VHB_HEADER_ESALL_SB', 0x1800)]
SPU_STARTS = [0x1010, 0xE800, 0x1B800, 0x2A000, 0x31800, 0x34000, 0x36800, 0x39000, 0x3B800]
SPU_REVERB = 0x7B7C0
SPU_SIZE = 0x80000

# VRAM (x, y, w, h in 16-bit units), the engine's VRAM map
VRAM_FIXED = [
    ('framebuffer 0', 0, 0, 320, 240), ('framebuffer 1', 0, 240, 320, 240),
    ('CLUT strip (map, models, font, effects)', 0, 480, 320, 32),
    ('item icons', 320, 0, 64, 128), ('SYSTEM_W (boxes, cursor)', 320, 128, 64, 128),
    ('tamer texture', 320, 256, 64, 128), ('partner texture', 320, 384, 64, 128),
    ('SBOY/medals (lower half)', 512, 384, 64, 128), ('rendered text', 704, 256, 64, 256),
    ('map background tile window', 768, 0, 256, 384),
    ('DEFEFF', 768, 384, 64, 48), ('EX', 768, 448, 34, 48), ('SPOT256 shadow', 832, 384, 64, 128),
    ('BI_IN', 896, 384, 64, 64), ('FI_INFO (clock/HUD)', 896, 448, 64, 64),
    ('FEEL_EF (status icons)', 960, 384, 64, 64), ('BTLCOMND', 960, 448, 64, 64),
]
NPC_SLOTS = [(384 + 64 * (k // 2), 256 + 128 * (k % 2), 64, 128) for k in range(5)]
EFE_SLOTS = [(576 + 64 * (i // 8), 256 + 32 * (i % 8), 64, 32) for i in range(16)]


# ---------------------------------------------------------------------------- data files
def _csv(name):
    return list(csv.DictReader(open(os.path.join(ROOT, 'docs/data', name))))


try:                                             # every species, 0..1023 (content/species, tools/species.py)
    import species as _species
    DIGI = _species.all_rows()
except ImportError:
    _species, DIGI = None, {}
MAPS = {int(r['id']): r for r in _csv('map_files.csv')}
_MODELS = {}


def model_file(t):
    """CHDAT/MMDn/NAME.MMD of Digimon type t: the model name of its species file (content/species `model.name`, the name the
    executable's table holds; any release's disc has the same files)."""
    if not _MODELS:
        _MODELS.update({i: (s.get('model') or {}).get('name') for i, s in _species.load_content().items()} if _species else {})
    name = _MODELS.get(t)
    if not name:
        raise ValueError(f'species {t}: no species file with a model.name (content/species): its model cannot be measured')
    return os.path.join(ROOT, f'extracted/CHDAT/MMD{t // 30}/{name}.MMD'), name


MODEL_ARCHIVE = None
TARGET_FACTS = {}
NPC_STAGE_MAX = 0


@lru_cache(None)
def archive_models(path):
    blob, _, rows = _species.read_archive(path)
    return blob, rows, _species.record_originals(blob)


@lru_cache(None)
def model_data(t):
    """Bytes the loader reads, including DIGI.DAT replacements of original species."""
    if MODEL_ARCHIVE:
        blob, rows, originals = archive_models(MODEL_ARCHIVE)
        if t >= 180 or t in originals:
            row = rows[t]
            start = row['modelSector'] * 2048
            return blob[start:start + row['modelSize']]
    if t >= 180:
        raise ValueError(f'species {t}: DW_MODEL_ARCHIVE is required to measure its model')
    path, _ = model_file(t)
    return open(path, 'rb').read()


def mmd_size(t):
    if MODEL_ARCHIVE:
        return len(model_data(t))  # explicit target checks must not silently budget missing models as zero
    if t < 180:
        try: return len(model_data(t))
        except FileNotFoundError: return 0
    return _species.model_size(t) if _species else 0


def staged(t):
    return 0 < mmd_size(t) <= NPC_STAGE_MAX and ((mmd_size(t) + 2047) & ~2047) <= NPC_STAGE_MAX


def blk(n):
    """malloc3 block size for a request of n bytes (rounded to 8 + 8 header)."""
    return ((n + 7) & ~7) + 8


TRIMMED = False         # NPC models trimmed on load (memreclaim builds: npc_anim_trim.c); set by --trimmed


@lru_cache(None)
def model_block(t):
    return blk((mmd_size(t) + 0x7FF) & ~0x7FF)


def model_block_resident(t):
    """The block a loaded NPC model keeps: trimNpcModel gives back all but its trimmed size
    (rounded to 8) when that frees 16 bytes or more."""
    full = model_block(t)
    # A recorded target has its compiled trim masks even without a local ELF.
    if not TRIMMED and not TARGET_FACTS.get('npc_anim_keep'):
        return blk(mmd_size(t)) if staged(t) else full
    import npcanims
    size = npcanims.trimmed_size(t)
    if staged(t): return blk(size)
    # trimNpcModel does not call shrinkBlock when compaction is a no-op.
    if size >= mmd_size(t): return full
    need = (size + 7) & ~7
    spare = (full - 8 - need) & ~7
    return full - spare if spare >= 16 else full


def instance_blocks(t):
    b = int(DIGI[t]['bone_count']) if t in DIGI else 0
    if MODEL_ARCHIVE:
        _, rows, originals = archive_models(MODEL_ARCHIVE)
        if t >= 180 or t in originals:
            b = rows[t]['para']['boneCount']
    return blk(b * POS_DATA) + blk(b * MOMENTUM)


def digi_name(t):
    return DIGI[t]['name'] if t in DIGI else f'#{t}'


def map_path(screen, ext='MAP'):
    r = MAPS.get(screen)
    if not r: return None
    f = glob.glob(os.path.join(ROOT, f'extracted/MAP/*/{r["file"]}.{ext}'))
    return f[0] if f else None


# ---------------------------------------------------------------------------- emulator access
class Emu:
    def __init__(self):
        from tools.dev import emulator as _emu
        self.e = _emu
        self.build = None
        self.syms = None

    def ram(self):
        r = self.e.api('/api/v1/cpu/ram/raw', timeout=30)
        if self.build is None:
            self.build = dwsyms.detect_build(r) or 'orig'
            self.syms = Syms(self.build)
        return r

    def vram(self):
        return self.e.api('/api/v1/gpu/vram/raw', timeout=30)

    def poke(self, addr, data):
        self.e.api(f'/api/v1/cpu/ram/raw?offset={addr - 0x80000000}&size={len(data)}', data=data)

    def load(self, path):
        import urllib.parse
        return self.e.api('/api/v1/lua/load?file=' + urllib.parse.quote(os.path.abspath(path)), timeout=60).decode()


class Syms:
    """Symbol addresses for a build; also the linker's `NAME = .` words of GCC maps."""
    def __init__(self, build):
        self.build = build
        self.t = dict(dwsyms.table(build))
        if build != 'orig':
            for line in open(dwsyms.CANDIDATES[build][1]):
                m = re.match(r'\s+(0x[0-9a-f]+)\s+([A-Za-z_]\w*) = \.\s*$', line)
                if m: self.t.setdefault(m.group(2), int(m.group(1), 16))

    def __getitem__(self, k):
        return self.t[k]

    def get(self, k, d=None):
        return self.t.get(k, d)


class Ram:
    def __init__(self, data, syms):
        self.d, self.s = data, syms

    def u32(self, a): return struct.unpack_from('<I', self.d, a - 0x80000000)[0]
    def i32(self, a): return struct.unpack_from('<i', self.d, a - 0x80000000)[0]
    def u16(self, a): return struct.unpack_from('<H', self.d, a - 0x80000000)[0]
    def i16(self, a): return struct.unpack_from('<h', self.d, a - 0x80000000)[0]
    def u8(self, a): return self.d[a - 0x80000000]
    def b(self, a, n): return self.d[a - 0x80000000:a - 0x80000000 + n]
    def sym(self, k): return self.s[k]


def screen_id(r):
    a = r.sym('CURRENT_SCREEN')
    return r.i16(a) if dwsyms.wide_ids(r.s.build) else r.u8(a)


# ---------------------------------------------------------------------------- heap
def heap_walk(r):
    """Walks the malloc3 heap; returns totals and the list of blocks with their owner."""
    base = (r.u32(r.sym('_end')) & ~0xF) + 0x10
    stack_bottom = (r.u32(r.sym('_stack_addr')) - (r.u32(r.sym('_stack_size')) << 10)) & ~0xF
    end = stack_bottom
    try:   # tier 2, 8 MB mode (story-state-engine.md "Memory modes"): the arena is above 2 MB
        hs, he = r.u32(r.sym('g_heap_start')), r.u32(r.sym('g_heap_end'))
        if hs: base, end = hs, he
    except KeyError: pass
    freep = r.u32(r.sym('_freep'))
    free = {}
    p = freep
    for _ in range(4096):
        if not base <= p < end: break
        free[p] = r.u32(p + 4) * 8
        p = r.u32(p)
        if p == freep: break
    owners = heap_owners(r)
    blocks, a, bad = [], base, None
    while a < end - 8:
        size = r.u32(a + 4) * 8
        if size == 0 or a + size > end:
            if size: bad = a
            break
        if a in free:
            blocks.append(dict(addr=a, size=size, owner='(free)', kind='free'))
        else:
            kind, owner = owners.get(a + 8, ('unknown', 'unknown: ' + r.b(a + 8, 16).hex()))
            blocks.append(dict(addr=a, size=size, owner=owner, kind=kind))
        a += size
    free_sizes = [s for k, s in free.items() if s]
    used = sum(b['size'] for b in blocks if b['kind'] != 'free')
    by_kind = {}
    for b in blocks:
        if b['kind'] != 'free': by_kind[b['kind']] = by_kind.get(b['kind'], 0) + b['size']
    return dict(base=base, end=end, total=end - base, free=sum(free_sizes), largest=max(free_sizes, default=0),
                free_blocks=len(free_sizes), used=used, blocks=blocks, by_kind=by_kind, corrupt=bad)


def heap_owners(r):
    """payload address -> (kind, description) for every known malloc3 pointer."""
    own = {}
    npc = r.sym('NPC_MODELS')
    for i in range(5):
        m = npc + i * MC
        use, tmd, anim, mmd = (r.u32(m + k) for k in (0, 4, 8, 12))
        t = r.i16(m + 0x18)
        if use and mmd: own[mmd] = ('model', f'NPC model {digi_name(t)} (slot {i}, used {use}x)')
    unk = r.sym('UNKNOWN_MODEL')
    for i in range(16):
        m = unk + i * MC
        tmd, anim = r.u32(m + 4), r.u32(m + 8)
        if r.u32(m) and tmd: own.setdefault(tmd, ('model', f'UNKNOWN_MODEL[{i}] TMD'))
        if r.u32(m) and anim: own.setdefault(anim, ('model', f'UNKNOWN_MODEL[{i}] MTN'))
    et = r.sym('ENTITY_TABLE')
    for i in range(2, ENTITY_MAX):
        e = r.u32(et + 4 * i)
        if not 0x80000000 < e < 0x80800000: continue
        t = r.i32(e)
        own[r.u32(e + 4)] = ('posdata', f'entity {i} {digi_name(t)} posData')
        own[r.u32(e + 0xC)] = ('posdata', f'entity {i} {digi_name(t)} momentum')
    arena = r.s.get('STD_ARENA_MODEL')
    if arena and r.u32(arena): own[r.u32(arena)] = ('arena', 'STD_ARENA_MODEL (tournament arena)')
    return own


def stack_highwater(r):
    top = r.u32(r.sym('_stack_addr'))
    bottom = (top - (r.u32(r.sym('_stack_size')) << 10)) & ~0xF
    d = r.b(bottom, top - bottom)
    canary = d[:16] == struct.pack('<I', 0x57A6C0DE) * 4      # memreclaim builds: MOD_STACK_GUARD at the limit
    i = next((k for k in range(16 if canary else 0, len(d), 4) if d[k:k + 4] != b'\0\0\0\0'), len(d))
    return dict(size=top - bottom, deepest=bottom + i, used=len(d) - i)


# ---------------------------------------------------------------------------- SPU
def spu_banks(r):
    out = []
    alloc = 'SPU_BANK_SIZE' in r.s.t           # soundlimits build: banks allocated per load (sound.md § 8.3)
    for i, (name, sym, hcap) in enumerate(SPU_BANKS):
        a = r.sym(sym)
        form, _ver, _id, fsize, _res, ps, ts, vs = struct.unpack_from('<4sIIIHHHH', r.b(a, 0x20))
        if alloc:
            start = r.u32(r.sym('VHB_SOUNDBUFFER_START') + 4 * i); size = r.u32(r.sym('SPU_BANK_SIZE') + 4 * i)
            slot = size
        else:
            start = SPU_STARTS[i]; size = None
            slot = (SPU_STARTS[i + 1] if i + 1 < len(SPU_STARTS) else SPU_REVERB) - SPU_STARTS[i]
        if form != b'pBAV' or (alloc and not size):
            out.append(dict(bank=i, name=name, slot=slot, body=0, loaded=False, header=0, header_cap=hcap, start=start)); continue
        hs = 0x20 + 0x800 + ps * 0x200
        vag = struct.unpack_from('<256H', r.b(a + hs, 0x200))
        body = sum(vag[1:vs + 1]) * 8
        if alloc:   # libsnd turned the size table into addresses: the allocation is the body (16-aligned)
            body = size
        out.append(dict(bank=i, name=name, slot=slot, body=body, loaded=True, header=hs + 0x200, header_cap=hcap,
                        programs=ps, vags=vs, start=start))
    return out


def spu_gaps(banks):
    """Free blocks between the loaded banks (soundlimits layout): [(start, size)]."""
    used = sorted((b['start'], b['start'] + b['body']) for b in banks if b['loaded'])
    gaps = []; p = SPU_STARTS[0]
    for a, e in used:
        if a > p: gaps.append((p, a - p))
        p = max(p, e)
    if SPU_REVERB > p: gaps.append((p, SPU_REVERB - p))
    return gaps


# ---------------------------------------------------------------------------- VRAM
def map_tims(screen):
    p = map_path(screen)
    if not p: return None
    import dwmap
    m = dwmap.MapFile(open(p, 'rb').read())
    out = []
    for i, raw in enumerate(m.tims):
        t = dwmap.TIM(raw)
        out.append((f'map TIM {i} ({t.bpp} bpp)', t.x, t.y, t.w, t.h))
        if t.clut and t.clut[1] != 480:                 # loadMapImage1 skips CLUTs at y 480
            out.append((f'map TIM {i} CLUT', t.clut[0], t.clut[1], t.clut[2], t.clut[3]))
    return out


def vram_owners(screen, npc_taken=(), efe_taken=(), battle=False):
    rects = list(VRAM_FIXED)
    tims = map_tims(screen)
    rects += tims or []
    for k in npc_taken: rects.append((f'NPC slot {k}',) + NPC_SLOTS[k])
    for i in efe_taken: rects.append((f'EFE slot {i}',) + EFE_SLOTS[i])
    if battle: rects.append(('battle digits (efe.c)', 512, 248, 256, 7))
    return rects, tims is not None


def vram_report(rects):
    W, H = 1024, 512
    grid = [bytearray(W) for _ in range(H)]
    for _, x, y, w, h in rects:
        for yy in range(max(0, y), min(H, y + h)):
            grid[yy][x:x + w] = b'\1' * len(grid[yy][x:x + w])
    free_units = sum(row.count(0) for row in grid)
    # 16x16 cells fully free, largest free rectangle of cells
    C, R = W // 16, H // 16
    cell = [[all(not any(grid[y][cx * 16:cx * 16 + 16]) for y in range(cy * 16, cy * 16 + 16)) for cx in range(C)]
            for cy in range(R)]
    def largest(cell):
        best, hist = (0, None), [0] * C
        for cy in range(R):
            for cx in range(C): hist[cx] = hist[cx] + 1 if cell[cy][cx] else 0
            stack = []
            for cx in range(C + 1):
                h = hist[cx] if cx < C else 0
                start = cx
                while stack and stack[-1][1] >= h:
                    s, hh = stack.pop()
                    if hh * (cx - s) > best[0]: best = (hh * (cx - s), (s, cy - hh + 1, cx - s, hh))
                    start = s
                stack.append((start, h))
        return best
    rects, work = [], [row[:] for row in cell]
    while len(rects) < 4:
        n, r = largest(work)
        if not n: break
        x, y, w, h = r
        rects.append((x * 16, y * 16, w * 16, h * 16))
        for yy in range(y, y + h):
            for xx in range(x, x + w): work[yy][xx] = False
    best = (rects[0][2] * rects[0][3] // 256, rects[0]) if rects else (0, None)
    free_cells = [(cx * 16, cy * 16) for cy in range(R) for cx in range(C) if cell[cy][cx]]
    tex_free = sum(grid[y][320:].count(0) for y in range(H))
    return dict(free=free_units * 2, texture_area_free=tex_free * 2, largest=best[1], largest_bytes=best[0] * 512,
                free_rects=rects,
                free_cells=len(free_cells), grid=grid)


def vram_unowned_nonzero(vram, grid):
    """KB of 16x16 cells that nobody owns but hold non-zero pixels (stale data or an unknown user)."""
    n = 0
    for cy in range(32):
        for cx in range(64):
            if any(grid[y][cx * 16:cx * 16 + 16].count(0) != 16 for y in range(cy * 16, cy * 16 + 16)): continue
            if any(vram[(y * 1024 + cx * 16) * 2:(y * 1024 + cx * 16 + 16) * 2].strip(b'\0') for y in range(cy * 16, cy * 16 + 16)):
                n += 1
    return n * 512


# ---------------------------------------------------------------------------- fixed buffers
def fixed_buffers(r, screen):
    out = []
    pt = r.i32(r.sym('PARTNER_ENTITY'))
    p, name = model_file(pt) if 0 <= pt < 180 else (None, '?')
    out.append(('PARTNER_MODEL_BUFFER', f'{name}.MMD ({digi_name(pt)})', mmd_size(pt) if p else 0, CAP['PARTNER_MODEL_BUFFER']))
    out.append(('TAMER_MODEL_BUFFER', 'BOYS.MMD', mmd_size(0), CAP['TAMER_MODEL_BUFFER']))
    mh = r.sym('MAPHEAD_SCRIPT_BUFFER')
    # GCC: whole sectors (mod 0004), 0x8000 since patch 0091: the distance to the next symbol is the buffer
    cap = CAP['MAPHEAD_SCRIPT_BUFFER'] if r.s.build == 'orig' else min(a for a in r.s.t.values() if a > mh) - mh
    d = r.b(mh, cap); out.append(('MAPHEAD_SCRIPT_BUFFER', 'MAPHEAD.SCN', len(d.rstrip(b'\0')), cap))
    sid = r.u16(r.sym('ACTIVE_MAP_SCRIPT'))
    tbl = r.sym('SCRIPT_OFFSET_TABLE')
    if 0 < sid < 0x7FF:
        size = r.u32(tbl + 4 * sid + 4) - r.u32(tbl + 4 * sid)
        out.append(('MAP_SCRIPT_BUFFER', f'DG.SCN entry {sid}', size, CAP['MAP_SCRIPT_BUFFER']))
    font = r.i16(r.sym('CURRENT_SEQ_FONT'))
    if 'SOUND_CHUNK_COUNT' in r.s.t:
        # soundlimits build (docs/mods/sound.md § 8): fonts come from an index and the buffer is
        # SEQ_BUFFER_SIZE; the block in use is measured in RAM (offsets, then the last SEQ's end)
        if font >= 1:
            out.append(('SEQ_BUFFER', f'FAALL font {font}', seq_block_size(r.b(r.sym('SEQ_BUFFER'), SEQ_BUFFER_MOD)),
                        SEQ_BUFFER_MOD))
    elif 1 <= font <= 0x21:
        with open(os.path.join(ROOT, 'extracted/SOUND/VHB/FAALL.VHB'), 'rb') as f:
            f.seek((font - 1) * 0x27 * 0x800); w = struct.unpack('<4I', f.read(16))
        out.append(('SEQ_BUFFER', f'FAALL font {font}', w[3] - w[2], CAP['SEQ_BUFFER']))
    t = map_path(screen, 'TFS')
    if t:
        size = (os.path.getsize(t) + 0x7FF) & ~0x7FF
        if 'MOD_TFS_STATS' in r.s.t:
            # streamed background (memreclaim): header + a ring of 9-sector tile slots, never more
            # than the whole file took
            slots = max(1, min(TFS_RING_SLOTS, (size - TFS_HEADER) // TFS_SLOT))
            out.append(('GENERAL_BUFFER (TFS)', os.path.basename(t) + f' ring {slots}', TFS_HEADER + slots * TFS_SLOT,
                        TFS_HEADER + TFS_RING_SLOTS * TFS_SLOT))
        else:
            out.append(('GENERAL_BUFFER (TFS)', os.path.basename(t), size, CAP['TFS']))
    return out


SEQ_BUFFER_MOD = 0x8000            # SEQ_BUFFER_SIZE of the soundlimits build (include/dw/memmap.h)


def seq_block_size(b):
    """Bytes of the SEQ block at the start of `b`: u32 offsets[n], n SEQs ending in FF 2F 00, 4-aligned."""
    n = struct.unpack_from('<I', b, 0)[0] // 4
    if not 0 < n < 64: return 0
    last = struct.unpack_from('<I', b, 4 * (n - 1))[0]
    e = b.find(b'\xff\x2f\x00', last)
    return 0 if e < 0 else (e + 3 + 3) & ~3


# ---------------------------------------------------------------------------- live report
def measure(em, with_vram=False):
    raw = em.ram()
    r = Ram(raw, em.syms)
    scr = screen_id(r)
    h = heap_walk(r)
    npc = r.sym('NPC_MODELS')
    models = []
    for i in range(5):
        m = npc + i * MC
        if r.u32(m) and r.u32(m + 12):
            t = r.i16(m + 0x18); models.append(dict(slot=i, type=t, name=digi_name(t), vram_slot=r.i16(m + 0x16)))
    npc_taken = [k for k in range(5) if r.u32(r.sym('NPC_MODEL_TAKEN') + 4 * k)]
    efe_taken = [k for k in range(16) if r.u32(r.sym('UNKNOWN_MODEL_TAKEN') + 4 * k)]
    efe_base, efe_ptr = r.u32(r.sym('EFE_HEAP_BASE')), r.u32(r.sym('EFE_HEAP_POINTER'))
    battle = bool(efe_taken) or (0x80010000 <= efe_base < 0x80090000 and efe_ptr > efe_base)
    rects, have_map = vram_owners(scr, npc_taken, efe_taken, battle)
    v = vram_report(rects)
    spu = spu_banks(r)
    res = dict(build=em.build, screen=scr, map=MAPS.get(scr, {}).get('file'), name=MAPS.get(scr, {}).get('map_name'),
               hour=r.i16(r.sym('HOUR')), minute=r.i16(r.sym('MINUTE')),
               tamer_state=r.u8(r.sym('TAMER_STATE')), script_paused=r.i32(r.sym('IS_SCRIPT_PAUSED')),
               heap=h, models=models, npc_slots=npc_taken, efe_slots=efe_taken,
               efe_heap=(efe_ptr - efe_base) if battle else 0, efe_base=efe_base, battle=battle,
               stack=stack_highwater(r), vram=v, vram_rects=rects, vram_map_known=have_map,
               spu=spu, buffers=fixed_buffers(r, scr),
               spu_alloc='SPU_BANK_SIZE' in r.s.t,
               spu_fails=r.i32(r.sym('SPU_ALLOC_FAILS')) if 'SPU_ALLOC_FAILS' in r.s.t else 0)
    if with_vram:
        res['vram_unowned_nonzero'] = vram_unowned_nonzero(em.vram(), v['grid'])
    return res


def kb(n): return f'{n / 1024:.1f} KB'


def print_report(m):
    h = m['heap']
    print(f"build {m['build']}  screen {m['screen']} {m['map']} ({m['name']})  {m['hour']:02d}:{m['minute']:02d}"
          f"  tamer_state {m['tamer_state']} script_paused {m['script_paused']}" + ('  [BATTLE]' if m['battle'] else ''))
    print(f"\nRAM heap {h['base']:#x}-{h['end']:#x}: total {kb(h['total'])}, used {kb(h['used'])}, "
          f"free {kb(h['free'])} in {h['free_blocks']} block(s), largest {kb(h['largest'])}"
          + (f"  CORRUPT at {h['corrupt']:#x}" if h['corrupt'] else ''))
    for b in h['blocks']:
        print(f"  {b['addr']:#010x} {b['size']:#8x} {kb(b['size']):>9}  {b['owner']}")
    print('  by kind: ' + ', '.join(f'{k} {kb(v)}' for k, v in sorted(h['by_kind'].items())))
    s = m['stack']
    print(f"stack: {kb(s['used'])} of {kb(s['size'])} touched (deepest {s['deepest']:#x}; cumulative since boot/state history)")
    print('\nfixed buffers:')
    for name, what, used, cap in m['buffers']:
        print(f"  {name:24} {what:28} {used:#8x} / {cap:#8x}  {100 * used / cap:5.1f}%  margin {kb(cap - used)}")
    if m['battle']:
        print(f"  {'EFE heap (battle)':24} {'from ' + hex(m['efe_base']):28} {m['efe_heap']:#8x} / {CAP['EFE_HEAP']:#8x}"
              f"  {100 * m['efe_heap'] / CAP['EFE_HEAP']:5.1f}%")
    v = m['vram']
    print(f"\nVRAM: free {kb(v['free'])} of 1024 KB (texture area x>=320: {kb(v['texture_area_free'])}), "
          f"{v['free_cells']} free 16x16 cells; largest free rectangle {v['largest']} ({kb(v['largest_bytes'])})"
          + ('' if m['vram_map_known'] else '  [.MAP not extracted: map TIMs unknown]'))
    print('  free rectangles (x, y, w, h; greedy, largest first): ' + ', '.join(str(r) for r in v['free_rects']))
    for name, x, y, w, hh in m['vram_rects']:
        print(f"  ({x:4},{y:3}) {w:4}x{hh:<3}  {name}")
    if 'vram_unowned_nonzero' in m:
        print(f"  non-zero pixels in unowned cells: {kb(m['vram_unowned_nonzero'])} (stale data or an unlisted user)")
    print('\nSPU RAM (512 KB; 4 KB libspu + reverb 18 KB reserved):')
    tot = 0
    if m.get('spu_alloc'):
        for b in m['spu']:
            print(f"  bank {b['bank']} {b['name']:9} " + (f"at {b['start']:#07x} {b['body']:#7x} bytes ({kb(b['body'])})"
                  if b['loaded'] else 'not loaded') + f"   header {b['header']:#x}/{b['header_cap']:#x}")
        gaps = spu_gaps(m['spu'])
        print('  free blocks: ' + ', '.join(f'{a:#07x} {kb(n)}' for a, n in gaps))
        print(f"  free {kb(sum(n for _, n in gaps))}, largest block {kb(max((n for _, n in gaps), default=0))}"
              f"; failed loads since boot: {m['spu_fails']}")
        return
    for b in m['spu']:
        tot += b['slot'] - b['body']
        print(f"  bank {b['bank']} {b['name']:9} slot {b['slot']:#7x}  body {b['body']:#7x}  free {kb(b['slot'] - b['body']):>9}"
              + ('' if b['loaded'] else '  (not loaded)') + f"   header {b['header']:#x}/{b['header_cap']:#x}")
    print(f"  free in the bank slots: {kb(tot)}")


# ---------------------------------------------------------------------------- static estimate
def maphead_text():
    os.makedirs(CACHE, exist_ok=True)
    out = os.path.join(CACHE, 'maphead', 'maphead.scn.txt')
    src = os.path.join(ROOT, 'extracted/SCN/MAPHEAD.SCN')
    if not os.path.exists(out) or os.path.getmtime(out) < os.path.getmtime(src):
        subprocess.run([sys.executable, os.path.join(ROOT, 'tools/dws/bytecode/__main__.py'), 'dis', src, os.path.dirname(out)],
                       check=True, stdout=subprocess.DEVNULL)
    return open(out, encoding='utf-8').read()


def section(text, screen):
    m = re.search(rf'^sec{screen}:.*?(?=^sec\d+:|\Z)', text, re.S | re.M)
    return m.group(0) if m else None


def _atoms(cond):
    out = []
    for part in [p.strip() for p in cond.split(',')]:
        o = None
        if part.startswith('and '): o, part = 'and', part[4:]
        elif part.startswith('or '): o, part = 'or', part[3:]
        out.append((o, part))
    return out


def _eval_cond(cond, hour_var, hour, known=None):
    """Kleene left-to-right evaluation of `a, and b, or c`; None = unknown. `known` maps
    atoms ('trigger 232') to the value this path already assumed for them."""
    val = None
    for o, part in _atoms(cond):
        m = re.fullmatch(r'p(\d+)\s*(==|!=|>=|<=|>|<)\s*(-?\d+)', part)
        neg = part.startswith('not ')
        atom = part[4:] if neg else part
        if m and hour is not None and hour_var is not None and int(m.group(1)) == hour_var:
            x = eval(f'{hour} {m.group(2)} {m.group(3)}')
        elif m and known and f'p{m.group(1)}' in known:      # a pstat this path set (SET/ADD_TO_PSTAT)
            x = eval(f'{known["p" + m.group(1)]} {m.group(2)} {m.group(3)}')
        elif known and atom in known:
            x = known[atom] != neg
        else:
            x = None
        if o is None: val = x
        elif o == 'and': val = False if (val is False or x is False) else (True if (val and x) else None)
        else: val = True if (val is True or x is True) else (False if (val is False and x is False) else None)
    return val


def _assume(cond, known, value):
    """What taking a branch tells about the atoms: a true conjunction makes every atom
    true; a false single atom is false."""
    at = _atoms(cond); k = dict(known)
    if value and all(o in (None, 'and') for o, _ in at):
        for _, part in at:
            if part.startswith('not '): k[part[4:]] = False
            else: k[part] = True
    elif not value and len(at) == 1:
        part = at[0][1]
        if part.startswith('not '): k[part[4:]] = True
        else: k[part] = False
    return k


_parsed = {}


def _parse(text):
    """Whole MAPHEAD disassembly -> (instructions, labels); sections may jump into shared code."""
    key = hash(text)
    if key not in _parsed:
        ins, labels = [], {}
        for line in text.splitlines():
            if line.lstrip().startswith(('"', '.', ';')): continue
            m = re.match(r'^([A-Za-z_][\w.]*):', line)          # L12, sec204, and the labels tools/dws writes (dws_presence_204_7)
            if m: labels[m.group(1)] = len(ins); continue
            code = line.split(';')[0].strip()
            if code: ins.append(code)
        _parsed[key] = (ins, labels)
    return _parsed[key]


def setup_paths(text, screen, hour=None):
    """Every distinct path through MAPHEAD section `screen`: list of (loads, sets), sets = [(type, slot)]."""
    ins, labels = _parse(text)
    if f'sec{screen}' not in labels: raise KeyError(f'no MAPHEAD section for screen {screen}')
    start = labels[f'sec{screen}']
    paths, todo, n, seen = [], [(start, (), (), None, {})], 0, set()
    while todo and n < 20000:
        n += 1
        pc, loads, sets, hv, known = todo.pop()
        hv = hv or 107                      # STORE_DATE p105 -> p107 = hour (all of MAPHEAD uses p105)
        key = (pc, frozenset(loads), tuple(sorted(sets)), tuple(sorted(known.items())))
        if key in seen: continue
        seen.add(key); steps = 0
        while pc < len(ins) and steps < 2000:
            steps += 1
            c = ins[pc]; w = c.split(None, 1); op = w[0]; arg = w[1] if len(w) > 1 else ''
            if op == 'STORE_DATE':
                hv = int(arg.strip().lstrip('p')) + 2
            elif op in ('SET_PSTAT', 'ADD_TO_PSTAT'):
                a = [x.strip() for x in arg.split(',')]
                if re.fullmatch(r'p\d+', a[0]) and re.fullmatch(r'-?\d+', a[1]) and a[0] != f'p{hv}':
                    if op == 'SET_PSTAT': known = dict(known, **{a[0]: int(a[1])})
                    elif a[0] in known: known = dict(known, **{a[0]: known[a[0]] + int(a[1])})
            elif op == 'LOAD_DIGIMON':
                loads += (int(arg.split(',')[0]),)
            elif op == 'SET_DIGIMON':
                a = [int(x) for x in arg.split(',')]; sets += ((a[0], a[1]),)
            elif op == 'JUMP_TO':
                pc = labels[arg.strip()]; continue
            elif op == 'IF':
                cond, _, lab = arg.rpartition(', else ')
                v = _eval_cond(cond, hv, hour, known)
                if v is None:
                    todo.append((labels[lab.strip()], loads, sets, hv, _assume(cond, known, False)))
                    known = _assume(cond, known, True)
                elif v is False: pc = labels[lab.strip()]; continue
            elif op == 'END_SECTION':
                break
            pc += 1
        paths.append((tuple(dict.fromkeys(loads)), tuple(sorted(sets))))
    return sorted(set(paths))


@lru_cache(None)
def npc_twin_types(archive):
    """Field model identities present in this target archive; legacy builds keep theirs."""
    _, rows, _ = archive_models(archive)
    return {s['_npc_original']: t for t, s in _species.load_content().items()
            if '_npc_original' in s and t < len(rows) and rows[t]['modelSize']}


def path_cost(loads, sets):
    """Conservative peak for any interleaving of model loads and placements.

    A load may happen after earlier SET_DIGIMON allocations. Charge all other
    resident models/instances when bounding its temporary TIM or full MMD.
    Field staging allocates only compact bytes; larger/non-field models still
    need the whole sector-rounded allocation before compaction.
    """
    if MODEL_ARCHIVE and _species:
        twins = npc_twin_types(MODEL_ARCHIVE)
        loads = tuple(twins.get(t, t) for t in loads)
        sets = tuple((twins.get(t, t), slot) for t, slot in sets)
    order = list(dict.fromkeys(list(loads) + [t for t, _ in sets]))
    mod = sum(model_block_resident(t) for t in order)
    inst = sum(instance_blocks(t) for t, _ in sets)
    total = mod + inst
    peak = total
    for t in order:
        before = total - model_block_resident(t) - sum(instance_blocks(x) for x, _ in sets if x == t)
        peak = max(peak, before + blk(TEMP_TIM))
        if not staged(t): peak = max(peak, before + model_block(t))
    return dict(types=sorted(order), models=mod, instances=inst, total=total, peak=peak)


def sweep_rows(path=CSV_OUT):
    return list(csv.DictReader(open(path))) if os.path.exists(path) else []


HEAP_MAP_DEFAULT = os.path.join(ROOT, 'build/decomp-int/build/us/psx/gcc/SLUS_010.32.elf.map')
HEAP_MAP = HEAP_MAP_DEFAULT


def configure(env=None, partner_mmd_max=None, heap_map=None):
    """The settings of the checks, from an environment (default os.environ, as the command line) or the keywords (a
    caller in the same process): the partner model buffer (PARTNER_MMD_MAX, default the original 0x18800) and the ELF
    map heap_total_now() reads (DW_HEAP_MAP, else build/decomp-int's). Both are checks only: nothing a build writes
    depends on them."""
    global HEAP_MAP, MODEL_ARCHIVE, TARGET_FACTS, NPC_STAGE_MAX
    e = os.environ if env is None else env
    CAP['PARTNER_MODEL_BUFFER'] = partner_mmd_max if partner_mmd_max is not None else \
        int(e.get('PARTNER_MMD_MAX') or '0x18800', 0)
    HEAP_MAP = heap_map or e.get('DW_HEAP_MAP') or HEAP_MAP_DEFAULT
    MODEL_ARCHIVE = e.get('DW_MODEL_ARCHIVE') or None
    path = e.get('DW_EXE_FACTS')
    TARGET_FACTS = json.load(open(path)) if path else {}
    NPC_STAGE_MAX = TARGET_FACTS.get('npc_stage_max') or 0
    npc_twin_types.cache_clear()
    model_data.cache_clear()
    model_block.cache_clear()
    if 'npcanims' in sys.modules:
        sys.modules['npcanims'].trimmed_size.cache_clear()


configure()


def heap_total_now(map_path=None):
    """The malloc3 heap of the executable built now, from its ELF map (map_path, else HEAP_MAP: DW_HEAP_MAP, else
    build/decomp-int's): from (main_BSS_END & ~15) + 16 (initializeHeap) to the stack's bottom (_stack_addr -
    _stack_size KB); None without a map."""
    try: text = open(map_path or HEAP_MAP).read()
    except OSError: return TARGET_FACTS.get('heap_total')
    def word(name):
        m = re.search(r'^\s+0x[0-9a-f]+\s+' + name + r' = \.\n\s+0x[0-9a-f]+\s+0x4 LONG (0x[0-9a-f]+)', text, re.M)
        return int(m.group(1), 16) if m else None
    end, stack, size = word('_end'), word('_stack_addr'), word('_stack_size')
    if None in (end, stack, size): return None
    return ((stack - (size << 10)) & ~0xF) - ((end & ~0xF) + 0x10)


def screen_budget(screen, hour=None, maphead_text=None, sweep_csv=CSV_OUT):
    """Static check for a quest/map change. Returns a dict:
      need      bytes of heap the worst path of the screen's MAPHEAD setup takes
                (NPC MMDs sector-rounded + posData/momentum per placed Digimon + 8-byte headers),
      peak      the most the heap holds at once during the setup (a model's 0x4800 temporary
                TIM is malloc3'd and freed before its MMD, so it only matters before the last load),
      available heap the sweep found for NPC data on that screen (free + what the measured
                models/posData took) — None if the screen was not measured,
      margin    available - peak (negative: malloc3 fails and the loading screen hangs),
      paths     every setup path with its cost; worst is paths[0].
    hour: evaluate the section's time conditions (p107 after STORE_DATE) for that hour;
    None: every hour of the day, each on its own (a day NPC and a night NPC never load together, so their
    models are not summed). maphead_text: an edited MAPHEAD disassembly (bytecode dis)."""
    text = maphead_text or maphead_text_cached()
    paths = setup_paths(text, screen, hour) if hour is not None else \
        sorted({p for h in range(24) for p in setup_paths(text, screen, h)})
    costs = sorted((dict(path_cost(l, s), loads=l, sets=s) for l, s in paths), key=lambda c: -c['peak'])
    worst = costs[0]
    rows = [r for r in sweep_rows(sweep_csv) if r['screen'] == str(screen) and r['ok'] == '1']
    if rows:
        # heap left for this screen's NPCs = free + what its measured NPC data took; the minimum over hours
        avail = min(int(r['heap_free']) + int(r['models_bytes']) + int(r['posdata_bytes']) for r in rows)
        # the sweep's executable may have had a bigger heap than the one built now (main's BSS grows with the patches):
        # the difference comes off every screen
        now = heap_total_now()
        if now: avail -= max(0, min(int(r['heap_total']) for r in rows) - now)
        measured = True
    else:
        avail, measured = HEAP_FOR_NPCS, False
        now = heap_total_now()
        if now and HEAP_FOR_NPCS == 0x30388: avail -= max(0, 0x30390 - now)   # (the original's heap: tier 2 sets its own)
    return dict(measured=measured, screen=screen, hour=hour, need=worst['total'], peak=worst['peak'], available=avail,
                margin=avail - worst['peak'],
                worst=[digi_name(t) for t in worst['types']], paths=costs)


_mh = None


def maphead_text_cached():
    global _mh
    if _mh is None: _mh = maphead_text()
    return _mh


# ---------------------------------------------------------------------------- sweep
COLUMNS = ['screen', 'map', 'name', 'hour', 'ok', 'note', 'heap_total', 'heap_used', 'heap_free', 'heap_largest',
           'free_blocks', 'models', 'models_bytes', 'posdata_bytes', 'other_bytes', 'npc_vram_slots',
           'vram_map_kb', 'vram_free_kb', 'vram_tex_free_kb', 'vram_largest_free', 'spu_free_kb', 'spu_esall_kb',
           'tfs_kb', 'script_bytes', 'static_need', 'stack_used']


def row_of(m, screen, hour, ok, note):
    h = m['heap']
    k = h['by_kind']
    lr = m['vram']['largest']
    tims = map_tims(screen) or []
    buf = {b[0]: b[2] for b in m['buffers']}
    try:
        st = path_cost_live(screen, hour)
    except Exception:
        st = ''
    return dict(screen=screen, map=MAPS.get(screen, {}).get('file', ''), name=MAPS.get(screen, {}).get('map_name', ''),
                hour=hour, ok=ok, note=note, heap_total=h['total'], heap_used=h['used'], heap_free=h['free'],
                heap_largest=h['largest'], free_blocks=h['free_blocks'],
                models=' '.join(x['name'].replace(' ', '_') for x in m['models']),
                models_bytes=k.get('model', 0), posdata_bytes=k.get('posdata', 0),
                other_bytes=h['used'] - k.get('model', 0) - k.get('posdata', 0),
                npc_vram_slots=len(m['npc_slots']),
                vram_map_kb=round(sum(w * hh * 2 for n, x, y, w, hh in tims if 'CLUT' not in n) / 1024, 1),
                vram_free_kb=round(m['vram']['free'] / 1024, 1), vram_tex_free_kb=round(m['vram']['texture_area_free'] / 1024, 1),
                vram_largest_free=f'{lr[2]}x{lr[3]}@{lr[0]},{lr[1]}' if lr else '',
                spu_free_kb=round((sum(n for _, n in spu_gaps(m['spu'])) if m.get('spu_alloc') else
                                   sum(b['slot'] - b['body'] for b in m['spu'])) / 1024, 1),
                spu_esall_kb=round(m['spu'][8]['body'] / 1024, 1),
                tfs_kb=round(buf.get('GENERAL_BUFFER (TFS)', 0) / 1024, 1), script_bytes=buf.get('MAP_SCRIPT_BUFFER', ''),
                static_need=st, stack_used=m['stack']['used'])


def path_cost_live(screen, hour):
    return max(path_cost(l, s)['total'] for l, s in setup_paths(maphead_text_cached(), screen, hour))


def time_dependent(screen):
    """Whether the screen's setup (shared tails included) differs by hour."""
    t = maphead_text_cached()
    try:
        return len({tuple(setup_paths(t, screen, h)) for h in (3, 9, 12, 15, 20)}) > 1
    except KeyError:
        return False


def warp(em, screen, hour, timeout=25):
    em.ram()
    s = em.syms
    em.poke(s['HOUR'], struct.pack('<hh', hour, 0))
    em.poke(s['TAMER_SUB_STATE'], b'\0')
    em.poke(s['TARGET_MAP'], struct.pack('<h', screen) if dwsyms.wide_ids(em.build) else bytes([screen]))
    em.poke(s['CURRENT_EXIT'], b'\0')
    em.poke(s['TAMER_STATE'], b'\5\0')
    t0 = time.time(); seen5 = False; last = None
    while time.time() - t0 < timeout:
        time.sleep(0.5)
        r = Ram(em.ram(), s)
        ts = r.u8(s['TAMER_STATE'])
        if ts == 5: seen5 = True
        if screen_id(r) == screen and ts != 5 and seen5:
            # wait for the heap to settle (NPC loads) for two polls
            free = heap_walk(r)['free']
            if last == free:
                return True, ''
            last = free
    r = Ram(em.ram(), s)
    return False, f'timeout: screen {screen_id(r)} tamer_state {r.u8(s["TAMER_STATE"])}'


def refresh_static(path=CSV_OUT):
    """Rewrites the static_need column of the sweep CSV with the current estimator."""
    rows = sweep_rows(path)
    for r in rows:
        try: r['static_need'] = path_cost_live(int(r['screen']), int(r['hour']))
        except KeyError: r['static_need'] = ''
    with open(path, 'w', newline='') as f:
        w = csv.DictWriter(f, COLUMNS); w.writeheader(); w.writerows(rows)


def parse_screens(spec):
    out = []
    for part in spec.split(','):
        if '-' in part:
            a, b = part.split('-'); out += range(int(a), int(b) + 1)
        elif part: out.append(int(part))
    return out


def sweep(args):
    em = Emu()
    state = args.state
    out = args.out
    screens = parse_screens(args.screens) if args.screens else sorted(MAPS)
    done = set()
    if os.path.exists(out) and not args.fresh:
        for r in csv.DictReader(open(out)): done.add((int(r['screen']), int(r['hour'])))
    new = not os.path.exists(out) or args.fresh
    f = open(out, 'w' if new else 'a', newline='')
    w = csv.DictWriter(f, COLUMNS)
    if new: w.writeheader()
    hours = [int(x) for x in args.hours.split(',')]
    if not args.chain: em.load(state); time.sleep(1)
    for scr in screens:
        hs = hours[:1] + [h for h in hours[1:] if time_dependent(scr)]
        for hour in hs:
            if (scr, hour) in done: continue
            if not args.chain:
                em.load(state); time.sleep(0.5)
            else:
                time.sleep(3)                       # a warp poked right after the previous one is ignored
            try:
                ok, note = warp(em, scr, hour)
                if map_path(scr) is None: note = (note + '; ' if note else '') + '.MAP not extracted: VRAM map part unknown'
                m = measure(em)
                if m['screen'] != scr: ok = False
                w.writerow(row_of(m, scr, hour, int(ok), note)); f.flush()
                print(f"{scr:3} h{hour:02d} ok={int(ok)} free {m['heap']['free']:6} largest {m['heap']['largest']:6} "
                      f"models {' '.join(x['name'] for x in m['models'])} {note}", flush=True)
            except SystemExit as e:
                print(f'{scr:3} h{hour:02d} emulator error: {e}', flush=True)
                raise
    f.close()
    refresh_static(out)


# ---------------------------------------------------------------------------- main
def main():
    global TRIMMED
    import argparse
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest='cmd', required=True)
    p = sub.add_parser('live'); p.add_argument('--json', action='store_true'); p.add_argument('--vram', action='store_true')
    p = sub.add_parser('sweep')
    p.add_argument('--state', default=os.path.join(ROOT, 'build/states/u.state'))
    p.add_argument('--out', default=CSV_OUT); p.add_argument('--screens'); p.add_argument('--hours', default='12,20')
    p.add_argument('--chain', action='store_true', help='no state reload between screens (fragmentation test)')
    p.add_argument('--fresh', action='store_true', help='overwrite the CSV instead of resuming')
    p = sub.add_parser('estimate'); p.add_argument('screen', type=int); p.add_argument('--hour', type=int)
    p.add_argument('--maphead'); p.add_argument('--trimmed', action='store_true', help='NPC models trimmed on load (memreclaim)')
    p = sub.add_parser('worst', help='static: the screens whose MAPHEAD setup needs the most heap (every path)')
    p.add_argument('--trimmed', action='store_true'); p.add_argument('-n', type=int, default=8)
    p = sub.add_parser('vram-map'); p.add_argument('screen', type=int)
    a = ap.parse_args()
    if a.cmd == 'live':
        m = measure(Emu(), with_vram=a.vram)
        if a.json:
            m['vram'] = {k: v for k, v in m['vram'].items() if k != 'grid'}
            print(json.dumps(m, indent=1, default=str))
        else:
            print_report(m)
    elif a.cmd == 'sweep':
        sweep(a)
    elif a.cmd == 'worst':
        TRIMMED = a.trimmed
        text = maphead_text_cached(); res = []
        for scr in sorted(MAPS):
            try: c = max((path_cost(l, st) for l, st in setup_paths(text, scr)), key=lambda c: c['peak'])
            except (KeyError, ValueError): continue
            res.append((c['peak'], scr, MAPS[scr]['map_name'], [digi_name(t) for t in c['types']]))
        for peak, scr, name, types in sorted(res, reverse=True)[:a.n]:
            print(f'{peak:7} B ({peak / 1024:.1f} KB)  {scr:3} {name:24} {" ".join(types)}')
    elif a.cmd == 'estimate':
        TRIMMED = a.trimmed
        r = screen_budget(a.screen, a.hour, maphead_text=open(a.maphead).read() if a.maphead else None)
        print(f"screen {a.screen} {MAPS.get(a.screen, {}).get('map_name', '')}" + (f' at {a.hour}h' if a.hour is not None else ' (any hour)'))
        print(f"  worst setup path: {', '.join(r['worst']) or 'no NPCs'}: {kb(r['need'])} "
              f"(peak while loading {kb(r['peak'])})")
        print(f"  available for NPC data ({'measured by the sweep' if r['measured'] else 'whole heap, screen not measured'}):"
              f" {kb(r['available'])}  ->  margin {kb(r['margin'])}" + ('  ** DOES NOT FIT **' if r['margin'] < 0 else ''))
        for c in r['paths'][:8]:
            print(f"    {kb(c['total']):>9}  models {', '.join(f'{digi_name(t)} {kb(model_block(t))}' for t in c['types']) or '-'};"
                  f" {len(c['sets'])} placed")
    elif a.cmd == 'vram-map':
        rects, known = vram_owners(a.screen)
        v = vram_report(rects)
        for name, x, y, w, h in rects: print(f'  ({x:4},{y:3}) {w:4}x{h:<3}  {name}')
        print(f"free {kb(v['free'])} (texture area {kb(v['texture_area_free'])}), free rectangles {v['free_rects']}"
              + ('' if known else '  [.MAP not extracted]'))


if __name__ == '__main__':
    main()
