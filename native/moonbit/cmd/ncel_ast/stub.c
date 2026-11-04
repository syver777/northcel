#include <stdio.h>
#include <stdint.h>
#include <stdlib.h>
#include "moonbit.h"
uint8_t* ncel_read_file(moonbit_bytes_t path) {
  FILE *f = fopen((const char*)path, "rb");
  if (!f) return moonbit_make_bytes(0, 0);
  fseek(f,0,SEEK_END); long n=ftell(f); fseek(f,0,SEEK_SET);
  uint8_t *b = moonbit_make_bytes((uint32_t)n, 0);
  if (n>0) fread(b,1,(size_t)n,f);
  fclose(f);
  return b;
}
int32_t ncel_write_file(moonbit_bytes_t path, moonbit_bytes_t data) {
  FILE *f = fopen((const char*)path, "wb");
  if (!f) return 1;
  fwrite(data, 1, (size_t)Moonbit_array_length(data), f);
  fclose(f);
  return 0;
}
