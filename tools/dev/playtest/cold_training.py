#!/usr/bin/env python3
"""Full gym sessions with an imported partner; retain vsync traces and states.

Run once per RAM mode, using a freshly built disc and its matching executable.
Example: python3 tools/dev/playtest/cold_training.py build/everything.cue
  --exe build/everything/exe/SLUS_010.32 --out build/cold-training-2mb
Add --ram8 and choose a different --out and --port for the 8 MB run.

No training timers are shortened. The setup entry points are the same ones the
training scripts call. The normal session (pstat 246 = 0) is used.
"""
import argparse
import csv
import json
from pathlib import Path
import struct
import sys
import time

sys.path.insert(0, str(Path(__file__).resolve().parent))
from cold_cache import ColdTest, ROOT

CASES = [('hp',112,'TRN_setupHpTraining'), ('mp',112,'TRN_setupMpTraining'),
         ('offense',112,'TRN_setupOffenseTraining'), ('defense',112,'TRN_setupDefenseTraining'),
         ('speed',112,'TRN_setupSpeedTraining'), ('brains',112,'TRN_setupBrainsTraining'),
         ('hp-map99',99,'TRN2_setupHpTraining'), ('hp-map107',107,'TRN2_setupHpTraining')]


def session(test, name, screen, setup):
    e = test.e
    print(json.dumps(dict(phase='session',name=name,screen=screen,ram_mb=8 if test.args.ram8 else 2)),flush=True)
    test.lua('if GT then GT.v:remove();GT.r:remove();GT.c:remove();if GT.ret then GT.ret:remove() end;if GT.cret then GT.cret:remove() end;GT=nil end return true')
    e.run('load', str(test.out/'boot.state'))
    assert e.warp(screen),f'warp to {screen} failed'
    e.run('pause')
    test.switch(test.args.species)
    e.run('resume')
    time.sleep(3)  # allow the optional cache to fill in the normal field tick
    test.calls([('loadTrainingLibrary',(screen,))])
    e.run('resume')
    deadline=time.monotonic()+90
    while e.peek('TRN_LOADING_COMPLETE','B')!=0:
        assert time.monotonic()<deadline,'training overlay did not finish loading'
        time.sleep(.2)
    e.run('pause')
    test.calls([('writePStat',(246,0))])
    e.gs('set','partner.stats.hp=1000','partner.stats.mp=1000',
         'partner.stats.off=100','partner.stats.def=100','partner.stats.speed=100',
         'partner.stats.brain=100','partner.para.tiredness=0','partner.para.energyLevel=900')
    ram=e.ram();table=e.peek('PARTNER_ENTITY+8','I',ram)-0x80000000
    cold_slots=[s for s in range(0x14,0x1c) if struct.unpack_from('<I',ram,table+4*s)[0]&0x80000000]
    if name.startswith('hp'):assert 0x1b in cold_slots,cold_slots
    if name=='brains':assert 0x16 in cold_slots,cold_slots
    before = e.raw('PARTNER_ENTITY+0x38',20,ram).hex()
    rules='MOD_TRAIN_RULES' if screen==112 else 'MOD_TRAIN2_RULES'
    session_ticks=e.peek(rules+'+0x40','h',ram)
    assert session_ticks==1200,session_ticks
    state = 'TRAINING_STATE' if screen==112 else 'MAIN_D_801353BD'
    timer='MAIN_D_8013537A' if screen==112 else 'MAIN_D_801353C2'
    trace = test.out/f'{name}.csv'
    test.count_reads()
    a=e.A
    # EntityAnim offsets are relative to Entity, including its 12-byte header.
    test.lua(f'''
if GT then GT.v:remove();GT.r:remove();GT.c:remove();if GT.ret then GT.ret:remove() end;if GT.cret then GT.cret:remove() end end
GT={{vcount=0,peak=0,done=false,lines={{'vsync,state,complete,game_state,anim,frame,frames,flags,pending,timer'}},played={{}},waits={{}},wait=0,maxwait=0,blocked={{}},starts={{}}}}
local m=PCSX.getMemPtr()
local function b(a) return tonumber(m[a%0x200000]) end
local function h(a) return b(a)+256*b(a+1) end
local function w(a) return h(a)+65536*h(a+2) end
GT.v=PCSX.Events.createEventListener('GPU::Vsync',function()
 GT.vcount=GT.vcount+1
 GT.peak=math.max(GT.peak,h({a(timer)}))
 local p={a('PARTNER_ENTITY')};local pending=w({a('MOD_COLD_PENDING')})
 local anim=b(p+0x2e);local frame=h(p+0x1c);local frames=h(p+0x1e);local flags=b(p+0x30)
 if pending~=0 then GT.wait=GT.wait+1 elseif GT.wait>0 then
  GT.waits[#GT.waits+1]=GT.wait;GT.maxwait=math.max(GT.maxwait,GT.wait);GT.wait=0
 end
 if pending==0 and frame>1 and flags%2==1 then GT.played[anim]=true end
 GT.lines[#GT.lines+1]=table.concat({{GT.vcount,b({a(state)}),w({a('TRAINING_COMPLETE')}),b({a('GAME_STATE')}),anim,frame,frames,flags,pending,h({a(timer)})}},',')
 if GT.armed and w({a('TRAINING_COMPLETE')})==1 then GT.done=true;PCSX.pauseEmulator() end
end)
GT.r=PCSX.addBreakpoint({a('readFileSectors')},'Exec',4,'gym-blocking-read',function()
 local regs=PCSX.getRegisters()
 if regs.GPR.n.a1~={a('COLD_ANIM_BUFFER')} then return end
 local began=GT.vcount
 GT.ret=PCSX.addBreakpoint(regs.GPR.n.ra,'Exec',4,'gym-read-return',function()
  GT.blocked[#GT.blocked+1]=GT.vcount-began;GT.ret:remove();GT.ret=nil
 end)
end)
GT.c=PCSX.addBreakpoint({a('loadColdAnimation')},'Exec',4,'gym-cold-start',function()
 local regs=PCSX.getRegisters();local began=GT.vcount
 GT.cret=PCSX.addBreakpoint(regs.GPR.n.ra,'Exec',4,'gym-cold-return',function()
  GT.starts[#GT.starts+1]=GT.vcount-began;GT.cret:remove();GT.cret=nil
 end)
end)
return 'armed'
''')
    e.run('save',str(test.out/f'{name}-before.state'))
    test.calls([(setup,(screen,))])
    test.lua('GT.armed=true;PCSX.resumeEmulator();return true')
    deadline=time.monotonic()+480
    clip_saved=False
    tally_confirmed=False
    while test.lua('return GT.done')!='true':
        if not clip_saved and test.lua('return GT.played[27] or GT.played[22] or false')=='true':
            e.run('save',str(test.out/f'{name}-playing.state'))
            e.run('shot',str(test.out/f'{name}-playing.png'));clip_saved=True
        # The normal results box waits for a face-button edge. Confirm only
        # after the full session timer has run, so no work is skipped.
        if not tally_confirmed and int(test.lua('return GT.peak'))>=session_ticks-1:
            if e.peek('UI_BOX_DATA+54','h')==1:
                e.press('CONFIRM',12);tally_confirmed=True
        if time.monotonic()>deadline:
            e.run('pause')
            trace.write_text(test.lua("return table.concat(GT.lines,'\\n')")+'\n')
            e.run('save',str(test.out/f'{name}-timeout.state'))
            e.run('shot',str(test.out/f'{name}-timeout.png'))
            raise RuntimeError(f'{name}: session timeout')
        time.sleep(.5)
    trace.write_text(test.lua("return table.concat(GT.lines,'\\n')")+'\n')
    after=e.raw('PARTNER_ENTITY+0x38',20,e.ram()).hex()
    result=dict(name=name,screen=screen,setup=setup,species=test.args.species,ram_mb=8 if test.args.ram8 else 2,
                configured_session_ticks=session_ticks,cold_training_slots=cold_slots,before_stats=before,after_stats=after,
                stat_deltas=[b-a for a,b in zip(struct.unpack('<10h',bytes.fromhex(before)),struct.unpack('<10h',bytes.fromhex(after)))],complete=e.peek('TRAINING_COMPLETE','i'),
                vsyncs=int(test.lua('return GT.vcount')),max_queued_wait_vsyncs=int(test.lua('return GT.maxwait')),
                played=json.loads(test.lua("local t={} for k in pairs(GT.played) do t[#t+1]=k end return '['..table.concat(t,',')..']'")),
                cold_start_vsyncs=json.loads(test.lua("return '['..table.concat(GT.starts,',')..']'")),
                blocking_read_vsyncs=json.loads(test.lua("return '['..table.concat(GT.blocked,',')..']'")),
                reads=test.counts(),cache_type=e.peek('MOD_COLD_CACHE_TYPE','i'))
    e.run('save',str(test.out/f'{name}-after.state'))
    e.run('shot',str(test.out/f'{name}-after.png'))
    assert result['complete']==1 and before!=after,result
    samples=list(csv.DictReader(trace.read_text().splitlines()))
    assert any(int(r['timer'])==session_ticks-1 for r in samples),name
    pending=[r for r in samples if int(r['pending'])]
    assert all(int(r['frames'])==0x7fff and not int(r['flags'])&1 for r in pending),pending[:3]
    if name.startswith('hp') or name=='brains':
        if test.args.ram8:
            assert not pending,result
            assert result['reads']['clip_reads']==0 and not result['blocking_read_vsyncs'],result
            assert result['cache_type']==test.args.species,result
        else:assert pending and result['reads']['async']==1,result
    stat={'hp':8,'mp':9,'offense':0,'defense':1,'speed':2,'brains':3}.get(name,8)
    assert result['stat_deltas'][stat]>0,result
    assert (result['cache_type']>=0)==test.args.ram8,result
    expected=0x1b if name.startswith('hp') else {'mp':0,'defense':0x25,'speed':4,'brains':0x16}.get(name)
    if name=='offense':
        definition=json.loads(next((Path(e.exe).parent.parent/'species').glob(f'{test.args.species}-*.json')).read_text())
        expected=definition['partner']['training']['animation']
    assert expected in result['played'],result
    (test.out/f'{name}.json').write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps(result),flush=True)
    return result


def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('disc');ap.add_argument('--exe',required=True);ap.add_argument('--out',type=Path,required=True)
    ap.add_argument('--port',type=int,default=41154);ap.add_argument('--species',type=int,default=241)
    ap.add_argument('--boot-state',type=Path,help='reuse a settled boot state from this exact disc and RAM mode')
    ap.add_argument('--ram8',action='store_true');ap.add_argument('--case',choices=[c[0] for c in CASES],action='append')
    args=ap.parse_args();test=ColdTest(args);e=test.e
    e.start(str(ROOT/'tools/dev/saves/corpus/20261027-d2796814.mcd'))
    try:
        if args.boot_state:
            e.run('pause');e.run('load',str(args.boot_state.resolve()))
        else:
            assert e.continue_game()==0 and e.in_control(),'Continue failed'
        # Continue can expose the control flags while initializeLoadedMap is
        # still finishing; let its final tamer-state reset finish before a warp.
        e.run('resume');time.sleep(8)
        assert e.in_control(),'no control after map initialization'
        e.run('pause');e.run('save',str(test.out/'boot.state'))
        rows=[session(test,*case) for case in CASES if not args.case or case[0] in args.case]
        (test.out/'results.json').write_text(json.dumps(rows,indent=2)+'\n')
        print('PASS',flush=True)
    finally:e.stop()


if __name__=='__main__':main()
