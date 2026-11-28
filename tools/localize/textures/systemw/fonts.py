"""Glyph sets of SYSTEM_W's label fonts. '#'=ink, 'c'/'x'=second ink tone, 'd'=glyph-drawn shadow.
Original letters were measured from the English words; letters marked NEW are ours, drawn in the same style."""
def F(s):
    d={}
    for line in s.strip().splitlines():
        k,v=line.split(':',1); k=k.strip()
        if k=='SP': k=' '
        d[k]=v.strip().split('/')
    return d

# 7-px header labels (tech header, shop headers): 5-row ink '#' + AA 'c', 8-neighbour outline D. clut row 4.
SMALL=F('''
A: c#c/#.#/###/#.#/#.#
B: ##c/#.#/##c/#.#/##c
C: c##/#../#../#../c##
D: ##c/#.#/#.#/#.#/##c
E: ###/#../###/#../###
F: ###/#../###/#../#..
G: c##./#.../#.##/#..#/c###
H: #.#/#.#/###/#.#/#.#
I: #/#/#/#/#
J: ..#/..#/..#/#.#/c#c
L: #../#../#../#../###
M: #...#/##c##/#.#.#/#...#/#...#
N: #..#/#c.#/##c#/#.##/#..#
O: c#c/#.#/#.#/#.#/c#c
P: ##c/#.#/##c/#../#..
R: ##c/#.#/##./#.#/#.#
S: c##/#../c#c/..#/##c
T: ###/.#./.#./.#./.#.
U: #.#/#.#/#.#/#.#/c#c
.: ././././#
º: c#c/#.#/c#c/.../###
Í: .#/./#/#/#/#/#
É: ..#/.../###/#../###/#../###
SP: ./././././.
''')
SMALL.update(F('''
V: #.#/#.#/#.#/#.#/.#.
Q: c#c/#.#/#.#/##c/.##
'''))
SMALL_NEW='B J º Í É'

# element names (move help): 7-row ink '#' (white, A) with hand-drawn shadow 'd' (D). clut row 4.
ELEM=F('''
F: ###./#dd./#d../###./#dd./#d../#d../.d..
I: #./#d/#d/#d/#d/#d/#d/.d
R: ##d./#d#d/#d#d/##d./#d#d/#d#d/#d#d/.d.d
E: ###./#ddd/#dd./###./#ddd/#dd./###./.ddd
B: ##../#d#./#d#d/##.d/#d#./#d#d/##.d/.dd.
A: .#../#.#./#d#d/###d/#d#d/#d#d/#d#d/.d.d
T: ###./.#dd/.#d./.#d./.#d./.#d./.#d./..d.
H: #.#./#d#d/#d#d/###d/#d#d/#d#d/#d#d/.d.d
C: .##./#.dd/#d../#d../#d../#d../.##./..dd
M: #...#./##.##d/#d#.#d/#d.d#d/#d..#d/#d..#d/#d..#d/.d...d
L: #.../#d../#d../#d../#d../#d../###./.ddd
U: #.#./#d#d/#d#d/#d#d/#d#d/#d#d/###d/.ddd
O: .#../#.#./#d#d/#d#d/#d#d/#d#d/.#.d/..d.
G: .##./#.dd/#d../#d#./#d#d/#d#d/.##d/..dd
''')
ELEM.update(F('''
J: ..#./..#d/..#d/..#d/#.#d/#d#d/.#.d/..d.
S: .##./#.dd/#d../.#../..#./..#d/##.d/.dd.
'''))
# the three new rows' names (DARK, LIGHT, WATER; SOMBRA, LUZ, AGUA / ÁGUA)
ELEM.update(F('''
D: ##../#d#./#d#d/#d#d/#d#d/#d#d/##.d/.dd.
K: #.#./#d#d/#d#d/##.d/#d#./#d#d/#d#d/.d.d
W: #...#./#d..#d/#d..#d/#d..#d/#d#.#d/##d##d/#d.d#d/.d...d
Z: ###./..#d/..#d/.#.d/#.d./#d../###./.ddd
Á: ..#./.#../#.#./#d#d/###d/#d#d/#d#d/.d.d
'''))
# the names of the weapon row and of the fourth row's new name (WEAPON, NATURE; ARMA, NATURA)
ELEM.update(F('''
N: #..#./##.#d/##d#d/#d##d/#d##d/#d.#d/#d.#d/.d..d
P: ##../#d#./#d#d/##.d/#dd./#d../#d../.d..
'''))
ELEM_NEW='L U O G M(5-wide; the original 4-wide M reads as N)'

# status-screen stat labels (HAPPINESS/SPEED/BRAINS): 7-row yellow ink (E), shadow D at (+1,+1). clut row 4.
STAT=F('''
A: .##./#..#/#..#/####/#..#/#..#/#..#
B: ###./#..#/#..#/###./#..#/#..#/###.
D: ###./#..#/#..#/#..#/#..#/#..#/###.
E: ###/#../#../###/#../#../###
H: #..#/#..#/#..#/####/#..#/#..#/#..#
I: #/#/#/#/#/#/#
N: #..#/#..#/##.#/####/#.##/#..#/#..#
P: ###./#..#/#..#/###./#.../#.../#...
R: ###./#..#/#..#/###./#..#/#..#/#..#
S: .##./#..#/#.../.##./...#/#..#/.##.
F: ###/#../#../###/#../#../#..
L: #../#../#../#../#../#../###
C: .##./#..#/#.../#.../#.../#..#/.##.
O: .##./#..#/#..#/#..#/#..#/#..#/.##.
T: ###/.#./.#./.#./.#./.#./.#.
V: #.#/#.#/#.#/#.#/#.#/#.#/.#.
Z: ####/...#/..#./..#./.#../#.../####
.: ./././././././#
''')
STAT_NEW='F L C O T V Z .'

# gold section tags (PROFILE/CONDITION/PARAMETER): 8-row ink (1) with shadow 8 at (+1,+1) over a striped band. clut row 8.
GOLD5=F('''
P: ####./#...#/#...#/#...#/####./#..../#..../#....
R: ####./#...#/#...#/#...#/####./#..#./#...#/#...#
O: .###./#...#/#...#/#...#/#...#/#...#/#...#/.###.
F: #####/#..../#..../####./#..../#..../#..../#....
I: #/#/#/#/#/#/#/#
L: #..../#..../#..../#..../#..../#..../#..../#####
E: #####/#..../#..../####./#..../#..../#..../#####
C: .###./#...#/#..../#..../#..../#..../#...#/.###.
N: #....#/##...#/###..#/#.#..#/#..#.#/#...##/#....#/#....#
D: ####./#...#/#...#/#...#/#...#/#...#/#...#/####.
T: #####/..#../..#../..#../..#../..#../..#../..#..
S: .###./#...#/#..../.###./....#/....#/#...#/.###.
A: .###./#...#/#...#/#...#/#####/#...#/#...#/#...#
''')
GOLD4=F('''
P: ###./#..#/#..#/#..#/###./#.../#.../#...
R: ###./#..#/#..#/#..#/###./#..#/#..#/#..#
E: ####/#.../#.../###./#.../#.../#.../####
A: .##./#..#/#..#/#..#/####/#..#/#..#/#..#
M: #...#/##.##/##.##/#.#.#/#...#/#...#/#...#/#...#
T: #####/..#../..#../..#../..#../..#../..#../..#..
I: #/#/#/#/#/#/#/#
B: ###./#..#/#..#/###./#..#/#..#/#..#/###.
U: #..#/#..#/#..#/#..#/#..#/#..#/#..#/.##.
O: .##./#..#/#..#/#..#/#..#/#..#/#..#/.##.
S: .##./#..#/#.../.##./...#/...#/#..#/.##.
''')
GOLD_NEW='GOLD5: S A; GOLD4: B U O S'

# NAME/DIGI/WEIGHT/AGE tags: 8-row ink (2) with an 8-neighbour outline (1). clut row 9.
TAG=F('''
A: .##./#..#/#..#/####/#..#/#..#/#..#/#..#
D: ###./#..#/#..#/#..#/#..#/#..#/#..#/###.
E: ###/#../#../###/#../#../#../###
G: .###/#.../#.../#.##/#..#/#..#/#..#/.###
H: #..#/#..#/#..#/####/#..#/#..#/#..#/#..#
I: #/#/#/#/#/#/#/#
M: #...#/##.##/#####/#.#.#/#...#/#...#/#...#/#...#
N: #...#/##..#/###.#/#####/#.###/#..##/#...#/#...#
T: ###/.#./.#./.#./.#./.#./.#./.#.
W: #...#/#...#/#...#/#...#/#.#.#/#####/##.##/#...#
O: .##./#..#/#..#/#..#/#..#/#..#/#..#/.##.
B: ###./#..#/#..#/###./#..#/#..#/#..#/###.
R: ###./#..#/#..#/###./#..#/#..#/#..#/#..#
S: .###/#.../#.../.##./...#/...#/...#/###.
P: ###./#..#/#..#/###./#.../#.../#.../#...
C: .###/#.../#.../#.../#.../#.../#.../.###
''')
TAG.update(F('''
U: #..#/#..#/#..#/#..#/#..#/#..#/#..#/.##.
K: #..#/#.#./##../##../#.#./#..#/#..#/#..#
F: ###/#../#../###/#../#../#../#..
L: #../#../#../#../#../#../#../###
'''))
TAG_NEW='O B R S P C K F L U'
# Like NOMBRE's four-pixel N below: keep MISTAKES in its 36-pixel tag
# without scaling the other letters or changing the eight-row label body.
TAG_STATUS=dict(TAG,M='#..#/####/####/#..#/#..#/#..#/#..#/#..#'.split('/'))

# TYPE/SPECIAL/ACTIVE: 5-row, no outline; '#' main tone, 'x' darker corner tone. clut row 9.
TSA=F('''
T: ###/.#./.#./.#./.#.
Y: #.#/#.#/x#x/.#./.#.
P: ##x/#.#/##x/#../#..
E: ###/#../###/#../###
F: ###/#../###/#../#..
S: x##/#../###/..#/##x
C: x##/#x./#../#x./x##
I: #/#/#/#/#
A: x#x/#.#/###/#.#/#.#
L: #../#../#../#../###
V: #.#/#.#/#.#/#.#/.#.
O: x#x/#.#/#.#/#.#/x#x
''')
TSA_SPECIAL=dict(TSA,E='###/#../##./#../###'.split('/'))
TSA_ACTIVE=dict(TSA,C='###/#../#../#../###'.split('/'))
TSA_NEW='O'

def compose(font,text,gap=1,space=None):
    """-> rows (list of str), glyph height aligned at the bottom. Overlay priority: ink > tone > shadow > empty."""
    gl=[font[c] for c in text]
    H=max(len(g) for g in gl)
    W=sum(len(g[-1]) for g in gl)+gap*(len(gl)-1)
    out=[['.']*W for _ in range(H)]
    pri={'.':0,'d':1,'c':2,'x':2,'#':3}
    x=0
    for c,g in zip(text,gl):
        w=len(g[-1]); off=H-len(g)
        for y,row in enumerate(g):
            for i,ch in enumerate(row):
                if x+i>=W: continue
                if pri[ch]>pri[out[y+off][x+i]]: out[y+off][x+i]=ch
        # glyphs with a drawn shadow column (ELEM) advance by w (the shadow column is the gap)
        x+=w+gap
    return [''.join(r) for r in out]
# NOMBRE uses a 4-wide N (NEW) so the tag keeps 3 px from the panel frame and 2 px from the field box
TAG_NOMBRE=dict(TAG,N='#..#/##.#/##.#/#.##/#.##/#..#/#..#/#..#'.split('/'))

# ---- the letters the other translations (French, German, Italian, Catalan) need: all NEW, in each font's style. ----
# tools/localize/labels.py sets those languages' SYSTEM_W words in these fonts at their native size (never scaled).
# An accented capital is the letter under a one-pixel accent and a blank row, as É is above. Where a cell has no rows
# for that, the letter's body is shorter: an element name's keeps the blank row (a five-row body), a tag's and a shop
# header's (TAG_COMPACT, SMALL_COMPACT below) put the accent on the body's first row, as Á is in ELEM.
for _font in (SMALL,):
    _font.update(F('''
K: #.#/#.#/##c/#.#/#.#
W: #...#/#...#/#.#.#/##c##/#...#
X: #.#/#.#/c#c/#.#/#.#
Z: ###/..#/c#c/#../###
È: #../.../###/#../###/#../###
o: .../.../c#c/#.#/c#c
'''))
TAG.update(F('''
Y: #.#/#.#/#.#/#.#/.#./.#./.#./.#.
.: ./././././././#
'''))
# narrower letters for a word too wide for its 20-pixel tag with the four-pixel ones (as NOMBRE's N)
TAG_NARROW = dict(TAG, **F('''
P: ##./#.#/#.#/#.#/##./#../#../#..
O: .#./#.#/#.#/#.#/#.#/#.#/#.#/.#.
D: ##./#.#/#.#/#.#/#.#/#.#/#.#/##.
S: .##/#../#../.#./..#/..#/..#/##.
'''))
for _font in (TSA, TSA_SPECIAL, TSA_ACTIVE):
    _font.update(F('''
K: #.#/#.#/##x/#.#/#.#
U: #.#/#.#/#.#/#.#/x#x
Z: ###/..#/x#x/#../###
'''))
TSA_SPECIAL['É'] = ['..#', '...'] + TSA_SPECIAL['E']
STAT.update(F('''
G: .##./#..#/#.../#.##/#..#/#..#/.##.
K: #..#/#.#./##../##../#.#./#..#/#..#
M: #...#/##.##/#.#.#/#...#/#...#/#...#/#...#
U: #..#/#..#/#..#/#..#/#..#/#..#/.##.
·: ./././#/./././.
'''))
STAT['À'] = ['.#..', '....'] + STAT['A']
ELEM.update(F('''
Q: .#../#.#./#d#d/#d#d/#d#d/#d#d/.##d/..d#
É: ..#./..../###./#ddd/##d./#dd./###./.ddd
È: #.../..../###./#ddd/##d./#dd./###./.ddd
Í: .#/../#./#d/#d/#d/#d/.d
'''))
# the accented capitals for a cell with no spare rows (a shop header's seven, a tag's ten): accent on the letter's top row
SMALL_COMPACT = dict(SMALL, **F('''
É: ..#/##./#../##./###
À: #../.../c#c/###/#.#
'''))
TAG_COMPACT = dict(TAG, **F('''
Â: .##./#..#/..../.##./#..#/####/#..#/#..#
À: .#../..#./.##./#..#/#..#/####/#..#/#..#
È: #../.#./###/#../###/#../#../###
'''))
STAT.update(F('''
!: #/#/#/#/#/./#
'''))
