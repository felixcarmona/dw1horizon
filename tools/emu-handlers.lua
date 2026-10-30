-- PCSX-Redux web server handlers used by tools/emu.py.
-- Loaded at startup with:  -exec "dofile('.../tools/emu-handlers.lua')"
-- Each handler receives the request and returns a string (the response body).
--   GET /api/v1/lua/eval?code=<url-encoded lua>   runs Lua code, returns tostring(result)
--   GET /api/v1/lua/eval?file=/path/x.lua        same, reading the code from a file (long URLs fail)
--   GET /api/v1/lua/press?button=START            holds a button down (until release)
--   GET /api/v1/lua/release?button=START          releases it
--   GET /api/v1/lua/save?file=/path/x.state        saves a full emulator save state
--   GET /api/v1/lua/load?file=/path/x.state        loads a save state (reproduces the exact state)

PCSX.WebServer = PCSX.WebServer or {}            -- the server creates these tables later with getfieldtable,
PCSX.WebServer.Handlers = PCSX.WebServer.Handlers or {}   -- so it reuses the ones we define here

local function urldecode(s)
  s = s:gsub('+', ' ')
  return (s:gsub('%%(%x%x)', function(h) return string.char(tonumber(h, 16)) end))
end

local function query(req)
  local t = {}
  for k, v in string.gmatch(req.urlData.query or '', '([^&=]+)=([^&]*)') do t[k] = urldecode(v) end
  return t
end

-- No per-frame Lua listener on purpose: a GPU::Vsync listener here ended up in a
-- Lua stack overflow inside the emulator after long runs. Buttons are pressed and
-- released by tools/emu.py, which waits in between.

PCSX.WebServer.Handlers.press = function(req)
  local q = query(req)
  local name = (q.button or 'START'):upper()
  local button = PCSX.CONSTS.PAD.BUTTON[name]
  if button == nil then return 'error: unknown button ' .. name end
  PCSX.SIO0.slots[1].pads[1].setOverride(button)
  return 'ok ' .. name
end

PCSX.WebServer.Handlers.release = function(req)
  local q = query(req)
  local name = (q.button or 'START'):upper()
  local button = PCSX.CONSTS.PAD.BUTTON[name]
  if button == nil then return 'error: unknown button ' .. name end
  PCSX.SIO0.slots[1].pads[1].clearOverride(button)
  return 'ok ' .. name
end

PCSX.WebServer.Handlers.eval = function(req)
  local q = query(req)
  local fn, err
  if q.file then fn, err = loadfile(q.file)          -- the server rejects long URLs: code in a file
  else fn, err = loadstring(q.code or '', 'eval') end
  if not fn then return 'error: ' .. tostring(err) end
  local ok, res = pcall(fn)
  if not ok then return 'error: ' .. tostring(res) end
  return tostring(res)
end

PCSX.WebServer.Handlers.save = function(req)
  local q = query(req)
  if not q.file then return 'error: missing file=' end
  local slice = PCSX.createSaveState()
  local f = Support.File.open(q.file, 'TRUNCATE')
  f:write(slice)
  f:close()
  return 'ok ' .. q.file
end

PCSX.WebServer.Handlers.load = function(req)
  local q = query(req)
  if not q.file then return 'error: missing file=' end
  local f = Support.File.open(q.file, 'READ')
  if f:failed() then return 'error: cannot open ' .. q.file end
  PCSX.loadSaveState(f)
  f:close()
  return 'ok ' .. q.file
end
