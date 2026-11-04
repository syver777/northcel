# NorthCel native runtime - Linux x86_64 build
#
# Produces:
#   build/bin/ncel-native   orchestration CLI (C)
#   build/bin/ncel-ast      typed AST / contour / frame stage (MoonBit native)
#   build/bin/ncel-gl       headless EGL + GLSL rasteriser (C)
#   build/share/ncel/*.glsl rasterisation shaders
#
# Pinned toolchain: run `scripts/provision-toolchain.sh` first (or set MOON_HOME
# to an existing MoonBit install). See BUILD.md and toolchain.lock.

SHELL := /bin/bash
ROOT := $(patsubst %/,%,$(dir $(abspath $(lastword $(MAKEFILE_LIST)))))
BUILD ?= $(ROOT)/build
MOON_HOME ?= $(ROOT)/.toolchain/moon
MOON ?= $(MOON_HOME)/bin/moon
CC ?= cc
CFLAGS ?= -O2 -std=c11 -Wall -Wextra
LDLIBS := -ldl -lm

MB_DIR := $(ROOT)/moonbit
AST_SRC := $(MB_DIR)/_build/native/release/build/cmd/ncel_ast/ncel_ast.exe

.PHONY: all clean ast gl cli shaders test package doctor

all: ast gl cli shaders

ast:
	@test -x "$(MOON)" || { echo "error: $(MOON) not found; run scripts/provision-toolchain.sh"; exit 1; }
	cd $(MB_DIR) && MOON_HOME="$(MOON_HOME)" $(MOON) build --target native --release cmd/ncel_ast
	@mkdir -p $(BUILD)/bin
	cp "$(AST_SRC)" $(BUILD)/bin/ncel-ast
	@chmod +x $(BUILD)/bin/ncel-ast

gl:
	@mkdir -p $(BUILD)/bin
	$(CC) $(CFLAGS) -o $(BUILD)/bin/ncel-gl \
	  $(ROOT)/src/gl/ncel_gl.c $(ROOT)/src/gl/ncel_ir.c $(LDLIBS)

cli:
	@mkdir -p $(BUILD)/bin
	$(CC) $(CFLAGS) -I $(ROOT)/src/cli -o $(BUILD)/bin/ncel-native \
	  $(ROOT)/src/cli/ncel_native.c $(ROOT)/src/cli/sha256.c

shaders:
	@mkdir -p $(BUILD)/share/ncel
	cp $(ROOT)/shaders/draw430.glsl $(ROOT)/shaders/draw410.glsl $(BUILD)/share/ncel/

doctor: all
	$(BUILD)/bin/ncel-native doctor

test: all
	bash $(ROOT)/tests/run-tests.sh

package: all
	bash $(ROOT)/scripts/package.sh

clean:
	rm -rf $(BUILD)
	rm -rf $(MB_DIR)/_build
