-- Cut a memory card write: a breakpoint on MemCardWriteFile logs each part (buffer, offset, size, vsync);
-- on part NTH, after VS vsyncs (0 = at the call), the emulator pauses (the test then kills it: a power cut).
CUT = CUT or {}
local function u32(a) local m = PCSX.getMemPtr(); a = a % 0x200000; return m[a] + m[a + 1] * 256 + m[a + 2] * 65536 + m[a + 3] * 16777216 end
function CUT.arm(addr, nth, vs)
  CUT.n = 0; CUT.v = 0; CUT.log = {}; CUT.paused = false
  if CUT.bp then pcall(function() CUT.bp:remove() end) end
  if CUT.l then pcall(function() CUT.l:remove() end) end
  CUT.l = PCSX.Events.createEventListener('GPU::Vsync', function()
    CUT.v = CUT.v + 1
    if CUT.at and CUT.v >= CUT.at and not CUT.paused then CUT.paused = true; CUT.log[#CUT.log + 1] = 'pause ' .. CUT.v; PCSX.pauseEmulator() end
  end)
  CUT.bp = PCSX.addBreakpoint(addr, 'Exec', 4, 'MemCardWriteFile', function()
    local r = PCSX.getRegisters().GPR.n
    CUT.n = CUT.n + 1
    CUT.log[#CUT.log + 1] = string.format('part %d buf %08x ofs %x size %x vsync %d', CUT.n, r.a2, r.a3, u32(r.sp + 16), CUT.v)
    if CUT.n == nth then
      if vs == 0 then CUT.paused = true; CUT.log[#CUT.log + 1] = 'pause ' .. CUT.v; PCSX.pauseEmulator() else CUT.at = CUT.v + vs end
    end
  end)
  return 'armed'
end
function CUT.report() return table.concat(CUT.log, '\n') end
-- Make call NTH of the function at ADDR (MemCardReadFile/MemCardWriteFile) fail to start: it returns 0 at once.
function CUT.fail(addr, nth)
  CUT.fn = 0; CUT.log = CUT.log or {}
  if CUT.fbp then pcall(function() CUT.fbp:remove() end) end
  CUT.fbp = PCSX.addBreakpoint(addr, 'Exec', 4, 'fail', function()
    local r = PCSX.getRegisters()
    CUT.fn = CUT.fn + 1
    CUT.log[#CUT.log + 1] = string.format('call %d ofs %x', CUT.fn, r.GPR.n.a3)
    if CUT.fn == nth then r.GPR.n.v0 = 0; r.pc = r.GPR.n.ra; CUT.log[#CUT.log + 1] = 'forced 0' end
  end)
  return 'armed'
end
