#!/usr/bin/env python3
"""Capture real evolution popups in EN/ES, both fonts, on original 2 MB RAM.

Fixture evolution loads GrapLeomon's real model. Subsequent care/timer writes
isolate three popup states; they do not prove natural evolution or survival.
"""
import argparse
import json
from pathlib import Path
import struct
import sys

ROOT = Path(__file__).resolve().parents[3]
sys.path[:0] = [str(ROOT), str(ROOT / 'tools')]
from tools.dev.playtest.qol import ProofEmu, test_card, press_value
from tools.dev.playtest.training_evolution import call, await_value
from tools.langpatch import elf_symbols


def open_chart(e, parent=306, target=258):
    e.poke('SPECIES_RAISED_BITS', b'\xff' * 128)
    call(e, 'tamerSetState', 1)
    e.poke('IS_IN_MENU', struct.pack('<i', 1))
    call(e, 'addGameMenu'); e.run('resume')
    await_value(e, 'TRIANGLE_MENU_STATE', 'i', lambda n: n == -1)
    call(e, 'handleGameMenuSelection', 3); e.run('resume')
    await_value(e, 'MENU_STATE', 'b', lambda n: n == 1)
    press_value(e, 'RIGHT', 'PLAYER_MENU_STATE', 1, 'b')
    press_value(e, 'CONFIRM', 'MENU_STATE', 2, 'b')
    press_value(e, 'CONFIRM', 'MENU_STATE', 3, 'b')
    call(e, 'chartDetailGoto', parent); e.run('resume'); e.wait(1)
    ids = e.peek('CHART_TO_IDS', '24h')
    index = ids.index(target)
    call(e, 'chartDetailMoveCursor', 1, index); e.run('resume')
    e.poke('MOD_OPT_EVO_GUIDE', struct.pack('<i', 1))
    for _ in range(8):
        e.press('SQUARE', 8)
        if e.peek('CHART_POPUP', 'b'):
            break
    assert e.peek('CHART_POPUP', 'b') == 1


def check(e, out, language):
    assert e.continue_game() == 0
    assert e.in_control()
    assert e.peek('MOD_OPT_NEW_DIGIMON', 'i') == 1
    e.poke('PAUSE_STATE', b'\0')
    print(f'{language}: save loaded with field control', flush=True)
    assert call(e, 'modNewGame', 3) == 408
    assert call(e, 'modNewGame', 6) == 408
    e.run('resume')
    e.gs('set', 'gametime_running=0')
    e.run('pause')
    for name, fmt, value in [('EVOLUTION_TARGET','h',306), ('HAS_USED_EVOITEM','B',1),
                             ('TAMER_STATE','B',6), ('TAMER_SUB_STATE','B',0),
                             ('PARTNER_STATE','B',13), ('PARTNER_SUB_STATE','B',0)]:
        e.poke(name, struct.pack('<'+fmt,value))
    e.run('resume')
    await_value(e, 'PARTNER_ENTITY', 'i', lambda n:n==306)
    await_value(e, 'PARTNER_STATE', 'b', lambda n:n==1)
    e.poke('PAUSE_STATE', b'\0')
    print(f'{language}: GrapLeomon model loaded', flush=True)
    e.gs('set', 'gametime_running=0', 'partner.para.evoTimer=83',
         'partner.para.remainingLifetime=500', 'partner.para.careMistakes=0',
         'partner.para.weight=10', 'partner.para.happiness=100',
         'partner.stats.hp=9999', 'partner.stats.mp=9999',
         'partner.stats.off=999', 'partner.stats.def=999',
         'partner.stats.speed=999', 'partner.stats.brain=999')
    # Explicitly select the shipped Japanese pad convention: Circle confirms.
    e.poke('MOD_OPT_BUTTONS', struct.pack('<i', 1))
    open_chart(e)
    print(f'{language}: requirements popup opened', flush=True)
    assert call(e, 'chartTargetHours', 258) == 120
    e.run('resume')
    results=[]
    for font, number in [('new-font',0), ('original-font',1)]:
        call(e, 'modSetFont', number); e.run('resume')
        for label, timer, life, color, warning in [
            ('in-37-hours',83,500,6,False),
            ('life-runs-out-first-12-hours',83,12,6,True),
            ('ready',120,500,7,False)]:
            e.run('pause')
            e.gs('set',f'partner.para.evoTimer={timer}',f'partner.para.remainingLifetime={life}')
            e.poke('CHART_CARD_ID',struct.pack('<h',-1))
            e.run('resume');e.wait(1)
            assert e.peek('CHART_CARD_VERDICT_COLOR','b') == color
            assert bool(e.peek('CHART_LIFE','h')) == warning
            assert e.peek('CHART_CARD_MINE','b') == 1
            assert e.peek('CHART_CARD_ID','h') == 258
            assert e.peek('CHART_PACK_V','h') + 12 <= 204, 'text cells overlap the title row'
            path=out/f'{language}-{font}-{label}.png'
            e.run('shot',str(path))
            results.append(dict(font=font,state=label,timer=timer,remaining_life=life,
                                verdict_color=color,warning=warning,shot=str(path)))
    assert len(e.ram())==2*1024*1024
    assert not json.loads(e.api('/api/v1/execution-flow'))['8mb']
    return results


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('disc');p.add_argument('--exe',required=True)
    p.add_argument('--out',required=True);p.add_argument('--port',type=int,default=39341)
    p.add_argument('--language',choices=('en','es','all'),default='all')
    a=p.parse_args();out=Path(a.out).resolve();out.mkdir(parents=True,exist_ok=True)
    results={}
    for language, index in [('en',0),('es',1)]:
        if a.language not in ('all',language):continue
        work=out/language;work.mkdir(exist_ok=True)
        e=ProofEmu(a.disc,a.exe,a.port,str(work/'emu'))
        e.env['EMU_ARGS']='-interpreter -debugger'
        for name,(address,_,_) in elf_symbols(a.exe+'.elf').items():e.table.setdefault(name,address)
        try:
            e.start(test_card(work,index))
            results[language]=check(e,out,language)
            print(f'ok: {language}, both fonts, all three popup states',flush=True)
        finally:e.stop()
        (out/'results.json').write_text(json.dumps(results,indent=2)+'\n')


if __name__=='__main__':main()
