/* Horizon Play's buttons: keyboard (with its ready layouts), controllers (SDL's known ones and any other joystick), the
 * button setup and the player's choice of touch or controller (controls.c, docs/player.md). */
#pragma once
#include <SDL.h>
#include <stdbool.h>
#include <stddef.h>
#include <stdint.h>

#define CONTROL_COUNT 14
extern const int control_ids[CONTROL_COUNT];   /* libretro joypad ids, in the order the setup asks for them */
extern int remap_step;                         /* the button the setup asks for now, or -1 */
extern float remap_time_left;                  /* 1 .. 0 */

enum { MODE_UNSET, MODE_TOUCH, MODE_PAD };
extern int controls_mode;                      /* what the player said they play with (asked on the first start) */
extern bool controls_menu_asked;               /* SELECT and START were pressed together */
extern bool controls_setup_wanted;             /* a joystick not set up before was connected */

void controls_load(const char *save_dir);
void controls_set_mode(int mode);
void controls_open_all(void);                  /* the controllers already connected at start */
uint16_t controls_bits(void);                  /* keyboard + every controller, as libretro joypad bits */
void controls_event(const SDL_Event *e);
uint16_t controls_frame(uint16_t bits);        /* once a frame: the bits the game gets */
void controls_setup_start(void);
void controls_setup_cancel(void);              /* the back arrow or Escape: the buttons stay as they were */

/* the keyboard alone (the menu's KEYBOARD screens): a layout, or one key for one button */
enum { KEYS_RETROARCH, KEYS_DUCKSTATION, KEYS_EPSXE, KEY_PRESETS };
extern const SDL_Scancode key_presets[KEY_PRESETS][CONTROL_COUNT][2];   /* up to two keys a button, 0 for none */
extern int key_capture;                        /* the button whose key is asked for now, or -1 */
void controls_keys(SDL_Scancode out[CONTROL_COUNT][2]);
void controls_set_keys(const SDL_Scancode keys[CONTROL_COUNT][2]);   /* and saves controls.txt */
int controls_key_preset(void);                 /* the layout the keys are now, or -1 */
void controls_capture_key(int button, bool chain);   /* the next key pressed is that button's (then the next one's) */
void controls_capture_stop(void);
float controls_capture_left(void);             /* 1 .. 0 while a key is asked for; ten seconds end it */
void controls_key_label(SDL_Scancode sc, char *out, size_t n);   /* "Z", "ENTER", "RSHIFT" */
