"""Tiny pixel fonts in the styles of the game's baked texture labels, and a renderer into 4-bit index grids."""
def F(s):  # 'A: row/row/...' lines -> dict
    d={}
    for line in s.strip().splitlines():
        k,v=line.split(':',1); k=k.strip() or ' '
        if k=='SP': k=' '
        d[k]=v.strip().split('/')
    return d

# 3x6, the triangle menu's labels (FI_INFO u 80-128): ink + diagonal shadow
LABEL6=F('''
A: .#./#.#/#.#/###/#.#/#.#
B: ##./#.#/##./#.#/#.#/##.
C: .##/#../#../#../#../.##
D: ##./#.#/#.#/#.#/#.#/##.
E: ###/#../###/#../#../###
F: ###/#../###/#../#../#..
G: .##/#../#../#.#/#.#/.##
H: #.#/#.#/###/#.#/#.#/#.#
I: #/#/#/#/#/#
J: ..#/..#/..#/..#/#.#/.#.
L: #./#./#./#./#./##
M: #..#/####/##.#/#..#/#..#/#..#
N: #..#/##.#/##.#/#.##/#.##/#..#
Ñ: ####/..../#..#/##.#/#.##/#..#
O: ###/#.#/#.#/#.#/#.#/###
P: ##./#.#/#.#/##./#../#..
R: ##./#.#/#.#/##./#.#/#.#
S: .##/#../##./.##/..#/##.
T: ###/.#./.#./.#./.#./.#.
U: #.#/#.#/#.#/#.#/#.#/###
V: #.#/#.#/#.#/#.#/#.#/.#.
Y: #.#/#.#/#.#/.#./.#./.#.
Z: ###/..#/.#./#../#../###
SP: ../../../../../..
''')

# 3x7, the status bubbles (FI_INFO EVOLVE/POOP/DEAD)
BUBBLE7=F('''
A: .#./#.#/#.#/#.#/###/#.#/#.#
C: .##/#../#../#../#../#../.##
D: ##./#.#/#.#/#.#/#.#/#.#/##.
E: ###/#../#../###/#../#../###
G: .##/#../#../#.#/#.#/#.#/.##
I: #/#/#/#/#/#/#
L: #../#../#../#../#../#../###
M: #...#/##.##/#.#.#/#...#/#...#/#...#/#...#
N: #..#/##.#/##.#/#.##/#.##/#..#/#..#
O: .#./#.#/#.#/#.#/#.#/#.#/.#.
P: ##./#.#/#.#/##./#../#../#..
R: ##./#.#/#.#/##./#.#/#.#/#.#
S: .##/#../#../.#./..#/..#/##.
T: ###/.#./.#./.#./.#./.#./.#.
U: #.#/#.#/#.#/#.#/#.#/#.#/.#.
V: #.#/#.#/#.#/#.#/#.#/.#./.#.
''')

def text_mask(font,word,gap=1):
    """-> list of rows of bools, width, height"""
    glyphs=[font[c] for c in word]
    h=max(len(g) for g in glyphs)
    rows=['']*h
    for i,g in enumerate(glyphs):
        w=len(g[0])
        for y in range(h):
            rows[y]+=(g[y] if y<len(g) else '.'*w)+('.'*gap if i<len(glyphs)-1 else '')
    return [[c=='#' for c in r] for r in rows]

def width(font,word,gap=1): return len(text_mask(font,word,gap)[0])

def stamp(grid,mask,x0,y0,ink,shadow=None,shadow_off=(1,1)):
    """grid: dict-like set(x,y,idx). Draw the shadow first, then the ink."""
    H=len(mask); W=len(mask[0])
    if shadow is not None:
        dx,dy=shadow_off
        for y in range(H):
            for x in range(W):
                if mask[y][x]:
                    xx,yy=x+dx,y+dy
                    if not (0<=yy<H and 0<=xx<W and mask[yy][xx]): grid(x0+xx,y0+yy,shadow)
    for y in range(H):
        for x in range(W):
            if mask[y][x]: grid(x0+x,y0+y,ink)
