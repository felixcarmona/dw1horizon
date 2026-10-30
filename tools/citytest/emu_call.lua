-- Calls functions of the game at frame boundaries and reads what they returned (tools/citytest/emu_scenarios.py).
-- The emulator must run with EMU_ARGS="-interpreter -debugger": Lua breakpoints only fire there.
--   CC.install(gameLoop)     a breakpoint on gameLoop (one hit per frame)
--   CC.run(ops)              ops = { {fn, a0, a1, rec}, ... }: one call per frame; fn runs with a0, a1 and returns to gameLoop's first
--                            instruction (the section runner trick of tools/dev/story_trace.lua); v0 is appended to CC.out when rec is true.
--                            CC.done becomes true after the last one.
CC = CC or {}
function CC.install(gameLoop)
  if CC.bp then CC.bp:remove() end
  CC.gl = gameLoop + 0x80000000; CC.phase = 0; CC.ops = {}; CC.i = 1; CC.done = true; CC.out = {}
  CC.bp = PCSX.addBreakpoint(CC.gl, 'Exec', 4, 'cc_gameLoop', function()
    local r = PCSX.getRegisters()
    if CC.phase == 1 then
      local o = CC.ops[CC.i]
      if o[4] then CC.out[#CC.out + 1] = tostring(tonumber(r.GPR.n.v0)) end
      CC.i = CC.i + 1
      r.GPR.n.ra = CC.saved_ra; CC.phase = 0
      if CC.i > #CC.ops then CC.done = true end
      return
    end
    local o = CC.ops[CC.i]
    if o and not CC.done then
      CC.saved_ra = r.GPR.n.ra
      r.GPR.n.a0 = o[2] or 0; r.GPR.n.a1 = o[3] or 0
      r.GPR.n.ra = CC.gl; r.pc = o[1] + 0x80000000; CC.phase = 1
    end
  end)
  return 'installed'
end
function CC.run(ops)
  CC.ops = ops; CC.i = 1; CC.out = {}; CC.done = (#ops == 0)
  return 'queued ' .. #ops
end
function CC.result() return table.concat(CC.out, ',') end
