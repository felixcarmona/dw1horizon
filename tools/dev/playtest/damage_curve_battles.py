#!/usr/bin/env python3
"""Run controlled late-field, Machinedramon and tournament battles on 2 MB.

Starts real battles with actual placed/generated enemy stats; sets only a
reproducible partner (MetalEtemon, 4000 Offense, 800 Defense, Megaton Punch).
Traces damage function inputs, random rolls and returns without changing them.
Use --old for the baseline disc. No savestate crosses executable versions.
"""
import argparse
import hashlib
import json
from pathlib import Path
import re
import struct
import sys
import time

ROOT=Path(__file__).resolve().parents[3]
sys.path[:0]=[str(ROOT),str(ROOT/'tools')]
from tools.dev.saves.releases import Emu
from tools.dev.playtest.birdramon_recruitment import field_card, free_heap
from tools.langpatch import elf_symbols
from tools import battle_audit as B


def arm_call(e,name,args):
    vals=list(args)+[0]*(4-len(args))
    e.run('lua',f'''
if DCall and DCall.bp then DCall.bp:remove() end
DCall={{phase=0}}
DCall.bp=PCSX.addBreakpoint({e.A('gameLoop')},'Exec',4,'damage-call',function()
 local r=PCSX.getRegisters()
 if DCall.phase==1 then r.GPR.n.ra=DCall.saved;DCall.phase=2;DCall.bp:remove();return end
 if DCall.phase==0 then
  DCall.saved=r.GPR.n.ra;r.GPR.n.a0={vals[0]};r.GPR.n.a1={vals[1]};r.GPR.n.a2={vals[2]};r.GPR.n.a3={vals[3]}
  r.GPR.n.ra={e.A('gameLoop')};r.pc={e.A(name)};DCall.phase=1
 end
end)
return 'armed' ''')


def trace(e,exe,kind,out):
    function='STD_calculateDamage' if kind=='tournament' else 'BTL_calculateDamage'
    overlay='STD_REL.BIN' if kind=='tournament' else 'BTL_REL.BIN'
    base='std_START' if kind=='tournament' else 'btl_START'
    data=Path(exe).with_name(overlay).read_bytes()
    addr=e.A(function)
    words=struct.unpack_from('<4I',data,addr-e.A(base))
    guard=' and '.join(f'u32({addr+4*i})=={w}' for i,w in enumerate(words))
    code=f'''
DC={{hits={{}},bps={{}}}}
local mem=PCSX.getMemPtr()
local function u8(a)return tonumber(mem[a-0x80000000])end
local function u16(a)return u8(a)+256*u8(a+1)end
local function s16(a)local v=u16(a);return v>=32768 and v-65536 or v end
local function u32(a)return u16(a)+65536*u16(a+2)end
DC.bps[#DC.bps+1]=PCSX.addBreakpoint({addr},'Exec',4,'damage-entry',function()
 if not ({guard}) then return end
 local regs=PCSX.getRegisters().GPR.n;local a=regs.a0;local b=regs.a1;local move=regs.a2%65536
 if a<0x80000000 or b<0x80000000 or move>=58 then return end
 local power=s16({e.A('MOVE_DATA')}+move*16+4)
 local x={{u32(a),u32(b),move,s16(a+56),s16(b+58),power,a==u32({e.A('ENTITY_TABLE')}+4) and 1 or 0,-1,0}}
 DC.current=x
 local bp
 bp=PCSX.addBreakpoint(regs.ra,'Exec',4,'damage-return',function()
  bp:remove();x[9]=PCSX.getRegisters().GPR.n.v0;DC.hits[#DC.hits+1]=x;DC.current=nil
 end)
 DC.bps[#DC.bps+1]=bp
end)
DC.bps[#DC.bps+1]=PCSX.addBreakpoint({e.A('randomLimit')},'Exec',4,'damage-roll',function()
 if not DC.current then return end
 local r=PCSX.getRegisters().GPR.n
 if r.a0~=21 then return end
 local x=DC.current;local bp
 bp=PCSX.addBreakpoint(r.ra,'Exec',4,'damage-roll-return',function()
  bp:remove();x[8]=PCSX.getRegisters().GPR.n.v0+90
 end)
 DC.bps[#DC.bps+1]=bp
end)
return 'trace armed'
'''
    (out/(kind+'-trace.lua')).write_text(code)
    e.run('lua',code)


def hits(e):
    text=e.run('lua',"local out={} for _,x in ipairs(DC.hits) do out[#out+1]='DAMAGE,'..table.concat(x,',') end return table.concat(out,';')")
    return [list(map(int,m.split(','))) for m in re.findall(r'DAMAGE,([0-9,\-]+)',text)]


def fixture(e, close=False, enemy_slot=0):
    # Original resident DigimonPara is 52 bytes: moves start at byte 35.
    ram=e.ram();para=e.A('DIGIMON_DATA')-0x80000000+65*52
    moves=list(ram[para+35:para+51]);slot=moves.index(46)
    e.run('pause')
    try:
        e.poke('PARTNER_ENTITY+0x38',struct.pack('<4h',4000,800,700,700))
        e.poke('PARTNER_ENTITY+0x40',bytes([30,0,0,0,0x2e+slot,255,255,255]))
        e.poke('PARTNER_ENTITY+0x48',struct.pack('<4h',12000,12000,12000,12000))
        e.poke('PARTNER_ENTITY+0x58',struct.pack('<4I',0,1<<14,0,0))
        e.poke('MOD_OPT_DIFFICULTY',struct.pack('<i',0))
        e.poke('PARTNER_PARA',bytes(4))
        if close:
            # A direct scripted start must not leave the partner behind a wall
            # at the map's arrival point. Only initial partner position changes.
            ram=e.ram()
            npc=e.peek('NPC_ENTITIES+'+str(enemy_slot*0x68+4),'I',ram)
            x,y,z=struct.unpack_from('<3i',ram,(npc-0x80000000)+0x78)
            x+=300;z+=100
            pd=e.peek('PARTNER_ENTITY+4','I',ram)
            e.run('poke',hex(pd+0x78),struct.pack('<3i',x,y,z).hex())
            e.poke('PARTNER_ENTITY+0x10',struct.pack('<3i',x<<15,y<<15,z<<15))
    finally:e.run('resume')


def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('disc');ap.add_argument('--exe',required=True)
    ap.add_argument('--card',default='tools/dev/saves/corpus/20261027-d2796814.mcd')
    ap.add_argument('--out',type=Path,required=True);ap.add_argument('--port',type=int,default=44326)
    ap.add_argument('--old',action='store_true');ap.add_argument('--seconds',type=int,default=600)
    ap.add_argument('--cases',default='field,boss,tournament')
    ap.add_argument('--resume',action='store_true',help='reuse this output folder’s field checkpoint (same executable only)')
    a=ap.parse_args();a.out=a.out.resolve();a.out.mkdir(parents=True,exist_ok=True)
    e=Emu(a.disc,a.exe,a.port,str(a.out/'emu'))
    for name,(addr,_,_) in elf_symbols(a.exe+'.elf').items():e.table.setdefault(name,addr)
    e.env['EMU_ARGS']='-interpreter -debugger'
    rules=B.load('content/tables/battle-formulas.json')['battleFormulas']['damage']
    species={s['id']:s for s in (B.load(p.relative_to(ROOT)) for p in (ROOT/'content/species').glob('*.json'))}
    factors=B.load('content/tables/type-factors.json')['typeFactors']
    results=json.loads((a.out/'results.json').read_text()) if a.resume and (a.out/'results.json').exists() else []
    results=[r for r in results if r['case'] not in a.cases.split(',')]
    def note(**row):print(json.dumps(row),flush=True)
    try:
        card=field_card(a.card,str(a.out/'test.mcd'),partner_type=65)
        e.start(card)
        checkpoint=str(a.out/'field.state')
        identity=hashlib.sha256(Path(a.exe).read_bytes()).hexdigest()
        stamp=a.out/'checkpoint-exe.sha256'
        if a.resume:
            assert stamp.read_text().strip()==identity,'checkpoint executable differs'
            e.run('load',checkpoint)
        else:
            assert e.continue_game()==0,'Continue failed'
            e.gs('set','gametime_running=0','hour=10','minute=0')
            e.run('save',checkpoint);stamp.write_text(identity+'\n')
        assert len(e.ram())==0x200000
        for kind in a.cases.split(','):
            e.run('load',checkpoint);time.sleep(1)
            if kind=='boss':e.gs('pstat','16','1')
            screen={'field':153,'boss':104,'tournament':208}[kind]
            assert e.warp(screen),f'{kind} warp failed'
            if kind=='boss':
                e.gs('approach','0','600')
                # The real story removes Analogman before fighting. Hide its
                # actor here too; it must not enter the unrelated NPC flee wait.
                e.poke('NPC_ENTITIES+0x9c',bytes(2))
                e.poke('MOD_OPT_QUICK_BATTLE',struct.pack('<i',1))
            enemy_slot=1 if kind=='field' else 0
            e.wait(2);fixture(e,close=kind!='tournament',enemy_slot=enemy_slot);ram=e.ram();note(case=kind,phase='ready',heap=free_heap(e,ram))
            trace(e,a.exe,kind,a.out)
            if kind=='tournament':
                e.gs('pstat','3','4');arm_call(e,'startTournament',[])
            else:
                # Only the named actor joins; no enemy stats or hit outcomes are injected.
                for n,v in ((250,1),(251,enemy_slot+2),(252,255),(253,255)):e.gs('pstat',str(n),str(v))
                e.gs('trigger','1','1' if kind=='boss' else '0')
                arm_call(e,'startBattle',[enemy_slot+2])
            start=time.monotonic();samples=[];seen=False;shot=False
            while time.monotonic()-start<a.seconds:
                ram=e.ram();gs=e.peek('GAME_STATE','H',ram);frame=e.peek('BATTLE_FRAME_COUNT','h',ram)
                partner=e.peek('PARTNER_ENTITY+0x4c','h',ram)
                samples.append(dict(t=round(time.monotonic()-start,2),gs=gs,frame=frame,hp=partner))
                seen=seen or gs in (1,4)
                if seen and not shot and time.monotonic()-start>10:
                    e.run('shot',str(a.out/(kind+'-battle.png')));shot=True
                    note(case=kind,phase='battle',heap=free_heap(e,ram))
                if seen and gs==0:break
                if kind=='tournament' and seen and gs==5 and hits(e):break
                e.press('CONFIRM',3);time.sleep(.5)
            recorded=hits(e)
            checked=[]
            for row in recorded:
                attacker,target,move,off,defense,power,partner,roll,actual=row
                assert roll in range(90,111),(kind,row)
                tech=B.load(next((ROOT/'content/techniques').glob(str(move)+'-*.json')).relative_to(ROOT))
                sp=species[target]
                specialties=sp.get('specialties',[None]*3)
                total=sum(10 if x is None else factors[B.ELEMENTS.index(tech['element'])][B.ELEMENTS.index(x)] for x in specialties)
                want=B.damage(power,off,defense,total,rules,old=a.old,roll=roll,counter=move==45)
                assert actual==want,(kind,row,total,want)
                checked.append(dict(attacker=attacker,target=target,move=move,off=off,defense=defense,power=power,
                                    partner=bool(partner),roll=roll,elementSum=total,damage=actual))
            assert seen and checked,(kind,'no landed ordinary hit')
            assert any(x['partner'] and x['off']-x['defense']>500 for x in checked),(kind,'no positive-tail partner hit')
            assert len({s['frame'] for s in samples})>3,(kind,'battle did not advance')
            result=dict(case=kind,old=a.old,ramBytes=len(e.ram()),hits=checked,samples=samples,
                        finished=samples[-1]['gs']==0 or (kind=='tournament' and samples[-1]['gs']==5),elapsed=round(time.monotonic()-start,2),
                        partnerKnockedOut=samples[-1]['hp']<=0,
                        positiveGapPartnerHits=sum(h['partner'] and h['off']-h['defense']>500 for h in checked),
                        positiveGapEnemyHits=sum(not h['partner'] and h['off']-h['defense']>500 for h in checked))
            if kind=='tournament':result['matchResult']=e.peek('STD_MATCH_RESULT','h')
            assert result['finished'],(kind,'battle did not finish within deadline')
            results.append(result);(a.out/'results.json').write_text(json.dumps(results,indent=2)+'\n')
            note(case=kind,result='PASS',hits=len(checked),finished=result['finished'],elapsed=result['elapsed'])
            e.run('lua',"for _,bp in ipairs(DC.bps) do pcall(function()bp:remove()end) end return 'trace removed'")
        note(result='PASS',cases=len(results))
    except BaseException:
        e.run('shot',str(a.out/'failure.png'),check=False);raise
    finally:e.stop()


if __name__=='__main__':main()
