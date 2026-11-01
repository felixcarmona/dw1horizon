#!/usr/bin/env python3
"""Prove Cheats navigation and repeat farm purchases on an original-2-MB disc.

Boots the release corpus card; setup writes select the farm branch and inventory.
Farm sections start through a frame-boundary call; purchases and list navigation
use pad input, with balances and cursor read back.
Use --page-step 1 to document the pre-0287 left/right behavior.
"""
import argparse
import json
import os
from pathlib import Path
import shutil
import struct
import sys

ROOT = Path(__file__).resolve().parents[3]
sys.path[:0] = [str(ROOT), str(ROOT / 'tools')]
from tools.dev.saves.releases import Emu
from tools.dev import memory_card
from tools.langpatch import elf_symbols


class ProofEmu(Emu):
    def press(self, button, frames=10):
        # Count emulated refreshes instead of wall-clock time on a shared host.
        if button in ('CONFIRM', 'CANCEL'):
            japanese = self.peek('MOD_OPT_BUTTONS', 'i') != 0
            button = ('CIRCLE' if japanese else 'CROSS') if button == 'CONFIRM' else ('CROSS' if japanese else 'TRIANGLE')
        frames = max(frames, 8)
        self.run('lua', f'''
          QOL_PAD={{n=0,done=false}}
          local pad=PCSX.SIO0.slots[1].pads[1]
          local b=PCSX.CONSTS.PAD.BUTTON.{button}
          pad.setOverride(b)
          QOL_PAD.listener=PCSX.Events.createEventListener('GPU::Vsync',function()
            QOL_PAD.n=QOL_PAD.n+1
            if QOL_PAD.n=={frames} then pad.clearOverride(b) end
            if QOL_PAD.n=={frames + 4} then
              QOL_PAD.done=true; QOL_PAD.listener:remove()
            end
          end)
        ''')
        try:
            for _ in range(100):
                if self.run('lua', 'return QOL_PAD.done').strip() == 'true':
                    return
                self.wait(.1)
            raise AssertionError(f'{button}: no emulated refreshes')
        finally:
            self.api(f'/api/v1/lua/release?button={button}')
            self.run('lua', 'if not QOL_PAD.done then QOL_PAD.listener:remove() end; QOL_PAD.listener=nil')


def test_card(out):
    """Private corpus copy with English and US controls selected."""
    path = out / 'english.mcd'
    shutil.copyfile(ROOT / 'tools/dev/saves/corpus/20261027-d2796814.mcd', path)
    card = memory_card.Card(path)
    name = 'BASLUS-01032DMR0'
    data = card.read(name)
    size = 0x2000 if len(data) >= 0x6000 else 0x1000
    for k in range(2):
        offset = 0x2000 + k * size
        head = data[offset:offset + size]
        records = []
        for tag, value in memory_card.parse_records(head):
            if tag == 9:
                options = bytearray(value)
                for i in (0, 7):
                    options[i] = 0
                value = bytes(options)
            records.append((tag, value))
        card.write(name, offset, memory_card.build_extension(head, records, size))
    if data[0x50] == ord('O'):
        header = bytearray(data[0x54:0x60])
        for i in (0, 7):
            header[i] = 0
        card.write(name, 0x54, header)
    return str(path)


def talk(e):
    gl = e.A('gameLoop')
    script_id = e.peek('CURRENT_SCRIPT_ID', 'H')
    e.poke('TALKED_TO_ENTITY', bytes([8]))  # NPC slot 6, after tamer/partner.
    e.run('lua', f'''
      QOL_CALL={{phase=0}}
      QOL_CALL.bp=PCSX.addBreakpoint({gl}, 'Exec', 4, 'qol-farm', function()
        local r=PCSX.getRegisters()
        if QOL_CALL.phase==0 then
          QOL_CALL.ra=r.GPR.n.ra
          r.GPR.n.a0={script_id}; r.GPR.n.a1=11; r.GPR.n.a2=1
          r.GPR.n.ra={gl}; r.pc={e.A('callScriptSection')}; QOL_CALL.phase=1
        else
          r.GPR.n.ra=QOL_CALL.ra; QOL_CALL.phase=2; QOL_CALL.bp:remove()
        end
      end)
    ''')
    for _ in range(100):
        if e.run('lua', 'return QOL_CALL.phase').strip() == '2':
            return dict(script=script_id, section=11, event=1, entity=8)
        e.wait(.1)
    raise AssertionError('farm section call did not return')


def restore(e, out):
    e.run('load', str(out / 'boot.state'))
    e.run('lua', 'PCSX.resumeEmulator()')
    e.wait(1)


def wait_value(e, symbol, value, fmt='i'):
    for _ in range(80):
        if e.peek(symbol, fmt) == value:
            return
        e.wait(.25)
    raise AssertionError(f'{symbol} did not become {value}')


def press_value(e, button, symbol, value, fmt='i'):
    before = e.peek(symbol, fmt)
    for _ in range(8):
        e.press(button, 16)
        for _ in range(10):
            got = e.peek(symbol, fmt)
            if got == value:
                return
            assert got == before, (button, symbol, before, got, value)
            e.wait(.2)
    raise AssertionError(f'{button}: {symbol} stayed at {before}, expected {value}')


def navigation(e, out, step):
    e.poke('MOD_OPT_CHEATS', struct.pack('<i', 1))
    e.poke('MOD_OPT_BUTTONS', struct.pack('<i', 0))
    press_value(e, 'START', 'PAUSE_BOX_VISIBLE', 1, 'B')
    for _ in range(3):
        e.press('SELECT', 30)
        for _ in range(20):
            if e.peek('MOD_LAB_ACTIVE', 'i') == 1:
                break
            e.wait(.5)
        else:
            continue
        break
    wait_value(e, 'MOD_LAB_ACTIVE', 1)
    press_value(e, 'RIGHT', 'MOD_LAB_CURSOR', step)
    press_value(e, 'LEFT', 'MOD_LAB_CURSOR', 0)
    results = {'home': dict(rows=12, right=step, left=0)}
    for label, home_row, view in [('parameters', 2, 1), ('evolution', 3, 3), ('teleport', 4, 4)]:
        e.poke('MOD_LAB_CURSOR', struct.pack('<i', home_row))
        press_value(e, 'CONFIRM', 'MOD_LAB_VIEW', view)
        count = 20
        if view != 1:
            # List construction selects the current partner/map after filling
            # the choices. Wait for that final selection before resetting the
            # test cursor; the view changes before CD-backed construction ends.
            for _ in range(100):
                ram = e.ram()
                count = e.peek('labCount', 'i', ram)
                cursor = e.peek('MOD_LAB_CURSOR', 'i', ram)
                choices = e.peek('labChoices', 'I', ram) - 0x80000000
                target = e.peek('PARTNER_ENTITY', 'i', ram) if view == 3 else e.peek('CURRENT_SCREEN', 'h', ram)
                if (0 <= cursor < count and 0 <= choices < len(ram)
                        and struct.unpack_from('<H', ram, choices + cursor * 2)[0] == target):
                    break
                e.wait(.25)
            else:
                raise AssertionError(f'{label} list did not finish loading')
        e.poke('MOD_LAB_CURSOR', struct.pack('<i', 0))
        e.poke('labTop', struct.pack('<i', 0))
        trace = []
        for key, want in [('LEFT', 0), ('RIGHT', step), ('DOWN', step + 1),
                          ('UP', step), ('LEFT', 0), ('UP', 0)]:
            press_value(e, key, 'MOD_LAB_CURSOR', want)
            got = e.peek('MOD_LAB_CURSOR', 'i')
            trace.append([key, got]); assert got == want, (label, trace, want)
        e.poke('MOD_LAB_CURSOR', struct.pack('<i', 3))
        press_value(e, 'LEFT', 'MOD_LAB_CURSOR', max(0, 3 - step))
        assert e.peek('MOD_LAB_CURSOR', 'i') == max(0, 3 - step)
        e.poke('MOD_LAB_CURSOR', struct.pack('<i', 0))
        press_value(e, 'R1', 'MOD_LAB_CURSOR', 10)
        assert e.peek('MOD_LAB_CURSOR', 'i') == 10
        press_value(e, 'L1', 'MOD_LAB_CURSOR', 0)
        assert e.peek('MOD_LAB_CURSOR', 'i') == 0
        e.poke('MOD_LAB_CURSOR', struct.pack('<i', count - 2))
        press_value(e, 'RIGHT', 'MOD_LAB_CURSOR', count - 1)
        assert e.peek('MOD_LAB_CURSOR', 'i') == count - 1
        press_value(e, 'DOWN', 'MOD_LAB_CURSOR', count - 1)
        assert e.peek('MOD_LAB_CURSOR', 'i') == count - 1
        e.run('shot', str(out / f'{label}-last.png'))
        results[label] = dict(rows=count, trace=trace, upper_clamp=count - 1)
        press_value(e, 'CANCEL', 'MOD_LAB_VIEW', 0)
    # Numeric editing keeps its separate left/right amount and up/down step rules.
    e.poke('MOD_LAB_CURSOR', struct.pack('<i', 2))
    press_value(e, 'CONFIRM', 'MOD_LAB_VIEW', 1)
    press_value(e, 'CONFIRM', 'MOD_LAB_VIEW', 2)
    e.poke('MOD_LAB_VALUE', struct.pack('<i', 50))
    press_value(e, 'LEFT', 'MOD_LAB_VALUE', 49)
    assert e.peek('MOD_LAB_VALUE', 'i') == 49
    press_value(e, 'UP', 'labStep', 10)
    press_value(e, 'RIGHT', 'MOD_LAB_VALUE', 59)
    assert e.peek('MOD_LAB_VALUE', 'i') == 59
    results['number_editor'] = dict(start=50, after_left=49, after_up_right=59)
    return results


LIFETIME = 'PARTNER_PARA+74'  # game_state.py PARTNER_PARA_FIELDS


def old_age(e, out):
    """The editor stops at 1 hour; only the confirmed row ends the life, as a natural death."""
    e.poke('MOD_OPT_CHEATS', struct.pack('<i', 1))
    e.poke('MOD_OPT_BUTTONS', struct.pack('<i', 0))
    e.gs('set', 'partner.para.remainingLifetime=500')
    press_value(e, 'START', 'PAUSE_BOX_VISIBLE', 1, 'B')
    for _ in range(3):
        e.press('SELECT', 30)
        for _ in range(20):
            if e.peek('MOD_LAB_ACTIVE', 'i') == 1:
                break
            e.wait(.5)
        else:
            continue
        break
    wait_value(e, 'MOD_LAB_ACTIVE', 1)
    e.poke('MOD_LAB_CURSOR', struct.pack('<i', 2))
    press_value(e, 'CONFIRM', 'MOD_LAB_VIEW', 1)
    e.poke('MOD_LAB_CURSOR', struct.pack('<i', 7))
    press_value(e, 'CONFIRM', 'MOD_LAB_VIEW', 2)
    assert e.peek('MOD_LAB_VALUE', 'i') == 500
    for _ in range(3):
        e.press('UP', 8); e.wait(.3)
    press_value(e, 'LEFT', 'MOD_LAB_VALUE', 1)
    e.run('shot', str(out / 'lifetime-floor.png'))
    e.press('LEFT', 8); e.wait(.3)
    assert e.peek('MOD_LAB_VALUE', 'i') == 1
    press_value(e, 'CONFIRM', 'MOD_LAB_VIEW', 1)
    assert e.peek(LIFETIME, 'h') == 1
    e.poke(LIFETIME, struct.pack('<h', 500))
    press_value(e, 'CANCEL', 'MOD_LAB_VIEW', 0)
    e.poke('MOD_LAB_CURSOR', struct.pack('<i', 10))
    e.press('DOWN', 8); e.wait(.3); e.press('UP', 8); e.wait(.5)
    assert e.peek('MOD_LAB_CURSOR', 'i') == 10
    e.run('shot', str(out / 'old-age-row.png'))
    press_value(e, 'CONFIRM', 'MOD_LAB_VIEW', 5)
    e.wait(.5); e.run('shot', str(out / 'old-age-confirm.png'))
    press_value(e, 'CANCEL', 'MOD_LAB_VIEW', 0)
    assert e.peek('MOD_LAB_CURSOR', 'i') == 10 and e.peek(LIFETIME, 'h') == 500
    press_value(e, 'CONFIRM', 'MOD_LAB_VIEW', 5)
    press_value(e, 'CONFIRM', 'MOD_LAB_ACTIVE', 0)
    for _ in range(40):
        if e.peek('IS_NATURAL_DEATH', 'i') == 1:
            break
        e.wait(.5)
    assert e.peek('IS_NATURAL_DEATH', 'i') == 1, 'no natural death after the row'
    for n in range(8):
        e.wait(5); e.run('shot', str(out / f'old-age-{n}.png'))
        e.press('CONFIRM', 8)
    return dict(natural_death=True)


def state(e):
    ram = e.ram()
    return dict(bits=e.peek('MONEY', 'i', ram), paused=e.peek('IS_SCRIPT_PAUSED', 'i', ram),
                opcode=e.peek('ACTIVE_INSTRUCTION', 'B', ram),
                options=e.peek('DIALOGUE_SELECTION+8', 'H', ram),
                cursor=e.peek('DIALOGUE_SELECTION+10', 'H', ram),
                types=e.peek('INVENTORY', '30h', ram),
                amounts=e.peek('INVENTORY+60', '30B', ram))


def menu(e, refusal_shot):
    for _ in range(80):
        s = state(e)
        if s['paused'] == 1:
            return False
        if s['opcode'] == 0x10:
            e.wait(1)
            return True
        if s['opcode'] == 0x1A:
            e.wait(.4)
            e.run('shot', str(refusal_shot))
        e.press('CONFIRM', 8); e.wait(.2)
    raise AssertionError('no choice menu')


def select_option(e, target, count):
    current = e.peek('DIALOGUE_SELECTION+10', 'H')
    while current != target:
        down = (target - current) % count
        up = (current - target) % count
        button = 'DOWN' if down <= up else 'UP'
        current = (current + (1 if button == 'DOWN' else -1)) % count
        press_value(e, button, 'DIALOGUE_SELECTION+10', current, 'H')


def farm(e, out, seller, item, full=False, initial=2000):
    restore(e, out)
    e.gs('trigger', '225', str(int(seller == 'vegiemon')))
    e.gs('trigger', '246', '1')
    for n in (82, 186):
        e.gs('trigger', str(n), '1')
    e.gs('pstat', '31', '0')
    e.gs('set', 'hour=12', 'minute=0', 'gametime_running=0')
    assert e.warp(169 if seller == 'palmon' else 170)
    e.gs('pstat', '31', '0')
    types = list(range(1, 31)) if full else [-1] * 30
    inventory = struct.pack('<30h', *types) + bytes([99 if full else 0] * 30) + bytes(30) + bytes([30])
    e.poke('INVENTORY', inventory)
    e.poke('MONEY', struct.pack('<i', initial))
    entry = talk(e)
    trace = []; bought = 0
    refusal = out / f'{seller}-{item}-{"full" if full else initial}-dialogue.png'
    while menu(e, refusal):
        s = state(e)
        trace.append(dict(bits=s['bits'], options=s['options']))
        if (not full and initial == 2000 and s['bits'] == 500
                and (seller == 'palmon' or s['options'] == 3)):
            # Three purchases in the same section, then explicitly leave.
            e.run('shot', str(out / f'{seller}-{item}-three.png'))
            select_option(e, s['options'] - 1, s['options'])
            e.press('CONFIRM', 8); e.wait(.3)
            break
        if seller == 'vegiemon' and s['options'] == 3 and item == 42:
            select_option(e, 1, s['options'])
        e.press('CONFIRM', 8); e.wait(.3)
        bought += 1
        assert bought < 20, trace
    # Dismiss only dialogue after leave/refusal. No new conversation is started.
    for _ in range(60):
        s = state(e)
        if s['paused'] == 1:
            break
        e.press('CONFIRM', 8); e.wait(.2)
    else:
        raise AssertionError('farm did not return control')
    s = state(e)
    quantity = sum(n for t, n in zip(s['types'], s['amounts']) if t == item)
    want = 0 if full else 3
    assert quantity == want, (seller, item, quantity, trace)
    assert s['bits'] == initial - want * 500, (s, trace)
    if full:
        assert s['types'] == types and s['amounts'] == [99] * 30
    e.run('shot', str(out / f'{seller}-{item}-{"full" if full else initial}-done.png'))
    return dict(initial_bits=initial, final_bits=s['bits'], quantity=quantity,
                full_bag=full, menus=trace, returned_control=True, conversation_entry=entry)


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('disc'); p.add_argument('--exe', required=True)
    p.add_argument('--out', required=True)
    p.add_argument('--boot-state', help='control checkpoint from this exact disc')
    p.add_argument('--case', choices=('all', 'navigation', 'old-age', 'palmon', 'supercarrot', 'hawk-radish'), default='all')
    p.add_argument('--page-step', type=int, choices=(1, 10), default=10)
    p.add_argument('--port', type=int, default=int(os.environ.get('EMU_PORT', 39145)))
    a = p.parse_args(); out = Path(a.out).resolve(); out.mkdir(parents=True, exist_ok=True)
    e = ProofEmu(a.disc, a.exe, a.port, str(out / 'emu'))
    for name, (address, _, _) in elf_symbols(a.exe + '.elf').items():
        e.table.setdefault(name, address)
    if a.case != 'navigation':
        e.env['EMU_ARGS'] = '-interpreter -debugger'
    results = {}
    try:
        e.start(test_card(out))
        if a.boot_state:
            e.run('load', str(Path(a.boot_state).resolve()))
            e.run('lua', 'PCSX.resumeEmulator()')
        else:
            error = e.continue_game()
            assert error == 0, f'Continue failed: {error}'
        e.wait(5); assert e.in_control()
        results['ram_bytes'] = len(e.ram())
        e.gs('set', 'partner.para.age=1', 'partner.para.evoTimer=0',
             'partner.para.condition=0', 'partner.para.foodLevel=240',
             'partner.para.tiredness=0', 'gametime_running=0')
        e.poke('MOD_OPT_STORY', struct.pack('<i', 0))
        assert e.warp(218), 'Jijimon house did not load'
        e.wait(2); assert e.in_control()
        e.run('save', str(out / 'boot.state'))
        if a.case in ('all', 'navigation'):
            results['navigation'] = navigation(e, out, a.page_step)
            print('navigation', results['navigation'], flush=True)
            (out / 'result.json').write_text(json.dumps(results, indent=2) + '\n')
        if a.case == 'old-age':
            results['old_age'] = old_age(e, out)
            print('old-age', results['old_age'], flush=True)
            (out / 'result.json').write_text(json.dumps(results, indent=2) + '\n')
        for seller, item in [('palmon', 39), ('vegiemon', 41), ('vegiemon', 42)]:
            if a.case not in ('all', {39: 'palmon', 41: 'supercarrot', 42: 'hawk-radish'}[item]):
                continue
            for case, initial, full in [('three', 2000, False), ('out-of-bits', 1500, False), ('full-bag', 2000, True)]:
                key = f'{seller}-{item}-{case}'
                results[key] = farm(e, out, seller, item, full, initial)
                (out / 'result.json').write_text(json.dumps(results, indent=2) + '\n')
                print(key, results[key], flush=True)
    except BaseException as err:
        results['error'] = str(err)
        e.run('shot', str(out / 'failure.png'), check=False)
        e.run('save', str(out / 'failure.state'), check=False)
        raise
    finally:
        (out / 'result.json').write_text(json.dumps(results, indent=2) + '\n')
        e.stop()


if __name__ == '__main__':
    main()
