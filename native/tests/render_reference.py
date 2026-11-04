#!/usr/bin/env python3
"""Render a frame with the Python reference renderer (test oracle only)."""
import sys

from PIL import Image

sys.path.insert(0, sys.argv[1])
from northcel.parser import parse_ncel  # noqa: E402
from northcel.renderer import render_document_frame  # noqa: E402

src, out, frame = sys.argv[2], sys.argv[3], int(sys.argv[4]) if len(sys.argv) > 4 else 0
doc = parse_ncel(open(src).read())
Image.fromarray(render_document_frame(doc, frame), "RGB").save(out)
