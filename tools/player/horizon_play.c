/* Horizon Play: a small libretro host that runs the patched disc in the SwanStation core with fixed settings
 * (8 MB RAM, CPU at 250 %, GPU upscaling, the free OpenBIOS), full screen, pad, keyboard or touch, no emulator menus.
 * docs/player.md describes the bundle and the controls.
 *
 *   horizon-play [--windowed] [--scale N] [--core PATH] [--system DIR] [--saves DIR] DISC.cue
 *
 * SDL2 and OpenGL (desktop 3.3 core, or OpenGL ES 3 on Android). MIT, like the rest of Horizon's code; the core it
 * loads is GPL-3 and ships as its own library next to this program.
 */
#include <SDL.h>
#ifdef HORIZON_GLES
#include <SDL_opengles2.h>
#ifndef GL_READ_FRAMEBUFFER
#define GL_READ_FRAMEBUFFER 0x8CA8
#define GL_DRAW_FRAMEBUFFER 0x8CA9
#endif
#ifndef GL_DEPTH24_STENCIL8
#define GL_DEPTH24_STENCIL8 0x88F0
#endif
#ifndef GL_RGBA8
#define GL_RGBA8 0x8058
#endif
#else
#include <SDL_opengl.h>
#endif
#include <stdarg.h>
#include <stdbool.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include "libretro.h"
#include "overlay.h"
#include "controls.h"
#include "menu.h"
#include <time.h>
#ifdef __ANDROID__
#include <jni.h>
#endif
#ifdef _WIN32
#include <windows.h>
#endif

/* fopen with a UTF-8 path (Windows too) */
static FILE *open_utf8(const char *path, const char *mode) {
#ifdef _WIN32
  wchar_t wp[1300], wm[8];
  if (!MultiByteToWideChar(CP_UTF8, 0, path, -1, wp, 1300) || !MultiByteToWideChar(CP_UTF8, 0, mode, -1, wm, 8)) return NULL;
  return _wfopen(wp, wm);
#else
  return fopen(path, mode);
#endif
}

/* rename over an existing file (UTF-8 paths on Windows too) */
static bool replace_file(const char *from, const char *to) {
#ifdef _WIN32
  wchar_t wf[1300], wt[1300];
  if (!MultiByteToWideChar(CP_UTF8, 0, from, -1, wf, 1300) || !MultiByteToWideChar(CP_UTF8, 0, to, -1, wt, 1300)) return false;
  return MoveFileExW(wf, wt, MOVEFILE_REPLACE_EXISTING) != 0;
#else
  return rename(from, to) == 0;
#endif
}

#ifndef APIENTRY
#define APIENTRY
#endif

/* ---- the GL calls the host itself makes (the core loads its own through get_proc_address) ---- */
typedef void(APIENTRY *p_GenFramebuffers)(GLsizei, GLuint *);
typedef void(APIENTRY *p_DeleteFramebuffers)(GLsizei, const GLuint *);
typedef void(APIENTRY *p_BindFramebuffer)(GLenum, GLuint);
typedef void(APIENTRY *p_FramebufferTexture2D)(GLenum, GLenum, GLenum, GLuint, GLint);
typedef void(APIENTRY *p_GenRenderbuffers)(GLsizei, GLuint *);
typedef void(APIENTRY *p_DeleteRenderbuffers)(GLsizei, const GLuint *);
typedef void(APIENTRY *p_BindRenderbuffer)(GLenum, GLuint);
typedef void(APIENTRY *p_RenderbufferStorage)(GLenum, GLenum, GLsizei, GLsizei);
typedef void(APIENTRY *p_FramebufferRenderbuffer)(GLenum, GLenum, GLenum, GLuint);
typedef void(APIENTRY *p_BlitFramebuffer)(GLint, GLint, GLint, GLint, GLint, GLint, GLint, GLint, GLbitfield, GLenum);
typedef void(APIENTRY *p_GenTextures)(GLsizei, GLuint *);
typedef void(APIENTRY *p_DeleteTextures)(GLsizei, const GLuint *);
typedef void(APIENTRY *p_BindTexture)(GLenum, GLuint);
typedef void(APIENTRY *p_TexImage2D)(GLenum, GLint, GLint, GLsizei, GLsizei, GLint, GLenum, GLenum, const void *);
typedef void(APIENTRY *p_TexSubImage2D)(GLenum, GLint, GLint, GLint, GLsizei, GLsizei, GLenum, GLenum, const void *);
typedef void(APIENTRY *p_TexParameteri)(GLenum, GLenum, GLint);
typedef void(APIENTRY *p_PixelStorei)(GLenum, GLint);
typedef void(APIENTRY *p_Viewport)(GLint, GLint, GLsizei, GLsizei);
typedef void(APIENTRY *p_ClearColor)(GLfloat, GLfloat, GLfloat, GLfloat);
typedef void(APIENTRY *p_Clear)(GLbitfield);
typedef void(APIENTRY *p_ReadPixels)(GLint, GLint, GLsizei, GLsizei, GLenum, GLenum, void *);
typedef void(APIENTRY *p_Disable)(GLenum);
typedef void(APIENTRY *p_ColorMask)(GLboolean, GLboolean, GLboolean, GLboolean);
typedef GLenum(APIENTRY *p_GetError)(void);

static struct {
  p_GenFramebuffers GenFramebuffers; p_DeleteFramebuffers DeleteFramebuffers; p_BindFramebuffer BindFramebuffer;
  p_FramebufferTexture2D FramebufferTexture2D; p_GenRenderbuffers GenRenderbuffers;
  p_DeleteRenderbuffers DeleteRenderbuffers; p_BindRenderbuffer BindRenderbuffer;
  p_RenderbufferStorage RenderbufferStorage; p_FramebufferRenderbuffer FramebufferRenderbuffer;
  p_BlitFramebuffer BlitFramebuffer; p_GenTextures GenTextures; p_DeleteTextures DeleteTextures;
  p_BindTexture BindTexture; p_TexImage2D TexImage2D; p_TexSubImage2D TexSubImage2D; p_TexParameteri TexParameteri;
  p_PixelStorei PixelStorei; p_Viewport Viewport; p_ClearColor ClearColor; p_Clear Clear; p_ReadPixels ReadPixels;
  p_Disable Disable; p_ColorMask ColorMask; p_GetError GetError;
} gl;

static bool load_gl(void) {
#define L(n) if (!(gl.n = (p_##n)SDL_GL_GetProcAddress("gl" #n))) { SDL_Log("missing gl%s", #n); return false; }
  L(GenFramebuffers) L(DeleteFramebuffers) L(BindFramebuffer) L(FramebufferTexture2D) L(GenRenderbuffers)
  L(DeleteRenderbuffers) L(BindRenderbuffer) L(RenderbufferStorage) L(FramebufferRenderbuffer) L(BlitFramebuffer)
  L(GenTextures) L(DeleteTextures) L(BindTexture) L(TexImage2D) L(TexSubImage2D) L(TexParameteri) L(PixelStorei)
  L(Viewport) L(ClearColor) L(Clear) L(ReadPixels) L(Disable) L(ColorMask) L(GetError)
#undef L
  return true;
}

/* ---- the core's entry points ---- */
static struct {
  void *lib;
  void (*set_environment)(retro_environment_t);
  void (*set_video_refresh)(retro_video_refresh_t);
  void (*set_audio_sample)(retro_audio_sample_t);
  void (*set_audio_sample_batch)(retro_audio_sample_batch_t);
  void (*set_input_poll)(retro_input_poll_t);
  void (*set_input_state)(retro_input_state_t);
  void (*init)(void);
  void (*deinit)(void);
  void (*get_system_av_info)(struct retro_system_av_info *);
  void (*set_controller_port_device)(unsigned, unsigned);
  bool (*load_game)(const struct retro_game_info *);
  void (*unload_game)(void);
  void (*run)(void);
  void (*reset)(void);
  void *(*get_memory_data)(unsigned);
  size_t (*get_memory_size)(unsigned);
  size_t (*serialize_size)(void);              /* (optional) the snapshot kept when Android sends the app away */
  bool (*serialize)(void *, size_t);
  bool (*unserialize)(const void *, size_t);
} core;

/* ---- host state ---- */
static SDL_Window *window;
static SDL_GLContext glctx;
static SDL_AudioDeviceID audio_dev;
static char system_dir[1100], save_dir[1100];
static struct retro_hw_render_callback hw;
static bool hw_requested;
static unsigned pixel_format = RETRO_PIXEL_FORMAT_0RGB1555;
static struct retro_system_av_info av;
static GLuint fbo, fbo_tex, fbo_depth, fbo_w, fbo_h;   /* the core renders here (hardware) */
static GLuint sw_fbo, sw_tex, sw_w, sw_h;              /* software frames are uploaded here */
static unsigned frame_w, frame_h;                      /* the last frame's size */
static bool frame_is_hw, have_frame;
static uint16_t pad_bits;                              /* libretro joypad bits of port 0 */
static bool quit, paused;
static const char *screenshot_path;                    /* --screenshot: write the last frame and leave */
static int run_frames = -1;                            /* --frames N: leave after N frames (tests) */
static bool fast_start = true;
static bool force_touch;                                /* --touch: the touch pad from the start */
static bool first_start, ask_card;
static const char *press_script;                       /* --press "frame:button:len,..." (tests) */

#define MAX_OPTIONS 32
static const char *opt_key[MAX_OPTIONS], *opt_val[MAX_OPTIONS];
static int opt_count;
static char scale_text[8];
static bool options_changed;   /* the core reads its options again (the menu's resolution) */

static void set_option(const char *k, const char *v) {
  for (int i = 0; i < opt_count; i++) if (!strcmp(opt_key[i], k)) { opt_val[i] = v; return; }
  if (opt_count < MAX_OPTIONS) { opt_key[opt_count] = k; opt_val[opt_count++] = v; }
}

/* horizon-play.log in the save folder: the last run's log, for reports (the core's notes and this program's) */
static FILE *log_file;

static void core_log(enum retro_log_level level, const char *fmt, ...) {
  va_list a;
  if (log_file && level >= RETRO_LOG_INFO) { va_start(a, fmt); vfprintf(log_file, fmt, a); va_end(a); fflush(log_file); }
  if (level < RETRO_LOG_WARN && !getenv("HORIZON_PLAY_DEBUG")) return;
  va_start(a, fmt); vfprintf(stderr, fmt, a); va_end(a);
}

static SDL_LogOutputFunction sdl_default_log;
static void *sdl_default_log_data;
static void host_log(void *data, int category, SDL_LogPriority priority, const char *msg) {
  (void)data;
  if (log_file) { fprintf(log_file, "%s\n", msg); fflush(log_file); }
  if (sdl_default_log) sdl_default_log(sdl_default_log_data, category, priority, msg);
}

static uintptr_t get_current_framebuffer(void) { return fbo; }
static retro_proc_address_t get_proc_address(const char *sym) { return (retro_proc_address_t)SDL_GL_GetProcAddress(sym); }

static void make_fbo(unsigned w, unsigned h) {
  if (fbo && w <= fbo_w && h <= fbo_h) return;
  if (fbo) { gl.DeleteFramebuffers(1, &fbo); gl.DeleteTextures(1, &fbo_tex); gl.DeleteRenderbuffers(1, &fbo_depth); }
  fbo_w = w; fbo_h = h;
  gl.GenTextures(1, &fbo_tex); gl.BindTexture(GL_TEXTURE_2D, fbo_tex);
  gl.TexImage2D(GL_TEXTURE_2D, 0, GL_RGBA8, w, h, 0, GL_RGBA, GL_UNSIGNED_BYTE, NULL);
  gl.TexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MIN_FILTER, GL_LINEAR);
  gl.TexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MAG_FILTER, GL_LINEAR);
  gl.GenRenderbuffers(1, &fbo_depth); gl.BindRenderbuffer(GL_RENDERBUFFER, fbo_depth);
  gl.RenderbufferStorage(GL_RENDERBUFFER, GL_DEPTH24_STENCIL8, w, h);
  gl.GenFramebuffers(1, &fbo); gl.BindFramebuffer(GL_FRAMEBUFFER, fbo);
  gl.FramebufferTexture2D(GL_FRAMEBUFFER, GL_COLOR_ATTACHMENT0, GL_TEXTURE_2D, fbo_tex, 0);
  gl.FramebufferRenderbuffer(GL_FRAMEBUFFER, GL_DEPTH_ATTACHMENT, GL_RENDERBUFFER, fbo_depth);
  gl.FramebufferRenderbuffer(GL_FRAMEBUFFER, GL_STENCIL_ATTACHMENT, GL_RENDERBUFFER, fbo_depth);
  gl.ClearColor(0, 0, 0, 1); gl.Clear(GL_COLOR_BUFFER_BIT);
  gl.BindFramebuffer(GL_FRAMEBUFFER, 0);
}

/* A disc inside another file (Android: assets/horizon.bin stored in the APK, docs/player.md). The core reads files
   through libretro's VFS; on Android a path it cannot open locally comes here, and the one path we serve is the track
   named by the cue: it reads the range [embedded_at, embedded_at + embedded_size) of the APK. */
static int64_t embedded_size;   /* 0 without an embedded disc; also ties a resume snapshot to the disc */
#ifndef _WIN32
#include <fcntl.h>
#include <unistd.h>
static char embedded_track[1200];
static const char *embedded_file;
static int64_t embedded_at;
struct retro_vfs_file_handle { int fd; int64_t pos; };
static const char *RETRO_CALLCONV vfs_get_path(struct retro_vfs_file_handle *h) { (void)h; return embedded_track; }
static struct retro_vfs_file_handle *RETRO_CALLCONV vfs_open(const char *path, unsigned mode, unsigned hints) {
  (void)hints;
  if (!embedded_file || strcmp(path, embedded_track) || mode != RETRO_VFS_FILE_ACCESS_READ) return NULL;
  int fd = open(embedded_file, O_RDONLY);
  if (fd < 0) { SDL_Log("embedded disc: cannot open %s", embedded_file); return NULL; }
  struct retro_vfs_file_handle *h = calloc(1, sizeof *h);
  h->fd = fd;
  return h;
}
static int RETRO_CALLCONV vfs_close(struct retro_vfs_file_handle *h) { close(h->fd); free(h); return 0; }
static int64_t RETRO_CALLCONV vfs_size(struct retro_vfs_file_handle *h) { (void)h; return embedded_size; }
static int64_t RETRO_CALLCONV vfs_tell(struct retro_vfs_file_handle *h) { return h->pos; }
static int64_t RETRO_CALLCONV vfs_seek(struct retro_vfs_file_handle *h, int64_t off, int whence) {
  int64_t to = whence == RETRO_VFS_SEEK_POSITION_START ? off : whence == RETRO_VFS_SEEK_POSITION_CURRENT ? h->pos + off
             : embedded_size + off;
  if (to < 0 || to > embedded_size) return -1;
  h->pos = to;
  return 0;   /* like the core's own local files (fseek): rfseek() takes anything else as a failure */
}
static int64_t RETRO_CALLCONV vfs_read(struct retro_vfs_file_handle *h, void *buf, uint64_t len) {
  if (h->pos + (int64_t)len > embedded_size) len = (uint64_t)(embedded_size - h->pos);
  ssize_t n = pread(h->fd, buf, (size_t)len, (off_t)(embedded_at + h->pos));
  if (n < 0) return -1;
  h->pos += n;
  return n;
}
static int64_t RETRO_CALLCONV vfs_write(struct retro_vfs_file_handle *h, const void *b, uint64_t l) { (void)h; (void)b; (void)l; return -1; }
static int RETRO_CALLCONV vfs_flush(struct retro_vfs_file_handle *h) { (void)h; return 0; }
static int RETRO_CALLCONV vfs_remove(const char *p) { (void)p; return -1; }
static int RETRO_CALLCONV vfs_rename(const char *a, const char *b) { (void)a; (void)b; return -1; }
static struct retro_vfs_interface vfs = {vfs_get_path, vfs_open, vfs_close, vfs_size, vfs_tell, vfs_seek, vfs_read,
                                         vfs_write, vfs_flush, vfs_remove, vfs_rename};
#endif

static bool environment(unsigned cmd, void *data) {
  switch (cmd) {
#ifndef _WIN32
  case RETRO_ENVIRONMENT_GET_VFS_INTERFACE: {   /* version 1 is all the embedded track needs */
    struct retro_vfs_interface_info *info = data;
    if (!embedded_file || info->required_interface_version > 1) return false;
    info->iface = &vfs;
    return true;
  }
#endif
  case RETRO_ENVIRONMENT_GET_SYSTEM_DIRECTORY: *(const char **)data = system_dir; return true;
  case RETRO_ENVIRONMENT_GET_SAVE_DIRECTORY: *(const char **)data = save_dir; return true;
  case RETRO_ENVIRONMENT_GET_CORE_ASSETS_DIRECTORY: *(const char **)data = system_dir; return true;
  case RETRO_ENVIRONMENT_SET_PIXEL_FORMAT: pixel_format = *(const unsigned *)data; return true;
  case RETRO_ENVIRONMENT_GET_LOG_INTERFACE: ((struct retro_log_callback *)data)->log = core_log; return true;
  case RETRO_ENVIRONMENT_GET_CAN_DUPE: *(bool *)data = true; return true;
  case RETRO_ENVIRONMENT_GET_INPUT_BITMASKS: return true;
  case RETRO_ENVIRONMENT_GET_CORE_OPTIONS_VERSION: *(unsigned *)data = 0; return true;
  case RETRO_ENVIRONMENT_GET_VARIABLE_UPDATE: *(bool *)data = options_changed; options_changed = false; return true;
  case RETRO_ENVIRONMENT_GET_VARIABLE: {
    struct retro_variable *v = data; v->value = NULL;
    for (int i = 0; i < opt_count; i++) if (!strcmp(opt_key[i], v->key)) { v->value = opt_val[i]; return true; }
    return false;
  }
  case RETRO_ENVIRONMENT_GET_PREFERRED_HW_RENDER:
#ifdef HORIZON_GLES
    *(unsigned *)data = RETRO_HW_CONTEXT_OPENGLES3;
#else
    *(unsigned *)data = RETRO_HW_CONTEXT_OPENGL_CORE;
#endif
    return true;
  case RETRO_ENVIRONMENT_SET_HW_RENDER: {
    struct retro_hw_render_callback *cb = data;
#ifdef HORIZON_GLES
    if (cb->context_type != RETRO_HW_CONTEXT_OPENGLES3 && cb->context_type != RETRO_HW_CONTEXT_OPENGLES_VERSION) return false;
#else
    if (cb->context_type != RETRO_HW_CONTEXT_OPENGL_CORE) return false;
    if (cb->version_major * 10 + cb->version_minor > 33) return false;
#endif
    cb->get_current_framebuffer = get_current_framebuffer;
    cb->get_proc_address = get_proc_address;
    hw = *cb; hw_requested = true;
    return true;
  }
  case RETRO_ENVIRONMENT_SET_GEOMETRY: {
    const struct retro_game_geometry *g = data;
    av.geometry.base_width = g->base_width; av.geometry.base_height = g->base_height;
    av.geometry.aspect_ratio = g->aspect_ratio;
    return true;
  }
  case RETRO_ENVIRONMENT_SET_SYSTEM_AV_INFO:
    av = *(const struct retro_system_av_info *)data;
    if (hw_requested && glctx) make_fbo(av.geometry.max_width, av.geometry.max_height);
    return true;
  case RETRO_ENVIRONMENT_SET_MESSAGE: {
    const struct retro_message *m = data;
    if (getenv("HORIZON_PLAY_DEBUG")) fprintf(stderr, "[core] %s\n", m->msg);
    return true;
  }
  case RETRO_ENVIRONMENT_SET_SUPPORT_NO_GAME: return true;
  default: return false;
  }
}

static void video_refresh(const void *data, unsigned w, unsigned h, size_t pitch) {
  if (!data) return;                       /* duplicate frame: keep the last one */
  frame_w = w; frame_h = h; have_frame = true;
  if (data == RETRO_HW_FRAME_BUFFER_VALID) { frame_is_hw = true; return; }
  frame_is_hw = false;
  if (!sw_tex || w > sw_w || h > sw_h) {
    if (sw_tex) { gl.DeleteFramebuffers(1, &sw_fbo); gl.DeleteTextures(1, &sw_tex); }
    sw_w = w > 1024 ? w : 1024; sw_h = h > 512 ? h : 512;
    gl.GenTextures(1, &sw_tex); gl.BindTexture(GL_TEXTURE_2D, sw_tex);
    gl.TexImage2D(GL_TEXTURE_2D, 0, GL_RGBA8, sw_w, sw_h, 0, GL_RGBA, GL_UNSIGNED_BYTE, NULL);
    gl.GenFramebuffers(1, &sw_fbo); gl.BindFramebuffer(GL_FRAMEBUFFER, sw_fbo);
    gl.FramebufferTexture2D(GL_FRAMEBUFFER, GL_COLOR_ATTACHMENT0, GL_TEXTURE_2D, sw_tex, 0);
    gl.BindFramebuffer(GL_FRAMEBUFFER, 0);
  }
  /* convert to RGBA8 rows (GLES has no BGRA upload) */
  static uint8_t *rgba; static size_t rgba_size;
  if (rgba_size < (size_t)w * h * 4) { rgba_size = (size_t)w * h * 4; rgba = realloc(rgba, rgba_size); }
  for (unsigned y = 0; y < h; y++) {
    const uint8_t *row = (const uint8_t *)data + y * pitch; uint8_t *out = rgba + (size_t)y * w * 4;
    for (unsigned x = 0; x < w; x++, out += 4) {
      if (pixel_format == RETRO_PIXEL_FORMAT_XRGB8888) {
        uint32_t c = ((const uint32_t *)row)[x]; out[0] = c >> 16; out[1] = c >> 8; out[2] = c;
      } else {
        uint16_t c = ((const uint16_t *)row)[x];
        if (pixel_format == RETRO_PIXEL_FORMAT_RGB565) { out[0] = (c >> 11) << 3; out[1] = ((c >> 5) & 63) << 2; out[2] = (c & 31) << 3; }
        else { out[0] = ((c >> 10) & 31) << 3; out[1] = ((c >> 5) & 31) << 3; out[2] = (c & 31) << 3; }
      }
      out[3] = 255;
    }
  }
  gl.BindTexture(GL_TEXTURE_2D, sw_tex);
  gl.PixelStorei(GL_UNPACK_ALIGNMENT, 1);
  gl.TexSubImage2D(GL_TEXTURE_2D, 0, 0, 0, w, h, GL_RGBA, GL_UNSIGNED_BYTE, rgba);
}

/* whether the last picture shows anything: a few rows of it, read back (only while booting) */
static bool picture_lit(void) {
  if (!have_frame || !frame_w || !frame_h) return false;
  static uint8_t row[4096 * 4];
  unsigned w = frame_w > 4096 ? 4096 : frame_w;
  bool lit = false;
  gl.BindFramebuffer(GL_READ_FRAMEBUFFER, frame_is_hw ? fbo : sw_fbo);
  gl.PixelStorei(GL_PACK_ALIGNMENT, 4);
  for (int k = 1; k < 8 && !lit; k++) {
    gl.ReadPixels(0, (GLint)(frame_h * k / 8), (GLsizei)w, 1, GL_RGBA, GL_UNSIGNED_BYTE, row);
    for (unsigned i = 0; i < w * 4; i++) if ((i & 3) != 3 && row[i] > 24) { lit = true; break; }
  }
  gl.BindFramebuffer(GL_READ_FRAMEBUFFER, 0);
  return lit;
}

static void save_screenshot(const char *path);
static void present(bool last) {
  int ww, wh; SDL_GL_GetDrawableSize(window, &ww, &wh);
  /* the core leaves its own state behind: scissor and masks clip a clear and a blit */
  gl.Disable(GL_SCISSOR_TEST);
  gl.ColorMask(GL_TRUE, GL_TRUE, GL_TRUE, GL_TRUE);
  gl.BindFramebuffer(GL_DRAW_FRAMEBUFFER, 0);
  gl.Viewport(0, 0, ww, wh);
  gl.ClearColor(0, 0, 0, 1); gl.Clear(GL_COLOR_BUFFER_BIT);
  if (have_frame && frame_w && frame_h) {
    float aspect = av.geometry.aspect_ratio > 0 ? av.geometry.aspect_ratio : (float)frame_w / frame_h;
    int dw = ww, dh = (int)(ww / aspect + 0.5f);
    if (dh > wh) { dh = wh; dw = (int)(wh * aspect + 0.5f); }
    int dx = (ww - dw) / 2, dy = (wh - dh) / 2;
    gl.BindFramebuffer(GL_READ_FRAMEBUFFER, frame_is_hw ? fbo : sw_fbo);
    if (frame_is_hw && hw.bottom_left_origin)
      gl.BlitFramebuffer(0, 0, frame_w, frame_h, dx, dy, dx + dw, dy + dh, GL_COLOR_BUFFER_BIT, GL_LINEAR);
    else   /* top-left origin: flip */
      gl.BlitFramebuffer(0, 0, frame_w, frame_h, dx, dy + dh, dx + dw, dy, GL_COLOR_BUFFER_BIT, GL_LINEAR);
    gl.BindFramebuffer(GL_READ_FRAMEBUFFER, 0);
    static int checked;
    if (!checked++) { GLenum e = gl.GetError(); if (e) SDL_Log("first frame: GL error 0x%x", e); }
  }
  overlay_draw(ww, wh);
  if (last && screenshot_path) save_screenshot(screenshot_path);
  SDL_GL_SwapWindow(window);
}

static void save_screenshot(const char *path) {
  int ww, wh; SDL_GL_GetDrawableSize(window, &ww, &wh);
  uint8_t *px = malloc((size_t)ww * wh * 4);
  gl.BindFramebuffer(GL_READ_FRAMEBUFFER, 0);
  gl.ReadPixels(0, 0, ww, wh, GL_RGBA, GL_UNSIGNED_BYTE, px);
  FILE *f = fopen(path, "wb");   /* (tests only) */
  if (f) {
    fprintf(f, "P6 %d %d 255\n", ww, wh);
    for (int y = wh - 1; y >= 0; y--) for (int x = 0; x < ww; x++) fwrite(px + ((size_t)y * ww + x) * 4, 1, 3, f);
    fclose(f);
  }
  free(px);
}

static bool booting;   /* the black start, run as fast as the machine goes: its sound is dropped */
/* The sound follows the screen. With a screen refresh near the console's (60 Hz against 59.82), the loop keeps the
 * screen's pace (vsync) and the sound is stretched by a fraction of a percent, more or less as the queue sits below or
 * above its target (dynamic rate control). Waiting on the sound instead made the loop miss a refresh several times a
 * second. audio_ratio is the output samples per input sample; 1 = not stretched (other refresh rates: the sound sets
 * the pace, see the main loop). */
static double audio_ratio = 1, audio_pos = -1;   /* audio_pos: the read position, -1 = the previous batch's last */
static int16_t audio_last[2];
static void audio_push(const int16_t *d, size_t frames) {
  if (!audio_dev || booting || !frames) return;
  if (audio_ratio == 1) { SDL_QueueAudio(audio_dev, d, (Uint32)(frames * 4)); return; }
  static int16_t out[2048 * 2];
  size_t n = 0;
  double step = 1 / audio_ratio;
  for (; audio_pos < (double)frames - 1; audio_pos += step) {
    int i = (int)SDL_floor(audio_pos);
    float f = (float)(audio_pos - i);
    const int16_t *a = i < 0 ? audio_last : d + i * 2, *b = d + (i + 1) * 2;
    out[n * 2] = (int16_t)(a[0] + (b[0] - a[0]) * f);
    out[n * 2 + 1] = (int16_t)(a[1] + (b[1] - a[1]) * f);
    if (++n == 2048) { SDL_QueueAudio(audio_dev, out, (Uint32)(n * 4)); n = 0; }
  }
  if (n) SDL_QueueAudio(audio_dev, out, (Uint32)(n * 4));
  audio_pos -= (double)frames;
  audio_last[0] = d[frames * 2 - 2]; audio_last[1] = d[frames * 2 - 1];
}
static void audio_sample(int16_t l, int16_t r) { int16_t s[2] = {l, r}; audio_push(s, 1); }
static size_t audio_batch(const int16_t *d, size_t frames) { audio_push(d, frames); return frames; }

/* ---- input ---- */
static void input_poll(void) {}
static int16_t input_state(unsigned port, unsigned device, unsigned index, unsigned id) {
  (void)index;
  if (port != 0) return 0;
  if (device == RETRO_DEVICE_JOYPAD) {
    if (id == RETRO_DEVICE_ID_JOYPAD_MASK) return (int16_t)pad_bits;
    return (pad_bits >> id) & 1;
  }
  return 0;
}

static int scripted_bits(int frame) {
  if (!press_script) return 0;
  int bits = 0; const char *p = press_script;
  while (*p) {
    int f, b, len, n = 0;
    if (sscanf(p, "%d:%d:%d%n", &f, &b, &len, &n) != 3) break;
    if (frame >= f && frame < f + len) bits |= 1 << b;
    p += n; if (*p == ',') p++;
  }
  return bits;
}

/* settings.txt in the saves folder: the menu's settings ("scale N", "touch_size P", "touch_opacity P"), kept apart
 * from options.txt (troubleshooting). Each save writes them all. */
static int settings_scale;   /* 0: none chosen, the screen decides */

static void settings_load(void) {
  char path[1200]; snprintf(path, sizeof path, "%s/settings.txt", save_dir);
  int v; char line[128];
  FILE *f = fopen(path, "r");
  if (!f) return;
  while (fgets(line, sizeof line, f)) {
    if (sscanf(line, "scale %d", &v) == 1 && v >= 1 && v <= 8) settings_scale = v;
    if (sscanf(line, "touch_size %d", &v) == 1 && v >= 50 && v <= 150) overlay_touch_size = v;
    if (sscanf(line, "touch_opacity %d", &v) == 1 && v >= 10 && v <= 100) overlay_touch_alpha = v;
  }
  fclose(f);
}

static void settings_save(void) {
  char path[1200]; snprintf(path, sizeof path, "%s/settings.txt", save_dir);
  FILE *f = fopen(path, "w");
  if (!f) return;
  if (settings_scale) fprintf(f, "scale %d\n", settings_scale);
  fprintf(f, "touch_size %d\ntouch_opacity %d\n", overlay_touch_size, overlay_touch_alpha);
  fclose(f);
}

static void toggle_fullscreen(void) {
  bool full = SDL_GetWindowFlags(window) & SDL_WINDOW_FULLSCREEN;
  SDL_SetWindowFullscreen(window, full ? 0 : SDL_WINDOW_FULLSCREEN_DESKTOP);
  SDL_ShowCursor(full ? SDL_ENABLE : SDL_DISABLE);
}

static void card_save(void);
static void card_import(const char *path);
static void resume_save(void);
static void resume_drop(void);

static void handle_events(void) {
  SDL_Event e;
  while (SDL_PollEvent(&e)) {
    int ww, wh; SDL_GL_GetDrawableSize(window, &ww, &wh);
    overlay_event(&e, ww, wh);
    if (menu_open) menu_event(&e, ww, wh);
    controls_event(&e);
    switch (e.type) {
    case SDL_QUIT: quit = true; break;
    case SDL_KEYDOWN:
      if (e.key.keysym.sym == SDLK_F11 || (e.key.keysym.sym == SDLK_RETURN && (e.key.keysym.mod & KMOD_ALT))) toggle_fullscreen();
      else if (e.key.keysym.sym == SDLK_ESCAPE && menu_open) menu_back();
      else if (e.key.keysym.sym == SDLK_ESCAPE && remap_step < 0) controls_menu_asked = true;   /* Escape opens the menu */
      break;
    case SDL_MOUSEBUTTONDOWN:   /* so does a right click: a computer always has a way in, whatever its pad */
      if (e.button.button == SDL_BUTTON_RIGHT && !menu_open && remap_step < 0) controls_menu_asked = true;
      break;
    case SDL_DROPFILE:   /* a memory card dropped on the window, while the menu waits for one */
      if (menu_waiting_drop()) card_import(e.drop.file);
      SDL_free(e.drop.file);
      break;
    case SDL_WINDOWEVENT:
      if (e.window.event == SDL_WINDOWEVENT_MINIMIZED) paused = true;
      else if (e.window.event == SDL_WINDOWEVENT_RESTORED || e.window.event == SDL_WINDOWEVENT_SHOWN) paused = false;
      break;
    case SDL_APP_WILLENTERBACKGROUND: paused = true; card_save(); resume_save(); break;
    case SDL_APP_TERMINATING: card_save(); break;
    case SDL_APP_DIDENTERFOREGROUND: paused = false; resume_drop(); break;   /* still alive: no need for it */
    }
  }
}

/* ---- the memory card: the core's "Libretro" card is a 128 KB buffer this program keeps in the save folder, in the
 * file DuckStation's shared card uses. It is written whenever it changes (checked every second), when the app goes to
 * the background and at exit, so a closed window or an app Android kills keeps the last save. */
static char card_path[1200];
static uint8_t card_written[128 * 1024];
static bool card_existed;   /* the saves folder had a card at start (a new install has none) */
#ifdef __ANDROID__
static void android_backup(const char *card);
/* a card with a save on it: a directory frame (1-15) marks a save's first block in use (0x51) */
static bool card_has_save(const uint8_t *card) {
  for (int i = 1; i < 16; i++) if (card[i * 128] == 0x51) return true;
  return false;
}
#endif

static void card_load(void) {
  uint8_t *data = core.get_memory_data(RETRO_MEMORY_SAVE_RAM);
  size_t size = core.get_memory_size(RETRO_MEMORY_SAVE_RAM);
  if (!data || size != sizeof card_written) return;
  SDL_RWops *f = SDL_RWFromFile(card_path, "rb");
  card_existed = f != NULL;
  if (f) {
    if (SDL_RWread(f, card_written, 1, size) == size) memcpy(data, card_written, size);
    SDL_RWclose(f);
  }
  memcpy(card_written, data, size);
}

static void card_write(bool always) {
  uint8_t *data = core.get_memory_data(RETRO_MEMORY_SAVE_RAM);
  size_t size = core.get_memory_size(RETRO_MEMORY_SAVE_RAM);
  if (!data || size != sizeof card_written || (!always && !memcmp(data, card_written, size))) return;
  /* the whole card in one write to a fresh file, then over the old one: a cut in the middle keeps the old card */
  char tmp[1300]; snprintf(tmp, sizeof tmp, "%s.new", card_path);
  SDL_RWops *f = SDL_RWFromFile(tmp, "wb");
  if (!f) { SDL_Log("cannot write %s", tmp); return; }
  bool ok = SDL_RWwrite(f, data, 1, size) == size;
  ok = SDL_RWclose(f) == 0 && ok;
  if (ok && replace_file(tmp, card_path)) {
    memcpy(card_written, data, size);
#ifdef __ANDROID__
    if (card_has_save(data)) android_backup(card_path);   /* the copy in Documents, which an uninstall leaves */
#endif
  } else SDL_Log("cannot save the memory card %s", card_path);
}

static void card_save(void) { card_write(false); }

/* ---- the menu's memory card export and import ---- */
static bool restart_asked;   /* an imported card: the game starts again to read it */

/* a card from another file: a raw 128 KB PlayStation memory card (.mcd, .mcr, .srm...). The card in use is copied
 * next to it first (duckstation_shared_card_1.backup-DATE.mcd), then the game starts again to read the new one. */
static void card_import(const char *path) {
  uint8_t *data = core.get_memory_data(RETRO_MEMORY_SAVE_RAM);
  size_t size = core.get_memory_size(RETRO_MEMORY_SAVE_RAM);
  static uint8_t in[128 * 1024 + 1];
  size_t got = 0;
  SDL_RWops *f = SDL_RWFromFile(path, "rb");
  if (f) { got = SDL_RWread(f, in, 1, sizeof in); SDL_RWclose(f); }
  if (!data || size != sizeof card_written || got != size || in[0] != 'M' || in[1] != 'C') {
    SDL_Log("import: %s is not a 128 KB PlayStation memory card", path);
    menu_result(0);
    return;
  }
  char backup[1300], stamp[32];
  time_t now = time(NULL);
  strftime(stamp, sizeof stamp, "%Y%m%d-%H%M%S", localtime(&now));
  snprintf(backup, sizeof backup, "%s/duckstation_shared_card_1.backup-%s.mcd", save_dir, stamp);
  SDL_RWops *b = SDL_RWFromFile(backup, "wb");
  bool ok = b && SDL_RWwrite(b, data, 1, size) == size;
  if (b) ok = SDL_RWclose(b) == 0 && ok;
  if (!ok) { SDL_Log("import: cannot write the backup %s", backup); menu_result(0); return; }
  memcpy(data, in, size);
  card_save();
  SDL_Log("import: %s is the memory card now; the old one is in %s", path, backup);
  restart_asked = true;
  menu_result(1);
}

/* ---- where the player left off (Android) ----
 * Android may end an app it has sent to the background (another app opened, the screen locked a while) and the
 * game would lose everything since its last save. So when the app goes to the background the whole machine is
 * written to resume.state in the saves folder, and a start that finds it goes on from there. The file only lives
 * while the app is away: it is deleted when the app comes back by itself, as soon as it has been loaded, on QUIT and
 * when a memory card is imported, so an old moment never comes back over a newer save. It is tied to this program
 * and this disc (its header), and the memory card stays the one on file: the snapshot's copy of it is not used. */
#ifndef HORIZON_VERSION
#define HORIZON_VERSION "DEV"
#endif
static bool game_started;
static int suspend_at = -1;   /* --suspend-at N: keep the snapshot at frame N and end, as Android may (tests) */     /* the game is past its start: a snapshot is worth keeping */
static char resume_path[1200];
typedef struct { char magic[8], version[40]; int64_t disc_size, state_size; } ResumeHeader;

static void resume_header(ResumeHeader *h, size_t state_size) {
  memset(h, 0, sizeof *h);
  memcpy(h->magic, "HPRESUME", 8);
  snprintf(h->version, sizeof h->version, "%s", HORIZON_VERSION);
  h->disc_size = embedded_size; h->state_size = (int64_t)state_size;
}

static void resume_drop(void) { if (resume_path[0]) remove(resume_path); }

static void resume_save(void) {
  if (!core.serialize || !core.serialize_size || !game_started || booting || !resume_path[0]) return;
  size_t n = core.serialize_size();
  void *buf = n ? malloc(n) : NULL;
  if (!buf || !core.serialize(buf, n)) { SDL_Log("resume: no snapshot"); free(buf); return; }
  ResumeHeader h; resume_header(&h, n);
  char tmp[1300]; snprintf(tmp, sizeof tmp, "%s.new", resume_path);
  SDL_RWops *f = SDL_RWFromFile(tmp, "wb");
  bool ok = f && SDL_RWwrite(f, &h, sizeof h, 1) == 1 && SDL_RWwrite(f, buf, 1, n) == n;
  if (f) ok = SDL_RWclose(f) == 0 && ok;
  free(buf);
  if (ok && replace_file(tmp, resume_path)) SDL_Log("resume: the game kept (%u KB)", (unsigned)(n / 1024));
  else { SDL_Log("resume: cannot write %s", resume_path); remove(tmp); }
}

/* the snapshot from when the app was sent away, if there is one for this program and disc: true if loaded */
static bool resume_load(void) {
  if (!core.unserialize || !core.serialize_size) return false;
  SDL_RWops *f = SDL_RWFromFile(resume_path, "rb");
  if (!f) return false;
  ResumeHeader h, want; resume_header(&want, core.serialize_size());
  bool ok = SDL_RWread(f, &h, sizeof h, 1) == 1 && !memcmp(h.magic, want.magic, 8) && !strcmp(h.version, want.version)
            && h.disc_size == want.disc_size && h.state_size > 0 && h.state_size <= 64 << 20;
  void *buf = ok ? malloc((size_t)h.state_size) : NULL;
  ok = buf && SDL_RWread(f, buf, 1, (size_t)h.state_size) == (size_t)h.state_size;
  SDL_RWclose(f);
  resume_drop();
  if (ok) ok = core.unserialize(buf, (size_t)h.state_size);
  free(buf);
  if (!ok) { SDL_Log("resume: %s is not for this game, left out", resume_path); return false; }
  /* the memory card stays the one on file */
  uint8_t *data = core.get_memory_data(RETRO_MEMORY_SAVE_RAM);
  if (data && core.get_memory_size(RETRO_MEMORY_SAVE_RAM) == sizeof card_written && memcmp(data, card_written, sizeof card_written)) {
    SDL_Log("resume: the snapshot's memory card differs from the file; the file's is kept");
    memcpy(data, card_written, sizeof card_written);
  }
  SDL_Log("resume: the game goes on where it was left");
  return true;
}

#ifdef __ANDROID__
/* HorizonActivity.pickCard opens Android's file picker; cardResult is 1 done, 2 failed, 3 cancelled */
static void android_pick(bool export_, const char *card, const char *dest) {
  JNIEnv *env = (JNIEnv *)SDL_AndroidGetJNIEnv();
  jobject act = (jobject)SDL_AndroidGetActivity();
  jclass cls = (*env)->GetObjectClass(env, act);
  jmethodID m = (*env)->GetMethodID(env, cls, "pickCard", "(ZLjava/lang/String;Ljava/lang/String;)V");
  jstring a = (*env)->NewStringUTF(env, card), b = (*env)->NewStringUTF(env, dest);
  if (m) (*env)->CallVoidMethod(env, act, m, (jboolean)export_, a, b);
  (*env)->DeleteLocalRef(env, a); (*env)->DeleteLocalRef(env, b);
  (*env)->DeleteLocalRef(env, cls); (*env)->DeleteLocalRef(env, act);
}

static void android_backup(const char *card) {
  JNIEnv *env = (JNIEnv *)SDL_AndroidGetJNIEnv();
  jobject act = (jobject)SDL_AndroidGetActivity();
  jclass cls = (*env)->GetObjectClass(env, act);
  jmethodID m = (*env)->GetMethodID(env, cls, "backupCard", "(Ljava/lang/String;)V");
  jstring a = (*env)->NewStringUTF(env, card);
  if (m) (*env)->CallVoidMethod(env, act, m, a);
  (*env)->DeleteLocalRef(env, a); (*env)->DeleteLocalRef(env, cls); (*env)->DeleteLocalRef(env, act);
}

/* HorizonActivity.newVersion: a newer release's tag, once its check (a thread at start) found one; "" until then */
static bool android_new_version(char *out, size_t n) {
  JNIEnv *env = (JNIEnv *)SDL_AndroidGetJNIEnv();
  jobject act = (jobject)SDL_AndroidGetActivity();
  jclass cls = (*env)->GetObjectClass(env, act);
  jfieldID f = (*env)->GetStaticFieldID(env, cls, "newVersion", "Ljava/lang/String;");
  bool got = false;
  jstring v = f ? (jstring)(*env)->GetStaticObjectField(env, cls, f) : NULL;
  if (v) {
    const char *c = (*env)->GetStringUTFChars(env, v, NULL);
    if (c) { got = c[0] != 0; snprintf(out, n, "%s", c); (*env)->ReleaseStringUTFChars(env, v, c); }
    (*env)->DeleteLocalRef(env, v);
  }
  if ((*env)->ExceptionCheck(env)) (*env)->ExceptionClear(env);
  (*env)->DeleteLocalRef(env, cls); (*env)->DeleteLocalRef(env, act);
  return got;
}

static int android_pick_result(void) {
  JNIEnv *env = (JNIEnv *)SDL_AndroidGetJNIEnv();
  jobject act = (jobject)SDL_AndroidGetActivity();
  jclass cls = (*env)->GetObjectClass(env, act);
  jfieldID f = (*env)->GetStaticFieldID(env, cls, "cardResult", "I");
  int r = f ? (*env)->GetStaticIntField(env, cls, f) : 2;
  (*env)->DeleteLocalRef(env, cls); (*env)->DeleteLocalRef(env, act);
  return r;
}
#endif

static int card_waiting;   /* (Android) the picker is open: MENU_EXPORT or MENU_IMPORT */

static void card_action(int action) {
  char import_path[1300];
  snprintf(import_path, sizeof import_path, "%s/import.mcd", save_dir);
  card_write(true);   /* a card never saved to yet has no file to export */
#ifdef __ANDROID__
  android_pick(action == MENU_EXPORT, card_path, import_path);
  card_waiting = action;
#else
  (void)import_path;
  if (action == MENU_EXPORT) {   /* the save folder, opened in the file manager: the card is the .mcd file there */
    char url[1300];
    snprintf(url, sizeof url, "file:///%s", save_dir[0] == '/' ? save_dir + 1 : save_dir);
    menu_result(SDL_OpenURL(url) == 0 ? 1 : 0);
  }
#endif
}

static void card_poll(void) {
#ifdef __ANDROID__
  if (!card_waiting) return;
  int r = android_pick_result();
  if (!r) return;
  int action = card_waiting;
  card_waiting = 0;
  if (r == 3) { menu_result(-1); return; }
  if (r != 1) { menu_result(0); return; }
  if (action == MENU_EXPORT) { menu_result(1); return; }
  char import_path[1300];
  snprintf(import_path, sizeof import_path, "%s/import.mcd", save_dir);
  card_import(import_path);
  remove(import_path);
#endif
}

static bool load_core(const char *path) {
  core.lib = SDL_LoadObject(path);
  if (!core.lib) { SDL_Log("cannot load the core %s: %s", path, SDL_GetError()); return false; }
#define F(n) if (!(*(void **)&core.n = SDL_LoadFunction(core.lib, "retro_" #n))) { SDL_Log("core lacks retro_%s", #n); return false; }
  F(set_environment) F(set_video_refresh) F(set_audio_sample) F(set_audio_sample_batch) F(set_input_poll)
  F(set_input_state) F(init) F(deinit) F(get_system_av_info) F(set_controller_port_device) F(load_game)
  F(unload_game) F(run) F(reset) F(get_memory_data) F(get_memory_size)
#undef F
  *(void **)&core.serialize_size = SDL_LoadFunction(core.lib, "retro_serialize_size");
  *(void **)&core.serialize = SDL_LoadFunction(core.lib, "retro_serialize");
  *(void **)&core.unserialize = SDL_LoadFunction(core.lib, "retro_unserialize");
  return true;
}

static void fail(const char *title, const char *msg) {
  SDL_Log("%s: %s", title, msg);
  SDL_ShowSimpleMessageBox(SDL_MESSAGEBOX_ERROR, title, msg, window);
}

/* --unpack SETUP DIR: write the disc appended to the Windows setup (tools/patcher/setup_exe.py) into DIR as
 * "Digimon World Horizon.bin" and ".cue". The trailer: ... BIN | CUE | bin size u64 | cue size u32 | version u32 |
 * "HZSETUP1". Through .new files, renamed at the end. SDL_RWops: 64-bit offsets and UTF-8 paths on every system. */
#define SETUP_NAME "Digimon World Horizon"
static int unpack_fail(const char *what, const char *path) {
  fprintf(stderr, "unpack: %s%s%s\n", what, path ? ": " : "", path ? path : "");
  return 2;
}
static bool unpack_copy(SDL_RWops *in, Sint64 from, Sint64 size, const char *path) {
  SDL_RWops *out = SDL_RWFromFile(path, "wb");
  static char buf[1 << 20];
  if (!out) return false;
  bool ok = SDL_RWseek(in, from, RW_SEEK_SET) == from;
  while (ok && size > 0) {
    size_t n = size < (Sint64)sizeof buf ? (size_t)size : sizeof buf;
    ok = SDL_RWread(in, buf, 1, n) == n && SDL_RWwrite(out, buf, 1, n) == n;
    size -= (Sint64)n;
  }
  return SDL_RWclose(out) == 0 && ok;
}
static bool unpack_rename(const char *from, const char *to) {
#ifdef _WIN32
  wchar_t a[1024], b[1024];
  if (!MultiByteToWideChar(CP_UTF8, 0, from, -1, a, 1024) || !MultiByteToWideChar(CP_UTF8, 0, to, -1, b, 1024)) return false;
  return MoveFileExW(a, b, MOVEFILE_REPLACE_EXISTING) != 0;
#else
  return rename(from, to) == 0;
#endif
}
static int unpack_setup(const char *setup, const char *dir) {
  unsigned char t[24];
  SDL_RWops *in = SDL_RWFromFile(setup, "rb");
  if (!in) return unpack_fail("cannot open", setup);
  Sint64 end = SDL_RWsize(in);
  if (end < (Sint64)sizeof t || SDL_RWseek(in, end - (Sint64)sizeof t, RW_SEEK_SET) < 0 ||
      SDL_RWread(in, t, 1, sizeof t) != sizeof t) { SDL_RWclose(in); return unpack_fail("cannot read the end of", setup); }
  if (memcmp(t + 16, "HZSETUP1", 8)) { SDL_RWclose(in); return unpack_fail("no game inside (not made by the Horizon Patcher)", setup); }
  Sint64 bin = 0; Uint32 cue = 0, ver = 0;
  for (int i = 7; i >= 0; i--) bin = (bin << 8) | t[i];
  for (int i = 11; i >= 8; i--) cue = (cue << 8) | t[i];
  for (int i = 15; i >= 12; i--) ver = (ver << 8) | t[i];
  if (ver != 1) { SDL_RWclose(in); return unpack_fail("a setup of a newer kind: update the Horizon Patcher", setup); }
  if (bin <= 0 || bin + (Sint64)cue + (Sint64)sizeof t > end) { SDL_RWclose(in); return unpack_fail("the setup is damaged (too short)", setup); }
  char binp[1024], cuep[1024], binn[1040], cuen[1040];
  const char sep = (strchr(dir, '\\') || strstr(dir, ":")) ? '\\' : '/';
  snprintf(binp, sizeof binp, "%s%c%s.bin", dir, sep, SETUP_NAME);
  snprintf(cuep, sizeof cuep, "%s%c%s.cue", dir, sep, SETUP_NAME);
  snprintf(binn, sizeof binn, "%s.new", binp);
  snprintf(cuen, sizeof cuen, "%s.new", cuep);
  Sint64 at = end - (Sint64)sizeof t - (Sint64)cue - bin;
  bool ok = unpack_copy(in, at, bin, binn) && unpack_copy(in, at + bin, cue, cuen);
  SDL_RWclose(in);
  if (!ok) { return unpack_fail("cannot write the disc (disk full?)", binn); }
  if (!unpack_rename(binn, binp) || !unpack_rename(cuen, cuep)) return unpack_fail("cannot rename into place", binp);
  return 0;
}

/* ---- a newer release (docs/player.md) ----
 * At start a thread asks GitHub's API which release is the latest (as HorizonActivity.checkVersion does) and,
 * when it is newer than this program, the menu says so once
 * (menu_show_update). Android asks in Java (HorizonActivity.checkVersion). Offline, or with no repository built in,
 * nothing shows. */
static char test_new_version[40];   /* --new-version TAG (tests): as if the check had found it */
#if !defined(__ANDROID__) && defined(HORIZON_REPOSITORY)
#ifdef _WIN32
#include <winhttp.h>
#endif
static char latest_tag[40];
static SDL_atomic_t latest_done;

static void version_key(const char *v, int k[3]) {
  k[0] = k[1] = k[2] = -1;
  if (v && (*v == 'v' || *v == 'V')) v++;
  if (v) sscanf(v, "%d.%d.%d", &k[0], &k[1], &k[2]);
}

static int latest_thread(void *unused) {
  (void)unused;
  char loc[8192] = "";   /* the start of the answer: "tag_name" comes early, before the assets */
  size_t got = 0;
#ifdef _WIN32
  wchar_t path[300]; char p8[300];
  snprintf(p8, sizeof p8, "/repos/%s/releases/latest", HORIZON_REPOSITORY);
  MultiByteToWideChar(CP_UTF8, 0, p8, -1, path, 300);
  HINTERNET ses = WinHttpOpen(L"Horizon Play", WINHTTP_ACCESS_TYPE_DEFAULT_PROXY, WINHTTP_NO_PROXY_NAME,
                              WINHTTP_NO_PROXY_BYPASS, 0);
  HINTERNET con = ses ? WinHttpConnect(ses, L"api.github.com", INTERNET_DEFAULT_HTTPS_PORT, 0) : NULL;
  HINTERNET req = con ? WinHttpOpenRequest(con, L"GET", path, NULL, WINHTTP_NO_REFERER, WINHTTP_DEFAULT_ACCEPT_TYPES,
                                           WINHTTP_FLAG_SECURE) : NULL;
  if (req) {
    WinHttpSetTimeouts(ses, 10000, 10000, 10000, 10000);
    if (WinHttpSendRequest(req, L"Accept: application/vnd.github+json\r\n", (DWORD)-1L, WINHTTP_NO_REQUEST_DATA, 0, 0, 0)
        && WinHttpReceiveResponse(req, NULL)) {
      DWORD n;
      while (got < sizeof loc - 1 && WinHttpReadData(req, loc + got, (DWORD)(sizeof loc - 1 - got), &n) && n) got += n;
    }
  }
  if (req) WinHttpCloseHandle(req);
  if (con) WinHttpCloseHandle(con);
  if (ses) WinHttpCloseHandle(ses);
#else
  /* curl is part of macOS and of nearly every Linux; without it there is simply no notice */
  char cmd[400];
  snprintf(cmd, sizeof cmd, "curl -s -m 10 -H 'Accept: application/vnd.github+json' "
           "'https://api.github.com/repos/%s/releases/latest' 2>/dev/null", HORIZON_REPOSITORY);
  FILE *p = popen(cmd, "r");
  if (p) {
    size_t n;
    while (got < sizeof loc - 1 && (n = fread(loc + got, 1, sizeof loc - 1 - got, p)) > 0) got += n;
    while (fread(cmd, 1, sizeof cmd, p) > 0) {}   /* the rest, so curl ends by itself */
    pclose(p);
  }
#endif
  loc[got] = 0;
  const char *t = strstr(loc, "\"tag_name\"");
  if (t) t = strchr(t + 10, '"');
  if (t) {
    char tag[40]; int n = 0;
    for (t++; *t && *t != '"' && n < (int)sizeof tag - 1; t++) tag[n++] = *t;
    tag[n] = 0;
    int a[3], b[3]; version_key(tag, a); version_key(HORIZON_VERSION, b);
    bool newer = false;
    if (a[0] >= 0 && b[0] >= 0 && b[2] >= 0)
      for (int i = 0; i < 3; i++) if (a[i] != b[i]) { newer = a[i] > b[i]; break; }
    if (newer) snprintf(latest_tag, sizeof latest_tag, "%s", tag);
    SDL_Log("latest release: %s (this is %s)", tag, HORIZON_VERSION);
  }
  SDL_AtomicSet(&latest_done, 1);
  return 0;
}
#endif

static void new_version_check(void) {
#if !defined(__ANDROID__) && defined(HORIZON_REPOSITORY)
  SDL_Thread *t = SDL_CreateThread(latest_thread, "latest", NULL);
  if (t) SDL_DetachThread(t);
#endif
}

/* a newer release's tag, once the check found one */
static bool new_version_found(char *out, size_t n) {
  if (test_new_version[0]) { snprintf(out, n, "%s", test_new_version); return true; }
#ifdef __ANDROID__
  return android_new_version(out, n);
#elif defined(HORIZON_REPOSITORY)
  if (!SDL_AtomicGet(&latest_done) || !latest_tag[0]) return false;
  snprintf(out, n, "%s", latest_tag); return true;
#else
  (void)out; (void)n; return false;
#endif
}

int main(int argc, char **argv) {
  if (argc == 4 && !strcmp(argv[1], "--unpack")) return unpack_setup(argv[2], argv[3]);
  const char *disc = NULL, *core_path = NULL, *sys = NULL, *saves = NULL;
  bool windowed = false, no_disc = false; int scale = 0, force_w = 0, force_h = 0;
  for (int i = 1; i < argc; i++) {
    if (!strcmp(argv[i], "--windowed")) windowed = true;
    else if (!strcmp(argv[i], "--window") && i + 1 < argc) {   /* --window WxH: a window of that size (tests) */
      windowed = sscanf(argv[++i], "%dx%d", &force_w, &force_h) == 2;
    }
    else if (!strcmp(argv[i], "--no-disc")) no_disc = true;               /* the BIOS alone (a smoke test) */
    else if (!strcmp(argv[i], "--touch")) force_touch = true;            /* the touch pad from the start */
    else if (!strcmp(argv[i], "--ask-card")) ask_card = true;           /* (tests) the new install's card question */
    else if (!strcmp(argv[i], "--first-start")) first_start = true;      /* the first start's question, in tests too */
    else if (!strcmp(argv[i], "--new-version") && i + 1 < argc)   /* (tests) */
      snprintf(test_new_version, sizeof test_new_version, "%s", argv[++i]);
    else if (!strcmp(argv[i], "--suspend-at") && i + 1 < argc) suspend_at = atoi(argv[++i]);   /* (tests) */
    else if (!strcmp(argv[i], "--no-fast-start")) fast_start = false;     /* the start at the console's own pace */
    else if (!strcmp(argv[i], "--scale") && i + 1 < argc) scale = atoi(argv[++i]);
    else if (!strcmp(argv[i], "--core") && i + 1 < argc) core_path = argv[++i];
    else if (!strcmp(argv[i], "--system") && i + 1 < argc) sys = argv[++i];
    else if (!strcmp(argv[i], "--saves") && i + 1 < argc) saves = argv[++i];
    else if (!strcmp(argv[i], "--screenshot") && i + 1 < argc) screenshot_path = argv[++i];
    else if (!strcmp(argv[i], "--frames") && i + 1 < argc) run_frames = atoi(argv[++i]);
    else if (!strcmp(argv[i], "--press") && i + 1 < argc) press_script = argv[++i];
    else if (!strcmp(argv[i], "--set") && i + 1 < argc) {   /* --set KEY=VALUE: override a core option */
      char *kv = argv[++i], *eq = strchr(kv, '='); if (eq) { *eq = 0; set_option(kv, eq + 1); }
    }
#ifndef _WIN32
    /* --embedded FILE OFFSET SIZE: the cue's track lies inside FILE (the APK) at OFFSET */
    else if (!strcmp(argv[i], "--embedded") && i + 3 < argc) {
      embedded_file = argv[++i]; embedded_at = strtoll(argv[++i], NULL, 10); embedded_size = strtoll(argv[++i], NULL, 10);
    }
#endif
    else disc = argv[i];
  }
#ifndef _WIN32
  if (embedded_file && disc) {   /* the cue names its track "embedded.bin", beside it */
    const char *slash = strrchr(disc, '/');
    snprintf(embedded_track, sizeof embedded_track, "%.*s/embedded.bin", slash ? (int)(slash - disc) : 1, slash ? disc : ".");
    SDL_Log("embedded disc: %s at %lld, %lld bytes, as %s", embedded_file, (long long)embedded_at,
            (long long)embedded_size, embedded_track);
  }
#endif

  SDL_SetHint(SDL_HINT_ANDROID_TRAP_BACK_BUTTON, "1");   /* a pad's B must not close the game */
  SDL_SetHint(SDL_HINT_ORIENTATIONS, "LandscapeLeft LandscapeRight");
  SDL_SetHint(SDL_HINT_ACCELEROMETER_AS_JOYSTICK, "0");   /* a phone's tilt would move the menu and the game */
  if (SDL_Init(SDL_INIT_VIDEO | SDL_INIT_AUDIO | SDL_INIT_GAMECONTROLLER) != 0) { fprintf(stderr, "SDL: %s\n", SDL_GetError()); return 1; }
  char *base = SDL_GetBasePath();
  char here[1024]; snprintf(here, sizeof here, "%s", base ? base : "./"); SDL_free(base);


  char core_default[1200];
#if defined(_WIN32)
  snprintf(core_default, sizeof core_default, "%sswanstation_libretro.dll", here);
#elif defined(__APPLE__)
  snprintf(core_default, sizeof core_default, "%sswanstation_libretro.dylib", here);
#elif defined(__ANDROID__)
  snprintf(core_default, sizeof core_default, "libswanstation_libretro_android.so");
#else
  snprintf(core_default, sizeof core_default, "%sswanstation_libretro.so", here);
#endif
  if (!core_path) core_path = core_default;
  if (sys) snprintf(system_dir, sizeof system_dir, "%s", sys);
  else snprintf(system_dir, sizeof system_dir, "%ssystem", here);
  if (saves) snprintf(save_dir, sizeof save_dir, "%s", saves);
  else { char *p = SDL_GetPrefPath("Horizon", "Horizon"); snprintf(save_dir, sizeof save_dir, "%s", p ? p : here); SDL_free(p); }
  size_t sl = strlen(save_dir); if (sl && (save_dir[sl - 1] == '/' || save_dir[sl - 1] == '\\')) save_dir[sl - 1] = 0;
  { char lp[1300]; snprintf(lp, sizeof lp, "%s/horizon-play.log", save_dir); log_file = open_utf8(lp, "w"); }
  { /* options.txt in the save folder: KEY=VALUE lines that override core options (troubleshooting) */
    char op[1300]; snprintf(op, sizeof op, "%s/options.txt", save_dir);
    FILE *f = open_utf8(op, "r"); char line[512];
    while (f && fgets(line, sizeof line, f)) {
      line[strcspn(line, "\r\n")] = 0;
      char *eq = strchr(line, '=');
      if (eq && line[0] != '#') { *eq = 0; set_option(SDL_strdup(line), SDL_strdup(eq + 1)); }
    }
    if (f) fclose(f);
  }
  SDL_LogGetOutputFunction(&sdl_default_log, &sdl_default_log_data);
  SDL_LogSetOutputFunction(host_log, NULL);

  /* the disc: the one given (and remembered), else the one played last time */
  static char last_disc[2048];
  char last_file[1200]; snprintf(last_file, sizeof last_file, "%s/last-disc.txt", save_dir);
  /* (SDL_RWops: UTF-8 paths on Windows too) */
  if (disc) {
    SDL_RWops *f = SDL_RWFromFile(last_file, "wb"); if (f) { SDL_RWwrite(f, disc, 1, strlen(disc)); SDL_RWclose(f); }
  } else if (!no_disc) {
    /* a disc put inside the app (tools/patcher/mac_app.py, linux_run.py) or beside the program: play it first */
    static char beside[1300]; snprintf(beside, sizeof beside, "%s%s.cue", here, SETUP_NAME);
    SDL_RWops *b = SDL_RWFromFile(beside, "rb");
    if (b) { SDL_RWclose(b); disc = beside; SDL_Log("disc beside the program: %s", beside); }
    SDL_RWops *f = disc ? NULL : SDL_RWFromFile(last_file, "rb");
    if (f) {
      size_t n = SDL_RWread(f, last_disc, 1, sizeof last_disc - 1); SDL_RWclose(f); last_disc[n] = 0;
      SDL_RWops *t = n ? SDL_RWFromFile(last_disc, "rb") : NULL;
      if (t) { SDL_RWclose(t); disc = last_disc; }
    }
    if (!disc) {
      fail("Digimon World: Horizon", "Press Play in the Horizon Patcher after it builds your disc, "
           "or drop the Horizon disc (.cue) on this program.");
      return 2;
    }
  }

  /* the window: full screen on the desktop's mode unless --windowed */
  SDL_DisplayMode dm = {0, 1440, 1080, 0, NULL}; int disp_h = 1080;
  if (SDL_GetDesktopDisplayMode(0, &dm) == 0) disp_h = dm.h < dm.w ? dm.h : dm.w;   /* a phone may report portrait */
#ifdef HORIZON_GLES
  SDL_GL_SetAttribute(SDL_GL_CONTEXT_PROFILE_MASK, SDL_GL_CONTEXT_PROFILE_ES);
  SDL_GL_SetAttribute(SDL_GL_CONTEXT_MAJOR_VERSION, 3);
  SDL_GL_SetAttribute(SDL_GL_CONTEXT_MINOR_VERSION, 0);
#else
  SDL_GL_SetAttribute(SDL_GL_CONTEXT_PROFILE_MASK, SDL_GL_CONTEXT_PROFILE_CORE);
  SDL_GL_SetAttribute(SDL_GL_CONTEXT_MAJOR_VERSION, 3);
  SDL_GL_SetAttribute(SDL_GL_CONTEXT_MINOR_VERSION, 3);
#ifdef __APPLE__
  SDL_GL_SetAttribute(SDL_GL_CONTEXT_FLAGS, SDL_GL_CONTEXT_FORWARD_COMPATIBLE_FLAG);
#endif
#endif
  SDL_GL_SetAttribute(SDL_GL_DOUBLEBUFFER, 1);
  int win_h = disp_h * 3 / 4, win_w = win_h * 4 / 3;
  Uint32 flags = SDL_WINDOW_OPENGL | SDL_WINDOW_RESIZABLE | SDL_WINDOW_ALLOW_HIGHDPI;
#ifdef __ANDROID__
  flags = SDL_WINDOW_OPENGL | SDL_WINDOW_FULLSCREEN | SDL_WINDOW_ALLOW_HIGHDPI;   /* the whole screen, landscape */
  win_w = dm.w > dm.h ? dm.w : dm.h; win_h = dm.w > dm.h ? dm.h : dm.w;
#else
  if (!windowed) flags |= SDL_WINDOW_FULLSCREEN_DESKTOP;
  if (force_w > 0 && force_h > 0) { win_w = force_w; win_h = force_h; }
#endif
  window = SDL_CreateWindow("Digimon World: Horizon", SDL_WINDOWPOS_CENTERED, SDL_WINDOWPOS_CENTERED, win_w, win_h, flags);
  if (!window) { fail("Horizon", SDL_GetError()); return 1; }
  if (!windowed) SDL_ShowCursor(SDL_DISABLE);
  glctx = SDL_GL_CreateContext(window);
  if (!glctx || !load_gl()) { fail("Horizon", "This computer's graphics do not support OpenGL 3.3."); return 1; }
  if (!overlay_init()) SDL_Log("no touch pad: its drawing could not be set up");
  SDL_GL_SetSwapInterval(1);
  { typedef const GLubyte *(APIENTRY *p_GetString)(GLenum); p_GetString gs = (p_GetString)SDL_GL_GetProcAddress("glGetString");
    if (gs) SDL_Log("OpenGL: %s / %s", (const char *)gs(GL_VERSION), (const char *)gs(GL_RENDERER)); }

  /* fixed settings: the reason this program exists */
#ifdef __ANDROID__
  /* phone and handheld GPUs: 4x is too much for some while the game loads (a handheld tested drops to 41 fps there,
   * 3x keeps 59), so a sharper picture is only the menu's choice */
  const int max_scale = 3;
#else
  const int max_scale = 8;
#endif
  settings_load();
  if (!scale) scale = settings_scale;   /* the menu's choice */
  if (!scale) { scale = (disp_h + 239) / 240; if (scale < 2) scale = 2; if (scale > max_scale) scale = max_scale; }
  snprintf(scale_text, sizeof scale_text, "%d", scale);
  static const char *fixed[][2] = {
    {"swanstation_BIOS_PathNTSCU", "openbios.bin"}, {"swanstation_BIOS_PathNTSCJ", "openbios.bin"},
    {"swanstation_BIOS_PathPAL", "openbios.bin"}, {"swanstation_BIOS_PatchFastBoot", "false"},
    {"swanstation_Console_Enable8MBRAM", "true"}, {"swanstation_CPU_Overclock", "250"},
    {"swanstation_GPU_Renderer", "OpenGL"}, {"swanstation_GPU_TrueColor", "false"},
    {"swanstation_MemoryCards_Card1Type", "Libretro"}, {"swanstation_MemoryCards_Card2Type", "None"},
    {"swanstation_Display_AspectRatio", "4:3"},
    /* the CD at 8x reads and 10x seeks: loads take half the time (the core keeps music and movie sound at 1x) */
    {"swanstation_CDROM_ReadSpeedup", "4"}, {"swanstation_CDROM_SeekSpeedup", "10"},
  };
  for (int i = (int)(sizeof fixed / sizeof *fixed) - 1; i >= 0; i--) {
    bool overridden = false;
    for (int j = 0; j < opt_count; j++) if (!strcmp(opt_key[j], fixed[i][0])) overridden = true;
    if (!overridden) set_option(fixed[i][0], fixed[i][1]);
  }
  {
#ifdef __ANDROID__
    static const int scales[] = {1, 2, 3, 4};
#else
    static const int scales[] = {1, 2, 3, 4, 6, 8};
#endif
    menu_set_scales(scales, (int)(sizeof scales / sizeof *scales), scale);
  }
  bool scale_set = false;
  for (int j = 0; j < opt_count; j++) if (!strcmp(opt_key[j], "swanstation_GPU_ResolutionScale")) scale_set = true;
  if (!scale_set) set_option("swanstation_GPU_ResolutionScale", scale_text);

  if (!load_core(core_path)) { fail("Horizon", "The emulator library is missing next to the program."); return 1; }
  core.set_environment(environment);
  core.init();
  core.set_video_refresh(video_refresh);
  core.set_audio_sample(audio_sample);
  core.set_audio_sample_batch(audio_batch);
  core.set_input_poll(input_poll);
  core.set_input_state(input_state);

  struct retro_game_info game = {disc, NULL, 0, NULL};
  if (!core.load_game(disc ? &game : NULL)) { fail("Horizon", "The disc could not be started. Is it the patched Horizon disc (.cue)?"); return 1; }
  core.get_system_av_info(&av);
  core.set_controller_port_device(0, RETRO_DEVICE_JOYPAD);
  snprintf(card_path, sizeof card_path, "%s/duckstation_shared_card_1.mcd", save_dir);
  card_load();
  controls_load(save_dir);
  if (hw_requested) {
    make_fbo(av.geometry.max_width, av.geometry.max_height);
    if (hw.context_reset) hw.context_reset();
  }
  snprintf(resume_path, sizeof resume_path, "%s/resume.state", save_dir);
  bool resumed = resume_load();   /* (after the context: the snapshot's video memory goes into it) */

  SDL_AudioSpec want = {0}, got;
  want.freq = av.timing.sample_rate > 0 ? (int)av.timing.sample_rate : 44100;
  want.format = AUDIO_S16SYS; want.channels = 2; want.samples = 1024;
  audio_dev = SDL_OpenAudioDevice(NULL, 0, &want, &got, 0);
  if (audio_dev) SDL_PauseAudioDevice(audio_dev, 0);

  controls_open_all();
  if (run_frames < 0 && !press_script) new_version_check();   /* (not in tests: no network) */
  /* the first start asks touch or controller (not in tests); the answer decides whether the touch pad shows */
  /* a new install on Android has no card: it may have a copy from before (HorizonActivity.backupCard) to import */
#ifdef __ANDROID__
  if (!card_existed && !resumed && run_frames < 0 && !press_script) ask_card = true;
#endif
  if (first_start || ask_card || (controls_mode == MODE_UNSET && run_frames < 0 && !press_script))
    menu_show_first(ask_card);
  touch_shown = force_touch || controls_mode == MODE_TOUCH;

  const Uint32 bytes_per_sec = (Uint32)want.freq * 4;
  /* the screen's refresh near the console's: the sound is stretched to it (audio_push) */
  double audio_base = 0;
  { SDL_DisplayMode m; double fps = av.timing.fps > 0 ? av.timing.fps : 59.82;
    if (audio_dev && SDL_GetWindowDisplayMode(window, &m) == 0 && m.refresh_rate > 0 && SDL_fabs(m.refresh_rate - fps) < 1.5)
      audio_base = fps / m.refresh_rate;
    SDL_Log("sound: %d Hz, %d-sample buffer, %s; screen %d Hz, %s", got.freq, got.samples, SDL_GetCurrentAudioDriver(),
            SDL_GetWindowDisplayMode(window, &m) == 0 ? m.refresh_rate : 0, audio_base ? "stretched to the screen" : "paced by the sound"); }
  int frame = 0;
  /* the start is black for about 15 seconds (OpenBIOS and the game loading): it runs unpaced and unseen until the
   * game's first picture after OpenBIOS's own screen, so it takes as long as the machine needs, not the console */
  booting = fast_start && run_frames < 0 && !resumed;
  game_started = resumed;
  Uint32 boot_ms = SDL_GetTicks();
  if (booting) SDL_GL_SetSwapInterval(0);
  int boot_frame = 0;
  while (!quit) {
    Uint32 loop_ms = SDL_GetTicks();
    handle_events();
    if (paused) { SDL_Delay(50); continue; }
    uint16_t bits = controls_bits() | (uint16_t)scripted_bits(frame);
    bits = controls_frame(bits);
    if ((controls_menu_asked || overlay_menu_tapped) && !menu_open && remap_step < 0) menu_show();
    /* a joystick SDL does not know, not set up before: its buttons are asked for at once (after the first start's
     * question), since its SELECT and START may not be where the menu expects them */
    if (controls_setup_wanted && !menu_open && remap_step < 0 && run_frames < 0 && !press_script) {
      controls_setup_wanted = false; controls_setup_start();
    }
    controls_menu_asked = overlay_menu_tapped = false;
    if (menu_open || remap_step >= 0) {   /* the game waits under the menu and the button setup */
      if (menu_open) {
        int a = menu_frame(bits);
        if (a != MENU_NONE) SDL_Log("menu: action %d", a);
        if (a == MENU_QUIT) quit = true;
        else if (a == MENU_TOUCH) { controls_set_mode(MODE_TOUCH); touch_shown = true; }
        else if (a == MENU_PAD) { controls_set_mode(MODE_PAD); touch_shown = false; }
        else if (a == MENU_SETUP) controls_setup_start();
        else if (a == MENU_SCALE) {   /* the core changes its resolution at once */
          snprintf(scale_text, sizeof scale_text, "%d", menu_scale);
          set_option("swanstation_GPU_ResolutionScale", scale_text);
          options_changed = true;
          settings_scale = menu_scale; settings_save();
        }
        else if (a == MENU_TOUCHPAD) settings_save();
        else if (a == MENU_EXPORT || a == MENU_IMPORT) card_action(a);
        else if (a == MENU_UPDATE) {   /* the website, where the patcher makes the new version from the player's disc */
          if (SDL_GetWindowFlags(window) & SDL_WINDOW_FULLSCREEN) SDL_MinimizeWindow(window);
          SDL_OpenURL("https://dw1horizon.com/");
        }
        card_poll();
      }
      pad_bits = 0;
      if (run_frames >= 0) frame++;   /* (tests: the scripted presses go on) */
      present(run_frames >= 0 && frame >= run_frames);
      if (run_frames >= 0 && frame >= run_frames) break;
      if (booting) SDL_Delay(15);   /* (no vsync while booting) */
      boot_ms += SDL_GetTicks() - loop_ms;   /* the start's time leaves out the time in the menu */
      continue;
    }
    if (restart_asked) {   /* a new memory card: the game starts again, fast, to read it */
      restart_asked = false;
      resume_drop();
      core.reset();
      booting = fast_start; boot_frame = frame; boot_ms = SDL_GetTicks();
      if (booting) SDL_GL_SetSwapInterval(0);
    }
    { int ww, wh; SDL_GL_GetDrawableSize(window, &ww, &wh); bits |= overlay_touch_bits(ww, wh); }
    pad_bits = bits;
    core.run();
    frame++;
    if (!booting) game_started = true;
    {   /* a newer release: asked every two seconds until the check answers (it may never: offline), then said once */
      static bool told; char tag[40];
      if (!told && !booting && !menu_open && remap_step < 0 && frame % 120 == 0 && new_version_found(tag, sizeof tag)) {
        told = true; overlay_set_new_version(tag); SDL_Log("a newer release: %s", tag); menu_show_update();
      }
    }
    if (frame == suspend_at) { resume_save(); paused = true; break; }   /* (tests: as if Android ended the app in the background) */
    if (frame % 60 == 0) card_save();
    {   /* the frame rate in the corner: the game's frames in the last second */
      static Uint32 fps_since; static int fps_frames; Uint32 now = SDL_GetTicks();
      if (!fps_since) fps_since = now;
      fps_frames++;
      if (now - fps_since >= 1000) { overlay_fps = (int)(fps_frames * 1000.0 / (now - fps_since) + 0.5); fps_since = now; fps_frames = 0; }
    }
    if (frame % 1800 == 0) {   /* the log notes the speed: a slow device shows here */
      static Uint32 since; Uint32 now = SDL_GetTicks(); int dw, dh; SDL_GL_GetDrawableSize(window, &dw, &dh);
      SDL_Log("frame %d: %.1f fps, picture %ux%u %s, screen %dx%d, scale %s", frame, since ? 1800000.0 / (now - since) : 0.0,
              frame_w, frame_h, !have_frame ? "none" : frame_is_hw ? "hw" : "sw", dw, dh, scale_text);
      since = now;
    }
    if (booting) {
      int f = frame - boot_frame;
      if ((f >= 400 && f % 4 == 0 && picture_lit()) || f >= 3000) {
        booting = false;
        SDL_GL_SetSwapInterval(1);
        SDL_Log("started: the first picture at frame %d, after %u ms", f, SDL_GetTicks() - boot_ms);
      } else {
        if (f % 20 == 0) present(false);   /* the window stays alive (and the touch pad drawn) */
        continue;
      }
    }
    /* Catching up. A slow frame (the game busy while it loads) costs a screen refresh and leaves the sound queue short
     * by a frame; then the next frame runs without being shown, so the game and its music keep their pace and the
     * screen holds its picture one refresh longer. The queue counts at its highest over the last three frames: the
     * sound device takes it in bites of about 23 ms, so a single reading swings that much. */
    if (audio_dev && run_frames < 0) {
      static Uint32 q_seen[3]; static int q_at; static bool skipped;
      q_seen[q_at++ % 3] = SDL_GetQueuedAudioSize(audio_dev);
      Uint32 top = SDL_max(q_seen[0], SDL_max(q_seen[1], q_seen[2]));
      if (!skipped && top < bytes_per_sec * 3 / 100) { skipped = true; continue; }
      skipped = false;
    }
    present(run_frames >= 0 && frame >= run_frames);
    if (run_frames >= 0 && frame >= run_frames) break;
    if (audio_dev && run_frames < 0) {
      if (audio_base) {   /* stretched: the queue steered towards 60 ms, at most 0.5 % either way */
        double target = (double)bytes_per_sec * 6 / 100, err = (target - (double)SDL_GetQueuedAudioSize(audio_dev)) / target;
        audio_ratio = audio_base * (1 + 0.005 * (err > 1 ? 1 : err < -1 ? -1 : err));
      }
      /* paced by the sound: never more than about 80 ms queued (stretched: only a guard, 200 ms) */
      while (SDL_GetQueuedAudioSize(audio_dev) > (audio_base ? bytes_per_sec / 5 : bytes_per_sec / 12) && !quit) SDL_Delay(1);
    }
  }

  card_save();
  if (!paused) resume_drop();   /* QUIT; an end while in the background (Android closing the app) keeps it */
  core.unload_game();
  core.deinit();
  if (audio_dev) SDL_CloseAudioDevice(audio_dev);
  SDL_GL_DeleteContext(glctx);
  SDL_DestroyWindow(window);
  SDL_Quit();
  return 0;
}
