
# Allow both direct script execution and package imports.
import sys as _image_sys
from pathlib import Path as _ImagePath
_image_sys.path.insert(0, str(next(p for p in _ImagePath(__file__).resolve().parents if (p / 'tools').is_dir())))
import json, copy, os
from tex import *; from words import *
PT_WORDS = {'NOMBRE': 'NOME', 'ESPECIE': 'DIGI', 'EDAD': 'DIAS', 'ACTIVO': 'ATIVO', 'FELICIDAD': 'FELICID.', 'VELOCIDAD': 'VELOCID.', 'INTELECTO': 'INTELECTO', 'RAPIDEZ': 'RAPIDEZ', 'POTENCIA': 'POT.', 'ALCANCE': 'ALCANCE', 'EFECTO': 'EFEITO', 'DATOS TÉC.': 'DADOS TÉC.', 'OBJETO': 'ITEM', 'PRECIO': 'VALOR', 'TÍTULO': 'TÍTULO', 'PUNTOS': 'PONTOS', 'CANT.': 'QTD.', 'FUEGO': 'FOGO', 'AIRE': 'AR', 'TIERRA': 'TERRA', 'HIELO': 'GELO', 'MUGRE': 'SUJO'}
def tr(word):
    return PT_WORDS.get(word, word) if os.environ.get('LOCALIZE_LANGUAGE') == 'pt-br' else word
EN=grid(); ES=copy.deepcopy(EN)
def fill(u,v,w,h,val):
    for y in range(h):
        for x in range(w): ES[v+y][u+x]=val
def put(arr,u,v):
    for y,row in enumerate(arr):
        for x,val in enumerate(row): ES[v+y][u+x]=val

# ---- clear the English words that move or are replaced (only areas the Spanish layout rewrites) ----
fill(0,24,140,10,15)          # element names strip (clut 4, F = transparent)
fill(0,34,116,7,15)           # header row 1 (MP at 116 kept)
fill(0,41,128,7,15)           # header row 2 (unused V.W.D LIVE TIME TYPE PROPERTY + RANG)
fill(0,48,128,7,15)           # header row 3 (SPEC TECH. DATA PLACE POINT COUNT)
fill(212,58,44,36,15)         # HAPPINESS / SPEED / BRAINS
fill(128,48,101,10,0)          # NAME DIGI WEIGHT (clut 9, 0 = transparent)
fill(0,56,25,8,0); fill(50,56,25,8,0)   # TYPE, ACTIVE cells (SPECIAL's cell left as is: nothing Spanish draws it)

items=[]
def add(en,es,arr,u,v,en_rect,clut,drawn_by,screen):
    put(arr,u,v); h=len(arr); w=len(arr[0])
    items.append(dict(en=en,es=es,texture='ETCDAT/SYSTEM_W.TIM (= ETCTIM.BIN entry 8)',u=u,v=v,w=w,h=h,en_rect=en_rect,
                      clut_row=clut,clut=[96,488+clut],drawn_by=drawn_by,screen_xy_change=screen))

# gold section tags, in place: regenerate the striped band, then letters (ink 1, shadow 8 at +1,+1)
def gold(word,font,v0):
    band={}
    for y in range(11):
        vals=[EN[v0+y][x] for x in range(1,53) if EN[v0+y][x] not in (1,8)]
        band[y]=max(set(vals),key=vals.count)
    word=tr(word)
    rows=compose(font,word); W=len(rows[0])
    x0=1+(52-(W+1))//2
    for y in range(11):
        for x in range(1,53): ES[v0+y][x]=band[y]
    for y,row in enumerate(rows):
        for x,c in enumerate(row):
            if c=='#':
                ES[v0+1+y][x0+x]=1
                if y+1>=len(rows) or x+1>=W or rows[y+1][x+1]!='#': ES[v0+2+y][x0+x+1]=8
    arr=[ES[v0+y][0:53] for y in range(11)]
    return arr,x0
SV='STATS_VIEW_ELEMENTS game_menu.c:672 (renderDigimonStatsView game_menu.c:2157)'
for en,es,font,v0 in [('PROFILE','PERFIL',GOLD5,75),('CONDITION','ESTADO',GOLD5,86),('PARAMETER','ATRIBUTOS',GOLD4,97)]:
    arr,_=gold(es,font,v0)
    items.append(dict(en=en,es=es,texture='ETCDAT/SYSTEM_W.TIM (= ETCTIM.BIN entry 8)',u=0,v=v0,w=53,h=11,en_rect=[0,v0,53,11],clut_row=8,clut=[96,496],
                      drawn_by=SV,screen_xy_change='none (same rect, same position)'))

# name tags (clut 9): ink 2, outline 1
add('NAME','NOMBRE',r_tag(tr('NOMBRE'),TAG_NOMBRE),128,48,[128,48,26,10],9,SV+' [3]','posX -138 -> -143, rect w 26 -> 31, texX 128 (same)')
add('DIGI','ESPECIE',r_tag(tr('ESPECIE')),159,48,[154,48,26,10],9,SV+' [4]','posX -138 -> -143, rect u 154 -> 159, w 26 -> 30')
add('WEIGHT','PESO',r_tag(tr('PESO')),189,48,[180,48,28,10],9,SV+' [5]','posX -67 -> -63 (centred on the old label), rect u 180 -> 189, w 28 -> 20')
add('AGE','EDAD',r_tag(tr('EDAD')),209,48,[128,58,19,10],9,SV+' [6]','posX -133 -> -135, rect (128,58,19) -> (209,48,20); moved: 20 px would touch the heart icon at u 147')
# TYPE / SPECIAL / ACTIVE (clut 9)
def tsa_cell(word,font,main,acc,w,off):
    t=r_tsa(word,main,acc) if font is None else None
    word=tr(word)
    rows=compose(font,word); arr=[[0]*w for _ in range(8)]
    for y,row in enumerate(rows):
        for x,c in enumerate(row): arr[1+y][off+x]= main if c=='#' else acc if c=='x' else 0
    return arr
add('TYPE','TIPO',tsa_cell('TIPO',TSA,12,13,25,5),0,56,[0,56,25,8],9,SV+' [7]','none (same rect and position; ink 5..17 where TYPE was 4..18)')
add('ACTIVE','ACTIVO',tsa_cell(tr('ACTIVO'),TSA_ACTIVE,8,9,25,2),50,56,[50,56,25,8],9,SV+' [9]','none (same rect and position)')
rows=compose(TSA_SPECIAL,tr('ESPECIAL')); add('SPECIAL','ESPECIAL',tsa_cell('ESPECIAL',TSA_SPECIAL,6,7,len(rows[0]),0),144,72,[25,56,25,8],9,SV+' [8]','posX 9 (same); rect (25,56,25) -> (144,72,29) in free space')
# stat labels (clut 4): ink E, shadow D
add('HAPPINESS','FELICIDAD',r_stat(tr('FELICIDAD')),212,58,[212,58,36,12],4,SV+' [17]','posX -126 -> -125 (rect unchanged; the English art was 41 px and cut at 36)')
add('SPEED','VELOCIDAD',r_stat(tr('VELOCIDAD')),212,70,[212,70,36,12],4,SV+' [18]','posX -4 -> -5, rect w 36 -> 39 (ink ends at screen 192; the bar inset starts at 194)')
add('BRAINS','INTELECTO',r_stat(tr('INTELECTO')),212,82,[212,82,36,12],4,SV+' [19]','posX -4 -> -5, rect w 36 -> 37 (INTELIGENCIA would be 47 px: no room)')
add('SPEED (alternative)','RAPIDEZ',r_stat(tr('RAPIDEZ')),110,72,[212,70,36,12],4,'alternative only (not drawn by default)','if chosen: rect (110,72,31,12), posX -4')
# tech header + move detail + shop headers (clut 4)
TT='MOVES_VIEW_TECHSET_TEXT game_menu.c:562 (renderDigimonMovesView 2279, Final row 2333)'
MD='renderDigimonMovesSelected game_menu.c:2606-2610'
SH='ITEM_MENU_HEADER_UVS script_common.c:318 (renderItemMenuSprite 2233)'
add('POWER','POTENCIA',r_small(tr('POTENCIA')),0,41,[92,34,23,7],4,TT+' [0]; '+MD,'tech header posX 22 -> 14 (also the Final row); detail panel unchanged (x0, value at x0+40)')
add('MP','MP',[[EN[34+y][116+x] for x in range(11)] for y in range(7)],116,34,[116,34,11,7],4,TT+' [3]; '+MD,'none (unchanged)')
add('RANG','ALC.',r_small(tr('ALC.')),32,41,[76,41,19,7],4,TT+' [1]','tech header posX 98 (same), rect (76,41,19) -> (32,41,15)')
add('RANG','ALCANCE',r_small(tr('ALCANCE')),47,41,[76,41,19,7],4,MD+' (0x4c,0xa9)','detail panel only: rect (76,41,19) -> (47,41,30); position unchanged')
add('SPEC','EFECTO',r_small(tr('EFECTO')),77,41,[0,48,16,7],4,TT+' [2]; '+MD+' (0,0xb0)','tech header posX 122 -> 117 (ends at 142, frame at 146); detail panel position unchanged')
add('TECH. DATA','DATOS TÉC.',r_small(tr('DATOS TÉC.')),144,96,[17,48,37,7],4,MD+' (0x11,0xb0)','rect (17,48,37,7) -> (144,96,37,9): 2 rows taller for the accent, posY -2 -> -4')
add('MENU','OBJETO',r_small(tr('OBJETO')),0,34,[0,34,20,7],4,SH+' [0]; script_common.c:962, shop/script_menu.c:1818, 2285','rect w 20 -> 25; positions unchanged (bx+8)')
add('PRICE','PRECIO',r_small(tr('PRECIO')),25,34,[20,34,20,7],4,SH+' [1]; script_common.c:965, shop/script_menu.c:1820','rect (20,34,20) -> (25,34,23); positions unchanged (bx+0x80)')
add('No.','Nº',r_small(tr('Nº')),48,34,[40,34,12,7],4,SH+' [4]; shop/script_menu.c:2387','rect (40,34,12) -> (48,34,10); position unchanged (bx+8)')
add('TITLE','TÍTULO',r_small(tr('TÍTULO')),120,96,[52,34,20,7],4,SH+' [5]; shop/script_menu.c:2388','rect (52,34,20,7) -> (120,96,23,9): 2 rows taller for the accent, y by+5 -> by+3')
add('PLACE','LUGAR',r_small(tr('LUGAR')),58,34,[56,48,20,7],4,SH+' [6]; shop/script_menu.c:2463','rect (56,48,20) -> (58,34,22); position unchanged (bx+8)')
add('POINT','PUNTOS',r_small(tr('PUNTOS')),80,34,[80,48,20,7],4,SH+' [2]; script_common.c:970, shop/script_menu.c:2464','rect (80,48,20) -> (80,34,26); positions unchanged (bx+0x80 / bx+0xa2)')
add('COUNT','CANT.',r_small(tr('CANT.')),102,41,[100,48,22,7],4,SH+' [3]; script_common.c:967,973, shop/script_menu.c:1822,1825,2287','rect (100,48,22) -> (102,41,20); positions unchanged')
# element names (clut 4): per-word rects
EL='renderDigimonMovesView case 6, game_menu.c:2403-2404 (u = j*20, v 0x98, w 20)'
x=0
for j,(en,es) in enumerate([('FIRE','FUEGO'),('BATTLE','COMBATE'),('AIR','AIRE'),('EARTH','TIERRA'),('ICE','HIELO'),('MECH','MECA'),('FILTH','MUGRE')]):
    arr=r_elem(tr(es)); w=len(r_elem(es)[0])
    assert len(arr[0]) <= w, es
    arr=[row + [15] * (w-len(row)) for row in arr]
    if es=='MUGRE': u,v=60,96
    else: u,v=x,24; x+=w
    add(en,es,arr,u,v,[j*20,24,20,10],4,EL,'per-word table {u,v,w}: left column x = -45 - w (right-aligned, 3 px before the grid at -42), right column x = 100 (unchanged)')

# ---- outputs ----
open('SYSTEM_W.es.idx','wb').write(bytes(ES[y][x] for y in range(H) for x in range(W)))
json.dump(items,open('rects.json','w'),ensure_ascii=False,indent=1)
REG8=[(0,74,55,35)]
REG9=[(128,48,82,10),(128,58,20,10),(0,56,76,8),(144,72,29,8),(209,48,20,10)]
PREVIEWS = os.environ.get('LOCALIZE_PREVIEWS') != '0'   # (tools/localize/build.py: a build writes no previews: no Pillow)
if PREVIEWS:
    from tools.image import Image
    def full(gr):
        im=Image.new('RGBA',(W,H)); p=im.load()
        def rowof(x,y):
            for (u,v,w,h) in REG8:
                if u<=x<u+w and v<=y<v+h: return 8
            for (u,v,w,h) in REG9:
                if u<=x<u+w and v<=y<v+h: return 9
            return 4
        for y in range(H):
            for x in range(W): p[x,y]=c15(pal(rowof(x,y))[gr[y][x]])
        return im
    full(EN).save('SYSTEM_W.en.png'); full(ES).save('SYSTEM_W.es.png')
    for k,s in (('en',EN),('es',ES)):
        b=Image.new('RGBA',(W,H),(40,40,60,255)); b.alpha_composite(full(s)); b.resize((W*4,H*4),Image.NEAREST).save('view_%s_x4.png'%k)
print(len(items),'items')
for it in items: print(it['es'],it['u'],it['v'],it['w'],it['h'])
