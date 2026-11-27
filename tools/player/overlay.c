/* Horizon Play's own drawing over the game (docs/player.md): the touch pad for phones with no controller, and the
 * prompts of the button setup. Everything is drawn at start into one texture (shapes from distance functions, a 5x7
 * font), then each frame as quads with one small shader. The core keeps its own GL state cached, so every piece of
 * state touched here is put back as it was. MIT, like the rest of Horizon's code.
 */
#include "overlay.h"
#include "controls.h"
#include <math.h>
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
#define AH 1024
static uint8_t *pix;

typedef struct { int x, y, w, h; } Cell;
enum { I_TRI, I_CIRCLE, I_CROSS, I_SQUARE, I_UP, I_DOWN, I_LEFT, I_RIGHT, I_DPAD,
       I_L1, I_L2, I_R1, I_R2, I_SELECT, I_START, I_PANEL, I_DOT, I_WHITE, I_COUNT };
static Cell cells[I_COUNT] = {
  [I_TRI] = {0, 0, 128, 128}, [I_CIRCLE] = {128, 0, 128, 128}, [I_CROSS] = {256, 0, 128, 128},
  [I_SQUARE] = {384, 0, 128, 128}, [I_UP] = {0, 128, 128, 128}, [I_DOWN] = {128, 128, 128, 128},
  [I_LEFT] = {256, 128, 128, 128}, [I_RIGHT] = {384, 128, 128, 128}, [I_DPAD] = {512, 0, 256, 256},
  [I_L1] = {0, 256, 192, 80}, [I_L2] = {192, 256, 192, 80}, [I_R1] = {384, 256, 192, 80}, [I_R2] = {576, 256, 192, 80},
  [I_SELECT] = {0, 336, 192, 80}, [I_START] = {192, 336, 192, 80}, [I_PANEL] = {768, 0, 64, 64},
  [I_DOT] = {832, 0, 32, 32}, [I_WHITE] = {872, 8, 16, 16},
};

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

/* 5x7 font: the letters the labels need */
static const struct { char ch; uint8_t rows[7]; } font[] = {
  {'L', {0x10, 0x10, 0x10, 0x10, 0x10, 0x10, 0x1F}}, {'R', {0x1E, 0x11, 0x11, 0x1E, 0x14, 0x12, 0x11}},
  {'1', {0x04, 0x0C, 0x04, 0x04, 0x04, 0x04, 0x0E}}, {'2', {0x0E, 0x11, 0x01, 0x02, 0x04, 0x08, 0x1F}},
  {'S', {0x0F, 0x10, 0x10, 0x0E, 0x01, 0x01, 0x1E}}, {'E', {0x1F, 0x10, 0x10, 0x1E, 0x10, 0x10, 0x1F}},
  {'C', {0x0E, 0x11, 0x10, 0x10, 0x10, 0x11, 0x0E}}, {'T', {0x1F, 0x04, 0x04, 0x04, 0x04, 0x04, 0x04}},
  {'A', {0x0E, 0x11, 0x11, 0x1F, 0x11, 0x11, 0x11}},
};

static void text(Cell c, const char *s) {
  int n = (int)strlen(s), scale = (c.w - 40) / (n * 6);
  if (scale > 6) scale = 6;
  int tw = (n * 6 - 1) * scale, x0 = (c.w - tw) / 2, y0 = (c.h - 7 * scale) / 2;
  for (int i = 0; i < n; i++)
    for (size_t f = 0; f < sizeof font / sizeof *font; f++)
      if (font[f].ch == s[i])
        for (int row = 0; row < 7; row++)
          for (int col = 0; col < 5; col++)
            if (font[f].rows[row] & (0x10 >> col)) {
              float b[] = {x0 + (i * 6 + col + 0.5f) * scale, y0 + (row + 0.5f) * scale, scale / 2.0f + 0.3f,
                           scale / 2.0f + 0.3f, scale * 0.2f};
              paint(c, sd_rbox, b, 0.95f, 0.95f, 0.97f, 1);
            }
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
bool touch_shown;
static struct { SDL_FingerID id; float x, y; bool down; } fingers[10];
static uint16_t touch_now;

typedef struct { int icon, id; float x, y, w, h; } Control;   /* centre and size, in pixels */
static Control controls[16];
static int ncontrols;
static float dpad_x, dpad_y, dpad_r, unit;

static void layout(int ww, int wh) {
  float s = (float)wh, W = (float)ww;
  if (W < s) s = W;      /* (a portrait window: size by the narrower side) */
  unit = s;
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
  if (best >= 0) bits |= 1u << controls[best].id;
  return bits;
}

void overlay_event(const SDL_Event *e, int ww, int wh) {
  switch (e->type) {
  case SDL_FINGERDOWN: case SDL_FINGERMOTION: case SDL_FINGERUP: {
    touch_shown = true;
    int free_slot = -1, slot = -1;
    for (int i = 0; i < 10; i++) {
      if (fingers[i].down && fingers[i].id == e->tfinger.fingerId) slot = i;
      if (!fingers[i].down && free_slot < 0) free_slot = i;
    }
    if (slot < 0 && e->type == SDL_FINGERDOWN) slot = free_slot;
    if (slot < 0) break;
    fingers[slot].id = e->tfinger.fingerId;
    fingers[slot].x = e->tfinger.x * ww; fingers[slot].y = e->tfinger.y * wh;
    fingers[slot].down = e->type != SDL_FINGERUP;
    break;
  }
  case SDL_CONTROLLERBUTTONDOWN: case SDL_KEYDOWN:   /* a pad or keyboard in use: the touch pad steps aside */
    if (e->type == SDL_KEYDOWN && e->key.keysym.scancode == SDL_SCANCODE_AC_BACK) break;
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
static float verts[64 * 6 * 8];
static int nverts;

static void quad(int icon, float cx, float cy, float w, float h, float bright, float alpha, int ww, int wh) {
  if (nverts + 6 > 64 * 6) return;
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
  float w = ic >= I_L1 ? 0.42f * s : 0.3f * s, h = ic >= I_L1 ? 0.175f * s : 0.3f * s;
  quad(ic, cx, wh * 0.42f, w, h, 1.2f, 1, ww, wh);
  float gap = 0.05f * s, x0 = cx - gap * (CONTROL_COUNT - 1) / 2;
  for (int i = 0; i < CONTROL_COUNT; i++) {
    float d = i == remap_step ? 0.035f * s : 0.022f * s;
    quad(I_DOT, x0 + i * gap, wh * 0.72f, d, d, 1, i < remap_step ? 0.9f : i == remap_step ? 1 : 0.3f, ww, wh);
  }
  float bw = gap * (CONTROL_COUNT - 1);
  quad(I_WHITE, cx, wh * 0.8f, bw, 0.008f * s, 1, 0.15f, ww, wh);
  quad(I_WHITE, cx - bw / 2 + bw * remap_time_left / 2, wh * 0.8f, bw * remap_time_left, 0.008f * s, 1, 0.7f, ww, wh);
}

void overlay_draw(int ww, int wh) {
  if (!ready) return;
  if (remap_step >= 0) draw_setup(ww, wh);
  else if (touch_shown) {
    layout(ww, wh);
    const float a = 0.75f;
    uint16_t on = touch_now;
    float d = dpad_r * 2;
    quad(I_DPAD, dpad_x, dpad_y, d, d, 1, a, ww, wh);
    static const int dirs[4] = {RETRO_DEVICE_ID_JOYPAD_RIGHT, RETRO_DEVICE_ID_JOYPAD_DOWN, RETRO_DEVICE_ID_JOYPAD_LEFT,
                                RETRO_DEVICE_ID_JOYPAD_UP};
    for (int k = 0; k < 4; k++)   /* a lit dot on a pressed arm */
      if (on & (1u << dirs[k])) {
        float ang = k * 1.5707963f;
        quad(I_DOT, dpad_x + cosf(ang) * d * 0.31f, dpad_y + sinf(ang) * d * 0.31f, d * 0.2f, d * 0.2f, 1, 0.6f, ww, wh);
      }
    for (int i = 0; i < ncontrols; i++) {
      Control *c = &controls[i];
      bool pressed = on & (1u << c->id);
      float grow = pressed ? 0.92f : 1;
      quad(c->icon, c->x, c->y, c->w * grow, c->h * grow, pressed ? 1.6f : 1, pressed ? 1 : a, ww, wh);
    }
  }
  flush(ww, wh);
}
