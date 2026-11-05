#!/usr/bin/env python3
"""Run the actual row parser against guarded, adjacent bank text columns.

Usage: python3 tools/test_item_bank_text.py build/decomp-dev
Glyph drawing is stubbed; the real parser and proportional clear rounding run
under sanitizers. Emulator checks cover real glyphs and asynchronous page flips.
"""
import re
import subprocess
import sys
import tempfile
from pathlib import Path


def function(source, name):
    source = source.replace('\n#endif\n{', '\n{')
    match = re.search(r'^(?:static )?(?:int32_t|void) ' + name + r'\([^;\n]*?\)\n\{', source, re.M)
    assert match, name
    return source[match.start():source.index('\n}', match.end()) + 2]


def main():
    source = Path(sys.argv[1], 'src/main/script_textbox.c').read_text()
    macros = source[source.index('#define CLEAR_FROM_PEN'):source.index('\n#else\n#define CLEAR_FROM_PEN')]
    code = r'''
#include <assert.h>
#include <stdint.h>
#include <stdio.h>
#include <string.h>
#define VERSION_IS(x) 1
#define FONT_SWITCH 1
#define DRAW_STRING2_SPACE_WIDTH 8
#define TEXT_FIT_TIGHT 0x10
#define TEXT_FIT_CONDENSED 0x11
#define TEXT_COLUMN 0x12
typedef struct { int16_t x,y,w,h; } RECT;
#define setRECT(r,X,Y,W,H) (*(r)=(RECT){X,Y,W,H})
int FONT_PROPORTIONAL, DRAW_STRING2_IS_FIXED_WIDTH, FONT_CELLS;
void *DRAW2_PIECES;
unsigned char pixels[256];
int glyphAdvance;
void clearTextSubArea(RECT *r) {
    /* Match the PSX's 4-bpp cell conversion. */
    int x=(r->x/4)*4, w=(r->w/4)*4;
    assert(x>=0 && w>=0 && x+w<=256);
    memset(pixels+x,0,w);
}
void setTextColor(int color) { (void)color; }
int isAsciiEncoded(char *s) { return (unsigned char)*s < 128; }
int convertAsciiToJis(int c) { return c; }
int swapShortBytes(int c) { return c; }
int glyphWidth(int g) { (void)g; return glyphAdvance; }
int drawGlyph(int g,int x,int y) {
    (void)y;
    int advance=g==65 ? glyphAdvance : (FONT_PROPORTIONAL ? 8 : 12);
    assert(x>=0 && x+advance<=256);
    memset(pixels+x,1,advance);
    return advance;
}
int drawString2Fit(uint8_t **s,int x,int y,int pos,int c) {
    (void)s;(void)x;(void)y;(void)c;return pos;
}
int drawString2Pieces(uint8_t *s,int x,int y) {
    (void)s;(void)x;(void)y;assert(0);return 0;
}
'''
    code += function(source, 'clearFromPen') + '\n' + macros + '\n'
    code += function(source, 'drawString2') + r'''
int main(void) {
    /* Redraw either column with every possible name pen and both fonts.
       Include the half-space code emitted before the count for short names. */
    for(FONT_PROPORTIONAL=0;FONT_PROPORTIONAL<=1;FONT_PROPORTIONAL++) {
        for(int pen=0;pen<=104;pen++) {
            for(int gap=0;gap<=1;gap++) {
                uint8_t row[]={65,0x1c,0,'2','3',0,0,0};
                if(gap) {
                    uint8_t spaced[]={65,0xf,0,0x1c,0,'2','3',0};
                    memcpy(row,spaced,sizeof row);
                }
                glyphAdvance=pen;
                memset(pixels,0x7f,sizeof pixels);
                assert(drawString2(row,0,120,1)==1);
                for(int x=128;x<256;x++) assert(pixels[x]==0x7f);
                memset(pixels,0x7f,sizeof pixels);
                assert(drawString2(row,128,192,1)==1);
                for(int x=0;x<128;x++) assert(pixels[x]==0x7f);
            }
        }
    }
    puts("PASS: both bank columns preserve their neighbor for both fonts");
    return 0;
}
'''
    with tempfile.TemporaryDirectory(prefix='bank-text-') as td:
        path = Path(td)
        (path / 'test.c').write_text(code)
        subprocess.run(['cc', '-std=c99', '-Wall', '-Wextra', '-Wno-unused-parameter', '-Wno-dangling-else',
                        '-fsanitize=address,undefined', '-fno-pie', '-no-pie',
                        str(path / 'test.c'), '-o', str(path / 'test')], check=True)
        subprocess.run([str(path / 'test')], check=True)


if __name__ == '__main__':
    main()
