#!/usr/bin/env python3
"""Measure experimental AUTO/forced/feedback policies on matching Redux states.

Start the matching disc with tools/dev/emulator.py (EMU_PORT), then provide
same-build field or battle checkpoints. Captures use guest refresh time;
wall throughput and physical display presentation are separate measurements.
"""
from pathlib import Path
import argparse
import sys, json, time, urllib.parse, math
ROOT = Path(__file__).resolve().parents[3]
sys.path[:0] = [str(ROOT), str(ROOT / 'tools')]
from tools.dev.saves.releases import Emu
from tools.langpatch import elf_symbols

e = None
out = None
states = {}


def lua(code):
 p=out/'command.lua';p.write_text(code)
 r=e.api('/api/v1/lua/eval?file='+urllib.parse.quote(str(p))).decode()
 if r.startswith('error:'):raise RuntimeError(r)
 return r

def sample(label,policy,refreshes=3600):
 # Start from same executable's scene snapshot. Counters and controller state
 # restore together; no state from another executable is used.
 e.run('load',str(states[label]))
 # This private study ABI is checked against the ELF size before any write.
 lua(f'''local m=PCSX.getMemPtr(); local ffi=require('ffi');
 local function w(a,v) ffi.cast('uint32_t*',m+a-0x80000000)[0]=v end
 ffi.fill(m+{e.A('modAdapt')}-0x80000000,48,0); w({e.A('MOD_ADAPT_POLICY')},{policy}); w({e.A('MOD_ADAPT_SWITCHES')},0)
 if STUDY then STUDY.vl:remove() end
 if not pcall(ffi.typeof,'struct adaptive_timespec') then
  ffi.cdef[[struct adaptive_timespec {{ long sec; long ns; }}; int clock_gettime(int,void*);]]
 end
 local ts=ffi.new('struct adaptive_timespec')
 local function clock() ffi.C.clock_gettime(1,ts);return tonumber(ts.sec)*1000000000+tonumber(ts.ns) end
 local function r(a) return tonumber(ffi.cast('uint32_t*',m+a-0x80000000)[0]) end
 STUDY={{v=0,warm=0,rows={{}},sw=0,prevMode=nil,renders=r({e.A('MOD_FPS_RENDERS')}),badDelta=0}}
 STUDY.vl=PCSX.Events.createEventListener('GPU::Vsync',function()
   if STUDY.warm<6 then STUDY.warm=STUDY.warm+1;STUDY.renders=r({e.A('MOD_FPS_RENDERS')});return end
   STUDY.v=STUDY.v+1
   local mode=r({e.A('MOD_FPS_MODE_RUN')})
   if STUDY.prevMode and mode~=STUDY.prevMode then STUDY.sw=STUDY.sw+1 end
   STUDY.prevMode=mode
   local renders=r({e.A('MOD_FPS_RENDERS')})
   if renders~=STUDY.renders then
     if renders-STUDY.renders~=1 then STUDY.badDelta=STUDY.badDelta+1 end
     STUDY.rows[#STUDY.rows+1]=tostring(STUDY.v)..','..tostring(mode)..','..string.format('%.0f',clock())
     STUDY.renders=renders
   end
   if STUDY.v>={refreshes} then PCSX.pauseEmulator() end
 end)
 PCSX.resumeEmulator(); return 'armed' ''')
 start=time.monotonic(); lastprint=start
 while int(lua('return STUDY.v'))<refreshes:
  if time.monotonic()-start>600:raise RuntimeError('capture timeout')
  if time.monotonic()-lastprint>30:print(label,policy,lua('return STUDY.v'),flush=True);lastprint=time.monotonic()
  time.sleep(.5)
 host=time.monotonic()-start
 raw=lua("return table.concat(STUDY.rows,'\\n')")
 rows=[[int(x) for x in r.split(',')] for r in raw.splitlines() if ',' in r]
 if int(lua('return STUDY.badDelta')) or len(rows)<2:
  raise RuntimeError('incomplete swap sampling; reject this capture')
 if any(b[0]<=a[0] or b[2]<=a[2] for a,b in zip(rows,rows[1:])):
  raise RuntimeError('non-monotonic swap timestamps; reject this capture')
 def stats(rows):
  ds=[b[0]-a[0] for a,b in zip(rows,rows[1:])]
  slow=sorted(ds,reverse=True)[:max(1,math.ceil(len(ds)*.01))]
  from collections import Counter
  walls=[(b[2]-a[2])/1e9 for a,b in zip(rows,rows[1:])]
  wallslow=sorted(walls,reverse=True)[:max(1,math.ceil(len(walls)*.01))]
  return dict(swaps=len(rows),host_fps=len(walls)/sum(walls),host_low1=1/(sum(wallslow)/len(wallslow)),fps=60*len(ds)/sum(ds),low1=60/(sum(slow)/len(slow)),intervals=dict(sorted(Counter(ds).items())))
 ram=e.ram()
 result=dict(scene=label,policy=policy,screen=e.peek('CURRENT_SCREEN','h',ram),game_state=e.peek('GAME_STATE','H',ram),cpu_spins=e.peek('MOD_CPU_SPINS','i',ram),logic_ticks=e.peek('MOD_FPS_TICKS','i',ram),guest_refreshes=refreshes,host_seconds=host,bad_counter_deltas=int(lua('return STUDY.badDelta')),
             switches=int(lua('return STUDY.sw')),whole=stats(rows),steady=stats([r for r in rows if r[0]>=600]),raw=rows)
 result['switches_per_guest_minute']=result['switches']*3600/refreshes
 (out/f'{label}-policy{policy}.json').write_text(json.dumps(result,indent=2)+'\n')
 print(json.dumps({k:v for k,v in result.items() if k!='raw'}),flush=True)
 lua('STUDY.vl:remove();STUDY=nil;return true')
 return result
def main():
 global e, out, states
 p=argparse.ArgumentParser(description=__doc__)
 p.add_argument('--disc',required=True)
 p.add_argument('--exe',required=True)
 p.add_argument('--port',type=int,default=42516)
 p.add_argument('--out',type=Path,required=True)
 p.add_argument('--refreshes',type=int,default=3600)
 p.add_argument('--policies',default='1,2,0')
 p.add_argument('states',nargs='+',help='scene=matching-checkpoint.state')
 a=p.parse_args()
 if a.refreshes<720: p.error('capture at least 720 refreshes (steady range starts at 600)')
 policies=[int(x) for x in a.policies.split(',')]
 if any(x not in (0,1,2,3) for x in policies):p.error('policies must be 0,1,2,3')
 out=a.out.resolve();out.mkdir(parents=True,exist_ok=True)
 states={name:Path(path).resolve() for name,path in (x.split('=',1) for x in a.states)}
 if any(not name or any(c not in 'abcdefghijklmnopqrstuvwxyz0123456789-_' for c in name) for name in states):
  p.error('scene labels use lowercase letters, digits, hyphens and underscores')
 e=Emu(a.disc,a.exe,a.port,str(out))
 syms=elf_symbols(e.exe+'.elf')
 if syms.get('modAdapt',(0,0,''))[1]!=48:raise RuntimeError('unsupported controller ABI; expected 48-byte state')
 for name,(address,_,_) in syms.items():e.table.setdefault(name,address)
 try:
  for label in states:
   for policy in policies:sample(label,policy,a.refreshes)
 finally:
  lua('if STUDY then STUDY.vl:remove();STUDY=nil end;return true')


if __name__=='__main__':main()
