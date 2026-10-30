#!/usr/bin/env python3
"""presented_frames.py start RAW NSWAPS  |  presented_frames.py wait RAW  |  presented_frames.py mp4 RAW OUT.mp4 [K]
Captures every frame the game presents: a Lua exec breakpoint on GsSortClear (called
right after GsSwapDispBuff in every loop) grabs the newly displayed buffer
(PCSX.GPU.takeScreenShot, 320x240 15-bit) and the vblank count (GPU::Vsync events).
'mp4' expands that to a 60 Hz video: each frame is held until the vblank of the
next swap, as on a TV. (The HTTP 'record' of tools/dev/emulator.py polls stills at
<= 30 fps, and grabbing the screen at the Vsync event races with the swap.)"""

from pathlib import Path as _DevPath
import sys as _dev_sys
_DEV_ROOT = str(next(p for p in _DevPath(__file__).resolve().parents if (p / "tools").is_dir()))
_dev_sys.path.insert(0, _DEV_ROOT)
_dev_sys.path.insert(0, str(_DevPath(_DEV_ROOT) / "tools"))
from tools.dev.lua import write_script
import subprocess, sys, os, time
R=_DEV_ROOT
S=os.path.dirname(os.path.abspath(__file__))
MAP=os.environ.get('FD_MAP', R+'/build/full/exe/SLUS_010.32.elf.map')
def lua(code):
    p = write_script('fps', 'frame-dump', code)
    return subprocess.run([R+'/tools/dev/emulator.py','lua','return dofile("%s")'%p],capture_output=True,text=True,cwd=R).stdout.strip()
def sym(name):
    import re
    for line in open(MAP):
        m=re.match(r'\s+(0x[0-9a-f]+)\s+'+name+r'\s*$',line)
        if m: return int(m.group(1),16)
    sys.exit('no '+name)
cmd=sys.argv[1]
if cmd=='start':
    raw=os.path.abspath(sys.argv[2]); n=int(sys.argv[3])
    # optional extra args ADDR:SIZE (2 or 4, signed) logged at each swap into RAW.extra
    rd=[]
    for spec in sys.argv[4:]:
        a,sz=spec.split(':'); a=int(a,16)&0x1fffff; sz=int(sz)
        if sz==4: e='(m[%d]+m[%d]*256+m[%d]*65536+m[%d]*16777216)'%(a,a+1,a+2,a+3); lim=2**32
        else: e='(m[%d]+m[%d]*256)'%(a,a+1); lim=2**16
        rd.append('(function(x) if x>=%d then return x-%d end return x end)(%s)'%(lim//2,lim,e))
    xcode='local m = PCSX.getMemPtr(); FD_X[FD_N] = table.concat({%s}, " ")'%(', '.join('tostring(%s)'%e for e in rd)) if rd else ''
    # FD_FROM=ADDR:VALUE: start capturing once the signed halfword at ADDR >= VALUE
    start=''
    if os.environ.get('FD_FROM'):
        a,v=os.environ['FD_FROM'].split(':'); a=int(a,16)&0x1fffff
        start=('if FD_N == 0 then local mm = PCSX.getMemPtr(); local x = mm[%d] + mm[%d] * 256; '
               'if x >= 32768 then x = x - 65536 end; if x < %d then return end end')%(a,a+1,int(v))
    print(lua('''FD_N = 0; FD_MAX = %d; FD_V = 0; FD_T = {}; FD_X = {}
FD_F = Support.File.open('%s', 'TRUNCATE')
FD_VL = PCSX.Events.createEventListener('GPU::Vsync', function() FD_V = FD_V + 1 end)
FD_BP = PCSX.addBreakpoint(0x%x, 'Exec', 4, 'framedump', function()
  %s
  if FD_N < FD_MAX then
    local s = PCSX.GPU.takeScreenShot()
    if s.width == 320 and s.height == 240 then FD_F:writeMoveSlice(s.data) else FD_F:write(string.rep('\\0', 153600)) end
    FD_N = FD_N + 1
    FD_T[FD_N] = FD_V
    %s
    if FD_N == FD_MAX then FD_F:close(); FD_BP:remove(); FD_VL:remove() end
  end
end)
return 'dumping'
'''%(n,raw,sym('GsSortClear'),start,xcode)))
elif cmd=='wait':
    while True:
        r=lua('return tostring(FD_N) .. "/" .. tostring(FD_MAX)'); print(r, flush=True)
        a,b=r.split('/')
        if a==b: break
        time.sleep(1)
    open(sys.argv[2]+'.vbl','w').write(lua('return table.concat(FD_T, " ")'))
    open(sys.argv[2]+'.extra','w').write(lua('return table.concat(FD_X, "\\n")'))
elif cmd=='mp4':
    # optional 4th argument K: every swap is held K refreshes instead of until
    # the next swap's vblank (game time for runs with MOD_FPS_TEST_TICK,
    # whose ticks last longer than 3 refreshes: K = 3 / renders per tick)
    raw,out=sys.argv[2],sys.argv[3]
    fixed=int(sys.argv[4]) if len(sys.argv)>4 else 0
    vbl=[int(x) for x in open(raw+'.vbl').read().split()]
    n=len(vbl); fr=open(raw,'rb').read()
    seq=bytearray()
    for i in range(n-1):
        seq+=fr[i*153600:(i+1)*153600]*(fixed if fixed else max(vbl[i+1]-vbl[i],0))
    seq+=fr[(n-1)*153600:n*153600]
    open(raw+'.60','wb').write(seq)
    subprocess.run([os.path.expanduser('~/.local/bin/ffmpeg'),'-y','-loglevel','error','-f','rawvideo','-pix_fmt','bgr555le','-s','320x240','-r','60','-i',raw+'.60',
                    '-vf','scale=640:480:flags=neighbor','-c:v','libx264','-crf','12','-pix_fmt','yuv420p',out],check=True)
    print(out, n, 'swaps', len(seq)//153600, 'frames at 60 Hz')
