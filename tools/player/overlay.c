/* Horizon Play's own drawing over the game (docs/player.md): the touch pad, the prompts of the button setup and the
 * pictures of the menu (menu.c). Everything is drawn at start into one texture (shapes from distance functions, a 5x7
 * font), then each frame as quads with one small shader. The core keeps its own GL state cached, so every piece of
 * state touched here is put back as it was. MIT, like the rest of Horizon's code.
 */
#include "overlay.h"
#include "controls.h"
#include "menu.h"
#include <math.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include "libretro.h"

#ifdef HORIZON_GLES
#include <SDL_opengles2.h>
#else
#include <SDL_opengl.h>
#endif
#ifndef APIENTRY
#define APIENTRY
#endif
#ifndef GL_VERTEX_ARRAY_BINDING
#define GL_VERTEX_ARRAY_BINDING 0x85B5
#endif

/* ---- the GL calls this file makes ---- */
typedef GLuint(APIENTRY *o_CreateShader)(GLenum);
typedef void(APIENTRY *o_ShaderSource)(GLuint, GLsizei, const GLchar *const *, const GLint *);
typedef void(APIENTRY *o_CompileShader)(GLuint);
typedef void(APIENTRY *o_GetShaderiv)(GLuint, GLenum, GLint *);
typedef void(APIENTRY *o_GetShaderInfoLog)(GLuint, GLsizei, GLsizei *, GLchar *);
typedef GLuint(APIENTRY *o_CreateProgram)(void);
typedef void(APIENTRY *o_AttachShader)(GLuint, GLuint);
typedef void(APIENTRY *o_BindAttribLocation)(GLuint, GLuint, const GLchar *);
typedef void(APIENTRY *o_LinkProgram)(GLuint);
typedef void(APIENTRY *o_GetProgramiv)(GLuint, GLenum, GLint *);
typedef void(APIENTRY *o_UseProgram)(GLuint);
typedef GLint(APIENTRY *o_GetUniformLocation)(GLuint, const GLchar *);
typedef void(APIENTRY *o_Uniform1i)(GLint, GLint);
typedef void(APIENTRY *o_GenVertexArrays)(GLsizei, GLuint *);
typedef void(APIENTRY *o_BindVertexArray)(GLuint);
typedef void(APIENTRY *o_GenBuffers)(GLsizei, GLuint *);
typedef void(APIENTRY *o_BindBuffer)(GLenum, GLuint);
typedef void(APIENTRY *o_BufferData)(GLenum, GLsizeiptr, const void *, GLenum);
typedef void(APIENTRY *o_VertexAttribPointer)(GLuint, GLint, GLenum, GLboolean, GLsizei, const void *);
typedef void(APIENTRY *o_EnableVertexAttribArray)(GLuint);
typedef void(APIENTRY *o_DrawArrays)(GLenum, GLint, GLsizei);
typedef void(APIENTRY *o_Enable)(GLenum);
typedef void(APIENTRY *o_Disable)(GLenum);
typedef GLboolean(APIENTRY *o_IsEnabled)(GLenum);
typedef void(APIENTRY *o_BlendFuncSeparate)(GLenum, GLenum, GLenum, GLenum);
typedef void(APIENTRY *o_BlendEquationSeparate)(GLenum, GLenum);
typedef void(APIENTRY *o_GetIntegerv)(GLenum, GLint *);
typedef void(APIENTRY *o_ActiveTexture)(GLenum);
typedef void(APIENTRY *o_GenTextures)(GLsizei, GLuint *);
typedef void(APIENTRY *o_BindTexture)(GLenum, GLuint);
typedef void(APIENTRY *o_TexImage2D)(GLenum, GLint, GLint, GLsizei, GLsizei, GLint, GLenum, GLenum, const void *);
typedef void(APIENTRY *o_TexParameteri)(GLenum, GLenum, GLint);
typedef void(APIENTRY *o_PixelStorei)(GLenum, GLint);
typedef void(APIENTRY *o_ColorMask)(GLboolean, GLboolean, GLboolean, GLboolean);

static struct {
  o_CreateShader CreateShader; o_ShaderSource ShaderSource; o_CompileShader CompileShader; o_GetShaderiv GetShaderiv;
  o_GetShaderInfoLog GetShaderInfoLog; o_CreateProgram CreateProgram; o_AttachShader AttachShader;
  o_BindAttribLocation BindAttribLocation; o_LinkProgram LinkProgram; o_GetProgramiv GetProgramiv;
  o_UseProgram UseProgram; o_GetUniformLocation GetUniformLocation; o_Uniform1i Uniform1i;
  o_GenVertexArrays GenVertexArrays; o_BindVertexArray BindVertexArray; o_GenBuffers GenBuffers;
  o_BindBuffer BindBuffer; o_BufferData BufferData; o_VertexAttribPointer VertexAttribPointer;
  o_EnableVertexAttribArray EnableVertexAttribArray; o_DrawArrays DrawArrays; o_Enable Enable; o_Disable Disable;
  o_IsEnabled IsEnabled; o_BlendFuncSeparate BlendFuncSeparate; o_BlendEquationSeparate BlendEquationSeparate;
  o_GetIntegerv GetIntegerv; o_ActiveTexture ActiveTexture; o_GenTextures GenTextures; o_BindTexture BindTexture;
  o_TexImage2D TexImage2D; o_TexParameteri TexParameteri; o_PixelStorei PixelStorei; o_ColorMask ColorMask;
} g;

static GLuint program, vao, vbo, atlas;
static bool ready;

/* ---- the atlas: 1024 x 1024, premultiplied RGBA ---- */
#define AW 1024
#define AH 2048
static uint8_t *pix;

typedef struct { int x, y, w, h; } Cell;
static Cell cells[I_COUNT] = {
  [I_TRI] = {0, 0, 128, 128}, [I_CIRCLE] = {128, 0, 128, 128}, [I_CROSS] = {256, 0, 128, 128},
  [I_SQUARE] = {384, 0, 128, 128}, [I_UP] = {0, 128, 128, 128}, [I_DOWN] = {128, 128, 128, 128},
  [I_LEFT] = {256, 128, 128, 128}, [I_RIGHT] = {384, 128, 128, 128}, [I_DPAD] = {512, 0, 256, 256},
  [I_L1] = {0, 256, 192, 80}, [I_L2] = {192, 256, 192, 80}, [I_R1] = {384, 256, 192, 80}, [I_R2] = {576, 256, 192, 80},
  [I_SELECT] = {0, 336, 192, 80}, [I_START] = {192, 336, 192, 80}, [I_PANEL] = {768, 0, 64, 64},
  [I_DOT] = {832, 0, 32, 32}, [I_WHITE] = {872, 8, 16, 16}, [I_MENU] = {768, 96, 128, 128},
  /* the menu's pictures, 160 x 160 */
  [I_PLAY] = {0, 416, 160, 160}, [I_GAMEPAD] = {160, 416, 160, 160}, [I_CARD] = {320, 416, 160, 160},
  [I_POWER] = {480, 416, 160, 160}, [I_TOUCH] = {640, 416, 160, 160}, [I_KEYBOARD] = {800, 416, 160, 160},
  [I_CHECK] = {0, 576, 160, 160}, [I_FAIL] = {160, 576, 160, 160}, [I_PENCIL] = {320, 576, 160, 160},
  [I_EXPORT] = {480, 576, 160, 160}, [I_IMPORT] = {640, 576, 160, 160}, [I_BACK] = {800, 576, 160, 160},
  [I_DROP] = {0, 736, 160, 160}, [I_GEAR] = {160, 736, 160, 160}, [I_SCREEN] = {320, 736, 160, 160},
  /* the words (T_): 256, 512 or 1024 x 56 by their length, in rows from y = 1024, set in draw_words */
};

#define WORD_SCALE 6   /* one font dot is 6 x 6 atlas pixels: letters 42 high */
#ifndef HORIZON_VERSION
#define HORIZON_VERSION "DEV"   /* build.py and build_apk.py give the release version (tools/version.py) */
#endif
static char version_word[40];   /* "V0.0.10", in capitals: the font has no small letters */
static struct { int id; const char *s; } words[] = {
  {T_RESUME, "RESUME"}, {T_CONTROLS, "CONTROLS"}, {T_CARD, "MEMORY CARD"}, {T_QUIT, "QUIT"},
  {T_TOUCH, "TOUCH SCREEN"}, {T_CONTROLLER, "CONTROLLER"}, {T_KEEP, "KEEP BUTTONS"}, {T_SET, "SET BUTTONS"},
  {T_EXPORT, "EXPORT"}, {T_IMPORT, "IMPORT"}, {T_DONE, "DONE"}, {T_FAILED, "FAILED"},
  {T_DROP, "DROP A MEMORY CARD FILE HERE"}, {T_NEW, "NEW GAME"}, {T_SETTINGS, "SETTINGS"},
  {T_RESOLUTION, "RESOLUTION"}, {T_ORIGINAL, "ORIGINAL"}, {T_1X, "1X"}, {T_2X, "2X"}, {T_3X, "3X"}, {T_4X, "4X"},
  {T_6X, "6X"}, {T_8X, "8X"}, {T_480P, "480P"}, {T_720P, "720P"}, {T_960P, "960P"}, {T_1440P, "1440P"},
  {T_1920P, "1920P"},
  {T_D0, "0"}, {T_D0 + 1, "1"}, {T_D0 + 2, "2"}, {T_D0 + 3, "3"}, {T_D0 + 4, "4"}, {T_D0 + 5, "5"},
  {T_D0 + 6, "6"}, {T_D0 + 7, "7"}, {T_D0 + 8, "8"}, {T_D0 + 9, "9"}, {T_FPS, "FPS"},
  {T_VERSION, version_word}, {T_BUTTON_SIZE, "BUTTON SIZE"}, {T_OPACITY, "OPACITY"}, {T_SMALL, "SMALL"},
  {T_MEDIUM, "MEDIUM"}, {T_LARGE, "LARGE"}, {T_HUGE, "HUGE"}, {T_FAINT, "FAINT"}, {T_LIGHT, "LIGHT"},
  {T_SOLID, "SOLID"}, {T_FULL, "FULL"},
};
static float word_w[I_COUNT];   /* the letters' width in atlas pixels */

static float clampf(float v, float lo, float hi) { return v < lo ? lo : v > hi ? hi : v; }

/* paints colour (r,g,b,a) over the cell wherever the distance function is negative, antialiased */
typedef float (*Sdf)(float x, float y, const float *p);
static void paint(Cell c, Sdf f, const float *p, float r, float gg, float b, float a) {
  for (int y = 0; y < c.h; y++)
    for (int x = 0; x < c.w; x++) {
      float cov = clampf(0.5f - f(x + 0.5f, y + 0.5f, p), 0, 1) * a;
      if (cov <= 0) continue;
      uint8_t *d = pix + ((size_t)(c.y + y) * AW + c.x + x) * 4;
      float k = 1 - cov;
      d[0] = (uint8_t)(r * 255 * cov + d[0] * k); d[1] = (uint8_t)(gg * 255 * cov + d[1] * k);
      d[2] = (uint8_t)(b * 255 * cov + d[2] * k); d[3] = (uint8_t)(255 * cov + d[3] * k);
    }
}

static float seg(float x, float y, float ax, float ay, float bx, float by) {
  float px = x - ax, py = y - ay, dx = bx - ax, dy = by - ay;
  float t = clampf((px * dx + py * dy) / (dx * dx + dy * dy), 0, 1);
  return hypotf(px - dx * t, py - dy * t);
}
/* p: cx cy r */
static float sd_disc(float x, float y, const float *p) { return hypotf(x - p[0], y - p[1]) - p[2]; }
/* p: cx cy r width */
static float sd_ring(float x, float y, const float *p) { return fabsf(hypotf(x - p[0], y - p[1]) - p[2]) - p[3] / 2; }
/* p: cx cy hw hh radius */
static float sd_rbox(float x, float y, const float *p) {
  float qx = fabsf(x - p[0]) - p[2] + p[4], qy = fabsf(y - p[1]) - p[3] + p[4];
  return hypotf(fmaxf(qx, 0), fmaxf(qy, 0)) + fminf(fmaxf(qx, qy), 0) - p[4];
}
/* p: cx cy hw hh radius width: the outline of a rounded box */
static float sd_rbox_line(float x, float y, const float *p) { return fabsf(sd_rbox(x, y, p)) - p[5] / 2; }
/* p: cx cy long short radius: a plus sign made of two rounded boxes */
static float sd_cross(float x, float y, const float *p) {
  float h[] = {p[0], p[1], p[2], p[3], p[4]}, v[] = {p[0], p[1], p[3], p[2], p[4]};
  return fminf(sd_rbox(x, y, h), sd_rbox(x, y, v));
}
/* p: as sd_cross, then the line width */
static float sd_cross_line(float x, float y, const float *p) { return fabsf(sd_cross(x, y, p)) - p[5] / 2; }
/* p: n, then n points (x,y) of a closed polyline, then its width */
static float sd_poly_line(float x, float y, const float *p) {
  int n = (int)p[0]; const float *v = p + 1; float d = 1e9f;
  for (int i = 0; i < n; i++) {
    int j = (i + 1) % n;
    d = fminf(d, seg(x, y, v[2 * i], v[2 * i + 1], v[2 * j], v[2 * j + 1]));
  }
  return d - v[2 * n] / 2;
}
/* p: n, then n points of a convex polygon in clockwise or anticlockwise order: filled */
static float sd_poly_fill(float x, float y, const float *p) {
  int n = (int)p[0]; const float *v = p + 1; float d = -1e9f; float area = 0;
  for (int i = 0; i < n; i++) { int j = (i + 1) % n; area += v[2 * i] * v[2 * j + 1] - v[2 * j] * v[2 * i + 1]; }
  float s = area > 0 ? 1.0f : -1.0f;
  for (int i = 0; i < n; i++) {
    int j = (i + 1) % n;
    float ex = v[2 * j] - v[2 * i], ey = v[2 * j + 1] - v[2 * i + 1], len = hypotf(ex, ey);
    float nd = s * ((x - v[2 * i]) * ey - (y - v[2 * i + 1]) * ex) / len;   /* outward distance */
    d = fmaxf(d, nd);
  }
  return d;
}
/* p: x0 y0 x1 y1 width: one stroke */
static float sd_seg(float x, float y, const float *p) { return seg(x, y, p[0], p[1], p[2], p[3]) - p[4] / 2; }
/* p: cx cy r width, the gap's middle angle and half width (radians): a ring with an opening */
static float sd_arc(float x, float y, const float *p) {
  float d = atan2f(y - p[1], x - p[0]) - p[4];
  while (d > 3.1415927f) d -= 6.2831853f;
  while (d < -3.1415927f) d += 6.2831853f;
  if (fabsf(d) > p[5]) return fabsf(hypotf(x - p[0], y - p[1]) - p[2]) - p[3] / 2;
  float e1 = p[4] + p[5], e2 = p[4] - p[5];
  return fminf(hypotf(x - p[0] - cosf(e1) * p[2], y - p[1] - sinf(e1) * p[2]),
               hypotf(x - p[0] - cosf(e2) * p[2], y - p[1] - sinf(e2) * p[2])) - p[3] / 2;
}
/* p: cx cy: a controller's outline (a body and two grips) */
static float sd_gamepad(float x, float y, const float *p) {
  float body[] = {p[0], p[1], 62, 28, 26}, g1[] = {p[0] - 42, p[1] + 20, 22}, g2[] = {p[0] + 42, p[1] + 20, 22};
  return fabsf(fminf(sd_rbox(x, y, body), fminf(sd_disc(x, y, g1), sd_disc(x, y, g2)))) - 4.5f;
}

/* p: cx cy: a cog, eight teeth round a ring */
static float sd_gear(float x, float y, const float *p) {
  float dx = x - p[0], dy = y - p[1], a = atan2f(dy, dx), r = hypotf(dx, dy);
  float k = fmodf(a + 6.2831853f + 0.3926991f, 0.7853982f) - 0.3926991f;   /* angle from the nearest tooth's middle */
  float tx = cosf(k) * r, ty = sinf(k) * r;                                /* the point turned onto that tooth */
  float tooth[] = {58, 0, 12, 11, 3}, ring[] = {0, 0, 47};
  float body = fminf(sd_disc(tx, ty, ring), sd_rbox(tx, ty, tooth));
  return fmaxf(body, 20 - r);   /* the hole */
}

/* strokes of a picture: n segments (x0 y0 x1 y1), all of one width and colour */
static void strokes(Cell c, const float *v, int n, float w, float r, float gg, float b) {
  for (int i = 0; i < n; i++) {
    float s[] = {v[4 * i], v[4 * i + 1], v[4 * i + 2], v[4 * i + 3], w};
    paint(c, sd_seg, s, r, gg, b, 1);
  }
}

static void draw_menu_pictures(void) {
  const float L = 0.95f;   /* the pictures are near white: the menu tints them */
  { Cell c = cells[I_PLAY]; float t[] = {3, 56, 38, 56, 122, 124, 80}; paint(c, sd_poly_fill, t, L, L, L, 1); }
  { Cell c = cells[I_GAMEPAD]; float o[] = {80, 76}; paint(c, sd_gamepad, o, L, L, L, 1);
    float x[] = {50, 74, 14, 5, 2}; paint(c, sd_cross, x, L, L, L, 1);
    float b[][3] = {{110, 63, 6}, {110, 85, 6}, {99, 74, 6}, {121, 74, 6}};
    for (int i = 0; i < 4; i++) paint(c, sd_disc, b[i], L, L, L, 1); }
  { Cell c = cells[I_CARD]; float o[] = {80, 80, 44, 60, 9, 9}; paint(c, sd_rbox_line, o, L, L, L, 1);
    float lab[] = {80, 62, 26, 20, 4, 5}; paint(c, sd_rbox_line, lab, L, L, L, 1);
    for (int i = 0; i < 5; i++) { float s[] = {58 + i * 11.0f, 108, 58 + i * 11.0f, 124, 5}; paint(c, sd_seg, s, L, L, L, 1); } }
  { Cell c = cells[I_POWER]; float a[] = {80, 88, 42, 11, -1.5707963f, 0.62f}; paint(c, sd_arc, a, L, L, L, 1);
    float s[] = {80, 28, 80, 80, 11}; paint(c, sd_seg, s, L, L, L, 1); }
  { Cell c = cells[I_TOUCH]; float o[] = {80, 80, 38, 64, 11, 9}; paint(c, sd_rbox_line, o, L, L, L, 1);
    float sp[] = {70, 30, 90, 30, 5}; paint(c, sd_seg, sp, L, L, L, 1);
    float d[] = {80, 82, 10}, r[] = {80, 82, 22, 4}; paint(c, sd_disc, d, L, L, L, 1); paint(c, sd_ring, r, L, L, L, 0.7f); }
  { Cell c = cells[I_KEYBOARD]; float o[] = {80, 80, 68, 38, 8, 8}; paint(c, sd_rbox_line, o, L, L, L, 1);
    for (int row = 0; row < 2; row++)
      for (int k = 0; k < 7; k++) { float b[] = {35 + k * 15.0f, 62 + row * 16.0f, 5, 5, 1.5f}; paint(c, sd_rbox, b, L, L, L, 1); }
    float sp[] = {80, 98, 30, 5, 2}; paint(c, sd_rbox, sp, L, L, L, 1); }
  { float v[] = {40, 84, 68, 112, 68, 112, 122, 50}; strokes(cells[I_CHECK], v, 2, 16, 0.45f, 0.95f, 0.55f); }
  { float v[] = {46, 46, 114, 114, 114, 46, 46, 114}; strokes(cells[I_FAIL], v, 2, 16, 1, 0.45f, 0.45f); }
  { Cell c = cells[I_PENCIL]; float s[] = {62, 98, 116, 44, 24}; paint(c, sd_seg, s, L, L, L, 1);
    float t[] = {3, 46.5f, 96.5f, 63.5f, 113.5f, 38, 122}; paint(c, sd_poly_fill, t, L, L, L, 1); }
  { float v[] = {36, 92, 36, 124, 36, 124, 124, 124, 124, 124, 124, 92, 80, 104, 80, 30, 56, 54, 80, 30, 80, 30, 104, 54};
    strokes(cells[I_EXPORT], v, 6, 10, L, L, L); }
  { float v[] = {36, 92, 36, 124, 36, 124, 124, 124, 124, 124, 124, 92, 80, 26, 80, 102, 56, 78, 80, 102, 80, 102, 104, 78};
    strokes(cells[I_IMPORT], v, 6, 10, L, L, L); }
  { float v[] = {120, 80, 42, 80, 70, 52, 42, 80, 42, 80, 70, 108}; strokes(cells[I_BACK], v, 3, 12, L, L, L); }
  { Cell c = cells[I_DROP]; float o[] = {80, 100, 64, 44, 8, 8}; paint(c, sd_rbox_line, o, L, L, L, 1);
    float bar[] = {20, 76, 140, 76, 5}; paint(c, sd_seg, bar, L, L, L, 0.6f);
    float v[] = {80, 14, 80, 110, 60, 90, 80, 110, 80, 110, 100, 90}; strokes(c, v, 3, 10, L, L, L); }
  { Cell c = cells[I_GEAR]; float o[] = {80, 80}; paint(c, sd_gear, o, L, L, L, 1); }
  { Cell c = cells[I_SCREEN]; float o[] = {80, 70, 64, 44, 8, 9}; paint(c, sd_rbox_line, o, L, L, L, 1);
    float v[] = {80, 114, 80, 132, 52, 134, 108, 134}; strokes(c, v, 2, 9, L, L, L); }
}

/* a round button: dark disc, light rim */
static void button_base(Cell c) {
  float d[] = {c.w / 2.0f, c.h / 2.0f, c.w / 2.0f - 6}, ring[] = {c.w / 2.0f, c.h / 2.0f, c.w / 2.0f - 7, 4};
  paint(c, sd_disc, d, 0.08f, 0.08f, 0.1f, 0.55f);
  paint(c, sd_ring, ring, 1, 1, 1, 0.7f);
}

static void arrow(Cell c, float angle) {
  float cx = c.w / 2.0f, cy = c.h / 2.0f, r = 26, ca = cosf(angle), sa = sinf(angle);
  float pts[] = {3, cx + ca * r, cy + sa * r, cx - ca * r * 0.6f - sa * r, cy - sa * r * 0.6f + ca * r,
                 cx - ca * r * 0.6f + sa * r, cy - sa * r * 0.6f - ca * r};
  paint(c, sd_poly_fill, pts, 0.92f, 0.92f, 0.95f, 0.95f);
}

/* 5x7 font: capitals, digits and / . - + */
static const struct { char ch; uint8_t rows[7]; } font[] = {
  {'A', {0x0E, 0x11, 0x11, 0x1F, 0x11, 0x11, 0x11}}, {'B', {0x1E, 0x11, 0x11, 0x1E, 0x11, 0x11, 0x1E}},
  {'C', {0x0E, 0x11, 0x10, 0x10, 0x10, 0x11, 0x0E}}, {'D', {0x1E, 0x11, 0x11, 0x11, 0x11, 0x11, 0x1E}},
  {'E', {0x1F, 0x10, 0x10, 0x1E, 0x10, 0x10, 0x1F}}, {'F', {0x1F, 0x10, 0x10, 0x1E, 0x10, 0x10, 0x10}},
  {'G', {0x0E, 0x11, 0x10, 0x17, 0x11, 0x11, 0x0F}}, {'H', {0x11, 0x11, 0x11, 0x1F, 0x11, 0x11, 0x11}},
  {'I', {0x0E, 0x04, 0x04, 0x04, 0x04, 0x04, 0x0E}}, {'J', {0x07, 0x02, 0x02, 0x02, 0x02, 0x12, 0x0C}},
  {'K', {0x11, 0x12, 0x14, 0x18, 0x14, 0x12, 0x11}}, {'L', {0x10, 0x10, 0x10, 0x10, 0x10, 0x10, 0x1F}},
  {'M', {0x11, 0x1B, 0x15, 0x15, 0x11, 0x11, 0x11}}, {'N', {0x11, 0x11, 0x19, 0x15, 0x13, 0x11, 0x11}},
  {'O', {0x0E, 0x11, 0x11, 0x11, 0x11, 0x11, 0x0E}}, {'P', {0x1E, 0x11, 0x11, 0x1E, 0x10, 0x10, 0x10}},
  {'Q', {0x0E, 0x11, 0x11, 0x11, 0x15, 0x12, 0x0D}}, {'R', {0x1E, 0x11, 0x11, 0x1E, 0x14, 0x12, 0x11}},
  {'S', {0x0F, 0x10, 0x10, 0x0E, 0x01, 0x01, 0x1E}}, {'T', {0x1F, 0x04, 0x04, 0x04, 0x04, 0x04, 0x04}},
  {'U', {0x11, 0x11, 0x11, 0x11, 0x11, 0x11, 0x0E}}, {'V', {0x11, 0x11, 0x11, 0x11, 0x11, 0x0A, 0x04}},
  {'W', {0x11, 0x11, 0x11, 0x15, 0x15, 0x15, 0x0A}}, {'X', {0x11, 0x11, 0x0A, 0x04, 0x0A, 0x11, 0x11}},
  {'Y', {0x11, 0x11, 0x0A, 0x04, 0x04, 0x04, 0x04}}, {'Z', {0x1F, 0x01, 0x02, 0x04, 0x08, 0x10, 0x1F}},
  {'0', {0x0E, 0x11, 0x13, 0x15, 0x19, 0x11, 0x0E}},
  {'1', {0x04, 0x0C, 0x04, 0x04, 0x04, 0x04, 0x0E}}, {'2', {0x0E, 0x11, 0x01, 0x02, 0x04, 0x08, 0x1F}},
  {'3', {0x1F, 0x02, 0x04, 0x02, 0x01, 0x11, 0x0E}}, {'4', {0x02, 0x06, 0x0A, 0x12, 0x1F, 0x02, 0x02}},
  {'5', {0x1F, 0x10, 0x1E, 0x01, 0x01, 0x11, 0x0E}}, {'6', {0x06, 0x08, 0x10, 0x1E, 0x11, 0x11, 0x0E}},
  {'7', {0x1F, 0x01, 0x02, 0x04, 0x08, 0x08, 0x08}}, {'8', {0x0E, 0x11, 0x11, 0x0E, 0x11, 0x11, 0x0E}},
  {'9', {0x0E, 0x11, 0x11, 0x0F, 0x01, 0x02, 0x0C}},
  {'/', {0x01, 0x02, 0x02, 0x04, 0x08, 0x08, 0x10}}, {'.', {0x00, 0x00, 0x00, 0x00, 0x00, 0x0C, 0x0C}},
  {'-', {0x00, 0x00, 0x00, 0x1F, 0x00, 0x00, 0x00}}, {'+', {0x00, 0x04, 0x04, 0x1F, 0x04, 0x04, 0x00}},
};

static const uint8_t *glyph(char ch) {
  for (size_t f = 0; f < sizeof font / sizeof *font; f++) if (font[f].ch == ch) return font[f].rows;
  return NULL;
}

/* the font's dots for s, scale atlas pixels each, from (x0, y0) in c; each dot painted over its own few pixels */
static void dots(Cell c, const char *s, int scale, int x0, int y0) {
  for (int i = 0; s[i]; i++) {
    const uint8_t *g = glyph(s[i]);
    if (!g) continue;
    for (int row = 0; row < 7; row++)
      for (int col = 0; col < 5; col++)
        if (g[row] & (0x10 >> col)) {
          int dx = x0 + (i * 6 + col) * scale, dy = y0 + row * scale;
          Cell d = {c.x + dx - 2, c.y + dy - 2, scale + 4, scale + 4};
          float b[] = {scale / 2.0f + 2, scale / 2.0f + 2, scale / 2.0f + 0.3f, scale / 2.0f + 0.3f, scale * 0.2f};
          paint(d, sd_rbox, b, 0.95f, 0.95f, 0.97f, 1);
        }
  }
}

static void draw_words(void) {
  int x = 0, y = 1024;
  snprintf(version_word, sizeof version_word, "V%s", HORIZON_VERSION);
  for (char *p = version_word; *p; p++) *p = (char)SDL_toupper((unsigned char)*p);
  for (size_t i = 0; i < sizeof words / sizeof *words; i++) {
    int n = (int)strlen(words[i].s), id = words[i].id, tw = n * 6 * WORD_SCALE;
    int w = tw > 500 ? 1024 : tw > 240 ? 512 : 256;
    if (x + w > AW) { x = 0; y += 56; }   /* a word that does not fit starts the next row */
    if (y + 56 > AH) { SDL_Log("overlay: no room for the word %s", words[i].s); break; }
    Cell c = {x, y, w, 56};
    x += w;
    cells[id] = c;
    word_w[id] = (float)((n * 6 - 1) * WORD_SCALE);
    dots(c, words[i].s, WORD_SCALE, (int)(c.w - word_w[id]) / 2, (c.h - 7 * WORD_SCALE) / 2);
  }
}

static void text(Cell c, const char *s) {
  int n = (int)strlen(s), scale = (c.w - 40) / (n * 6);
  if (scale > 6) scale = 6;
  int tw = (n * 6 - 1) * scale;
  dots(c, s, scale, (c.w - tw) / 2, (c.h - 7 * scale) / 2);
}

static void pill(Cell c, const char *label) {
  float b[] = {c.w / 2.0f, c.h / 2.0f, c.w / 2.0f - 6, c.h / 2.0f - 6, c.h / 2.0f - 6},
        line[] = {c.w / 2.0f, c.h / 2.0f, c.w / 2.0f - 7, c.h / 2.0f - 7, c.h / 2.0f - 7, 4};
  paint(c, sd_rbox, b, 0.08f, 0.08f, 0.1f, 0.55f);
  paint(c, sd_rbox_line, line, 1, 1, 1, 0.7f);
  text(c, label);
}

static void draw_atlas(void) {
  pix = calloc((size_t)AW * AH, 4);
  const float W = 7;   /* symbol stroke */
  /* the four face buttons, in the PlayStation's colours */
  for (int i = I_TRI; i <= I_RIGHT; i++) button_base(cells[i]);
  { Cell c = cells[I_TRI]; float t[] = {3, 64, 36, 90, 82, 38, 82, W}; paint(c, sd_poly_line, t, 0.35f, 0.9f, 0.7f, 1); }
  { Cell c = cells[I_CIRCLE]; float r[] = {64, 64, 25, W}; paint(c, sd_ring, r, 1, 0.42f, 0.48f, 1); }
  { Cell c = cells[I_CROSS]; float a[] = {42, 42, 86, 86, W}, b[] = {86, 42, 42, 86, W};
    paint(c, sd_seg, a, 0.5f, 0.68f, 1, 1); paint(c, sd_seg, b, 0.5f, 0.68f, 1, 1); }
  { Cell c = cells[I_SQUARE]; float s[] = {64, 64, 22, 22, 2, W}; paint(c, sd_rbox_line, s, 0.95f, 0.55f, 0.85f, 1); }
  arrow(cells[I_UP], -1.5707963f); arrow(cells[I_DOWN], 1.5707963f);
  arrow(cells[I_LEFT], 3.1415927f); arrow(cells[I_RIGHT], 0);
  /* the pad: a cross with an arrow in each arm */
  { Cell c = cells[I_DPAD];
    float fill[] = {128, 128, 118, 40, 14}, line[] = {128, 128, 117, 39, 13, 4};
    paint(c, sd_cross, fill, 0.08f, 0.08f, 0.1f, 0.55f);
    paint(c, sd_cross_line, line, 1, 1, 1, 0.7f);
    for (int k = 0; k < 4; k++) {
      float a = k * 1.5707963f, ca = cosf(a), sa = sinf(a), cx = 128 + ca * 80, cy = 128 + sa * 80, r = 18;
      float pts[] = {3, cx + ca * r, cy + sa * r, cx - ca * r * 0.6f - sa * r, cy - sa * r * 0.6f + ca * r,
                     cx - ca * r * 0.6f + sa * r, cy - sa * r * 0.6f - ca * r};
      paint(c, sd_poly_fill, pts, 0.92f, 0.92f, 0.95f, 0.9f);
    }
  }
  pill(cells[I_L1], "L1"); pill(cells[I_L2], "L2"); pill(cells[I_R1], "R1"); pill(cells[I_R2], "R2");
  pill(cells[I_SELECT], "SELECT"); pill(cells[I_START], "START");
  { Cell c = cells[I_PANEL]; float b[] = {32, 32, 32, 32, 0}; paint(c, sd_rbox, b, 0, 0, 0, 1); }
  { Cell c = cells[I_DOT]; float d[] = {16, 16, 12}; paint(c, sd_disc, d, 1, 1, 1, 1); }
  { Cell c = cells[I_WHITE]; float b[] = {8, 8, 8, 8, 0}; paint(c, sd_rbox, b, 1, 1, 1, 1); }
  { Cell c = cells[I_MENU]; button_base(c);
    for (int i = 0; i < 3; i++) { float s[] = {44, 46 + i * 18.0f, 84, 46 + i * 18.0f, 7}; paint(c, sd_seg, s, 0.92f, 0.92f, 0.95f, 0.95f); } }
  draw_menu_pictures();
  draw_words();
}

/* ---- setup ---- */
static GLuint shader(GLenum type, const char *src) {
  GLuint s = g.CreateShader(type);
  g.ShaderSource(s, 1, &src, NULL);
  g.CompileShader(s);
  GLint ok = 0; g.GetShaderiv(s, 0x8B81 /* GL_COMPILE_STATUS */, &ok);
  if (!ok) { char log[512]; g.GetShaderInfoLog(s, sizeof log, NULL, log); SDL_Log("overlay shader: %s", log); }
  return s;
}

bool overlay_init(void) {
#define L(n) if (!(g.n = (o_##n)SDL_GL_GetProcAddress("gl" #n))) { SDL_Log("overlay: no gl%s", #n); return false; }
  L(CreateShader) L(ShaderSource) L(CompileShader) L(GetShaderiv) L(GetShaderInfoLog) L(CreateProgram) L(AttachShader)
  L(BindAttribLocation) L(LinkProgram) L(GetProgramiv) L(UseProgram) L(GetUniformLocation) L(Uniform1i)
  L(GenVertexArrays) L(BindVertexArray) L(GenBuffers) L(BindBuffer) L(BufferData) L(VertexAttribPointer)
  L(EnableVertexAttribArray) L(DrawArrays) L(Enable) L(Disable) L(IsEnabled) L(BlendFuncSeparate)
  L(BlendEquationSeparate) L(GetIntegerv) L(ActiveTexture) L(GenTextures) L(BindTexture) L(TexImage2D)
  L(TexParameteri) L(PixelStorei) L(ColorMask)
#undef L
#ifdef HORIZON_GLES
  const char *head = "#version 300 es\nprecision mediump float;\n";
#else
  const char *head = "#version 330 core\n";
#endif
  char vs[512], fs[512];
  SDL_snprintf(vs, sizeof vs, "%sin vec2 p; in vec2 t; in vec4 c; out vec2 vt; out vec4 vc;\n"
               "void main() { gl_Position = vec4(p, 0.0, 1.0); vt = t; vc = c; }\n", head);
  SDL_snprintf(fs, sizeof fs, "%sin vec2 vt; in vec4 vc; uniform sampler2D s; out vec4 o;\n"
               "void main() { o = texture(s, vt) * vc; }\n", head);
  program = g.CreateProgram();
  g.AttachShader(program, shader(0x8B31 /* GL_VERTEX_SHADER */, vs));
  g.AttachShader(program, shader(0x8B30 /* GL_FRAGMENT_SHADER */, fs));
  g.BindAttribLocation(program, 0, "p"); g.BindAttribLocation(program, 1, "t"); g.BindAttribLocation(program, 2, "c");
  g.LinkProgram(program);
  GLint ok = 0; g.GetProgramiv(program, 0x8B82 /* GL_LINK_STATUS */, &ok);
  if (!ok) { SDL_Log("overlay: the shader did not link"); return false; }

  GLint old_prog, old_vao, old_buf, old_tex, old_unit;
  g.GetIntegerv(GL_CURRENT_PROGRAM, &old_prog); g.GetIntegerv(GL_VERTEX_ARRAY_BINDING, &old_vao);
  g.GetIntegerv(GL_ARRAY_BUFFER_BINDING, &old_buf); g.GetIntegerv(GL_ACTIVE_TEXTURE, &old_unit);
  g.ActiveTexture(GL_TEXTURE0); g.GetIntegerv(GL_TEXTURE_BINDING_2D, &old_tex);
  g.UseProgram(program); g.Uniform1i(g.GetUniformLocation(program, "s"), 0);
  g.GenVertexArrays(1, &vao); g.BindVertexArray(vao);
  g.GenBuffers(1, &vbo); g.BindBuffer(GL_ARRAY_BUFFER, vbo);
  g.VertexAttribPointer(0, 2, GL_FLOAT, GL_FALSE, 8 * sizeof(float), (void *)0);
  g.VertexAttribPointer(1, 2, GL_FLOAT, GL_FALSE, 8 * sizeof(float), (void *)(2 * sizeof(float)));
  g.VertexAttribPointer(2, 4, GL_FLOAT, GL_FALSE, 8 * sizeof(float), (void *)(4 * sizeof(float)));
  g.EnableVertexAttribArray(0); g.EnableVertexAttribArray(1); g.EnableVertexAttribArray(2);
  draw_atlas();
  g.GenTextures(1, &atlas); g.BindTexture(GL_TEXTURE_2D, atlas);
  g.PixelStorei(GL_UNPACK_ALIGNMENT, 4);
  g.TexImage2D(GL_TEXTURE_2D, 0, GL_RGBA, AW, AH, 0, GL_RGBA, GL_UNSIGNED_BYTE, pix);
  g.TexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MIN_FILTER, GL_LINEAR);
  g.TexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MAG_FILTER, GL_LINEAR);
  free(pix); pix = NULL;
  g.UseProgram(old_prog); g.BindVertexArray(old_vao); g.BindBuffer(GL_ARRAY_BUFFER, old_buf);
  g.BindTexture(GL_TEXTURE_2D, old_tex); g.ActiveTexture(old_unit);
  ready = true;
  return true;
}

/* ---- the touch pad ---- */
bool touch_shown, overlay_menu_tapped;
static struct { SDL_FingerID id; float x, y; bool down; } fingers[10];
static uint16_t touch_now;

typedef struct { int icon, id; float x, y, w, h; } Control;   /* centre and size, in pixels */
static Control controls[16];
static int ncontrols;
static float dpad_x, dpad_y, dpad_r, unit;

int overlay_touch_size = 100, overlay_touch_alpha = 75;

static void layout(int ww, int wh) {
  float s = (float)wh, W = (float)ww;
  if (W < s) s = W;      /* (a portrait window: size by the narrower side) */
  unit = s;
  s *= overlay_touch_size / 100.0f;   /* the menu's button size: every control keeps its corner */
  float b = 0.16f * s, off = 0.11f * s, fx = W - 0.21f * s, fy = wh - 0.30f * s;
  dpad_x = 0.21f * s; dpad_y = fy; dpad_r = 0.17f * s;
  float pw = 0.19f * s, ph = 0.08f * s;
  Control c[] = {
    {I_TRI, RETRO_DEVICE_ID_JOYPAD_X, fx, fy - off, b, b}, {I_CROSS, RETRO_DEVICE_ID_JOYPAD_B, fx, fy + off, b, b},
    {I_SQUARE, RETRO_DEVICE_ID_JOYPAD_Y, fx - off, fy, b, b}, {I_CIRCLE, RETRO_DEVICE_ID_JOYPAD_A, fx + off, fy, b, b},
    {I_L2, RETRO_DEVICE_ID_JOYPAD_L2, 0.03f * s + pw / 2, 0.04f * s + ph / 2, pw, ph},
    {I_L1, RETRO_DEVICE_ID_JOYPAD_L, 0.03f * s + pw / 2, 0.14f * s + ph / 2, pw, ph},
    {I_R2, RETRO_DEVICE_ID_JOYPAD_R2, W - 0.03f * s - pw / 2, 0.04f * s + ph / 2, pw, ph},
    {I_R1, RETRO_DEVICE_ID_JOYPAD_R, W - 0.03f * s - pw / 2, 0.14f * s + ph / 2, pw, ph},
    {I_SELECT, RETRO_DEVICE_ID_JOYPAD_SELECT, W / 2 - 0.12f * s, wh - 0.06f * s, pw * 0.85f, ph * 0.85f},
    {I_START, RETRO_DEVICE_ID_JOYPAD_START, W / 2 + 0.12f * s, wh - 0.06f * s, pw * 0.85f, ph * 0.85f},
    {I_MENU, -1, W / 2, 0.07f * s, 0.1f * s, 0.1f * s},   /* Horizon Play's menu */
  };
  ncontrols = (int)(sizeof c / sizeof *c);
  memcpy(controls, c, sizeof c);
}

static uint16_t bits_at(float x, float y) {
  uint16_t bits = 0;
  float dx = x - dpad_x, dy = y - dpad_y, d = hypotf(dx, dy);
  if (d < dpad_r * 1.5f && d > dpad_r * 0.15f) {   /* eight ways: 45-degree sectors around each axis */
    float a = atan2f(dy, dx) * 180 / 3.1415927f;
    if (a > -67.5f && a < 67.5f) bits |= 1u << RETRO_DEVICE_ID_JOYPAD_RIGHT;
    if (a > 112.5f || a < -112.5f) bits |= 1u << RETRO_DEVICE_ID_JOYPAD_LEFT;
    if (a > 22.5f && a < 157.5f) bits |= 1u << RETRO_DEVICE_ID_JOYPAD_DOWN;
    if (a < -22.5f && a > -157.5f) bits |= 1u << RETRO_DEVICE_ID_JOYPAD_UP;
    return bits;
  }
  /* the nearest control within reach (face buttons reach a little past their circle) */
  int best = -1; float best_d = 1e9f;
  for (int i = 0; i < ncontrols; i++) {
    Control *c = &controls[i];
    float ex = fmaxf(fabsf(x - c->x) - c->w / 2, 0), ey = fmaxf(fabsf(y - c->y) - c->h / 2, 0), e = hypotf(ex, ey);
    float reach = c->icon <= I_SQUARE ? 0.02f * unit : 0.025f * unit;
    if (e <= reach && hypotf(x - c->x, y - c->y) < best_d) { best = i; best_d = hypotf(x - c->x, y - c->y); }
  }
  if (best >= 0 && controls[best].id >= 0) bits |= 1u << controls[best].id;
  return bits;
}

void overlay_event(const SDL_Event *e, int ww, int wh) {
  switch (e->type) {
  case SDL_FINGERDOWN: case SDL_FINGERMOTION: case SDL_FINGERUP: {
    if (!menu_open && remap_step < 0) touch_shown = true;
    int free_slot = -1, slot = -1;
    for (int i = 0; i < 10; i++) {
      if (fingers[i].down && fingers[i].id == e->tfinger.fingerId) slot = i;
      if (!fingers[i].down && free_slot < 0) free_slot = i;
    }
    if (slot < 0 && e->type == SDL_FINGERDOWN) slot = free_slot;
    if (slot < 0) break;
    if (e->type == SDL_FINGERDOWN && (menu_open || remap_step >= 0)) break;   /* the menu has its own touch */
    if (e->type == SDL_FINGERDOWN) {   /* the menu button works on the first touch */
      layout(ww, wh);
      Control *m = &controls[ncontrols - 1];
      if (fabsf(e->tfinger.x * ww - m->x) < m->w * 0.7f && fabsf(e->tfinger.y * wh - m->y) < m->h * 0.7f && touch_shown) {
        overlay_menu_tapped = true; break;
      }
    }
    fingers[slot].id = e->tfinger.fingerId;
    fingers[slot].x = e->tfinger.x * ww; fingers[slot].y = e->tfinger.y * wh;
    fingers[slot].down = e->type != SDL_FINGERUP;
    break;
  }
  case SDL_CONTROLLERBUTTONDOWN: case SDL_JOYBUTTONDOWN: case SDL_KEYDOWN:   /* a pad or keyboard in use: the touch pad steps aside */
    if (e->type == SDL_KEYDOWN)   /* a phone's own keys are not a keyboard */
      switch (e->key.keysym.scancode) {
      case SDL_SCANCODE_AC_BACK: case SDL_SCANCODE_VOLUMEUP: case SDL_SCANCODE_VOLUMEDOWN: case SDL_SCANCODE_MUTE:
      case SDL_SCANCODE_AUDIOMUTE: return;
      default: break;
      }
    touch_shown = false;
    memset(fingers, 0, sizeof fingers);
    break;
  }
}

uint16_t overlay_touch_bits(int ww, int wh) {
  layout(ww, wh);
  touch_now = 0;
  if (touch_shown)
    for (int i = 0; i < 10; i++) if (fingers[i].down) touch_now |= bits_at(fingers[i].x, fingers[i].y);
  return touch_now;
}

/* ---- drawing ---- */
#define MAX_QUADS 160
static float verts[MAX_QUADS * 6 * 8];
static int nverts, cur_w = 1, cur_h = 1;

static void quad(int icon, float cx, float cy, float w, float h, float bright, float alpha, int ww, int wh) {
  if (nverts + 6 > MAX_QUADS * 6) return;
  Cell c = cells[icon];
  float x0 = (cx - w / 2) / ww * 2 - 1, x1 = (cx + w / 2) / ww * 2 - 1;
  float y0 = 1 - (cy - h / 2) / wh * 2, y1 = 1 - (cy + h / 2) / wh * 2;
  float u0 = (c.x + 0.5f) / AW, u1 = (c.x + c.w - 0.5f) / AW, v0 = (c.y + 0.5f) / AH, v1 = (c.y + c.h - 0.5f) / AH;
  float k = bright * alpha;
  float q[6][4] = {{x0, y0, u0, v0}, {x1, y0, u1, v0}, {x1, y1, u1, v1}, {x0, y0, u0, v0}, {x1, y1, u1, v1}, {x0, y1, u0, v1}};
  for (int i = 0; i < 6; i++) {
    float *v = verts + nverts++ * 8;
    v[0] = q[i][0]; v[1] = q[i][1]; v[2] = q[i][2]; v[3] = q[i][3]; v[4] = k; v[5] = k; v[6] = k; v[7] = alpha;
  }
}

static void flush(int ww, int wh) {
  if (!nverts) return;
  GLint prog, va, buf, unit_, tex, src_rgb, dst_rgb, src_a, dst_a, eq_rgb, eq_a, vp[4];
  g.GetIntegerv(GL_CURRENT_PROGRAM, &prog); g.GetIntegerv(GL_VERTEX_ARRAY_BINDING, &va);
  g.GetIntegerv(GL_ARRAY_BUFFER_BINDING, &buf); g.GetIntegerv(GL_ACTIVE_TEXTURE, &unit_);
  g.ActiveTexture(GL_TEXTURE0); g.GetIntegerv(GL_TEXTURE_BINDING_2D, &tex);
  g.GetIntegerv(GL_BLEND_SRC_RGB, &src_rgb); g.GetIntegerv(GL_BLEND_DST_RGB, &dst_rgb);
  g.GetIntegerv(GL_BLEND_SRC_ALPHA, &src_a); g.GetIntegerv(GL_BLEND_DST_ALPHA, &dst_a);
  g.GetIntegerv(GL_BLEND_EQUATION_RGB, &eq_rgb); g.GetIntegerv(GL_BLEND_EQUATION_ALPHA, &eq_a);
  g.GetIntegerv(GL_VIEWPORT, vp);
  GLboolean blend = g.IsEnabled(GL_BLEND), depth = g.IsEnabled(GL_DEPTH_TEST), cull = g.IsEnabled(GL_CULL_FACE),
            stencil = g.IsEnabled(GL_STENCIL_TEST), scissor = g.IsEnabled(GL_SCISSOR_TEST);
  (void)vp;

  g.Enable(GL_BLEND); g.Disable(GL_DEPTH_TEST); g.Disable(GL_CULL_FACE); g.Disable(GL_STENCIL_TEST);
  g.Disable(GL_SCISSOR_TEST);
  g.BlendFuncSeparate(GL_ONE, GL_ONE_MINUS_SRC_ALPHA, GL_ONE, GL_ONE_MINUS_SRC_ALPHA);
  g.BlendEquationSeparate(GL_FUNC_ADD, GL_FUNC_ADD);
  g.UseProgram(program); g.BindVertexArray(vao); g.BindBuffer(GL_ARRAY_BUFFER, vbo);
  g.BindTexture(GL_TEXTURE_2D, atlas);
  g.BufferData(GL_ARRAY_BUFFER, (GLsizeiptr)(nverts * 8 * sizeof(float)), verts, GL_STREAM_DRAW);
  g.DrawArrays(GL_TRIANGLES, 0, nverts);
  nverts = 0;
  (void)ww; (void)wh;

  g.BindTexture(GL_TEXTURE_2D, tex); g.ActiveTexture(unit_);
  g.BindBuffer(GL_ARRAY_BUFFER, buf); g.BindVertexArray(va); g.UseProgram(prog);
  g.BlendFuncSeparate(src_rgb, dst_rgb, src_a, dst_a); g.BlendEquationSeparate(eq_rgb, eq_a);
  if (!blend) g.Disable(GL_BLEND);
  if (depth) g.Enable(GL_DEPTH_TEST);
  if (cull) g.Enable(GL_CULL_FACE);
  if (stencil) g.Enable(GL_STENCIL_TEST);
  if (scissor) g.Enable(GL_SCISSOR_TEST);
}

/* the setup: the PlayStation button to press now, big, the steps as dots, and the time left as a bar */
static void draw_setup(int ww, int wh) {
  static const int icon[CONTROL_COUNT] = {I_UP, I_DOWN, I_LEFT, I_RIGHT, I_CROSS, I_CIRCLE, I_SQUARE, I_TRI,
                                          I_L1, I_R1, I_L2, I_R2, I_SELECT, I_START};
  float s = ww < wh ? (float)ww : (float)wh, cx = ww / 2.0f;
  quad(I_PANEL, cx, wh / 2.0f, (float)ww, (float)wh, 1, 0.8f, ww, wh);
  int ic = icon[remap_step];
  if (ic >= I_UP && ic <= I_RIGHT) {   /* a direction: the pad, with that arm lit */
    static const float ang[4] = {-1.5707963f, 1.5707963f, 3.1415927f, 0};
    float d = 0.36f * s, a = ang[ic - I_UP];
    quad(I_DOT, cx + cosf(a) * d * 0.31f, wh * 0.42f + sinf(a) * d * 0.31f, d * 0.3f, d * 0.3f, 1, 0.75f, ww, wh);
    quad(I_DPAD, cx, wh * 0.42f, d, d, 1, 1, ww, wh);   /* over the light: the arm glows, its arrow stays */
  } else {
    float w = ic >= I_L1 ? 0.42f * s : 0.3f * s, h = ic >= I_L1 ? 0.175f * s : 0.3f * s;
    quad(ic, cx, wh * 0.42f, w, h, 1.2f, 1, ww, wh);
  }
  float gap = 0.05f * s, x0 = cx - gap * (CONTROL_COUNT - 1) / 2;
  for (int i = 0; i < CONTROL_COUNT; i++) {
    float d = i == remap_step ? 0.035f * s : 0.022f * s;
    quad(I_DOT, x0 + i * gap, wh * 0.72f, d, d, 1, i < remap_step ? 0.9f : i == remap_step ? 1 : 0.3f, ww, wh);
  }
  float bw = gap * (CONTROL_COUNT - 1);
  quad(I_WHITE, cx, wh * 0.8f, bw, 0.008f * s, 1, 0.15f, ww, wh);
  quad(I_WHITE, cx - bw / 2 + bw * remap_time_left / 2, wh * 0.8f, bw * remap_time_left, 0.008f * s, 1, 0.7f, ww, wh);
}

void overlay_quad(int icon, float cx, float cy, float w, float h, float bright, float alpha) {
  quad(icon, cx, cy, w, h, bright, alpha, cur_w, cur_h);
}

float overlay_text_width(int word, float glyph_h) {
  return word >= T_RESUME && word < I_COUNT ? word_w[word] * glyph_h / (7 * WORD_SCALE) : 0;
}

void overlay_text(int word, float cx, float cy, float glyph_h, float max_w, float bright, float alpha) {
  if (word < T_RESUME || word >= I_COUNT || !word_w[word]) return;
  float k = glyph_h / (7 * WORD_SCALE);
  if (word_w[word] * k > max_w) k = max_w / word_w[word];
  quad(word, cx, cy, cells[word].w * k, cells[word].h * k, bright, alpha, cur_w, cur_h);
}

int overlay_fps = -1;

/* the frame rate, small, in the top left corner: "60 FPS" */
static void draw_fps(int ww, int wh) {
  if (overlay_fps < 0) return;
  char num[8];
  int n = snprintf(num, sizeof num, "%d", overlay_fps > 999 ? 999 : overlay_fps);
  float gh = (ww < wh ? ww : wh) * 0.022f;
  if (gh < 8) gh = 8;
  float adv = gh * 6 / 7, pad = gh * 0.5f, x = pad * 1.5f, y = pad * 1.5f + gh / 2;
  float tw = (n + 4) * adv - adv / 6;   /* the digits, a space and FPS */
  quad(I_WHITE, x + tw / 2, y, tw + pad * 2, gh + pad * 1.4f, 0, 0.45f, ww, wh);   /* a dark backing */
  for (int i = 0; i < n; i++) overlay_text(T_D0 + num[i] - '0', x + i * adv + adv / 2 - adv / 12, y, gh, adv * 2, 1, 0.95f);
  overlay_text(T_FPS, x + (n + 1) * adv + overlay_text_width(T_FPS, gh) / 2, y, gh, adv * 4, 1, 0.95f);
}

void overlay_draw(int ww, int wh) {
  if (!ready) return;
  cur_w = ww; cur_h = wh;
  if (remap_step >= 0) draw_setup(ww, wh);
  else if (menu_open) menu_draw(ww, wh);
  else if (touch_shown) {
    layout(ww, wh);
    const float a = overlay_touch_alpha / 100.0f;
    uint16_t on = touch_now;
    float d = dpad_r * 2;
    static const int dirs[4] = {RETRO_DEVICE_ID_JOYPAD_RIGHT, RETRO_DEVICE_ID_JOYPAD_DOWN, RETRO_DEVICE_ID_JOYPAD_LEFT,
                                RETRO_DEVICE_ID_JOYPAD_UP};
    for (int k = 0; k < 4; k++)   /* a lit dot on a pressed arm */
      if (on & (1u << dirs[k])) {
        float ang = k * 1.5707963f;
        quad(I_DOT, dpad_x + cosf(ang) * d * 0.31f, dpad_y + sinf(ang) * d * 0.31f, d * 0.3f, d * 0.3f, 1, 0.6f, ww, wh);
      }
    quad(I_DPAD, dpad_x, dpad_y, d, d, 1, a, ww, wh);   /* over the lit arms */
    for (int i = 0; i < ncontrols; i++) {
      Control *c = &controls[i];
      bool pressed = on & (1u << c->id);
      float grow = pressed ? 0.92f : 1;
      quad(c->icon, c->x, c->y, c->w * grow, c->h * grow, pressed ? 1.6f : 1, pressed ? 1 : a, ww, wh);
    }
  }
  if (remap_step < 0 && !menu_open) draw_fps(ww, wh);
  flush(ww, wh);
}
