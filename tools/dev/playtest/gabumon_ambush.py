#!/usr/bin/env python3
"""Exercise screen 45's third Gabumon dialogue and battle, with heap diagnostics.

Run separately for each disc and RAM size. --force-kotemon adds the dormant
map slot through the game's model/entity loaders, recreating the pre-separation
four-NPC layout without changing the disc. This is a diagnostic setup, not a
claim that the supplied disc normally spawns Kotemon during the ambush.
"""
import argparse
import hashlib
import itertools
import json
import math
from pathlib import Path
import shutil
import struct
import sys
import time
import urllib.parse
import urllib.request

ROOT = Path(__file__).resolve().parents[3]
sys.path[:0] = [str(ROOT), str(ROOT / 'tools')]
from tools.dev.playtest.eggs import EggEmu, evolve
from tools.dev.playtest.ogre_tunnel import call
from tools.dev.playtest.qol import test_card
from tools.langpatch import elf_symbols
from tools.membudget import Ram, heap_walk


class AmbushEmu(EggEmu):
    """Use the harness's HTTP endpoints directly for frequent RAM/Lua calls."""
    def ram(self):
        data = self.api('/api/v1/cpu/ram/raw')
        assert len(data) == self.ram_mb * 1024 * 1024
        return data

    def set_backend(self, backend):
        """Preserve the complete scene while restarting with another CPU core."""
        expected = backend == 'dynarec'
        if json.loads(self.api('/api/v1/execution-flow'))['isDynarec'] == expected:
            return
        checkpoint = Path(self.home).parent / 'backend.state'
        self.run('save', str(checkpoint.resolve()))
        self.stop()
        self.env['EMU_ARGS'] = ('-interpreter -debugger' if not expected else '') + (' -8mb' if self.ram_mb == 8 else '')
        self.run('start', self.disc, '--keep-cards')
        self.run('load', str(checkpoint.resolve()))
        self.run('lua', 'PCSX.resumeEmulator()')
        flow = json.loads(self.api('/api/v1/execution-flow'))
        assert flow['isDynarec'] == expected, flow
        assert len(self.ram()) == self.ram_mb * 1024 * 1024

    def press(self, button, frames=10):
        if button in ('CONFIRM', 'CANCEL'):
            japanese = self.peek('MOD_OPT_BUTTONS', 'i') != 0
            button = ('CIRCLE' if japanese else 'CROSS') if button == 'CONFIRM' else ('CROSS' if japanese else 'TRIANGLE')
        frames = max(frames, 8)
        self.run('lua', f'''
          AMBUSH_PAD={{n=0,done=false}}
          local pad=PCSX.SIO0.slots[1].pads[1]
          local b=PCSX.CONSTS.PAD.BUTTON.{button}
          pad.setOverride(b)
          AMBUSH_PAD.listener=PCSX.Events.createEventListener('GPU::Vsync',function()
            AMBUSH_PAD.n=AMBUSH_PAD.n+1
            if AMBUSH_PAD.n=={frames} then pad.clearOverride(b) end
            if AMBUSH_PAD.n=={frames+4} then
              AMBUSH_PAD.done=true; AMBUSH_PAD.listener:remove()
            end
          end)
        ''')
        try:
            deadline = time.monotonic() + 60
            while time.monotonic() < deadline:
                if self.run('lua', 'return AMBUSH_PAD.done or (AMBUSH_RETURN and AMBUSH_RETURN.seen) or false').strip() == 'true':
                    return
                self.wait(.2)
            raise AssertionError(f'{button}: no emulated refreshes for 60 seconds')
        finally:
            self.api(f'/api/v1/lua/release?button={button}')
            self.run('lua', 'if not AMBUSH_PAD.done then AMBUSH_PAD.listener:remove() end; AMBUSH_PAD.listener=nil')

    def warp(self, screen, ex=0):
        self.api('/api/v1/execution-flow?function=pause')
        try:
            self.poke('TAMER_SUB_STATE', b'\0')
            self.poke('TARGET_MAP', struct.pack('<h', screen))
            self.poke('CURRENT_EXIT', bytes([ex]))
            self.poke('TAMER_STATE', b'\5')
        finally:
            self.api('/api/v1/execution-flow?function=start')
        deadline = time.monotonic() + 300
        while time.monotonic() < deadline:
            self.wait(1)
            ram = self.ram()
            if self.peek('CURRENT_SCREEN', 'h', ram) == screen and self.peek('TAMER_STATE', 'B', ram) == 0:
                return True
        return False

    def poke(self, expr, data):
        req = urllib.request.Request(
            f'http://127.0.0.1:{self.port}/api/v1/cpu/ram/raw?offset={self.A(expr)-0x80000000}&size={len(data)}',
            data=data, method='POST')
        with urllib.request.urlopen(req, timeout=15) as response:
            response.read()

    def run(self, *args, check=True):
        if args[0] == 'lua':
            code = args[1]
            if len(urllib.parse.quote(code)) >= 150:
                path = Path(self.home).parent / f'ambush-call-{self.port}.lua'
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text(code)
                query = 'file=' + urllib.parse.quote(str(path.resolve()))
            else:
                query = 'code=' + urllib.parse.quote(code)
            return self.api('/api/v1/lua/eval?' + query).decode()
        result = super().run(*args, check=check)
        if args[0] == 'load':
            # A restored scene can replace code previously compiled at the
            # same overlay addresses. Discard host translations of that code.
            self.run('lua', 'PCSX.invalidateCache()')
        return result


def snapshot(e):
    ram = e.ram()
    values = {n: e.peek(n, fmt, ram) for n, fmt in (
        ('CURRENT_SCREEN', 'h'), ('GAME_STATE', 'B'), ('TAMER_STATE', 'B'),
        ('PARTNER_STATE', 'B'), ('IS_SCRIPT_PAUSED', 'i'), ('ACTIVE_INSTRUCTION', 'B'),
        ('SCRIPT_SECTION', 'H'), ('TALKED_TO_ENTITY', 'B'), ('BATTLE_FRAME_COUNT', 'h'),
        ('ENEMY_COUNT', 'h'), ('PARTNER_ENTITY', 'i'), ('MOD_BTL_PRELOAD', 'b'),
        ('MOD_BTL_PRELOAD_BLOCKED', 'b'), ('MOD_BATTLE_LOADING', 'b'),
        ('MOD_COLD_CACHE_TYPE', 'i'), ('MOD_OPT_QUICK_BATTLE', 'i')) if e.has(n)}
    values['ram_bytes'] = len(ram)
    values['kotemon_recruited'] = bool(e.peek('SPECIES_RECRUITED_BITS+43', 'B', ram) & 0x80)
    values['heap'] = heap_walk(Ram(ram, e.table))
    values['npc_models'] = [e.peek(f'NPC_MODELS+{i*28+24}', 'h', ram)
                            for i in range(5) if e.peek(f'NPC_MODELS+{i*28}', 'i', ram)]
    values['entities'] = [e.peek(f'ENTITY_TABLE+{i*4}', 'I', ram) for i in range(10)]
    # Four FighterData records (360 bytes each), then PlayerData.entityIds.
    values['fighter_ids'] = e.peek('COMBAT_DATA+0x66c', '4B', ram)
    values['fighter_species'] = [struct.unpack_from('<I', ram, values['entities'][i]-0x80000000)[0]
                                 if i < 10 and 0x80000000 <= values['entities'][i] < 0x80000000+len(ram)-4 else None
                                 for i in values['fighter_ids']]
    frame = e.peek('ACTIVE_FRAMEBUFFER', 'i', ram)
    packet_base = e.A('GS_WORK_BASES') + frame * 0x14000
    packet_cursor = e.peek('GsOUT_PACKET_P', 'I', ram)
    values['gpu_packets'] = dict(frame=frame, base=packet_base, cursor=packet_cursor,
                                 used=packet_cursor-packet_base, capacity=0x14000,
                                 ordering_tables=e.peek('GS_ORDERING_TABLE', '10I', ram))
    values['cpu'] = e.run('lua', 'local r=PCSX.getRegisters(); return string.format("pc=%08x ra=%08x",r.pc,r.GPR.n.ra)').strip()
    return values


def start_gpu_monitor(e):
    """Measure render passes, including undisplayed fast ticks; the interpreter executes the watch callback."""
    if json.loads(e.api('/api/v1/execution-flow'))['isDynarec']:
        return False
    symbols = elf_symbols(e.exe + '.elf')
    gather = symbols['BTL_renderBattleStartText']
    burst = symbols['BTL_renderBattleStartTextBurst']
    e.run('lua', f"""
      local ffi=require('ffi')
      local function word(a)
        return tonumber(ffi.cast('uint32_t*',PCSX.getMemPtr()+a-0x80000000)[0])
      end
      AMBUSH_GPU={{passes=0,peak=0,violations=0,tail_peak=0,banner_passes=0,gather_calls=0,burst_calls=0}}
      AMBUSH_GPU.work=PCSX.addBreakpoint({e.A('GsSetWorkBase')},'Exec',4,'ambush-banner-end',function()
        local r=PCSX.getRegisters()
        local ra=r.GPR.n.ra
        local frame=word({e.A('ACTIVE_FRAMEBUFFER')})
        if r.GPR.n.a0=={e.A('GS_WORK_BASES')}+frame*0x14000 then
          AMBUSH_GPU.banner_end=nil; AMBUSH_GPU.banner_frame=nil
        end
        if (ra>={gather[0]} and ra<{gather[0]+gather[1]}) or
           (ra>={burst[0]} and ra<{burst[0]+burst[1]}) then
          if ra>={gather[0]} and ra<{gather[0]+gather[1]} then
            AMBUSH_GPU.gather_calls=AMBUSH_GPU.gather_calls+1
          else
            AMBUSH_GPU.burst_calls=AMBUSH_GPU.burst_calls+1
          end
          AMBUSH_GPU.banner_end=r.GPR.n.a0
          AMBUSH_GPU.banner_frame=word({e.A('ACTIVE_FRAMEBUFFER')})
        end
        return true
      end)
      AMBUSH_GPU.bp=PCSX.addBreakpoint({e.A('applyDrawOffset')},'Exec',4,'ambush-packets',function()
        local frame=word({e.A('ACTIVE_FRAMEBUFFER')})
        if frame~=0 and frame~=1 then
          AMBUSH_GPU.violations=AMBUSH_GPU.violations+1; return true
        end
        local used=word({e.A('GsOUT_PACKET_P')})-({e.A('GS_WORK_BASES')}+frame*0x14000)
        if AMBUSH_GPU.banner_frame==frame and AMBUSH_GPU.banner_end then
          local tail=word({e.A('GsOUT_PACKET_P')})-AMBUSH_GPU.banner_end
          AMBUSH_GPU.tail_peak=math.max(AMBUSH_GPU.tail_peak,tail)
          AMBUSH_GPU.banner_passes=AMBUSH_GPU.banner_passes+1
          AMBUSH_GPU.banner_end=nil
        end
        AMBUSH_GPU.passes=AMBUSH_GPU.passes+1
        AMBUSH_GPU.peak=math.max(AMBUSH_GPU.peak,used)
        if used<0 or used>0x14000 or word({e.A('GS_ORDERING_TABLE')}+frame*20)~=12 then
          AMBUSH_GPU.violations=AMBUSH_GPU.violations+1
        end
        return true
      end)
    """)
    return True


def finish_gpu_monitor(e):
    values = e.run('lua', "return string.format('%d,%d,%d,%d,%d,%d,%d',AMBUSH_GPU.passes,AMBUSH_GPU.peak,AMBUSH_GPU.violations,AMBUSH_GPU.tail_peak,AMBUSH_GPU.banner_passes,AMBUSH_GPU.gather_calls,AMBUSH_GPU.burst_calls)")
    e.run('lua', 'AMBUSH_GPU.bp:remove(); AMBUSH_GPU.work:remove(); AMBUSH_GPU.bp=nil; AMBUSH_GPU.work=nil')
    result = dict(zip(('passes', 'peak', 'violations', 'tail_peak', 'banner_passes', 'gather_calls', 'burst_calls'),
                      map(int, values.strip().split(','))))
    result['sample_point'] = 'applyDrawOffset'
    return result


def control(e):
    ram = e.ram()
    return (e.peek('GAME_STATE', 'B', ram) == 0 and e.peek('TAMER_STATE', 'B', ram) == 0
            and e.peek('IS_SCRIPT_PAUSED', 'i', ram) == 1)


def encounter(e, out):
    # Slot 2 owns section 7, the reported "W-wait a second!" line.
    gameplay = getattr(e, 'gameplay', False)
    if not gameplay:
        e.poke('BATTLE_FRAME_COUNT', b'\0\0')
    ram = e.ram()
    slots = [i for i in range(8) if e.peek(f'ENTITY_TABLE+{(i+2)*4}', 'I', ram)]
    flags = {} if gameplay else {i:e.peek(f'NPC_ENTITIES+{i*0x68+0x66}', 'B', ram) for i in slots}
    try:
        # Other nearby wild NPCs can start their own line first, especially
        # with a tall partner. Restore every flag before battle selection.
        for i in flags:
            e.poke(f'NPC_ENTITIES+{i*0x68+0x66}', bytes([1 if i == 2 else 0]))
        # Gameplay mode uses the existing positioning helper once, then only
        # controller input and observation until control returns after combat.
        e.gs('approach', '2', '500' if gameplay else '0')
        deadline = time.monotonic() + 300
        last_place = time.monotonic()
        while time.monotonic() < deadline:
            ram = e.ram()
            if (e.peek('IS_SCRIPT_PAUSED', 'i', ram) == 0 and e.peek('SCRIPT_SECTION', 'H', ram) == 7
                    and e.peek('TEXTBOX_OPEN_TIMER', 'B', ram) >= 10):
                break
            if gameplay:
                if e.peek('IS_SCRIPT_PAUSED', 'i', ram) == 0:
                    assert e.peek('SCRIPT_SECTION', 'H', ram) == 7, 'another NPC started a conversation'
                    e.wait(.2)
                    continue
                pd = e.peek('NPC_ENTITIES+212', 'I', ram)
                nx, _, nz = struct.unpack_from('<3i', ram, pd - 0x80000000 + 0x78)
                tx, _, tz = e.peek('TAMER_POSITION_DATA+0x78', '3i', ram)
                vx, _, vz, rx, _, rz = e.peek('GS_VIEWPOINT', '6i', ram)
                rotation = round(math.atan2(vz-rz, vx-rx) * 4096 / (2*math.pi) / 512) * 512
                target = math.atan2(nz-tz, nx-tx) * 4096 / (2*math.pi)
                choices = {'UP': rotation+2048, 'DOWN': rotation, 'LEFT': rotation+1024, 'RIGHT': rotation+3072}
                button = min(choices, key=lambda k: abs((choices[k]-target+2048) % 4096-2048))
                e.press(button, 8)
                e.press('CONFIRM', 8)
            elif e.peek('IS_SCRIPT_PAUSED', 'i', ram) == 1 and time.monotonic()-last_place >= 2:
                e.gs('approach', '2', '0')
                last_place = time.monotonic()
            e.wait(.2)
        else:
            raise AssertionError('third Gabumon dialogue did not open')
    finally:
        for i, flag in flags.items():
            e.poke(f'NPC_ENTITIES+{i*0x68+0x66}', bytes([flag]))
    e.run('shot', str(out / 'dialogue.png'))
    before = snapshot(e)
    (out / 'before.json').write_text(json.dumps(before, indent=2) + '\n')
    started = False
    battle = None
    banner_bucket = -1
    deadline = time.monotonic() + 300
    while time.monotonic() < deadline:
        ram = e.ram()
        frame = e.peek('BATTLE_FRAME_COUNT', 'h', ram)
        if (getattr(e, 'banner_shots', False) and e.peek('GAME_STATE', 'B', ram) == 1
                and e.peek('BTL_START_TEXT_ACTIVE', 'B', ram) == 1 and frame >= 5):
            bucket = min(frame // 8, 4)
            if bucket > banner_bucket:
                e.run('shot', str(out / f'banner-{frame:04d}.png'))
                banner_bucket = bucket
        if (e.peek('GAME_STATE', 'B', ram) == 1 and frame >= 5
                and e.peek('MOD_BATTLE_LOADING', 'b', ram) == 0):
            battle = snapshot(e)
            assert battle['SCRIPT_SECTION'] == 7 and battle['TALKED_TO_ENTITY'] == 4
            assert 1 <= battle['ENEMY_COUNT'] <= 3
            e.run('shot', str(out / 'battle.png'))
            started = True
            break
        e.press('CONFIRM', 8)
        e.wait(.3)
    if not started:
        return dict(started=False, before=before, failure=snapshot(e))
    if gameplay:
        # Polling from the host can miss a field frame before another touch
        # conversation. Pause on the first refresh with control, without
        # changing game RAM, so confirm cannot run through that return.
        e.run('lua', f'''
          local ffi=require('ffi')
          local function byte(a) return tonumber(ffi.cast('uint8_t*',PCSX.getMemPtr()+a-0x80000000)[0]) end
          AMBUSH_RETURN={{seen=false}}
          AMBUSH_RETURN.listener=PCSX.Events.createEventListener('GPU::Vsync',function()
            if byte({e.A('GAME_STATE')})==0 and byte({e.A('TAMER_STATE')})==0 and byte({e.A('IS_SCRIPT_PAUSED')})==1 then
              AMBUSH_RETURN.seen=true; AMBUSH_RETURN.listener:remove(); AMBUSH_RETURN.listener=nil
              PCSX.pauseEmulator()
            end
          end)
        ''')
    # Keep victory and teardown in the game; shorten only the fighting itself.
    deadline = time.monotonic() + (900 if gameplay else 300)
    while time.monotonic() < deadline:
        if control(e):
            e.run('shot', str(out / 'after.png'))
            return dict(started=True, returned=True, before=before, battle=battle, after=snapshot(e))
        for entity_id in ([] if gameplay else battle['fighter_ids'][1:1+battle['ENEMY_COUNT']]):
            assert 2 <= entity_id < 10
            e.poke(f'NPC_ENTITIES+{(entity_id-2)*0x68+0x4c}', b'\0\0')
        e.press('CONFIRM', 8)
        e.wait(.4)
    return dict(started=True, returned=False, before=before, battle=battle, failure=snapshot(e))


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('disc')
    p.add_argument('--exe', required=True)
    p.add_argument('--out', required=True)
    p.add_argument('--port', type=int, default=39941)
    p.add_argument('--ram-mb', type=int, choices=(2, 8), default=2)
    p.add_argument('--cpu', choices=('dynarec', 'interpreter'), default='interpreter')
    p.add_argument('--partners', default='3,330,373,461')
    p.add_argument('--quick', default='0,1')
    p.add_argument('--recruited', default='0,1')
    p.add_argument('--force-kotemon', action='store_true')
    p.add_argument('--layouts', default='normal', help='comma-separated normal,forced layouts')
    p.add_argument('--boot-state', help='reuse this probe\'s boot.state with its matching boot.json')
    p.add_argument('--resume', action='store_true', help='keep completed cases in the output and rerun unfinished cases')
    p.add_argument('--prior-battle', action='store_true')
    p.add_argument('--banner-shots', action='store_true', help='capture the early running-fight banner for review')
    p.add_argument('--keep-going', action='store_true', help='capture failed encounters and continue the matrix')
    p.add_argument('--gameplay', action='store_true', help='position 500 units away, then use only controller input through the full fight; normal layout only')
    a = p.parse_args()
    layouts = ['forced'] if a.force_kotemon else a.layouts.split(',')
    if not layouts or any(n not in ('normal', 'forced') for n in layouts):
        p.error('--layouts accepts normal,forced')
    if a.gameplay and layouts != ['normal']:
        p.error('--gameplay requires the normal layout')
    out = Path(a.out).resolve(); out.mkdir(parents=True, exist_ok=True)
    e = AmbushEmu(a.disc, a.exe, a.port, str(out / 'emu'))
    e.ram_mb = a.ram_mb
    e.banner_shots = a.banner_shots
    e.gameplay = a.gameplay
    e.env['EMU_ARGS'] = ('-interpreter -debugger' if a.cpu == 'interpreter' else '') + (' -8mb' if a.ram_mb == 8 else '')
    for n, (addr, _, _) in elf_symbols(a.exe + '.elf').items():
        e.table.setdefault(n, addr)
    result = dict(ram_mb=a.ram_mb, cpu_backend=a.cpu, disc=Path(a.disc).name,
                  exe_sha256=hashlib.sha256(Path(a.exe).read_bytes()).hexdigest(),
                  main_BSS_END=e.A('main_BSS_END'), layouts=layouts,
                  prior_battle=a.prior_battle, cases=[])
    result['gameplay'] = a.gameplay
    if a.resume and (out / 'result.json').exists():
        previous = json.loads((out / 'result.json').read_text())
        assert previous.get('gameplay', False) == a.gameplay, 'resume changes gameplay mode'
        for key in ('ram_mb', 'exe_sha256', 'layouts', 'prior_battle'):
            assert previous[key] == result[key], f'resume changes {key}'
        result['cases'] = [r for r in previous['cases'] if r.get('returned') or (a.keep_going and ('error' in r or 'failure' in r))]
    def completed(species, quick, recruited, layout):
        return any((r['partner'], r['quick'], r['recruited'], r['layout']) == (species, quick, recruited, layout)
                   for r in result['cases'])
    try:
        if a.boot_state:
            metadata = json.loads(Path(a.boot_state).with_suffix('.json').read_text())
            assert metadata == dict(exe_sha256=result['exe_sha256'], ram_mb=a.ram_mb)
            e.start(None)
            e.run('load', str(Path(a.boot_state).resolve()))
            e.run('lua', 'PCSX.resumeEmulator()')
            assert control(e), 'boot checkpoint is not in field control'
        else:
            print('booting', flush=True)
            e.start(test_card(out, language=1))
            assert e.continue_game() == 0
            e.gs('set', 'hour=10', 'gametime_running=0', 'partner.para.remainingLifetime=500')
            e.poke('MOD_OPT_STORY', struct.pack('<i', 1))
            e.gs('trigger', '150', '0')
            e.gs('trigger', '1', '1')
        e.run('save', str(out / 'boot.state'))
        (out / 'boot.json').write_text(json.dumps(dict(exe_sha256=result['exe_sha256'], ram_mb=a.ram_mb)) + '\n')
        print('boot ready', flush=True)
        for species in map(int, a.partners.split(',')):
            combinations = list(itertools.product(map(int, a.quick.split(',')), map(int, a.recruited.split(',')), layouts))
            if all(completed(species, *case) for case in combinations):
                continue
            e.run('load', str(out / 'boot.state')); e.run('lua', 'PCSX.resumeEmulator()')
            evolve(e, species)
            e.gs('set', 'partner.para.age=1', 'partner.para.evoTimer=0', 'partner.para.condition=0',
                 'partner.stats.hp=9000', 'partner.stats.mp=9000', 'partner.stats.currentHP=9000',
                 'partner.stats.currentMP=9000', 'partner.stats.off=900', 'partner.stats.def=900')
            if a.prior_battle:
                from tools.dev.playtest.eggs import battle_before_death
                assert battle_before_death(e, out)
            e.run('save', str(out / 'partner.state'))
            for quick, recruited, layout in combinations:
                if completed(species, quick, recruited, layout):
                    continue
                forced = layout == 'forced'
                label = f'p{species}-q{quick}-r{recruited}-{layout}'
                folder = out / label; folder.mkdir(exist_ok=True)
                row = dict(partner=species, quick=quick, recruited=recruited, layout=layout,
                           restore_cache_guard=True)
                result['cases'].append(row)
                e.run('load', str(out / 'partner.state')); e.run('lua', 'PCSX.resumeEmulator()')
                e.poke('MOD_OPT_QUICK_BATTLE', struct.pack('<i', quick))
                addr = 'SPECIES_RECRUITED_BITS+43'  # 351 / 8, bit 7
                old = e.peek(addr, 'B')
                e.poke(addr, bytes([(old & 0x7f) | (recruited << 7)]))
                assert e.warp(45), 'ambush map did not load'
                if forced:
                    # MapDigimonEntity is 196 bytes; the fourth entry remains
                    # in the map data even when its conditional spawn is false.
                    assert e.peek('MAP_DIGIMON_TABLE+588', 'h') == 351
                    e.set_backend('interpreter')
                    call(e, 'scriptLoadModel', [351])
                    call(e, 'scriptSetDigimon', [351, 3, 0])
                    e.set_backend(a.cpu)
                (folder / 'before.json').unlink(missing_ok=True)
                row['loaded'] = snapshot(e)
                row['execution_flow'] = json.loads(e.api('/api/v1/execution-flow'))
                assert (351 in row['loaded']['npc_models']) == forced
                assert row['loaded']['MOD_OPT_QUICK_BATTLE'] == quick
                assert row['loaded']['kotemon_recruited'] == bool(recruited)
                assert sum(bool(p) for p in row['loaded']['entities'][2:]) == (4 if forced else 3)
                e.run('save', str(folder / 'before.state'))
                monitoring = start_gpu_monitor(e)
                try:
                    row.update(encounter(e, folder))
                except Exception as error:
                    row['error'] = str(error)
                    try:
                        row['failure'] = snapshot(e)
                        row['failure_execution_flow'] = json.loads(e.api('/api/v1/execution-flow'))
                        e.run('save', str(folder / 'failure.state'))
                        e.run('shot', str(folder / 'failure.png'))
                    except Exception as diagnostic_error:
                        row['diagnostic_error'] = str(diagnostic_error)
                        if not a.keep_going:
                            raise
                        # A native-core failure can terminate the emulator.
                        # Relaunch; the next case restores its partner checkpoint.
                        log = ROOT / f'build/emu-{e.port}.out'
                        if log.exists():
                            shutil.copyfile(log, folder / 'emulator-failure.log')
                        monitoring = False
                        e.stop()
                        e.env['EMU_ARGS'] = ('-interpreter -debugger' if a.cpu == 'interpreter' else '') + (' -8mb' if a.ram_mb == 8 else '')
                        e.run('start', e.disc, '--keep-cards')
                    if (folder / 'before.json').exists():
                        row['before'] = json.loads((folder / 'before.json').read_text())
                    if not a.keep_going:
                        raise
                finally:
                    if a.gameplay:
                        e.run('lua', 'if AMBUSH_RETURN and AMBUSH_RETURN.listener then AMBUSH_RETURN.listener:remove() end; AMBUSH_RETURN=nil')
                    if monitoring:
                        row['gpu_monitor'] = finish_gpu_monitor(e)
                for phase in ('loaded', 'before', 'battle', 'after', 'failure'):
                    if phase in row:
                        assert row[phase]['heap']['corrupt'] is None, f'{phase}: corrupt heap'
                if not row.get('returned') and 'diagnostic_error' not in row:
                    e.run('save', str(folder / 'failure.state'))
                    e.run('shot', str(folder / 'failure.png'))
                (out / 'result.json').write_text(json.dumps(result, indent=2) + '\n')
                print(label, 'PASS' if row.get('returned') else 'FAIL', flush=True)
    except BaseException as error:
        result['error'] = str(error)
        try:
            result['error_state'] = snapshot(e)
            result['execution_flow'] = json.loads(e.api('/api/v1/execution-flow'))
            e.run('save', str(out / 'error.state'))
        except Exception as diagnostic_error:
            result['diagnostic_error'] = str(diagnostic_error)
        e.run('shot', str(out / 'error.png'), check=False)
        raise
    finally:
        (out / 'result.json').write_text(json.dumps(result, indent=2) + '\n')
        e.stop()
    assert all(r.get('returned') for r in result['cases']), 'encounter failed; see result.json'


if __name__ == '__main__':
    main()
