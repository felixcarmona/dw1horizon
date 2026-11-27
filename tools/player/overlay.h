/* Horizon Play's own drawing over the game: the touch pad, the button setup, the menu and the
 * drawn PlayStation controller of the keyboard screens (overlay.c, menu.c). */
#pragma once
#include <SDL.h>
#include <stdbool.h>
#include <stdint.h>

extern bool touch_shown;            /* the touch pad is on screen */
extern bool overlay_menu_tapped;    /* the touch pad's menu button was tapped */
extern int overlay_touch_size, overlay_touch_alpha;   /* the touch pad: size and opacity in percent */
extern int overlay_fps;
/* a newer release ("V0.0.11"), once known: shown for a while over the game, and in the menu */
void overlay_set_new_version(const char *tag);
void overlay_draw_new_version(float cx, float cy, float glyph_h, float alpha);             /* frames a second, shown small in the top left corner; < 0 hides it */

/* the pictures, drawn at start into one texture */
enum { I_TRI, I_CIRCLE, I_CROSS, I_SQUARE, I_UP, I_DOWN, I_LEFT, I_RIGHT, I_DPAD,
       I_L1, I_L2, I_R1, I_R2, I_SELECT, I_START, I_PANEL, I_DOT, I_WHITE, I_MENU,
       I_PLAY, I_GAMEPAD, I_CARD, I_POWER, I_TOUCH, I_KEYBOARD, I_CHECK, I_FAIL, I_PENCIL, I_EXPORT, I_IMPORT,
       I_BACK, I_DROP, I_GEAR, I_SCREEN,
       /* the menu's words, in English, under its pictures */
       T_RESUME, T_CONTROLS, T_CARD, T_QUIT, T_TOUCH, T_CONTROLLER, T_KEEP, T_SET, T_EXPORT, T_IMPORT, T_DONE,
       T_FAILED, T_DROP, T_NEW, T_SETTINGS, T_RESOLUTION, T_ORIGINAL,
       T_1X, T_2X, T_3X, T_4X, T_6X, T_8X, T_480P, T_720P, T_960P, T_1440P, T_1920P,
       T_D0, T_FPS = T_D0 + 10, T_VERSION, T_BUTTON_SIZE, T_OPACITY, T_SMALL, T_MEDIUM, T_LARGE, T_HUGE,
       T_FAINT, T_LIGHT, T_SOLID, T_FULL, T_NEW_VERSION, T_AT_SITE, T_DOT, T_V, T_DOWNLOAD, T_LATER,
       T_KEYBOARD, T_RETROARCH, T_DUCKSTATION, T_EPSXE, T_CUSTOM, I_COUNT };   /* T_D0 + n: the digit n, for the frame rate */

bool overlay_init(void);
void overlay_event(const SDL_Event *e, int ww, int wh);
uint16_t overlay_touch_bits(int ww, int wh);
void overlay_draw(int ww, int wh);
/* one picture centred at (cx, cy), w x h pixels, for the menu */
void overlay_quad(int icon, float cx, float cy, float w, float h, float bright, float alpha);
/* one of the T_ words centred at (cx, cy), its letters glyph_h pixels high, narrowed to max_w if it is wider */
/* its width in pixels with letters glyph_h high */
float overlay_text_width(int word, float glyph_h);
void overlay_text(int word, float cx, float cy, float glyph_h, float max_w, float bright, float alpha);
/* any short text in the font's characters (capitals, digits, some signs), the same way */
float overlay_string_width(const char *s, float glyph_h);
void overlay_string(const char *s, float cx, float cy, float glyph_h, float max_w, float bright, float alpha);
/* a PlayStation controller, centred at (cx, cy), w pixels wide and w * PAD_RATIO high. lit: the button (controls.h's
 * order) shown lit, or -1; labels: up to two lines of text beside each button (NULL or "" for none) */
#define PAD_RATIO 0.533f
void overlay_pad(float cx, float cy, float w, int lit, const char *const labels[][2], float alpha);
int overlay_pad_hit(float cx, float cy, float w, float x, float y);   /* the button (or its label) at (x, y), or -1 */
