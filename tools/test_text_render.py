#!/usr/bin/env python3
"""Host regression for the actual fitted battle cursor and color parser.

Usage: python3 tools/test_text_render.py /path/to/patched/decomp
The emulator matrix checks the real glyph widths, VRAM pixels and row timing.
"""
import subprocess
import sys
import tempfile
from pathlib import Path
from test_lab import function

def main():
    source = Path(sys.argv[1], 'src/btl/battle_hud.c').read_text()
    code = r'''
    #include <stdint.h>
    #include <string.h>
    #include <assert.h>
    #define FIT_VANILLA 0
    #define FIT_TIGHT 1
    #define FIT_CONDENSED 2
    #define FIT_COMPACT 3
    char BTL_END_BOX_TEXTBUFFER[512];
    uint8_t *BATTLE_END_CURSOR;
    int BATTLE_END_PEN_X, BATTLE_END_PEN_Y, modeDrawn, colorSet;
    char drawn[256]; uint8_t drawnColors[256];
    int measureStringMode(char *s, int mode) { return strlen(s) * (8-mode); }
    int drawFittedRow(char *s, int y, int mode, const uint8_t *colors) {
     assert(y==24); strcpy(drawn,s); modeDrawn=mode;
     memcpy(drawnColors,colors,strlen(s));return strlen(s)*5;
    }
    void setTextColor(int c) { colorSet=c; }
    '''
    code += function(source, 'BTL_drawFittedEndGlyph') + r'''
    int main(void) {
     char *row="#C3Enemy#R#C1a very long reward with #C7accent \xf0\x40 and item!#C1#W";
     strcpy(BTL_END_BOX_TEXTBUFFER,row); BATTLE_END_PEN_Y=24;
     BATTLE_END_CURSOR=(uint8_t*)strstr(BTL_END_BOX_TEXTBUFFER,"a very");
     char expected[256]={0};int n=0;
     while(*BATTLE_END_CURSOR!='#' || BATTLE_END_CURSOR[1]=='C') {
      if(*BATTLE_END_CURSOR=='#') { BATTLE_END_CURSOR+=3;continue; }
      int bytes=(*BATTLE_END_CURSOR&128)?2:1;
      memcpy(expected+n,BATTLE_END_CURSOR,bytes);n+=bytes;expected[n]=0;
      uint8_t *next=BATTLE_END_CURSOR+bytes;
      assert(BTL_drawFittedEndGlyph()==1);
      assert(BATTLE_END_CURSOR==next);
      assert(!strcmp(drawn,expected));assert(modeDrawn==FIT_COMPACT);
     }
     assert(drawnColors[0]=='1');assert(drawnColors[24]=='7');
     assert(colorSet=='7');
     /* A short row retains the original glyph renderer and cursor. */
     strcpy(BTL_END_BOX_TEXTBUFFER,"#C2short#W");
     BATTLE_END_CURSOR=(uint8_t*)BTL_END_BOX_TEXTBUFFER+3;
     uint8_t *before=BATTLE_END_CURSOR;assert(BTL_drawFittedEndGlyph()==0);
     assert(BATTLE_END_CURSOR==before);
     /* A maximal malformed row safely falls back, without a stack write past end. */
     memset(BTL_END_BOX_TEXTBUFFER,'x',511);BTL_END_BOX_TEXTBUFFER[511]=0;
     BATTLE_END_CURSOR=(uint8_t*)BTL_END_BOX_TEXTBUFFER;
     assert(BTL_drawFittedEndGlyph()==0);
     return 0;
    }
    '''
    with tempfile.TemporaryDirectory(prefix='text-render-') as td:
        p=Path(td);(p/'test.c').write_text(code)
        subprocess.run(['cc','-std=c99','-Wall','-Wextra','-fsanitize=address,undefined',
                        '-fno-pie','-no-pie',str(p/'test.c'),'-o',str(p/'test')],check=True)
        subprocess.run([str(p/'test')],check=True)
    print('PASS: actual C parser preserves typed prefixes, colors, multibyte glyphs and short rows')


if __name__ == '__main__':
    main()
