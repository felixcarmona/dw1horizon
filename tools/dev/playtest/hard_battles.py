#!/usr/bin/env python3
"""Compare NORMAL/HARD wild and boss fights on 2 MB; inspect scaling and damage.

No enemy stats, outcomes, accuracy or damage rolls are forced. A controlled
MetalEtemon partner provides controlled stats and three legal techniques.
"""
import argparse
import hashlib
import json
from pathlib import Path
import re
import signal
import struct
import sys
import time
ROOT=Path(__file__).resolve().parents[3]
sys.path[:0]=[str(ROOT),str(ROOT/'tools')]
from tools.dev.saves.releases import Emu
from tools.dev.playtest.birdramon_recruitment import free_heap
from tools.dev.playtest.hard_options import hard_card
from tools.dev.playtest.damage_curve_battles import arm_call,fixture,hits
from tools.langpatch import elf_symbols
from tools import battle_audit as B

def trace(e,exe,kind,out):
    function='STD_calculateDamage' if kind=='tournament' else 'BTL_calculateDamage'
    overlay='STD_REL.BIN' if kind=='tournament' else 'BTL_REL.BIN'
    base='std_START' if kind=='tournament' else 'btl_START'
    data=Path(exe).with_name(overlay).read_bytes()
    addr=e.A(function)
    prefix='STD' if kind=='tournament' else 'BTL'
    zero=e.table.get(prefix+'_HARD_ZERO_DAMAGE',0)
    tick=e.A(prefix+'_tickAttackHits');tick_end=tick+elf_symbols(exe+'.elf')[prefix+'_tickAttackHits'][1]
    minimum=B.load('content/tables/battle-formulas.json')['battleFormulas']['hard']['minimumDamagePercent']
    assert zero or e.peek('MOD_OPT_DIFFICULTY','i')!=2,'HARD proof needs the native zero-Defense comparator'
    words=struct.unpack_from('<4I',data,addr-e.A(base))
    guard=' and '.join(f'u32({addr+4*i})=={w}' for i,w in enumerate(words))
    code=f'''
if DC then for _,bp in ipairs(DC.bps) do bp:remove() end end
DC={{hits={{}},applied={{}},bps={{}},violations={{}}}}
local mem=PCSX.getMemPtr()
local function u8(a)return tonumber(mem[a-0x80000000])end
local function u16(a)return u8(a)+256*u8(a+1)end
local function s16(a)local v=u16(a);return v>=32768 and v-65536 or v end
local function u32(a)return u16(a)+65536*u16(a+2)end
DC.bps[#DC.bps+1]=PCSX.addBreakpoint({addr},'Exec',4,'damage-entry',function()
 if not ({guard}) then return end
 local regs=PCSX.getRegisters().GPR.n;local a=regs.a0;local b=regs.a1;local move=regs.a2%65536
 if a<0x80000000 or b<0x80000000 or move>=113 then return end
 local power=s16({e.A('MOVE_DATA')}+move*16+4)
 local x={{u32(a),u32(b),move,s16(a+56),s16(b+58),power,a==u32({e.A('ENTITY_TABLE')}+4) and 1 or 0,-1,0,u8(u32({e.A("COMBAT_DATA_PTR")})+1640),100,u16({e.A("BATTLE_FRAME_COUNT")}),0,100}}
 DC.current=x
 local bp
 bp=PCSX.addBreakpoint(regs.ra,'Exec',4,'damage-return',function()
  bp:remove();x[9]=PCSX.getRegisters().GPR.n.v0;x[13]={zero}~=0 and u32({zero}) or 0;DC.hits[#DC.hits+1]=x;DC.latest=x;DC.current=nil
 end)
 DC.bps[#DC.bps+1]=bp
end)
DC.bps[#DC.bps+1]=PCSX.addBreakpoint({e.A('randomLimit')},'Exec',4,'damage-roll',function()
 local r=PCSX.getRegisters().GPR.n
 if not DC.current then
  if DC.latest and r.a0==21 and r.ra>={tick} and r.ra<{tick_end} then
   local x=DC.latest;local bp
   bp=PCSX.addBreakpoint(r.ra,'Exec',4,'block-roll-return',function()
    bp:remove();x[14]=PCSX.getRegisters().GPR.n.v0+10
   end)
   DC.bps[#DC.bps+1]=bp
  end
  return
 end
 if r.a0~=21 and r.a0~=101 then return end
 local fin=r.a0==101
 local x=DC.current;local bp
 bp=PCSX.addBreakpoint(r.ra,'Exec',4,'damage-roll-return',function()
  bp:remove();if fin then x[11]=PCSX.getRegisters().GPR.n.v0+100 else x[8]=PCSX.getRegisters().GPR.n.v0+90 end
 end)
 DC.bps[#DC.bps+1]=bp
end)
DC.bps[#DC.bps+1]=PCSX.addBreakpoint({e.A('addEntityText')},'Exec',4,'damage-applied',function()
 local r=PCSX.getRegisters().GPR.n
 if u16({e.A('GAME_STATE')})~=1 or r.a2~=0 or r.ra<{tick} or r.ra>={tick_end} then return end
 local target=r.a0==u32({e.A('ENTITY_TABLE')}+4) and 1 or 0
 local x=DC.latest;local pct=x and x[14] or 100;local without=0
 if x and u32({e.A('MOD_OPT_DIFFICULTY')})==2 and target==1 then
  without=math.max(1,math.floor((x[3]>=58 and x[9] or x[13])*pct/100))
  if r.a3*100<without*{minimum} then DC.violations[#DC.violations+1]=u16({e.A('BATTLE_FRAME_COUNT')}) end
 end
 DC.applied[#DC.applied+1]={{u16({e.A('BATTLE_FRAME_COUNT')}),target,r.a3,u16(r.a0+76),pct,without}}
end)
return 'trace armed'
'''
    (out/(kind+'-trace.lua')).write_text(code)
    e.run('lua',code)



def throw_recovery(e):
    # startBattle owns a nested loop, so gameLoop cannot service a call here.
    # Inject the real item throw at the next battle-tick boundary instead.
    e.run('lua',f'''
if DItem and DItem.bp then DItem.bp:remove() end
DItem={{phase=0}}
DItem.bp=PCSX.addBreakpoint({e.A('BTL_battleTickFrame')},'Exec',4,'recovery-call',function()
 local r=PCSX.getRegisters()
 if DItem.phase==1 then r.GPR.n.ra=DItem.saved;DItem.phase=2;DItem.bp:remove();return end
 DItem.saved=r.GPR.n.ra;r.GPR.n.ra={e.A('BTL_battleTickFrame')};r.pc={e.A('startThrowingItem')};DItem.phase=1
end)
return 'recovery armed' ''')


def setup_trace(e):
    a=e.A
    data=Path(e.exe).with_name('BTL_REL.BIN').read_bytes()
    words=struct.unpack_from('<8I',data,a('BTL_initializeCombat')-a('btl_START'))
    guard=' and '.join(f'u32({a("BTL_initializeCombat")+4*i})=={word}' for i,word in enumerate(words))
    e.run('lua',f'''
HC={{}}
local mem=PCSX.getMemPtr()
local function u8(a)return tonumber(mem[a-0x80000000])end
local function u16(a)return u8(a)+256*u8(a+1)end
local function u32(a)return u16(a)+65536*u16(a+2)end
local bp
bp=PCSX.addBreakpoint({a('BTL_initializeCombat')},'Exec',4,'hard-init',function()
 if not ({guard}) then return end
 local ra=PCSX.getRegisters().GPR.n.ra
 bp:remove()
 local ret
 ret=PCSX.addBreakpoint(ra,'Exec',4,'hard-ready',function()
  ret:remove()
  -- entityIds is resolved below by the real NPC slot for these solo fixtures.
  local enemy=u32({a('ENTITY_TABLE')}+HC.enemyEntity*4)
  local raw={a('INITIAL_COMBAT_STATS')}+12
  HC.values={{u32({a('MOD_OPT_DIFFICULTY')}),enemy,u32(enemy),u16(enemy+72),u16(enemy+76),u16(enemy+56),u16(enemy+58),u16(enemy+60),u16(enemy+62),u16(enemy+74),u16(raw),u16(raw+4),u16(raw+6),u16(raw+8),u16(raw+10)}}
 end)
end)
return 'armed'
''')

def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('disc');ap.add_argument('--exe',required=True)
    ap.add_argument('--card',default='tools/dev/saves/corpus/20261027-d2796814.mcd')
    ap.add_argument('--out',type=Path,default=Path('build/hard-proof'))
    ap.add_argument('--port',type=int,default=44379);ap.add_argument('--seconds',type=int,default=420)
    ap.add_argument('--resume',action='store_true')
    ap.add_argument('--before',action='store_true',help='old NORMAL image before the Defense extension; same owned encounter data')
    ap.add_argument('--cases',default='wild,boss');ap.add_argument('--profiles',default='late,strong,max');ap.add_argument('--modes',default='NORMAL,HARD')
    ap.add_argument('--battle-state',type=Path,help='paused checkpoint at the real final-scene startBattle entry')
    ap.add_argument('--boss-move',type=int,default=47,help='legal boss technique in slot zero (default Buster Dive)')
    ap.add_argument('--recoveries',type=int,default=0,help='player-strategy trial: carry large recoveries and throw one below 75%% HP')
    ap.add_argument('--muscle-first',action='store_true',help='select the legal Muscle Charge command until its five-use budget is spent, then Buster Dive')
    ap.add_argument('--finishers',action='store_true',help='use Square when the native gauge is ready and Confirm to charge it')
    a=ap.parse_args();
    if a.before:a.modes='NORMAL'
    a.out=a.out.resolve();a.out.mkdir(parents=True,exist_ok=True)
    e=Emu(a.disc,a.exe,a.port,str(a.out/'emu'))
    for n,(address,_,_) in elf_symbols(a.exe+'.elf').items():e.table.setdefault(n,address)
    e.env['EMU_ARGS']='-interpreter -debugger -bios '+str(ROOT/'.tools/emu/pcsx-redux-zip/squashfs-root/usr/share/pcsx-redux/resources/openbios.bin')
    if not a.before:e.env['EMU_AUDIO']=str(a.out/'audio.raw')
    formulas=B.load('content/tables/battle-formulas.json')['battleFormulas'];hard=formulas['hard']
    if a.before:
        for key in ('defenseKnee','defenseTailHalf'):formulas['damage'].pop(key)
    species={s['id']:s for s in (B.load(p.relative_to(ROOT)) for p in (ROOT/'content/species').glob('*.json'))}
    tf=B.load('content/tables/type-factors.json')['typeFactors']
    results=json.loads((a.out/'results.json').read_text()) if a.resume and (a.out/'results.json').exists() else []
    profiles={'late':(800,8005,9520),'strong':(1500,15000,15000),'max':(9999,30000,30000)}
    def stop_signal(n,f):raise SystemExit(128+n)
    signal.signal(signal.SIGTERM,stop_signal)
    try:
        card=hard_card(a.card,str(a.out/'test.mcd'))
        e.start(card)
        base=str(a.out/'base.state')
        identity=hashlib.sha256(Path(a.exe).read_bytes()).hexdigest()
        stamp=a.out/'base-exe.sha256'
        if a.resume:
            assert stamp.read_text().strip()==identity,'stale executable in checkpoint'
            e.run('load',base)
        else:
            assert e.continue_game()==0
            assert e.peek('MOD_OPT_DIFFICULTY','i')==(0 if a.before else 2),'saved difficulty did not match this reader'
            e.gs('set','gametime_running=0','hour=10','minute=0')
            e.run('save',base);stamp.write_text(identity+'\n')
        assert len(e.ram())==0x200000
        assert e.peek('MOD_COLD_CACHE_TYPE','i')<0,'2 MB proof must not have expanded RAM'
        for kind,screen,slot,profile,modeName in [(k,s,n,p,m) for k,s,n in [('wild',153,0),('boss',225 if a.battle_state else 104,0)] if k in a.cases.split(',') for p in a.profiles.split(',') for m in a.modes.split(',')]:
            case=f'{kind}-{profile}-{modeName.lower()}'
            if any(r.get('case')==case for r in results):continue
            mode=2 if modeName=='HARD' else 0
            print('START '+case,flush=True)
            e.run('load',base);e.wait(1)
            if a.battle_state:
                assert a.battle_state.with_suffix('.sha256').read_text().strip()==identity
                e.run('pause');e.run('load',str(a.battle_state));e.run('pause')
            else:
                if kind=='boss':e.gs('pstat','16','1')
                assert e.warp(screen)
                if kind=='boss':
                    e.gs('approach','0','600')
                    e.poke('NPC_ENTITIES+0x9c',bytes(2))
                e.wait(2);fixture(e,close=True,enemy_slot=slot)
            # One legal late-game loadout for all fixtures; AI chooses naturally.
            ram=e.ram();para=e.A('DIGIMON_DATA')-0x80000000+65*52
            available=list(ram[para+35:para+51]);loadout=[46 if kind=='wild' else a.boss_move,41,42]
            animations=[0x2e+available.index(move) for move in loadout]
            finisherSlot=next(i for i in range(15,-1,-1) if 58<=available[i]<113)
            animations.append(0x2e+finisherSlot)
            e.poke('PARTNER_ENTITY+0x40',bytes([30]*4+animations))
            learned=[0]*4
            for move in loadout:learned[move//32]|=1<<(move%32)
            e.poke('PARTNER_ENTITY+0x58',struct.pack('<4I',*learned))
            value,health,magic=profiles[profile];stats=(value,)*4
            e.poke('PARTNER_ENTITY+0x38',struct.pack('<4h',*stats))
            e.poke('PARTNER_ENTITY+0x48',struct.pack('<4h',health,magic,health,magic))
            if a.recoveries:
                assert 0<a.recoveries<=99
                e.poke('INVENTORY',struct.pack('<30h',2,*([-1]*29))+bytes([a.recoveries])+bytes(29)+bytes([0])+bytes([255]*29)+bytes([30]))
                e.poke('INVENTORY_POINTER',bytes([0]))
            e.poke('MOD_OPT_DIFFICULTY',struct.pack('<i',mode))
            setup_trace(e);e.run('lua',f'HC.enemyEntity={slot+2}')
            trace(e,a.exe,'field' if kind=='wild' else 'boss',a.out)
            if a.battle_state:e.run('resume')
            else:
                for n,v in ((250,1),(251,slot+2),(252,255),(253,255)):e.gs('pstat',str(n),str(v))
                e.gs('trigger','1','1' if kind=='boss' else '0')
                arm_call(e,'startBattle',[slot+2])
            start=time.monotonic();samples=[];seen=False;shot=False;recorded=False;throws=[];lastThrow=-1000
            while time.monotonic()-start<a.seconds:
                ram=e.ram();gs=e.peek('GAME_STATE','H',ram);frame=e.peek('BATTLE_FRAME_COUNT','h',ram)
                hp=e.peek('PARTNER_ENTITY+0x4c','h',ram)
                samples.append(dict(wallSeconds=round(time.monotonic()-start,2),state=gs,frame=frame,partnerHP=hp))
                seen=seen or gs==1
                if seen and not shot and frame>20:
                    e.run('shot',str(a.out/(case+'.png')))
                    shot=True
                if seen and not recorded and case=='boss-max-hard' and screen==104 and frame>=120:
                    e.run('record',str(a.out/'hard-boss.mp4'),'180','8');recorded=True
                if seen and gs==0:break
                combat=e.peek('COMBAT_DATA_PTR','I',ram)-0x80000000
                if gs==1 and a.recoveries and 0<hp<health*3//4 and frame-lastThrow>40:
                    left=e.peek('INVENTORY+60','B',ram)
                    if left and e.peek('NO_AI_FLAG','i',ram)==0:
                        # The game's throw consumes inventory and applies its effect
                        # after flight. The test never writes HP or damage in battle.
                        throw_recovery(e)
                        throws.append(dict(frame=frame,hp=hp,itemsBefore=left));lastThrow=frame
                goal,progress=struct.unpack_from('<2h',ram,combat+24) if gs==1 else (0,0)
                if a.finishers and gs==1 and goal>0 and progress==goal and e.peek('NO_AI_FLAG','i',ram)==0:
                    e.press('SQUARE',24)
                else:
                    if a.muscle_first and gs==1 and e.peek('NO_AI_FLAG','i',ram)==0:
                        # Move the ordinary command cursor, then submit actual input.
                        # Buff limits and the selected technique execute in game code.
                        command=9 if ram[combat+57] else 8
                        available=list(ram[combat+1620:combat+1620+ram[combat+1638]])
                        assert command in available,(command,available)
                        e.run('poke',hex(combat+0x80000000+1618),bytes([available.index(command)]).hex())
                    e.press('CONFIRM',12 if a.finishers else 3)
                e.wait(.5)
            inittext=e.run('lua',"return HC.values and 'INIT,'..table.concat(HC.values,',') or 'missing'")
            found=re.search(r'INIT,([0-9,]+)',inittext);assert found,inittext
            init=list(map(int,found.group(1).split(',')))
            actualMode,address,sid,hp,current,off,defense,speed,brain,mp,rawhp,rawoff,rawdef,rawspeed,rawbrain=init
            assert actualMode==mode
            for got,raw,key,cap in [(hp,rawhp,'hpPercent',30000),(off,rawoff,'offensePercent',9999),(defense,rawdef,'defensePercent',9999),(speed,rawspeed,'speedPercent',9999),(brain,rawbrain,'brainsPercent',9999)]:
                assert got==(min(cap,raw*hard[key]//100) if mode==2 else raw),(case,init,key)
            checked=[]
            for row in hits(e):
                attacker,target,move,o,d,power,partner,roll,actual,charge,finRoll,frame,zeroNative,blockPercent=row
                assert roll in range(90,111)
                tech=B.load(next((ROOT/'content/techniques').glob(str(move)+'-*.json')).relative_to(ROOT)) if move<58 else species[attacker]['finisher']
                total=sum(10 if x is None else tf[B.ELEMENTS.index(tech['element'])][B.ELEMENTS.index(x)] for x in species[target].get('specialties',[None]*3))
                if move>=58:
                    # Species-owned finishers override the shared MOVE_DATA row.
                    power=tech['power']
                    if mode==2 and not partner:power=min(32767,power*hard['finisherPowerPercent']//100)
                    expected=(o+power)*total//30
                    if partner and charge>=formulas['damage']['chargeupFrom']:expected=expected*charge//formulas['damage']['chargeupDivisor']
                    elif not partner:expected=expected*finRoll//100
                    expected=expected*roll//100
                    if mode==2 and partner:expected=expected*hard['partnerDamagePercent']//100
                    expected=max(1,min(30000,expected))
                else:
                    expected=B.damage(power,o,d,total,formulas['damage'],roll=roll,counter=move==45)
                    if mode==2:
                        if partner:expected=max(1,expected*hard['partnerDamagePercent']//100)
                        else:expected=max(expected,(B.damage(power,o,0,total,formulas['damage'],roll=roll)*hard['minimumDamagePercent']+99)//100)
                assert expected==actual,(row,total,expected)
                checked.append(dict(partner=bool(partner),offense=o,defense=d,power=power,roll=roll,damage=actual,frame=frame,move=move,finisher=move>=58,zeroDefenseNative=zeroNative,blockPercent=blockPercent))
            (a.out/(case+'-observations.json')).write_text(json.dumps(dict(initialization=init,hits=checked,samples=samples),indent=2)+'\n')
            assert seen and checked and any(h['partner'] for h in checked)
            assert samples[-1]['state']==0,'battle did not return to the field'
            if e.peek('CURRENT_SCREEN','H')==screen and e.peek('ENTITY_TABLE+'+str((slot+2)*4),'I')==address:
                assert struct.unpack_from('<h',e.ram(),address+72-0x80000000)[0]==rawhp,'scaled max HP leaked into field'
            e.run('shot',str(a.out/(case+'-end.png')))
            appliedText=e.run('lua',"local out={} for _,x in ipairs(DC.applied) do out[#out+1]='HIT,'..table.concat(x,',') end return table.concat(out,';')")
            applied=[dict(zip(('frame','partnerTarget','damage','hpBefore','blockPercent','zeroDefenseNative'),map(int,m.split(',')))) for m in re.findall(r'HIT,([0-9,]+)',appliedText)]
            assert e.run('lua',"return #DC.violations").strip()=='0','native applied damage fell below the HARD minimum'
            after_ram=e.ram()
            after_stats=list(struct.unpack_from('<4h',after_ram,e.A('PARTNER_ENTITY')-0x80000000+0x38))
            after_max=list(struct.unpack_from('<2h',after_ram,e.A('PARTNER_ENTITY')-0x80000000+0x48))
            row=dict(beforeDefenseCurve=a.before,case=case,kind=kind,screen=screen,profile=profile,mode=modeName,loadout=loadout,recoveryThrows=throws,recoveriesCarried=a.recoveries,recoveriesRemaining=e.peek('INVENTORY+60','B') if a.recoveries else 0,finisherInput=a.finishers,muscleFirst=a.muscle_first,afterPartnerStats=after_stats,afterPartnerMaxHPMP=after_max,partnerStats=stats,partnerMaxHP=health,partnerMaxMP=magic,ramBytes=len(e.ram()),expandedRAM=False,initialization=init,hits=checked,appliedHits=applied,samples=samples,
                     finished=True,partnerKnockedOut=any(s['state']==1 and s['partnerHP']<=0 for s in samples) or any(h['partnerTarget'] and 0<h['hpBefore']<=h['damage'] for h in applied),minimumObservedHP=min(s['partnerHP'] for s in samples),heap=free_heap(e,e.ram()),elapsedWallSeconds=round(time.monotonic()-start,2),
                     combatSeconds=max(s['frame'] for s in samples)/20)
            results.append(row);(a.out/'results.json').write_text(json.dumps(results,indent=2)+'\n');print(json.dumps({k:v for k,v in row.items() if k not in ('samples','hits','appliedHits')}),flush=True)
    finally:e.stop()
if __name__=='__main__':main()
