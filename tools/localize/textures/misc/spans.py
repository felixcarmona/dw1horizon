import sys;sys.path.insert(0,'.');from idx import load
def spans(path,entry,x0,x1,y0,y1,bg):
    w,h,px,cl,b=load(path,entry)
    out=[];s=None
    for x in range(x0,x1+1):
        on= x<x1 and any(px(x,y) not in bg for y in range(y0,y1))
        if on and s is None: s=x
        if not on and s is not None: out.append((s,x-1)); s=None
    return out
if __name__=='__main__':
    p,e,x0,x1,y0,y1=sys.argv[1],int(sys.argv[2]),*map(int,sys.argv[3:7]); bg=set(map(int,sys.argv[7].split(',')))
    print(spans(p,e,x0,x1,y0,y1,bg))
