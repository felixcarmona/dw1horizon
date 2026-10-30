#!/usr/bin/env python3
"""Audit resident and sector-aligned cold animation reads for the tested engine."""
import argparse
import json
import re
from pathlib import Path
import motionlab as M
import coldsplit as C


def cold_reads(resident,buffer_bytes=0x2000):
    rows=[]
    for slot,entry in C.entries(resident).items():
        offset=(entry&0xffff)*4;length=((entry>>16)&0x7fff)*4
        read_bytes=((offset%2048+length+2047)//2048)*2048
        rows.append(dict(slot=slot,offset=offset,length=length,sector_read_bytes=read_bytes,
                         fits=length>0 and read_bytes<=buffer_bytes))
    return rows


def audit(data,nb,resident_limit=0x18800,cold_limit=0x2000):
    try:resident,cold=C.split(data,nb,buffer_bytes=cold_limit)
    except ValueError as error:
        return dict(resident_bytes=None,resident_limit=resident_limit,cold_bytes=None,
                    cold_buffer_bytes=cold_limit,cold_reads=[],fits=False,error=str(error))
    rows=cold_reads(resident,cold_limit)
    return dict(resident_bytes=len(resident),resident_limit=resident_limit,cold_bytes=len(cold),
                cold_buffer_bytes=cold_limit,cold_reads=rows,
                fits=len(resident)<=resident_limit and all(r['fits'] for r in rows))


def require(data,nb):
    report=audit(data,nb)
    if not report['fits']:
        failures=[f'slot{r["slot"]}: {r["sector_read_bytes"]}>{report["cold_buffer_bytes"]}' for r in report['cold_reads'] if not r['fits']]
        if report.get('error'):failures.append(report['error'])
        if report['resident_bytes'] is not None and report['resident_bytes']>report['resident_limit']:failures.append(f'resident buffer overflow ({report["resident_bytes"]}>{report["resident_limit"]})')
        raise ValueError('animation storage budget failed: '+', '.join(failures))
    return report


def linker_limits(text):
    result={}
    for symbol,key in [('PARTNER_MODEL_BUFFER','resident_limit'),('COLD_ANIM_BUFFER','cold_limit')]:
        match=re.search(r'\.bss\.'+symbol+r'\s*\n\s*0x[0-9a-fA-F]+\s+(0x[0-9a-fA-F]+)',text)
        if not match:raise ValueError(f'linker map does not declare {symbol} capacity')
        result[key]=int(match[1],16)
    return result


def audit_archive(path,resident_limit=0x18800,cold_limit=0x2000):
    import species
    data,_,records=species.read_archive(str(path));rows=[]
    for sid,record in enumerate(records):
        if sid<180 or not record['flags']&species.FLAG_PARTNER or record['modelName'] or not record['modelSize']:continue
        start=record['modelSector']*2048;resident=data[start:start+record['modelSize']]
        reads=cold_reads(resident,cold_limit)
        rows.append(dict(species=sid,resident_bytes=len(resident),cold_reads=reads,
                         fits=len(resident)<=resident_limit and all(r['fits'] for r in reads)))
    return dict(archive_sha256=M.digest(data),species=len(rows),resident_limit=resident_limit,
                cold_limit=cold_limit,fits=all(r['fits'] for r in rows),rows=rows)


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('model',type=Path);p.add_argument('species',type=int);p.add_argument('out',type=Path);a=p.parse_args()
    result=audit(a.model.read_bytes(),len(M.mmd.exe().skeleton[a.species]));result['input_sha256']=M.digest(a.model.read_bytes())
    a.out.parent.mkdir(parents=True,exist_ok=True);a.out.write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result),flush=True)
    raise SystemExit(0 if result['fits'] else 1)
