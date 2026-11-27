/* Horizon Play's menu (docs/player.md). SELECT and START together (or the touch pad's menu button) pause the game
 * and show big pictures, each with a word in English under it:
 *
 *   play            back to the game
 *   controls        controller and keyboard: keep the buttons or set them (controls.c)
 *   memory card     export (a file picker on Android, the save folder opened on a computer) or import (a file
 *                   picker, or a file dropped on the window); the card in use is backed up first
 *   gear            settings: resolution (the core's internal resolution scale, settings.txt)
 *   power           quit
 *
 * The first start shows the touch / controller question before the game; on Android a new install with no memory
 * card first offers to import one (the copy HorizonActivity keeps in Documents) or to start a new game. The pictures
 * are chosen with a tap or the mouse, or with the pad's arrows and Cross, Circle or START; Triangle goes back.
 */
#include "menu.h"
#include "overlay.h"
#include "controls.h"
#include <math.h>
#include "libretro.h"

bool menu_open;

enum { S_RESTORE, S_FIRST, S_MAIN, S_PADCHECK, S_CARD, S_WAIT, S_DROP, S_RESULT, S_SETTINGS, S_SCALE };
static int screen, focus, result_ok, touched = -3;
static Uint32 result_at;
static bool first;            /* the first-start question: no way back, the game waits for an answer */
static bool fire, fire_back;  /* a tap or click to act on in the next frame */
static int fire_card;
static int card_screen;   /* where the memory card's screens return to: S_CARD, or S_RESTORE */
static uint16_t prev;

typedef struct { int icon, icon2, action, word; } Card;
enum { A_CONTINUE = 100, A_CONTROLS, A_CARD, A_CHECK, A_NEW, A_SETTINGS, A_RESOLUTION, A_SCALE = 200 /* + N */ };
static const Card main_cards[] = {{I_PLAY, -1, A_CONTINUE, T_RESUME}, {I_GAMEPAD, I_KEYBOARD, A_CONTROLS, T_CONTROLS},
                                  {I_CARD, -1, A_CARD, T_CARD}, {I_GEAR, -1, A_SETTINGS, T_SETTINGS},
                                  {I_POWER, -1, MENU_QUIT, T_QUIT}};
static const Card settings_cards[] = {{I_SCREEN, -1, A_RESOLUTION, T_RESOLUTION}};
/* the resolution's choices: the card shows the scale (a word), the word under it the picture's height */
static Card scale_cards[8];
static int scale_count, scale_now;
int menu_scale;
static const Card mode_cards[] = {{I_TOUCH, -1, MENU_TOUCH, T_TOUCH}, {I_GAMEPAD, I_KEYBOARD, MENU_PAD, T_CONTROLLER}};
static const Card check_cards[] = {{I_CHECK, -1, A_CHECK, T_KEEP}, {I_PENCIL, -1, MENU_SETUP, T_SET}};
static const Card restore_cards[] = {{I_IMPORT, -1, MENU_IMPORT, T_IMPORT}, {I_PLAY, -1, A_NEW, T_NEW}};
static const Card card_cards[] = {{I_EXPORT, -1, MENU_EXPORT, T_EXPORT}, {I_IMPORT, -1, MENU_IMPORT, T_IMPORT}};

static const Card *cards(int *n) {
  switch (screen) {
  case S_MAIN: *n = (int)(sizeof main_cards / sizeof *main_cards); return main_cards;
  case S_FIRST: *n = 2; return mode_cards;
  case S_PADCHECK: *n = 2; return check_cards;
  case S_CARD: *n = 2; return card_cards;
  case S_RESTORE: *n = 2; return restore_cards;
  case S_SETTINGS: *n = 1; return settings_cards;
  case S_SCALE: *n = scale_count; return scale_cards;
  }
  *n = 0; return NULL;
}

static int header(void) {
  switch (screen) {
  case S_PADCHECK: return I_GAMEPAD;
  case S_CARD: case S_RESTORE: return I_CARD;
  case S_SETTINGS: return I_GEAR;
  case S_SCALE: return I_SCREEN;
  }
  return -1;
}

static void go(int s) {
  screen = s; focus = 0; touched = -3;
  if (s == S_RESTORE || s == S_CARD) card_screen = s;
  if (s == S_SCALE) for (int i = 0; i < scale_count; i++) if (scale_cards[i].action == A_SCALE + scale_now) focus = i;
}

void menu_set_scales(const int *scales, int n, int now) {
  static const struct { int scale, card, word; } names[] = {
    {1, T_1X, T_ORIGINAL}, {2, T_2X, T_480P}, {3, T_3X, T_720P}, {4, T_4X, T_960P}, {6, T_6X, T_1440P}, {8, T_8X, T_1920P}};
  scale_count = 0; scale_now = now;
  for (int i = 0; i < n && scale_count < 8; i++)
    for (size_t j = 0; j < sizeof names / sizeof *names; j++)
      if (names[j].scale == scales[i])
        scale_cards[scale_count++] = (Card){names[j].card, -1, A_SCALE + scales[i], names[j].word};
}

static void open_at(int s) { menu_open = true; prev = 0xFFFF; fire = fire_back = false; go(s); }
void menu_show_first(bool ask_card) {
  first = true; open_at(ask_card ? S_RESTORE : S_FIRST);
}
/* after the new install's card question: the controls question, unless the player already answered it */
static void after_restore(void) {
  card_screen = S_CARD;
  if (controls_mode == MODE_UNSET) go(S_FIRST);
  else { menu_open = false; first = false; }
}
void menu_show(void) { first = false; card_screen = S_CARD; open_at(S_MAIN); }
static void close_menu(void) { menu_open = false; first = false; }

void menu_back(void) {
  switch (screen) {
  case S_MAIN: close_menu(); break;
  case S_CARD: case S_SETTINGS: go(S_MAIN); break;
  case S_SCALE: go(S_SETTINGS); break;
  case S_PADCHECK: go(first ? S_FIRST : S_MAIN); break;
  case S_DROP: go(card_screen); break;
  }
}

void menu_result(int r) {
  if (r < 0) { go(card_screen); return; }
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

static bool has_back(void) { return screen != S_RESULT && screen != S_WAIT && screen != S_FIRST && screen != S_RESTORE; }

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
  case A_CONTROLS: go(S_PADCHECK); return MENU_NONE;
  case A_CARD: go(S_CARD); return MENU_NONE;
  case A_CHECK: close_menu(); return MENU_NONE;
  case A_NEW: after_restore(); return MENU_NONE;
  case A_SETTINGS: go(S_SETTINGS); return MENU_NONE;
  case A_RESOLUTION: go(S_SCALE); return MENU_NONE;
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
  if (c[i].action >= A_SCALE) {   /* a resolution: back to the game, to see it */
    menu_scale = scale_now = c[i].action - A_SCALE; close_menu(); return MENU_SCALE;
  }
  return MENU_NONE;
}

int menu_frame(uint16_t bits) {
  uint16_t edge = bits & ~prev;
  prev = bits;
  if (screen == S_RESULT) {
    if (SDL_GetTicks() - result_at > 1300) {
      if (!result_ok) go(card_screen);
      else if (card_screen == S_RESTORE) after_restore();
      else close_menu();
    }
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
    overlay_quad(result_ok ? I_CHECK : I_FAIL, ww / 2.0f, wh * 0.45f, 0.4f * s, 0.4f * s, 1, 1);
    overlay_text(result_ok ? T_DONE : T_FAILED, ww / 2.0f, wh * 0.45f + 0.27f * s, 0.05f * s, ww * 0.9f, 1, 1);
    return;
  }
  if (screen == S_WAIT) return;
  if (screen == S_DROP) {   /* drop the memory card file on the window */
    overlay_quad(I_CARD, ww / 2.0f - 0.16f * s, wh * 0.5f, 0.3f * s, 0.3f * s, 1, 0.9f);
    overlay_quad(I_DROP, ww / 2.0f + 0.16f * s, wh * 0.5f, 0.36f * s, 0.36f * s, 1, 1);
    overlay_text(T_DROP, ww / 2.0f, wh * 0.5f + 0.27f * s, 0.04f * s, ww * 0.9f, 1, 0.95f);
  }
  if (header() >= 0) overlay_quad(header(), ww / 2.0f, wh * 0.24f, 0.22f * s, 0.22f * s, 1, 0.85f);
  int n; const Card *c = cards(&n);
  /* the words under the cards: one size for all, the largest that keeps each within its card's width */
  float gh = 0.036f * s;
  for (int i = 0; i < n; i++) {
    float cx, cy, size, w;
    card_rect(i, n, ww, wh, &cx, &cy, &size);
    w = overlay_text_width(c[i].word, gh);
    if (w > size * 0.95f) gh *= size * 0.95f / w;
  }
  for (int i = 0; i < n; i++) {
    float cx, cy, size;
    card_rect(i, n, ww, wh, &cx, &cy, &size);
    bool on = i == focus;
    float k = on ? 1.06f : 1, z = size * k;
    overlay_quad(I_PANEL, cx, cy, z, z, 1, on ? 0.8f : 0.5f);
    frame_box(cx, cy, z, z, (on ? 0.012f : 0.006f) * s, on ? 0.95f : 0.35f);
    float bright = on ? 1.1f : 0.8f;
    if (c[i].icon >= T_RESUME) overlay_text(c[i].icon, cx, cy, z * 0.3f, z * 0.8f, bright, 1);   /* a word as the picture */
    else if (c[i].icon2 < 0) overlay_quad(c[i].icon, cx, cy, z * 0.7f, z * 0.7f, bright, 1);
    else {
      overlay_quad(c[i].icon, cx, cy - z * 0.17f, z * 0.58f, z * 0.58f, bright, 1);
      overlay_quad(c[i].icon2, cx, cy + z * 0.24f, z * 0.46f, z * 0.46f, bright, 1);
    }
    if (c[i].action == A_SCALE + scale_now)   /* the resolution in use */
      overlay_quad(I_CHECK, cx + z * 0.36f, cy - z * 0.36f, z * 0.3f, z * 0.3f, 1, 1);
    /* the word under the card */
    overlay_text(c[i].word, cx, cy + size * 0.53f + 0.03f * s + gh / 2, gh, size, on ? 1.1f : 0.8f, 1);
  }
  if (screen == S_MAIN)   /* the version, small, at the bottom */
    overlay_text(T_VERSION, ww / 2.0f, wh - 0.04f * s, 0.022f * s, ww * 0.9f, 0.7f, 0.8f);
  if (has_back()) {
    float cx, cy, size;
    back_rect(ww, wh, &cx, &cy, &size);
    overlay_quad(I_BACK, cx, cy, size, size, 1, 0.8f);
  }
}
