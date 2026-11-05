#!/usr/bin/env python3
"""Check the actual packed-row renderer against all translated answer words and all fonts.

Usage: python3 tools/dev/playtest/yes_no_host.py PREPARED_DECOMP
Requires the original disc extraction for font metrics; compiles the real C function on the host."""
from pathlib import Path
import sys
ROOT = next(p for p in Path(__file__).resolve().parents if (p / 'tools').is_dir())
sys.path.insert(0, str(ROOT))
import json, subprocess, tempfile, sys
from tools import fontgen as f
w=Path(sys.argv[1]);source=(w/'src/main/font.c').read_text();a=source.index('void drawGlyphPieces(');b=source.index('#define PIECES_MAX',a)
func=source[a:b]
h=r'''
#include <stdint.h>
#include <stddef.h>
#include <stdio.h>
#include <assert.h>
#define PIECE_CENTRE 0x8000
#define PIECE_LEFT 0x4000
#define PIECE_WORDS 0x2000
#define PIECE_FLAGS (PIECE_CENTRE|PIECE_LEFT|PIECE_WORDS)
#define PIECES_END 0xffff
int proportional;
#define FONT_PROPORTIONAL proportional
const uint8_t *PIECE_COLORS;
int expected[256],drawn,widths[65536],advances[65536],ink[65536],crop;
int pieceOf(const uint16_t*p,int cell){int k=0;while(p[k+1]!=PIECES_END&&(p[k+1]&~PIECE_FLAGS)<=cell)k++;return k;}
void setTextColor(int c){}
int glyphWidth(uint16_t cp){return widths[cp];}
int drawGlyph(uint16_t cp,int x,int y){assert(x>=expected[drawn]*crop);assert(x+ink[cp]<=(expected[drawn]+1)*crop);drawn++;return advances[cp];}
'''
codes,base=f.base_font();extra={c:(width,rows) for c,width,rows in f.load_extra()};em=f.extra_map();newbase,newextra=f.font_tables('b');new={}
for i,(code) in enumerate(codes):new.setdefault(code,newbase[i])
for i,(c,_,_) in enumerate(f.load_extra()):new[em[c][0]]=newextra[i][1:]
def cp(c):
 code=em[c][0] if c in em else 0x8260+ord(c)-65 if 'A'<=c<='Z' else 0x8281+ord(c)-97 if 'a'<=c<='z' else f.ASCII[c]
 return (code>>8)|(code&255)<<8,code
lines=['int main(void){']
for lang in ('en','es','pt-br','fr','de','it','ja','ca'):
 d=json.loads(Path(f'text/{lang if lang!="en" else "ours"}/names.json').read_text()) if lang!='en' else {'main.STR_YES_NO_SPACED':'Yes No'}
 text=d['main.STR_YES_NO_SPACED'];assert len(text.split())==2
 for font in (0,1,2):
  for shop in (False,True):
   cells=[];glyphs=[];word=0;previous=12;drawn=0
   lines.append("drawn=0;")
   for c in text:
    code,be=cp(c);cell,rows=f.glyph_for(c,codes,base,extra)
    if c==' ':
     cells.append(previous if shop else cell);glyphs.append(code);word=1;continue
    na,nr=new[be];li=min((r.find('#') for r in rows if '#' in r),default=0);ri=max((r.rfind('#') for r in rows),default=-1)
    width=na&255 if font==0 else ri-li+2
    original_ink=ri+1
    inkwidth= max((r.rfind('#') for r in nr),default=-1)+1 if font==0 else ri-li+1 if font==2 else original_ink
    advance=cell if font==1 else width
    lines.append(f'expected[{drawn}]={word};widths[{code}]={width};advances[{code}]={advance};ink[{code}]={inkwidth};')
    cells.append(cell);glyphs.append(code);previous=cell;drawn+=1
   crop=36 if shop else 48;flags='PIECE_CENTRE' if shop else '0';other='PIECE_CENTRE' if shop else 'PIECE_LEFT'
   lines += ['{',f'uint16_t glyphs[]={{{",".join(map(str,glyphs))}}};',f'uint8_t cells[]={{{",".join(map(str,cells))}}};',f'uint16_t pieces[]={{PIECE_WORDS|{flags},{crop}|{other},PIECES_END}};',f'crop={crop};proportional={int(font!=1)};drawGlyphPieces(glyphs,cells,{len(glyphs)},0,0,pieces);','}']
lines+=['return 0;}']
(ROOT/'build').mkdir(exist_ok=True)
with tempfile.TemporaryDirectory(dir=ROOT/'build') as d:
 p=Path(d);(p/'test.c').write_text(h+func+'\n'.join(lines));subprocess.run(['cc','-std=c99',str(p/'test.c'),'-o',str(p/'test')],check=True);subprocess.run([str(p/'test')],check=True)
print('pass: 8 languages x 3 fonts x card menu/card shop; every answer glyph stays in its crop')
