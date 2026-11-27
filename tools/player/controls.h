/* Horizon Play's buttons: keyboard, controllers (SDL's known ones and any other joystick), the button setup and the
 * player's choice of touch or controller (controls.c, docs/player.md). */
#pragma once
#include <SDL.h>
#include <stdbool.h>
#include <stdint.h>

#define CONTROL_COUNT 14
extern const int control_ids[CONTROL_COUNT];   /* libretro joypad ids, in the order the setup asks for them */
extern int remap_step;                         /* the button the setup asks for now, or -1 */
extern float remap_time_left;                  /* 1 .. 0 */

enum { MODE_UNSET, MODE_TOUCH, MODE_PAD };
extern int controls_mode;                      /* what the player said they play with (asked on the first start) */
extern bool controls_menu_asked;               /* SELECT and START were pressed together */

void controls_load(const char *save_dir);
void controls_set_mode(int mode);
void controls_open_all(void);                  /* the controllers already connected at start */
uint16_t controls_bits(void);                  /* keyboard + every controller, as libretro joypad bits */
void controls_event(const SDL_Event *e);
uint16_t controls_frame(uint16_t bits);        /* once a frame: the bits the game gets */
void controls_setup_start(void);
