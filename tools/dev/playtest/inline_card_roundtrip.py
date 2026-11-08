#!/usr/bin/env python3
"""Prove one-block Horizon saves, raw-card reloads and interrupted overwrites.

Loads a real original one-block save, fills the card, saves marked native/imported
history and recruits, reloads both .mcd and .mcr, and boots power-cut snapshots.
"""
import argparse
import json
from pathlib import Path
import shutil
import struct
import sys

ROOT = Path(__file__).resolve().parents[3]
sys.path[:0] = [str(ROOT), str(ROOT/'tools')]
from tools.dev import memory_card as mcd
from tools.dev.playtest.qol import ProofEmu
from tools.dev.playtest.chart_card_roundtrip import history, save, chart
from tools.dev.playtest.save_policy import mark, filled
from tools.langpatch import elf_symbols
from tools.dev.saves.measure import profiles, packbits

NAME = 'BASLUS-01032DMR0'


def snapshot(old, new, target, frames):
    """Stop the actual writer's copy-1-first order after N raw card frames."""
    shutil.copyfile(old, target); card=mcd.Card(target); src=mcd.Card(new).read(NAME)
    sequence = list(range(0x1100,0x2000,128)) + list(range(0,0x1100,128))
    for offset in sequence[:frames]: card.write(NAME,offset,src[offset:offset+128])


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('disc');p.add_argument('--exe',required=True)
    p.add_argument('--legacy-card',required=True,type=Path);p.add_argument('--out',required=True,type=Path)
    p.add_argument('--two-block-card',type=Path,help='optional real two-block save from the previous writer')
    p.add_argument('--port',type=int,default=39719);a=p.parse_args()
    out=a.out.resolve();out.mkdir(parents=True,exist_ok=True)
    e=ProofEmu(a.disc,a.exe,a.port,str(out/'emu'));e.env['EMU_ARGS']='-interpreter -debugger'
    for name,(addr,_,_) in elf_symbols(a.exe+'.elf').items():e.table.setdefault(name,addr)
    result={}
    try:
        full=out/'full.mcd';filled(a.legacy_card,full,15)
        assert len(mcd.Card(full).find(NAME)['blocks'])==1
        e.start(str(full));assert e.continue_game()==0
        mark(e);assert e.warp(218)
        result['before']=history(e);assert save(e)==0;e.wait(2);e.stop()
        written=out/'written.mcd';shutil.copyfile(e.card_out(),written)
        result['directory']=mcd.Card(written).find(NAME)
        assert result['directory']['size']==8192 and len(result['directory']['blocks'])==1
        dec=mcd.decode_save(mcd.Card(written).read(NAME));result['decoded']=dec
        for k in range(2):
            assert dec[f'copy{k}']['version']==5
            assert dec[f'ext{k}']['checksum_ok'] and dec[f'ext{k}']['matches_v1']
        for suffix in ('mcd','mcr'):
            card=out/f'reload.{suffix}';shutil.copyfile(written,card)
            e.start(str(card));assert e.continue_game()==0
            loaded=history(e);result[suffix]=loaded
            for key in ('native','imported','recruited','bits','recruit_bits'):assert loaded[key]==result['before'][key],key
            e.run('shot',str(out/f'reload-{suffix}.png'))
            if suffix == 'mcr': chart(e,out,'restored')
            e.stop()
        # Save different progress; generate real raw cards at each part boundary.
        e.start(str(written));assert e.continue_game()==0
        bits=bytearray(e.raw('SPECIES_RAISED_BITS',128,e.ram()));bits[477//8]|=1<<(477%8)
        e.poke('SPECIES_RAISED_BITS',bits);assert save(e)==0;e.wait(2);e.stop()
        newer=out/'newer.mcd';shutil.copyfile(e.card_out(),newer)
        result['cuts']={}
        for cut in (1,29,30,31,63,64):
            card=out/f'cut-{cut}.mcr';snapshot(written,newer,card,cut)
            e.start(str(card));assert e.continue_game()==0
            loaded=history(e)
            for key in ('native','imported','recruited'):assert all(loaded[key].values()),(cut,key)
            result['cuts'][str(cut)]=loaded;e.stop()
        # A legacy two-block save still loads, migrates and retains its chain.
        e.start(str(a.two_block_card.resolve() if a.two_block_card else ROOT/'tools/dev/saves/corpus/20261027-d2796814.mcd'))
        assert e.continue_game()==0;mark(e);assert e.warp(218)
        assert save(e)==0;e.wait(2);e.stop()
        migrated=out/'migrated.mcr';shutil.copyfile(e.card_out(),migrated)
        assert len(mcd.Card(migrated).find(NAME)['blocks'])==2
        e.start(str(migrated));assert e.continue_game()==0
        loaded=history(e)
        for key in ('native','imported','recruited'):assert all(loaded[key].values())
        result['migrated']=loaded;e.stop()
        # Mimic an emulator retaining only the first block of a two-block chain.
        mcd.Card(migrated).write(NAME,0x2000,bytes(0x2000))
        e.start(str(migrated));assert e.continue_game()==0
        loaded=history(e)
        for key in ('native','imported','recruited'):assert all(loaded[key].values())
        result['only_first_block']=loaded;e.stop()
        # Earlier writers could leave ordinary v1 checksums with missing v4
        # extensions. Construct that historical failure explicitly, without
        # claiming the unavailable reported card had these bytes.
        historic=out/'historic-payload-only.mcr';shutil.copyfile(written,historic)
        card=mcd.Card(historic);data=card.read(NAME)
        for k in range(2):
            base=0x200+k*0xF00;p=bytearray(data[base:base+0xF00]);p[0x4E8]=4
            for i in range(40):p[0x524+i*64:0x540+i*64]=bytes(28)
            struct.pack_into('<I',p,0x4FC,mcd.v1_checksum(p));card.write(NAME,base,p)
        e.start(str(historic));assert e.continue_game()==0
        lost=history(e);result['historic_loss']=lost
        assert all(lost['native'].values()) and not any(lost['imported'].values()) and not any(lost['recruited'].values())
        e.run('shot',str(out/'historic-loss.png'));e.stop()
        # Measure records actually emitted by the game for controlled progress
        # profiles. Every profile uses an actual card-menu save, not a Python writer.
        e.start(str(written));assert e.continue_game()==0
        result['profiles']=[]
        for label,raw in profiles():
            records=dict(mcd.parse_records(bytes(12)+raw+bytes(4)))
            for tag,symbol in [(7,'SPECIES_RAISED_BITS'),(8,'SPECIES_RECRUITED_BITS'),(12,'MOD_GROUND_PICKED')]:
                e.poke(symbol,records[tag])
            assert save(e)==0;e.wait(2)
            target=out/f'profile-{label}.mcr';shutil.copyfile(e.card_out(),target)
            ext=mcd.extension(mcd.Card(target).read(NAME));records=mcd.parse_records(ext)
            body=b''.join(struct.pack('<HH',tag,len(value))+value for tag,value in records)+bytes(4)
            result['profiles'].append(dict(profile=label,records_raw=len(body),framed_raw=len(body)+16,packbits=len(packbits(body))))
        e.stop()
        spare=out/'one-free.mcr';filled(a.legacy_card,spare,14)
        e.start(str(spare));e.to_title();e.run('pause')
        for symbol,value in [('CURRENT_MENU',0x10),('TARGET_MENU',0x10),('MAIN_MENU_TICKS',3),
                             ('MEMORY_CARD_ID',0),('MEMORY_CARD_SLOT',1)]:
            e.poke(symbol,struct.pack('<i',value))
        e.run('resume');e.wait(5);e.stop()
        created=mcd.Card(e.card_out());newname='BASLUS-01032DMR1'
        result['created']=created.find(newname)
        assert result['created']['size']==8192 and len(result['created']['blocks'])==1
        dec=mcd.decode_save(created.read(newname))
        assert dec['copy0']['version']==5 and dec['ext0']['checksum_ok'] and dec['ext1']['matches_v1']
        result['ok']=True
        print('PASS: full one-block card, .mcd/.mcr reload, six power cuts, legacy two-block migration')
    finally:
        e.stop();(out/'result.json').write_text(json.dumps(result,indent=2)+'\n')


if __name__=='__main__':main()
