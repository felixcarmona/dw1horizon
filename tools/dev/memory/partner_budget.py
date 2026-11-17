#!/usr/bin/env python3
"""Measure complete partner MMDs, slot aliases and whole-sector CD reads.

--native-dir adds partners loaded from separate files; --replacement ID=PATH
supplies final replacement files without modifying the source disc tree.
"""
import argparse
import json
from pathlib import Path
import struct
import sys

ROOT = Path(__file__).resolve().parents[3]
sys.path[:0] = [str(ROOT), str(ROOT/'tools')]
import species
import coldsplit
import motionstorage


def model_row(sid, name, raw, limit):
    n=len(raw)
    mesh,table=struct.unpack_from('<II',raw)
    groups={}
    for slot in range(coldsplit.table_length(raw)):
        entry=struct.unpack_from('<I',raw,table+slot*4)[0]
        if entry and not entry&coldsplit.FLAG:
            groups.setdefault(entry,[]).append(slot)
    offsets=sorted(groups)
    streams=[dict(slots=groups[o],offset=table+o,
                  bytes=(offsets[i+1] if i+1<len(offsets) else n-table)-o)
             for i,o in enumerate(offsets)]
    read=(n+2047)//2048*2048
    cold=motionstorage.cold_reads(raw)
    return dict(species=sid,name=name,resident=n,cd_read=read,
                payload_margin=limit-n,read_margin=limit-read,
                header_bytes=mesh,mesh_bytes=table-mesh,
                animation_table_bytes=4*coldsplit.table_length(raw),
                resident_streams=streams,cold_reads=cold,
                fits=read<=limit and all(x['fits'] for x in cold))


def audit(archive, limit=0x18800, native_dir=None, replacements=None):
    data,_,records=species.read_archive(str(archive))
    partners,_,_=species.read_index(data)
    rows=[]
    for sid in partners:
        r=records[sid]
        if not r['modelSize'] or r['modelName']:continue
        raw=data[r['modelSector']*2048:][:r['modelSize']]
        rows.append(model_row(sid,r['para']['name'],raw,limit))
    archive_models=len(rows)
    if native_dir:
        carried=species.record_originals(data)
        for sid,s in species.load_content().items():
            if sid>=180 or sid in carried or 'partner' not in s:continue
            m=s['model']
            filename=Path(m['partner_file']).name if m.get('partner_file') else m['name']+'.MMD'
            paths=list(Path(native_dir).rglob(filename))
            if len(paths)!=1:raise ValueError(f'{sid}: expected one {filename}, found {paths}')
            path=(replacements or {}).get(sid,paths[0])
            rows.append(model_row(sid,s['name'],Path(path).read_bytes(),limit))
    rows.sort(key=lambda r:r['resident'],reverse=True)
    return dict(archive=str(archive),buffer=limit,archive_models=archive_models,
                measured_models=len(rows),fits=all(r['fits'] for r in rows),rows=rows)


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('archive',type=Path);p.add_argument('out',type=Path)
    p.add_argument('--native-dir',type=Path)
    p.add_argument('--replacement',action='append',default=[])
    a=p.parse_args()
    replacements={int(s.split('=',1)[0]):Path(s.split('=',1)[1]) for s in a.replacement}
    r=audit(a.archive,native_dir=a.native_dir,replacements=replacements)
    a.out.parent.mkdir(parents=True,exist_ok=True)
    a.out.write_text(json.dumps(r,indent=2)+'\n')
    print(json.dumps(dict(fits=r['fits'],measured_models=r['measured_models'],archive_models=r['archive_models'],
                         peak={k:v for k,v in r['rows'][0].items() if k not in ('resident_streams','cold_reads')})))
    raise SystemExit(0 if r['fits'] else 1)
