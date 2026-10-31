#!/usr/bin/env python3
"""Exercise the overlay renderer with real digit runs and packet bounds on the host."""
import json
import subprocess
import sys
import tempfile
from pathlib import Path


def main():
    root = Path(__file__).resolve().parents[1]
    sys.path.insert(0, str(root))
    from tools.fontgen import text_width
    for lang in ('en', 'es', 'pt-br', 'fr', 'de', 'it', 'ja', 'ca'):
        bank = {} if lang == 'en' else json.loads((root / 'text' / lang / 'names.json').read_text())
        label = bank.get('main.MOD_OPT_STR_ENEMY', 'NEW ENEMY BARS')
        values = [bank.get('main.MOD_OPT_STR_' + k, k) for k in ('OFF', 'ON')]
        width = text_width(label, 'original')
        assert width < 256, (lang, label, width)
        assert width + 8 + max(text_width(v, 'original') for v in values) + 18 <= 304, lang
    print('PASS: all eight enemy-bar labels fit the original font text area and menu row')
    work = Path(sys.argv[1]) if len(sys.argv) > 1 else Path('build/decomp-feature')
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
uint8_t BATTLE_TOGGLE_LIFEBAR;
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
            calls = 0; next = packets; renderEnemyHeadHP(&d, &f, 1);
            assert(next > packets && next < packets + 1024);
            int n = 1; for (int v = hp; v >= 10; v /= 10) n++;
            int frame_x = packets[0].x, max_x = frame_x;
            if (edge == 1) assert(frame_x == 102); /* max HP reserves five digits, without padding the value */
            for (TILE *p = packets; p < next; p++) {
                assert(p->x >= -160 && p->x + p->w <= 160);
                assert(p->y >= -120 && p->y + p->h <= 120);
                if (edge == 2) assert(p->y >= -75);
                if (edge == 4) assert(p->y >= -51);
                if (p->x + p->w > max_x) max_x = p->x + p->w;
            }
            assert(max_x == frame_x + 37 + (n-1)*4 + 4);
            assert(packets[2].w >= 1 && packets[2].w <= 32);
            assert(packets[1].r == 52 && packets[1].g == 52 && packets[1].b == 60);
            assert(packets[3].r - packets[2].r == (packets[2].r > 205 ? 255-packets[2].r : 50));
            /* Every glyph starts at the fixed gap, independent of digit count. */
            assert(packets[4].x >= frame_x + 36 && packets[4].x <= frame_x + 38);
        }
    }
    /* The gap between wild HUDs stays available at the top. */
    next = packets; calls = 0; pos.location.vx = -5; head_y = -200;
    renderEnemyHeadHP(&d, &f, 1); assert(packets[0].y == -118);
    /* Arena's left HP/MP panel reaches farther right than the wild portrait. */
    GAME_STATE = 4; next = packets; calls = 0; pos.location.vx = -25;
    renderEnemyHeadHP(&d, &f, 4);
    for (TILE *p = packets; p < next; p++) assert(p->y >= -75);
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
        renderEnemyHeadHP(&d, &f, 1); assert(next == packets);
    }
    puts("PASS: all 32767 living HP values at five anchors on a scrolled camera; bounds, fixed digit gap, HUD avoidance, track, minimum fill, dead/offscreen/finisher/results suppression");
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
