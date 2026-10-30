#!/usr/bin/env python3
"""battlecheck.py run STATE MODE INTERP NTICKS "INPUT" OUT [SET=VAL ...]
              | battlecheck.py diff A B
Replays a battle from a save state and hashes the game state at every logic
tick, to prove that extra render passes do not change it.

'run' does, in one Lua call (so no emulated time passes in between): load
STATE (MODE 0/1/2 = 20/30/60 fps is only a label: the frame rate is a build
parameter, FPS=, so the state must come from a disc built with it; MOD_FPS_BUILD
in RAM says which), set MOD_FPS_INTERP=INTERP (plus
any extra NAME=VALUE words), install the per-tick pad input INPUT
("CROSS:3 NONE:2000", by MOD_FPS_TICKS as ticks_input.py) and an exec
breakpoint at the entry of modPresent (every loop's render: the logic of this
tick has run, every pass of the previous tick is over and put back). There it
logs, for NTICKS ticks: MOD_FPS_TICKS, GAME_STATE, the rand() seed, the
partner's and enemies' HP/MP, money and the partner's stats (off/def/speed/
brains/max HP/max MP), BATTLE_FRAME_COUNT, the partner's finisher progress,
and hashes of COMBAT_DATA, every ENTITY_TABLE entity (struct with
stats, bones without posMatrix.flg, momentum), WORLD_OBJECTS, the battle HUD
state, the result-screen counters (money, stat gains), and the EFE engine
(slot table, every loaded effect's script/data area, particle emitters,
sound channels without their SPU voice masks); each line ends with the vblank count and a hash of the
first bytes of the load area (timing, not compared by 'diff'). With the
interpreter CPU extra passes rarely fit in battle: pass MOD_FPS_TEST_TICK=8
to every run compared (20 fps too): ticks of 8 refreshes, every pass
rendered, the same emulated time per tick in every mode.
Extra words: OVL=STD (or VS, BTL) also hashes that overlay's .data/.bss
(column 'o'), minus the mod's own buffers, model data, sprite templates and
ordering tables (GsOT/GsOT_TAG arrays: render scratch) and the coord flg of
PositionData arrays (libgs cache tag);
POKE=N:SYM+OFF:VALUE writes a 16-bit VALUE right after logging tick N (e.g.
a rival's HP to 0, on the same tick in every run); SAVEAT=N:FILE and
DUMPAT=N:FILE save a state / dump RAM at tick N.
Needs EMU_ARGS="-interpreter -debugger".
'diff' compares two logs line by line (the tick counter column excluded)."""

from pathlib import Path as _DevPath
import sys as _dev_sys
_DEV_ROOT = str(next(p for p in _DevPath(__file__).resolve().parents if (p / "tools").is_dir()))
_dev_sys.path.insert(0, _DEV_ROOT)
_dev_sys.path.insert(0, str(_DevPath(_DEV_ROOT) / "tools"))
from tools.dev.lua import write_script
import subprocess, sys, os, re, time
R = _DEV_ROOT
S = os.path.dirname(os.path.abspath(__file__))
DECOMP = os.environ.get('FPS_DECOMP', R + '/build/decomp-full')
# FPS_MAP: the linker map of the executable under test (default: build/full)
MAP = os.environ.get('FPS_MAP', R + '/build/full/exe/SLUS_010.32.elf.map')


def sym(n):
    for l in open(MAP):
        m = re.match(r'\s+(0x[0-9a-f]+)\s+' + n + r'\s*$', l)
        if m:
            return int(m.group(1), 16) & 0x1fffff
    sys.exit('no ' + n)


def ovl_chunks(ov):
    # [start, len) pieces of an overlay's .data/.bss, from the linker map
    L = open(MAP).read().splitlines()
    on, out = False, []
    for i, l in enumerate(L):
        if re.match(r'^\.%s\s' % ov, l):
            on = True
            continue
        if on and re.match(r'^\.\w+\s+0x', l):
            break
        if not on:
            continue
        m = re.match(r'^ \.(?:s?data|s?bss)\.(\w+)\s*$', l)
        if m:
            a, n = L[i + 1].split()[:2]
            out.append((int(a, 16), int(n, 16), m.group(1)))
            continue
        m = re.match(r'^ \.(?:s?data|s?bss)\.(\w+)\s+(0x\w+)\s+(0x\w+)', l)
        if m:
            out.append((int(m.group(2), 16), int(m.group(3), 16), m.group(1)))
    skip = re.compile(r'_MOD_|TMD_BUFFER|OT_TAGS|ORDERING_TABLE|_SPRITE$|D_8007AF88|D_8007AFAC|D_80070FB4|D_80070FD8')
    # ordering tables (GsOT headers and GsOT_TAG arrays): render scratch that
    # points into the buffer of the last pass
    ots = set()
    import glob
    for f in glob.glob(DECOMP + '/include/dw/*.h') + glob.glob(DECOMP + '/src/*/*_bss_us.c'):
        ots.update(re.findall(r'\bGsOT(?:_TAG)?\s+(\w+)\s*\[', open(f).read()))
    # PositionData arrays (0x88 bytes each): not the coord's flg, libgs's
    # per-call cache tag (as for the entities)
    pds = set()
    for f in glob.glob(DECOMP + '/include/dw/*.h'):
        pds.update(re.findall(r'\bPositionData(?:Raw)?\s+(\w+)\s*\[', open(f).read()))
    res = []
    for a, n, name in sorted(out):
        if n <= 0 or skip.search(name) or name in ots:
            continue
        a &= 0x1fffff
        if name in pds:
            for k in range(0, n, 0x88):
                res += [(a + k, 0x10), (a + k + 0x14, min(0x88, n - k) - 0x14)]
        else:
            res.append((a, n))
    return res


def lua(code):
    p = write_script('fps', 'battle-check', code)
    return subprocess.run([R + '/tools/dev/emulator.py', 'lua', 'return dofile("%s")' % p],
                          capture_output=True, text=True, cwd=R).stdout.strip()


if sys.argv[1] == 'diff':
    # the tick counter and the trailing vblank count / load area hash (timing,
    # not game state) are not compared
    def rows(f):
        return [' '.join(w for w in l.split(' ')[1:] if not (w[:1] in 'vL' and len(w) > 1 and w[1:2].isalnum() and w[0] + w[1:] == w and (w[0] == 'L' or w[1:].isdigit())))
                for l in open(f).read().splitlines()]
    a = rows(sys.argv[2])
    b = rows(sys.argv[3])
    n = min(len(a), len(b))
    bad = [i for i in range(n) if a[i] != b[i]]
    print('%d / %d ticks, %d differ' % (n, max(len(a), len(b)), len(bad)))
    if bad:
        # which columns (by their letter, or position) differ how often
        cols = {}
        for i in bad:
            for k, (x, y) in enumerate(zip(a[i].split(' '), b[i].split(' '))):
                if x != y:
                    key = x[0] if x[:1].isalpha() and x[1:2] != ':' else str(k)
                    cols[key] = cols.get(key, 0) + 1
        print('columns: ' + ', '.join('%s %d' % kv for kv in sorted(cols.items())))
    for i in bad[:5]:
        print('tick %d\n  A %s\n  B %s' % (i, a[i], b[i]))
    sys.exit(1 if bad or len(a) != len(b) else 0)

state, mode, interp, nticks, inp, out = sys.argv[2:8]
sets = {'MOD_FPS_INTERP': int(interp)}
saveat, saveto = -1, ''
ovl = []
pokes = []
dumpat, dumpto = -1, ''
for kv in sys.argv[8:]:
    k, v = kv.split('=')
    if k == 'DUMPAT':
        n, dumpto = v.split(':')
        dumpat, dumpto = int(n), os.path.abspath(dumpto)
        continue
    if k == 'OVL':
        ovl = ovl_chunks(v)
        continue
    if k == 'POKE':
        n, a, val = v.split(':')
        base, _, off = a.partition('+')
        pokes.append((int(n), sym(base) + (int(off, 0) if off else 0), int(val, 0) & 0xffff))
        continue
    if k == 'SAVEAT':
        n, saveto = v.split(':')
        saveat, saveto = int(n), os.path.abspath(saveto)
        continue
    sets[k] = int(v)
segs = []
for tok in inp.split():
    b, n = tok.split(':')
    segs.append(([x for x in b.split('+') if x != 'NONE'], int(n)))
tbl = '{' + ','.join('{%d,{%s}}' % (n, ','.join('PCSX.CONSTS.PAD.BUTTON.' + x for x in bs)) for bs, n in segs) + '}'
setcode = '\n'.join('  w32s(m, %d, %d)' % (sym(k), v) for k, v in sets.items())
code = r'''
local m = PCSX.getMemPtr()
local function w32(a) return m[a] + m[a+1]*256 + m[a+2]*65536 + m[a+3]*16777216 end
local function s16(a) local v = m[a] + m[a+1]*256; if v >= 32768 then v = v - 65536 end; return v end
function w32s(mm, a, v) mm[a] = v %% 256; mm[a+1] = math.floor(v / 256) %% 256; mm[a+2] = math.floor(v / 65536) %% 256; mm[a+3] = math.floor(v / 16777216) %% 256 end
local function hash(h, a, len, skip)
  for i = 0, len - 1 do
    if skip == nil or (i %% 0x88) < 0x10 or (i %% 0x88) >= 0x14 then h = (h * 33 + m[a + i]) %% 2147483647 end
  end
  return h
end
local function ram(p) if p >= 0x80000000 and p < 0x80200000 then return p - 0x80000000 end return nil end
PCSX.pauseEmulator()
-- listeners of a previous run
if BC_L ~= nil then BC_L:remove(); BC_L = nil end
if BC_BP ~= nil then BC_BP:remove(); BC_BP = nil end
local f = Support.File.open('%(state)s', 'READ')
PCSX.loadSaveState(f)
f:close()
m = PCSX.getMemPtr()
BC_SET = false
-- the state is applied when emulation resumes: set the variables at the
-- first vblank after that, and log from then on
function bc_apply()
  m = PCSX.getMemPtr()
%(setcode)s
  BC_SET = true
end
BC_LOG = {}; BC_N = 0; BC_MAX = %(nticks)d; BC_SAVEAT = %(saveat)d; BC_DUMPAT = %(dumpat)d
BC_SEGS = %(tbl)s; BC_START = nil; BC_HELD = {}
BC_OVL = %(ovl)s; BC_POKES = %(pokes)s
local pad = PCSX.SIO0.slots[1].pads[1]
BC_VBL = 0
local listener
listener = PCSX.Events.createEventListener('GPU::Vsync', function()
  if listener == nil then return end
  BC_VBL = BC_VBL + 1
  if not BC_SET then bc_apply() end
  local t = w32(%(ticks)d)
  if BC_START == nil then BC_START = t end
  local k = t - BC_START; local want = nil
  for _, s in ipairs(BC_SEGS) do
    if k < s[1] then want = s[2]; break end
    k = k - s[1]
  end
  for b, _ in pairs(BC_HELD) do pad.clearOverride(b) end
  BC_HELD = {}
  if want == nil then return end
  for _, b in ipairs(want) do pad.setOverride(b); BC_HELD[b] = true end
end)
BC_L = listener
local bp
bp = PCSX.addBreakpoint(0x%(present)x, 'Exec', 4, 'battlecheck', function()
  if bp == nil then return end
  if BC_N >= BC_MAX or not BC_SET then return end
  local gs = m[%(gstate)d]
  local ents = {}
  for e = 0, 9 do
    local p = ram(w32(%(etable)d + e * 4))
    if p == nil then ents[#ents + 1] = '-' else
      local typ = w32(p)
      local bones = w32(%(ddata)d + typ * 52 + 20)
      local pd = ram(w32(p + 4)); local mo = ram(w32(p + 12))
      local h = hash(7, p, 0x58)
      if pd ~= nil and bones < 64 then h = hash(h, pd, bones * 0x88, true) end
      if mo ~= nil and bones < 64 then h = hash(h, mo, bones * 82) end
      ents[#ents + 1] = string.format('%%x', h)
    end
  end
  local hp = {}
  local pe = %(partner)d
  hp[1] = s16(pe + 0x4c) .. '/' .. s16(pe + 0x4e)
  local ec = s16(%(ecount)d)
  if ec > 3 or ec < 0 then ec = 0 end
  local cb = %(combat)d
  local ids = cb + %(idsoff)d
  for i = 1, ec do
    local ep = ram(w32(%(etable)d + m[ids + i] * 4))
    if ep ~= nil then hp[#hp + 1] = s16(ep + 0x4c) .. '/' .. s16(ep + 0x4e) end
  end
  -- COMBAT_DATA without the enemy HP bar sprites' screen position
  -- (player.unk1[i] + 4..7): a draw cache BTL_renderEnemyHPBars writes right
  -- before drawing, from the entity's position, which the first pass of an
  -- interpolated tick already sees interpolated; nothing else reads it
  local hc = 5
  for i = 0, 0x683 do
    local o = i - 0x5a0
    if o < 0 or o >= 0xa0 or (o %% 0x28) < 4 or (o %% 0x28) > 7 then hc = (hc * 33 + m[cb + i]) %% 2147483647 end
  end
  local hw = hash(5, %(wobj)d, 129 * 12)
  local hu = hash(5, %(money)d, 4)
  hu = hash(hu, %(gains)d, 12); hu = hash(hu, %(icstats)d, 48); hu = hash(hu, %(uibox)d, 6 * 0x24); hu = hash(hu, %(flee)d, 96)
  local hb = hash(5, %(fready)d, 1); hb = hash(hb, %(ffull)d, 1); hb = hash(hb, %(tfin)d, 4); hb = hash(hb, %(shout)d, 12)
  hb = hash(hb, %(pieces)d, 3100)
  local he = 5
  local slots = ram(w32(%(efeptr)d))
  local efe = false  -- the EFE engine object (0x500) exists: its memory is live
  for i = 0, 127 do
    if m[%(wobj)d + i * 12] + m[%(wobj)d + i * 12 + 1] * 256 == 0x500 then efe = true end
  end
  if gs ~= 0 and slots ~= nil and efe then
    he = hash(he, slots, 16 * 0x28)
    for i = 0, 15 do
      local d = ram(w32(slots + i * 0x28 + 8))
      if d ~= nil then
        local tmd = w32(d - 0x34 + 20)
        if tmd > 0 and tmd < 0x10000 then he = hash(he, d, tmd) end
      end
    end
    he = string.format('%%x', he)
    local em = ram(w32(%(emit)d))
    if em ~= nil then he = he .. string.format('/%%x', hash(5, em, 4 * 0x1b4)) end
    -- sound channels: the effect each one plays, not the SPU voice mask
    -- playSound2 returned (which voice was free depends on timing)
    local hs = 5
    for k = 0, 9 do hs = hash(hs, %(sound)d + k * 8 + 4, 4); hs = (hs * 33 + (w32(%(sound)d + k * 8) == 4294967295 and 1 or 0)) %% 2147483647 end
    he = he .. string.format('/%%x', hs)
  else
    he = string.format('%%x', he)
  end
  local ho = 5
  for _, c in ipairs(BC_OVL) do ho = hash(ho, c[1], c[2]) end
  BC_N = BC_N + 1
  for _, p in ipairs(BC_POKES) do
    if p[1] == BC_N then m[p[2]] = p[3] %% 256; m[p[2] + 1] = math.floor(p[3] / 256) end
  end
  local st = {}
  for k = 0, 3 do st[#st + 1] = s16(pe + 0x38 + k * 2) end
  st[#st + 1] = s16(pe + 0x48); st[#st + 1] = s16(pe + 0x4a)
  BC_LOG[BC_N] = table.concat({w32(%(ticks)d), gs, string.format('%%08x', w32(0x8464)), table.concat(hp, ','),
     'm' .. w32(%(money)d) .. ':' .. table.concat(st, '/'),
     s16(%(bframe)d), s16(cb + 0x1a) .. '/' .. s16(cb + 0x18), string.format('c%%x w%%x u%%x b%%x o%%x e', hc, hw, hu, hb, ho) .. he,
     table.concat(ents, ','), 'v' .. BC_VBL .. ' L' .. string.format('%%x', hash(5, 0x10000, 256))}, ' ')
  if BC_N == BC_DUMPAT then
    local f = Support.File.open('%(dumpto)s', 'TRUNCATE')
    f:write(ffi.string(m, 0x200000))
    f:close()
  end
  if BC_N == BC_SAVEAT then
    local slice = PCSX.createSaveState()
    local f = Support.File.open('%(saveto)s', 'TRUNCATE')
    f:write(slice); f:close()
  end
  if BC_N >= BC_MAX then bp:remove(); bp = nil; BC_BP = nil end
end)
BC_BP = bp
PCSX.resumeEmulator()
return 'running'
''' % dict(ovl='{' + ','.join('{%d,%d}' % c for c in ovl) + '}',
           pokes='{' + ','.join('{%d,%d,%d}' % p for p in pokes) + '}',
           state=os.path.abspath(state), setcode=setcode, saveat=saveat, saveto=saveto, dumpat=dumpat, dumpto=dumpto, nticks=int(nticks), tbl=tbl,
           ticks=sym('MOD_FPS_TICKS'), present=sym('modPresent') | 0x80000000, gstate=sym('GAME_STATE'),
           etable=sym('ENTITY_TABLE'), ddata=sym('DIGIMON_DATA'), partner=sym('PARTNER_ENTITY'),
           ecount=sym('ENEMY_COUNT'), combat=sym('COMBAT_DATA'), idsoff=0x5a0 + 0xcc,
           wobj=sym('WORLD_OBJECTS'), money=sym('MONEY'), gains=sym('STATS_GAINS'),
           icstats=sym('INITIAL_COMBAT_STATS'), uibox=sym('UI_BOX_DATA'), flee=sym('FLEE_BUBBLE_DATA'),
           fready=sym('BTL_FINISHER_READY'), ffull=sym('BTL_FINISHER_FULL_FRAMES'),
           tfin=sym('BTL_BATTLE_TEXT_FINISHED'), shout=sym('BTL_COMMAND_SHOUT'),
           pieces=sym('BTL_BATTLE_START_TEXT_PIECES'), efeptr=sym('EFE_DATA_PTR'),
           emit=sym('EFE_PARTICLE_EMITTERS'), sound=sym('EFE_SOUND_DATA'), bframe=sym('BATTLE_FRAME_COUNT'))
print(lua(code))
while True:
    time.sleep(2)
    n = lua('return tostring(BC_N)')
    print(n, flush=True, end=' ')
    if n == str(nticks):
        break
open(out, 'w').write(lua('return table.concat(BC_LOG, "\\n")') + '\n')
print('\n' + out)
