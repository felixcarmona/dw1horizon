/* Horizon Play's menu and first-start question (menu.c, docs/player.md). */
#pragma once
#include <SDL.h>
#include <stdbool.h>
#include <stdint.h>

/* what the menu asks the program to do */
enum { MENU_NONE, MENU_QUIT, MENU_EXPORT, MENU_IMPORT, MENU_SETUP, MENU_TOUCH, MENU_PAD, MENU_SCALE, MENU_TOUCHPAD, MENU_UPDATE };

extern bool menu_open;
extern int menu_scale;                /* MENU_SCALE: the resolution scale chosen */
/* MENU_TOUCHPAD: overlay_touch_size or overlay_touch_alpha changed (overlay.h) */
void menu_set_scales(const int *scales, int n, int now);   /* the resolution's choices, and the one in use */
void menu_show_first(bool ask_card);  /* the first start: (a memory card from before?) touch, or controller? */
void menu_show(void);                 /* the menu: continue, controls, memory card, quit */
void menu_show_pad(void);             /* the controller screen: choose a button to set again, nothing lit */
extern int menu_setup_button;         /* MENU_SETUP: that button alone, or -1 for every button in turn */
void menu_show_update(void);          /* a newer release (overlay_set_new_version): download (MENU_UPDATE) or later */
void menu_back(void);                 /* Back / Escape */
void menu_event(const SDL_Event *e, int ww, int wh);
int menu_frame(uint16_t bits);        /* once a frame while open, with the buttons held: a MENU_ action */
void menu_result(int r);              /* an export or import ended: 1 done, 0 failed, -1 cancelled */
bool menu_waiting_drop(void);         /* (desktop) waiting for a memory card file dropped on the window */
void menu_draw(int ww, int wh);
