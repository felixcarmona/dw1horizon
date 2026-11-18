#!/usr/bin/env python3
"""Check the Mount Infinity lower portal and three-Vermilimon encounter on 2 MB.

Boots a disposable corpus card and installs fixture partners through evolution.
The portal section, arrival, enemy placements and battle loader are unmodified.
Strong partner stats bound the encounter; --cleanup may zero enemy HP after
observing battle progress, so that mode proves loading rather than combat AI.
"""
import argparse
import bisect
import json
import os
from pathlib import Path
import struct
import sys
import time
from concurrent.futures import ThreadPoolExecutor

ROOT = Path(__file__).resolve().parents[3]
sys.path[:0] = [str(ROOT), str(ROOT / 'tools')]
from tools.dev.playtest.qol import ProofEmu, test_card
from tools.dev.playtest.quest_regressions import evolve_fixture
from tools.dev.playtest.training_evolution import call
from tools.langpatch import elf_symbols
from tools.membudget import Ram, heap_walk


def sample(e):
    ram = e.ram()
    flow = json.loads(e.api('/api/v1/execution-flow'))
    assert flow['8mb'] == e.expanded_ram and len(ram) == 0x200000
    heap = heap_walk(Ram(ram, e.table))
    row = {k: e.peek(k, f, ram) for k, f in (
        ('CURRENT_SCREEN', 'h'), ('TAMER_STATE', 'B'), ('GAME_STATE', 'H'),
        ('ENEMY_COUNT', 'i'), ('BATTLE_FRAME_COUNT', 'i'), ('PARTNER_ENTITY', 'i'),
        ('MOD_OPT_QUICK_BATTLE', 'i'), ('MOD_BATTLE_LOADING', 'b'))}
    row.update(ram_bytes=len(ram), expanded_ram=flow['8mb'], running=flow['running'],
               tamer=e.peek('TAMER_POSITION_DATA+0x78', '3i', ram),
               heap={k: v for k, v in heap.items() if k != 'blocks'})
    row['stream_failures'] = int(e.run('lua', 'return IP.streamFailures').strip())
    row['battle_cold_reads'] = int(e.run('lua', 'return IP.coldReads').strip())
    row['tile_window'] = [e.peek(k, 'b', ram) for k in ('MAP_TILE_X', 'MAP_TILE_Y')]
    frame=e.peek('ACTIVE_FRAMEBUFFER','i',ram)
    row['gpu']={
        'framebuffer': frame,
        'packet_pointer': e.peek('GsOUT_PACKET_P','I',ram),
        'ot_lengths': e.peek('GS_ORDERING_TABLE','I',ram),
        'ot1_length': e.peek('GS_ORDERING_TABLE+20','I',ram),
    }
    row['enemies'] = []
    for slot in range(8):
        ptr = e.peek(f'ENTITY_TABLE+{4*(slot+2)}', 'I', ram)
        if not 0x80000000 < ptr < 0x80200000:
            continue
        pd = e.peek(f'NPC_ENTITIES+{104*slot+4}', 'I', ram)
        row['enemies'].append(dict(slot=slot, species=e.peek(f'NPC_ENTITIES+{104*slot}', 'i', ram),
             position=struct.unpack_from('<3i', ram, (pd & 0x1fffff)+0x78),
             hp=e.peek(f'NPC_ENTITIES+{104*slot+0x4c}', 'h', ram)))
    combat = e.peek('COMBAT_DATA_PTR', 'I', ram)
    row['participants'] = []
    if row['GAME_STATE'] == 1 and 0x80000000 <= combat < 0x80200000 - 1668:
        ids = ram[(combat & 0x1fffff) + 1645:][:row['ENEMY_COUNT']]
        row['participants'] = [n for n in row['enemies'] if n['slot'] + 2 in ids]
    return row


def equip_only(e, technique):
    """Leave the partner one learned and equipped technique (as seam_movesets' fixture)."""
    ram = e.ram()
    species = e.peek('PARTNER_ENTITY', 'i', ram)
    if species < 180:
        para = e.A('DIGIMON_DATA') - 0x80000000 + species * 52
    else:
        # New species come from DIGI.DAT through getSpeciesPara's cache (params.h)
        para = call(e, 'getSpeciesPara', species) & 0x1fffff
        e.run('resume')
        ram = e.ram()
    moves = list(ram[para + 35:para + 51])
    if technique not in moves:
        # a technique of a species the fixture cannot be evolved to: lend it to this one (first slot of its RAM copy)
        assert os.environ.get('PACKET_LEND_TECHNIQUE'), f'species {species} cannot use technique {technique}: {moves}'
        assert species < 180, 'lending needs the plain species table'
        e.poke('DIGIMON_DATA+%d' % (species * 52 + 35), bytes([technique]))
        moves[0] = technique
    e.poke('PARTNER_ENTITY+0x40', bytes([100, 0, 0, 0, 46 + moves.index(technique), 255, 255, 255]))
    e.poke('PARTNER_ENTITY+0x58', (1 << technique).to_bytes(16, 'little'))


# Every renderer that writes packets in a battle, by symbol: --profile measures the bytes each one adds
# (largest single call, largest per-frame total) so the heavy techniques show which path they stress.
OVERLAY = 'BTL'  # the overlay whose renderers are profiled: BTL, STD (tournament) or VS (versus)
PROFILE_FUNCS = [
    'BTL_renderRingTube', 'BTL_renderRadialWaves', 'BTL_renderRibbonStrip', 'BTL_renderParallelLines',
    'BTL_renderWireframeBox', 'BTL_renderParallaxSprites', 'BTL_renderScrollingBackground',
    'BTL_render3DTexturedQuad', 'BTL_render2DTexturedQuad', 'BTL_renderScreenFade', 'BTL_renderScreenOverlay',
    'BTL_renderFinisherAuraSpark', 'BTL_renderAuraProjectile', 'BTL_renderBuffTrails', 'BTL_renderBuffRingsSpark',
    'BTL_drawTMD', 'BTL_drawTMDYXZ', 'BTL_drawTMDScreenSpace', 'BTL_renderProjectedSprite', 'BTL_renderScreenSprite',
    'renderEntityParticleFX', 'renderParticleFlash', 'renderFXParticle', 'GsSortSprite', 'GsSortObject4',
]


def profile_lua(e, pad=0):
    """Lua that wraps every PROFILE_FUNCS renderer in a packet-cursor delta (the return address gets a breakpoint
    the first time each call site is seen). Per function: calls, largest call, largest per-frame total, and
    the calls after which the cursor was past the frame's area."""
    # The tournament (STD_) and versus (VS_) overlays carry copies of the battle (BTL_) effect renderers
    # (the overlays share one address range, so only the running overlay's names mean anything)
    funcs = [OVERLAY + '_' + n[4:] if n.startswith('BTL_') else n for n in PROFILE_FUNCS]
    funcs = [n for i, n in enumerate(funcs) if n in e.table and n not in funcs[:i]]
    addrs = ','.join(f'["{n}"]={e.A(n)}' for n in funcs)
    names = ','.join(f'"{n}"' for n in funcs)
    return f'''
      local name_addr={{{addrs}}}
      local function cursor()
        local frame=word({e.A('ACTIVE_FRAMEBUFFER')})
        return word({e.A('GsOUT_PACKET_P')})-({e.A('GS_WORK_BASES')}+frame*0x14000)
      end
      local function stat(name) local s=IP.prof[name]; if not s then s={{max=0,sum=0,fmax=0,calls=0,over=0}}; IP.prof[name]=s end; return s end
      local function entry(name)
        return function()
          if not battle() then return end
          local frame=word({e.A('ACTIVE_FRAMEBUFFER')})
          if frame~=0 and frame~=1 then return end
          IP.pstart[name]=cursor()
          local ra=PCSX.getRegisters().GPR.n.ra
          if not IP.retbps[ra] then
            IP.retbps[ra]=name
            IP.bp[#IP.bp+1]=PCSX.addBreakpoint(ra,'Exec',4,'portal-ret-'..name,function()
              local st=IP.pstart[name]
              if not st or not battle() then return end
              IP.pstart[name]=nil
              local frame=word({e.A('ACTIVE_FRAMEBUFFER')})
              if frame~=0 and frame~=1 then return end
              local c=cursor()
              local d=c-st
              local s=stat(name)
              s.calls=s.calls+1; s.sum=s.sum+d
              if d>s.max then s.max=d end
              if c>0x14000 then s.over=s.over+1 end
            end)
          end
        end
      end
      for _,name in ipairs({{{names}}}) do
        IP.bp[#IP.bp+1]=PCSX.addBreakpoint(name_addr[name],'Exec',4,'portal-p-'..name,entry(name))
      end
      -- Every object render callback: its packet bytes per call and per frame, keyed by the callee's address.
      IP.rend={{}}; IP.rstart={{}}
      do
        local base={e.A('renderObjects')}
        local mem=PCSX.getMemPtr()
        for off=0,0x100,4 do
          local w=word(base+off)
          if w%64==9 and (w-w%0x4000000)/0x4000000==0 then
            local rs=math.floor(w/0x200000)%32
            local pc=base+off
            IP.bp[#IP.bp+1]=PCSX.addBreakpoint(pc,'Exec',4,'portal-jalr',function()
              if not battle() then return end
              IP.rtarget=PCSX.getRegisters().GPR.r[rs]
              IP.rstart[1]=cursor()
            end)
            IP.bp[#IP.bp+1]=PCSX.addBreakpoint(pc+8,'Exec',4,'portal-jalr-ret',function()
              local st=IP.rstart[1]
              if not st or not battle() then return end
              IP.rstart[1]=nil
              local d=cursor()-st
              local t=string.format('%08x',IP.rtarget)
              local s=IP.rend[t]
              if not s then s={{calls=0,max=0,sum=0,fmax=0}}; IP.rend[t]=s end
              s.calls=s.calls+1; s.sum=s.sum+d
              if d>s.max then s.max=d end
            end)
          end
        end
      end
      IP.bp[#IP.bp+1]=PCSX.addBreakpoint({e.A('applyDrawOffset')},'Exec',4,'portal-pframe',function()
        do
          -- the pass that used most of the area, split by object callback (applyDrawOffset ends the pass)
          local g=IP.gpu; local used=cursor()
          if battle() and used>(g.worstUsed or 0) then
            g.worstUsed=used; g.worst={{}}; local all=0
            for k,v in pairs(IP.rend) do g.worst[k]=v.sum; all=all+v.sum end
            g.worstOther=used-{pad}-all
          end
        end
        for _,s in pairs(IP.rend) do
          if s.sum>s.fmax then s.fmax=s.sum end
          s.sum=0
        end
        for _,s in pairs(IP.prof) do
          if s.sum>s.fmax then s.fmax=s.sum end
          s.sum=0
        end
      end)
'''


def gpu_monitor(e, pad=0, profile=False):
    """Per render pass: packet-area peak and violations; every write to the ordering-table headers in battle."""
    out = e.run('lua', f'''
      local ffi=require('ffi')
      local function word(a) return tonumber(ffi.cast('uint32_t*',PCSX.getMemPtr()+a-0x80000000)[0]) end
      local function battle() local g=word({e.A('GAME_STATE')})%65536; return g==1 or g==4 or g==5 end
      IP.prof={{}}; IP.pstart={{}}; IP.retbps={{}}
      IP.gpu={{passes=0,peak=0,violations=0,first=nil,writers={{}},moves={{}},
        swaps=0,swapPeak=0,menuSwaps=0,menuPeak=0,pauseSwaps=0,pausePeak=0,itemSwaps=0,itemPeak=0,noItemPeak=0}}
      -- Every presented frame, pause frames included (pauseFrame never calls applyDrawOffset):
      -- the packets used when the buffer is swapped, split by command menu shown and game paused.
      IP.bp[5]=PCSX.addBreakpoint({e.A('GsSwapDispBuff')},'Exec',4,'portal-swap',function()
        if not battle() then return end
        local frame=word({e.A('ACTIVE_FRAMEBUFFER')})
        if frame~=0 and frame~=1 then return end
        local used=word({e.A('GsOUT_PACKET_P')})-({e.A('GS_WORK_BASES')}+frame*0x14000)
        local g=IP.gpu
        g.swaps=g.swaps+1
        if used>g.swapPeak then g.swapPeak=used end
        if word({e.A('BTL_COMMAND_MENU_ACTIVE')})==1 then
          g.menuSwaps=g.menuSwaps+1
          if used>g.menuPeak then g.menuPeak=used end
        end
        if word({e.A('IS_INVENTORY_INITIALIZED')})%256==1 then
          g.itemSwaps=g.itemSwaps+1
          if used>g.itemPeak then g.itemPeak=used end
        elseif used>g.noItemPeak then g.noItemPeak=used end
        if word({e.A('PAUSE_STATE')})%256~=0 then
          g.pauseSwaps=g.pauseSwaps+1
          if used>g.pausePeak then g.pausePeak=used end
        end
        if used<0 or used>0x14000 then g.violations=g.violations+1 end
      end)
      IP.bp[6]=PCSX.addBreakpoint({e.A('renderInventoryTop')},'Exec',4,'portal-inv-top',function()
        local frame=word({e.A('ACTIVE_FRAMEBUFFER')})
        if frame~=0 and frame~=1 then return end
        IP.gpu.invStart=word({e.A('GsOUT_PACKET_P')})-({e.A('GS_WORK_BASES')}+frame*0x14000)
      end)
      local function boxStart()
        local frame=word({e.A('ACTIVE_FRAMEBUFFER')})
        if frame~=0 and frame~=1 or IP.gpu.bs then return end
        local r=PCSX.getRegisters()
        IP.gpu.bs=word({e.A('GsOUT_PACKET_P')})-({e.A('GS_WORK_BASES')}+frame*0x14000)
        IP.gpu.bi=r.GPR.n.a0
        if not IP.raBp then
          IP.raBp=r.GPR.n.ra
          IP.bp[9]=PCSX.addBreakpoint(IP.raBp,'Exec',4,'portal-box-end',function()
            local g=IP.gpu
            if not g.bs then return end
            local frame=word({e.A('ACTIVE_FRAMEBUFFER')})
            local used=word({e.A('GsOUT_PACKET_P')})-({e.A('GS_WORK_BASES')}+frame*0x14000)
            local d=used-g.bs
            local i=g.bi
            g.boxMax=g.boxMax or {{}}
            if word({e.A('IS_INVENTORY_INITIALIZED')})%256==1 and i>=0 and i<4 then
              if d>(g.boxMax[i] or 0) then g.boxMax[i]=d end
              g.frameSum=(g.frameSum or 0)+d
            end
            g.bs=nil
          end)
        end
      end
      IP.bp[7]=PCSX.addBreakpoint({e.A('renderUIBoxStatic')},'Exec',4,'portal-box-s',boxStart)
      IP.bp[8]=PCSX.addBreakpoint({e.A('renderUIBoxAnimated')},'Exec',4,'portal-box-a',boxStart)
      if {pad}>0 then
        -- Test load: a battle scene that has already used {pad} bytes of the frame's packet area, as the
        -- heaviest technique frames do. Every render pass starts that far in; nothing else changes.
        IP.bp[10]=PCSX.addBreakpoint({e.A('renderObjects')},'Exec',4,'portal-pad',function()
          if not battle() then return end
          local frame=word({e.A('ACTIVE_FRAMEBUFFER')})
          if frame~=0 and frame~=1 then return end
          local p=ffi.cast('uint32_t*',PCSX.getMemPtr()+{e.A('GsOUT_PACKET_P')}-0x80000000)
          p[0]=p[0]+{pad}
        end)
      end
      IP.bp[3]=PCSX.addBreakpoint({e.A('applyDrawOffset')},'Exec',4,'portal-packets',function()
        local frame=word({e.A('ACTIVE_FRAMEBUFFER')})
        if frame~=0 and frame~=1 then IP.gpu.violations=IP.gpu.violations+1; return end
        local used=word({e.A('GsOUT_PACKET_P')})-({e.A('GS_WORK_BASES')}+frame*0x14000)
        IP.gpu.passes=IP.gpu.passes+1
        if used>IP.gpu.peak then IP.gpu.peak=used end
        local g=IP.gpu
        if (g.frameSum or 0)>(g.frameMax or 0) then g.frameMax=g.frameSum end
        g.frameSum=0
        if word({e.A('IS_INVENTORY_INITIALIZED')})%256==1 then
          g.pItemN=(g.pItemN or 0)+1
          if g.invStart then
            local d=used-g.invStart
            if d>(g.invDelta or 0) then g.invDelta=d end
            g.invStart=nil
          end
          if used>(g.pItemPeak or 0) then g.pItemPeak=used end
        else
          if used>(g.pNoPeak or 0) then g.pNoPeak=used end
        end
        if used<0 or used>0x14000 or word({e.A('GS_ORDERING_TABLE')}+frame*20)~=12 then
          IP.gpu.violations=IP.gpu.violations+1
          if not IP.gpu.first then IP.gpu.first=string.format('used=%d frame=%d',used,frame) end
        end
      end)
      IP.bp[4]=PCSX.addBreakpoint({e.A('GS_ORDERING_TABLE')},'Write',40,'portal-ot',function(address,width,cause)
        if not battle() then return end
        local pc=string.format('%08x',PCSX.getRegisters().pc)
        IP.gpu.writers[pc]=(IP.gpu.writers[pc] or 0)+1
        -- the caller of a stranger: the function that drew past the area
        local ra=string.format('%08x',PCSX.getRegisters().GPR.n.ra)
        IP.gpu.callers=IP.gpu.callers or {{}}
        IP.gpu.callers[ra]=(IP.gpu.callers[ra] or 0)+1
      end)
      {profile_lua(e, pad) if profile else ""}
      return 'armed' ''').strip()
    assert out == 'armed', f'GPU monitor: {out!r}'


def gpu_report(e):
    raw = e.run('lua', '''
      local w={} for k,v in pairs(IP.gpu.writers) do w[#w+1]=string.format('"%s":%d',k,v) end
      local g=IP.gpu
      return string.format('{"passes":%d,"peak":%d,"violations":%d,"first":"%s","swaps":%d,"swap_peak":%d,"menu_swaps":%d,"menu_peak":%d,"pause_swaps":%d,"pause_peak":%d,"item_swaps":%d,"item_peak":%d,"no_item_peak":%d,"pass_item_n":%d,"pass_item_peak":%d,"pass_no_item_peak":%d,"inv_delta":%d,"box0":%d,"box1":%d,"box2":%d,"box3":%d,"boxes_frame_max":%d,"writers":{%s}}',
        g.passes,g.peak,g.violations,g.first or '',g.swaps,g.swapPeak,g.menuSwaps,g.menuPeak,g.pauseSwaps,g.pausePeak,g.itemSwaps,g.itemPeak,g.noItemPeak,g.pItemN or 0,g.pItemPeak or 0,g.pNoPeak or 0,g.invDelta or 0,(g.boxMax or {})[0] or 0,(g.boxMax or {})[1] or 0,(g.boxMax or {})[2] or 0,(g.boxMax or {})[3] or 0,g.frameMax or 0,table.concat(w,','))''').strip()
    try:
        report = json.loads(raw)
    except ValueError:
        raise AssertionError(f'GPU monitor report: {raw!r}') from None
    # Only the ordering-table clear may write its headers; any other writer is a packet run past the area
    # (a pass that crashes mid-frame never reaches the peak sample).
    others = tuple(p + '_' for p in ('BTL', 'STD', 'VS') if p != OVERLAY)
    names = sorted((a, n) for n, a in e.table.items()
                   if isinstance(a, int) and 0x80010000 <= a < 0x80200000 and '.' not in n
                   and not n.startswith(others))
    def owner(pc):
        i = bisect.bisect_right(names, (pc, chr(0x10ffff))) - 1
        return names[i][1] if i >= 0 else '?'
    prof = e.run('lua', '''
      local o={} for k,v in pairs(IP.prof or {}) do
        o[#o+1]=string.format('"%s":[%d,%d,%d,%d]',k,v.calls,v.max,v.fmax,v.over) end
      return '{'..table.concat(o,',')..'}' ''').strip()
    callers = e.run('lua', '''
      local o={} for k,v in pairs(IP.gpu.callers or {}) do o[#o+1]=string.format('"%s":%d',k,v) end
      return '{'..table.concat(o,',')..'}' ''').strip()
    report['callers'] = {f'{ra}:{owner(int(ra, 16))}': n for ra, n in json.loads(callers).items()}
    rend = e.run('lua', '''
      local o={} for k,v in pairs(IP.rend or {}) do
        o[#o+1]=string.format('"%s":[%d,%d,%d]',k,v.calls,v.max,v.fmax) end
      return '{'..table.concat(o,',')..'}' ''').strip()
    report['renderers'] = {f'{owner(int(a, 16))}:{a[-6:]}': dict(zip(('calls', 'max_call', 'max_frame'), v))
                           for a, v in json.loads(rend).items()}
    worst = e.run('lua', '''
      local o={} for k,v in pairs((IP.gpu.worst) or {}) do o[#o+1]=string.format('"%s":%d',k,v) end
      return string.format('{"used":%d,"other":%d,"objects":{%s}}',IP.gpu.worstUsed or 0,IP.gpu.worstOther or 0,table.concat(o,','))''').strip()
    worst = json.loads(worst)
    worst['objects'] = {f'{owner(int(a, 16))}:{a[-6:]}': n for a, n in worst['objects'].items() if n}
    report['worst_frame'] = worst
    report['profile'] = {k: dict(zip(('calls', 'max_call', 'max_frame', 'over'), v)) for k, v in json.loads(prof).items()}
    report['strangers'] = {f'{pc}:{owner(int(pc, 16))}': n for pc, n in report['writers'].items()
                           if owner(int(pc, 16)) not in ('GsClearOt', '_otc')}
    return report


def prepare_fixture(e, species, quick, technique, offense, all_join):
    """Evolve the fixture partner, give it stats and one equipped technique, and hand it back in the field."""
    evolve_fixture(e, species)
    # The type changes before the EVL scene releases its overlay and objects.
    # Wait for partner field control before starting another map or overlay.
    for _ in range(180):
        if e.peek('PARTNER_STATE','B') != 13 and e.peek('TAMER_STATE','B') == 0 and not e.peek('IS_IN_MENU','i'):
            break
        if e.peek('IS_IN_MENU','i'):e.press('CANCEL',8)
        elif e.peek('PARTNER_STATE','B') == 13:e.press('START',8)
        else:e.press('CONFIRM',8)
        e.wait(.3)
    else:raise AssertionError('fixture evolution did not release field control')
    e.wait(1)
    e.poke('PAUSE_STATE', b'\0')
    e.gs('set', 'gametime_running=0', 'partner.para.condition=0', 'partner.para.age=1',
         'partner.para.evoTimer=0', 'partner.para.remainingLifetime=1000',
         'partner.stats.hp=9999', 'partner.stats.mp=9999',
         'partner.stats.currentHP=9999', 'partner.stats.currentMP=9999', f'partner.stats.off={offense}',
         'partner.stats.def=999', 'partner.stats.speed=999', 'partner.stats.brain=999')
    e.poke('MOD_OPT_QUICK_BATTLE', struct.pack('<i', quick))
    if technique is not None:
        equip_only(e, technique)
    if all_join:
        # Seed only the join roll; visibility, collision and the three-enemy
        # limit still choose the participants through native encounter code.
        e.poke('FLEE_CHANCES', bytes([100]) * 12)
    for _ in range(12):
        if e.peek('IS_IN_MENU', 'i'):
            e.press('CANCEL', 8)
        elif e.peek('TAMER_STATE', 'B') == 20:
            e.press('CONFIRM', 8)
        else:
            break
        e.wait(.2)
    e.poke('PAUSE_STATE', b'\0')


def encounter(e, out, species, quick, cleanup, video_seconds=35, all_join=False, city_entrance=False,
              technique=None, offense=999, menu=False, items=False, cleanup_frames=90, timeout=600):
    prepare_fixture(e, species, quick, technique, offense, all_join)
    if items:
        e.poke('INVENTORY', struct.pack('<30h', *range(1, 31)) + bytes([99] * 30) + bytes(30) + bytes([30]))
    assert e.warp(168 if city_entrance else 167, 0), 'source room did not load'
    stem=f'partner-{species}-quick-{quick}'+(f'-tech-{technique}' if technique is not None else '')
    before=sample(e)
    e.run('save', str(out/(stem+'-source.state')))
    rows=[before]
    with ThreadPoolExecutor() as pool:
        video=pool.submit(e.run,'record',str(out/(stem+'.mp4')),str(video_seconds)) if video_seconds else None
        # Step trigger 0 is the portal returning to 166, arrival 1. Move onto
        # its real tile; the game's script performs the walk and warp.
        if city_entrance:
            # Run File City's real Mt. Infinity entrance handler (arrival 0).
            call(e, 'callScriptSection', e.peek('CURRENT_SCRIPT_ID', 'H'), 56, 1)
            e.run('resume')
        else:
            e.gs('move', '1200', '1200')
        end=time.monotonic()+timeout
        started=False; frame_start=None; auto=False; cleaned=False; window=None
        while time.monotonic()<end:
            row=sample(e);rows.append(row)
            (out/(stem+'-samples.json')).write_text(json.dumps(rows,indent=2)+'\n')
            row['gpu_monitor']=gpu_report(e)
            assert row['heap']['corrupt'] is None, row['heap']
            assert row['gpu_monitor']['violations']==0 and not row['gpu_monitor']['strangers'], row['gpu_monitor']
            assert row['running'] and row['stream_failures'] == 0 and row['battle_cold_reads'] == 0, row
            assert row['gpu']['ot_lengths']==12 and row['gpu']['ot1_length']==12, row['gpu']
            if row['CURRENT_SCREEN']==166 and row['GAME_STATE']==1:
                started=True
                if row['BATTLE_FRAME_COUNT']>=20 and row['MOD_BATTLE_LOADING']==0:
                    if window is None:
                        window = row['tile_window']
                    assert row['tile_window'] == window, 'tile window moved during battle'
                    if frame_start is None:
                        frame_start=row['BATTLE_FRAME_COUNT']
                        e.run('shot',str(out/(stem+'-battle.png')))
                    if row['BATTLE_FRAME_COUNT']-frame_start>=cleanup_frames and cleanup and not cleaned:
                        for enemy in row['participants']:
                            e.poke(f'NPC_ENTITIES+{104*enemy["slot"]+0x4c}',b'\0\0')
                        cleaned=True
                if items:
                    # The battle item menu (Triangle): full bag, open it, scroll, close it, repeat.
                    e.press('TRIANGLE',8)
                    e.wait(.7)
                    e.press('DOWN',8); e.press('DOWN',8); e.press('RIGHT',8)
                    e.wait(.3)
                    if items == 'throw':
                        e.press('CONFIRM',8); e.wait(.4); e.press('CONFIRM',8); e.wait(.8)
                    e.press('CANCEL',8)
                    e.wait(.4)
                    if row['participants'] and all(n['hp'] <= 0 for n in row['participants']):
                        e.press('CONFIRM',8)
                elif menu:
                    # A player working the battle menu: move along the command ring and pause with
                    # START (the pause box is drawn over the same frame). Pausing re-renders the
                    # whole scene, so the pause frames are what could exceed a normal frame.
                    e.press('RIGHT',8)
                    e.press('START',8)
                    e.wait(.4)
                    e.press('START',8)
                    if row['participants'] and all(n['hp'] <= 0 for n in row['participants']):
                        e.press('CONFIRM',8)
                elif not auto:
                    e.press('CONFIRM',8);auto=True
                elif row['participants'] and all(n['hp'] <= 0 for n in row['participants']):
                    e.press('CONFIRM',8)
                else:
                    e.press('CIRCLE',8)
            # The interrupted arrival walk may touch the return portal before
            # the observer's next sample. Both rooms are valid field returns.
            elif started and row['CURRENT_SCREEN'] in (166,168 if city_entrance else 167) and row['GAME_STATE']==0 and row['TAMER_STATE']==0:
                e.run('shot',str(out/(stem+'-after.png')))
                break
            else:
                e.press('CONFIRM',8)
            e.wait(.4)
        else:
            raise AssertionError(f'{stem}: encounter did not return to field')
        assert frame_start is not None, 'battle did not advance'
        if all_join:
            assert any(len(r['participants']) == 3 for r in rows), 'triple battle absent'
        assert any(len([n for n in r['enemies'] if n['species']==88])>=3 for r in rows), 'three Vermilimon absent'
        if video is not None:
            video.result()
    result=dict(species=species,quick=quick,technique=technique,forced_cleanup=cleaned,all_join=all_join,
                city_entrance=city_entrance,gpu=gpu_report(e),samples=rows)
    (out/(stem+'.json')).write_text(json.dumps(result,indent=2)+'\n')
    print('PASS',stem,flush=True)


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('disc');p.add_argument('--exe',required=True)
    p.add_argument('--out',type=Path,required=True);p.add_argument('--port',type=int,default=39711)
    p.add_argument('--card',type=Path);p.add_argument('--state',type=Path);p.add_argument('--species',type=int,nargs='+',default=[3,407])
    p.add_argument('--quick',type=int,nargs='+',default=[0,1]);p.add_argument('--cleanup',action='store_true')
    p.add_argument('--city-entrance', action='store_true', help='enter from File City instead of the lower return portal')
    p.add_argument('--ram8', action='store_true', help='repeat the same encounter with expanded emulator RAM')
    p.add_argument('--video-seconds', type=int, default=35, help='set 0 to keep samples and screenshots only')
    p.add_argument('--all-join', action='store_true', help='seed bystander join chances to require a triple battle')
    p.add_argument('--technique', type=int, help='leave the partner only this learned and equipped technique')
    p.add_argument('--offense', type=int, default=999, help='partner Offense (lower keeps the battle going longer)')
    p.add_argument('--menu', action='store_true', help='work the battle command menu (ring moves) and pause with START instead of the usual auto presses')
    p.add_argument('--items', choices=['open','throw'], help='battle item menu (Triangle) with a full bag: open and close it, or throw an item')
    p.add_argument('--pad-packets', type=int, default=0, help='test load: every battle render pass starts this many bytes into the frame packet area')
    p.add_argument('--profile', action='store_true', help='per-renderer packet bytes (largest call and per-frame total)')
    p.add_argument('--cleanup-frames', type=int, default=90, help='with --cleanup, battle frames before the enemies are zeroed')
    p.add_argument('--timeout', type=int, default=600, help='seconds the encounter may take')
    p.add_argument('--repeat', type=int, default=1, help='run every combination this many times')
    a=p.parse_args();out=a.out.resolve();out.mkdir(parents=True,exist_ok=True)
    e=ProofEmu(a.disc,a.exe,a.port,str(out/'emu'))
    e.expanded_ram = a.ram8
    e.env['EMU_ARGS'] = '-interpreter -debugger' + (' -8mb' if a.ram8 else '')
    if a.ram8:
        # Heap and gameplay addresses remain in the original 2 MB region.
        e.ram = lambda: e.api('/api/v1/cpu/ram/raw')[:0x200000]
    for name,(addr,_,_) in elf_symbols(a.exe+'.elf').items():e.table.setdefault(name,addr)
    try:
        e.start(str(a.card.resolve()) if a.card else test_card(out))
        if a.state:
            e.run('load',str(a.state.resolve()));e.run('resume')
        else:assert e.continue_game()==0, 'Continue failed'
        if os.environ.get('PACKET_LANG'):
            # a multi-language build: switch the language the way the options menu does (index as in modSetLanguage)
            call(e, 'modSetLanguage', int(os.environ['PACKET_LANG']))
            assert e.peek('MOD_LANG', 'i') == int(os.environ['PACKET_LANG']), 'language did not switch'
        e.run('lua', f'''IP={{streamFailures=0,coldReads=0,bp={{}}}}
          local m=PCSX.getMemPtr()
          local function battle() return tonumber(m[{e.A('GAME_STATE') & 0x1fffff}])~=0 end
          IP.bp[1]=PCSX.addBreakpoint({e.A('tfsStreamOpen')},'Exec',4,'portal-stream',function()
            if battle() then IP.streamFailures=IP.streamFailures+1 end
          end)
          IP.bp[2]=PCSX.addBreakpoint({e.A('loadColdAnimation')},'Exec',4,'portal-cold',function()
            if battle() then IP.coldReads=IP.coldReads+1 end
          end)''')
        gpu_monitor(e, a.pad_packets, a.profile)
        base=out/'base.state';e.run('save',str(base))
        for run in range(a.repeat):
          for species in a.species:
            for quick in a.quick:
                e.run('load',str(base));e.run('resume')
                e.run('lua','IP.gpu.passes=0;IP.gpu.peak=0;IP.gpu.violations=0;IP.gpu.first=nil;IP.gpu.writers={};IP.gpu.callers={};IP.gpu.swaps=0;IP.gpu.swapPeak=0;IP.gpu.menuSwaps=0;IP.gpu.menuPeak=0;IP.gpu.pauseSwaps=0;IP.gpu.pausePeak=0;IP.gpu.itemSwaps=0;IP.gpu.itemPeak=0;IP.gpu.noItemPeak=0;IP.gpu.pItemN=0;IP.gpu.pItemPeak=0;IP.gpu.pNoPeak=0;IP.gpu.invDelta=0;IP.gpu.boxMax={};IP.gpu.frameMax=0;IP.gpu.frameSum=0;IP.prof={};IP.pstart={};IP.rend={};IP.rstart={};IP.gpu.worstUsed=0;IP.gpu.worst={};IP.gpu.worstOther=0')
                encounter(e,out,species,quick,a.cleanup,a.video_seconds,a.all_join,a.city_entrance,a.technique,a.offense,a.menu,a.items,a.cleanup_frames,a.timeout)
                print('gpu', json.dumps(gpu_report(e)), flush=True)
    except BaseException:
        e.run('shot',str(out/'failure.png'),check=False)
        try:print('gpu at failure', json.dumps(gpu_report(e)), flush=True)
        except Exception as error:print('gpu report failed', error, flush=True)
        e.run('save',str(out/'failure.state'),check=False)
        raise
    finally:e.stop()


if __name__=='__main__':main()
