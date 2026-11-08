#!/usr/bin/env python3
"""Record captioned emulator motion clips and real technique attempts.

Set EMU_PORT and DW_SYMS as for species_proof.py. Field playback uses the
engine's animation entry point with the partner AI held, including cold clips;
battle mode equips each technique and records the normal combat engine.
Disc assets and videos stay in the ignored output directory.
"""
import argparse
import json
import os
from pathlib import Path
import subprocess
import struct
import sys
import threading
import time

ROOT = Path(__file__).resolve().parents[3]
sys.path[:0] = [str(ROOT), str(ROOT/'tools'), str(ROOT/'tools/playtest')]
from tools.image import Image, ImageDraw, ImageFont
from tools.dev.playtest import species_proof as P
import technique_proof as T


def command(args):
    subprocess.run(list(map(str,args)),check=True)


def caption(source, target, text, start=0, duration=None):
    label=target.with_suffix('.png')
    picture=Image.new('RGB',(640,72),'black')
    draw=ImageDraw.Draw(picture)
    font=ImageFont.truetype('DejaVuSans.ttf',21)
    for i,line in enumerate(text.splitlines()):
        draw.text((12,8+28*i),line,font=font,fill='white')
    picture.save(label)
    args=['ffmpeg','-y','-loglevel','error','-ss',str(max(0,start)),'-i',source]
    args+=['-i',label]
    if duration is not None: args+=['-t',str(duration)]
    args+=['-filter_complex',"[0:v]fps=30,pad=640:552:0:72:color=black[game];[game][1:v]overlay=0:0",
           '-c:v','libx264','-crf','23','-pix_fmt','yuv420p','-c:a','aac','-movflags','+faststart',target]
    command(args)


def start_slot(slot):
    gl=P.EMU.A('gameLoop'); fn=P.EMU.A('partnerStartAnimation')
    script=f"""
if SV and SV.bp then SV.bp:remove() end
SV={{phase=0}}
SV.bp=PCSX.addBreakpoint({gl},'Exec',4,'motion-review',function()
 local r=PCSX.getRegisters()
 if SV.phase==0 then
  SV.saved=r.GPR.n.ra; r.GPR.n.a0={slot}; r.GPR.n.ra={gl}; r.pc={fn}; SV.phase=1
 else
  r.GPR.n.ra=SV.saved; SV.bp:remove(); SV.phase=2
 end
end)
return 'armed'
"""
    P.EMU.run('lua',script)
    for _ in range(40):
        if P.EMU.run('lua','return SV.phase').strip()=='2': return
        time.sleep(.1)
    raise RuntimeError('animation call did not complete')


def stage():
    entity=P.EMU.A('PARTNER_ENTITY')
    ram=P.EMU.ram()
    pos=struct.unpack_from('<I',ram,(entity&0x1fffff)+4)[0]
    # Screen 1's entry has an open patch to the right of the tamer. Hold
    # entity travel so a whole run/dash remains visible on the fixed camera.
    code=f"""
local ffi=require('ffi')
local function put(a,v) ffi.cast('int32_t*',PCSX.getMemPtr()+bit.band(a,0x1fffff))[0]=v end
if STAGE and STAGE.bp then STAGE.bp:remove() end
STAGE={{}}
STAGE.bp=PCSX.addBreakpoint({P.EMU.A('gameLoop')},'Exec',4,'review-stage',function()
 put({pos+120},-1500);put({pos+128},300)
 put({entity+16},{-1500<<15});put({entity+24},{300<<15})
end)
return 'staged'
"""
    P.EMU.run('lua',code)


def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('cue');ap.add_argument('digi');ap.add_argument('out',type=Path)
    ap.add_argument('--card',required=True);ap.add_argument('--label',required=True)
    ap.add_argument('--id',type=int,default=226)
    ap.add_argument('--state',help='reuse a checkpoint from this exact disc')
    ap.add_argument('--slots',help='comma-separated hexadecimal battle slots to retry')
    ap.add_argument('--mode',choices=['field','follow','battle'],required=True)
    a=ap.parse_args(); a.out.mkdir(parents=True,exist_ok=True)
    os.environ['EMU_AUDIO']=str((a.out/'audio.raw').resolve())
    if a.mode=='field':
        factory=P.emulator
        def interpreter(cue):
            emu=factory(cue);emu.env['EMU_ARGS']='-interpreter -debugger'
            return emu
        P.emulator=interpreter
    if a.state:
        P.EMU=P.emulator(a.cue);P.EMU.start(None);P.EMU.run('load',a.state)
    else:
        assert P.boot(a.cue,a.card),'could not Continue'
        P.lab_evolve(a.id,str(a.out))
    assert P.partner_type()==a.id,'evolution failed'
    assert len(P.EMU.ram())==0x200000
    clips=[]; evidence=[]
    def record(path,secs):
        return P.EMU.run('record',str(path),str(secs),'30')
    try:
        if a.mode=='field':
            if P.EMU.peek('CURRENT_SCREEN','h')!=1:
                assert P.EMU.warp(1),'could not reach open review screen'
            P.mset('PARTNER_STATE=12','PARTNER_PARA.condition=0','CAMERA_FOLLOW_PLAYER=0',
                   'PARTNER_ENTITY.digimonEntity.entity.posData[0].rotation.vy=512',
                   'PARTNER_ENTITY.digimonEntity.entity.posData[0].location.vy=0',
                   'PARTNER_ENTITY.digimonEntity.entity.anim.locY=0')
            stage()
            P.seq('wait 2')
            P.EMU.run('save',str(a.out/'stage.state'))
            actions=[(0,'Idle',4),(2,'Walk - engine slot playback',4),
                     (4,'Run - engine slot playback',4),(40,'Hit from front',4),
                     (41,'Knocked back',4),(43,'Faint / die',5),
                     (44,'Get up',4),(1,'Poor-condition idle',4),
                     (18,'Tired',4),(9,'Sleeping',5),
                     (49 if a.id==48 else 57,'Counter - slot playback',4)]
            if a.id==48:
                actions += [(47,'Dynamite Kick',4),(48,'Megaton Punch',4),
                            (50,'Buster Dive',5),(51,'Tremar',4),
                            (54,'Static Elect',4),(55,'Megalo Spark',4),
                            (56,'Fist of the Beast King / cast reference',4)]
            if a.slots:
                wanted={int(s,16) for s in a.slots.split(',')}
                actions=[r for r in actions if r[0] in wanted]
            for slot,name,secs in actions:
                raw=a.out/f'raw-{slot}.mp4'
                # Capture before calling so the first displayed pose survives.
                worker=threading.Thread(target=record,args=(raw,secs));worker.start()
                start_slot(slot)
                worker.join()
                actual=P.mem(P.ANIM,P.FRAME)
                evidence.append(dict(action=name,slot=slot,observed=actual))
                clip=a.out/f'clip-{slot:02}.mp4'
                caption(raw,clip,f'{a.label}\n{name}')
                clips.append(clip)
        elif a.mode=='follow':
            P.mset('PARTNER_STATE=1','PARTNER_PARA.condition=0','PARTNER_PARA.tiredness=0',
                   'CAMERA_FOLLOW_PLAYER=1')
            raw=a.out/'following.mp4'
            worker=threading.Thread(target=record,args=(raw,16));worker.start()
            def drive():
                P.EMU.press('RIGHT',60)
                P.EMU.api('/api/v1/lua/press?button=R1')
                try:
                    P.EMU.press('RIGHT',100);P.EMU.press('LEFT',100)
                finally:P.EMU.api('/api/v1/lua/release?button=R1')
                P.EMU.press('LEFT',60)
            driving=threading.Thread(target=drive);driving.start()
            while worker.is_alive():
                evidence.append(P.mem(P.ANIM,P.FRAME,'GAME_STATE'))
                worker.join(timeout=.25)
            driving.join()
            clip=a.out/'clip-follow.mp4'
            caption(raw,clip,f'{a.label}\nLive walking / running with partner AI',duration=12)
            clips.append(clip)
        else:
            _,_,recs=T.species.read_archive(a.digi)
            moves=recs[a.id]['para']['moves']; names=T.species.names('techs')
            if P.game_state()!=1:
                assert T.start_battle(moves),'battle did not start'
            P.EMU.run('save',str(a.out/'battle.state'))
            fin=next(46+i for i,m in enumerate(moves) if 58<=m<=112)
            requests=[(46+i,m) for i,m in enumerate(moves) if m!=255 and not 58<=m<=112]+[(fin,moves[fin-46])]
            if a.slots:
                wanted={int(s,16) for s in a.slots.split(',')}
                requests=[r for r in requests if r[0] in wanted]
            for slot,move in requests:
                raw=a.out/f'raw-{slot}.mp4'; seen=[]
                # Observe the slot while the standard damage proof runs.
                mem=P.mem
                def observe(*args):
                    values=mem(*args)
                    if values.get(P.ANIM)==slot and not seen: seen.append(time.time())
                    return values
                P.mem=observe
                started=time.time()
                worker=threading.Thread(target=record,args=(raw,28));worker.start()
                if slot==fin: played,damage=T.finisher(slot,str(a.out),a.id)
                else:
                    T.equip(slot)
                    if move==45:
                        # Counter is never chosen by normal attack AI. It
                        # reacts to a missed incoming melee hit; provide one
                        # instead of waiting for an unusable queued attack.
                        key='NPC_ENTITIES[0].digimonEntity.entity.type'
                        enemy=P.mem(key)[key]
                        melee=next(46+i for i,m in enumerate(recs[enemy]['para']['moves'])
                                   if m!=255 and m!=45 and T.TD[str(m)]['range']==1)
                        P.mset('PARTNER_ENTITY.digimonEntity.stats.base.speed=999',
                               'NPC_ENTITIES[0].digimonEntity.stats.current.currentMP=4000',
                               f'NPC_ENTITIES[0].digimonEntity.stats.base.moves[0]={melee}',
                               *[f'NPC_ENTITIES[0].digimonEntity.stats.base.moves[{i}]=255' for i in (1,2,3)])
                    played,damage=T.watch(slot,str(a.out),f'tech-{slot}',secs=20)
                # Keep this one fight alive while the capture finishes. The
                # damage observation above completes before these refills.
                while worker.is_alive():
                    P.mset(f'{T.HPK}=9999',
                           'PARTNER_ENTITY.digimonEntity.stats.current.currentHP=4000',
                           'PARTNER_ENTITY.digimonEntity.stats.current.currentMP=4000')
                    worker.join(timeout=1)
                P.mem=mem
                evidence.append(dict(action=names[move],slot=slot,played=played,damage=damage))
                if played:
                    clip=a.out/f'clip-{slot:02}.mp4'
                    timeline=json.loads(Path(str(raw)+'.frames.json').read_text())['frames']
                    moment=(seen[0] if seen else started)-.6
                    begin=next((f['video_seconds'] for f in timeline if f['wall_end']>=moment),0)
                    caption(raw,clip,f'{a.label}\n{names[move]} - battle',begin,8)
                    clips.append(clip)
                print(json.dumps(evidence[-1]),flush=True)
        listing=a.out/'concat.txt'
        listing.write_text(''.join(f"file '{p.resolve()}'\n" for p in clips))
        command(['ffmpeg','-y','-loglevel','error','-f','concat','-safe','0','-i',listing,
                 '-c','copy','-movflags','+faststart',a.out/'review.mp4'])
    finally:
        (a.out/'evidence.json').write_text(json.dumps(evidence,indent=2)+'\n')
        P.EMU.stop()


if __name__=='__main__':
    main()
