/* NorthCel native runtime - NCIR v1 reader. */
#include "ncel_ir.h"

#include <stdio.h>
#include <stdlib.h>
#include <string.h>

typedef struct {
  const unsigned char *p;
  size_t n;
  size_t off;
  int bad;
} Reader;

static uint32_t rd_u32(Reader *r) {
  if (r->off + 4 > r->n) { r->bad = 1; return 0; }
  uint32_t v = (uint32_t)r->p[r->off] | ((uint32_t)r->p[r->off + 1] << 8) |
               ((uint32_t)r->p[r->off + 2] << 16) | ((uint32_t)r->p[r->off + 3] << 24);
  r->off += 4;
  return v;
}

static int32_t rd_i32(Reader *r) { return (int32_t)rd_u32(r); }

static uint64_t rd_u64(Reader *r) {
  uint64_t lo = rd_u32(r);
  uint64_t hi = rd_u32(r);
  return lo | (hi << 32);
}

static double rd_f64(Reader *r) {
  uint64_t bits = rd_u64(r);
  double d;
  memcpy(&d, &bits, 8);
  return d;
}

static char *rd_str(Reader *r) {
  uint32_t len = rd_u32(r);
  if (r->bad || r->off + len > r->n || len > (1u << 28)) { r->bad = 1; return NULL; }
  char *s = (char *)malloc((size_t)len + 1);
  if (!s) { r->bad = 1; return NULL; }
  memcpy(s, r->p + r->off, len);
  s[len] = 0;
  r->off += len;
  return s;
}

static int ensure(uint32_t count, size_t elem, char *err, size_t errcap) {
  if ((uint64_t)count * (uint64_t)elem > (uint64_t)1 << 32) {
    snprintf(err, errcap, "IR allocation too large (%u x %zu)", count, elem);
    return 0;
  }
  return 1;
}

int ncel_ir_read(const char *path, NcelIr *out, char *err, size_t errcap) {
  memset(out, 0, sizeof(*out));
  FILE *f = fopen(path, "rb");
  if (!f) { snprintf(err, errcap, "cannot open IR file: %s", path); return 1; }
  if (fseek(f, 0, SEEK_END) != 0) { fclose(f); snprintf(err, errcap, "cannot seek IR file"); return 1; }
  long sz = ftell(f);
  if (sz < 16) { fclose(f); snprintf(err, errcap, "IR file too small"); return 1; }
  if (fseek(f, 0, SEEK_SET) != 0) { fclose(f); snprintf(err, errcap, "cannot rewind IR file"); return 1; }
  unsigned char *buf = (unsigned char *)malloc((size_t)sz);
  if (!buf) { fclose(f); snprintf(err, errcap, "out of memory"); return 1; }
  if (fread(buf, 1, (size_t)sz, f) != (size_t)sz) {
    fclose(f); free(buf); snprintf(err, errcap, "short read on IR file"); return 1;
  }
  fclose(f);

  Reader r = { buf, (size_t)sz, 0, 0 };
  if (memcmp(r.p, "NCIR", 4) != 0) {
    free(buf); snprintf(err, errcap, "bad IR magic (expected NCIR)"); return 1;
  }
  r.off = 4;
  uint32_t version = rd_u32(&r);
  if (version != 1) {
    free(buf); snprintf(err, errcap, "unsupported IR version %u", version); return 1;
  }
  out->width = rd_u32(&r);
  out->height = rd_u32(&r);
  out->fps = rd_u32(&r);
  out->declared_frames = rd_u32(&r);
  out->flags = rd_u32(&r);
  out->source_bytes = rd_u32(&r);
  out->seed = (int64_t)rd_u64(&r);
  out->spec_version = rd_str(&r);
  out->name = rd_str(&r);
  out->precision = rd_str(&r);
  out->warning_count = rd_u32(&r);
  if (!r.bad && out->warning_count) {
    out->warnings = (NcelWarning *)calloc(out->warning_count, sizeof(NcelWarning));
    if (!out->warnings) r.bad = 1;
    for (uint32_t i = 0; i < out->warning_count && !r.bad; i++) {
      out->warnings[i].line = rd_u32(&r);
      out->warnings[i].col = rd_u32(&r);
      out->warnings[i].msg = rd_str(&r);
    }
  }
  out->frame_count = rd_u32(&r);
  if (r.bad || !ensure(out->frame_count, sizeof(NcelFrame), err, errcap)) {
    ncel_ir_free(out); free(buf); snprintf(err, errcap, "truncated IR header"); return 1;
  }
  out->frames = (NcelFrame *)calloc(out->frame_count ? out->frame_count : 1, sizeof(NcelFrame));
  if (!out->frames) { ncel_ir_free(out); free(buf); snprintf(err, errcap, "out of memory"); return 1; }

  for (uint32_t fi = 0; fi < out->frame_count && !r.bad; fi++) {
    NcelFrame *fr = &out->frames[fi];
    fr->index = rd_i32(&r);
    fr->aa = rd_u32(&r);
    fr->grain = rd_f64(&r);
    fr->paper_r = (float)rd_u32(&r);
    fr->paper_g = (float)rd_u32(&r);
    fr->paper_b = (float)rd_u32(&r);
    fr->layer_count = rd_u32(&r);
    if (!ensure(fr->layer_count, sizeof(NcelLayer), err, errcap)) { r.bad = 1; break; }
    fr->layers = (NcelLayer *)calloc(fr->layer_count ? fr->layer_count : 1, sizeof(NcelLayer));
    if (!fr->layers) { r.bad = 1; break; }
    for (uint32_t li = 0; li < fr->layer_count && !r.bad; li++) {
      NcelLayer *l = &fr->layers[li];
      l->name = rd_str(&r);
      l->r = (float)rd_u32(&r);
      l->g = (float)rd_u32(&r);
      l->b = (float)rd_u32(&r);
      l->band_count = rd_u32(&r);
      l->edge_count = rd_u32(&r);
      if (!ensure(l->band_count, sizeof(uint32_t) * 2, err, errcap) ||
          !ensure(l->edge_count, sizeof(float) * 4, err, errcap)) { r.bad = 1; break; }
      l->spans = (uint32_t *)calloc(l->band_count ? (size_t)l->band_count * 2 : 1, sizeof(uint32_t));
      l->edges = (float *)calloc(l->edge_count ? (size_t)l->edge_count * 4 : 1, sizeof(float));
      if (!l->spans || !l->edges) { r.bad = 1; break; }
      for (uint32_t b = 0; b < l->band_count * 2; b++) l->spans[b] = rd_u32(&r);
      for (uint32_t e = 0; e < l->edge_count * 4; e++) l->edges[e] = (float)rd_f64(&r);
      if (r.off > r.n) { r.bad = 1; }
    }
  }
  if (r.bad || r.off != r.n) {
    ncel_ir_free(out);
    free(buf);
    snprintf(err, errcap, "truncated or overlong IR payload (offset %zu of %zu)", r.off, r.n);
    return 1;
  }
  free(buf);
  return 0;
}

void ncel_ir_free(NcelIr *ir) {
  if (!ir) return;
  for (uint32_t fi = 0; ir->frames && fi < ir->frame_count; fi++) {
    NcelFrame *fr = &ir->frames[fi];
    for (uint32_t li = 0; li < fr->layer_count; li++) {
      free(fr->layers[li].name);
      free(fr->layers[li].spans);
      free(fr->layers[li].edges);
    }
    free(fr->layers);
  }
  free(ir->frames);
  for (uint32_t i = 0; i < ir->warning_count; i++) free(ir->warnings[i].msg);
  free(ir->warnings);
  free(ir->spec_version);
  free(ir->name);
  free(ir->precision);
  memset(ir, 0, sizeof(*ir));
}

const NcelFrame *ncel_ir_frame(const NcelIr *ir, int32_t index) {
  for (uint32_t i = 0; i < ir->frame_count; i++) {
    if (ir->frames[i].index == index) return &ir->frames[i];
  }
  return ir->frame_count ? &ir->frames[0] : NULL;
}
