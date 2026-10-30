import struct,sys
def load(path,entry=0):
    buf=open(path,'rb').read(); off=0
    for k in range(entry+1):
        magic,flag=struct.unpack_from('<II',buf,off); p=off+8; bpp=flag&3; cl=None
        if flag&8:
            ln,cx,cy,cw,ch=struct.unpack_from('<IHHHH',buf,p); cl=(cx,cy,cw,ch,[struct.unpack_from('<%dH'%cw,buf,p+12+2*cw*j) for j in range(ch)]); p+=ln
        ln,ix,iy,iw,ih=struct.unpack_from('<IHHHH',buf,p); data=buf[p+12:p+ln]
        if k==entry: break
        off=(p+ln+3)&~3
    w={0:iw*4,1:iw*2,2:iw}[bpp]
    def px(x,y):
        if bpp==0: return (data[y*iw*2+x//2]>>((x&1)*4))&15
        return data[y*iw*2+x]
    return w,ih,px,cl,bpp
if __name__=='__main__':
    path,x0,y0,x1,y1=sys.argv[1],*map(int,sys.argv[2:6]); e=int(sys.argv[6]) if len(sys.argv)>6 else 0
    w,h,px,cl,bpp=load(path,e)
    for y in range(y0,y1): print('%3d '%y+''.join('.123456789ABCDEF'[px(x,y)] if bpp==0 else '%02x'%px(x,y) for x in range(x0,x1)))
