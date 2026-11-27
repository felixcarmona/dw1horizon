/* Horizon Play's drawing over the game: the touch pad (overlay.c). */
#ifndef HORIZON_OVERLAY_H
#define HORIZON_OVERLAY_H
#include <SDL.h>
#include <stdbool.h>
#include <stdint.h>

extern bool touch_shown;                       /* the touch pad is on screen */
bool overlay_init(void);                       /* after the GL context is made; false: no overlay */
void overlay_event(const SDL_Event *e, int ww, int wh);
uint16_t overlay_touch_bits(int ww, int wh);   /* libretro joypad bits the fingers hold now */
void overlay_draw(int ww, int wh);             /* over the picture, before the swap */
#endif
