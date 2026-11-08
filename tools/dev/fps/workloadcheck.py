#!/usr/bin/env python3
"""Read the title trial and sample actual flips on GPU vblanks in PCSX-Redux.

Use an FPS_DIAGNOSTICS=1 executable matching the running disc. No debugger
breakpoints are installed. --mode changes RAM only for a comparison capture;
load the same scene checkpoint before comparing AUTO, 20 and 60.
"""
import argparse
from collections import Counter
import json
from pathlib import Path
import sys
import time
import urllib.parse
import urllib.request

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))
from tools.langpatch import elf_symbols


def capture(exe, port, refreshes, mode=None):
    symbols = elf_symbols(str(exe) + '.elf')
    names = ('MOD_FPS_TRIAL_SWAPS', 'MOD_FPS_TRIAL_VBLANKS',
             'MOD_FPS_TRIAL_FPS100', 'MOD_FPS_TRIAL_CPU_SPINS', 'MOD_FPS_MODE_RUN',
             'MOD_FPS_TRIAL_PACKET_BYTES', 'MOD_FPS_AUTO_MODE')
    addresses = {n: symbols[n][0] for n in (*names, 'MOD_FPS_RENDERS', 'MOD_FPS_TICKS')}
    def lua(code):
        script = ROOT / 'build/dev/fps' / f'workload-{port}.lua'
        script.parent.mkdir(parents=True, exist_ok=True)
        script.write_text(code)
        url = f'http://127.0.0.1:{port}/api/v1/lua/eval?file=' + urllib.parse.quote(str(script))
        with urllib.request.urlopen(url, timeout=30) as response:
            result = response.read().decode()
        if result.startswith('error:'):
            raise RuntimeError(result)
        return result
    read = "local ffi=require('ffi');local m=PCSX.getMemPtr();local function r(a) return tonumber(ffi.cast('uint32_t*',m+a-0x80000000)[0]) end;"
    raw = {n: int(lua(read + f'return r({addresses[n]})')) for n in names}
    if not raw['MOD_FPS_TRIAL_VBLANKS']:
        raise RuntimeError('title trial has not completed')
    write = '' if mode is None else f"ffi.cast('uint32_t*',m+{addresses['MOD_FPS_MODE_RUN']}-0x80000000)[0]={mode};"
    lua(read + write + f'''
if WORKLOAD_CHECK then error('another workload capture is active') end
WORKLOAD_CHECK={{v=-6,rows={{}},bad=0,last=r({addresses['MOD_FPS_RENDERS']}),ticks=r({addresses['MOD_FPS_TICKS']})}}
WORKLOAD_CHECK.listener=PCSX.Events.createEventListener('GPU::Vsync',function()
 local s=WORKLOAD_CHECK;s.v=s.v+1
 if s.v<=0 then s.last=r({addresses['MOD_FPS_RENDERS']});s.ticks=r({addresses['MOD_FPS_TICKS']});s.hostStart=luv.hrtime();return end
 local count=r({addresses['MOD_FPS_RENDERS']})
 if count~=s.last then
  if (count-s.last)%4294967296~=1 then s.bad=s.bad+1 end
  s.rows[#s.rows+1]=s.v;s.last=count
 end
 if s.v>={refreshes} then s.endTicks=r({addresses['MOD_FPS_TICKS']});s.hostEnd=luv.hrtime();s.listener:remove();s.done=true end
end);return true''')
    start = time.monotonic()
    try:
        while lua('return WORKLOAD_CHECK.done and 1 or 0') != '1':
            if time.monotonic() - start > max(60, refreshes / 60 * 30):
                raise TimeoutError('no vblank progress')
            time.sleep(.25)
        host = float(lua('return tonumber(WORKLOAD_CHECK.hostEnd-WORKLOAD_CHECK.hostStart)/1e9'))
        rows = [int(v) for v in lua("return table.concat(WORKLOAD_CHECK.rows,',')").split(',') if v]
        bad = int(lua('return WORKLOAD_CHECK.bad'))
        ticks = int(lua('return (WORKLOAD_CHECK.endTicks-WORKLOAD_CHECK.ticks)%4294967296'))
        if bad:
            raise RuntimeError(f'vblank sampler missed {bad} render counter increments')
        intervals = [b - a for a, b in zip(rows, rows[1:])]
        return dict(title=raw, old_probe_mode=2 if raw['MOD_FPS_TRIAL_CPU_SPINS'] >= 8500 else 0,
                    mode=mode, refreshes=refreshes, swaps=len(rows),
                    guest_fps=len(rows)*60/refreshes, guest_logic_hz=ticks*60/refreshes,
                    host_seconds=host, observed_host_swaps_per_second=len(rows)/host,
                    intervals=dict(sorted(Counter(intervals).items())), swap_vblanks=rows)
    finally:
        lua('if WORKLOAD_CHECK then WORKLOAD_CHECK.listener:remove();WORKLOAD_CHECK=nil end;return true')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--exe', type=Path, required=True)
    parser.add_argument('--port', type=int, default=38090)
    parser.add_argument('--refreshes', type=int, default=600)
    parser.add_argument('--mode', type=int, choices=(0,2))
    parser.add_argument('--out', type=Path, required=True)
    args = parser.parse_args()
    if args.refreshes < 120:
        parser.error('--refreshes must be at least 120')
    result = capture(args.exe, args.port, args.refreshes, args.mode)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(result, indent=2)+'\n')
    print(json.dumps({k:v for k,v in result.items() if k!='swap_vblanks'}))


if __name__ == '__main__':
    main()
