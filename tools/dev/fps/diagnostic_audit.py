#!/usr/bin/env python3
"""Verify a diagnostic disc changes only program sectors and layout lengths.

Also inspect BPS TargetRead operations: inherited glyph data must come from the
player's input via SourceRead/SourceCopy, never literal patch bytes.
"""
from pathlib import Path
import argparse,bisect,json,mmap,struct,sys
ROOT=Path(__file__).resolve().parents[3];sys.path.insert(0,str(ROOT))
from tools.isowriter import Image


def audit(base,target,patch,changes,protection,plan):
    old=Image(str(base));new=Image(str(target));rows=json.loads(changes.read_text());fonts=json.loads(protection.read_text())['font_objects'];p=json.loads(plan.read_text())
    programs={'SLUS_010.32',*[x.rsplit('/',1)[-1] for x in old.files if x.endswith('_REL.BIN')]}
    programs|={s.split(':')[2] for s in p['LANG_OVL']}
    programs|={'LANG'+code+'.BIN' for code in ('EN','ES','PT','FR','DE','IT','JA','CA','ZH')}
    assert old.files.keys()==new.files.keys()
    growth=[]
    for name,(lba,size,kind) in old.files.items():
        nl,ns,nk=new.files[name];assert (lba,kind)==(nl,nk)
        if ns!=size:
            assert name.rsplit('/',1)[-1].startswith('LANG') and ns-size==32
            growth.append(dict(file=name,old=size,new=ns))
    bounds=[]
    for row in rows:
        name=row['file']
        if name.startswith('@directory/'):
            bounds.append((row['lba']*2352,(row['lba']+1)*2352))
        else:
            assert name.rsplit('/',1)[-1] in programs,name
            bounds.append((row['lba']*2352,(row['lba']+(row['bytes']+2047)//2048)*2352))
    bounds.sort();starts=[a for a,b in bounds];changed=0
    with open(base,'rb') as f,open(target,'rb') as g:
        a=mmap.mmap(f.fileno(),0,access=mmap.ACCESS_READ);b=mmap.mmap(g.fileno(),0,access=mmap.ACCESS_READ);assert len(a)==len(b)
        stride=2352*2048
        for begin in range(0,len(a),stride):
            if a[begin:begin+stride]==b[begin:begin+stride]:continue
            for at in range(begin,min(begin+stride,len(a)),2352):
                if a[at:at+2352]==b[at:at+2352]:continue
                i=bisect.bisect_right(starts,at)-1
                assert i>=0 and at+2352<=bounds[i][1],f'changed asset/structural sector {at//2352}'
                changed+=1
        a.close();b.close()
    # LANGZH is a container: its embedded assets require a byte-level check.
    from tools import chinese_resources as zh
    chinese=next(name for name in old.files if name.endswith('/LANGZH.BIN'))
    za,zb=old.read(chinese),new.read(chinese);assert len(za)==len(zb)
    zh.validate(za);zh.validate(zb)
    code_sources={'lang/'+spec.split(':')[1] for spec in p['CHINESE_OVL']}
    routes={(zh.key(row['name']),row.get('story',0)) for row in p['CHINESE_RESOURCES'] if row['source'] in code_sources}
    allowed=[(12,16),(24,32),(zh.MODULE_OFFSET,zh.FONT_OFFSET),(zh.PATCH_OFFSET,zh.UI_OFFSET)]
    for i in range(struct.unpack_from('<I',za,20)[0]):
        hashed,flags,sector,length=zh.ENTRY.unpack_from(za,zh.DIRECTORY_OFFSET+i*zh.ENTRY.size)
        if (hashed,flags&1) in routes:allowed.append((sector*2048,sector*2048+length))
    last=0
    for lo,hi in sorted(allowed):
        assert za[last:lo]==zb[last:lo],'changed Chinese font/name/texture/story asset'
        last=max(last,hi)
    assert za[last:]==zb[last:],'changed Chinese trailing asset'
    raw=patch.read_bytes();assert raw[:4]==b'BPS1';at=4
    def vl():
        nonlocal at
        n=0;shift=1
        while True:
            c=raw[at];at+=1;n+=(c&127)*shift
            if c&128:return n
            shift*=128;n+=shift
    source_size,target_size=vl(),vl();metadata=vl();at+=metadata
    glyphs=sorted((lo,lo+n) for font in fonts for lo,n in font['ranges']);gs=[x[0] for x in glyphs]
    position=0;literals=0
    while at<len(raw)-12:
        action=vl();kind=action&3;n=(action>>2)+1
        if kind==1:
            i=bisect.bisect_right(gs,position+n-1)-1
            if i>=0:assert glyphs[i][1]<=position,f'original glyph literal at {position}'
            at+=n;literals+=n
        elif kind in (2,3):vl()
        position+=n
    assert position==target_size==target.stat().st_size and source_size==base.stat().st_size
    old.f.close();new.f.close()
    return dict(changed_raw_sectors=changed,asset_sectors_changed=0,chinese_asset_bytes_changed=0,original_glyph_literal_bytes=0,glyph_objects=len(fonts),literal_bytes=literals,directory_growth=growth,only_program_and_layout_changes=True)

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    for name in ('base','target','patch','changes','protection','plan'):p.add_argument(name,type=Path)
    a=p.parse_args();print(json.dumps(audit(a.base,a.target,a.patch,a.changes,a.protection,a.plan)))
