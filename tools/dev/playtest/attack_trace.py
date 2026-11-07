"""Read-only launch, contact and direct-damage traces for a battle fixture.

The breakpoints observe actual effect transforms and battle damage calls.
Poison ticks are excluded from direct hits. No game values are changed.
"""
import os
from pathlib import Path
import urllib.parse

from tools.dev import emulator as E


class AttackTrace:
    def _eval(self, code):
        # Redux's inline-code query is short; use a file for complete programs.
        path = Path(E.ROOT) / 'build' / ('trace-' + os.environ['EMU_PORT'] + '.lua')
        path.write_text(code)
        return E.api('/api/v1/lua/eval?file=' + urllib.parse.quote(str(path))).decode()

    def __init__(self, battle):
        a = battle.address
        code = '''
if ORIGIN then for _,b in ipairs(ORIGIN.bp) do pcall(function() b:remove() end) end end
ORIGIN={bp={},rows={},hits={},contacts={}}
local m=PCSX.getMemPtr()
local function u(a,n)
 local o=bit.band(a,0x1fffff);local v=0
 for i=n-1,0,-1 do v=v*256+tonumber(m[o+i]) end
 return v
end
local function s(a,n)
 local v=u(a,n);return v>=2^(n*8-1) and v-2^(n*8) or v
end
local function hook(addr)
 ORIGIN.bp[#ORIGIN.bp+1]=PCSX.addBreakpoint(addr,'Exec',4,'attack-origin',function()
  local ctx=u(CTX,4);local src=u(ctx+16,4)
  if src~=ENEMY then return end
  local p=u(DATA,4)+4;local bone=u(ctx+24,4);local pos=u(src+4,4)
  local row={frame=s(FRAME,2),anim=u(src+46,1),anim_frame=s(src+28,2),bone=s(bone,2),
             offset={s(bone+2,2),s(bone+4,2),s(bone+6,2)}}
  local ret
  ret=PCSX.addBreakpoint(tonumber(PCSX.getRegisters().GPR.n.ra),'Exec',4,'attack-origin-return',function()
   row.xyz={s(p,4)-s(pos+120,4),s(p+4,4)-s(pos+124,4),s(p+8,4)-s(pos+128,4)}
   ORIGIN.rows[#ORIGIN.rows+1]=row;ret:remove()
  end)
  ORIGIN.bp[#ORIGIN.bp+1]=ret
 end)
end
hook(OFFSET);hook(MATRIX)
for _,pair in ipairs({{DAMAGE,'hits'},{CHANCE,'contacts'}}) do
 local key=pair[2]
 ORIGIN.bp[#ORIGIN.bp+1]=PCSX.addBreakpoint(pair[1],'Exec',4,'attack-contact',function()
  local r=PCSX.getRegisters().GPR.n
  if tonumber(r.a0)==ENEMY then
   ORIGIN[key][#ORIGIN[key]+1]={s(FRAME,2),tonumber(key=='hits' and r.a2 or r.a3)}
  end
 end)
end
return 'installed'
'''
        addresses = dict(
            DAMAGE=a('BTL_calculateDamage'), CHANCE=a('BTL_calculateHitChance'),
            CTX=a('EFE_SCRIPT_CONTEXT'), ENEMY=a('NPC_ENTITIES') + battle.enemy_slot * 104,
            DATA=a('EFE_CURRENT_DATA_SEGMENT'), FRAME=a('BATTLE_FRAME_COUNT'),
            OFFSET=a('BTL_setTransformToBoneOffset'), MATRIX=a('BTL_setTransformToBoneMatrix'))
        for name, address in addresses.items():
            code = code.replace(name, str(address))
        response = self._eval(code)
        if response != 'installed':
            raise RuntimeError(response)

    def finish(self):
        # CSV avoids depending on a Lua JSON module. Each origin row contains
        # battle frame, animation, animation frame, bone, local xyz, relative xyz.
        raw = self._eval('''
local out={}
for _,r in ipairs(ORIGIN.rows) do
 out[#out+1]=table.concat({r.frame,r.anim,r.anim_frame,r.bone,unpack(r.offset)},',')..','..table.concat(r.xyz,',')
end
return table.concat(out,';')
''')
        result = dict(origins=[list(map(int, row.split(','))) for row in raw.split(';') if row])
        for key in ('hits', 'contacts'):
            raw = self._eval("local out={};for _,r in ipairs(ORIGIN." + key +
                             ") do out[#out+1]=table.concat(r,',') end;return table.concat(out,';')")
            result[key] = [list(map(int, row.split(','))) for row in raw.split(';') if row]
        # Overlay addresses are reused outside battle. Remove observers before
        # the next fixture restores its field snapshot or loads another map.
        self._eval("for _,b in ipairs(ORIGIN.bp) do pcall(function() b:remove() end) end;ORIGIN=nil;return 'cleared'")
        return result
