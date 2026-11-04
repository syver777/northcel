/* Minimal SHA-256 (public-domain style implementation, FIPS 180-4). */
#ifndef NCEL_SHA256_H
#define NCEL_SHA256_H
#include <stddef.h>
#include <stdint.h>

void ncel_sha256(const void *data, size_t len, uint8_t out[32]);
void ncel_sha256_hex(const void *data, size_t len, char out[65]);

#endif
