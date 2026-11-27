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
static bool first_start;
static const char *press_script;                       /* --press "frame:button:len,..." (tests) */

#define MAX_OPTIONS 32
static const char *opt_key[MAX_OPTIONS], *opt_val[MAX_OPTIONS];
static int opt_count;
static char scale_text[8];

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
#ifndef _WIN32
#include <fcntl.h>
#include <unistd.h>
static char embedded_track[1200];
static const char *embedded_file;
static int64_t embedded_at, embedded_size;
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
  case RETRO_ENVIRONMENT_GET_VARIABLE_UPDATE: *(bool *)data = false; return true;
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
static void audio_sample(int16_t l, int16_t r) { int16_t s[2] = {l, r}; if (audio_dev && !booting) SDL_QueueAudio(audio_dev, s, sizeof s); }
static size_t audio_batch(const int16_t *d, size_t frames) {
  if (audio_dev && !booting) SDL_QueueAudio(audio_dev, d, (Uint32)(frames * 4));
  return frames;
}

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

static void toggle_fullscreen(void) {
  bool full = SDL_GetWindowFlags(window) & SDL_WINDOW_FULLSCREEN;
  SDL_SetWindowFullscreen(window, full ? 0 : SDL_WINDOW_FULLSCREEN_DESKTOP);
  SDL_ShowCursor(full ? SDL_ENABLE : SDL_DISABLE);
}

static void card_save(void);
static void card_import(const char *path);

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
      else if (e.key.keysym.sym == SDLK_ESCAPE && (SDL_GetWindowFlags(window) & SDL_WINDOW_FULLSCREEN)) toggle_fullscreen();
      break;
    case SDL_DROPFILE:   /* a memory card dropped on the window, while the menu waits for one */
      if (menu_waiting_drop()) card_import(e.drop.file);
      SDL_free(e.drop.file);
      break;
    case SDL_WINDOWEVENT:
      if (e.window.event == SDL_WINDOWEVENT_MINIMIZED) paused = true;
      else if (e.window.event == SDL_WINDOWEVENT_RESTORED || e.window.event == SDL_WINDOWEVENT_SHOWN) paused = false;
      break;
    case SDL_APP_WILLENTERBACKGROUND: paused = true; card_save(); break;
    case SDL_APP_TERMINATING: card_save(); break;
    case SDL_APP_DIDENTERFOREGROUND: paused = false; break;
    }
  }
}

/* ---- the memory card: the core's "Libretro" card is a 128 KB buffer this program keeps in the save folder, in the
 * file DuckStation's shared card uses. It is written whenever it changes (checked every second), when the app goes to
 * the background and at exit, so a closed window or an app Android kills keeps the last save. */
static char card_path[1200];
static uint8_t card_written[128 * 1024];

static void card_load(void) {
  uint8_t *data = core.get_memory_data(RETRO_MEMORY_SAVE_RAM);
  size_t size = core.get_memory_size(RETRO_MEMORY_SAVE_RAM);
  if (!data || size != sizeof card_written) return;
  SDL_RWops *f = SDL_RWFromFile(card_path, "rb");
  if (f) {
    if (SDL_RWread(f, card_written, 1, size) == size) memcpy(data, card_written, size);
    SDL_RWclose(f);
  }
  memcpy(card_written, data, size);
}

static void card_save(void) {
  uint8_t *data = core.get_memory_data(RETRO_MEMORY_SAVE_RAM);
  size_t size = core.get_memory_size(RETRO_MEMORY_SAVE_RAM);
  if (!data || size != sizeof card_written || !memcmp(data, card_written, size)) return;
  /* the whole card in one write to a fresh file, then over the old one: a cut in the middle keeps the old card */
  char tmp[1300]; snprintf(tmp, sizeof tmp, "%s.new", card_path);
  SDL_RWops *f = SDL_RWFromFile(tmp, "wb");
  if (!f) { SDL_Log("cannot write %s", tmp); return; }
  bool ok = SDL_RWwrite(f, data, 1, size) == size;
  ok = SDL_RWclose(f) == 0 && ok;
  if (ok && replace_file(tmp, card_path)) memcpy(card_written, data, size);
  else SDL_Log("cannot save the memory card %s", card_path);
}

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
  card_save();
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
  return true;
}

static void fail(const char *title, const char *msg) {
  SDL_Log("%s: %s", title, msg);
  SDL_ShowSimpleMessageBox(SDL_MESSAGEBOX_ERROR, title, msg, window);
}

int main(int argc, char **argv) {
  const char *disc = NULL, *core_path = NULL, *sys = NULL, *saves = NULL;
  bool windowed = false, no_disc = false; int scale = 0, force_w = 0, force_h = 0;
  for (int i = 1; i < argc; i++) {
    if (!strcmp(argv[i], "--windowed")) windowed = true;
    else if (!strcmp(argv[i], "--window") && i + 1 < argc) {   /* --window WxH: a window of that size (tests) */
      windowed = sscanf(argv[++i], "%dx%d", &force_w, &force_h) == 2;
    }
    else if (!strcmp(argv[i], "--no-disc")) no_disc = true;               /* the BIOS alone (a smoke test) */
    else if (!strcmp(argv[i], "--touch")) force_touch = true;            /* the touch pad from the start */
    else if (!strcmp(argv[i], "--first-start")) first_start = true;      /* the first start's question, in tests too */
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
    SDL_RWops *f = SDL_RWFromFile(last_file, "rb");
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
  const int max_scale = 4;    /* phone and handheld GPUs */
#else
  const int max_scale = 8;
#endif
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

  SDL_AudioSpec want = {0}, got;
  want.freq = av.timing.sample_rate > 0 ? (int)av.timing.sample_rate : 44100;
  want.format = AUDIO_S16SYS; want.channels = 2; want.samples = 1024;
  audio_dev = SDL_OpenAudioDevice(NULL, 0, &want, &got, 0);
  if (audio_dev) SDL_PauseAudioDevice(audio_dev, 0);

  controls_open_all();
  /* the first start asks touch or controller (not in tests); the answer decides whether the touch pad shows */
  if (first_start || (controls_mode == MODE_UNSET && run_frames < 0 && !press_script)) menu_show_first();
  touch_shown = force_touch || controls_mode == MODE_TOUCH;

  const Uint32 bytes_per_sec = (Uint32)want.freq * 4;
  int frame = 0;
  /* the start is black for about 15 seconds (OpenBIOS and the game loading): it runs unpaced and unseen until the
   * game's first picture after OpenBIOS's own screen, so it takes as long as the machine needs, not the console */
  booting = fast_start && run_frames < 0;
  Uint32 boot_ms = SDL_GetTicks();
  if (booting) SDL_GL_SetSwapInterval(0);
  int boot_frame = 0;
  while (!quit) {
    handle_events();
    if (paused) { SDL_Delay(50); continue; }
    uint16_t bits = controls_bits() | (uint16_t)scripted_bits(frame);
    bits = controls_frame(bits);
    if ((controls_menu_asked || overlay_menu_tapped) && !menu_open && remap_step < 0) menu_show();
    controls_menu_asked = overlay_menu_tapped = false;
    if (menu_open || remap_step >= 0) {   /* the game waits under the menu and the button setup */
      if (menu_open) {
        int a = menu_frame(bits);
        if (a == MENU_QUIT) quit = true;
        else if (a == MENU_TOUCH) { controls_set_mode(MODE_TOUCH); touch_shown = true; }
        else if (a == MENU_PAD) { controls_set_mode(MODE_PAD); touch_shown = false; }
        else if (a == MENU_SETUP) controls_setup_start();
        else if (a == MENU_EXPORT || a == MENU_IMPORT) card_action(a);
        card_poll();
      }
      pad_bits = 0;
      if (run_frames >= 0) frame++;   /* (tests: the scripted presses go on) */
      present(run_frames >= 0 && frame >= run_frames);
      if (run_frames >= 0 && frame >= run_frames) break;
      if (booting) SDL_Delay(15);   /* (no vsync while booting) */
      continue;
    }
    if (restart_asked) {   /* a new memory card: the game starts again, fast, to read it */
      restart_asked = false;
      core.reset();
      booting = fast_start; boot_frame = frame; boot_ms = SDL_GetTicks();
      if (booting) SDL_GL_SetSwapInterval(0);
    }
    { int ww, wh; SDL_GL_GetDrawableSize(window, &ww, &wh); bits |= overlay_touch_bits(ww, wh); }
    pad_bits = bits;
    core.run();
    frame++;
    if (frame % 60 == 0) card_save();
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
    present(run_frames >= 0 && frame >= run_frames);
    if (run_frames >= 0 && frame >= run_frames) break;
    /* the sound sets the pace: never more than about 80 ms queued */
    if (audio_dev && run_frames < 0)
      while (SDL_GetQueuedAudioSize(audio_dev) > bytes_per_sec / 12 && !quit) SDL_Delay(1);
  }

  card_save();
  core.unload_game();
  core.deinit();
  if (audio_dev) SDL_CloseAudioDevice(audio_dev);
  SDL_GL_DeleteContext(glctx);
  SDL_DestroyWindow(window);
  SDL_Quit();
  return 0;
}
