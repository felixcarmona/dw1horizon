#!/usr/bin/env python3
"""Exercise the overlay renderer with real digit runs and packet bounds on the host."""
import sys as _sys, pathlib as _pl; _sys.path.insert(0, str(_pl.Path(__file__).resolve().parent))  # tools/ modules resolve under `python -m unittest tools.<name>`
from host_tree import host_tree
import json
import subprocess
import sys
import tempfile
from pathlib import Path


def main():
    root = Path(__file__).resolve().parents[1]
    sys.path.insert(0, str(root))
    work = host_tree()
    for lang in ('es', 'pt-br', 'fr', 'de', 'it', 'ja', 'ca', 'zh-hans'):
        bank = json.loads((root / 'text' / lang / 'names.json').read_text())
        for key in ('BARS', 'CLOCK', 'ENEMY'):
            assert f'main.MOD_OPT_STR_{key}' not in bank
    english = (work / 'text/main/main_menu.yaml').read_text()
    for key in ('BARS', 'CLOCK', 'ENEMY'):
        assert f'MOD_OPT_STR_{key}:' not in english
    print('PASS: removed option labels are absent in every language')
    source = (work / 'include/dw/enemy_bars.h').read_text()
    source = '\n'.join(line for line in source.splitlines() if not line.startswith('#include'))
    harness = r'''
#include <stdint.h>
#include <assert.h>
#include <stdio.h>
typedef struct { int16_t vx, vy, vz; } SVECTOR;
typedef struct { int16_t vx, vy; } DVECTOR;
typedef struct { int x, y, w, h, r, g, b, z; } TILE;
typedef TILE PACKET;
#define ONE 4096
typedef struct { int attribute, x, y, w, h, tpage, u, v, cx, cy, r, g, b, mx, my, scalex, scaley, rotate; } GsSPRITE;
GsSPRITE sprite_seen; int sprites;
void GsSortFastSprite(GsSPRITE *s, void *ot, int z) { sprite_seen = *s; sprites++; }
struct { int digits, x, y, value; } text_seen; int texts;
void drawEntityText(int32_t color, int32_t n, int32_t x, int32_t y, int32_t value, int32_t layer) { text_seen.digits = n; text_seen.x = x; text_seen.y = y; text_seen.value = value; texts++; }
struct { void *org; } ot, *ACTIVE_ORDERING_TABLE = &ot;
TILE packets[1024], *next = packets;
#define setTile(p) ((void)0)
#define setRGB0(p,a,c,d) ((p)->r=(a),(p)->g=(c),(p)->b=(d))
#define setXY0(p,a,b) ((p)->x=(a),(p)->y=(b))
#define setWH(p,a,b) ((p)->w=(a),(p)->h=(b))
#define AddPrim(z,p) ((void)(p))
void *GsGetWorkBase(void) { return next; }
void GsSetWorkBase(PACKET *p) { next = p; }
typedef struct { SVECTOR location; } Pos;
typedef struct { struct { Pos *posData; int type; } entity;
    struct { struct { int16_t currentHP; } current; struct { int16_t hp; } base; } stats; } DigimonEntity;
typedef struct { int flags; } FighterData;
#define FIGHTER_FLAG_DEAD 1
struct { int height; } para;
#define DIGI_PARA(t) para
int GAME_STATE = 1, NO_AI_FLAG, head_y, calls;
int DRAWING_OFFSET_X = 342, DRAWING_OFFSET_Y = 320;
int32_t worldPosToScreenPos(SVECTOR *p, DVECTOR *out) {
    assert(calls++ % 2 == 0 || p->vy == -para.height);
    out->vx = p->vx + 160 - DRAWING_OFFSET_X;
    out->vy = (calls % 2 ? p->vz : head_y) + 120 - DRAWING_OFFSET_Y;
    return 100;
}
'''
    checks = r'''
int main(void) {
    Pos pos = { {0, 0, 0} };
    DigimonEntity d = {0}; FighterData f = {0};
    d.entity.posData = &pos; para.height = 1000;
    d.stats.base.hp = 32767;
    for (int hp = 1; hp <= 32767; hp++) {
        d.stats.current.currentHP = hp;
        for (int edge = 0; edge < 5; edge++) {
            pos.location.vx = edge == 0 ? -159 : edge == 1 ? 159 : edge == 2 ? 80 : edge == 4 ? -130 : 0;
            head_y = (edge == 2 || edge == 4) ? -200 : -30;
            calls = 0; next = packets; sprites = texts = 0; renderEnemyHeadHP(&d, &f);
            /* the outline is four rectangles, the fill one sprite, the number one text run */
            assert(next == packets + 4 && sprites == 1 && texts == 1);
            int frame_x = packets[0].x, frame_y = packets[0].y;
            if (edge == 0) assert(frame_x == -159);
            if (edge == 1) assert(frame_x == 145 - 50); /* clamped clear of the partner panel's edge */
            for (TILE *p = packets; p < next; p++) {
                assert(p->x >= -160 && p->x + p->w <= 160);
                assert(p->y >= -120 && p->y + p->h <= 120);
            }
            if (edge == 2) assert(frame_y >= -65);
            if (edge == 4) assert(frame_y >= -41);
            assert(packets[0].w == 50 && packets[1].y == frame_y + 6);
            assert(packets[0].r == 10 && packets[0].g == 180 && packets[0].b == 10);
            /* the fill never leaves the frame and keeps at least one pixel */
            assert(sprite_seen.w >= 1 && sprite_seen.w <= 45);
            assert(sprite_seen.x == frame_x + 2 && sprite_seen.y == frame_y + 2);
            assert(sprite_seen.w == (hp * 45 / 32767 < 1 ? 1 : hp * 45 / 32767));
            /* max HP reserves five digits, so the last digit stays put as the HP loses digits */
            assert(text_seen.digits == 5 && text_seen.value == hp);
            assert(text_seen.x == frame_x + 50 - 22 - 9 && text_seen.y == frame_y - 9);
        }
    }
    /* The gap between wild HUDs stays available at the top. */
    next = packets; calls = 0; pos.location.vx = -5; head_y = -200;
    renderEnemyHeadHP(&d, &f); assert(packets[0].y == -108);
    /* Arena and VS draw none: their top-right panel already shows the opponent's HP. */
    GAME_STATE = 4; next = packets; calls = 0; pos.location.vx = -25;
    renderEnemyHeadHP(&d, &f); assert(next == packets);
    GAME_STATE = 1;
    for (int reason = 0; reason < 6; reason++) {
        next = packets; calls = 0; pos.location.vx = 0; GAME_STATE = 1; NO_AI_FLAG = 0;
        d.stats.current.currentHP = 1; f.flags = 0;
        if (reason == 0) d.stats.current.currentHP = 0;
        if (reason == 1) f.flags = FIGHTER_FLAG_DEAD;
        if (reason == 2) GAME_STATE = 2;
        if (reason == 3) NO_AI_FLAG = 1;
        if (reason == 4) pos.location.vx = 160;
        if (reason == 5) pos.location.vx = -161;
        renderEnemyHeadHP(&d, &f); assert(next == packets);
    }
    puts("PASS: all 32767 living HP values at five anchors on a scrolled camera; bounds, fixed digit gap, HUD avoidance, minimum fill, dead/offscreen/finisher/results suppression, no bar in arena or VS");
}
'''
    with tempfile.TemporaryDirectory() as temp:
        path = Path(temp) / 'bars.c'
        path.write_text(harness + source + checks)
        exe = Path(temp) / 'bars'
        subprocess.run(['cc', '-std=c99', '-O1', '-fsanitize=address,undefined', str(path), '-o', str(exe)], check=True)
        subprocess.run([str(exe)], check=True)


if __name__ == '__main__':
    main()
