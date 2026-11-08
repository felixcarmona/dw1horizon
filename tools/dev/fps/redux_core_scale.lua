-- Test-only model of a faster/slower CPU in pinned Redux's x64 JIT.
-- recompiler.cc charges (count + ROM extras) * BIAS at each compiled block.
-- Change only that charge; vblank/root-counter/GPU scheduling is untouched.
-- GTE and multiply latency stay fixed, so this is not a hardware overclock.
local ffi=require('ffi')
local reg=ffi.cast('uint8_t*',PCSX.getRegisters())
assert(ffi.cast('uint64_t*',reg+528)[0]==PCSX.getCPUCycles())
local scale=CORE_SCALE or 0.5
assert(scale==0.5 or scale==2)
if CORE then CORE.listener:remove();error('scale already installed') end
CORE={patched={},count=0,scale=scale}
local function patch()
 local f=assert(io.open('/proc/self/maps'))
 for l in f:lines() do
  local a,b=l:match('^(%x+)%-(%x+) rwxp')
  if a then
   local base=tonumber(a,16);local size=tonumber(b,16)-base
   -- Only Redux's large, anonymous 32 MB code cache, never LuaJIT's pages.
   if size>=32*1024*1024 then
    local p=ffi.cast('uint8_t*',base)
    local s=ffi.string(p,math.min(size,8*1024*1024))
    for _,op in ipairs({0x83,0x81}) do
     local pos=1
     while true do
      local i=s:find(string.char(0x48,op,0x85,0x48,0x02,0,0),pos,true)
      if not i then break end
      local off=i+6;local addr=base+off
      if not CORE.patched[addr] then
       local width=op==0x83 and 1 or 4
       local imm=width==1 and tonumber(p[off]) or tonumber(ffi.cast('uint32_t*',p+off)[0])
       assert(imm>0 and imm%2==0 and imm<=1100,'unexpected block cycle charge')
       local target=math.floor(imm*scale)
       -- An imm8 add sign-extends; promoting an opcode would change its size.
       -- Slower-core tests cap at 126; omit longer blocks from that model.
       if imm%22~=0 and (width==4 or target<=127) then
        CORE.patched[addr]={imm,width}
        if width==1 then p[off]=target else ffi.cast('uint32_t*',p+off)[0]=target end
        CORE.count=CORE.count+1
       end
      end
      pos=i+7+(op==0x83 and 1 or 4)
     end
    end
   end
  end
 end
 f:close()
end
patch()
CORE.listener=PCSX.Events.createEventListener('GPU::Vsync',patch)
return CORE.count
