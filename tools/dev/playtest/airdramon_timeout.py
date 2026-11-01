#!/usr/bin/env python3
"""Exercise the real Airdramon ambush on an original-2-MB English test disc.

Shorten only the test's Hold back timer to ten seconds. Fill Airdramon's
finisher gauge near the deadline, at quarter HP, and let the engine run it.
No choice keeps its unlimited battle and wins after the same finisher.
Artifacts include the deadline state, screenshots and RAM evidence.
"""
from pathlib import Path
import argparse
import hashlib
import json
import shutil
import struct
import sys

ROOT = Path(__file__).resolve().parents[3]
sys.path[:0] = [str(ROOT), str(ROOT / 'tools')]
from tools.dev.saves.releases import Emu
from tools.langpatch import elf_symbols
from tools.dev import memory_card as mcd
from tools.dev.game_state import PARTNER_PARA_FIELDS


def native_card(source, target, *, tamer_position=(410, 0, -1474), partner_type=3):
    """Keep the corpus immutable; use English and a healthy partner (native Agumon by default)."""
    shutil.copyfile(source,target)
    card=mcd.Card(target);name='BASLUS-01032DMR0';data=bytearray(card.read(name))
    options=bytes([0,0,30,0,0,0,1,0,0,1,0,0])
    data[0x54:0x60]=options
    size=0x2000 if len(data)>=0x6000 else 0x1000
    for i,base in enumerate((0x200,0x1100)):
        payload=bytearray(data[base:base+0xf00])
        struct.pack_into('<i',payload,0x1b8,partner_type)
        payload[0x1bc:0x1cc]=bytes([1])+bytes(15)
        payload[0x27c:0x280]=bytes([0x2e,255,255,0x35])
        struct.pack_into('<4h',payload,0x280,9000,9000,9000,9000)
        payload[0x28a:0x28c]=bytes(2)
        care=dict(condition=0,age=1,evoTimer=0,poopLevel=24,poopingTimer=-1,virusBar=0,
                  tiredness=0,subTiredness=0,tirednessHungerTimer=0,sicknessTimer=0,injuryTimer=0,
                  foodLevel=100,energyLevel=40,nextHungerHour=18,timeAwakeToday=0,
                  sleepyHour=19,sleepyMinute=0,wakeupHour=4,wakeupMinute=0,remainingLifetime=1000)
        at=0x1e0
        for field,fmt in PARTNER_PARA_FIELDS:
            if field in care:
                struct.pack_into('<'+fmt,payload,at,care[field])
            at+=struct.calcsize('<'+fmt)
        struct.pack_into('<HH4h',payload,0x1cc,10*1200,10*1200,1,1,10,0)
        payload[0x49a:0x49e]=bytes([168,218,2,0])
        struct.pack_into('<3i',payload,4,*tamer_position)
        struct.pack_into('<3i',payload,20,50,0,-1950)
        payload[0x467:0x47b]=b'TEST'+bytes(16)
        payload[0x49e:0x4da]=bytes(60)
        payload[0x4dc:0x4de]=bytes([255,0])
        payload[0x4e0]=255
        # The saved story starts at 0x290; its trigger array starts at +245.
        for flag in (87,88,354): payload[0x290+245+flag//8] &= ~(1 << (flag%8))
        checksum=mcd.v1_checksum(payload)^0xffffffff
        struct.pack_into('<I',payload,0x4fc,checksum)
        data[base:base+0xf00]=payload
        off=0x2000+i*size;head=bytearray(data[off:off+size])
        struct.pack_into('<I',head,8,checksum)
        replacements={1:struct.pack('<hh',168,218),3:struct.pack('<i',partner_type),9:options}
        records=[(tag,replacements.get(tag,value)) for tag,value in mcd.parse_records(head)]
        data[off:off+size]=mcd.build_extension(head,records,size)
    card.write(name,0,data)
    return target


def install(e, choice, release_tick=80):
    a = e.A
    overlay=Path(e.exe).with_name('BTL_REL.BIN').read_bytes()
    def loaded(name):
        words=struct.unpack_from('<8I',overlay,a(name)-a('btl_START'))
        return ' and '.join(f'u32({a(name)+4*i})=={word}' for i,word in enumerate(words))
    # Layouts from combat.h/entity.h: FighterData 360 bytes; flags at 52,
    # finisher goal/progress at 24/26; CurrentStats starts at entity + 76.
    lua = f"""
if AT then for _, b in ipairs(AT.bp) do b:remove() end end
AT = {{bp={{}}, events={{}}, forced=false, deadline=false, entered=false, ended=false}}
local m=PCSX.getMemPtr()
local function u8(a) return tonumber(m[a-0x80000000]) end
local function u16(a) return u8(a)+256*u8(a+1) end
local function u32(a) return u16(a)+65536*u16(a+2) end
local function w8(a,v) m[a-0x80000000]=v%256 end
local function w16(a,v) w8(a,v);w8(a+1,math.floor(v/256)) end
local function hook(a,f) AT.bp[#AT.bp+1]=PCSX.addBreakpoint(a,'Exec',4,'air-test',f) end
local function event(s) AT.events[#AT.events+1]=s end
hook({a('tickSelectionDialogue')},function() w16({a('DIALOGUE_SELECTION')}+10,{choice}) end)
hook({a('BTL_battleMain')},function()
  if not ({loaded('BTL_battleMain')}) then return end
  AT.entered=true
  event('battle timer '..u8({a('SCRIPT_STATE')}+345+242))
  if {choice}==0 then w8({a('SCRIPT_STATE')}+345+242,10) end
end)
hook({a('BTL_isBattleFinished')},function()
  if not ({loaded('BTL_isBattleFinished')}) then return end
  if not AT.entered or AT.ended or u16({a('GAME_STATE')})~=1 then return end
  local f=u16({a('BATTLE_FRAME_COUNT')})
  local c=u32({a('COMBAT_DATA_PTR')})
  -- Overlay addresses are reused during loading. Never dereference a bogus
  -- pointer through the emulator's raw host memory interface.
  if c<0x80000000 or c+1668>0x80200000 then return end
  local slot=u8(c+1645) -- player.entityIds[1], not the script's entity id
  if slot<2 or slot>=10 then return end
  local enemy=u32({a('ENTITY_TABLE')}+4*slot)
  if enemy<0x80000000 or enemy+88>0x80200000 then return end
  -- Defend without issuing repeated pad commands that would close dialogue.
  -- PlayerData currentCommand/bufferedCommand are at 1614/1616.
  w8(c+1614,6);w8(c+1616,6)
  local lock=u32({a('NO_AI_FLAG')})
  -- Hold idle until release, then let the real AI start the finisher.
  -- Its four-second aura hold selects charge/impact/tail around tick 200.
  if f<{release_tick} then
    w16(c+360+52,0x40)
    w8(c+360+54,255)
  end
  if f>={release_tick} and not AT.forced then
    w16(enemy+76,math.max(1,math.floor(u16(enemy+72)/4)))
    w16(c+360+26,u16(c+360+24))
    w16(c+360+40,0)
    w16(c+360+52,0)
    w8(c+360+54,0)
    AT.forced=true;event('finisher requested '..f..' hp '..u16(enemy+76)..' max '..u16(enemy+72))
  end
  if lock~=0 and not AT.finisher then AT.finisher=true;event('finisher lock '..f) end
  if lock==0 and AT.finisher and not AT.finished_event then
    AT.finished_event=true;event('finisher closed '..f)
  end
  if f>=200 and not AT.deadline then
    AT.deadline=true;event('deadline '..f..' lock '..lock..' enemy flags '..u16(c+360+52))
    PCSX.pauseEmulator()
  end
  if {choice}==1 and f>300 and lock==0 then
    w8(c+1614,0);w8(c+1616,0)
    if not AT.victory_seeded then
      w16(enemy+76,1);AT.victory_seeded=true;event('fight to knockout '..f)
    end
  end
end)
hook({a('BTL_deinitializeCombat')},function()
  if not ({loaded('BTL_deinitializeCombat')}) then return end
  AT.ended=true
  event('teardown frame '..u16({a('BATTLE_FRAME_COUNT')})..' lock '..u32({a('NO_AI_FLAG')}))
end)
return 'installed'
"""
    # Layout offsets checked against battle_main.c.o DWARF (original 2 MB build).
    e.run('lua', lua)


def evidence(e):
    ram = e.ram()
    ids = [struct.unpack_from('<h', ram, e.A('WORLD_OBJECTS')-0x80000000+i*12)[0] for i in range(129)]
    combat=e.peek('COMBAT_DATA_PTR','I',ram)
    slot=ram[combat-0x80000000+1645]
    enemy=e.peek(f'ENTITY_TABLE+{4*slot}','I',ram)
    enemy_type=struct.unpack_from('<I',ram,enemy-0x80000000)[0] if enemy else None
    return dict(screen=e.peek('CURRENT_SCREEN','h',ram), game=e.peek('GAME_STATE','H',ram),
                running=json.loads(e.api('/api/v1/execution-flow'))['running'],
                script_paused=e.peek('IS_SCRIPT_PAUSED','i',ram), tamer=e.peek('TAMER_STATE','b',ram),
                lock=e.peek('NO_AI_FLAG','i',ram), finishing=e.peek('FINISHING_ENTITY','I',ram),
                timed_out=ram[e.A('SCRIPT_STATE')-0x80000000+345+241],
                ambush_fought=bool(ram[e.A('SCRIPT_STATE')-0x80000000+245+88//8] & (1 << (88%8))),
                airdramon_killed=bool(ram[e.A('SCRIPT_STATE')-0x80000000+245+748//8] & (1 << (748%8))),
                enemy_slot=slot,enemy_pointer=enemy,enemy_type=enemy_type,
                enemy_flags=struct.unpack_from('<H',ram,combat-0x80000000+360+52)[0],
                partner_hp=e.peek('PARTNER_ENTITY+76','h',ram),
                partner_damage=struct.unpack_from('<h',ram,combat-0x80000000+46)[0],
                partner_hit=e.peek('PARTNER_ENTITY+83','B',ram),
                partner_animation=[e.peek('PARTNER_ENTITY+46','B',ram),e.peek('PARTNER_ENTITY+28','h',ram)],
                enemy_animation=[ram[enemy-0x80000000+46],struct.unpack_from('<h',ram,enemy-0x80000000+28)[0]] if enemy else None,
                hud=[i for i in ids if i in (0x191,0x198,0x19c)], ram_bytes=len(ram),
                events=e.run('lua', "return table.concat(AT.events, '\\n')").strip())


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('disc');p.add_argument('--exe',required=True)
    p.add_argument('--card',default='tools/dev/saves/corpus/20261027-d2796814.mcd')
    p.add_argument('--out',default='build/airdramon-proof');p.add_argument('--port',type=int,default=39141)
    p.add_argument('--case',choices=('hold','fight'),default='hold')
    p.add_argument('--expect-unsafe','--expect-broken',dest='expect_unsafe',action='store_true',help='expect the old timeout to leave active finisher state behind')
    p.add_argument('--allow-charge',action='store_true',help='also accept finisher aura/charge at the deadline')
    p.add_argument('--release-tick',type=int,default=80,help='release the idle enemy to its finisher at this fight tick')
    p.add_argument('--field-state',type=Path,help='reuse a post-Continue state; checked against disc and test card SHA-1')
    args=p.parse_args();out=Path(args.out);out.mkdir(parents=True,exist_ok=True)
    e=Emu(args.disc,args.exe,args.port,str(out/'emu'))
    press=e.press
    # emulator.py measures button holds in host time. Give the interpreter
    # enough time to observe an edge even when parallel builds slow it down.
    e.press=lambda button,frames=10: press(button,max(frames,30))
    for name,(addr,_,_) in elf_symbols(args.exe+'.elf').items(): e.table.setdefault(name,addr)
    e.env['EMU_ARGS']='-interpreter -debugger'
    result={'case':args.case,'phase':'boot'}
    try:
        card=native_card(args.card,out/'native.mcd')
        e.start(card)
        # Cinematics are outside this test; avoid waiting for streaming FMV.
        e.run('lua',f"""AT_MOV=PCSX.addBreakpoint({e.A('playMovie')},'Exec',4,'air-skip-intro',function()
          PCSX.getRegisters().GPR.n.a1=0
        end)""")
        image_hash=None
        if args.field_state:
            with Path(args.disc).with_suffix('.bin').open('rb') as image_file:
                digest=hashlib.sha1()
                for chunk in iter(lambda: image_file.read(1024*1024),b''):
                    digest.update(chunk)
            image_hash={'disc_sha1':digest.hexdigest(),'card_sha1':hashlib.sha1(card.read_bytes()).hexdigest()}
        if args.field_state and args.field_state.exists():
            assert json.loads(args.field_state.with_suffix('.json').read_text())==image_hash,'field state belongs to another disc or test card'
            e.run('load',str(args.field_state));e.run('lua','PCSX.resumeEmulator()')
        else:
            loaded=e.continue_game()
            assert loaded==0,loaded
            e.wait(8)
            if args.field_state:
                args.field_state.parent.mkdir(parents=True,exist_ok=True)
                e.run('save',str(args.field_state))
                args.field_state.with_suffix('.json').write_text(json.dumps(image_hash,indent=2)+'\n')
        print('continued card on original 2 MB', flush=True)
        result['phase']='field'
        e.gs('set','partner.para.age=1','partner.para.evoTimer=0','partner.para.condition=0',
             'partner.para.discipline=100','partner.stats.hp=9000','partner.stats.mp=9000',
             'partner.stats.currentHP=9000','partner.stats.currentMP=9000',
             'partner.stats.off=900','partner.stats.def=900','partner.stats.speed=900','partner.stats.brain=900',
             'gametime_running=0')
        e.poke('MOD_OPT_STORY',struct.pack('<i',1))
        e.wait(3)
        # Continue can briefly report idle just before pending medal awards
        # open a modal box. Let those finish before changing the tamer state.
        for _ in range(120):
            ram=e.ram()
            if (e.peek('TAMER_STATE','b',ram)==0
                    and not e.peek('MEDAL_AWARD_PENDING','i',ram)
                    and not e.peek('TAMER_LEVEL_AWARD_PENDING','i',ram)):
                break
            e.press('CONFIRM',30);e.wait(.5)
        else:
            raise AssertionError('post-Continue awards did not close')
        e.gs('trigger','354','0');e.gs('trigger','88','0')
        warped=e.warp(168)
        if not warped:
            for _ in range(150):
                e.wait(1)
                if e.peek('CURRENT_SCREEN','h')==168 and e.peek('TAMER_STATE','b')==0:
                    warped=True
                    break
        assert warped,'File City warp did not settle'
        print('File City ready', flush=True)
        e.gs('trigger','354','1')
        install(e,0 if args.case=='hold' else 1,args.release_tick)
        result['phase']='ambush'
        # Enter the same section as step trigger 6, at a game-loop boundary.
        a=e.A
        e.run('lua',f"""
AT.call=PCSX.addBreakpoint({a('gameLoop')},'Exec',4,'air-call',function()
  local r=PCSX.getRegisters()
  if AT.ra then r.GPR.n.ra=AT.ra;AT.call:remove();return end
  AT.ra=r.GPR.n.ra;r.GPR.n.a0=162;r.GPR.n.a1=57;r.GPR.n.a2=0
  r.GPR.n.ra={a('gameLoop')};r.pc={a('callScriptSection')}
end)
""")
        for _ in range(240):
            if e.run('lua','return AT.entered').strip()=='true': break
            e.press('CONFIRM',4);e.wait(.35)
        else: raise AssertionError('ambush did not enter battle')
        print('ambush battle entered', flush=True)
        for _ in range(180):
            if e.run('lua','return AT.deadline').strip()=='true': break
            e.wait(.5)
        else: raise AssertionError('deadline not reached')
        result['deadline']=evidence(e)
        print('deadline:', result['deadline'], flush=True)
        e.run('shot',str(out/'deadline.png'));e.run('save',str(out/'deadline.state'))
        assert 'deadline 200 lock 1' in result['deadline']['events'], result
        assert f"battle timer {90 if args.case=='hold' else 0}" in result['deadline']['events'],result
        if not args.allow_charge:
            assert result['deadline']['enemy_flags'] & 32,result
        assert result['deadline']['finishing']==result['deadline']['enemy_pointer'],result
        e.run('lua','PCSX.resumeEmulator()')
        for _ in range(80 if args.expect_unsafe else 300):
            e.wait(.5)
            r=evidence(e)
            assert r['running'],'emulator stayed paused after the deadline capture'
            if r['ambush_fought'] and r['game']==0 and r['script_paused']==1 and r['tamer']==0: break
            if r['game']!=1: e.press('CONFIRM',4)
        result['after']=evidence(e)
        e.run('shot',str(out/'after.png'));e.run('save',str(out/'after.state'))
        r=result['after']
        visible_clean=r['ambush_fought'] and r['game']==0 and r['script_paused']==1 and r['tamer']==0 and not r['hud']
        clean=visible_clean and not r['lock'] and not r['finishing'] and not r['partner_hit']
        result['visible_clean']=visible_clean
        result['clean']=clean
        if args.expect_unsafe:
            assert r['timed_out']==1 and r['lock'] and r['finishing']==result['deadline']['enemy_pointer'],result
        else:
            assert clean,result
        if clean: assert r['timed_out']==(args.case=='hold'),result
        if clean: assert not r['airdramon_killed'],result     # held back or beaten, he survives
        result['phase']='complete'
    except BaseException as error:
        result['error']=str(error)
        try:
            e.run('shot',str(out/'failure.png'))
            e.run('save',str(out/'failure.state'))
        except Exception:
            pass
        raise
    finally:
        (out/'result.json').write_text(json.dumps(result,indent=2)+'\n')
        e.stop()
    print(json.dumps(result,indent=2))


if __name__=='__main__':main()
