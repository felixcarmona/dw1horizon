/* Horizon Play's menu (docs/player.md). SELECT and START together (or the touch pad's menu button) pause the game
 * and show big pictures, each with a word in English under it:
 *
 *   play            back to the game
 *   controls        controller or keyboard (a tap or a click anywhere shows the touch pad):
 *                     controller  keep the buttons or set them (controls.c)
 *                     keyboard    a PlayStation controller drawn with each button's key, and the layouts RETROARCH,
 *                                 DUCKSTATION, EPSXE (the picture shows the focused one's keys) and CUSTOM: each
 *                                 button in turn asks for its key; a tap, a click or the arrows and confirm on one
 *                                 button set that one alone
 *   memory card     export (a file picker on Android, the save folder opened on a computer) or import (a file
 *                   picker, or a file dropped on the window); the card in use is backed up first
 *   gear            settings: resolution (the core's internal resolution scale, settings.txt)
 *   power           quit
 *
 * When a newer release is out, a screen says so once at start (NEW VERSION V0.0.11 AT DW1HORIZON.COM) with two
 * cards: download (the website opens) and later (back to the game).
 *
 * Nothing is asked about the controls before the game. On Android a new install with no memory
 * card first offers to import one (the copy HorizonActivity keeps in Documents) or to start a new game. The pictures
 * are chosen with a tap or the mouse, or with the pad's arrows and Cross, Circle or START; Triangle goes back.
 */
#include "menu.h"
#include "overlay.h"
#include "controls.h"
#include <math.h>
#include <stdio.h>
#include <string.h>
#include "libretro.h"

bool menu_open;

enum { S_RESTORE, S_MAIN, S_PADCHECK, S_CARD, S_WAIT, S_DROP, S_RESULT, S_SETTINGS, S_SCALE, S_TSIZE, S_TALPHA, S_UPDATE,
       S_CONTROLS, S_LAYOUT, S_KEYS };
static int screen, focus, result_ok, touched = -3;
static Uint32 result_at;
static bool first;            /* the new install's card question: no way back, the game waits for an answer */
static bool fire, fire_back;  /* a tap or click to act on in the next frame */
static int fire_card;
static int card_screen;   /* where the memory card's screens return to: S_CARD, or S_RESTORE */
static uint16_t prev;
static bool capturing, capture_chain;
static int asked;   /* the button whose key was asked for last */   /* S_KEYS: a key is being asked for (and then the next button's) */

typedef struct { int icon, icon2, action, word; } Card;
enum { A_CONTINUE = 100, A_CONTROLS, A_CARD, A_CHECK, A_NEW, A_SETTINGS, A_RESOLUTION, A_TSIZE, A_TALPHA,
       A_CONTROLLER, A_KEYBOARD, A_CUSTOM, A_PRESET /* + KEYS_ */,
       A_SCALE = 200 /* + N */, A_SIZE = 300 /* + percent */, A_ALPHA = 500 /* + percent */ };
static const Card main_cards[] = {{I_PLAY, -1, A_CONTINUE, T_RESUME}, {I_GAMEPAD, I_KEYBOARD, A_CONTROLS, T_CONTROLS},
                                  {I_CARD, -1, A_CARD, T_CARD}, {I_GEAR, -1, A_SETTINGS, T_SETTINGS},
                                  {I_POWER, -1, MENU_QUIT, T_QUIT}};
/* the touch pad's cards only where there is a touch screen */
static const Card settings_cards[] = {{I_SCREEN, -1, A_RESOLUTION, T_RESOLUTION}, {I_CROSS, -1, A_TSIZE, T_BUTTON_SIZE},
                                      {I_CROSS, -1, A_TALPHA, T_OPACITY}};
/* the touch pad's choices: each card shows a button at that size or opacity */
static const Card tsize_cards[] = {{I_CROSS, -1, A_SIZE + 75, T_SMALL}, {I_CROSS, -1, A_SIZE + 100, T_MEDIUM},
                                   {I_CROSS, -1, A_SIZE + 115, T_LARGE}, {I_CROSS, -1, A_SIZE + 130, T_HUGE}};
static const Card talpha_cards[] = {{I_CROSS, -1, A_ALPHA + 25, T_FAINT}, {I_CROSS, -1, A_ALPHA + 50, T_LIGHT},
                                    {I_CROSS, -1, A_ALPHA + 75, T_SOLID}, {I_CROSS, -1, A_ALPHA + 100, T_FULL}};
/* the resolution's choices: the card shows the scale (a word), the word under it the picture's height */
static Card scale_cards[8];
static int scale_count, scale_now;
int menu_scale;
/* no TOUCH card: a tap anywhere brings the touch pad up */
static const Card mode_cards[] = {{I_GAMEPAD, -1, A_CONTROLLER, T_CONTROLLER}, {I_KEYBOARD, -1, A_KEYBOARD, T_KEYBOARD}};
/* the keyboard's layouts: the word is the card */
static const Card layout_cards[] = {{T_RETROARCH, -1, A_PRESET + KEYS_RETROARCH, -1},
                                    {T_DUCKSTATION, -1, A_PRESET + KEYS_DUCKSTATION, -1},
                                    {T_EPSXE, -1, A_PRESET + KEYS_EPSXE, -1}, {T_CUSTOM, -1, A_CUSTOM, -1}};
static const Card check_cards[] = {{I_CHECK, -1, A_CHECK, T_KEEP}, {I_PENCIL, -1, MENU_SETUP, T_SET}};
static const Card restore_cards[] = {{I_IMPORT, -1, MENU_IMPORT, T_IMPORT}, {I_PLAY, -1, A_NEW, T_NEW}};
static const Card update_cards[] = {{I_IMPORT, -1, MENU_UPDATE, T_DOWNLOAD}, {I_PLAY, -1, A_CONTINUE, T_LATER}};
static const Card card_cards[] = {{I_EXPORT, -1, MENU_EXPORT, T_EXPORT}, {I_IMPORT, -1, MENU_IMPORT, T_IMPORT}};

static const Card *cards(int *n) {
  switch (screen) {
  case S_MAIN: *n = (int)(sizeof main_cards / sizeof *main_cards); return main_cards;
  case S_CONTROLS: *n = 2; return mode_cards;
  case S_LAYOUT: *n = 4; return layout_cards;
  case S_PADCHECK: *n = 2; return check_cards;
  case S_CARD: *n = 2; return card_cards;
  case S_RESTORE: *n = 2; return restore_cards;
  case S_UPDATE: *n = 2; return update_cards;
  case S_SETTINGS: *n = SDL_GetNumTouchDevices() > 0 || touch_shown ? 3 : 1; return settings_cards;
  case S_TSIZE: *n = 4; return tsize_cards;
  case S_TALPHA: *n = 4; return talpha_cards;
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
  case S_TSIZE: case S_TALPHA: return I_TOUCH;
  }
  return -1;
}

/* the screens with a line of their own at the top instead of a picture */
static bool has_banner(void) { return screen == S_UPDATE; }

static void go(int s) {
  screen = s; focus = 0; touched = -3;
  if (s == S_RESTORE || s == S_CARD) card_screen = s;
  if (s == S_LAYOUT) { int p = controls_key_preset(); focus = p >= 0 ? p : 3; }
  if (s == S_SCALE) for (int i = 0; i < scale_count; i++) if (scale_cards[i].action == A_SCALE + scale_now) focus = i;
  for (int i = 0; i < 4; i++) {
    if (s == S_TSIZE && tsize_cards[i].action == A_SIZE + overlay_touch_size) focus = i;
    if (s == S_TALPHA && talpha_cards[i].action == A_ALPHA + overlay_touch_alpha) focus = i;
  }
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
  first = true; open_at(ask_card ? S_RESTORE : S_CONTROLS);
}
/* after the new install's card question: the game */
static void after_restore(void) {
  card_screen = S_CARD;
  menu_open = false; first = false;
}
void menu_show(void) { first = false; card_screen = S_CARD; open_at(S_MAIN); }
void menu_show_update(void) { first = false; card_screen = S_CARD; open_at(S_UPDATE); }
static void close_menu(void) { menu_open = false; first = false; }

void menu_back(void) {
  switch (screen) {
  case S_MAIN: case S_UPDATE: close_menu(); break;
  case S_CARD: case S_SETTINGS: go(S_MAIN); break;
  case S_SCALE: case S_TSIZE: case S_TALPHA: go(S_SETTINGS); break;
  case S_CONTROLS: go(S_MAIN); break;
  case S_PADCHECK: case S_LAYOUT: {   /* back to the card that was chosen */
    int card = screen == S_LAYOUT ? 1 : 0;
    go(S_CONTROLS); focus = card;
    break;
  }
  case S_KEYS:   /* a key being asked for: not any more; else back to the layouts */
    if (capturing) { controls_capture_stop(); capturing = false; prev = 0xFFFF; }
    else go(S_LAYOUT);
    break;
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

static void card_rect(int i, int n, int ww, int wh, float *cx, float *cy, float *w, float *h) {
  float s = S(ww, wh), gap = 0.05f * s;
  if (screen == S_LAYOUT) {   /* low, wide cards under the controller */
    gap = 0.035f * s;
    *w = fminf(0.28f * s, (ww - gap * (n + 1)) / n); *h = 0.11f * s;
    *cx = ww / 2.0f + (i - (n - 1) / 2.0f) * (*w + gap);
    *cy = wh - 0.11f * s;
    return;
  }
  float cs = fminf(0.36f * s, (ww - gap * (n + 1)) / n);
  *w = *h = cs;
  *cx = ww / 2.0f + (i - (n - 1) / 2.0f) * (cs + gap);
  *cy = header() >= 0 || has_banner() ? wh * 0.6f : wh * 0.5f;
}

/* the controller picture of the keyboard and Cross screens: as wide as fits above the cards */
static void pad_rect(int ww, int wh, float *cx, float *cy, float *w) {
  float s = S(ww, wh), top = 0.05f * s, bottom = wh - 0.21f * s;
  *w = fminf(ww * 0.92f, 1.2f * s);
  if (*w * PAD_RATIO > bottom - top) *w = (bottom - top) / PAD_RATIO;
  *cx = ww / 2.0f; *cy = (top + bottom) / 2;
}

static void back_rect(int ww, int wh, float *cx, float *cy, float *size) {
  float s = S(ww, wh);
  *size = 0.13f * s; *cx = 0.1f * s; *cy = 0.1f * s;
}

static bool has_back(void) { return screen != S_RESULT && screen != S_WAIT && screen != S_RESTORE; }

/* which card is at (x, y): its index, -2 for the back arrow, -1 for none */
static int hit(float x, float y, int ww, int wh) {
  float cx, cy, size;
  if (has_back()) {
    back_rect(ww, wh, &cx, &cy, &size);
    if (fabsf(x - cx) < size * 0.7f && fabsf(y - cy) < size * 0.7f) return -2;
  }
  if (screen == S_KEYS) {   /* a button on the controller */
    float pw; pad_rect(ww, wh, &cx, &cy, &pw);
    return overlay_pad_hit(cx, cy, pw, x, y);
  }
  int n; cards(&n);
  for (int i = 0; i < n; i++) {
    float w, h;
    card_rect(i, n, ww, wh, &cx, &cy, &w, &h);
    if (fabsf(x - cx) < w / 2 && fabsf(y - cy) < h / 2) return i;
  }
  return -1;
}

void menu_event(const SDL_Event *e, int ww, int wh) {
  float x, y; bool down;
  switch (e->type) {
  case SDL_FINGERDOWN: case SDL_FINGERUP:
    if (SDL_GetTouchDeviceType(e->tfinger.touchId) == SDL_TOUCH_DEVICE_INDIRECT_RELATIVE) return;   /* (a trackpad) */
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
  case A_CONTROLS: go(S_CONTROLS); return MENU_NONE;
  case A_CONTROLLER: go(S_PADCHECK); return MENU_PAD;
  case A_KEYBOARD: go(S_LAYOUT); return MENU_PAD;
  case A_CUSTOM:   /* every button in turn */
    go(S_KEYS); controls_capture_key(0, true); capturing = capture_chain = true; asked = 0; return MENU_NONE;
  case A_CARD: go(S_CARD); return MENU_NONE;
  case A_CHECK: close_menu(); return MENU_NONE;
  case A_NEW: after_restore(); return MENU_NONE;
  case A_SETTINGS: go(S_SETTINGS); return MENU_NONE;
  case A_RESOLUTION: go(S_SCALE); return MENU_NONE;
  case A_TSIZE: go(S_TSIZE); return MENU_NONE;
  case A_TALPHA: go(S_TALPHA); return MENU_NONE;
  case MENU_TOUCH: close_menu(); return MENU_TOUCH;
  case MENU_SETUP: close_menu(); return MENU_SETUP;
  case MENU_QUIT: close_menu(); return MENU_QUIT;
  case MENU_UPDATE: close_menu(); return MENU_UPDATE;
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
  if (c[i].action >= A_PRESET && c[i].action < A_PRESET + KEY_PRESETS) {   /* a keyboard layout: in use at once, */
    controls_set_keys(key_presets[c[i].action - A_PRESET]);               /* the screen stays (its tick moves); */
    return MENU_NONE;                                                      /* the back arrow leaves */
  }
  if (c[i].action >= A_ALPHA) {   /* the touch pad's look: back to the game, to see it */
    overlay_touch_alpha = c[i].action - A_ALPHA; touch_shown = true; close_menu(); return MENU_TOUCHPAD;
  }
  if (c[i].action >= A_SIZE) {
    overlay_touch_size = c[i].action - A_SIZE; touch_shown = true; close_menu(); return MENU_TOUCHPAD;
  }
  if (c[i].action >= A_SCALE) {   /* a resolution: back to the game, to see it */
    menu_scale = scale_now = c[i].action - A_SCALE; close_menu(); return MENU_SCALE;
  }
  return MENU_NONE;
}

/* the CUSTOM keys screen: while a key is asked for the keyboard is not the menu's; otherwise the arrows pick a button
 * and confirm asks for its key */
static int keys_frame(uint16_t edge) {
  if (fire) {   /* a button tapped or clicked: that one alone */
    fire = false; focus = fire_card;
    controls_capture_key(fire_card, false); capturing = true; capture_chain = false; asked = fire_card;
    return MENU_NONE;
  }
  if (capturing) {
    int before = key_capture;
    controls_capture_left();   /* (ten seconds end it) */
    if (key_capture >= 0) { focus = asked = key_capture; prev = 0xFFFF; return MENU_NONE; }
    capturing = false; prev = 0xFFFF;   /* the key just pressed is not a menu press */
    bool timed_out = before >= 0;
    if (!timed_out && capture_chain && asked == CONTROL_COUNT - 1 && first) close_menu();   /* all set: the game */
    return MENU_NONE;
  }
#define E(b) (edge & (1u << RETRO_DEVICE_ID_JOYPAD_##b))
  if ((E(LEFT) || E(UP)) && focus > 0) focus--;
  if ((E(RIGHT) || E(DOWN)) && focus < CONTROL_COUNT - 1) focus++;
  if (E(B) || E(A) || E(START)) { controls_capture_key(focus, false); capturing = true; capture_chain = false; asked = focus; }
  else if (E(X)) menu_back();
#undef E
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
  if (screen == S_KEYS) return keys_frame(edge);
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
static const char *const button_names[CONTROL_COUNT] = {"UP", "DOWN", "LEFT", "RIGHT", "CROSS", "CIRCLE", "SQUARE",
                                                        "TRIANGLE", "L1", "R1", "L2", "R2", "SELECT", "START"};

static void time_bar(float cx, float y, float w, float left, float s) {
  overlay_quad(I_WHITE, cx, y, w, 0.008f * s, 1, 0.15f);
  overlay_quad(I_WHITE, cx - w / 2 + w * left / 2, y, w * left, 0.008f * s, 1, 0.7f);
}

/* the screens with the PlayStation controller: the keyboard's layouts and its own keys */
static void draw_pad_screen(int ww, int wh) {
  float s = S(ww, wh), cx, cy, pw;
  pad_rect(ww, wh, &cx, &cy, &pw);
  float hy = wh - 0.13f * s, gh = 0.036f * s;   /* the line under it */
  /* the keys: a layout's (the focused card's) or the ones in use */
  SDL_Scancode keys[CONTROL_COUNT][2];
  if (screen == S_LAYOUT && focus < KEY_PRESETS) memcpy(keys, key_presets[focus], sizeof keys);
  else controls_keys(keys);
  static char text[CONTROL_COUNT][2][24];
  const char *labels[CONTROL_COUNT][2];
  for (int i = 0; i < CONTROL_COUNT; i++)
    for (int k = 0; k < 2; k++) { controls_key_label(keys[i][k], text[i][k], sizeof text[i][k]); labels[i][k] = text[i][k]; }
  int lit = screen == S_KEYS ? (capturing && key_capture >= 0 ? key_capture : focus) : -1;
  overlay_pad(cx, cy, pw, lit, labels, 1);
  if (screen != S_KEYS) return;
  char line[64];
  if (capturing && key_capture >= 0) snprintf(line, sizeof line, "PRESS A KEY FOR %s", button_names[key_capture]);
  else snprintf(line, sizeof line, "CHOOSE A BUTTON TO CHANGE ITS KEY");
  overlay_string(line, ww / 2.0f, hy, gh, ww * 0.9f, 1.1f, 1);
  if (capturing && key_capture >= 0) time_bar(ww / 2.0f, hy + 0.07f * s, 0.6f * s, controls_capture_left(), s);
}

static void frame_box(float cx, float cy, float w, float h, float t, float alpha) {
  overlay_quad(I_WHITE, cx, cy - h / 2, w, t, 1, alpha);
  overlay_quad(I_WHITE, cx, cy + h / 2, w, t, 1, alpha);
  overlay_quad(I_WHITE, cx - w / 2, cy, t, h + t, 1, alpha);
  overlay_quad(I_WHITE, cx + w / 2, cy, t, h + t, 1, alpha);
}

void menu_draw(int ww, int wh) {
  float s = S(ww, wh);
  bool solid = screen == S_LAYOUT || screen == S_KEYS;
  overlay_quad(I_PANEL, ww / 2.0f, wh / 2.0f, (float)ww, (float)wh, 1, solid ? 0.92f : 0.75f);
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
  if (screen == S_LAYOUT || screen == S_KEYS) draw_pad_screen(ww, wh);
  if (has_banner()) overlay_draw_new_version(ww / 2.0f, wh * 0.24f, fminf(0.04f * s, ww * 0.9f / 33), 1);
  if (header() >= 0) overlay_quad(header(), ww / 2.0f, wh * 0.24f, 0.22f * s, 0.22f * s, 1, 0.85f);
  int n; const Card *c = cards(&n);
  /* the words under the cards: one size for all, the largest that keeps each within its card's width */
  float gh = 0.036f * s;
  for (int i = 0; i < n; i++) {
    float cx, cy, size, h, w;
    card_rect(i, n, ww, wh, &cx, &cy, &size, &h);
    w = overlay_text_width(c[i].word, gh);
    if (w > size * 0.95f) gh *= size * 0.95f / w;
  }
  for (int i = 0; i < n; i++) {
    float cx, cy, size, h;
    card_rect(i, n, ww, wh, &cx, &cy, &size, &h);
    bool on = i == focus;
    float k = on ? 1.06f : 1, z = size * k, zh = h * k;
    overlay_quad(I_PANEL, cx, cy, z, zh, 1, on ? 0.8f : 0.5f);
    frame_box(cx, cy, z, zh, (on ? 0.012f : 0.006f) * s, on ? 0.95f : 0.35f);
    float bright = on ? 1.1f : 0.8f;
    if (screen == S_LAYOUT) {   /* a layout's name as the card (one size for all), a tick on the one in use */
      float lh = h * 0.3f;
      for (int j = 0; j < n; j++) lh = fminf(lh, size * 0.84f * lh / fmaxf(overlay_text_width(c[j].icon, lh), 1));
      overlay_text(c[i].icon, cx, cy, lh * k, z * 0.9f, bright, 1);
      if (c[i].action == A_PRESET + controls_key_preset())
        overlay_quad(I_CHECK, cx + z * 0.5f - zh * 0.05f, cy - zh * 0.5f + zh * 0.05f, zh * 0.9f, zh * 0.9f, 1, 1);   /* big, on the corner */
      continue;
    }
    if (c[i].icon >= T_RESUME) overlay_text(c[i].icon, cx, cy, z * 0.3f, z * 0.8f, bright, 1);   /* a word as the picture */
    else if (c[i].action >= A_ALPHA) overlay_quad(c[i].icon, cx, cy, z * 0.5f, z * 0.5f, 1, (c[i].action - A_ALPHA) / 100.0f);
    else if (c[i].action >= A_SIZE) {
      float k = z * 0.5f * (c[i].action - A_SIZE) / 100.0f;
      overlay_quad(c[i].icon, cx, cy, k, k, bright, overlay_touch_alpha / 100.0f);
    }
    else if (c[i].action == A_TALPHA) overlay_quad(c[i].icon, cx, cy, z * 0.6f, z * 0.6f, 1, 0.35f);
    else if (c[i].icon2 < 0) overlay_quad(c[i].icon, cx, cy, z * 0.7f, z * 0.7f, bright, 1);
    else {
      overlay_quad(c[i].icon, cx, cy - z * 0.17f, z * 0.58f, z * 0.58f, bright, 1);
      overlay_quad(c[i].icon2, cx, cy + z * 0.24f, z * 0.46f, z * 0.46f, bright, 1);
    }
    if (c[i].action == A_SCALE + scale_now || c[i].action == A_SIZE + overlay_touch_size
        || c[i].action == A_ALPHA + overlay_touch_alpha)   /* the choice in use */
      overlay_quad(I_CHECK, cx + z * 0.36f, cy - z * 0.36f, z * 0.3f, z * 0.3f, 1, 1);
    /* the word under the card */
    overlay_text(c[i].word, cx, cy + size * 0.53f + 0.03f * s + gh / 2, gh, size, on ? 1.1f : 0.8f, 1);
  }
  if (screen == S_MAIN) {   /* the version, small, at the bottom, and a newer release above it */
    overlay_text(T_VERSION, ww / 2.0f, wh - 0.04f * s, 0.022f * s, ww * 0.9f, 0.7f, 0.8f);
    overlay_draw_new_version(ww / 2.0f, wh - 0.1f * s, 0.026f * s, 1);
  }
  if (has_back()) {
    float cx, cy, size;
    back_rect(ww, wh, &cx, &cy, &size);
    overlay_quad(I_BACK, cx, cy, size, size, 1, 0.8f);
  }
}
