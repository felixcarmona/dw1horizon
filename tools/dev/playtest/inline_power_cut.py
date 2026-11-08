#!/usr/bin/env python3
"""Kill a real save between its two writes, then cold-load the persisted card.

The existing card fault injector pauses at the second MemCardWriteFile call,
so copy 1 has completed MemCardSync but copy 0 has not started. SIGKILL prevents
emulator shutdown from adding further writes. Only a disposable card is used.
"""
import argparse
from concurrent.futures import ThreadPoolExecutor
import json
import os
from pathlib import Path
import shutil
import signal
import struct
import sys

ROOT=Path(__file__).resolve().parents[3]
sys.path[:0]=[str(ROOT),str(ROOT/'tools')]
from tools.dev.playtest.qol import ProofEmu
from tools.dev.playtest.chart_card_roundtrip import save,history
from tools.dev import memory_card as mcd
from tools.langpatch import elf_symbols


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('disc');p.add_argument('--exe',required=True)
    p.add_argument('--card',type=Path,required=True);p.add_argument('--out',type=Path,required=True)
    p.add_argument('--port',type=int,default=39727);a=p.parse_args()
    out=a.out.resolve();out.mkdir(parents=True,exist_ok=True)
    e=ProofEmu(a.disc,a.exe,a.port,str(out/'emu'));e.env['EMU_ARGS']='-interpreter -debugger'
    for n,(addr,_,_) in elf_symbols(a.exe+'.elf').items():e.table.setdefault(n,addr)
    result={}
    try:
        e.start(str(a.card.resolve()));assert e.continue_game()==0
        result['before']=history(e)
        bits=bytearray(e.raw('SPECIES_RAISED_BITS',128,e.ram()));bits[477//8]|=1<<(477%8)
        e.poke('SPECIES_RAISED_BITS',bits)
        injector=(ROOT/'tools/dev/saves/cut.lua').as_posix()
        e.run('lua',f"dofile('{injector}'); return CUT.arm({e.A('MemCardWriteFile')},2,0)")
        with ThreadPoolExecutor(max_workers=1) as pool:
            driver=pool.submit(save,e)
            for _ in range(240):
                if e.run('lua','return tostring(CUT.paused)').strip()=='true':break
                if driver.done():raise AssertionError(('save finished before cut',driver.result()))
                e.wait(.5)
            else:raise AssertionError('second write was never reached')
            result['writes']=e.run('lua','return CUT.report()')
            assert 'ofs 1100 size f00' in result['writes'] and 'ofs 0 size 1100' in result['writes']
            paused=Path(e.card_out()).read_bytes()
            state=json.loads((ROOT/f'build/emu-{a.port}.json').read_text())
            os.kill(state['pid'],signal.SIGKILL)
            e.wait(1);e.stop()
            assert Path(e.card_out()).read_bytes()==paused,'card changed after power cut'
            try:driver.result(timeout=45)
            except Exception as error:result['interrupted_driver']=type(error).__name__
        card=out/'power-cut.mcr';card.write_bytes(paused)
        data=mcd.Card(card).read('BASLUS-01032DMR0');decoded=mcd.decode_save(data)
        for k in range(2):assert decoded[f'ext{k}']['checksum_ok'] and decoded[f'ext{k}']['matches_v1']
        assert 477 not in decoded['ext0']['records']['speciesRaised']
        assert 477 in decoded['ext1']['records']['speciesRaised']
        result['old_copy_0_new_copy_1']=True
        e.start(str(card));assert e.continue_game()==0
        result['after']=history(e)
        for key in ('native','imported','recruited'):assert all(result['after'][key].values()),key
        assert e.warp(218)
        e.run('shot',str(out/'reloaded.png'));result['ok']=True
        print('PASS: real MemCardWriteFile interruption, SIGKILL, unchanged disk image, raw .mcr cold reload')
    finally:
        e.stop();(out/'result.json').write_text(json.dumps(result,indent=2)+'\n')


if __name__=='__main__':main()
