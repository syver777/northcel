/* NorthCel native runtime - NCIR v1 reader (shared by ncel-gl and ncel-native).
 *
 * The IR is produced by the MoonBit stage (ncel-ast): one expanded frame with
 * per-layer RGBA colours, contiguous 8-row band spans, and f64 edges.
 */
#ifndef NCEL_IR_H
#define NCEL_IR_H

#include <stdint.h>
#include <stddef.h>

#ifdef __cplusplus
extern "C" {
#endif

typedef struct {
  char *name;
  float r, g, b;
  uint32_t band_count;
  uint32_t edge_count;
  uint32_t *spans; /* band_count * 2 */
  float *edges;    /* edge_count * 4 */
} NcelLayer;

typedef struct {
  int32_t index;
  uint32_t aa;
  double grain;
  float paper_r, paper_g, paper_b;
  uint32_t layer_count;
  NcelLayer *layers;
} NcelFrame;

typedef struct {
  char *msg;
  uint32_t line, col;
} NcelWarning;

typedef struct {
  uint32_t width, height, fps, declared_frames, flags, source_bytes;
  int64_t seed;
  char *spec_version;
  char *name;
  char *precision;
  uint32_t warning_count;
  NcelWarning *warnings;
  uint32_t frame_count;
  NcelFrame *frames;
} NcelIr;

/* Reads and validates an IR file. Returns 0 on success. */
int ncel_ir_read(const char *path, NcelIr *out, char *err, size_t errcap);
void ncel_ir_free(NcelIr *ir);
const NcelFrame *ncel_ir_frame(const NcelIr *ir, int32_t index);

#ifdef __cplusplus
}
#endif

#endif
