/* Horizon Play's menu and first-start question (menu.c, docs/player.md). */
#pragma once
#include <SDL.h>
#include <stdbool.h>
#include <stdint.h>

/* what the menu asks the program to do */
enum { MENU_NONE, MENU_QUIT, MENU_EXPORT, MENU_IMPORT, MENU_SETUP, MENU_TOUCH, MENU_PAD };

extern bool menu_open;
void menu_show_first(void);           /* the first start: touch, or controller and keyboard? */
void menu_show(void);                 /* the menu: continue, controls, memory card, quit */
void menu_back(void);                 /* Back / Escape */
void menu_event(const SDL_Event *e, int ww, int wh);
int menu_frame(uint16_t bits);        /* once a frame while open, with the buttons held: a MENU_ action */
void menu_result(int r);              /* an export or import ended: 1 done, 0 failed, -1 cancelled */
bool menu_waiting_drop(void);         /* (desktop) waiting for a memory card file dropped on the window */
void menu_draw(int ww, int wh);
