#!/usr/bin/env python3
"""Checks the cup registration of species in the running emulator (EMU_PORT) against the rule of docs/reference/engine-patches.md.

The game must be in the Arena Lobby (screen 208) with control and the DGET overlay loaded by hand first:
  tools/dev/playtest/call_function.py 'loadDynamicLibrary(12,0,0,0,0)'
  EMU_PORT=38068 tools/dev/playtest/cupcheck.py 3 326 183 210 250     (types; each is poked into the partner)
For every cup it calls tournamentCheckEligible and tournamentCheckFair and compares them with the cup lists of
the arena script (DG.SCN entry 213, section 10): an original is in the list or not; a species is in a list that
holds nine originals of its level (a Mega counts as 5) or the original it borrows its techniques from.
"""

from pathlib import Path as _DevPath
import sys as _dev_sys
_DEV_ROOT = str(next(p for p in _DevPath(__file__).resolve().parents if (p / "tools").is_dir()))
_dev_sys.path.insert(0, _DEV_ROOT)
_dev_sys.path.insert(0, str(_DevPath(_DEV_ROOT) / "tools"))
import glob, json, os, struct, subprocess, sys
ROOT = _DEV_ROOT
sys.path.insert(0, os.path.join(ROOT, 'tools'))
from dws import bytecode as bytecode; import species
O=species.originals()
lev={t:O.rec[t]['para']['level'] for t in range(180)}
new={}
for t, d in species.imports().items():
    new[t]=dict(species.species_record(d), originalType=d['effects_like'])
d=open(os.path.join(ROOT, 'extracted/SCN/DG.SCN'),'rb').read()
offs=bytecode.container_entries(d); e=d[offs[213]:offs[214]]
sec=4182
def lst(off):
    o=off+2; r=[]
    while e[o]<0xFE: r.append(e[o]); o+=1
    return r
cups=[]
for c in range(23):
    co=struct.unpack_from('<H',e,sec+c*4+2)[0]
    tab=[struct.unpack_from('<H',e,co+k*4+2)[0] for k in range(5)]
    cups.append((lst(tab[2]),lst(tab[3])))
def expect(t):
    if t<180:
        return [int(t in cups[c][1]) for c in range(23)],[int(t in cups[c][0]) for c in range(23)]
    # new species: level / base
    level=min(new[t]['para']['level'],5); base=new[t]['originalType'] if 'originalType' in new[t] else new[t].get('base')
    el=[];fa=[]
    for c in range(23):
        for out,l in ((el,cups[c][1]),(fa,cups[c][0])):
            n=len(l)
            out.append(int(sum(1 for x in l if lev[x]==level)>=9 or base in l))
    return el,fa
test=[int(x) for x in sys.argv[1:]]
for t in test:
    subprocess.run(['python3','tools/dev/memory_inspector.py','set',f'PARTNER_ENTITY.digimonEntity.entity.type={t}'],cwd=ROOT,capture_output=True)
    calls=[f'tournamentCheckEligible({c})' for c in range(23)]+[f'tournamentCheckFair({c})' for c in range(23)]
    out=subprocess.run(['python3','tools/dev/playtest/call_function.py']+calls,cwd=ROOT,capture_output=True,text=True).stdout.strip().split('\n')
    got=[int(l.rsplit('= ',1)[1]) for l in out]
    el,fa=expect(t)
    print(t, new[t]['name'] if t in new else O.rec[t]['para']['name'], 'level', (new[t]['para']['level'] if t in new else lev[t]))
    print(' elig got ',''.join(map(str,got[:23])),'\n elig want',''.join(map(str,el)),'OK' if got[:23]==el else 'MISMATCH')
    print(' fair got ',''.join(map(str,got[23:])),'\n fair want',''.join(map(str,fa)),'OK' if got[23:]==fa else 'MISMATCH')
