# NorthCel — developer entry points.
#
#   make test     everything that a clean clone can run (Python + JS + conformance)
#   make lint     ruff + node --check + generated-asset check
#   make dist     wheels, sdist and npm tarballs into dist/
#   make verify   install the built artifacts into throwaway dirs and render
#
# Linux x86_64 note: `make native` needs the MoonBit compiler and a C toolchain and
# downloads a 101 MB toolchain; nothing else here does.

PYTHON ?= python3
NPM ?= npm
PYDIR := python
JSDIR := js/northcel
DIST := dist

.PHONY: all test test-py test-js conformance lint lint-py lint-js assets check-licenses \
        dist dist-py dist-npm verify native clean help

all: test

help:
	@sed -n '2,12p' Makefile

test: test-py test-js conformance

test-py:
	$(PYTHON) -m pytest $(PYDIR)/tests -q

test-js:
	$(NPM) --prefix $(JSDIR) test

conformance:
	PYTHONPATH=$(PYDIR) $(PYTHON) tests/conformance.py

lint: lint-py lint-js assets check-licenses

lint-py:
	$(PYTHON) -m ruff check $(PYDIR) tests packaging/scripts
	$(PYTHON) -m ruff format --check $(PYDIR) tests packaging/scripts

lint-js:
	@for f in $(JSDIR)/bin/northcel.js $(JSDIR)/lib/locate.js $(JSDIR)/index.cjs; do \
		node --check $$f || exit 1; done

assets:
	$(PYTHON) $(JSDIR)/scripts/sync-assets.py --check

# Every copy of the licence texts must be byte-identical to the root ones.
check-licenses:
	@for d in python python/northcel-native js/northcel js/northcel-linux-x64; do \
		for f in LICENSE-MIT LICENSE-APACHE; do \
			cmp -s $$f $$d/$$f || { echo "$$d/$$f differs from $$f"; exit 1; }; \
		done; \
	done
	@echo "licence copies in sync"

dist: dist-py dist-npm

dist-py:
	bash packaging/scripts/build_python.sh $(DIST)/python

dist-npm:
	bash packaging/scripts/build_npm.sh $(DIST)/npm

verify:
	bash packaging/scripts/verify.sh

native:
	$(MAKE) -C native

clean:
	rm -rf $(DIST) .pytest_cache .ruff_cache
	find . -name '__pycache__' -type d -prune -exec rm -rf {} +
	rm -rf $(JSDIR)/node_modules
