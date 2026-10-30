import sys; from tex import *
g=grid()
def show(u,v,w,h,ink,label=''):
    ink=set(ink)
    cols=[any(g[v+y][u+x] in ink for y in range(h)) for x in range(w)]
    segs=[];x=0
    while x<w:
        if cols[x]:
            s=x
            while x<w and cols[x]: x+=1
            segs.append((s,x))
        else: x+=1
    print(label,'segments',[(u+a,b-a) for a,b in segs])
    for y in range(h):
        print('  '+''.join(('%X'%g[v+y][u+x]) if g[v+y][u+x] in ink else ('.' if g[v+y][u+x] in (0,15) else '-') for x in range(w)))
if __name__=='__main__':
    a=sys.argv; show(int(a[1]),int(a[2]),int(a[3]),int(a[4]),[int(c,16) for c in a[5]],'')
