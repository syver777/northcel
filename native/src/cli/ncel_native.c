/* NorthCel native runtime - `ncel-native` CLI.
 *
 * Orchestrates the three genuine stages:
 *   1. ncel-ast  (MoonBit: typed AST, contour decode, frame expansion, IR)
 *   2. bend      (Bend/HVM2: stateless agent-swarm evaluation)
 *   3. ncel-gl   (EGL + GLSL: N x N subpixel even-odd rasterisation)
 *
 * The binary never falls back to the Python reference renderer; wrapper
 * installers (pip/npm/brew) decide policy, not this program.
 */
#define _GNU_SOURCE
#include <errno.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/stat.h>
#include <sys/types.h>
#include <sys/wait.h>
#include <time.h>
#include <unistd.h>

#include "sha256.h"

#define NCEL_VERSION "0.4.0"
#define NCEL_SPEC "0.3.0-draft"
#define PATH_MAX_LOCAL 4096

static double now_s(void) {
  struct timespec ts;
  clock_gettime(CLOCK_MONOTONIC, &ts);
  return (double)ts.tv_sec + (double)ts.tv_nsec / 1e9;
}

static char *xstrdup(const char *s) {
  if (!s) return NULL;
  size_t n = strlen(s) + 1;
  char *d = (char *)malloc(n);
  if (d) memcpy(d, s, n);
  return d;
}

static int file_exists(const char *p) {
  struct stat st;
  return stat(p, &st) == 0 && S_ISREG(st.st_mode);
}

static char *join_path(const char *a, const char *b) {
  size_t n = strlen(a) + strlen(b) + 2;
  char *p = (char *)malloc(n);
  snprintf(p, n, "%s/%s", a, b);
  return p;
}

static char *read_text(const char *path, size_t *len_out) {
  FILE *f = fopen(path, "rb");
  if (!f) return NULL;
  fseek(f, 0, SEEK_END);
  long n = ftell(f);
  if (n < 0) { fclose(f); return NULL; }
  fseek(f, 0, SEEK_SET);
  char *s = (char *)malloc((size_t)n + 1);
  if (!s) { fclose(f); return NULL; }
  size_t got = fread(s, 1, (size_t)n, f);
  fclose(f);
  s[got] = 0;
  if (len_out) *len_out = got;
  return s;
}

static int sha256_file(const char *path, char out[65]) {
  size_t n = 0;
  char *s = read_text(path, &n);
  if (!s) return 1;
  ncel_sha256_hex(s, n, out);
  free(s);
  return 0;
}

static int json_find_key(const char *s, const char *key, const char **at) {
  if (!s) return 0;
  char pat[256];
  snprintf(pat, sizeof pat, "\"%s\"", key);
  const char *p = strstr(s, pat);
  if (!p) return 0;
  p += strlen(pat);
  while (*p == ' ' || *p == '\t' || *p == '\n' || *p == '\r') p++;
  if (*p != ':') return 0;
  p++;
  while (*p == ' ' || *p == '\t' || *p == '\n' || *p == '\r') p++;
  *at = p;
  return 1;
}

static int json_int(const char *s, const char *key, long *out) {
  const char *p;
  if (!json_find_key(s, key, &p)) return 0;
  char *end = NULL;
  long v = strtol(p, &end, 10);
  if (end == p) return 0;
  *out = v;
  return 1;
}

static int json_str(const char *s, const char *key, char *out, size_t cap) {
  const char *p;
  if (!json_find_key(s, key, &p)) return 0;
  if (*p != '"') return 0;
  p++;
  size_t i = 0;
  while (*p && *p != '"' && i + 1 < cap) {
    if (*p == '\\' && p[1]) {
      p++;
      out[i++] = *p == 'n' ? '\n' : *p == 't' ? '\t' : *p;
    } else {
      out[i++] = *p;
    }
    p++;
  }
  out[i] = 0;
  return 1;
}

static void json_escape(const char *s, char *out, size_t cap) {
  size_t i = 0;
  for (const char *p = s; *p && i + 2 < cap; p++) {
    unsigned char c = (unsigned char)*p;
    if (c == '"' || c == '\\') { out[i++] = '\\'; out[i++] = (char)c; }
    else if (c == '\n') { out[i++] = '\\'; out[i++] = 'n'; }
    else if (c == '\r') { out[i++] = '\\'; out[i++] = 'r'; }
    else if (c == '\t') { out[i++] = '\\'; out[i++] = 't'; }
    else if (c < 32) out[i++] = '?';
    else out[i++] = (char)c;
  }
  out[i] = 0;
}

/* ------------------------------------------------------------- tool lookup */

static char *find_tool(const char *name, const char *envvar, const char *exe_dir) {
  const char *env = envvar ? getenv(envvar) : NULL;
  if (env && file_exists(env)) return xstrdup(env);
  if (exe_dir) {
    char *cand = join_path(exe_dir, name);
    if (file_exists(cand)) return cand;
    free(cand);
    char *up = join_path(exe_dir, "..");
    char *upbin = join_path(up, "bin");
    char *cand2 = join_path(upbin, name);
    if (file_exists(cand2)) { free(up); free(upbin); return cand2; }
    free(upbin);
    char *cand3 = join_path(up, name);
    if (file_exists(cand3)) { free(up); return cand3; }
    free(cand3);
    free(up);
  }
  const char *path = getenv("PATH");
  if (path) {
    char *copy = xstrdup(path);
    char *save = NULL;
    for (char *tok = strtok_r(copy, ":", &save); tok; tok = strtok_r(NULL, ":", &save)) {
      char *cand = join_path(tok, name);
      if (file_exists(cand)) { free(copy); return cand; }
      free(cand);
    }
    free(copy);
  }
  return NULL;
}

/* ---------------------------------------------------------------- spawning */

static int run_proc(char *const argv[], const char *stdout_path, int quiet) {
  pid_t pid = fork();
  if (pid < 0) return -1;
  if (pid == 0) {
    if (stdout_path) {
      FILE *f = fopen(stdout_path, "wb");
      if (!f) _exit(127);
      dup2(fileno(f), STDOUT_FILENO);
      fclose(f);
    }
    if (quiet) {
      FILE *n = fopen("/dev/null", "wb");
      if (n) { dup2(fileno(n), STDERR_FILENO); fclose(n); }
    }
    execv(argv[0], argv);
    _exit(127);
  }
  int status = 0;
  if (waitpid(pid, &status, 0) < 0) return -1;
  if (WIFEXITED(status)) return WEXITSTATUS(status);
  return -1;
}

static int run_capture(char *const argv[], char *out, size_t cap) {
  char tmp[PATH_MAX_LOCAL];
  snprintf(tmp, sizeof tmp, "/tmp/ncel-cap-%d.out", (int)getpid());
  int rc = run_proc(argv, tmp, 1);
  char *t = read_text(tmp, NULL);
  unlink(tmp);
  if (t) {
    snprintf(out, cap, "%s", t);
    free(t);
  } else if (cap) {
    out[0] = 0;
  }
  return rc;
}

/* ------------------------------------------------------------- shader path */

static char *resolve_shader(const char *exe_dir, const char *name) {
  const char *env = getenv("NCEL_SHADER");
  if (env && file_exists(env)) {
    if (!strcmp(name, "draw430.glsl")) return xstrdup(env);
    char *dir = xstrdup(env);
    char *slash = strrchr(dir, '/');
    if (slash) {
      *slash = 0;
      char *sib = join_path(dir, name);
      if (file_exists(sib)) { free(dir); return sib; }
      free(sib);
    }
    free(dir);
  }
  char *cands[6];
  int n = 0;
  if (exe_dir) {
    char *share = join_path(exe_dir, "../share/ncel");
    cands[n++] = join_path(share, name);
    free(share);
    cands[n++] = join_path(exe_dir, name);
    char *sh = join_path(exe_dir, "../shaders");
    cands[n++] = join_path(sh, name);
    free(sh);
  }
  cands[n++] = join_path(".", name);
  cands[n++] = join_path("shaders", name);
  for (int i = 0; i < n; i++) {
    if (file_exists(cands[i])) {
      for (int j = 0; j < n; j++) if (j != i) free(cands[j]);
      return cands[i];
    }
  }
  for (int i = 0; i < n; i++) free(cands[i]);
  return NULL;
}

static char *exe_directory(void) {
  char buf[PATH_MAX_LOCAL];
  ssize_t n = readlink("/proc/self/exe", buf, sizeof buf - 1);
  if (n <= 0) return xstrdup(".");
  buf[n] = 0;
  char *s = strrchr(buf, '/');
  if (!s) return xstrdup(".");
  *s = 0;
  return xstrdup(buf);
}

/* ---------------------------------------------------------------- pipeline */

typedef struct {
  char bend_path[PATH_MAX_LOCAL];
  char bend_out[PATH_MAX_LOCAL];
  char ir_path[PATH_MAX_LOCAL];
  long tasks, bend_agents, bend_points;
  long rings, vertices, source_bytes, ir_bytes, layer_count;
  long declared_frames, fps, width, height;
  char spec[128], name[256], precision[64], kind[32];
  double t_bend, t_ir, t_gl;
} Pipeline;

static void tmp_path(char *out, size_t cap, const char *dir, const char *name) {
  snprintf(out, cap, "%s/%s", dir, name);
}

typedef struct {
  const char *ast_exe;
  const char *bend_exe;
  const char *gl_exe;
  const char *shader;
} Tools;

static int pipeline_render(
  const char *src, int frame, int seed_has, int seed, const char *tmpdir,
  const Tools *tl, const char *out_png, Pipeline *pl, char *err, size_t errcap) {
  memset(pl, 0, sizeof(*pl));
  char bend_json[PATH_MAX_LOCAL], ir_json[PATH_MAX_LOCAL];
  tmp_path(pl->bend_path, sizeof pl->bend_path, tmpdir, "swarm.bend");
  tmp_path(pl->bend_out, sizeof pl->bend_out, tmpdir, "swarm.out");
  tmp_path(pl->ir_path, sizeof pl->ir_path, tmpdir, "frame.ir");
  tmp_path(bend_json, sizeof bend_json, tmpdir, "bend.json");
  tmp_path(ir_json, sizeof ir_json, tmpdir, "ir.json");
  char frame_s[32], seed_s[32];
  snprintf(frame_s, sizeof frame_s, "%d", frame);
  snprintf(seed_s, sizeof seed_s, "%d", seed);

  double t0 = now_s();
  char *argv1[12];
  int a = 0;
  argv1[a++] = (char *)tl->ast_exe;
  argv1[a++] = (char *)"emit-bend";
  argv1[a++] = (char *)src;
  argv1[a++] = pl->bend_path;
  argv1[a++] = (char *)"--frame";
  argv1[a++] = frame_s;
  if (seed_has) { argv1[a++] = (char *)"--seed"; argv1[a++] = seed_s; }
  argv1[a] = NULL;
  int rc = run_proc(argv1, bend_json, 0);
  char *bjson = read_text(bend_json, NULL);
  if (rc != 0) {
    snprintf(err, errcap, "AST swarm stage failed: %.4000s", bjson ? bjson : "(no output)");
    free(bjson);
    return 1;
  }
  json_int(bjson, "tasks", &pl->tasks);
  json_int(bjson, "agents", &pl->bend_agents);
  json_int(bjson, "points", &pl->bend_points);

  if (pl->tasks > 0) {
    char *bargv[5];
    bargv[0] = (char *)tl->bend_exe;
    bargv[1] = (char *)"run-c";
    bargv[2] = pl->bend_path;
    bargv[3] = NULL;
    if (run_proc(bargv, pl->bend_out, 0)) {
      snprintf(err, errcap, "Bend/HVM2 swarm stage failed (see stderr above)");
      free(bjson);
      return 1;
    }
  }
  free(bjson);
  pl->t_bend = now_s() - t0;

  double t1 = now_s();
  char *argv2[14];
  a = 0;
  argv2[a++] = (char *)tl->ast_exe;
  argv2[a++] = (char *)"emit-ir";
  argv2[a++] = (char *)src;
  argv2[a++] = pl->ir_path;
  argv2[a++] = (char *)"--frame";
  argv2[a++] = frame_s;
  if (seed_has) { argv2[a++] = (char *)"--seed"; argv2[a++] = seed_s; }
  if (pl->tasks > 0) { argv2[a++] = (char *)"--bend-results"; argv2[a++] = pl->bend_out; }
  argv2[a] = NULL;
  rc = run_proc(argv2, ir_json, 0);
  char *ijson = read_text(ir_json, NULL);
  if (rc != 0) {
    snprintf(err, errcap, "AST IR stage failed: %s", ijson ? ijson : "(no output)");
    free(ijson);
    return 1;
  }
  json_int(ijson, "rings", &pl->rings);
  json_int(ijson, "vertices", &pl->vertices);
  json_int(ijson, "source_bytes", &pl->source_bytes);
  json_int(ijson, "ir_bytes", &pl->ir_bytes);
  json_int(ijson, "declared_frames", &pl->declared_frames);
  json_int(ijson, "fps", &pl->fps);
  json_int(ijson, "width", &pl->width);
  json_int(ijson, "height", &pl->height);
  json_int(ijson, "layers", &pl->layer_count);
  if (!json_str(ijson, "spec_version", pl->spec, sizeof pl->spec))
    snprintf(pl->spec, sizeof pl->spec, "%s", NCEL_SPEC);
  json_str(ijson, "name", pl->name, sizeof pl->name);
  if (!json_str(ijson, "kind", pl->kind, sizeof pl->kind))
    snprintf(pl->kind, sizeof pl->kind, "%s", "scene");
  json_str(ijson, "precision", pl->precision, sizeof pl->precision);
  free(ijson);
  pl->t_ir = now_s() - t1;

  double t2 = now_s();
  char *argv3[12];
  a = 0;
  argv3[a++] = (char *)tl->gl_exe;
  argv3[a++] = (char *)"--ir";
  argv3[a++] = pl->ir_path;
  argv3[a++] = (char *)"--frame";
  argv3[a++] = frame_s;
  argv3[a++] = (char *)"--out";
  argv3[a++] = (char *)out_png;
  if (tl->shader) { argv3[a++] = (char *)"--shader"; argv3[a++] = (char *)tl->shader; }
  argv3[a] = NULL;
  if (run_proc(argv3, NULL, 0)) {
    snprintf(err, errcap, "GLSL raster stage failed (see stderr above)");
    return 1;
  }
  pl->t_gl = now_s() - t2;
  return 0;
}

/* ------------------------------------------------------------------ doctor */

static int cmd_doctor(const char *exe_dir) {
  char *ast = find_tool("ncel-ast", "NCEL_AST", exe_dir);
  char *gl = find_tool("ncel-gl", "NCEL_GL", exe_dir);
  char *bend = find_tool("bend", "NCEL_BEND", exe_dir);
  char *hvm = find_tool("hvm", "NCEL_HVM", exe_dir);
  if (!hvm && bend) {
    char *dir = xstrdup(bend);
    char *slash = strrchr(dir, '/');
    if (slash) {
      *slash = 0;
      char *cand = join_path(dir, "hvm");
      if (file_exists(cand)) hvm = cand; else free(cand);
    }
    free(dir);
  }
  char *ffmpeg = find_tool("ffmpeg", "NCEL_FFMPEG", exe_dir);
  char bend_ver[512] = "", hvm_ver[512] = "";
  if (bend) {
    char *argv[] = {bend, "--version", NULL};
    run_capture(argv, bend_ver, sizeof bend_ver);
  }
  if (hvm) {
    char *argv[] = {hvm, "--version", NULL};
    run_capture(argv, hvm_ver, sizeof hvm_ver);
  }
  for (char *p = bend_ver; *p; p++) if (*p == '\n' || *p == '\r') *p = ' ';
  for (char *p = hvm_ver; *p; p++) if (*p == '\n' || *p == '\r') *p = ' ';

  char gl_json[4096] = "{}";
  if (gl) {
    char *argv[] = {gl, "--probe", NULL};
    run_capture(argv, gl_json, sizeof gl_json);
  }
  char *sh430 = resolve_shader(exe_dir, "draw430.glsl");
  char *sh410 = resolve_shader(exe_dir, "draw410.glsl");
  char h430[65] = "", h410[65] = "";
  char ok430[2048] = "{}", ok410[2048] = "{}";
  if (sh430) {
    sha256_file(sh430, h430);
    if (gl) { char *argv[] = {gl, "--check-shader", sh430, NULL}; run_capture(argv, ok430, sizeof ok430); }
  }
  if (sh410) {
    sha256_file(sh410, h410);
    if (gl) { char *argv[] = {gl, "--check-shader", sh410, NULL}; run_capture(argv, ok410, sizeof ok410); }
  }
  char e430[PATH_MAX_LOCAL] = "", e410[PATH_MAX_LOCAL] = "";
  if (sh430) json_escape(sh430, e430, sizeof e430);
  if (sh410) json_escape(sh410, e410, sizeof e410);
  int ok = ast && gl && bend && hvm;
  printf("{\"ok\":%s,\"tool\":\"ncel-native\",\"version\":\"%s\",\"spec_version\":\"%s\","
         "\"platform\":\"linux-x86_64\",\"moonbit_stage\":%s,\"gl_stage\":%s,"
         "\"bend_path\":\"%s\",\"bend_version\":\"%s\",\"hvm_path\":\"%s\",\"hvm_version\":\"%s\","
         "\"gl\":%s,\"shaders\":{\"draw430\":{\"path\":\"%s\",\"sha256\":\"%s\",\"compile\":%s},"
         "\"draw410\":{\"path\":\"%s\",\"sha256\":\"%s\",\"compile\":%s}},"
         "\"ffmpeg\":%s,\"python_fallback\":false}\n",
         ok ? "true" : "false", NCEL_VERSION, NCEL_SPEC,
         ast ? "true" : "false", gl ? "true" : "false",
         bend ? bend : "", bend_ver, hvm ? hvm : "", hvm_ver,
         gl_json, e430, h430, ok430, e410, h410, ok410,
         ffmpeg ? "true" : "false");
  return ok ? 0 : 1;
}

/* ------------------------------------------------------------------- check */

static int cmd_check(const char *exe_dir, int argc, char **argv) {
  const char *file = NULL;
  int json = 0;
  for (int i = 2; i < argc; i++) {
    if (!strcmp(argv[i], "--json")) json = 1;
    else file = argv[i];
  }
  if (!file) { fprintf(stderr, "usage: ncel-native check FILE [--json]\n"); return 2; }
  if (!file_exists(file)) {
    if (json) printf("{\"ok\":false,\"partial\":false,\"validator\":\"native\",\"file\":\"%s\",\"spec_version\":null,\"errors\":[\"1:1: error: File not found: %s\"],\"warnings\":[]}\n", file, file);
    else fprintf(stderr, "1:1: error: File not found: %s\n", file);
    return 1;
  }
  char *ast = find_tool("ncel-ast", "NCEL_AST", exe_dir);
  if (!ast) { fprintf(stderr, "ncel-native: ncel-ast not found\n"); return 1; }
  char *aargv[6];
  int a = 0;
  aargv[a++] = ast;
  aargv[a++] = (char *)"check";
  aargv[a++] = (char *)file;
  if (json) aargv[a++] = (char *)"--json";
  aargv[a] = NULL;
  int status = 0;
  pid_t pid = fork();
  if (pid == 0) { execv(aargv[0], aargv); _exit(127); }
  waitpid(pid, &status, 0);
  free(ast);
  return WIFEXITED(status) ? WEXITSTATUS(status) : 1;
}

/* -------------------------------------------------------------------- info */

static int cmd_info(const char *exe_dir, int argc, char **argv) {
  const char *file = NULL;
  for (int i = 2; i < argc; i++) if (strcmp(argv[i], "--json")) file = argv[i];
  if (!file) { fprintf(stderr, "usage: ncel-native info FILE [--json]\n"); return 2; }
  char *ast = find_tool("ncel-ast", "NCEL_AST", exe_dir);
  if (!ast) { fprintf(stderr, "ncel-native: ncel-ast not found\n"); return 1; }
  char *aargv[5] = {ast, "info", (char *)file, "--json", NULL};
  int status = 0;
  pid_t pid = fork();
  if (pid == 0) { execv(aargv[0], aargv); _exit(127); }
  waitpid(pid, &status, 0);
  free(ast);
  return WIFEXITED(status) ? WEXITSTATUS(status) : 1;
}

/* ------------------------------------------------------------------ render */

static void print_receipt(const char *src, const char *out, int frame, int seed_has, int seed,
                          const Pipeline *pl, const char *sha, double total) {
  char seed_json[32];
  if (seed_has) snprintf(seed_json, sizeof seed_json, "%d", seed);
  else snprintf(seed_json, sizeof seed_json, "null");
  char esrc[PATH_MAX_LOCAL], eout[PATH_MAX_LOCAL], ename[512];
  json_escape(src, esrc, sizeof esrc);
  json_escape(out, eout, sizeof eout);
  json_escape(pl->name, ename, sizeof ename);
  printf("{\"ok\":true,\"language\":\"NorthCel\",\"northcel_version\":\"%s\",\"spec_version\":\"%s\","
         "\"input\":\"%s\",\"output\":\"%s\",\"kind\":\"%s\",\"name\":\"%s\","
         "\"frame\":{\"index\":%d,\"count\":%ld},\"size\":{\"width\":%ld,\"height\":%ld},\"fps\":%ld,"
         "\"precision\":\"%s\",\"seed\":%s,\"source\":{\"bytes\":%ld,\"tokens\":null},"
         "\"geometry\":{\"layers\":%ld,\"rings\":%ld,\"vertices\":%ld},"
         "\"swarm\":{\"tasks\":%ld,\"agents\":%ld,\"points\":%ld,\"stage\":\"Bend/HVM2\"},"
         "\"stage\":\"MoonBit+Bend+GLSL\",\"sha256\":\"%s\","
         "\"timings\":{\"bend_s\":%.4f,\"ir_s\":%.4f,\"gl_s\":%.4f,\"total_s\":%.4f},"
         "\"determinism\":{\"pure_frame_function\":true},\"errors\":[]}\n",
         NCEL_VERSION, pl->spec, esrc, eout,
         pl->kind, ename,
         frame, pl->declared_frames, pl->width, pl->height, pl->fps, pl->precision,
         seed_json,
         pl->source_bytes, pl->layer_count, pl->rings, pl->vertices,
         pl->tasks, pl->bend_agents, pl->bend_points, sha,
         pl->t_bend, pl->t_ir, pl->t_gl, total);
}

static int cmd_render(const char *exe_dir, int argc, char **argv) {
  const char *file = NULL, *out = NULL;
  int frame = 0, seed_has = 0, seed = 0, json = 0;
  for (int i = 2; i < argc; i++) {
    if (!strcmp(argv[i], "--frame") && i + 1 < argc) frame = atoi(argv[++i]);
    else if (!strcmp(argv[i], "--seed") && i + 1 < argc) { seed = atoi(argv[++i]); seed_has = 1; }
    else if (!strcmp(argv[i], "-o") || !strcmp(argv[i], "--out")) { if (i + 1 < argc) out = argv[++i]; }
    else if (!strcmp(argv[i], "--json")) json = 1;
    else file = argv[i];
  }
  if (!file) { fprintf(stderr, "usage: ncel-native render FILE [-o OUT.png] [--frame N] [--seed N] [--json]\n"); return 2; }
  if (!file_exists(file)) { fprintf(stderr, "ncel-native: no such file: %s\n", file); return 1; }
  char outbuf[PATH_MAX_LOCAL];
  if (!out) {
    snprintf(outbuf, sizeof outbuf, "%s", file);
    char *dot = strrchr(outbuf, '.');
    if (dot && !strcmp(dot, ".ncel")) *dot = 0;
    strncat(outbuf, ".png", sizeof outbuf - strlen(outbuf) - 1);
    out = outbuf;
  }
  char *ast = find_tool("ncel-ast", "NCEL_AST", exe_dir);
  char *gl = find_tool("ncel-gl", "NCEL_GL", exe_dir);
  char *bend = find_tool("bend", "NCEL_BEND", exe_dir);
  if (!ast || !gl || !bend) {
    fprintf(stderr, "ncel-native: missing stage (%s%s%s)\n", ast ? "" : " ncel-ast", gl ? "" : " ncel-gl", bend ? "" : " bend");
    return 1;
  }
  char *shader = resolve_shader(exe_dir, "draw430.glsl");
  char tmpdir_t[64];
  snprintf(tmpdir_t, sizeof tmpdir_t, "/tmp/ncel-native-%d-XXXXXX", (int)getpid());
  if (!mkdtemp(tmpdir_t)) { perror("mkdtemp"); return 1; }
  Tools tl = {ast, bend, gl, shader};
  Pipeline pl;
  char err[8192] = "";
  double t0 = now_s();
  int rc = pipeline_render(file, frame, seed_has, seed, tmpdir_t, &tl, out, &pl, err, sizeof err);
  double total = now_s() - t0;
  if (rc != 0) {
    fprintf(stderr, "ncel-native: %s\n", err);
    unlink(pl.bend_path); unlink(pl.bend_out); unlink(pl.ir_path);
    rmdir(tmpdir_t);
    return 1;
  }
  char sha[65] = "";
  sha256_file(out, sha);
  if (json) print_receipt(file, out, frame, seed_has, seed, &pl, sha, total);
  else printf("Rendered %s (%ldx%ld, frame %d) in %.3fs [MoonBit+Bend+GLSL]\n", out, pl.width, pl.height, frame, total);
  unlink(pl.bend_path); unlink(pl.bend_out); unlink(pl.ir_path);
  char extra[PATH_MAX_LOCAL];
  snprintf(extra, sizeof extra, "%s/bend.json", tmpdir_t); unlink(extra);
  snprintf(extra, sizeof extra, "%s/ir.json", tmpdir_t); unlink(extra);
  rmdir(tmpdir_t);
  free(ast); free(gl); free(bend); free(shader);
  return 0;
}

/* -------------------------------------------------------------------- film */

static int parse_frames(const char *spec, long total, long **out, int *count) {
  long *list = NULL;
  int n = 0, cap = 0;
  if (!spec) {
    n = (int)total;
    list = (long *)malloc(sizeof(long) * (n ? n : 1));
    for (long i = 0; i < total; i++) list[i] = i;
    *out = list;
    *count = n;
    return 0;
  }
  if (strstr(spec, "..")) {
    long a = 0, b = 0;
    if (sscanf(spec, "%ld..%ld", &a, &b) != 2 || b < a) return 1;
    n = (int)(b - a + 1);
    list = (long *)malloc(sizeof(long) * n);
    for (long i = 0; i < n; i++) list[i] = a + i;
  } else {
    char *copy = xstrdup(spec);
    char *save = NULL;
    for (char *tok = strtok_r(copy, ",", &save); tok; tok = strtok_r(NULL, ",", &save)) {
      if (n == cap) { cap = cap ? cap * 2 : 8; list = (long *)realloc(list, sizeof(long) * cap); }
      list[n++] = atol(tok);
    }
    free(copy);
  }
  *out = list;
  *count = n;
  return 0;
}

static int cmd_film(const char *exe_dir, int argc, char **argv) {
  const char *file = NULL, *outdir = NULL, *mp4 = NULL, *framespec = NULL;
  int json = 0, seed_has = 0, seed = 0;
  for (int i = 2; i < argc; i++) {
    if (!strcmp(argv[i], "-o") || !strcmp(argv[i], "--out-dir")) { if (i + 1 < argc) outdir = argv[++i]; }
    else if (!strcmp(argv[i], "--mp4")) { if (i + 1 < argc) mp4 = argv[++i]; }
    else if (!strcmp(argv[i], "--frames")) { if (i + 1 < argc) framespec = argv[++i]; }
    else if (!strcmp(argv[i], "--seed")) { if (i + 1 < argc) { seed = atoi(argv[++i]); seed_has = 1; } }
    else if (!strcmp(argv[i], "--json")) json = 1;
    else file = argv[i];
  }
  if (!file || !outdir) { fprintf(stderr, "usage: ncel-native film FILE -o OUTDIR [--frames 0..5] [--mp4 OUT] [--json]\n"); return 2; }
  if (!file_exists(file)) { fprintf(stderr, "ncel-native: no such file: %s\n", file); return 1; }
  char *ast = find_tool("ncel-ast", "NCEL_AST", exe_dir);
  char *gl = find_tool("ncel-gl", "NCEL_GL", exe_dir);
  char *bend = find_tool("bend", "NCEL_BEND", exe_dir);
  char *ffmpeg = find_tool("ffmpeg", "NCEL_FFMPEG", exe_dir);
  if (!ast || !gl || !bend) { fprintf(stderr, "ncel-native: missing stage\n"); return 1; }
  char *shader = resolve_shader(exe_dir, "draw430.glsl");
  /* Read document metadata through ncel-ast info. */
  char info_json[8192] = "";
  char *iargv[] = {ast, "info", (char *)file, "--json", NULL};
  if (run_capture(iargv, info_json, sizeof info_json)) { fprintf(stderr, "ncel-native: cannot read %s\n", file); return 1; }
  long total = 1, fps = 6;
  json_int(info_json, "frames", &total);
  json_int(info_json, "fps", &fps);
  long *frames = NULL;
  int count = 0;
  if (parse_frames(framespec, total, &frames, &count)) { fprintf(stderr, "ncel-native: bad --frames\n"); return 2; }
  mkdir(outdir, 0777);
  char tmpdir_t[64];
  snprintf(tmpdir_t, sizeof tmpdir_t, "/tmp/ncel-native-%d-XXXXXX", (int)getpid());
  if (!mkdtemp(tmpdir_t)) { perror("mkdtemp"); return 1; }
  Tools tl = {ast, bend, gl, shader};
  int failures = 0;
  double t_all = now_s();
  char **hashes = (char **)calloc((size_t)count, sizeof(char *));
  for (int i = 0; i < count; i++) {
    char out_png[PATH_MAX_LOCAL];
    snprintf(out_png, sizeof out_png, "%s/f%04ld.png", outdir, frames[i]);
    Pipeline pl;
    char err[8192] = "";
    if (pipeline_render(file, (int)frames[i], seed_has, seed, tmpdir_t, &tl, out_png, &pl, err, sizeof err)) {
      fprintf(stderr, "ncel-native: frame %ld: %s\n", frames[i], err);
      failures++;
      continue;
    }
    char sha[65];
    sha256_file(out_png, sha);
    hashes[i] = xstrdup(sha);
  }
  if (failures) {
    free(frames);
    return 1;
  }
  char mp4_out[PATH_MAX_LOCAL] = "";
  if (mp4 && ffmpeg) {
    char rate[32];
    snprintf(rate, sizeof rate, "%ld", fps);
    char pattern[PATH_MAX_LOCAL];
    snprintf(pattern, sizeof pattern, "%s/f%%04ld.png", outdir);
    char *fargv[] = {ffmpeg, "-y", "-framerate", rate, "-i", pattern, "-c:v", "libx264", "-pix_fmt", "yuv420p", (char *)mp4, NULL};
    if (run_proc(fargv, NULL, 0) == 0) snprintf(mp4_out, sizeof mp4_out, "%s", mp4);
  }
  double total_s = now_s() - t_all;
  if (json) {
    char efile[PATH_MAX_LOCAL], edir[PATH_MAX_LOCAL], emp4[PATH_MAX_LOCAL];
    json_escape(file, efile, sizeof efile);
    json_escape(outdir, edir, sizeof edir);
    json_escape(mp4_out, emp4, sizeof emp4);
    printf("{\"ok\":true,\"frames_rendered\":%d,\"fps\":%ld,\"frame_paths\":[", count, fps);
    for (int i = 0; i < count; i++) {
      printf("%s\"%s/f%04ld.png\"", i ? "," : "", edir, frames[i]);
    }
    printf("],\"hashes\":{");
    for (int i = 0; i < count; i++) {
      printf("%s\"%ld\":\"%s\"", i ? "," : "", frames[i], hashes[i] ? hashes[i] : "");
    }
    printf("},\"mp4_path\":\"%s\",\"seconds\":%.4f,\"stage\":\"MoonBit+Bend+GLSL\",\"input\":\"%s\"}\n", emp4, total_s, efile);
  } else {
    printf("Rendered %d frames to %s%s%.3fs\n", count, outdir, mp4_out[0] ? " (+ mp4)" : "", total_s);
  }
  for (int i = 0; i < count; i++) free(hashes[i]);
  free(hashes);
  free(frames);
  free(ast); free(gl); free(bend); free(ffmpeg); free(shader);
  return 0;
}

/* -------------------------------------------------------------------- main */

int main(int argc, char **argv) {
  char *exe_dir = exe_directory();
  /* Bend spawns `hvm` by name, so make sure the pinned pair is on PATH. */
  {
    char *b = find_tool("bend", "NCEL_BEND", exe_dir);
    if (b) {
      char *slash = strrchr(b, '/');
      if (slash) {
        *slash = 0;
        const char *old = getenv("PATH");
        size_t n = strlen(b) + (old ? strlen(old) : 0) + 2;
        char *np = (char *)malloc(n);
        snprintf(np, n, "%s:%s", b, old ? old : "");
        setenv("PATH", np, 1);
        free(np);
      }
      free(b);
    }
  }
  int rc = 2;
  if (argc < 2) {
    fprintf(stderr, "usage: ncel-native <doctor|check|info|render|film> ...\n");
  } else if (!strcmp(argv[1], "--version")) {
    printf("ncel-native %s (NorthCel %s)\n", NCEL_VERSION, NCEL_SPEC);
    rc = 0;
  } else if (!strcmp(argv[1], "doctor")) {
    rc = cmd_doctor(exe_dir);
  } else if (!strcmp(argv[1], "check")) {
    rc = cmd_check(exe_dir, argc, argv);
  } else if (!strcmp(argv[1], "info")) {
    rc = cmd_info(exe_dir, argc, argv);
  } else if (!strcmp(argv[1], "render")) {
    rc = cmd_render(exe_dir, argc, argv);
  } else if (!strcmp(argv[1], "film")) {
    rc = cmd_film(exe_dir, argc, argv);
  } else {
    fprintf(stderr, "ncel-native: unknown command %s\n", argv[1]);
  }
  free(exe_dir);
  return rc;
}
