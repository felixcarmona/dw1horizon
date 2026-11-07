#!/usr/bin/env python3
"""Observe every condition, emitted GPU bounds and presented frames on 2 MB.

Uses a fixture saved by hpmp_bubbles on the supplied executable. Positions are
held as test fixtures; condition flags, animation and GPU rendering run normally.
"""
import argparse
import hashlib
import json
from pathlib import Path
import struct
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parents[3]
sys.path[:0] = [str(ROOT), str(ROOT / 'tools')]
from tools.dev.playtest.hpmp_bubbles import ProofEmu, elf_symbols, setup, settle, state, shot
from tools.dev.playtest.quick_care import position


def observer(e):
    code = r'''
      WORST={active=false,quads={},records={},vbl={},v=0,n=0,max=0}
      local m=PCSX.getMemPtr()
      local function u16(a) return tonumber(m[a])+256*tonumber(m[a+1]) end
      local function u32(a) return u16(a)+65536*u16(a+2) end
      local function s16(a) local v=u16(a);return v>=32768 and v-65536 or v end
      local function w32(a,v)
        v=v%4294967296
        for i=0,3 do m[a+i]=v%256;v=math.floor(v/256) end
      end
      WORST.pin=PCSX.addBreakpoint(@LOOP@,'Exec',4,'worst-fixture',function()
        if not WORST.pos then return end
        local pp=u32(@PARTNER@+4)-2147483648
        for i=1,3 do
          w32(pp+0x78+(i-1)*4,WORST.pos[i])
          w32(@PARTNER@+0x10+(i-1)*4,WORST.pos[i]*32768)
        end
      end)
      WORST.entry=PCSX.addBreakpoint(@ENTRY@,'Exec',4,'worst-render',function()
        WORST.active=true;WORST.quads={};WORST.resources={};WORST.first=u32(@PACKET@)-2147483648
        if not WORST.ret then
          WORST.ret=PCSX.addBreakpoint(tonumber(PCSX.getRegisters().GPR.n.ra),'Exec',4,'worst-return',function()
            if not WORST.active then return end
            WORST.active=false
            local cursor=WORST.first
            local finish=u32(@PACKET@)-2147483648
            local ox=u32(@OX@);local oy=u32(@OY@)
            while cursor<finish do
              local words=tonumber(m[cursor+3]);local cmd=tonumber(m[cursor+7])
              assert(words>0 and words<=12,'unexpected GPU packet')
              local l,r,t,b=10000,-10000,10000,-10000
              if words==9 and (cmd==44 or cmd==46 or cmd==45 or cmd==47) then
                for _,o in ipairs({8,16,24,32}) do
                  local x=s16(cursor+o)+ox;local y=s16(cursor+o+2)+oy
                  l=math.min(l,x);r=math.max(r,x);t=math.min(t,y);b=math.max(b,y)
                end
                WORST.quads[#WORST.quads+1]={l,t,r,b}
                local u=tonumber(m[cursor+12]);local v=tonumber(m[cursor+13])
                if u==224 and (v==192 or v==208) then
                  WORST.resources[#WORST.resources+1]=string.format('[%d,%d,%d,%d,%d]',v==192 and 6 or 7,l,t,r,b)
                end
              elseif words==4 and cmd>=100 and cmd<=103 then
                l=s16(cursor+8)+ox;t=s16(cursor+10)+oy
                r=l+u16(cursor+16);b=t+u16(cursor+18)
                WORST.quads[#WORST.quads+1]={l,t,r,b}
              end
              cursor=cursor+(words+1)*4
            end
            local l,t,r,b=10000,10000,-10000,-10000
            for _,q in ipairs(WORST.quads) do
              l=math.min(l,q[1]);t=math.min(t,q[2]);r=math.max(r,q[3]);b=math.max(b,q[4])
            end
            WORST.report=string.format('{"clock":%d,"condition":%d,"badge":%d,"phase":%d,"quads":%d,"bounds":[%d,%d,%d,%d],"resources":[%s]}',
              u32(@CLOCK@),u32(@PARA@),u32(@BADGE@),u32(@PHASE@),#WORST.quads,l,t,r,b,table.concat(WORST.resources,','))
          end)
        end
      end)
      WORST.vsync=PCSX.Events.createEventListener('GPU::Vsync',function() WORST.v=WORST.v+1 end)
      WORST.swap=PCSX.addBreakpoint(@SWAP@,'Exec',4,'worst-presented',function()
        if WORST.n>=WORST.max or not WORST.report then return end
        local s=PCSX.GPU.takeScreenShot()
        assert(s.width==320 and s.height==240,'non-native frame')
        WORST.file:writeMoveSlice(s.data);WORST.n=WORST.n+1
        WORST.records[WORST.n]=WORST.report;WORST.vbl[WORST.n]=WORST.v
        if WORST.n==WORST.max then WORST.file:close() end
      end)
    '''
    for key, name, physical in (
        ('LOOP','gameLoop',False),('PARTNER','PARTNER_ENTITY',True),
        ('ENTRY','renderConditionRingObject',False),('PACKET','GsOUT_PACKET_P',True),
        ('CLOCK','MOD_RING_CLOCK',True),('PARA','PARTNER_PARA',True),
        ('BADGE','MOD_RING_BADGE',True),('PHASE','MOD_RING_T',True),
        ('OX','DRAWING_OFFSET_X',True),('OY','DRAWING_OFFSET_Y',True),('SWAP','GsSortClear',False)):
        addr=e.A(name);code=code.replace('@'+key+'@',str(addr&0x1fffff if physical else addr))
    e.run('lua',code)


def anchor(e,xyz):
    e.run('lua','WORST.pos={'+','.join(str(round(v)) for v in xyz)+'}')
    passes=e.peek('MOD_RING_SHOWN','i');end=time.monotonic()+20
    while e.peek('MOD_RING_SHOWN','i')<passes+4:
        assert time.monotonic()<end,'no field renders'
        e.wait(.05)
    xy=struct.unpack('<2h',struct.pack('<I',e.peek('MOD_RING_SHOWN+4','I')))
    return (xy[0]+e.peek('DRAWING_OFFSET_X','i'),xy[1]+e.peek('DRAWING_OFFSET_Y','i'))


def place(e,xyz,target):
    for _ in range(5):
        p=anchor(e,xyz)
        if abs(p[0]-target[0])+abs(p[1]-target[1])<=2:return xyz,p
        px=anchor(e,[xyz[0]+400,xyz[1],xyz[2]])
        pz=anchor(e,[xyz[0],xyz[1],xyz[2]+400])
        a,b,c,d=px[0]-p[0],pz[0]-p[0],px[1]-p[1],pz[1]-p[1]
        det=a*d-b*c;assert det
        dx,dy=target[0]-p[0],target[1]-p[1]
        xyz=[xyz[0]+round(400*(dx*d-b*dy)/det),xyz[1],xyz[2]+round(400*(a*dy-dx*c)/det)]
    return xyz,anchor(e,xyz)


def zoom(out,name,bounds):
    # Keep the entire crop inside the native framebuffer at the screen edges.
    from tools.image import Image
    im=Image.open(out/(name+'.png'))
    x=max(0,min(200,(bounds[0]+bounds[2])//2-60))
    y=max(0,min(144,(bounds[1]+bounds[3])//2-48))
    im.crop((x,y,x+120,y+96)).resize((480,384),Image.Resampling.NEAREST).save(out/(name+'-4x.png'))


def resource_fill(raw, records):
    """Check captured framebuffer colours inside the actual resource GPU quads."""
    minima={6:[10000,10000],7:[10000,10000]}
    with raw.open('rb') as stream:
        for record in records:
            frame=stream.read(320*240*2);assert len(frame)==320*240*2
            assert sorted(q[0] for q in record['resources'])==[6,7]
            for which,left,top,right,bottom in record['resources']:
                colour=empty=0
                for y in range(max(0,top),min(240,bottom)):
                    for x in range(max(0,left),min(320,right)):
                        c=struct.unpack_from('<H',frame,2*(y*320+x))[0]
                        r,g,b=c&31,(c>>5)&31,(c>>10)&31
                        colour+=int(r>g+3 and r>b+3 if which==6 else b>r+3 and b>g)
                        empty+=int(max(r,g,b)-min(r,g,b)<=3 and 7<=max(r,g,b)<=14)
                assert colour>=2,(which,'lost coloured fill',record['bounds'])
                assert empty>=4,(which,'lost empty area',record['bounds'])
                minima[which]=[min(minima[which][0],colour),min(minima[which][1],empty)]
        assert not stream.read(1),'extra framebuffer data'
    return {str(k):{'minimum_coloured_pixels':v[0],'minimum_empty_pixels':v[1]} for k,v in minima.items()}


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('disc');p.add_argument('--exe',required=True);p.add_argument('--card',required=True)
    p.add_argument('--fixture',type=Path,default=Path('build/hpmp-proof'))
    p.add_argument('--out',type=Path,required=True);p.add_argument('--allow-clipping',action='store_true')
    p.add_argument('--check-resource-fill',action='store_true',help='Check visible red/blue fill and empty areas in every captured frame')
    p.add_argument('--port',type=int,default=38864);p.add_argument('--frames',type=int,default=120)
    a=p.parse_args();a.out=a.out.resolve();a.out.mkdir(parents=True,exist_ok=True)
    expected=json.loads((a.fixture/'fixture.json').read_text())['exe_sha256']
    assert expected==hashlib.sha256(Path(a.exe).read_bytes()).hexdigest()
    e=ProofEmu(a.disc,a.exe,a.port,str(a.out/'emu'));e.env['EMU_ARGS']='-interpreter -debugger'
    for name,(addr,_,_) in elf_symbols(a.exe+'.elf').items():e.table.setdefault(name,addr)
    result={'exe_sha256':expected,'cases':{}}
    try:
        e.start(a.card);e.run('load',str((a.fixture/'base.state').resolve()));e.run('resume')
        assert len(e.ram())==0x200000
        assert not json.loads(e.api('/api/v1/execution-flow'))['8mb']
        result['ram_bytes']=0x200000
        setup(e,290,290,True)
        e.run('pause')
        e.gs('set','partner.para.condition=111','partner.para.tiredness=80',
             'partner.para.foodLevel=0','partner.para.poopLevel=0','partner.para.poopingTimer=2000',
             'partner.para.happiness=-50','partner.para.sicknessTimer=0','partner.para.injuryTimer=0',
             'gametime_running=1')
        e.poke('MOD_CLOCK',struct.pack('<h',-1))
        settle(e);assert state(e)['active']==list(range(8)),state(e)
        observer(e);initial=position(e,'PARTNER_ENTITY')
        for name,target in (('centre',(160,90)),('left',(8,90)),('right',(312,90)),('top',(160,-2)),
                            ('top-left',(8,-2)),('top-right',(312,-2))):
            xyz,projected=place(e,initial,target);got=state(e)
            assert got['active']==list(range(8)) and got['badge']==4,got
            shot(e,a.out,name,width=120,height=96)
            raw=a.out/(name+'.raw')
            e.run('lua',f"WORST.n=0;WORST.records={{}};WORST.vbl={{}};WORST.file=Support.File.open('{raw}','TRUNCATE');WORST.max={a.frames}")
            end=time.monotonic()+180
            while int(e.run('lua','return WORST.n').strip())<a.frames:
                assert time.monotonic()<end,'presented capture timed out'
                e.wait(.25)
            records=json.loads(e.run('lua',"return '['..table.concat(WORST.records,',')..']'").strip())
            (Path(str(raw)+'.vbl')).write_text(e.run('lua',"return table.concat(WORST.vbl,' ')").strip())
            assert all(r['condition']==111 and r['badge']==4 and 17<=r['quads']<=20 for r in records),records[:2]
            bounds=[min(r['bounds'][i] for r in records) if i<2 else max(r['bounds'][i] for r in records) for i in range(4)]
            zoom(a.out,name,bounds)
            clipped=bounds[0]<0 or bounds[1]<0 or bounds[2]>320 or bounds[3]>240
            clock_right=e.peek('CLOCK_OFFSET_X','h')+160+50
            clock_overlap=bounds[0]<clock_right and bounds[2]>clock_right-52 and bounds[1]<84 and bounds[3]>16
            result['cases'][name]={'position':xyz,'projected_head':projected,'state':got,
                'bounds':bounds,'clipped':clipped,'clock_overlap':clock_overlap,'frames':records}
            if a.check_resource_fill:
                result['cases'][name]['resource_fill']=resource_fill(raw,records)
            print(name,'bounds',bounds,'clipped',clipped,'clock overlap',clock_overlap,flush=True)
            subprocess.run([sys.executable,str(ROOT/'tools/dev/presented_frames.py'),'mp4',str(raw),str(a.out/(name+'.mp4'))],check=True)
            if not a.allow_clipping:assert not clipped and not clock_overlap,(name,bounds,clock_overlap)
        result['passed']=True
    finally:
        (a.out/'result.json').write_text(json.dumps(result,indent=2)+'\n')
        e.stop()


if __name__=='__main__':main()
