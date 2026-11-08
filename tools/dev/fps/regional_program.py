"""Retain regional program data at its new ELF symbol positions.

Differences between a pinned regional release and the USA reference must be
inside unchanged-size data objects. Code differences, uncovered bytes and a
changed template byte are refused. No regional asset bytes become patch literals
merely because a rebuilt executable used USA data as its compiler seed.
"""
from pathlib import Path
import struct


def symbols(path, overlay):
    data=Path(path).read_bytes();off=struct.unpack_from('<I',data,32)[0]
    stride,count,names=struct.unpack_from('<HHH',data,46)
    secs=[struct.unpack_from('<10I',data,off+i*stride) for i in range(count)]
    strings=secs[names][4]
    def text(at):return data[at:data.index(b'\0',at)].decode('latin1')
    snames=[text(strings+s[0]) for s in secs]
    result={}
    for sec in secs:
        if sec[1]!=2:continue
        names=secs[sec[6]][4]
        for at in range(sec[4],sec[4]+sec[5],16):
            name,value,size,info,_,idx=struct.unpack_from('<IIIBBH',data,at)
            if not name or idx>=len(secs) or not size:continue
            section=snames[idx]
            if overlay and section!='.'+overlay:continue
            if not overlay and (value<0x80090800 or section in ('.MENU','.ZH','.BTL','.STD','.VS','.EVL','.ENDI','.KAR','.MOV','.FISH','.TRN','.TRN2','.DOOA','.DOO2','.DGET','.EAB','.MURD')):continue
            result[(text(names+name),section)]=(value,size,info&15)
    base=secs[snames.index('.'+overlay)][3] if overlay else 0x80090000
    return base,result


def preserve(reference,regional,target,oldelf,newelf,overlay=None):
    if len(reference)!=len(regional):raise ValueError('regional program changed length')
    changes=[i for i,(a,b) in enumerate(zip(reference,regional)) if a!=b]
    if not changes:return target,0
    oldbase,old=symbols(oldelf,overlay);newbase,new=symbols(newelf,overlay)
    result=bytearray(target)
    objects=[]
    for key,(addr,size,kind) in old.items():
        if key[0]=='FILE_OFFSET_TABLE':continue
        if kind==1 and key in new and new[key][1]==size:
            objects.append((addr-oldbase,addr-oldbase+size,key,new[key][0]-newbase))
    objects.sort(key=lambda row:row[1]-row[0])
    filetable=next(((addr-oldbase,addr-oldbase+size) for (name,_),(addr,size,_) in old.items() if name=='FILE_OFFSET_TABLE'),None)
    for at in changes:
        if filetable and filetable[0]<=at<filetable[1]:continue
        found=next((r for r in objects if r[0]<=at<r[1]),None)
        if found is None:raise ValueError(f'unmapped regional byte at {at:#x} ({overlay or "main"})')
        lo,_,key,dest=found;dest+=at-lo
        if not 0<=dest<len(result) or result[dest]!=reference[at]:
            raise ValueError(f'regional object template changed: {key[0]} +{at-lo:#x}')
        result[dest]=regional[at]
    return bytes(result),len(changes)
