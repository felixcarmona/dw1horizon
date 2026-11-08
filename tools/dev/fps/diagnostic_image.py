#!/usr/bin/env python3
"""Replace compiled Horizon programs in a pinned disc without relocating assets.

All original sector allocations are retained; a program that outgrows
its allocation is refused. Directory sizes follow any growth inside that allocation. Chinese font/name/resource areas remain from the
player's baseline; only its runtime module, language writes and header change.
"""
from pathlib import Path
import argparse,hashlib,json,re,shutil,struct,sys
ROOT=Path(__file__).resolve().parents[3];sys.path.insert(0,str(ROOT))
from tools import isowriter as iw
from tools import chinese_resources as zh


def build(baseline, code, output, reference_image=None, reference_build=None):
    img=iw.Image(str(baseline));plan=json.loads((code/'derived/plan.json').read_text())
    byname={p.rsplit('/',1)[-1]:p for p in img.files}
    replacements={byname[p.name]:p.read_bytes() for p in (code/'exe-en').iterdir()
                  if p.name in byname and (p.name=='SLUS_010.32' or p.name.endswith('_REL.BIN'))}
    for spec in plan['LANG_OVL']:
        _,_,name=spec.split(':');replacements[byname[name]]=(code/'lang'/name).read_bytes()
    for name in ('LANGEN.BIN','LANGES.BIN','LANGPT.BIN','LANGFR.BIN','LANGDE.BIN','LANGIT.BIN','LANGJA.BIN','LANGCA.BIN'):
        replacements[byname[name]]=(code/'lang'/name).read_bytes()
    # Source-specific resources and all glyph pixels must remain byte-identical.
    name=byname['LANGZH.BIN'];old=img.read(name);new=(code/'lang/LANGZH.BIN').read_bytes();data=bytearray(old)
    assert old[:4]==new[:4]==b'DWCZ'
    for lo,hi in ((zh.MODULE_OFFSET,zh.FONT_OFFSET),(zh.PATCH_OFFSET,zh.UI_OFFSET)):
        data[lo:hi]=new[lo:hi]
    code_sources={'lang/'+spec.split(':')[1] for spec in plan['CHINESE_OVL']}
    originals={('lang/'+target):original for original,target in (spec.split(':') for spec in plan['CHINESE_OVL'])}
    oldroutes={}
    if reference_image:
        from regional_program import preserve
        ref=iw.Image(str(reference_image));refdata=ref.read(name);ref.f.close()
        for i in range(struct.unpack_from('<I',refdata,20)[0]):
            h,f,sector,length=zh.ENTRY.unpack_from(refdata,zh.DIRECTORY_OFFSET+i*zh.ENTRY.size)
            oldroutes[h,f&1]=refdata[sector*2048:sector*2048+length]
        oldmodule=struct.unpack_from('<I',old,12)[0];refmodule=struct.unpack_from('<I',refdata,12)[0];newmodule=struct.unpack_from('<I',new,12)[0]
        kept,_=preserve(refdata[zh.MODULE_OFFSET:zh.MODULE_OFFSET+refmodule],old[zh.MODULE_OFFSET:zh.MODULE_OFFSET+oldmodule],new[zh.MODULE_OFFSET:zh.MODULE_OFFSET+newmodule],reference_build/'exe-zh-hans/SLUS_010.32.elf',code/'exe-zh-hans/SLUS_010.32.elf','ZH')
        data[zh.MODULE_OFFSET:zh.MODULE_OFFSET+newmodule]=kept
    routes={(zh.key(row['name']),row.get('story',0)):row for row in plan['CHINESE_RESOURCES'] if row['source'] in code_sources}
    for i in range(struct.unpack_from('<I',old,20)[0]):
        at=zh.DIRECTORY_OFFSET+i*zh.ENTRY.size;hashed,flags,sector,length=zh.ENTRY.unpack_from(old,at)
        row=routes.get((hashed,flags&1))
        if row:
            program=(code/row['source']).read_bytes()
            if reference_image:
                overlay=originals[row['source']].split('_REL.BIN')[0]
                program,_=preserve(oldroutes[hashed,flags&1],old[sector*2048:sector*2048+length],program,reference_build/'exe-zh-hans/SLUS_010.32.elf',code/'exe-zh-hans/SLUS_010.32.elf',overlay)
            if len(program)>length:raise ValueError('Chinese program outgrew resource: '+row['name'])
            data[sector*2048:sector*2048+length]=program.ljust(length,b'\0')
    for offset in (12,24):data[offset:offset+4]=new[offset:offset+4]
    struct.pack_into('<I',data,28,zh.fnv(data[32:zh.PREFIX_SIZE]))
    zh.validate(data);replacements[name]=bytes(data)
    grown={}
    if reference_image:
        from regional_program import preserve
        reference=iw.Image(str(reference_image))
        descriptions={original:('en',original) for original in byname if original.endswith('_REL.BIN')}
        for spec in plan['LANG_OVL']:
            lang,original,name=spec.split(':');descriptions[name]=(lang,original)
        for path,program in list(replacements.items()):
            name=path.rsplit('/',1)[-1]
            if name=='SLUS_010.32':lang,overlay='en',None
            elif name in descriptions:
                lang,original=descriptions[name];overlay=original.split('_REL.BIN')[0]
            else:continue
            oldelf=reference_build/f'exe-{lang}/SLUS_010.32.elf';newelf=code/f'exe-{lang}/SLUS_010.32.elf'
            replacements[path],_=preserve(reference.read(path),img.read(path),program,oldelf,newelf,overlay)
        reference.f.close()
    for name,data in replacements.items():
        size=img.files[name][1]
        if len(data)>iw.blocks(size)*2048:raise ValueError(f'{name}: {len(data)} exceeds retained allocation {iw.blocks(size)*2048}')
        if len(data)>size:grown[name]=len(data)
        replacements[name]=data+bytes(max(0,size-len(data)))
    name=byname['SLUS_010.32'];exe=bytearray(replacements[name]);maptext=(code/'exe-en/SLUS_010.32.elf.map').read_text()
    offset=int(re.search(r'0x([0-9a-f]+)\s+FILE_OFFSET_TABLE\s*$',maptext,re.M)[1],16)-0x80090000
    where={p.rsplit('/',1)[-1]:(l,n) for p,(l,n,_) in img.files.items()};where.update({name.rsplit('/',1)[-1]:(img.files[name][0],size) for name,size in grown.items()});where['PSX.EXE']=where['SLUS_010.32']
    iw.rewrite_file_table(exe,offset,where);replacements[name]=bytes(exe)
    shutil.copyfile(baseline,output);report=[]
    with open(output,'r+b') as out:
        for name,data in replacements.items():
            original=img.read(name)
            if data==original:continue
            lba,size,mixed=img.files[name];assert not mixed
            changed=sum(a!=b for a,b in zip(data,original))+max(0,len(data)-len(original));sectors=0
            for k in range(iw.blocks(size)):
                raw=img.raw(lba+k);payload=data[k*2048:(k+1)*2048].ljust(2048,b'\0')
                if raw[24:2072]==payload:continue
                out.seek((lba+k)*2352);out.write(iw.form1(lba+k,raw[16:24],payload));sectors+=1
            report.append(dict(file=name,bytes=len(data),changed_bytes=changed,changed_sectors=sectors,lba=lba))
        for directory,(start,length) in img.dirs.items():
            for k in range(iw.blocks(length)):
                raw=img.raw(start+k);data=bytearray(raw[24:2072]);at=0;changed=False
                while at<2048 and data[at]:
                    name=bytes(data[at+33:at+33+data[at+32]])
                    if name not in (b'\0',b'\1'):
                        full=directory+name.decode('ascii').split(';')[0]
                        if full in grown:
                            struct.pack_into('<I',data,at+10,grown[full]);struct.pack_into('>I',data,at+14,grown[full]);changed=True
                    at+=data[at]
                if changed:
                    out.seek((start+k)*2352);out.write(iw.form1(start+k,raw[16:24],data))
                    report.append(dict(file='@directory/'+directory,bytes=2048,changed_bytes=sum(a!=b for a,b in zip(data,raw[24:2072])),changed_sectors=1,lba=start+k))
    img.f.close()
    return report


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('baseline',type=Path);p.add_argument('code',type=Path);p.add_argument('output',type=Path);p.add_argument('--reference-image',type=Path);p.add_argument('--reference-build',type=Path)
    a=p.parse_args();report=build(a.baseline,a.code,a.output,a.reference_image,a.reference_build)
    a.output.with_suffix('.changes.json').write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps(dict(files=len(report),changed_bytes=sum(x['changed_bytes'] for x in report))))
if __name__=='__main__':main()
