/* NorthCel native runtime - headless GLSL rasteriser.
 *
 * GLSL is not "installed": it is compiled by a GL driver. This host provides a
 * pinned, headless GL runtime through EGL (Mesa surfaceless platform) and
 * rasterises the IR's vector edges with a 4.30 (or 4.10-portable) fragment
 * shader. The shader performs the N x N subpixel even-odd parity integration;
 * the host only applies the reference paper grain and 8-bit rounding so the
 * output bytes are stable and comparable with the Python oracle.
 */
#define _GNU_SOURCE
#include <dlfcn.h>
#include <math.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#include "ncel_ir.h"

#define STB_IMAGE_WRITE_IMPLEMENTATION
#include "stb_image_write.h"

/* ------------------------------------------------------------------ EGL/GL */
typedef void *EGLDisplay;
typedef void *EGLConfig;
typedef void *EGLContext;
typedef void *EGLSurface;
typedef int32_t EGLint;
typedef unsigned int EGLBoolean;
typedef unsigned int EGLenum;
typedef unsigned int GLenum;
typedef unsigned int GLuint;
typedef int GLint;
typedef int GLsizei;
typedef float GLfloat;
typedef char GLchar;
typedef ptrdiff_t GLsizeiptr;
typedef ptrdiff_t GLintptr;

#define EGL_DEFAULT_DISPLAY ((void *)0)
#define EGL_NO_CONTEXT ((EGLContext)0)
#define EGL_NO_SURFACE ((EGLSurface)0)
#define EGL_OPENGL_API 0x30A2
#define EGL_PLATFORM_SURFACELESS_MESA 0x31DD
#define EGL_CONTEXT_MAJOR_VERSION 0x3098
#define EGL_CONTEXT_MINOR_VERSION 0x30FB
#define EGL_CONTEXT_OPENGL_PROFILE_MASK 0x30FD
#define EGL_CONTEXT_OPENGL_CORE_PROFILE_BIT 0x00000001
#define EGL_SURFACE_TYPE 0x3033
#define EGL_PBUFFER_BIT 0x0001
#define EGL_RENDERABLE_TYPE 0x3040
#define EGL_OPENGL_BIT 0x0008
#define EGL_NONE 0x3038

#define GL_TEXTURE_2D 0x0DE1
#define GL_FRAGMENT_SHADER 0x8B30
#define GL_VERTEX_SHADER 0x8B31
#define GL_COMPILE_STATUS 0x8B81
#define GL_LINK_STATUS 0x8B82
#define GL_INFO_LOG_LENGTH 0x8B84
#define GL_TEXTURE_BUFFER 0x8C2A
#define GL_TEXTURE0 0x84C0
#define GL_RGBA32F 0x8814
#define GL_RG32I 0x823B
#define GL_RGBA 0x1908
#define GL_RED 0x1903
#define GL_RG 0x8227
#define GL_RG_INTEGER 0x8228
#define GL_FLOAT 0x1406
#define GL_INT 0x1404
#define GL_FRAMEBUFFER 0x8D40
#define GL_COLOR_ATTACHMENT0 0x8CE0
#define GL_FRAMEBUFFER_COMPLETE 0x8CD5
#define GL_TRIANGLES 0x0004
#define GL_ARRAY_BUFFER 0x8892
#define GL_STATIC_DRAW 0x88E4
#define GL_NO_ERROR 0
#define GL_TEXTURE_MIN_FILTER 0x2801
#define GL_TEXTURE_MAG_FILTER 0x2800
#define GL_NEAREST 0x2600
#define GL_PACK_ALIGNMENT 0x0D05
#define GL_UNPACK_ALIGNMENT 0x0CF5
#define GL_MAX_TEXTURE_BUFFER_SIZE 0x8C2B
#define GL_MAX_TEXTURE_SIZE 0x0D33

typedef struct {
  void *lib;
  EGLDisplay (*eglGetPlatformDisplay)(EGLenum, void *, const EGLint *);
  EGLBoolean (*eglInitialize)(EGLDisplay, EGLint *, EGLint *);
  EGLBoolean (*eglBindAPI)(EGLenum);
  EGLBoolean (*eglChooseConfig)(EGLDisplay, const EGLint *, EGLConfig *, EGLint, EGLint *);
  EGLContext (*eglCreateContext)(EGLDisplay, EGLConfig, EGLContext, const EGLint *);
  EGLBoolean (*eglMakeCurrent)(EGLDisplay, EGLSurface, EGLSurface, EGLContext);
  EGLBoolean (*eglDestroyContext)(EGLDisplay, EGLContext);
  EGLBoolean (*eglTerminate)(EGLDisplay);
  EGLint (*eglGetError)(void);
  const char *(*eglQueryString)(EGLDisplay, EGLint);
  void *(*eglGetProcAddress)(const char *);
} Egl;

typedef struct {
  const unsigned char *(*glGetString)(GLenum);
  void (*glGetIntegerv)(GLenum, GLint *);
  GLenum (*glGetError)(void);
  void (*glViewport)(GLint, GLint, GLsizei, GLsizei);
  void (*glGenTextures)(GLsizei, GLuint *);
  void (*glBindTexture)(GLenum, GLuint);
  void (*glTexParameteri)(GLenum, GLenum, GLint);
  void (*glTexImage2D)(GLenum, GLint, GLint, GLsizei, GLsizei, GLint, GLenum, GLenum, const void *);
  void (*glGenBuffers)(GLsizei, GLuint *);
  void (*glBindBuffer)(GLenum, GLuint);
  void (*glBufferData)(GLenum, GLsizeiptr, const void *, GLenum);
  void (*glTexBuffer)(GLenum, GLenum, GLuint);
  void (*glGenFramebuffers)(GLsizei, GLuint *);
  void (*glBindFramebuffer)(GLenum, GLuint);
  void (*glFramebufferTexture2D)(GLenum, GLenum, GLenum, GLuint, GLint);
  GLenum (*glCheckFramebufferStatus)(GLenum);
  void (*glGenVertexArrays)(GLsizei, GLuint *);
  void (*glBindVertexArray)(GLuint);
  GLuint (*glCreateShader)(GLenum);
  void (*glShaderSource)(GLuint, GLsizei, const GLchar *const *, const GLint *);
  void (*glCompileShader)(GLuint);
  void (*glGetShaderiv)(GLuint, GLenum, GLint *);
  void (*glGetShaderInfoLog)(GLuint, GLsizei, GLsizei *, GLchar *);
  GLuint (*glCreateProgram)(void);
  void (*glAttachShader)(GLuint, GLuint);
  void (*glLinkProgram)(GLuint);
  void (*glGetProgramiv)(GLuint, GLenum, GLint *);
  void (*glGetProgramInfoLog)(GLuint, GLsizei, GLsizei *, GLchar *);
  void (*glUseProgram)(GLuint);
  GLint (*glGetUniformLocation)(GLuint, const GLchar *);
  void (*glUniform1i)(GLint, GLint);
  void (*glUniform2f)(GLint, GLfloat, GLfloat);
  void (*glActiveTexture)(GLenum);
  void (*glDrawArrays)(GLenum, GLint, GLsizei);
  void (*glReadPixels)(GLint, GLint, GLsizei, GLsizei, GLenum, GLenum, void *);
  void (*glFinish)(void);
  void (*glDeleteShader)(GLuint);
  void (*glDeleteProgram)(GLuint);
  void (*glDeleteBuffers)(GLsizei, const GLuint *);
  void (*glDeleteTextures)(GLsizei, const GLuint *);
  void (*glDeleteFramebuffers)(GLsizei, const GLuint *);
  void (*glDeleteVertexArrays)(GLsizei, const GLuint *);
} Gl;

#define LOAD_EGL(field, name)                                                       \
  do {                                                                              \
    *(void **)(&e->field) = dlsym(e->lib, name);                                    \
    if (!e->field) { snprintf(err, errcap, "missing EGL symbol %s", name); return 1; } \
  } while (0)
#define LOAD_GL(field, name)                                                        \
  do {                                                                              \
    *(void **)(&g->field) = e->eglGetProcAddress(name);                              \
    if (!g->field) { snprintf(err, errcap, "missing GL symbol %s", name); return 1; }\
  } while (0)

static int egl_open(Egl *e, char *err, size_t errcap) {
  memset(e, 0, sizeof(*e));
  e->lib = dlopen("libEGL.so.1", RTLD_NOW | RTLD_LOCAL);
  if (!e->lib) {
    snprintf(err, errcap, "cannot dlopen libEGL.so.1 (%s)", dlerror());
    return 1;
  }
  LOAD_EGL(eglGetPlatformDisplay, "eglGetPlatformDisplay");
  LOAD_EGL(eglInitialize, "eglInitialize");
  LOAD_EGL(eglBindAPI, "eglBindAPI");
  LOAD_EGL(eglChooseConfig, "eglChooseConfig");
  LOAD_EGL(eglCreateContext, "eglCreateContext");
  LOAD_EGL(eglMakeCurrent, "eglMakeCurrent");
  LOAD_EGL(eglDestroyContext, "eglDestroyContext");
  LOAD_EGL(eglTerminate, "eglTerminate");
  LOAD_EGL(eglGetError, "eglGetError");
  LOAD_EGL(eglQueryString, "eglQueryString");
  LOAD_EGL(eglGetProcAddress, "eglGetProcAddress");
  return 0;
}

static int gl_load(Gl *g, Egl *e, char *err, size_t errcap) {
  memset(g, 0, sizeof(*g));
  LOAD_GL(glGetString, "glGetString");
  LOAD_GL(glGetIntegerv, "glGetIntegerv");
  LOAD_GL(glGetError, "glGetError");
  LOAD_GL(glViewport, "glViewport");
  LOAD_GL(glGenTextures, "glGenTextures");
  LOAD_GL(glBindTexture, "glBindTexture");
  LOAD_GL(glTexParameteri, "glTexParameteri");
  LOAD_GL(glTexImage2D, "glTexImage2D");
  LOAD_GL(glGenBuffers, "glGenBuffers");
  LOAD_GL(glBindBuffer, "glBindBuffer");
  LOAD_GL(glBufferData, "glBufferData");
  LOAD_GL(glTexBuffer, "glTexBuffer");
  LOAD_GL(glGenFramebuffers, "glGenFramebuffers");
  LOAD_GL(glBindFramebuffer, "glBindFramebuffer");
  LOAD_GL(glFramebufferTexture2D, "glFramebufferTexture2D");
  LOAD_GL(glCheckFramebufferStatus, "glCheckFramebufferStatus");
  LOAD_GL(glGenVertexArrays, "glGenVertexArrays");
  LOAD_GL(glBindVertexArray, "glBindVertexArray");
  LOAD_GL(glCreateShader, "glCreateShader");
  LOAD_GL(glShaderSource, "glShaderSource");
  LOAD_GL(glCompileShader, "glCompileShader");
  LOAD_GL(glGetShaderiv, "glGetShaderiv");
  LOAD_GL(glGetShaderInfoLog, "glGetShaderInfoLog");
  LOAD_GL(glCreateProgram, "glCreateProgram");
  LOAD_GL(glAttachShader, "glAttachShader");
  LOAD_GL(glLinkProgram, "glLinkProgram");
  LOAD_GL(glGetProgramiv, "glGetProgramiv");
  LOAD_GL(glGetProgramInfoLog, "glGetProgramInfoLog");
  LOAD_GL(glUseProgram, "glUseProgram");
  LOAD_GL(glGetUniformLocation, "glGetUniformLocation");
  LOAD_GL(glUniform1i, "glUniform1i");
  LOAD_GL(glUniform2f, "glUniform2f");
  LOAD_GL(glActiveTexture, "glActiveTexture");
  LOAD_GL(glDrawArrays, "glDrawArrays");
  LOAD_GL(glReadPixels, "glReadPixels");
  LOAD_GL(glFinish, "glFinish");
  LOAD_GL(glDeleteShader, "glDeleteShader");
  LOAD_GL(glDeleteProgram, "glDeleteProgram");
  LOAD_GL(glDeleteBuffers, "glDeleteBuffers");
  LOAD_GL(glDeleteTextures, "glDeleteTextures");
  LOAD_GL(glDeleteFramebuffers, "glDeleteFramebuffers");
  LOAD_GL(glDeleteVertexArrays, "glDeleteVertexArrays");
  return 0;
}

static char *read_text_file(const char *path) {
  FILE *f = fopen(path, "rb");
  if (!f) return NULL;
  if (fseek(f, 0, SEEK_END) != 0) { fclose(f); return NULL; }
  long n = ftell(f);
  if (n < 0) { fclose(f); return NULL; }
  if (fseek(f, 0, SEEK_SET) != 0) { fclose(f); return NULL; }
  char *s = (char *)malloc((size_t)n + 1);
  if (!s) { fclose(f); return NULL; }
  size_t got = fread(s, 1, (size_t)n, f);
  fclose(f);
  s[got] = 0;
  return s;
}

static GLuint compile_shader(Gl *g, GLenum kind, const char *src, char *err, size_t errcap) {
  GLuint sh = g->glCreateShader(kind);
  g->glShaderSource(sh, 1, &src, NULL);
  g->glCompileShader(sh);
  GLint ok = 0;
  g->glGetShaderiv(sh, GL_COMPILE_STATUS, &ok);
  if (!ok) {
    char log[4096];
    GLsizei len = 0;
    g->glGetShaderInfoLog(sh, sizeof(log) - 1, &len, log);
    log[len > 0 ? len : 0] = 0;
    snprintf(err, errcap, "shader compile failed: %.2000s", log);
    g->glDeleteShader(sh);
    return 0;
  }
  return sh;
}

/* ------------------------------------------------------------------- output */

static void apply_grain_and_pack(const float *rgba, int w, int h, int aa, double grain,
                                 int64_t seed, uint8_t *out) {
  (void)aa;
  for (int y = 0; y < h; y++) {
    for (int x = 0; x < w; x++) {
      const float *px = &rgba[((size_t)(h - 1 - y) * w + x) * 4];
      double r = px[0], g = px[1], b = px[2];
      if (grain > 0.0) {
        uint64_t hh = ((uint64_t)x * 374761393ULL + (uint64_t)y * 668265263ULL +
                       (uint64_t)(uint32_t)seed * 1442695041ULL) & 0xFFFFFFFFULL;
        double noise = (sin((double)hh * 0.0001) * 0.5) * (grain * 255.0);
        r += noise;
        g += noise;
        b += noise;
      }
      int ri = (int)floor(r + 0.5);
      int gi = (int)floor(g + 0.5);
      int bi = (int)floor(b + 0.5);
      if (ri < 0) ri = 0;
      if (ri > 255) ri = 255;
      if (gi < 0) gi = 0;
      if (gi > 255) gi = 255;
      if (bi < 0) bi = 0;
      if (bi > 255) bi = 255;
      size_t o = ((size_t)y * w + x) * 3;
      out[o] = (uint8_t)ri;
      out[o + 1] = (uint8_t)gi;
      out[o + 2] = (uint8_t)bi;
    }
  }
}

/* --------------------------------------------------------------------- main */

static int gl_init(Egl *e, Gl *g, char *err, size_t errcap) {
  if (egl_open(e, err, errcap)) return 1;
  EGLDisplay dpy = e->eglGetPlatformDisplay(EGL_PLATFORM_SURFACELESS_MESA, EGL_DEFAULT_DISPLAY, NULL);
  if (!dpy) { snprintf(err, errcap, "eglGetPlatformDisplay returned no display"); return 1; }
  EGLint maj = 0, min = 0;
  if (!e->eglInitialize(dpy, &maj, &min)) {
    snprintf(err, errcap, "eglInitialize failed (0x%x)", e->eglGetError());
    return 1;
  }
  if (!e->eglBindAPI(EGL_OPENGL_API)) {
    snprintf(err, errcap, "eglBindAPI(OpenGL) failed (0x%x)", e->eglGetError());
    return 1;
  }
  EGLint cfg_attr[] = {EGL_SURFACE_TYPE, EGL_PBUFFER_BIT, EGL_RENDERABLE_TYPE, EGL_OPENGL_BIT, EGL_NONE};
  EGLConfig cfg = NULL;
  EGLint n = 0;
  e->eglChooseConfig(dpy, cfg_attr, &cfg, 1, &n);
  EGLint versions[3][2] = {{4, 5}, {4, 3}, {4, 1}};
  EGLContext ctx = NULL;
  for (int i = 0; i < 3 && !ctx; i++) {
    EGLint ctx_attr[] = {EGL_CONTEXT_MAJOR_VERSION, versions[i][0], EGL_CONTEXT_MINOR_VERSION,
                         versions[i][1], EGL_CONTEXT_OPENGL_PROFILE_MASK,
                         EGL_CONTEXT_OPENGL_CORE_PROFILE_BIT, EGL_NONE};
    ctx = e->eglCreateContext(dpy, cfg, EGL_NO_CONTEXT, ctx_attr);
  }
  if (!ctx) { snprintf(err, errcap, "eglCreateContext failed (0x%x)", e->eglGetError()); return 1; }
  if (!e->eglMakeCurrent(dpy, EGL_NO_SURFACE, EGL_NO_SURFACE, ctx)) {
    snprintf(err, errcap, "eglMakeCurrent failed (0x%x)", e->eglGetError());
    return 1;
  }
  return gl_load(g, e, err, errcap);
}

static int render_frame(const NcelIr *ir, const NcelFrame *fr, const char *shader_path,
                        const char *out_png, int verbose) {
  char err[4096];
  Egl e;
  Gl g;
  if (gl_init(&e, &g, err, sizeof err)) { fprintf(stderr, "ncel-gl: %s\n", err); return 1; }
  char *shader_src = shader_path ? read_text_file(shader_path) : NULL;
  if (!shader_src) { fprintf(stderr, "ncel-gl: cannot read shader %s\n", shader_path ? shader_path : "(none)"); return 1; }
  GLuint vs = compile_shader(&g, GL_VERTEX_SHADER,
      "#version 430 core\n"
      "void main(){ vec2 p=vec2(float((gl_VertexID<<1)&2), float(gl_VertexID&2));"
      " gl_Position=vec4(p*2.0-1.0,0.0,1.0); }\n", err, sizeof err);
  if (!vs) { fprintf(stderr, "ncel-gl: %s\n", err); return 1; }
  GLuint fs = compile_shader(&g, GL_FRAGMENT_SHADER, shader_src, err, sizeof err);
  if (!fs) { fprintf(stderr, "ncel-gl: %s\n", err); return 1; }
  GLuint prog = g.glCreateProgram();
  g.glAttachShader(prog, vs);
  g.glAttachShader(prog, fs);
  g.glLinkProgram(prog);
  GLint ok = 0;
  g.glGetProgramiv(prog, GL_LINK_STATUS, &ok);
  if (!ok) {
    char log[4096];
    GLsizei len = 0;
    g.glGetProgramInfoLog(prog, sizeof(log) - 1, &len, log);
    log[len > 0 ? len : 0] = 0;
    fprintf(stderr, "ncel-gl: program link failed: %s\n", log);
    return 1;
  }
  g.glUseProgram(prog);

  int W = (int)ir->width, H = (int)ir->height;
  GLint max_tbo = 0, max_tex = 0;
  g.glGetIntegerv(GL_MAX_TEXTURE_BUFFER_SIZE, &max_tbo);
  g.glGetIntegerv(GL_MAX_TEXTURE_SIZE, &max_tex);
  if (max_tex > 0 && (W > max_tex || H > max_tex)) {
    fprintf(stderr, "ncel-gl: canvas %dx%d exceeds GL_MAX_TEXTURE_SIZE %d\n", W, H, max_tex);
    return 1;
  }

  /* 32px x 8px spatial cells. Edges wholly right of a cell contribute a
   * y-only parity seed; only edges intersecting its x extent go to GLSL.
   * This is an exact partition of the original ray test, not raster fitting. */
  const int tile_count = (W + 31) / 32;
  const int band_count = (H + 7) / 8;
  const int sample_rows = H * (int)fr->aa;
  size_t total_edges = 0;
  size_t total_spans = (size_t)fr->layer_count * band_count * tile_count;
  size_t total_seeds = (size_t)fr->layer_count * sample_rows * tile_count;
  for (uint32_t li = 0; li < fr->layer_count; li++) {
    const NcelLayer *l = &fr->layers[li];
    for (uint32_t b = 0; b < l->band_count; b++) {
      for (uint32_t j = l->spans[b*2]; j < l->spans[b*2+1]; j++) {
        const float *e = &l->edges[(size_t)j*4];
        int lo = (int)floorf(fminf(e[0], e[2])/32.0f);
        int hi = (int)floorf(fmaxf(e[0], e[2])/32.0f);
        if (lo < 0) lo = 0;
        if (hi >= tile_count) hi = tile_count-1;
        if (hi >= lo) total_edges += (size_t)(hi-lo+1);
      }
    }
  }
  if (max_tbo > 0 && (total_edges > (size_t)max_tbo || total_spans > (size_t)max_tbo || total_seeds > (size_t)max_tbo)) {
    fprintf(stderr, "ncel-gl: geometry exceeds GL_MAX_TEXTURE_BUFFER_SIZE %d\n", max_tbo);
    return 1;
  }
  float *edges = (float *)malloc((total_edges ? total_edges : 1) * 4 * sizeof(float));
  int32_t *spans = (int32_t *)malloc((total_spans ? total_spans : 1) * 2 * sizeof(int32_t));
  float *colors = (float *)malloc(((size_t)fr->layer_count + 1) * 4 * sizeof(float));
  uint8_t *seeds = (uint8_t *)calloc(total_seeds ? total_seeds : 1, 1);
  if (!edges || !spans || !colors || !seeds) { fprintf(stderr, "ncel-gl: out of memory\n"); return 1; }
  colors[0] = fr->paper_r; colors[1] = fr->paper_g; colors[2] = fr->paper_b; colors[3] = 255.0f;
  size_t eoff = 0, soff = 0;
  for (uint32_t li = 0; li < fr->layer_count; li++) {
    const NcelLayer *l = &fr->layers[li];
    colors[(size_t)(li + 1) * 4 + 0] = l->r;
    colors[(size_t)(li + 1) * 4 + 1] = l->g;
    colors[(size_t)(li + 1) * 4 + 2] = l->b;
    colors[(size_t)(li + 1) * 4 + 3] = 255.0f;
    for (uint32_t b = 0; b < l->band_count; b++) {
      for (int tile = 0; tile < tile_count; tile++) {
        spans[soff*2] = (int32_t)eoff;
        for (uint32_t j = l->spans[b*2]; j < l->spans[b*2+1]; j++) {
          const float *e = &l->edges[(size_t)j*4];
          if (fmaxf(e[0], e[2]) >= tile*32.0f && fminf(e[0], e[2]) < (tile+1)*32.0f) {
            memcpy(&edges[eoff*4], e, 4*sizeof(float));
            eoff++;
          }
        }
        spans[soff*2+1] = (int32_t)eoff;
        soff++;
      }
      /* Difference-XOR prefix: one edge toggles every cell strictly left
       * of min(x0,x1). Only exact y comparisons are needed; GLSL keeps the
       * original float32 crossing formula for every local edge. */
      for (uint32_t j = l->spans[b*2]; j < l->spans[b*2+1]; j++) {
        const float *e = &l->edges[(size_t)j*4];
        int end = (int)floorf(fminf(e[0], e[2])/32.0f);
        if (end > tile_count) end = tile_count;
        if (end <= 0) continue;
        int last = (int)(b+1)*8*(int)fr->aa;
        if (last > sample_rows) last = sample_rows;
        for (int row = (int)b*8*(int)fr->aa; row < last; row++) {
          float py = ((float)row+0.5f)/(float)fr->aa;
          if ((e[1] > py) != (e[3] > py)) {
            size_t at = ((size_t)li*sample_rows+row)*tile_count;
            seeds[at] ^= 1;
            if (end < tile_count) seeds[at+end] ^= 1;
          }
        }
      }
    }
    for (int row = 0; row < sample_rows; row++) {
      size_t at = ((size_t)li*sample_rows+row)*tile_count;
      for (int tile = 1; tile < tile_count; tile++) seeds[at+tile] ^= seeds[at+tile-1];
    }
  }
  total_edges = eoff;

  GLuint bufs[4] = {0}, texs[4] = {0};
  g.glGenBuffers(4, bufs);
  g.glGenTextures(4, texs);
  g.glBindBuffer(GL_ARRAY_BUFFER, bufs[0]);
  g.glBufferData(GL_ARRAY_BUFFER, (GLsizeiptr)((total_edges ? total_edges : 1) * 4 * sizeof(float)),
                 edges, GL_STATIC_DRAW);
  g.glBindTexture(GL_TEXTURE_BUFFER, texs[0]);
  g.glTexBuffer(GL_TEXTURE_BUFFER, GL_RGBA32F, bufs[0]);
  g.glBindBuffer(GL_ARRAY_BUFFER, bufs[1]);
  g.glBufferData(GL_ARRAY_BUFFER, (GLsizeiptr)((total_spans ? total_spans : 1) * 2 * sizeof(int32_t)),
                 spans, GL_STATIC_DRAW);
  g.glBindTexture(GL_TEXTURE_BUFFER, texs[1]);
  g.glTexBuffer(GL_TEXTURE_BUFFER, GL_RG32I, bufs[1]);
  g.glBindBuffer(GL_ARRAY_BUFFER, bufs[2]);
  g.glBufferData(GL_ARRAY_BUFFER, (GLsizeiptr)(((size_t)fr->layer_count + 1) * 4 * sizeof(float)),
                 colors, GL_STATIC_DRAW);
  g.glBindTexture(GL_TEXTURE_BUFFER, texs[2]);
  g.glTexBuffer(GL_TEXTURE_BUFFER, GL_RGBA32F, bufs[2]);
  g.glBindBuffer(GL_ARRAY_BUFFER, bufs[3]);
  g.glBufferData(GL_ARRAY_BUFFER, (GLsizeiptr)(total_seeds ? total_seeds : 1), seeds, GL_STATIC_DRAW);
  g.glBindTexture(GL_TEXTURE_BUFFER, texs[3]);
  g.glTexBuffer(GL_TEXTURE_BUFFER, 0x8232 /* GL_R8UI */, bufs[3]);

  GLint u_edges = g.glGetUniformLocation(prog, "edgeTex");
  GLint u_spans = g.glGetUniformLocation(prog, "spanTex");
  GLint u_colors = g.glGetUniformLocation(prog, "colorTex");
  GLint u_bands = g.glGetUniformLocation(prog, "bandCount");
  GLint u_layers = g.glGetUniformLocation(prog, "layerCount");
  GLint u_aa = g.glGetUniformLocation(prog, "aa");
  GLint u_canvas = g.glGetUniformLocation(prog, "canvas");
  g.glUniform1i(u_edges, 0);
  g.glUniform1i(u_spans, 1);
  g.glUniform1i(u_colors, 2);
  g.glUniform1i(g.glGetUniformLocation(prog, "seedTex"), 3);
  g.glUniform1i(g.glGetUniformLocation(prog, "tileCount"), tile_count);
  g.glUniform1i(u_bands, fr->layer_count ? (GLint)fr->layers[0].band_count : 1);
  g.glUniform1i(u_layers, (GLint)fr->layer_count);
  g.glUniform1i(u_aa, (GLint)fr->aa);
  g.glUniform2f(u_canvas, (GLfloat)W, (GLfloat)H);
  for (int i = 0; i < 4; i++) {
    g.glActiveTexture((GLenum)(GL_TEXTURE0 + i));
    g.glBindTexture(GL_TEXTURE_BUFFER, texs[i]);
  }

  GLuint fbo = 0, color = 0;
  g.glGenTextures(1, &color);
  g.glBindTexture(GL_TEXTURE_2D, color);
  g.glTexImage2D(GL_TEXTURE_2D, 0, GL_RGBA32F, W, H, 0, GL_RGBA, GL_FLOAT, NULL);
  g.glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MIN_FILTER, GL_NEAREST);
  g.glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MAG_FILTER, GL_NEAREST);
  g.glGenFramebuffers(1, &fbo);
  g.glBindFramebuffer(GL_FRAMEBUFFER, fbo);
  g.glFramebufferTexture2D(GL_FRAMEBUFFER, GL_COLOR_ATTACHMENT0, GL_TEXTURE_2D, color, 0);
  if (g.glCheckFramebufferStatus(GL_FRAMEBUFFER) != GL_FRAMEBUFFER_COMPLETE) {
    fprintf(stderr, "ncel-gl: framebuffer incomplete\n");
    return 1;
  }
  GLuint vao = 0;
  g.glGenVertexArrays(1, &vao);
  g.glBindVertexArray(vao);
  g.glViewport(0, 0, W, H);
  g.glDrawArrays(GL_TRIANGLES, 0, 3);
  g.glFinish();
  GLenum glerr = g.glGetError();
  if (glerr != GL_NO_ERROR) {
    fprintf(stderr, "ncel-gl: GL error 0x%x after draw\n", glerr);
    return 1;
  }
  float *rgba = (float *)malloc((size_t)W * H * 4 * sizeof(float));
  uint8_t *rgb = (uint8_t *)malloc((size_t)W * H * 3);
  if (!rgba || !rgb) { fprintf(stderr, "ncel-gl: out of memory\n"); return 1; }
  g.glReadPixels(0, 0, W, H, GL_RGBA, GL_FLOAT, rgba);
  apply_grain_and_pack(rgba, W, H, (int)fr->aa, fr->grain, ir->seed, rgb);
  if (!stbi_write_png(out_png, W, H, 3, rgb, W * 3)) {
    fprintf(stderr, "ncel-gl: could not write %s\n", out_png);
    return 1;
  }
  if (verbose) {
    fprintf(stderr, "ncel-gl: %dx%d aa=%u layers=%u edges=%zu spans=%zu renderer=%s\n",
            W, H, fr->aa, fr->layer_count, total_edges, total_spans, g.glGetString(0x1F01));
  }
  free(edges); free(spans); free(colors); free(seeds); free(rgba); free(rgb); free(shader_src);
  g.glDeleteFramebuffers(1, &fbo);
  g.glDeleteTextures(1, &color);
  g.glDeleteTextures(4, texs);
  g.glDeleteBuffers(4, bufs);
  g.glDeleteVertexArrays(1, &vao);
  g.glDeleteProgram(prog);
  g.glDeleteShader(vs);
  g.glDeleteShader(fs);
  return 0;
}

static int probe(void) {
  char err[4096];
  Egl e;
  Gl g;
  if (gl_init(&e, &g, err, sizeof err)) {
    printf("{\"ok\":false,\"error\":\"%s\"}\n", err);
    return 1;
  }
  const unsigned char *ver = g.glGetString(0x1F02);
  const unsigned char *ren = g.glGetString(0x1F01);
  const unsigned char *glsl = g.glGetString(0x8B8C);
  const unsigned char *vendor = g.glGetString(0x1F00);
  printf("{\"ok\":true,\"gl_version\":\"%s\",\"gl_renderer\":\"%s\",\"gl_vendor\":\"%s\",\"glsl_version\":\"%s\"}\n",
         ver ? (const char *)ver : "", ren ? (const char *)ren : "", vendor ? (const char *)vendor : "",
         glsl ? (const char *)glsl : "");
  return 0;
}

static int check_shader(const char *path) {
  char err[4096];
  Egl e;
  Gl g;
  if (gl_init(&e, &g, err, sizeof err)) { printf("{\"ok\":false,\"error\":\"%s\"}\n", err); return 1; }
  char *src = read_text_file(path);
  if (!src) { printf("{\"ok\":false,\"error\":\"cannot read shader\"}\n"); return 1; }
  GLuint vs = compile_shader(&g, GL_VERTEX_SHADER,
      "#version 430 core\n"
      "void main(){ vec2 p=vec2(float((gl_VertexID<<1)&2), float(gl_VertexID&2));"
      " gl_Position=vec4(p*2.0-1.0,0.0,1.0); }\n", err, sizeof err);
  if (!vs) { printf("{\"ok\":false,\"error\":\"%s\"}\n", err); free(src); return 1; }
  GLuint fs = compile_shader(&g, GL_FRAGMENT_SHADER, src, err, sizeof err);
  free(src);
  if (!fs) { printf("{\"ok\":false,\"error\":\"%s\"}\n", err); return 1; }
  GLuint prog = g.glCreateProgram();
  g.glAttachShader(prog, vs);
  g.glAttachShader(prog, fs);
  g.glLinkProgram(prog);
  GLint ok = 0;
  g.glGetProgramiv(prog, GL_LINK_STATUS, &ok);
  if (!ok) {
    char log[4096];
    GLsizei len = 0;
    g.glGetProgramInfoLog(prog, sizeof(log) - 1, &len, log);
    log[len > 0 ? len : 0] = 0;
    printf("{\"ok\":false,\"error\":\"link failed: %s\"}\n", log);
    return 1;
  }
  printf("{\"ok\":true,\"glsl_version\":\"%s\"}\n", g.glGetString(0x8B8C));
  return 0;
}

int main(int argc, char **argv) {
  const char *ir_path = NULL, *shader = NULL, *out = NULL, *check = NULL;
  int frame = 0, verbose = 0, do_probe = 0;
  for (int i = 1; i < argc; i++) {
    if (!strcmp(argv[i], "--probe")) do_probe = 1;
    else if (!strcmp(argv[i], "--check-shader") && i + 1 < argc) check = argv[++i];
    else if (!strcmp(argv[i], "--ir") && i + 1 < argc) ir_path = argv[++i];
    else if (!strcmp(argv[i], "--shader") && i + 1 < argc) shader = argv[++i];
    else if (!strcmp(argv[i], "--out") && i + 1 < argc) out = argv[++i];
    else if (!strcmp(argv[i], "--frame") && i + 1 < argc) frame = atoi(argv[++i]);
    else if (!strcmp(argv[i], "--verbose")) verbose = 1;
    else {
      fprintf(stderr, "ncel-gl: unknown argument %s\n", argv[i]);
      return 2;
    }
  }
  if (do_probe) return probe();
  if (check) return check_shader(check);
  if (!ir_path || !out) {
    fprintf(stderr, "usage: ncel-gl --ir FILE --out PNG [--frame N] [--shader FILE]\n");
    return 2;
  }
  NcelIr ir;
  char err[4096];
  if (ncel_ir_read(ir_path, &ir, err, sizeof err)) {
    fprintf(stderr, "ncel-gl: %s\n", err);
    return 1;
  }
  const NcelFrame *fr = ncel_ir_frame(&ir, frame);
  if (!fr) { fprintf(stderr, "ncel-gl: IR has no frames\n"); return 1; }
  int rc = render_frame(&ir, fr, shader, out, verbose);
  ncel_ir_free(&ir);
  return rc;
}
