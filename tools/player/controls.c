/* Horizon Play's buttons (docs/player.md): which key or controller button presses which PlayStation button, and the
 * setup screen that changes it. Holding SELECT and START together for two seconds opens the setup: the screen shows
 * each PlayStation button in turn and the player presses the one they want for it, on the controller or the keyboard.
 * Nothing pressed for ten seconds leaves the buttons as they were. The choice is kept in controls.txt in the save
 * folder, one line per button ("pad cross=a", "key cross=Z"), so it can also be edited by hand.
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

/* a controller input: a button (0..), or a trigger as AXIS + its axis */
#define AXIS 100
static int pad_map[N];
static SDL_Scancode key_map[N][2];

static void defaults(void) {
  static const int pad[N] = {
    SDL_CONTROLLER_BUTTON_DPAD_UP, SDL_CONTROLLER_BUTTON_DPAD_DOWN, SDL_CONTROLLER_BUTTON_DPAD_LEFT,
    SDL_CONTROLLER_BUTTON_DPAD_RIGHT,
    SDL_CONTROLLER_BUTTON_A, SDL_CONTROLLER_BUTTON_B, SDL_CONTROLLER_BUTTON_X, SDL_CONTROLLER_BUTTON_Y,  /* by position */
    SDL_CONTROLLER_BUTTON_LEFTSHOULDER, SDL_CONTROLLER_BUTTON_RIGHTSHOULDER,
    AXIS + SDL_CONTROLLER_AXIS_TRIGGERLEFT, AXIS + SDL_CONTROLLER_AXIS_TRIGGERRIGHT,
    SDL_CONTROLLER_BUTTON_BACK, SDL_CONTROLLER_BUTTON_START,
  };
  static const SDL_Scancode key[N][2] = {
    {SDL_SCANCODE_UP}, {SDL_SCANCODE_DOWN}, {SDL_SCANCODE_LEFT}, {SDL_SCANCODE_RIGHT},
    {SDL_SCANCODE_Z}, {SDL_SCANCODE_X}, {SDL_SCANCODE_A}, {SDL_SCANCODE_S},
    {SDL_SCANCODE_Q}, {SDL_SCANCODE_W}, {SDL_SCANCODE_E}, {SDL_SCANCODE_R},
    {SDL_SCANCODE_BACKSPACE, SDL_SCANCODE_RSHIFT}, {SDL_SCANCODE_RETURN},
  };
  memcpy(pad_map, pad, sizeof pad_map);
  memcpy(key_map, key, sizeof key_map);
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
    if (sscanf(line, "%7s %15[^=]=%63[^\n]", kind, name, value) != 3) continue;
    int i = 0;
    while (i < N && strcmp(names[i], name)) i++;
    if (i == N) continue;
    if (!strcmp(kind, "pad")) {
      SDL_GameControllerButton b = SDL_GameControllerGetButtonFromString(value);
      SDL_GameControllerAxis a = SDL_GameControllerGetAxisFromString(value);
      if (b != SDL_CONTROLLER_BUTTON_INVALID) pad_map[i] = b;
      else if (a == SDL_CONTROLLER_AXIS_TRIGGERLEFT || a == SDL_CONTROLLER_AXIS_TRIGGERRIGHT) pad_map[i] = AXIS + a;
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
  fprintf(f, "# Horizon Play's buttons. Hold SELECT and START for two seconds in the game to set them again.\n");
  for (int i = 0; i < N; i++)
    fprintf(f, "pad %s=%s\n", names[i], pad_map[i] >= AXIS ? SDL_GameControllerGetStringForAxis(pad_map[i] - AXIS)
                                                           : SDL_GameControllerGetStringForButton(pad_map[i]));
  for (int i = 0; i < N; i++)
    for (int k = 0; k < 2; k++)
      if (key_map[i][k]) fprintf(f, "key %s=%s\n", names[i], SDL_GetScancodeName(key_map[i][k]));
  fclose(f);
  remove(path);
  if (rename(tmp, path)) SDL_Log("controls: cannot write %s", path);
  else SDL_Log("controls: saved %s", path);
}

uint16_t controls_keyboard_bits(void) {
  const Uint8 *k = SDL_GetKeyboardState(NULL);
  uint16_t bits = 0;
  for (int i = 0; i < N; i++)
    for (int j = 0; j < 2; j++)
      if (key_map[i][j] && k[key_map[i][j]]) bits |= 1u << control_ids[i];
  return bits;
}

uint16_t controls_pad_bits(SDL_GameController *c) {
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

/* ---- the setup ---- */
int remap_step = -1;           /* the button being asked for, or -1 */
float remap_time_left;         /* 1 .. 0: how long until it gives up */
static int held_frames, device;   /* device: 0 not known yet, 1 controller, 2 keyboard */
static bool armed;             /* every button let go since the setup opened */
static int new_pad[N];
static SDL_Scancode new_key[N];
static Uint32 asked_at;
#define WAIT_MS 10000

static void ask(int step) { remap_step = step; asked_at = SDL_GetTicks(); }

static void finish(bool keep) {
  if (keep) {
    if (device == 1) memcpy(pad_map, new_pad, sizeof pad_map);
    if (device == 2) for (int i = 0; i < N; i++) { key_map[i][0] = new_key[i]; key_map[i][1] = 0; }
    save();
  } else SDL_Log("controls: the setup timed out; the buttons stay as they were");
  remap_step = -1; held_frames = 0;
}

uint16_t controls_frame(uint16_t bits, bool any_down) {
  const uint16_t both = (1u << RETRO_DEVICE_ID_JOYPAD_SELECT) | (1u << RETRO_DEVICE_ID_JOYPAD_START);
  if (remap_step >= 0) {
    if (!armed && !any_down) { armed = true; asked_at = SDL_GetTicks(); }
    Uint32 waited = SDL_GetTicks() - asked_at;
    remap_time_left = waited >= WAIT_MS ? 0 : 1 - (float)waited / WAIT_MS;
    if (waited >= WAIT_MS) finish(false);
    return 0;
  }
  if ((bits & both) == both) {
    if (++held_frames == 120) {
      SDL_Log("controls: setup opened");
      device = 0; armed = false; ask(0);
    }
    return bits & ~both;   /* together they mean nothing in the game: it does not see them */
  }
  held_frames = 0;
  return bits;
}

static void pressed(int dev, int pad_input, SDL_Scancode key) {
  if (remap_step < 0 || !armed) return;
  if (device && dev != device) return;
  for (int i = 0; i < remap_step; i++)   /* one input, one button */
    if (dev == 1 ? new_pad[i] == pad_input : new_key[i] == key) return;
  device = dev;
  new_pad[remap_step] = pad_input; new_key[remap_step] = key;
  if (remap_step + 1 == N) finish(true);
  else ask(remap_step + 1);
}

void controls_event(const SDL_Event *e) {
  static bool trigger_down[SDL_CONTROLLER_AXIS_MAX];
  if (remap_step < 0) {
    if (e->type == SDL_CONTROLLERAXISMOTION && e->caxis.axis < SDL_CONTROLLER_AXIS_MAX)
      trigger_down[e->caxis.axis] = e->caxis.value > 8000;
    return;
  }
  switch (e->type) {
  case SDL_CONTROLLERBUTTONDOWN: pressed(1, e->cbutton.button, 0); break;
  case SDL_CONTROLLERAXISMOTION:
    if (e->caxis.axis == SDL_CONTROLLER_AXIS_TRIGGERLEFT || e->caxis.axis == SDL_CONTROLLER_AXIS_TRIGGERRIGHT) {
      /* down past 16000, up again below 8000: a trigger resting half way does not repeat */
      bool down = e->caxis.value > 16000;
      if (down && !trigger_down[e->caxis.axis]) pressed(1, AXIS + e->caxis.axis, 0);
      trigger_down[e->caxis.axis] = e->caxis.value > 8000;
    }
    break;
  case SDL_KEYDOWN:
    if (!e->key.repeat && e->key.keysym.scancode != SDL_SCANCODE_AC_BACK && e->key.keysym.scancode != SDL_SCANCODE_F11)
      pressed(2, 0, e->key.keysym.scancode);
    break;
  }
}
