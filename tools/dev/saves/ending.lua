-- Run script SCRIPT section SECTION (callScriptSection at a frame boundary, as tools/dev/story_trace.lua does) and log the
-- ending's sound bank state (SOUND_BUFFERS[8].isLoading) at loadMapSounds2, gameClearSave and every saveFileStart.
EN = EN or {}
local function u8(a) return PCSX.getMemPtr()[a % 0x200000] end
function EN.arm(A, script, section, param)
  EN.log = {}; EN.pending = { script, section, param }; EN.phase = 0; EN.f = 0
  local function L(s) EN.log[#EN.log + 1] = string.format('f%d %s', EN.f, s) end
  local function busy() return u8(A.sb + 8 * 8 + 6) end
  EN.bps = {}
  EN.bps[#EN.bps + 1] = PCSX.addBreakpoint(A.gameLoop, 'Exec', 4, 'gl', function()
    local r = PCSX.getRegisters(); EN.f = EN.f + 1
    if EN.phase == 1 then r.GPR.n.ra = EN.ra; EN.phase = 2; return end
    if EN.pending then
      local c = EN.pending; EN.pending = nil; EN.ra = r.GPR.n.ra
      r.GPR.n.a0 = c[1]; r.GPR.n.a1 = c[2]; r.GPR.n.a2 = c[3]
      r.GPR.n.ra = A.gameLoop; r.pc = A.css; EN.phase = 1; L('call section')
    end
  end)
  EN.bps[#EN.bps + 1] = PCSX.addBreakpoint(A.lms2, 'Exec', 4, 'lms2', function()
    L(string.format('loadMapSounds2(%#x) bank8 loading %d', PCSX.getRegisters().GPR.n.a0, busy())) end)
  EN.bps[#EN.bps + 1] = PCSX.addBreakpoint(A.gcs, 'Exec', 4, 'gcs', function() L('gameClearSave: bank8 loading ' .. busy()) end)
  EN.bps[#EN.bps + 1] = PCSX.addBreakpoint(A.sfs, 'Exec', 4, 'sfs', function() L('saveFileStart: bank8 loading ' .. busy()) end)
  return 'armed'
end
function EN.report() return table.concat(EN.log, '\n') end
