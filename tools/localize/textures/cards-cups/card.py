import os, struct
# the disc's files: tools/localize/build.py --extracted (LOCALIZE_EXTRACTED), else the repository's extracted/
EXT=os.environ.get('LOCALIZE_EXTRACTED') or os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..', '..', '..', 'extracted')
CARD=os.path.join(EXT,'CARD','CARD.ALL')
def load(k):
    buf=open(CARD,'rb').read()[k*0x7000:(k+1)*0x7000]
    magic,flag=struct.unpack_from('<II',buf,0); p=8
    ln,cx,cy,cw,ch=struct.unpack_from('<IHHHH',buf,p); pal=list(struct.unpack_from('<%dH'%cw,buf,p+12)); p+=ln
    ln,ix,iy,iw,ih=struct.unpack_from('<IHHHH',buf,p); data=bytearray(buf[p+12:p+12+iw*2*ih])
    return dict(w=iw*2,h=ih,data=data,pal=pal,clut=(cx,cy,cw,ch),img=(ix,iy),flag=flag)
def c15(v): return (0,0,0) if v==0 else ((v&31)<<3,((v>>5)&31)<<3,((v>>10)&31)<<3)
