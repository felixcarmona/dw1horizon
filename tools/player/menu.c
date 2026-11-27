/* Horizon Play's menu (docs/player.md). SELECT and START together (or the touch pad's menu button, or a phone's Back)
 * pause the game and show big pictures, no text, so it needs no language:
 *
 *   play            back to the game
 *   controller      touch, or controller and keyboard; then keep the buttons or set them (controls.c)
 *   memory card     export (a file picker on Android, the save folder opened on a computer) or import (a file
 *                   picker, or a file dropped on the window); the card in use is backed up first
 *   power           quit
 *
 * The first start shows the touch / controller question before the game. The pictures are chosen with a tap or the
 * mouse, or with the pad's arrows and Cross, Circle or START; Triangle goes back.
 */
#include "menu.h"
#include "overlay.h"
#include "controls.h"
#include <math.h>
#include "libretro.h"

bool menu_open;

enum { S_FIRST, S_MAIN, S_MODE, S_PADCHECK, S_CARD, S_WAIT, S_DROP, S_RESULT };
static int screen, focus, result_ok, touched = -3;
static Uint32 result_at;
static bool first;            /* the first-start question: no way back, the game waits for an answer */
static bool fire, fire_back;  /* a tap or click to act on in the next frame */
static int fire_card;
static uint16_t prev;

typedef struct { int icon, icon2, action; } Card;
enum { A_CONTINUE = 100, A_CONTROLS, A_CARD, A_CHECK };
static const Card main_cards[] = {{I_PLAY, -1, A_CONTINUE}, {I_GAMEPAD, -1, A_CONTROLS}, {I_CARD, -1, A_CARD},
                                  {I_POWER, -1, MENU_QUIT}};
static const Card mode_cards[] = {{I_TOUCH, -1, MENU_TOUCH}, {I_GAMEPAD, I_KEYBOARD, MENU_PAD}};
static const Card check_cards[] = {{I_CHECK, -1, A_CHECK}, {I_PENCIL, -1, MENU_SETUP}};
static const Card card_cards[] = {{I_EXPORT, -1, MENU_EXPORT}, {I_IMPORT, -1, MENU_IMPORT}};

static const Card *cards(int *n) {
  switch (screen) {
  case S_MAIN: *n = 4; return main_cards;
  case S_FIRST: case S_MODE: *n = 2; return mode_cards;
  case S_PADCHECK: *n = 2; return check_cards;
  case S_CARD: *n = 2; return card_cards;
  }
  *n = 0; return NULL;
}

static int header(void) {
  return screen == S_PADCHECK ? I_GAMEPAD : screen == S_CARD ? I_CARD : -1;
}

static void go(int s) { screen = s; focus = 0; touched = -3; }

static void open_at(int s) { menu_open = true; prev = 0xFFFF; fire = fire_back = false; go(s); }
void menu_show_first(void) { first = true; open_at(S_FIRST); }
void menu_show(void) { first = false; open_at(S_MAIN); }
static void close_menu(void) { menu_open = false; first = false; }

void menu_back(void) {
  switch (screen) {
  case S_MAIN: close_menu(); break;
  case S_MODE: case S_CARD: go(S_MAIN); break;
  case S_PADCHECK: go(first ? S_FIRST : S_MODE); break;
  case S_DROP: go(S_CARD); break;
  }
}

void menu_result(int r) {
  if (r < 0) { go(S_CARD); return; }
  result_ok = r > 0; result_at = SDL_GetTicks(); go(S_RESULT);
}

bool menu_waiting_drop(void) { return menu_open && screen == S_DROP; }

/* ---- layout ---- */
static float S(int ww, int wh) { return ww < wh ? (float)ww : (float)wh; }

static void card_rect(int i, int n, int ww, int wh, float *cx, float *cy, float *size) {
  float s = S(ww, wh), gap = 0.05f * s;
  float cs = fminf(0.36f * s, (ww - gap * (n + 1)) / n);
  *size = cs;
  *cx = ww / 2.0f + (i - (n - 1) / 2.0f) * (cs + gap);
  *cy = header() >= 0 ? wh * 0.6f : wh * 0.5f;
}

static void back_rect(int ww, int wh, float *cx, float *cy, float *size) {
  float s = S(ww, wh);
  *size = 0.13f * s; *cx = 0.1f * s; *cy = 0.1f * s;
}

static bool has_back(void) { return screen != S_RESULT && screen != S_WAIT && !(screen == S_FIRST); }

/* which card is at (x, y): its index, -2 for the back arrow, -1 for none */
static int hit(float x, float y, int ww, int wh) {
  float cx, cy, size;
  if (has_back()) {
    back_rect(ww, wh, &cx, &cy, &size);
    if (fabsf(x - cx) < size * 0.7f && fabsf(y - cy) < size * 0.7f) return -2;
  }
  int n; cards(&n);
  for (int i = 0; i < n; i++) {
    card_rect(i, n, ww, wh, &cx, &cy, &size);
    if (fabsf(x - cx) < size / 2 && fabsf(y - cy) < size / 2) return i;
  }
  return -1;
}

void menu_event(const SDL_Event *e, int ww, int wh) {
  float x, y; bool down;
  switch (e->type) {
  case SDL_FINGERDOWN: case SDL_FINGERUP:
    x = e->tfinger.x * ww; y = e->tfinger.y * wh; down = e->type == SDL_FINGERDOWN; break;
  case SDL_MOUSEBUTTONDOWN: case SDL_MOUSEBUTTONUP: {
    if (e->button.which == SDL_TOUCH_MOUSEID || e->button.button != SDL_BUTTON_LEFT) return;
    /* the mouse is in window points; the layout is in drawable pixels */
    int pw, ph; SDL_GetWindowSize(SDL_GetWindowFromID(e->button.windowID), &pw, &ph);
    x = e->button.x * (float)ww / (pw ? pw : 1); y = e->button.y * (float)wh / (ph ? ph : 1);
    down = e->type == SDL_MOUSEBUTTONDOWN; break;
  }
  default: return;
  }
  int h = hit(x, y, ww, wh);
  if (down) { touched = h; if (h >= 0) focus = h; return; }
  if (h != touched || h == -1) { touched = -3; return; }
  touched = -3;
  if (h == -2) fire_back = true;
  else { fire = true; fire_card = h; }
}

static int act(int i) {
  int n; const Card *c = cards(&n);
  if (!c || i < 0 || i >= n) return MENU_NONE;
  switch (c[i].action) {
  case A_CONTINUE: close_menu(); return MENU_NONE;
  case A_CONTROLS: go(S_MODE); return MENU_NONE;
  case A_CARD: go(S_CARD); return MENU_NONE;
  case A_CHECK: close_menu(); return MENU_NONE;
  case MENU_TOUCH: close_menu(); return MENU_TOUCH;
  case MENU_PAD: go(S_PADCHECK); return MENU_PAD;
  case MENU_SETUP: close_menu(); return MENU_SETUP;
  case MENU_QUIT: close_menu(); return MENU_QUIT;
  case MENU_EXPORT:
#ifdef __ANDROID__
    go(S_WAIT);
#endif
    return MENU_EXPORT;
  case MENU_IMPORT:
#ifdef __ANDROID__
    go(S_WAIT); return MENU_IMPORT;
#else
    go(S_DROP); return MENU_NONE;
#endif
  }
  return MENU_NONE;
}

int menu_frame(uint16_t bits) {
  uint16_t edge = bits & ~prev;
  prev = bits;
  if (screen == S_RESULT) {
    if (SDL_GetTicks() - result_at > 1300) { if (result_ok) close_menu(); else go(S_CARD); }
    return MENU_NONE;
  }
  if (screen == S_WAIT) return MENU_NONE;
  if (fire_back) { fire_back = false; menu_back(); return MENU_NONE; }
  if (fire) { fire = false; return act(fire_card); }
  int n; cards(&n);
#define E(b) (edge & (1u << RETRO_DEVICE_ID_JOYPAD_##b))
  if (n) {
    if ((E(LEFT) || E(UP)) && focus > 0) focus--;
    if ((E(RIGHT) || E(DOWN)) && focus < n - 1) focus++;
    if (E(B) || E(A) || E(START)) return act(focus);
  }
  if (E(X)) menu_back();
#undef E
  return MENU_NONE;
}

/* ---- drawing ---- */
static void frame_box(float cx, float cy, float w, float h, float t, float alpha) {
  overlay_quad(I_WHITE, cx, cy - h / 2, w, t, 1, alpha);
  overlay_quad(I_WHITE, cx, cy + h / 2, w, t, 1, alpha);
  overlay_quad(I_WHITE, cx - w / 2, cy, t, h + t, 1, alpha);
  overlay_quad(I_WHITE, cx + w / 2, cy, t, h + t, 1, alpha);
}

void menu_draw(int ww, int wh) {
  float s = S(ww, wh);
  overlay_quad(I_PANEL, ww / 2.0f, wh / 2.0f, (float)ww, (float)wh, 1, screen == S_FIRST ? 0.92f : 0.75f);
  if (screen == S_RESULT) {
    overlay_quad(result_ok ? I_CHECK : I_FAIL, ww / 2.0f, wh / 2.0f, 0.4f * s, 0.4f * s, 1, 1);
    return;
  }
  if (screen == S_WAIT) return;
  if (screen == S_DROP) {   /* drop the memory card file on the window */
    overlay_quad(I_CARD, ww / 2.0f - 0.16f * s, wh * 0.5f, 0.3f * s, 0.3f * s, 1, 0.9f);
    overlay_quad(I_DROP, ww / 2.0f + 0.16f * s, wh * 0.5f, 0.36f * s, 0.36f * s, 1, 1);
  }
  if (header() >= 0) overlay_quad(header(), ww / 2.0f, wh * 0.24f, 0.22f * s, 0.22f * s, 1, 0.85f);
  int n; const Card *c = cards(&n);
  for (int i = 0; i < n; i++) {
    float cx, cy, size;
    card_rect(i, n, ww, wh, &cx, &cy, &size);
    bool on = i == focus;
    float k = on ? 1.06f : 1, z = size * k;
    overlay_quad(I_PANEL, cx, cy, z, z, 1, on ? 0.8f : 0.5f);
    frame_box(cx, cy, z, z, (on ? 0.012f : 0.006f) * s, on ? 0.95f : 0.35f);
    float bright = on ? 1.1f : 0.8f;
    if (c[i].icon2 < 0) overlay_quad(c[i].icon, cx, cy, z * 0.7f, z * 0.7f, bright, 1);
    else {
      overlay_quad(c[i].icon, cx, cy - z * 0.17f, z * 0.58f, z * 0.58f, bright, 1);
      overlay_quad(c[i].icon2, cx, cy + z * 0.24f, z * 0.46f, z * 0.46f, bright, 1);
    }
  }
  if (has_back()) {
    float cx, cy, size;
    back_rect(ww, wh, &cx, &cy, &size);
    overlay_quad(I_BACK, cx, cy, size, size, 1, 0.8f);
  }
}
