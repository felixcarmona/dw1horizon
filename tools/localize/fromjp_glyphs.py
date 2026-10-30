"""Our glyph tables for fromjp.py: the English words of the textures the Japanese disc has in Japanese.

Each glyph is rows of '#' (ink) and '.', joined by '/'. Drawn by us in the style of each texture's words (stroke
width, height, letter widths); the renderers in fromjp.py add the outline or shadow each style has.
"""
import importlib.util, os

HERE = os.path.dirname(os.path.abspath(__file__))


def F(s):
    d = {}
    for line in s.strip().splitlines():
        k, v = line.split(':', 1)
        k = k.strip()
        d[' ' if k == 'SP' else k] = v.strip().split('/')
    return d


def _pixfont():
    spec = importlib.util.spec_from_file_location('fiinfo_pixfont', os.path.join(HERE, 'textures', 'fi-info', 'pixfont.py'))
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


_PF = _pixfont()

# BI_IN ○PUSH: 7 rows, 2-px gaps, an 8-neighbour outline (fromjp.draw_outlined)
PUSH = F('''
P: ###./#..#/#..#/#..#/###./#.../#...
U: #...#/#...#/#...#/#...#/#...#/#...#/.###.
S: .###./#...#/#..../.###./....#/#...#/.###.
H: #...#/#...#/#...#/#####/#...#/#...#/#...#
''')

# FI_INFO's triangle-menu labels: the 3x6 font of tools/localize/textures/fi-info/pixfont.py
MENU6 = dict(_PF.LABEL6)
# PRAISE has 20 px (the sprite at u 108..127): its E 2 wide ('e'), as the font's L
MENU6['e'] = '##/#./##/#./#./##'.split('/')

# FI_INFO's status bubbles (nothing draws them in the US game): the 3x7 font of fi-info/pixfont.py
BUBBLE7 = dict(_PF.BUBBLE7)
# POOP and DEAD have room for 4-wide letters with 2-px gaps, as the US bubbles have them
BUBBLE7W = F('''
P: ###./#..#/#..#/###./#.../#.../#...
O: .##./#..#/#..#/#..#/#..#/#..#/.##.
D: ###./#..#/#..#/#..#/#..#/#..#/###.
E: ####/#.../#.../###./#.../#.../####
A: .##./#..#/#..#/####/#..#/#..#/#..#
''')
# (word, font, gap, x0, x1, y0, y1 of the bubble's inside where the word goes, its fill index, the ink index)
BUBBLES = [('EVOLVE', BUBBLE7, 1, 165, 189, 36, 44, 11, 5), ('POOP', BUBBLE7W, 2, 133, 157, 52, 60, 11, 8),
           ('DEAD', BUBBLE7W, 2, 165, 189, 52, 60, 12, 14)]

# SYSTEM_W's element names: BATTLE has a 20-px cell (u 20..39), too narrow for the 4-wide letters of
# textures/systemw/fonts.py ELEM. Narrow letters, the T's joined (as the US art does), shadow at +1,+1.
BATTLE7 = F('''
B: ##./#.#/#.#/##./#.#/#.#/##.
A: .#./#.#/#.#/###/#.#/#.#/#.#
T: ######/.#..#./.#..#./.#..#./.#..#./.#..#./.#..#.
L: #./#./#./#./#./#./##
E: ##/#./#./##/#./#./##
''')

# TAISEN_F's headers (BATTLE MODE SELECT, STAGE SELECT): 11 rows, 2-px strokes, the ink's index by row
# (HEAD_ROWS: orange top, darker middle, the texture's bright 0 and orange again at the foot), outline 1
HEAD = F('''
A: ..##../.####./.####./##..##/##..##/##..##/######/######/##..##/##..##/##..##
B: #####./######/##..##/##..##/#####./#####./##..##/##..##/##..##/######/#####.
C: .#####/######/##..../##..../##..../##..../##..../##..../##..../######/.#####
D: #####./######/##..##/##..##/##..##/##..##/##..##/##..##/##..##/######/#####.
E: ######/######/##..../##..../#####./#####./##..../##..../##..../######/######
G: .#####/######/##..../##..../##.###/##.###/##..##/##..##/##..##/######/.#####
L: ##..../##..../##..../##..../##..../##..../##..../##..../##..../######/######
M: ##...##/###.###/#######/##.#.##/##.#.##/##...##/##...##/##...##/##...##/##...##/##...##
O: .####./######/##..##/##..##/##..##/##..##/##..##/##..##/##..##/######/.####.
S: .#####/######/##..../##..../#####./.#####/....##/....##/....##/######/#####.
T: ######/######/..##../..##../..##../..##../..##../..##../..##../..##../..##..
''')
HEAD_ROWS = [5, 5, 5, 5, 12, 12, 11, 11, 0, 0, 5]

# TAISEN_F's stage labels: 9 rows, 1-px strokes, outline 1 (the outline fills the 1-px counters)
STAGE9 = F('''
A: .##./#..#/#..#/#..#/####/#..#/#..#/#..#/#..#
B: ###./#..#/#..#/#..#/###./#..#/#..#/#..#/###.
C: .##./#..#/#.../#.../#.../#.../#.../#..#/.##.
D: ###./#..#/#..#/#..#/#..#/#..#/#..#/#..#/###.
E: ####/#.../#.../#.../###./#.../#.../#.../####
G: .##./#..#/#.../#.../#.##/#..#/#..#/#..#/.###
I: #/#/#/#/#/#/#/#/#
L: #.../#.../#.../#.../#.../#.../#.../#.../####
M: #...#/##.##/#.#.#/#.#.#/#...#/#...#/#...#/#...#/#...#
N: #..#/#..#/##.#/##.#/#.##/#.##/#..#/#..#/#..#
O: .##./#..#/#..#/#..#/#..#/#..#/#..#/#..#/.##.
R: ###./#..#/#..#/#..#/###./#.#./#..#/#..#/#..#
S: .##./#..#/#.../#.../.##./...#/...#/#..#/.##.
T: #####/..#../..#../..#../..#../..#../..#../..#../..#..
U: #..#/#..#/#..#/#..#/#..#/#..#/#..#/#..#/.##.
W: #...#/#...#/#...#/#...#/#.#.#/#.#.#/#.#.#/##.##/#...#
X: #...#/#...#/.#.#./.#.#./..#../.#.#./.#.#./#...#/#...#
''')

# TAISEN_F's mode labels (BATTLE under 1 vs 1, 3 vs 3, 5 vs 5): 7 rows, 2-px gaps, outline 1
MODE7 = F('''
A: ..##../.#..#./.#..#./#....#/######/#....#/#....#
B: #####./#....#/#....#/#####./#....#/#....#/#####.
E: ######/#...../#...../######/#...../#...../######
L: #..../#..../#..../#..../#..../#..../#####
T: #####/..#../..#../..#../..#../..#../..#..
''')
