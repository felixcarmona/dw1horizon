/* Horizon Play's buttons and their setup screen (controls.c). */
#ifndef HORIZON_CONTROLS_H
#define HORIZON_CONTROLS_H
#include <SDL.h>
#include <stdbool.h>
#include <stdint.h>

#define CONTROL_COUNT 14
extern const int control_ids[CONTROL_COUNT];   /* the libretro button each setup step asks for, in order */
extern int remap_step;                         /* the step on screen, or -1: no setup */
extern float remap_time_left;                  /* 1 .. 0 */

void controls_load(const char *save_dir);      /* controls.txt there, or the defaults */
uint16_t controls_keyboard_bits(void);
uint16_t controls_pad_bits(SDL_GameController *c);
void controls_event(const SDL_Event *e);
/* each frame with what the keyboard and controllers hold: what the game gets (nothing while the setup is open) */
uint16_t controls_frame(uint16_t bits, bool any_down);
#endif
