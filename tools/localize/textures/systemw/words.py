from fonts import *
def dilate8(mask):
    H=len(mask);W=len(mask[0])
    return [[any(0<=y+j<H and 0<=x+i<W and mask[y+j][x+i] for i in (-1,0,1) for j in (-1,0,1)) for x in range(W)] for y in range(H)]
def pad(rows,l,t,r,b,ch='.'):
    W=len(rows[0])+l+r
    return [ch*W]*t+[ch*l+row+ch*r for row in rows]+[ch*W]*b
def outline(rows,diag_from='#'):
    """outline pixels: 4-neighbours of any ink, diagonal neighbours only of the chars in diag_from"""
    H=len(rows);W=len(rows[0])
    def at(x,y): return rows[y][x] if 0<=x<W and 0<=y<H else '.'
    return [[any(at(x+i,y+j) in '#c' for i,j in ((1,0),(-1,0),(0,1),(0,-1))) or any(at(x+i,y+j) in diag_from for i in (-1,1) for j in (-1,1)) for x in range(W)] for y in range(H)]
def r_small(word):
    rows=pad(compose(SMALL,word),1,1,1,1)
    ol=outline(rows,'#')
    return [[1 if c=='#' else 12 if c=='c' else 13 if ol[y][x] else 15 for x,c in enumerate(r)] for y,r in enumerate(rows)]
def r_elem(word,h=10):
    rows=compose(ELEM,word,gap=0); rows=pad(rows,0,1,0,h-1-len(rows))
    return [[10 if c=='#' else 13 if c=='d' else 15 for c in r] for r in rows]
def shadow(rows,ink,sh,bg):
    H=len(rows);W=len(rows[0]); out=[[bg]*W for _ in range(H)]
    for y in range(H):
        for x in range(W):
            if rows[y][x]=='#':
                out[y][x]=ink
                if y+1<H and x+1<W and rows[y+1][x+1]!='#': out[y+1][x+1]=sh
    return out
def r_stat(word,lead=0,h=12,top=2):
    rows=compose(STAT,word); rows=pad(rows,lead,top,1,h-top-len(rows))
    return shadow(rows,14,13,15)
DIAG='#'
def r_tag(word,font=None):
    rows=pad(compose(font or TAG,word),1,1,1,1)
    ol=outline(rows,DIAG)
    return [[2 if c=='#' else 1 if ol[y][x] else 0 for x,c in enumerate(r)] for y,r in enumerate(rows)]
def r_tsa(word,main,acc,h=8,top=1):
    rows=compose(TSA,word); rows=pad(rows,0,top,0,h-top-len(rows))
    return [[main if c=='#' else acc if c=='x' else 0 for c in r] for r in rows]
