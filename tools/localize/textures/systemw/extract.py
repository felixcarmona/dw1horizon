from tex import *
g=grid()
def segs(u,v,w,h,ink):
    cols=[any(g[v+y][u+x] in ink for y in range(h)) for x in range(w)]
    out=[];x=0
    while x<w:
        if cols[x]:
            s=x
            while x<w and cols[x]: x+=1
            out.append((u+s,x-s))
        else: x+=1
    return out
def glyph(u,v,w,h,keep,sym):
    return '/'.join(''.join(sym.get(g[v+y][u+x],'.') if g[v+y][u+x] in keep else '.' for x in range(w)) for y in range(h))
def lib(rows):
    d={}
    for (u,v,w,h,ink,text,sym) in rows:
        ss=segs(u,v,w,h,ink)
        if len(ss)!=len(text): print('MISMATCH',text,len(ss),ss); continue
        for (x,ww),c in zip(ss,text):
            gl=glyph(x,v,ww,h,ink,sym)
            d.setdefault(c,[]); 
            if gl not in d[c]: d[c].append(gl)
    return d
if __name__=='__main__':
    sym={1:'#',12:'c'}
    d=lib([(0,35,128,5,{1,12},'MENUPRICENo.TITLENAMEPOWERMP',sym),(0,49,128,5,{1,12},'SPECTECH.DATAPLACEPOINTCOUNT',sym)])
    for k in sorted(d): print(k, d[k])
    for x,w in segs(0,42,128,5,{1,12}): print(x,w,glyph(x,42,w,5,{1,12},sym))
