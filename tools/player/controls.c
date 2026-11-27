/* Horizon Play's buttons (docs/player.md): which key or controller input presses which PlayStation button, and the
 * setup screen that changes it. The setup is opened from Horizon Play's menu (SELECT and START together): the screen
 * shows each PlayStation button in turn and the player presses the one they want for it, on the controller or the
 * keyboard. Nothing pressed for ten seconds leaves the buttons as they were.
 *
 * Controllers SDL knows (Xbox, PlayStation, Switch, 8BitDo, Android handhelds...) are read by position. Any other
 * joystick (a generic USB pad, an arcade stick) is read by its raw buttons, hats and axes, with the common USB
 * PlayStation adapter's layout until the setup sets it.
 *
 * The keyboard also has three ready layouts (key_presets: RetroArch, DuckStation, ePSXe), chosen from the menu's
 * keyboard screen, and a capture of one key for one button (controls_capture_key) for its CUSTOM screen. SDL reports
 * one Android handheld's built-in controller (USB 2022:3001) with both face pairs and SELECT/START swapped, so it gets
 * its own defaults while controls.txt has no "pad" lines (handheld_defaults).
 *
 * Everything is kept in controls.txt in the save folder, one line per button ("pad cross=a", "key cross=Z",
 * "joy cross=b2", "joy up=h0.1", "joy up=a1-"), plus "mode touch" or "mode pad", so it can also be edited by hand.
 */
#include "controls.h"
#include <stdio.h>
#include <string.h>
#include "libretro.h"

#define N CONTROL_COUNT
static const char *names[N] = {"up", "down", "left", "right", "cross", "circle", "square", "triangle",
                               "l1", "r1", "l2", "r2", "select", "start"};
const int control_ids[N] = {
  RETRO_DEVICE_ID_JOYPAD_UP, RETRO_DEVICE_ID_JOYPAD_DOWN, RETRO_DEVICE_ID_JOYPAD_LEFT, RETRO_DEVICE_ID_JOYPAD_RIGHT,
  RETRO_DEVICE_ID_JOYPAD_B, RETRO_DEVICE_ID_JOYPAD_A, RETRO_DEVICE_ID_JOYPAD_Y, RETRO_DEVICE_ID_JOYPAD_X,
  RETRO_DEVICE_ID_JOYPAD_L, RETRO_DEVICE_ID_JOYPAD_R, RETRO_DEVICE_ID_JOYPAD_L2, RETRO_DEVICE_ID_JOYPAD_R2,
  RETRO_DEVICE_ID_JOYPAD_SELECT, RETRO_DEVICE_ID_JOYPAD_START,
};

int controls_mode;
bool controls_menu_asked;
bool controls_setup_wanted;
static char joy_set_up[33];   /* the GUID of the joystick the "joy" buttons were set up on ("joy device=") */

/* a known controller's input: a button (0..), or a trigger as AXIS + its axis */
#define AXIS 100
/* another joystick's input: a button (0..), a hat direction (HAT + hat * 16 + SDL_HAT_UP...), or an axis pushed one
 * way (JAXIS + axis * 2 + 1 for negative) */
#define HAT 1000
#define JAXIS 2000
static int pad_map[N], joy_map[N];
static bool pad_lines_seen;   /* controls.txt has the controller's buttons (handheld_defaults) */
static SDL_Scancode key_map[N][2];

/* the keyboard layouts the player can pick (menu.c): RetroArch's (the default), DuckStation's and ePSXe's.
 * DuckStation binds its D-pad to the arrows and its left stick to W/A/S/D (src/util/input_manager.cpp); here both
 * move the D-pad. */
const SDL_Scancode key_presets[KEY_PRESETS][N][2] = {
  [KEYS_RETROARCH] = {
    {SDL_SCANCODE_UP}, {SDL_SCANCODE_DOWN}, {SDL_SCANCODE_LEFT}, {SDL_SCANCODE_RIGHT},
    {SDL_SCANCODE_Z}, {SDL_SCANCODE_X}, {SDL_SCANCODE_A}, {SDL_SCANCODE_S},
    {SDL_SCANCODE_Q}, {SDL_SCANCODE_W}, {SDL_SCANCODE_E}, {SDL_SCANCODE_R},
    {SDL_SCANCODE_BACKSPACE, SDL_SCANCODE_RSHIFT}, {SDL_SCANCODE_RETURN},
  },
  [KEYS_DUCKSTATION] = {
    {SDL_SCANCODE_UP, SDL_SCANCODE_W}, {SDL_SCANCODE_DOWN, SDL_SCANCODE_S}, {SDL_SCANCODE_LEFT, SDL_SCANCODE_A},
    {SDL_SCANCODE_RIGHT, SDL_SCANCODE_D},
    {SDL_SCANCODE_K}, {SDL_SCANCODE_L}, {SDL_SCANCODE_J}, {SDL_SCANCODE_I},
    {SDL_SCANCODE_Q}, {SDL_SCANCODE_E}, {SDL_SCANCODE_1}, {SDL_SCANCODE_3},
    {SDL_SCANCODE_BACKSPACE}, {SDL_SCANCODE_RETURN},
  },
  [KEYS_EPSXE] = {   /* ePSXe's own defaults (its docs/ePSXe_en.txt) */
    {SDL_SCANCODE_UP}, {SDL_SCANCODE_DOWN}, {SDL_SCANCODE_LEFT}, {SDL_SCANCODE_RIGHT},
    {SDL_SCANCODE_Z}, {SDL_SCANCODE_X}, {SDL_SCANCODE_S}, {SDL_SCANCODE_D},
    {SDL_SCANCODE_W}, {SDL_SCANCODE_E}, {SDL_SCANCODE_Q}, {SDL_SCANCODE_R},
    {SDL_SCANCODE_C}, {SDL_SCANCODE_V},
  },
};

static void defaults(void) {
  static const int pad[N] = {
    SDL_CONTROLLER_BUTTON_DPAD_UP, SDL_CONTROLLER_BUTTON_DPAD_DOWN, SDL_CONTROLLER_BUTTON_DPAD_LEFT,
    SDL_CONTROLLER_BUTTON_DPAD_RIGHT,
    SDL_CONTROLLER_BUTTON_A, SDL_CONTROLLER_BUTTON_B, SDL_CONTROLLER_BUTTON_X, SDL_CONTROLLER_BUTTON_Y,  /* by position */
    SDL_CONTROLLER_BUTTON_LEFTSHOULDER, SDL_CONTROLLER_BUTTON_RIGHTSHOULDER,
    AXIS + SDL_CONTROLLER_AXIS_TRIGGERLEFT, AXIS + SDL_CONTROLLER_AXIS_TRIGGERRIGHT,
    SDL_CONTROLLER_BUTTON_BACK, SDL_CONTROLLER_BUTTON_START,
  };
  /* the usual USB adapter for PlayStation pads: Triangle 0, Circle 1, Cross 2, Square 3, L2 4, R2 5, L1 6, R1 7,
   * SELECT 8, START 9, the pad on hat 0 (or on axes 0 and 1, which always move too) */
  static const int joy[N] = {HAT + SDL_HAT_UP, HAT + SDL_HAT_DOWN, HAT + SDL_HAT_LEFT, HAT + SDL_HAT_RIGHT,
                             2, 1, 3, 0, 6, 7, 4, 5, 8, 9};
  memcpy(pad_map, pad, sizeof pad_map);
  memcpy(joy_map, joy, sizeof joy_map);
  memcpy(key_map, key_presets[KEYS_RETROARCH], sizeof key_map);
}

static int joy_parse(const char *v) {
  int a, b; char sign;
  if (sscanf(v, "b%d", &a) == 1 && a >= 0 && a < HAT) return a;
  if (sscanf(v, "h%d.%d", &a, &b) == 2 && a >= 0 && a < 16 && (b == 1 || b == 2 || b == 4 || b == 8)) return HAT + a * 16 + b;
  if (sscanf(v, "a%d%c", &a, &sign) == 2 && a >= 0 && a < 64 && (sign == '+' || sign == '-'))
    return JAXIS + a * 2 + (sign == '-');
  return -1;
}

static void joy_name(int m, char *out, size_t n) {
  if (m >= JAXIS) snprintf(out, n, "a%d%c", (m - JAXIS) / 2, (m - JAXIS) % 2 ? '-' : '+');
  else if (m >= HAT) snprintf(out, n, "h%d.%d", (m - HAT) / 16, (m - HAT) % 16);
  else snprintf(out, n, "b%d", m);
}

static char path[1200];

void controls_load(const char *save_dir) {
  defaults();
  snprintf(path, sizeof path, "%s/controls.txt", save_dir);
  FILE *f = fopen(path, "r");
  if (!f) return;
  char line[200];
  bool key_seen[N] = {0};
  while (fgets(line, sizeof line, f)) {
    char kind[8], name[16], value[64];
    line[strcspn(line, "\r\n")] = 0;
    if (!strcmp(line, "mode touch")) { controls_mode = MODE_TOUCH; continue; }
    if (!strcmp(line, "mode pad")) { controls_mode = MODE_PAD; continue; }
    if (sscanf(line, "%7s %15[^=]=%63[^\n]", kind, name, value) != 3) continue;
    if (!strcmp(kind, "joy") && !strcmp(name, "device")) { snprintf(joy_set_up, sizeof joy_set_up, "%.32s", value); continue; }
    int i = 0;
    while (i < N && strcmp(names[i], name)) i++;
    if (i == N) continue;
    if (!strcmp(kind, "pad")) {
      pad_lines_seen = true;
      SDL_GameControllerButton b = SDL_GameControllerGetButtonFromString(value);
      SDL_GameControllerAxis a = SDL_GameControllerGetAxisFromString(value);
      if (b != SDL_CONTROLLER_BUTTON_INVALID) pad_map[i] = b;
      else if (a == SDL_CONTROLLER_AXIS_TRIGGERLEFT || a == SDL_CONTROLLER_AXIS_TRIGGERRIGHT) pad_map[i] = AXIS + a;
    } else if (!strcmp(kind, "joy")) {
      int m = joy_parse(value);
      if (m >= 0) joy_map[i] = m;
    } else if (!strcmp(kind, "key")) {
      SDL_Scancode sc = SDL_GetScancodeFromName(value);
      if (sc == SDL_SCANCODE_UNKNOWN) continue;
      if (!key_seen[i]) { key_map[i][0] = sc; key_map[i][1] = 0; key_seen[i] = true; }
      else key_map[i][1] = sc;
    }
  }
  fclose(f);
}

static void save(void) {
  char tmp[1210];
  snprintf(tmp, sizeof tmp, "%s.new", path);
  FILE *f = fopen(tmp, "w");
  if (!f) { SDL_Log("controls: cannot write %s", tmp); return; }
  pad_lines_seen = true;
  fprintf(f, "# Horizon Play's buttons. SELECT and START together in the game open the menu that sets them again.\n");
  if (controls_mode) fprintf(f, "mode %s\n", controls_mode == MODE_TOUCH ? "touch" : "pad");
  for (int i = 0; i < N; i++)
    fprintf(f, "pad %s=%s\n", names[i], pad_map[i] >= AXIS ? SDL_GameControllerGetStringForAxis(pad_map[i] - AXIS)
                                                           : SDL_GameControllerGetStringForButton(pad_map[i]));
  if (joy_set_up[0]) fprintf(f, "joy device=%s\n", joy_set_up);
  for (int i = 0; i < N; i++) {
    char v[16]; joy_name(joy_map[i], v, sizeof v);
    fprintf(f, "joy %s=%s\n", names[i], v);
  }
  for (int i = 0; i < N; i++)
    for (int k = 0; k < 2; k++)
      if (key_map[i][k]) fprintf(f, "key %s=%s\n", names[i], SDL_GetScancodeName(key_map[i][k]));
  fclose(f);
  remove(path);
  if (rename(tmp, path)) SDL_Log("controls: cannot write %s", path);
  else SDL_Log("controls: saved %s", path);
}

void controls_set_mode(int mode) { controls_mode = mode; save(); }

/* ---- the controllers ---- */
static SDL_GameController *pads[4];
static SDL_Joystick *joys[4];    /* the joysticks SDL does not know as controllers */

/* an Android handheld's built-in controller (USB 2022:3001) reports its bottom button as SDL's east one, the right as
 * south, left and top swapped the same way, and SELECT and START swapped: measured on the device.
 * Its own layout is the start when controls.txt has no "pad" lines yet. */
static void handheld_defaults(SDL_GameController *c) {
  if (pad_lines_seen || SDL_GameControllerGetVendor(c) != 0x2022 || SDL_GameControllerGetProduct(c) != 0x3001) return;
  pad_map[4] = SDL_CONTROLLER_BUTTON_B; pad_map[5] = SDL_CONTROLLER_BUTTON_A;
  pad_map[6] = SDL_CONTROLLER_BUTTON_Y; pad_map[7] = SDL_CONTROLLER_BUTTON_X;
  pad_map[12] = SDL_CONTROLLER_BUTTON_START; pad_map[13] = SDL_CONTROLLER_BUTTON_BACK;
  SDL_Log("controller: USB 2022:3001, the handheld's own layout");
}

static void add_device(int index) {
  if (SDL_IsGameController(index)) {
    SDL_JoystickID id = SDL_JoystickGetDeviceInstanceID(index);
    for (int i = 0; i < 4; i++)
      if (pads[i] && SDL_JoystickInstanceID(SDL_GameControllerGetJoystick(pads[i])) == id) return;
    for (int i = 0; i < 4; i++)
      if (!pads[i]) {
        pads[i] = SDL_GameControllerOpen(index);
        if (!pads[i]) return;
        SDL_Log("controller: %s", SDL_GameControllerName(pads[i]));
        handheld_defaults(pads[i]);
        return;
      }
  } else {
    const char *name = SDL_JoystickNameForIndex(index);
    if (name && SDL_strcasestr(name, "accelerometer")) return;   /* a phone's tilt is not a joystick */
    SDL_JoystickID id = SDL_JoystickGetDeviceInstanceID(index);
    for (int i = 0; i < 4; i++) if (joys[i] && SDL_JoystickInstanceID(joys[i]) == id) return;
    for (int i = 0; i < 4; i++)
      if (!joys[i]) {
        joys[i] = SDL_JoystickOpen(index); SDL_Log("joystick: %s", SDL_JoystickName(joys[i]));
        char guid[33]; SDL_JoystickGetGUIDString(SDL_JoystickGetGUID(joys[i]), guid, sizeof guid);
        if (strcmp(guid, joy_set_up)) controls_setup_wanted = true;   /* its buttons are asked for */
        return;
      }
  }
}

static void remove_device(SDL_JoystickID id) {
  for (int i = 0; i < 4; i++) {
    if (pads[i] && SDL_JoystickInstanceID(SDL_GameControllerGetJoystick(pads[i])) == id) {
      SDL_GameControllerClose(pads[i]); pads[i] = NULL;
    }
    if (joys[i] && SDL_JoystickInstanceID(joys[i]) == id) { SDL_JoystickClose(joys[i]); joys[i] = NULL; }
  }
}

static bool generic(SDL_JoystickID id) {
  for (int i = 0; i < 4; i++) if (joys[i] && SDL_JoystickInstanceID(joys[i]) == id) return true;
  return false;
}

void controls_open_all(void) {
  for (int i = 0; i < SDL_NumJoysticks(); i++) add_device(i);
}

static uint16_t pad_bits(SDL_GameController *c) {
  uint16_t bits = 0;
  for (int i = 0; i < N; i++) {
    int m = pad_map[i];
    if (m >= AXIS ? SDL_GameControllerGetAxis(c, m - AXIS) > 16000 : SDL_GameControllerGetButton(c, m))
      bits |= 1u << control_ids[i];
  }
  if (SDL_GameControllerGetButton(c, SDL_CONTROLLER_BUTTON_LEFTSTICK)) bits |= 1u << RETRO_DEVICE_ID_JOYPAD_L3;
  if (SDL_GameControllerGetButton(c, SDL_CONTROLLER_BUTTON_RIGHTSTICK)) bits |= 1u << RETRO_DEVICE_ID_JOYPAD_R3;
  /* the left stick also moves: the game uses the digital pad */
  int x = SDL_GameControllerGetAxis(c, SDL_CONTROLLER_AXIS_LEFTX), y = SDL_GameControllerGetAxis(c, SDL_CONTROLLER_AXIS_LEFTY);
  if (x < -16000) bits |= 1u << RETRO_DEVICE_ID_JOYPAD_LEFT;
  if (x > 16000) bits |= 1u << RETRO_DEVICE_ID_JOYPAD_RIGHT;
  if (y < -16000) bits |= 1u << RETRO_DEVICE_ID_JOYPAD_UP;
  if (y > 16000) bits |= 1u << RETRO_DEVICE_ID_JOYPAD_DOWN;
  return bits;
}

static bool joy_down(SDL_Joystick *j, int m) {
  if (m >= JAXIS) {
    int a = (m - JAXIS) / 2;
    if (a >= SDL_JoystickNumAxes(j)) return false;
    int v = SDL_JoystickGetAxis(j, a);
    return (m - JAXIS) % 2 ? v < -16000 : v > 16000;
  }
  if (m >= HAT) {
    int h = (m - HAT) / 16;
    return h < SDL_JoystickNumHats(j) && (SDL_JoystickGetHat(j, h) & ((m - HAT) % 16));
  }
  return m < SDL_JoystickNumButtons(j) && SDL_JoystickGetButton(j, m);
}

static uint16_t joy_bits(SDL_Joystick *j) {
  uint16_t bits = 0;
  for (int i = 0; i < N; i++) if (joy_down(j, joy_map[i])) bits |= 1u << control_ids[i];
  if (SDL_JoystickNumAxes(j) >= 2) {   /* the first two axes move too: a stick, or a pad reported as axes */
    int x = SDL_JoystickGetAxis(j, 0), y = SDL_JoystickGetAxis(j, 1);
    if (x < -16000) bits |= 1u << RETRO_DEVICE_ID_JOYPAD_LEFT;
    if (x > 16000) bits |= 1u << RETRO_DEVICE_ID_JOYPAD_RIGHT;
    if (y < -16000) bits |= 1u << RETRO_DEVICE_ID_JOYPAD_UP;
    if (y > 16000) bits |= 1u << RETRO_DEVICE_ID_JOYPAD_DOWN;
  }
  return bits;
}

uint16_t controls_bits(void) {
  const Uint8 *k = SDL_GetKeyboardState(NULL);
  uint16_t bits = 0;
  for (int i = 0; i < N; i++)
    for (int j = 0; j < 2; j++)
      if (key_map[i][j] && k[key_map[i][j]]) bits |= 1u << control_ids[i];
  for (int i = 0; i < 4; i++) {
    if (pads[i]) bits |= pad_bits(pads[i]);
    if (joys[i]) bits |= joy_bits(joys[i]);
  }
  return bits;
}

/* ---- the setup ---- */
int remap_step = -1;           /* the button being asked for, or -1 */
float remap_time_left;         /* 1 .. 0: how long until it gives up */
static int device;             /* 0 not known yet, 1 controller, 2 keyboard, 3 other joystick */
static bool armed;             /* every button let go since the setup opened */
static int new_pad[N];
static SDL_Scancode new_key[N];
static Uint32 asked_at;
#define WAIT_MS 10000

static void ask(int step) { remap_step = step; asked_at = SDL_GetTicks(); }

void controls_setup_start(void) {
  SDL_Log("controls: setup opened");
  device = 0; armed = false; ask(0);
}

static void finish(bool keep) {
  if (keep) {
    if (device == 1) memcpy(pad_map, new_pad, sizeof pad_map);
    if (device == 3) {
      memcpy(joy_map, new_pad, sizeof joy_map);
      for (int i = 0; i < 4; i++)   /* the joystick it was set up on is not asked about again */
        if (joys[i]) { SDL_JoystickGetGUIDString(SDL_JoystickGetGUID(joys[i]), joy_set_up, sizeof joy_set_up); break; }
    }
    if (device == 2) for (int i = 0; i < N; i++) { key_map[i][0] = new_key[i]; key_map[i][1] = 0; }
    save();
  } else SDL_Log("controls: the setup ended early; the buttons stay as they were");
  remap_step = -1;
}

void controls_setup_cancel(void) { if (remap_step >= 0) finish(false); }

uint16_t controls_frame(uint16_t bits) {
  const uint16_t both = (1u << RETRO_DEVICE_ID_JOYPAD_SELECT) | (1u << RETRO_DEVICE_ID_JOYPAD_START);
  if (remap_step >= 0) {
    if (!armed && !bits) { armed = true; asked_at = SDL_GetTicks(); }
    Uint32 waited = SDL_GetTicks() - asked_at;
    remap_time_left = waited >= WAIT_MS ? 0 : 1 - (float)waited / WAIT_MS;
    if (waited >= WAIT_MS) finish(false);
    return 0;
  }
  /* SELECT and START together open the menu at once; neither reaches the game until both are up. One of them alone
   * is held back for a few frames, in case the other follows, and a quick tap is passed on when it ends. */
  static bool together;
  static int alone, tail;
  static uint16_t alone_bit;
  enum { HOLD = 6 };
  uint16_t sel = bits & both;
  if (sel == both) {
    if (!together) controls_menu_asked = true;
    together = true; alone = 0; tail = 0;
    return bits & ~both;
  }
  if (together) {
    if (sel) return bits & ~both;
    together = false;
  }
  if (sel) {
    if (alone < HOLD) { alone++; alone_bit = sel; return bits & ~both; }
    return bits;
  }
  if (alone > 0 && alone < HOLD) tail = HOLD;
  alone = 0;
  if (tail > 0) { tail--; return bits | alone_bit; }
  return bits;
}

static void pressed(int dev, int pad_input, SDL_Scancode key) {
  if (remap_step < 0 || !armed) return;
  if (device && dev != device) return;
  for (int i = 0; i < remap_step; i++)   /* one input, one button */
    if (dev == 2 ? new_key[i] == key : new_pad[i] == pad_input) return;
  device = dev;
  new_pad[remap_step] = pad_input; new_key[remap_step] = key;
  if (remap_step + 1 == N) finish(true);
  else ask(remap_step + 1);
}

/* ---- the keyboard alone (menu.c): a layout, or one key for one button ---- */
int key_capture = -1;          /* the button whose key is asked for, or -1 */
static bool capture_chain;     /* then the next button, up to START */
static Uint32 capture_at;

void controls_keys(SDL_Scancode out[N][2]) { memcpy(out, key_map, sizeof key_map); }

void controls_set_keys(const SDL_Scancode keys[N][2]) { memcpy(key_map, keys, sizeof key_map); save(); }

int controls_key_preset(void) {
  for (int p = 0; p < KEY_PRESETS; p++)
    if (!memcmp(key_presets[p], key_map, sizeof key_map)) return p;
  return -1;
}

void controls_capture_key(int button, bool chain) {
  key_capture = button; capture_chain = chain; capture_at = SDL_GetTicks();
}

void controls_capture_stop(void) { key_capture = -1; }

float controls_capture_left(void) {
  if (key_capture < 0) return 0;
  Uint32 waited = SDL_GetTicks() - capture_at;
  if (waited >= WAIT_MS) { SDL_Log("controls: no key pressed; the key stays as it was"); key_capture = -1; return 0; }
  return 1 - (float)waited / WAIT_MS;
}

/* the key pressed for the button asked: a key another button had is swapped with this button's own */
static void key_captured(SDL_Scancode sc) {
  int b = key_capture;
  for (int i = 0; i < N; i++)
    for (int k = 0; k < 2; k++)
      if (i != b && key_map[i][k] == sc) {
        key_map[i][k] = key_map[b][0];
        if (!key_map[i][0]) { key_map[i][0] = key_map[i][1]; key_map[i][1] = 0; }
      }
  key_map[b][0] = sc; key_map[b][1] = 0;
  save();
  if (capture_chain && b + 1 < N) controls_capture_key(b + 1, true);
  else key_capture = -1;
}

/* a key's name, short and in capitals, for the controller picture: "Z", "ENTER", "RSHIFT", "KP 1"; the arrow keys
 * are the characters 1 to 4 (up, down, left, right), which overlay.c draws as arrows */
void controls_key_label(SDL_Scancode sc, char *out, size_t n) {
  static const struct { SDL_Scancode sc; const char *s; } short_names[] = {
    {SDL_SCANCODE_RETURN, "ENTER"}, {SDL_SCANCODE_KP_ENTER, "KP ENTER"}, {SDL_SCANCODE_RSHIFT, "RSHIFT"},
    {SDL_SCANCODE_LSHIFT, "LSHIFT"}, {SDL_SCANCODE_RCTRL, "RCTRL"}, {SDL_SCANCODE_LCTRL, "LCTRL"},
    {SDL_SCANCODE_RALT, "RALT"}, {SDL_SCANCODE_LALT, "LALT"}, {SDL_SCANCODE_RGUI, "RGUI"}, {SDL_SCANCODE_LGUI, "LGUI"},
    {SDL_SCANCODE_BACKSPACE, "BACKSPACE"}, {SDL_SCANCODE_CAPSLOCK, "CAPS"}, {SDL_SCANCODE_PAGEUP, "PGUP"},
    {SDL_SCANCODE_PAGEDOWN, "PGDN"}, {SDL_SCANCODE_DELETE, "DEL"}, {SDL_SCANCODE_INSERT, "INS"},
  };
  out[0] = 0;
  if (!sc) return;
  if (sc >= SDL_SCANCODE_RIGHT && sc <= SDL_SCANCODE_UP) {   /* the arrows, drawn as arrows (overlay.c's font) */
    static const char arrows[4] = {'\x04', '\x03', '\x02', '\x01'};   /* right, left, down, up */
    snprintf(out, n, "%c", arrows[sc - SDL_SCANCODE_RIGHT]);
    return;
  }
  for (size_t i = 0; i < sizeof short_names / sizeof *short_names; i++)
    if (short_names[i].sc == sc) { snprintf(out, n, "%s", short_names[i].s); return; }
  const char *name = SDL_GetScancodeName(sc);
  if (!strncmp(name, "Keypad ", 7)) { snprintf(out, n, "KP %s", name + 7); }
  else snprintf(out, n, "%s", name[0] ? name : "?");
  for (char *p = out; *p; p++) *p = (char)SDL_toupper((unsigned char)*p);
}

void controls_event(const SDL_Event *e) {
  static bool trigger_down[SDL_CONTROLLER_AXIS_MAX];
  static Uint8 hat_was[4][16];
  static bool axis_centred[4][64];
  switch (e->type) {
  case SDL_CONTROLLERDEVICEADDED: case SDL_JOYDEVICEADDED: add_device(e->cdevice.which); return;
  case SDL_JOYDEVICEREMOVED: remove_device(e->jdevice.which); return;
  }
  /* a generic joystick's slot, for the hat and axis state the setup keeps */
  int js = -1;
  if (e->type == SDL_JOYAXISMOTION || e->type == SDL_JOYHATMOTION || e->type == SDL_JOYBUTTONDOWN) {
    if (!generic(e->jaxis.which)) return;
    for (int i = 0; i < 4; i++) if (joys[i] && SDL_JoystickInstanceID(joys[i]) == e->jaxis.which) js = i;
  }
  switch (e->type) {
  case SDL_CONTROLLERBUTTONDOWN:
    pressed(1, e->cbutton.button, 0);
    break;
  case SDL_CONTROLLERAXISMOTION:
    if (e->caxis.axis == SDL_CONTROLLER_AXIS_TRIGGERLEFT || e->caxis.axis == SDL_CONTROLLER_AXIS_TRIGGERRIGHT) {
      /* down past 16000, up again below 8000: a trigger resting half way does not repeat */
      bool down = e->caxis.value > 16000;
      if (down && !trigger_down[e->caxis.axis]) pressed(1, AXIS + e->caxis.axis, 0);
    }
    if (e->caxis.axis < SDL_CONTROLLER_AXIS_MAX) trigger_down[e->caxis.axis] = e->caxis.value > 8000;
    break;
  case SDL_JOYBUTTONDOWN:
    pressed(3, e->jbutton.button, 0);
    break;
  case SDL_JOYHATMOTION:
    if (e->jhat.hat < 16) {
      Uint8 v = e->jhat.value, fresh = v & ~hat_was[js][e->jhat.hat];
      hat_was[js][e->jhat.hat] = v;
      for (int b = 1; b <= 8; b <<= 1) if (fresh & b) { pressed(3, HAT + e->jhat.hat * 16 + b, 0); break; }
    }
    break;
  case SDL_JOYAXISMOTION:
    if (e->jaxis.axis < 64) {
      /* pushed far from the middle after passing through it: a trigger resting at one end counts once pressed */
      int v = e->jaxis.value;
      bool *c = &axis_centred[js][e->jaxis.axis];
      if (v > -12000 && v < 12000) *c = true;
      else if (*c && (v > 20000 || v < -20000)) { *c = false; pressed(3, JAXIS + e->jaxis.axis * 2 + (v < 0), 0); }
    }
    break;
  case SDL_KEYDOWN:
    switch (e->key.keysym.scancode) {   /* the keys the program itself uses, and a phone's own keys */
    case SDL_SCANCODE_AC_BACK: case SDL_SCANCODE_F11: case SDL_SCANCODE_ESCAPE: case SDL_SCANCODE_VOLUMEUP:
    case SDL_SCANCODE_VOLUMEDOWN: case SDL_SCANCODE_MUTE: break;
    default:
      if (e->key.repeat) break;
      if (key_capture >= 0) key_captured(e->key.keysym.scancode);
      else pressed(2, 0, e->key.keysym.scancode);
    }
    break;
  }
}
