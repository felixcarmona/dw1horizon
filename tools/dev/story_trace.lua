-- Scenario player and tracer for tools/dev/story_test.py (runs inside PCSX-Redux).
-- Start the emulator with EMU_ARGS="-interpreter -debugger": Lua breakpoints only fire there.
--
-- DT.start(S) installs the hooks and returns at once; the scenario then runs frame by frame from a
-- breakpoint on gameLoop (one hit per frame), so button presses and waits are counted in game frames,
-- never in host time. That is what makes two runs of one scenario identical.
--   S.out      file the trace is written to when the run ends
--   S.A        symbol table: name -> physical RAM address (no 0x80000000)
--   S.steps    list of steps (see DT.run_step); S.max_frames  hard limit
--   S.watch    list of {name, addr, len}: regions diffed at every instruction and every frame
--   S.trace    true: the tracer is on from the start (the step {t='trace', on=...} switches it)
-- Trace lines (one per event, fields separated by one space, see tools/dev/story_test.py for the reader):
--   I f script ip op rand hex      a script instruction is dispatched (ip = offset in the script, hex = its bytes)
--   W f name off old new           a watched byte changed (decimal off, hex bytes)
--   S f bank value | M f a0 a1     playSound / playMusic called
--   B f a0 a1                      startBattle called
--   K f name                       checkpoint (step {t='mark'}): followed by D lines
--   D name off hex                 the whole watched region at a checkpoint
--   E f reason                     end
local ffi = require('ffi')
DT = DT or {}

local function mem() return PCSX.getMemPtr() end
local function u8(a) return mem()[a % 0x200000] end
local function u16(a) local m = mem(); a = a % 0x200000; return m[a] + m[a + 1] * 256 end
local function u32(a) local m = mem(); a = a % 0x200000; return m[a] + m[a + 1] * 256 + m[a + 2] * 65536 + m[a + 3] * 16777216 end
local function hexs(a, n)
  local m = mem(); a = a % 0x200000
  local t = {}
  for i = 0, n - 1 do t[#t + 1] = string.format('%02x', m[a + i]) end
  return table.concat(t)
end
local function bytes(a, n) return ffi.string(mem() + (a % 0x200000), n) end

function DT.stop_hooks()
  if DT.bps then for _, b in ipairs(DT.bps) do pcall(function() b:remove() end) end end
  DT.bps = {}
  if DT.vsl then pcall(function() DT.vsl:remove() end); DT.vsl = nil end
  if DT.held then pcall(function() PCSX.SIO0.slots[1].pads[1].clearOverride(DT.held.btn) end); DT.held = nil end
end

local function log(line) local o = DT.out; o[#o + 1] = line end

-- ---- watched regions -------------------------------------------------------------------------
local function snapshot()
  for _, w in ipairs(DT.S.watch) do w.snap = bytes(w.addr, w.len) end
end
local function diff()
  for _, w in ipairs(DT.S.watch) do
    local now = bytes(w.addr, w.len)
    if now ~= w.snap then
      local old = w.snap
      for i = 1, w.len do
        local a, b = old:byte(i), now:byte(i)
        if a ~= b then log(string.format('W %d %s %d %02x %02x', DT.frame, w.name, i - 1, a, b)); DT.nw = (DT.nw or 0) + 1 end
      end
      w.snap = now
    end
  end
end

-- ---- hooks -------------------------------------------------------------------------------------
local VARLEN = { [0x10] = true, [0x1A] = true, [0x18] = true, [0x19] = true, [0x6B] = true, [0x93] = true }
local function on_instruction()
  if not DT.tracing then return end
  local A = DT.S.A
  local r = PCSX.getRegisters()
  local op = r.GPR.n.a0 % 256
  local sp = u32(A.SCRIPT_POINTER); local base = u32(A.ACTIVE_SCRIPT)
  local ip = (sp - 1 - base) % 0x100000000
  local script = (base == u32(A.MAPHEAD_SCRIPT_PTR)) and 0 or u16(A.ACTIVE_MAP_SCRIPT)
  diff()
  if op == 0x24 and DT.S.pin then      -- STORE_RANDOM (optional, tools/dws/testing/sweep.py): the three generators are set from the instruction count, so that the value does not depend on how many
    DT.nrand = (DT.nrand or 0) + 1                      -- the k-th STORE_RANDOM of the run (not the instruction count: a moved code has more or fewer JUMP_TO, and the roll must not change with them)
    local k = DT.nrand * 2654435761          -- draws the entities' AI made since the call (one a frame or so: it moves with the frame phase, and the branch after the draw with it)
    local P = DT.S.pin
    DT.poke32(P.bios, k + 1); DT.poke32(P.v1, k * 3 + 7); DT.poke32(P.v2, k * 5 + 11)
  end
  local n = VARLEN[op] and 300 or 24
  log(string.format('I %d %d %d %02x %d %s', DT.frame, script, ip, op, DT.rand, hexs(sp - 1, n)))
  DT.ins = (DT.ins or 0) + 1
  if DT.S.max_ins and DT.ins >= DT.S.max_ins then DT.finish('ilimit') end   -- optional cap (tools/dws/testing/sweep.py): a deterministic cut
end

local function tick()
  DT.frame = DT.frame + 1
  if DT.tracing then diff() end
  if DT.tracing and DT.S.idle_frames and (DT.ins or 0) > 0 then   -- optional (tools/dws/testing/sweep.py): no event for N frames after the first instruction
    -- activity = a script instruction or a change of a watched byte; sounds and music do not count (the partner's idle animation
    -- plays one now and then, which kept a finished section from ever going idle: cases 0:1220..0:1230 ran to the 1500-frame cap)
    local act = (DT.ins or 0) * 1000003 + (DT.nw or 0)
    if act ~= DT.lastn then DT.lastn = act; DT.idle = 0
    else
      DT.idle = (DT.idle or 0) + 1
      if DT.idle >= DT.S.idle_frames then
        log(string.format('K %d final', DT.frame))
        for _, w in ipairs(DT.S.watch) do if w.digest then log(string.format('D %s %s', w.name, hexs(w.addr, w.len))) end end
        return DT.finish('idle')
      end
    end
  end
  DT.run_steps()
  if DT.S.steplog and DT.pc ~= DT.lastpc then          -- optional (tools/dws/testing/branches.py debugging): the frame at which each step starts, in a file of its own
    DT.lastpc = DT.pc; DT.sl = DT.sl or {}
    DT.sl[#DT.sl + 1] = string.format('%d %d', DT.frame, DT.pc)
  end
end

-- after the end of the fight (the results and level-up screens) the battle code waits for a button: CROSS is pressed for 4 frames every 40, counted on the vblank.
-- The listener lives only from here to the end of the battle (a Vsync listener held for hours overflowed the Lua stack, tools/emu-handlers.lua).
function DT.start_results(B)
  DT.bend = true; DT.vs = 0
  if DT.vsl then return end
  DT.vsl = PCSX.Events.createEventListener('GPU::Vsync', function()
    local p = PCSX.SIO0.slots[1].pads[1]; local b = PCSX.CONSTS.PAD.BUTTON.CROSS
    if u8(B.game_state) == 0 then p.clearOverride(b); DT.bend = nil; local l = DT.vsl; DT.vsl = nil; pcall(function() l:remove() end); return end
    DT.frame = DT.frame + 1; DT.vs = DT.vs + 1
    if DT.vs % 40 == 1 then p.setOverride(b) elseif DT.vs % 40 == 5 then p.clearOverride(b) end
  end)
end

function DT.install(S)
  DT.bps = {}
  local A = S.A
  local function hook(addr, name, fn)
    DT.bps[#DT.bps + 1] = PCSX.addBreakpoint(addr, 'Exec', 4, name, function()
      local ok, err = pcall(fn)
      if not ok then log('X ' .. tostring(err)) end
    end)
  end
  for _, nm in ipairs({ 'scriptInstructionFBtoFF', 'scriptInstruction10to27', 'scriptInstruction28to3F',
                        'scriptInstruction46to58', 'scriptInstruction5Ato5F', 'scriptInstruction64to7E' }) do
    hook(A[nm] + 0x80000000, nm, on_instruction)
  end
  hook(A.playSound + 0x80000000, 'playSound', function()
    if DT.tracing then local r = PCSX.getRegisters(); log(string.format('S %d %d %d', DT.frame, r.GPR.n.a0, r.GPR.n.a1)) end
  end)
  hook(A.playMusic + 0x80000000, 'playMusic', function()
    if DT.tracing then local r = PCSX.getRegisters(); log(string.format('M %d %d %d', DT.frame, r.GPR.n.a0, r.GPR.n.a1)) end
  end)
  hook(A.startBattle + 0x80000000, 'startBattle', function()
    if DT.tracing then diff(); local r = PCSX.getRegisters(); log(string.format('B %d %d %d', DT.frame, r.GPR.n.a0, r.GPR.n.a1)) end
    if DT.S.battle then DT.bf = 0; DT.nb = (DT.nb or 0) + 1; for _, pk in ipairs(DT.S.battle.rng or {}) do DT.poke(pk[1], pk[2]) end end      -- the generators are set at the start of every battle; DT.nb counts the battles of the run
    if DT.S.stop_on_battle then      -- the battle itself is not traced: freeze here, the host finishes the run
      if DT.tracing then
        log(string.format('K %d final', DT.frame))
        for _, w in ipairs(DT.S.watch) do if w.digest then log(string.format('D %s %s', w.name, hexs(w.addr, w.len))) end end
      end
      DT.tracing = false; DT.pending_finish = 'battle'; PCSX.pauseEmulator()
    end
  end)
  if S.battle then      -- optional (tools/dws/testing/checkpoints.py): the battle runs for real; at a fixed battle frame the enemies' HP is set to 0 (a win) or the partner's (a defeat), so that
    local B = S.battle    -- its result is the same on every disc. {mode='win'|'lose', after=battle frames, finished=BTL_isBattleFinished (an overlay address), game_state=, partner=, combat_ptr=, enemy_count=, entity_table=, rng={{addr,hex}..}}
    hook(B.finished + 0x80000000, 'btlFinished', function()
      if u8(B.game_state) ~= 1 then return end                -- the overlay address holds other code outside a battle
      DT.frame = DT.frame + 1; DT.bf = (DT.bf or 0) + 1       -- a battle frame is a frame of the run (the host's hang watch counts them)
      if DT.bf == B.after then
        local ids = u32(B.combat_ptr) + 1644                    -- CombatData.player.entityIds (offset computed from decomp/include/dw/combat.h)
        local mode = B.mode
        if B.lose_nth then mode = (DT.nb == B.lose_nth) and 'lose' or 'win' end      -- tools/dws/testing/branches.py: only the n-th battle of the run is lost (the wild ones on the way are won)
        if mode == 'lose' then DT.poke32(B.partner + 0x4C, 0) end
        local n = u8(B.enemy_count)
        for i = 1, n do
          local e = u32(B.entity_table + 4 * u8(ids + i))
          if mode == 'win' and e >= 0x80000000 then
            log(string.format('Y %d enemy %d entity %d hp %d>0', DT.frame, i, u8(ids + i), u16(e + 0x4C))); DT.poke32(e + 0x4C, 0)
          end
        end
        log(string.format('Y %d battle %s %d enemies at battle frame %d', DT.frame, mode, n, DT.bf)); DT.start_results(B)
      end
      if DT.bf > (B.max or 4000) then DT.finish('battle timeout') end
    end)
  end
  hook(A.rand + 0x80000000, 'rand', function() DT.rand = DT.rand + 1 end)
  hook(A.customRandom + 0x80000000, 'customRandom', function() DT.rand = DT.rand + 1 end)
  -- frame tick; also performs the section hijack (a call of callScriptSection made at a frame boundary)
  hook(A.gameLoop + 0x80000000, 'gameLoop', function()
    local r = PCSX.getRegisters()
    if DT.phase == 1 then                    -- callScriptSection returned to gameLoop's entry
      r.GPR.n.ra = DT.saved_ra; DT.phase = 0; return
    end
    tick()
    if DT.call then
      local c = DT.call; DT.call = nil
      DT.saved_ra = r.GPR.n.ra
      r.GPR.n.a0 = c[1]; r.GPR.n.a1 = c[2]; r.GPR.n.a2 = c[3]
      r.GPR.n.ra = A.gameLoop + 0x80000000; r.pc = A.callScriptSection + 0x80000000; DT.phase = 1
    elseif DT.ccall then          -- `camera`: createCameraMovement(&tamer location, speed), the call the training code makes to bring the view back to the tamer
      local c = DT.ccall; DT.ccall = nil
      DT.saved_ra = r.GPR.n.ra
      r.GPR.n.a0 = c[2]; r.GPR.n.a1 = c[3]
      r.GPR.n.ra = A.gameLoop + 0x80000000; r.pc = c[1] + 0x80000000; DT.phase = 1
    end
  end)
end

-- ---- input and steps -----------------------------------------------------------------------------
local function pad() return PCSX.SIO0.slots[1].pads[1] end
local function press(btn, frames)
  local b = PCSX.CONSTS.PAD.BUTTON[btn]
  if b == nil then error('unknown button ' .. tostring(btn)) end
  if DT.held then pad().clearOverride(DT.held.btn_id) end
  pad().setOverride(b); DT.held = { btn = btn, btn_id = b, left = frames }
end

local function cond_ok(conds)
  for _, c in ipairs(conds) do
    local v
    if c.n == 1 then v = u8(c.a) elseif c.n == 2 then v = u16(c.a) else v = u32(c.a) end
    if c.mask then v = bit.band(v, c.mask) end
    local ok
    if c.op == '==' then ok = v == c.v elseif c.op == '!=' then ok = v ~= c.v
    elseif c.op == '<' then ok = v < c.v elseif c.op == '>=' then ok = v >= c.v
    elseif c.op == '>' then ok = v > c.v else ok = v <= c.v end
    if not ok then return false end
  end
  return true
end

local function poke(addr, hex)
  local m = mem(); addr = addr % 0x200000
  for i = 1, #hex, 2 do m[addr + (i - 1) / 2] = tonumber(hex:sub(i, i + 1), 16) end
end

local function s32(a) local v = u32(a); if v >= 0x80000000 then v = v - 0x100000000 end return v end
local function poke32(addr, v)
  v = v % 0x100000000
  poke(addr, string.format('%02x%02x%02x%02x', v % 256, math.floor(v / 256) % 256, math.floor(v / 65536) % 256, math.floor(v / 16777216)))
end

DT.poke32 = poke32; DT.poke = poke

local function finish(reason)
  if DT.done then return end
  log(string.format('E %d %s', DT.frame, reason))
  DT.stop_hooks()
  local f = io.open(DT.S.out, 'w'); f:write(table.concat(DT.out, '\n') .. '\n'); f:close()
  if DT.S.steplog and DT.sl then local g = io.open(DT.S.steplog, 'w'); g:write(table.concat(DT.sl, '\n') .. '\n'); g:close() end
  DT.done = true; DT.reason = reason
end
DT.finish = finish

-- steps:
--   {t='wait', n=frames}
--   {t='press', b='CROSS', n=3}                    hold n frames (a gap of 2 frames follows)
--   {t='until', c={conds}, b='CROSS', n=3, gap=30, max=1800}   press b every gap frames until the conditions hold
--   {t='talk', c={conds}, max=3000}                press CROSS when a text box or menu waits, until the conditions hold
--   {t='poke', a=addr, hex='..'}  {t='warp', screen=, exit=}  {t='call', script=, section=, event=}
--   {t='trace', on=true|false}  {t='mark', name=}  {t='end'}
function DT.run_steps()
  if DT.held then
    DT.held.left = DT.held.left - 1
    if DT.held.left <= 0 then pad().clearOverride(DT.held.btn_id); DT.held = nil; DT.cool = 2 end
  end
  if DT.cool and DT.cool > 0 then DT.cool = DT.cool - 1; return end
  if DT.frame >= DT.S.max_frames then return finish('max_frames') end
  if DT.stop_at and DT.frame >= DT.stop_at then return finish('battle') end
  while true do
    local s = DT.S.steps[DT.pc]
    if not s then return finish('steps_done') end
    local t = s.t
    if t == 'wait' then
      DT.w = (DT.w or 0) + 1
      if DT.w >= s.n then DT.w = nil; DT.pc = DT.pc + 1 end
      return
    elseif t == 'press' then
      press(s.b, s.n); DT.pc = DT.pc + 1; return
    elseif t == 'until' or t == 'talk' then
      if cond_ok(s.c) and (not s.nb or ((DT.nb or 0) >= s.nb and not DT.bend)) then DT.w = nil; DT.lastpress = nil; DT.pc = DT.pc + 1          -- s.nb (`talk after battle N`): also N battles of the run started and over
      else
        DT.w = (DT.w or 0) + 1
        if DT.w > s.max then
          if s.soft then DT.w = nil; DT.lastpress = nil; DT.pc = DT.pc + 1; return end          -- `until?`/`talk?`: the condition did not come, go on
          return finish('timeout step ' .. DT.pc)
        end
        local A = DT.S.A
        if t == 'until' then
          if s.b and DT.w % s.gap == 1 then press(s.b, s.n or 3) end
        else
          local ai = u8(A.ACTIVE_INSTRUCTION)
          if (ai == 0x1A or ai == 0x10) and DT.w - (DT.lastpress or -999) > (s.gap or 25) then
            press('CROSS', 3); DT.lastpress = DT.w
          end
        end
        return
      end
    elseif t == 'poke' then poke(s.a, s.hex); DT.pc = DT.pc + 1
    elseif t == 'bitset' then
      local b = u8(s.a)
      if s.on then b = bit.bor(b, s.bit) else b = bit.band(b, bit.bnot(s.bit)) end
      poke(s.a, string.format('%02x', b)); DT.pc = DT.pc + 1
    elseif t == 'door' then          -- `door E SCREEN`: through exit E until SCREEN is loaded and the tamer is free. The tamer is put back on the exit tiles whenever he is free and still
      local A = DT.S.A               -- on the old screen: a wild Digimon that charges him on the way starts a battle (S.battle fights it) and the battle puts him back where it began
      local free = u32(A.IS_SCRIPT_PAUSED) == 1 and u8(A.TAMER_STATE) == 0
      if u8(A.CURRENT_SCREEN) == s.screen and free then DT.w = nil; DT.lastpress = nil; DT.lastplace = nil; DT.pc = DT.pc + 1
      else
        DT.w = (DT.w or 0) + 1
        if DT.w > s.max then return finish('timeout step ' .. DT.pc) end
        if free and u8(A.CURRENT_SCREEN) ~= s.screen and DT.w - (DT.lastplace or -999) > 30 then
          local idx = {}
          for i = 0, 9999 do if u8(s.a + i) == s.v then idx[#idx + 1] = i end end
          if #idx == 0 then return finish('door: no tile ' .. s.v) end
          local i = idx[math.floor((#idx + 1) / 2)]
          local x = (i % 100 - 50) * 100 + 50; local z = (50 - math.floor(i / 100)) * 100 - 50
          poke32(A.TAMER_POSITION_DATA + 0x78, x); poke32(A.TAMER_POSITION_DATA + 0x7C, 0); poke32(A.TAMER_POSITION_DATA + 0x80, z)
          poke32(A.STORED_TAMER_POS, x); poke32(A.STORED_TAMER_POS + 4, 0); poke32(A.STORED_TAMER_POS + 8, z)
          poke32(A.TAMER_ENTITY + 0x10, x * 32768); poke32(A.TAMER_ENTITY + 0x14, 0); poke32(A.TAMER_ENTITY + 0x18, z * 32768)
          DT.lastplace = DT.w
          if DT.tracing then log(string.format('Y %d door %d placed', DT.frame, s.v - 110)) end
        else
          local ai = u8(A.ACTIVE_INSTRUCTION)
          if not free and (ai == 0x1A or ai == 0x10) and DT.w - (DT.lastpress or -999) > 25 then press('CROSS', 3); DT.lastpress = DT.w end
        end
        return
      end
    elseif t == 'approach' or t == 'move' or t == 'tile' then
      local A = DT.S.A
      local x, z, rot
      if t == 'move' then x, z = s.x, s.z
      elseif t == 'tile' then          -- `tile V`: the tamer is put on the middle of the tiles of the map grid that hold the trigger value V (110+E: exit E, 51-79: a section run when stepped on, 80-109: on pressing X)
        local idx = {}
        for i = 0, 9999 do if u8(s.a + i) == s.v then idx[#idx + 1] = i end end
        if #idx == 0 then
          if s.optional then DT.pc = DT.pc + 1 + (s.skip or 0); return end          -- `skip`: the steps that act on what was not found are skipped too (tools/dws/testing/branches.py)
          return finish('tile: no tile ' .. s.v)
        end
        local i = idx[math.floor((#idx + 1) / 2)]
        x = (i % 100 - 50) * 100 + 50; z = (50 - math.floor(i / 100)) * 100 - 50
      else
        if s.sid then          -- `approach sid N`: the NPC whose script id is N (the section its talk runs) and that exists now
          local found
          for i = 0, 7 do
            if u8(A.NPC_ENTITIES + i * 0x68 + 0x65) == s.sid and u32(s.et + 4 * (i + 2)) ~= 0 then found = i; break end
          end
          if found == nil then
            if s.optional then DT.pc = DT.pc + 1 + (s.skip or 0); return end
            return finish('approach: no NPC with script id ' .. s.sid)
          end
          s.slot = found
        end
        local pd = u32(A.NPC_ENTITIES + s.slot * 0x68 + 4)
        if pd < 0x80000000 or pd >= 0x80200000 then
          if s.optional then DT.pc = DT.pc + 1 + (s.skip or 0); return end          -- `approach? SLOT`: nobody there, go on
          return finish('approach: no NPC in slot ' .. s.slot)
        end
        local nx, nz = s32(pd + 0x78), s32(pd + 0x80)
        local tx, tz = s32(A.TAMER_POSITION_DATA + 0x78), s32(A.TAMER_POSITION_DATA + 0x80)
        local d = math.sqrt((tx - nx) ^ 2 + (tz - nz) ^ 2); if d == 0 then d = 1 end
        x = math.floor(nx + (tx - nx) * s.dist / d + 0.5); z = math.floor(nz + (tz - nz) * s.dist / d + 0.5)
        rot = math.floor(math.atan2(nz - z, nx - x) * 4096 / (2 * math.pi) + 0.5) % 4096
        if s.ongrid and (x <= -5000 or x >= 5000 or z <= -5000 or z >= 5000) then          -- `ongrid` (tools/dws/testing/branches.py, steps_of): an NPC parked off the 100x100 tile grid (S63: Overdell NPC 7 at z=-15702) puts the tamer where
          if DT.tracing then log(string.format('Y %d approach off the tile grid, skipped', DT.frame)) end          -- getTileTrigger reads MAP_COLLISION_DATA past its end, into MAPHEAD's buffer: a byte of the script layout acts as a tile
          if s.optional then DT.pc = DT.pc + 1 + (s.skip or 0); return end          -- trigger (docs/developing.md, "S63")
          return finish('approach: NPC off the tile grid')
        end
      end
      poke32(A.TAMER_POSITION_DATA + 0x78, x); poke32(A.TAMER_POSITION_DATA + 0x7C, 0); poke32(A.TAMER_POSITION_DATA + 0x80, z)
      poke32(A.STORED_TAMER_POS, x); poke32(A.STORED_TAMER_POS + 4, 0); poke32(A.STORED_TAMER_POS + 8, z)
      poke32(A.TAMER_ENTITY + 0x10, x * 32768); poke32(A.TAMER_ENTITY + 0x14, 0); poke32(A.TAMER_ENTITY + 0x18, z * 32768)
      if rot then poke(A.TAMER_POSITION_DATA + 0x72, string.format('%02x%02x', rot % 256, math.floor(rot / 256))) end
      DT.pc = DT.pc + 1
    elseif t == 'warp' then
      local A = DT.S.A
      poke(A.TAMER_SUB_STATE, '00')
      poke(A.TARGET_MAP, s.screen16 and string.format('%02x%02x', s.screen % 256, math.floor(s.screen / 256)) or string.format('%02x', s.screen))
      poke(A.CURRENT_EXIT, string.format('%02x', s.exit)); poke(A.TAMER_STATE, '0500')
      DT.pc = DT.pc + 1
    elseif t == 'warpif' then        -- `warpif SCREEN [EXIT] skip K` (tools/dws/testing/branches.py): back to SCREEN by a warp when a script took the tamer elsewhere; on SCREEN already, the K steps that follow are skipped
      local A = DT.S.A
      if u8(A.CURRENT_SCREEN) == s.screen then DT.pc = DT.pc + 1 + (s.skip or 0)
      else
        poke(A.TAMER_SUB_STATE, '00'); poke(A.TARGET_MAP, string.format('%02x', s.screen))
        poke(A.CURRENT_EXIT, string.format('%02x', s.exit)); poke(A.TAMER_STATE, '0500'); DT.pc = DT.pc + 1
      end
    elseif t == 'call' then
      DT.call = { s.script, s.section, s.event or 1 }; DT.pc = DT.pc + 1; return
    elseif t == 'camera' then        -- the view follows the tamer only while he walks: after `npc`/`tile`/`move` put him far away, the NPCs there are off screen
      DT.ccall = { s.fn, s.target + 0x80000000, s.speed }; DT.pc = DT.pc + 1; return      -- (not drawn = not talkable, isInvisible); this moves the view to him
    elseif t == 'trace' then
      if s.on and not DT.tracing then snapshot() end
      DT.tracing = s.on; DT.pc = DT.pc + 1
    elseif t == 'mark' then
      if DT.tracing then
        diff(); log(string.format('K %d %s', DT.frame, s.name))
        for _, w in ipairs(DT.S.watch) do if w.digest then log(string.format('D %s %s', w.name, hexs(w.addr, w.len))) end end
      end
      DT.pc = DT.pc + 1
    elseif t == 'end' then return finish('end')
    else return finish('bad step ' .. tostring(t)) end
  end
end

function DT.start(S)
  DT.stop_hooks(); DT.ins = 0; DT.nw = 0; DT.idle = 0; DT.lastn = -1
  DT.S = S; DT.out = {}; DT.frame = 0; DT.rand = 0; DT.pc = 1; DT.w = nil; DT.cool = nil; DT.phase = 0
  DT.call = nil; DT.ccall = nil; DT.nb = 0; DT.sl = nil; DT.lastpc = nil; DT.nrand = 0; DT.stop_at = nil; DT.pending_finish = nil; DT.done = false; DT.reason = nil; DT.lastpress = nil
  DT.tracing = S.trace and true or false
  if DT.tracing then snapshot() end
  DT.install(S)
  return 'started'
end
