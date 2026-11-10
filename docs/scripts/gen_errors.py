"""Generate docs/errors.md from the real diagnostics of the real tool.

Every case below is written to a temporary `broken.ncel`, run through
`northcel check`, and the exact diagnostic it prints is embedded in the page.
`--check` regenerates the page and compares it with the committed file, so the
documentation cannot drift from the parser, the validator or the ring decoder.
"""

from __future__ import annotations

import argparse
import ast
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
PAGE = REPO / "docs" / "errors.md"
PYTHON_DIR = REPO / "python"

CASES = [
    dict(id="p-transform-attribute", title="An unknown transform attribute",
         cause="Only scale, rotate, anchor and translate are transform attributes.",
         fix="Use a supported attribute. Since spec 0.4, opacity is an attribute of primitives and of `use`, not of transforms.",
         source='northcel "0.3.0-draft"\nscene X { transform all(opacity: 1) }\n'),
    dict(id="p-transform-pair", title="A transform anchor with one component",
         cause="Anchors and translations are explicit two-component tuples.",
         fix="Write anchor: (x,y).",
         source='northcel "0.3.0-draft"\nscene X { transform all(anchor: 3) }\n'),
    dict(id="p-transform-number", title="A nonnumeric transform component",
         cause="Every transform component is a number or pure expression, not a colour.",
         fix="Use a numeric component.",
         source='northcel "0.3.0-draft"\nscene X { transform all(rotate: #FFF) }\n'),
    dict(id="p-easing-arity", title="An easing function with the wrong arity",
         cause="ease needs one argument; smoothstep needs three.",
         fix="Write ease(t) or smoothstep(0,1,t).",
         source='northcel "0.3.0-draft"\nscene X { transform all(scale: ease(1,2)) }\n'),
    # --- spec 0.4 -----------------------------------------------------------
    dict(id="p-frame-range-reversed", title="A frame range written backwards",
         cause="`frame A..B` covers A through B inclusive and needs A <= B.",
         fix="Swap the bounds: `frame 2..5`.",
         source='northcel "0.4.0-draft"\nfilm F(frames: 9) {\n  frame 5..2 { }\n}\n'),
    dict(id="p-mix-in-palette", title="A mix() inside a palette",
         cause="Palette entries are static colours; `mix` is evaluated per frame.",
         fix="Keep both colours in the palette and write `color: mix($a, $b, u)` on the primitive or paper.",
         source='northcel "0.4.0-draft"\nscene S {\n  palette { dusk: mix(#203040, #F0A060, 0.5) }\n}\n'),
    dict(id="p-mix-arguments", title="A mix() whose first argument is not a colour",
         cause="`mix(a, b, u)` takes two colours (hex, rgb(), $name or mix) and a number.",
         fix="Write `mix(#000000, #FFFFFF, t)`; for a grey use its hex value.",
         source='northcel "0.4.0-draft"\nscene S {\n  layer a(color: mix(0, #FFFFFF, 0.5)) { "0,0 4,0 0,4" }\n}\n'),
    dict(id="p-morph-u", title="A morph without u",
         cause="A morph needs the interpolation factor; there is no implicit time.",
         fix="Add `u: <expression>`, for example `u: smoothstep(11, 18, f)`.",
         source='northcel "0.4.0-draft"\nscene S {\n  morph m(tone: 0) { "0,0 4,0 0,4" => "0,0 8,0 0,8" }\n}\n'),
    dict(id="v-morph-rings", title="A morph whose sides have different ring counts",
         cause="Ring i of the first payload pairs with ring i of the second. The vertex counts may differ, the ring counts may not.",
         fix="Split the morph into one morph per ring pair, or give both sides the same number of rings.",
         source='northcel "0.4.0-draft"\nscene S {\n  morph m(tone: 0, u: 0.5) { "0,0 4,0 0,4|8,8 4,0 0,4" => "0,0 8,0 0,8" }\n}\n'),
    dict(id="v-spec04-header", title="A spec 0.4 construct in a 0.3 document",
         cause="`mix`, `morph` and frame ranges are spec 0.4. A document that declares an older version must not use them; the native runtime (spec 0.3) cannot render them.",
         fix='Change the header to `northcel "0.4.0-draft"` (the file then renders with the Python reference).',
         source='northcel "0.3.0-draft"\nfilm F(frames: 6) {\n  frame 1..3 { layer a(tone: 0) { "0,0 4,0 0,4" } }\n}\n'),
    dict(id="v-opacity-old-header", title="opacity in a 0.3 document",
         cause="Before spec 0.4 an `opacity` attribute was accepted and ignored. A document with an older header keeps that meaning.",
         fix='Change the header to `northcel "0.4.0-draft"` to apply it, or delete the attribute.',
         warning_only=True,
         source='northcel "0.3.0-draft"\nscene S {\n  layer a(tone: 0, opacity: 0.5) { "0,0 4,0 0,4" }\n}\n'),
    dict(id="v-frame-range-overlap", title="Overlapping frame ranges",
         cause="Exactly one frame block applies to a frame: an exact `frame N`, else the last range that contains it. Blocks are not merged.",
         fix="Make the ranges disjoint, or keep the overlap on purpose: the warning names the frames where the later block wins.",
         warning_only=True,
         source='northcel "0.4.0-draft"\nfilm F(frames: 10) {\n  frame 0..5 { layer a(tone: 0) { "0,0 4,0 0,4" } }\n  frame 4..9 { layer a(tone: 90) { "0,0 4,0 0,4" } }\n}\n'),
    # --- spec 0.5 (tools 0.6.0 source/unreleased) -----------------------------
    dict(id="p-nudge-vertex-integer", title="A fractional nudge vertex index",
         cause="Nudge vertex and ring indices are integers; fractions are not silently truncated.",
         fix="Use a zero-based integer vertex index (tools 0.6.0 from source, unreleased).",
         source='northcel "0.5.0-draft"\nscene S {\n  nudge a(vertex: 1.9, dx: 2px)\n}\n'),
    dict(id="p-nudge-ring-integer", title="A fractional nudge ring index",
         cause="A ring index must be a whole integer, not a fractional ring selection.",
         fix="Use a zero-based integer ring index, normally `ring: 0`.",
         source='northcel "0.5.0-draft"\nscene S {\n  nudge a(vertex: 0, ring: 0.7, dx: 2px)\n}\n'),
    dict(id="v-nudge-negative", title="A negative nudge index",
         cause="Vertex and ring indices start at zero.",
         fix="Choose an existing nonnegative index; render to verify it is in range.",
         source='northcel "0.5.0-draft"\nscene S {\n  nudge a(vertex: -1)\n}\n'),
    dict(id="v-spec05-def-header", title="A spec 0.5 construct inside an older-header def",
         cause="The version contract includes def bodies and nested groups, even unused definitions.",
         fix='Use tools 0.6.0 from source (unreleased) and `northcel "0.5.0-draft"`, or remove the 0.5 construct on published tools 0.5.0.',
         source='northcel "0.4.0-draft"\nscene S {\n  def D {\n    group g {}\n  }\n}\n'),
    # --- parser -------------------------------------------------------------
    dict(
        id="p-unexpected-char",
        title="A number that starts with a dot",
        cause="NorthCel numbers must start with a digit. `.5px` is not a token; the tokenizer stops at the dot.",
        fix="Write `0.5px`.",
        source='''northcel "0.2.0-draft"

scene BoilBad(width: 360, height: 210) {
  stroke wobble(color: #202830, width: 4px, boil: .5px) {
    (40, 90), (120, 70), (200, 100), (280, 80)
  }
}
''',
    ),
    dict(
        id="p-expected-token",
        title="A missing comma in a header",
        cause="The header's attribute list must close with `)`. The `{` arrived while the parser was still inside the list.",
        fix="Close the attributes: `width: 320, height: 180)` then `{`.",
        source='''northcel "0.2.0-draft"

scene HeaderBad(width: 320, height: 180 {
  paper { color: #F6F1E7 }
}
''',
    ),
    dict(
        id="p-no-root",
        title="A statement with no root container",
        cause="A document must start with `scene` or `film`. A bare primitive has nowhere to paint.",
        fix="Wrap the statements in `scene Name(...) { ... }` or `film Name(...) { ... }`.",
        source='''northcel "0.2.0-draft"

layer sky(color: #BFD8E8, rings: 1) { "0,0 1920,0 0,1080 -1920,0" }
''',
    ),
    dict(
        id="p-trailing-token",
        title="Text after the closing brace",
        cause="One document, one root. A second statement after the root's closing `}` is a trailing token.",
        fix="Delete the extra text, or move it inside the root (and give it a valid statement).",
        source='''northcel "0.2.0-draft"

scene Trailing(width: 320, height: 180) {
  paper { color: #F6F1E7 }
}

extra
''',
    ),
    dict(
        id="p-scene-statement",
        title="A film attribute inside a scene body",
        cause="`frames` is a `film` header attribute. It is not a scene statement.",
        fix="Use `film Name(..., frames: N)` if you want a timeline; a scene has one frame.",
        source='''northcel "0.2.0-draft"

scene SceneFrames(width: 320, height: 180, fps: 12) {
  paper { color: #F6F1E7 }
  frames: 12
}
''',
    ),
    dict(
        id="p-film-statement",
        title="A film attribute inside the film body",
        cause="`frames` belongs in the `film` header, not among the body statements.",
        fix="Move it: `film Name(..., frames: 12) { ... }`.",
        source='''northcel "0.2.0-draft"

film FilmFrames(width: 320, height: 180, fps: 12) {
  frames: 12
  paper { color: #F6F1E7 }
}
''',
    ),
    dict(
        id="p-frame-statement",
        title="A header attribute inside a frame override",
        cause="A `frame k { ... }` block holds primitives, defs, palette and paper — not header attributes.",
        fix="Put `frames`/`fps`/`seed` only in the film header.",
        source='''northcel "0.2.0-draft"

film FrameStmt(width: 320, height: 180, fps: 12, frames: 2) {
  paper { color: #F6F1E7 }
  frame 0 {
    frames: 2
  }
}
''',
    ),
    dict(
        id="p-unclosed-scene",
        title="A missing closing brace",
        cause="The parser reached end of file inside the `scene` block. The position points at where the block started, not at the missing brace.",
        fix="Close the block with `}`.",
        source='''northcel "0.2.0-draft"

scene Unclosed(width: 320, height: 180) {
  paper { color: #F6F1E7 }
  layer sky(color: #BFD8E8, rings: 1) { "0,0 1920,0 0,1080 -1920,0" }
''',
    ),
    dict(
        id="p-unclosed-def",
        title="A missing brace in a def",
        cause="The parser reached end of file inside a `def` block.",
        fix="Close the `def` block. The error names the def and its opening position.",
        source='''northcel "0.2.0-draft"

scene DefUnclosed(width: 320, height: 180) {
  def Mark(dx: 0) {
    stroke line(color: #202830, width: 2) { (0, 0), (10, 10) }
''',
    ),
    dict(
        id="p-unclosed-film",
        title="A missing brace in a film",
        cause="The parser reached end of file inside the `film` block.",
        fix="Close the film with `}`.",
        source='''northcel "0.2.0-draft"

film FilmOpen(width: 320, height: 180, fps: 12, frames: 2) {
  paper { color: #F6F1E7 }
''',
    ),
    dict(
        id="p-unclosed-frame",
        title="A missing brace in a frame override",
        cause="The parser reached end of file inside a `frame k` block.",
        fix="Close the override; the error points at the `frame` keyword.",
        source='''northcel "0.2.0-draft"

film FrameOpen(width: 320, height: 180, fps: 12, frames: 2) {
  paper { color: #F6F1E7 }
  frame 0 {
    layer sky(color: #BFD8E8, rings: 1) { "0,0 1920,0 0,1080 -1920,0" }
''',
    ),
    dict(
        id="p-def-statement",
        title="A `use` inside a `def`",
        cause="A `def` body may contain only layer/wash/cel, swarm, stroke and ribbon primitives. Nesting `use` is not supported.",
        fix="Expand the other def at the call site instead, or copy the primitive into this def.",
        source='''northcel "0.2.0-draft"

scene DefUse(width: 320, height: 180) {
  def Inner(dx: 0) {
    stroke line(color: #202830, width: 2) { (0, 0), (10, 10) }
  }
  def Outer(dx: 0) {
    use Inner(dx: 4)
  }
  use Outer(dx: 10)
}
''',
    ),
    dict(
        id="p-attr-colon",
        title="A missing colon after an attribute name",
        cause="Every attribute is `name: value`. The parser found the name and then something that is not `:`.",
        fix="Write `color: #RRGGBB`.",
        source='''northcel "0.2.0-draft"

scene AttrBad(width: 320, height: 180) {
  layer sky(color #BFD8E8, rings: 1) { "0,0 1920,0 0,1080 -1920,0" }
}
''',
    ),
    dict(
        id="p-palette-undefined",
        title="A palette colour used before it exists",
        cause="`$name` is resolved while the body is parsed. A name declared later (or never) is undefined at the reference.",
        fix="Declare the colour earlier in the same body, or use a literal.",
        source='''northcel "0.2.0-draft"

scene PaletteBad(width: 320, height: 180) {
  palette { ink: #202830 }
  layer sky(color: $blue, rings: 1) { "0,0 1920,0 0,1080 -1920,0" }
}
''',
    ),
    dict(
        id="p-unknown-function",
        title="A function NorthCel does not have",
        cause="Only `lerp`, `sin`, `cos` and `step` are expression functions. `oklch(...)` parses as a call and is rejected by name.",
        fix="Use `rgb(r, g, b)` / `#RRGGBB`, or precompute the sRGB value and put it in the palette.",
        source='''northcel "0.2.0-draft"

scene FunBad(width: 320, height: 180) {
  paper { color: #F6F1E7 }
  layer sky(color: oklch(0.7, 0.08, 220), rings: 1) { "0,0 1920,0 0,1080 -1920,0" }
}
''',
    ),
    dict(
        id="p-expected-expression",
        title="An empty attribute value",
        cause="The parser expected an expression after `color:` and found `)`.",
        fix="Give the attribute a value.",
        source='''northcel "0.2.0-draft"

scene ExprBad(width: 320, height: 180) {
  layer sky(color: , rings: 1) { "0,0 1920,0 0,1080 -1920,0" }
}
''',
    ),
    dict(
        id="p-version-value",
        title="A version header with no version",
        cause="`northcel` must be followed by a quoted version string or a number, then the root declaration.",
        fix="Write `northcel \"0.2.0-draft\"` or drop the header line.",
        source='''northcel scene

scene Bad(width: 320, height: 180) {
  paper { color: #F6F1E7 }
}
''',
    ),
    dict(
        id="p-colour-value",
        title="A colour attribute that is not a colour",
        cause="A tuple is a valid attribute value (for `translate:` and `taper:`), but it is not a colour.",
        fix="Use `#RRGGBB`, `rgb(r, g, b)`, `tone: N` or `$palette`.",
        source='''northcel "0.2.0-draft"

scene Bad(width: 320, height: 180) {
  layer sky(color: (1, 2), rings: 1) { "0,0 1280,0 0,720 -1280,0" }
}
''',
    ),
    # --- validator ----------------------------------------------------------
    dict(
        id="v-version",
        title="An unsupported specification version",
        cause="The version claim must be one of `0.1`, `0.1.0`, `0.1.0-draft`, `0.2`, `0.2.0`, `0.2.0-draft`.",
        fix="Use `northcel \"0.2.0-draft\"` (or drop the header).",
        source='''northcel "9.9.0"

scene Bad(width: 320, height: 180) {
  layer sky(color: #88AACC, rings: 1) { "0,0 1920,0 0,1080 -1920,0" }
}
''',
    ),
    dict(
        id="v-canvas",
        title="A canvas larger than 8192",
        cause="Each side is limited to 8192 pixels so a typo cannot request an impossible allocation.",
        fix="Render tiles, or use a realistic size.",
        source='''northcel "0.2.0-draft"

scene TooWide(width: 9000, height: 360) {
  paper { color: #F6F1E7 }
}
''',
    ),
    dict(
        id="v-fps",
        title="An fps outside 1..240",
        cause="`fps` drives timing and the MP4; zero would divide by zero.",
        fix="Use a value in `1..240`.",
        source='''northcel "0.2.0-draft"

scene FpsBad(width: 320, height: 180, fps: 0) {
  paper { color: #F6F1E7 }
}
''',
    ),
    dict(
        id="v-precision",
        title="An unknown contour precision",
        cause="Only `0.25px`, `0.25px-b63` and `1px` are decoders.",
        fix="Pick one of those three.",
        source='''northcel "0.2.0-draft"

scene PrecBad(width: 320, height: 180, precision: 0.5px) {
  paper { color: #F6F1E7 }
}
''',
    ),
    dict(
        id="v-colour-channel",
        title="A colour channel outside 0..255",
        cause="Colours are 8-bit RGB. The validator checks `rgb()` channels and hex-derived values.",
        fix="Clamp the channel to `0..255`.",
        source='''northcel "0.2.0-draft"

scene ColourBad(width: 320, height: 180) {
  layer sky(color: rgb(300, 0, 0), rings: 1) { "0,0 1920,0 0,1080 -1920,0" }
}
''',
    ),
    dict(
        id="v-antialias",
        title="An unsupported antialias grid",
        cause="The rasteriser integrates a square grid; only 1, 2, 4 and 8 are supported.",
        fix="Use `4` (default) or `8` for finer edges.",
        source='''northcel "0.2.0-draft"

scene AaBad(width: 320, height: 180) {
  paper { color: #F6F1E7, antialias_grid: 3 }
}
''',
    ),
    dict(
        id="v-rings-warning",
        title="A ring count that disagrees with the payload",
        cause="`rings:` is documentation. When it disagrees, the validator warns and still renders.",
        fix="Update `rings:` to the number of `|`-separated rings (or delete it).",
        source='''northcel "0.2.0-draft"

scene RingsWarn(width: 320, height: 180) {
  layer sky(color: #BFD8E8, rings: 3) { "0,0 1920,0 0,1080 -1920,0" }
}
''',
        warning_only=True,
    ),
    dict(
        id="v-swarm-agents",
        title="A swarm with no agents",
        cause="`agents` is the declared number of agents and must be at least 1.",
        fix="Declare the number of rings you actually put in the payload.",
        source='''northcel "0.2.0-draft"

scene SwarmBad(width: 320, height: 180) {
  bend_swarm dots(agents: 0, color: #202830) { "0,0 10,10 10,-10" }
}
''',
    ),
    dict(
        id="v-swarm-empty",
        title="A swarm whose payload decodes to no rings",
        cause="A swarm must paint at least one agent; an empty payload paints nothing.",
        fix="Add at least one `|`-separated ring.",
        source='''northcel "0.2.0-draft"

scene SwarmEmpty(width: 320, height: 180) {
  bend_swarm dots(agents: 2, color: #202830) { "" }
}
''',
    ),
    dict(
        id="v-swarm-ring",
        title="A swarm with a malformed ring",
        cause="Swarm payloads go through the same ring decoder as layers. A two-vertex ring is not an area.",
        fix="Give the agent at least three vertices.",
        source='''northcel "0.2.0-draft"

scene SwarmRing(width: 320, height: 180) {
  bend_swarm dots(agents: 1, color: #202830) { "0,0 40,0" }
}
''',
    ),
    dict(
        id="v-stroke-points",
        title="A stroke with one point",
        cause="A stroke needs a direction; one point cannot be offset into a polygon.",
        fix="Give it two points (a dot is a tiny layer, or a two-point stroke).",
        source='''northcel "0.2.0-draft"

scene StrokeBad(width: 320, height: 180) {
  stroke dot(color: #202830, width: 4px) { (40, 40) }
}
''',
    ),
    dict(
        id="v-stroke-width",
        title="A stroke with zero width",
        cause="Widths must be positive; zero would produce an empty polygon.",
        fix="Use a positive width (the renderer clamps ribbon widths below 0.25 to 0.25, but validation rejects zero stroke widths first).",
        source='''northcel "0.2.0-draft"

scene WidthBad(width: 320, height: 180) {
  stroke line(color: #202830, width: 0) { (40, 40), (80, 40) }
}
''',
    ),
    dict(
        id="v-ribbon-points",
        title="A ribbon with one point",
        cause="A ribbon needs two `(x, y, width)` points to have a length.",
        fix="Add a second point.",
        source='''northcel "0.2.0-draft"

scene RibbonBad(width: 320, height: 180) {
  ribbon line(color: #202830) { (40, 40, 4) }
}
''',
    ),
    dict(
        id="v-undefined-def",
        title="A use of an undefined def",
        cause="`use` is resolved against the defs in the same body (and, inside a frame, the film's defs too).",
        fix="Declare `def Name(...) { ... }` before the use.",
        source='''northcel "0.2.0-draft"

scene UseBad(width: 320, height: 180) {
  use Wave(dx: 10, dy: 0)
}
''',
    ),
    dict(
        id="v-film-frames",
        title="A film with zero frames",
        cause="A timeline must have at least one frame.",
        fix="Set `frames` to a positive integer.",
        source='''northcel "0.2.0-draft"

film FramesBad(width: 320, height: 180, fps: 12, frames: 0) {
  paper { color: #F6F1E7 }
}
''',
    ),
    dict(
        id="v-frame-range",
        title="A frame override beyond the film",
        cause="Override indices are checked against the current `frames` header.",
        fix="Fix `frames`, or delete/move the override.",
        source='''northcel "0.2.0-draft"

film RangeBad(width: 320, height: 180, fps: 12, frames: 4) {
  paper { color: #F6F1E7 }
  layer sky(color: #BFD8E8, rings: 1) { "0,0 1920,0 0,1080 -1920,0" }
  frame 6 { drop sky }
}
''',
    ),
    # --- ring decoder -------------------------------------------------------
    dict(
        id="r-q25-pair",
        title="A plain payload token without a comma",
        cause="Every plain quarter-pixel token is `dx,dy`; a bare number cannot be split.",
        fix="Write both components, e.g. `0,0 40,0 0,40`.",
        source='''northcel "0.2.0-draft"

scene RingPair(width: 320, height: 180) {
  layer sky(color: #BFD8E8, rings: 1) { "0,0 40 0,40" }
}
''',
    ),
    dict(
        id="r-q25-noninteger",
        title="A decimal in a quarter-pixel payload",
        cause="The plain encoding stores integers in quarter pixels, not floating-point pixels.",
        fix="Multiply by four and write integers: `1.5px` becomes `6`.",
        source='''northcel "0.2.0-draft"

scene RingDecimal(width: 320, height: 180) {
  layer sky(color: #BFD8E8, rings: 1) { "0,0 1.5,0 0,40" }
}
''',
    ),
    dict(
        id="r-q25-vertices",
        title="A two-vertex ring",
        cause="A closed contour needs at least three vertices.",
        fix="Use a stroke for a line, or add a third vertex.",
        source='''northcel "0.2.0-draft"

scene RingTwo(width: 320, height: 180) {
  layer sky(color: #BFD8E8, rings: 1) { "0,0 40,0" }
}
''',
    ),
    dict(
        id="r-b63-header",
        title="A Base-63 header without a comma",
        cause="The start coordinates are `x0,y0` before the colon.",
        fix="Write `x0,y0:PAIRS`.",
        source='''northcel "0.2.0-draft"

scene B63Head(width: 320, height: 180, precision: 0.25px-b63) {
  layer sky(color: #BFD8E8, rings: 1) { "abc:lxlxlx" }
}
''',
    ),
    dict(
        id="r-b63-start",
        title="Non-integer Base-63 start coordinates",
        cause="The start coordinates are plain integers.",
        fix="Write integers: `720,360`.",
        source='''northcel "0.2.0-draft"

scene B63Start(width: 320, height: 180, precision: 0.25px-b63) {
  layer sky(color: #BFD8E8, rings: 1) { "a,b:lxlxlx" }
}
''',
    ),
    dict(
        id="r-b63-odd",
        title="An odd Base-63 delta tail",
        cause="Each delta is exactly two characters; an odd tail cannot be split.",
        fix="Remove or add one character.",
        source='''northcel "0.2.0-draft"

scene B63Odd(width: 320, height: 180, precision: 0.25px-b63) {
  layer sky(color: #BFD8E8, rings: 1) { "720,360:lxlxl" }
}
''',
    ),
    dict(
        id="r-b63-pair",
        title="A character outside the Base-63 alphabet",
        cause="Only `0-9A-Za-z_` are deltas. `!` is not.",
        fix="Use a valid character pair.",
        source='''northcel "0.2.0-draft"

scene B63Pair(width: 320, height: 180, precision: 0.25px-b63) {
  layer sky(color: #BFD8E8, rings: 1) { "720,360:lx!!lx" }
}
''',
    ),
    dict(
        id="r-b63-vertices",
        title="A Base-63 ring with fewer than three vertices",
        cause="The start plus one pair is two vertices.",
        fix="Add at least one more pair.",
        source='''northcel "0.2.0-draft"

scene B63Two(width: 320, height: 180, precision: 0.25px-b63) {
  layer sky(color: #BFD8E8, rings: 1) { "720,360:lx" }
}
''',
    ),
    dict(
        id="v-file-not-found",
        title="A file that does not exist",
        cause="The path passed to `check` was not a readable file.",
        fix="Pass the right path. This diagnostic is produced before parsing.",
        source=None,
    ),
]


def _cli(args: list[str], cwd: Path | None = None) -> subprocess.CompletedProcess:
    env = dict(os.environ)
    env["PYTHONPATH"] = str(PYTHON_DIR) + (
        os.pathsep + env["PYTHONPATH"] if env.get("PYTHONPATH") else ""
    )
    return subprocess.run(
        [sys.executable, "-m", "northcel", *args, "--no-native"],
        cwd=str(cwd or REPO),
        env=env,
        capture_output=True,
        text=True,
    )


def run_case(case: dict) -> dict:
    with tempfile.TemporaryDirectory() as td:
        path = Path(td) / "broken.ncel"
        if case["source"] is not None:
            path.write_text(case["source"])
            proc = _cli(["check", str(path), "--json"])
        else:
            # A stable relative path, so the documented output is reproducible.
            proc = _cli(["check", "missing.ncel", "--json"], cwd=Path(td))
        try:
            receipt = json.loads(proc.stdout)
        except json.JSONDecodeError:
            raise SystemExit(f"{case['id']}: no JSON from check:\n{proc.stderr}")
        if case.get("warning_only"):
            if not receipt.get("warnings"):
                raise SystemExit(f"{case['id']}: expected a warning, none emitted")
        elif receipt.get("ok"):
            raise SystemExit(f"{case['id']}: expected a diagnostic, file passed")
        return {
            "errors": receipt.get("errors", []),
            "warnings": receipt.get("warnings", []),
            "exit": proc.returncode,
        }


def _call_name(node: ast.Call) -> str:
    f = node.func
    if isinstance(f, ast.Name):
        return f.id
    if isinstance(f, ast.Attribute):
        return f.attr
    return ""


def _template(node: ast.AST) -> str:
    if isinstance(node, ast.JoinedStr):
        out = []
        for v in node.values:
            if isinstance(v, ast.Constant):
                out.append(str(v.value))
            else:
                out.append("{…}")
        return "".join(out)
    if isinstance(node, ast.Constant):
        return str(node.value)
    return ""


def inventory() -> list[dict]:
    """Every message template the parser/validator/ring decoder raise today."""
    found = []
    for rel in ("python/northcel/parser.py", "python/northcel/validator.py", "python/northcel/rings.py"):
        tree = ast.parse((REPO / rel).read_text(), filename=rel)
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call):
                continue
            name = _call_name(node)
            if name not in ("NorthCelSyntaxError", "ValidationDiagnostic", "RingEncodingError"):
                continue
            arg = None
            if name == "ValidationDiagnostic":
                if len(node.args) >= 2:
                    arg = node.args[1]
            elif node.args:
                arg = node.args[0]
            if arg is None:
                continue
            msg = _template(arg)
            if not msg:
                continue
            level = "error"
            if name == "ValidationDiagnostic" and node.args:
                level = _template(node.args[0]) or "error"
            found.append({"file": rel.split("/")[-1], "level": level, "template": msg})
    # The one shared expect() template is produced inside Tool.expect.
    tree = ast.parse((REPO / "python/northcel/parser.py").read_text())
    for node in ast.walk(tree):
        if isinstance(node, ast.Call) and _call_name(node) == "NorthCelSyntaxError":
            pass
    # Deduplicate, keeping file order.
    seen = set()
    out = []
    for row in found:
        key = (row["file"], row["template"])
        if key in seen:
            continue
        seen.add(key)
        out.append(row)
    return out


def build() -> str:
    results = []
    for case in CASES:
        res = run_case(case)
        results.append({**case, **res})

    lines: list[str] = []
    lines.append("# Common errors and diagnostics\n")
    lines.append(
        "This page is **generated** by `docs/scripts/gen_errors.py` from the real parser, "
        "validator and ring decoder, and every example below is run through the real "
        "`northcel check` before it is written here. CI regenerates the page and compares "
        "it with this file, so a message cannot drift from the code.\n"
    )
    lines.append("## How a diagnostic is shaped\n")
    lines.append(
        "**Version scope:** spec 0.5 diagnostics require tools 0.6.0 from this "
        "source checkout (unreleased). Published tools 0.5.0 supports spec 0.4; "
        "do not run the 0.5-header examples on that install.\n"
    )
    lines.append(
        "```text\npath.ncel:5:20: error: Unknown function 'oklch'\n"
        "            │  │   │      └─ what is wrong\n"
        "            │  │   └─ level (error or warning)\n"
        "            │  └─ column, 1-based\n"
        "            └─ line, 1-based\n```\n"
    )
    lines.append(
        "`northcel check` prints diagnostics to stderr and exits `1` when there is at "
        "least one error. `--json` returns the same strings in `errors` and `warnings`; "
        "the process exit code remains the reliable signal. `ok: true` means *this "
        "validator found no error*, not that the picture is right. A warning never "
        "blocks a render.\n"
    )
    lines.append(
        "The npm package without Python can only run a structural pre-check. It reports "
        "`partial: true`, `validator: \"js\"` and `--require-full` exits `2` when no full "
        "validator is available. See "
        "[the validation contract](reference.md#validation-contract).\n"
    )

    lines.append("## Message inventory (from the source)\n")
    lines.append(
        "These are the message templates raised by `parser.py`, `validator.py` and "
        "`rings.py`. `{…}` marks an interpolated value. Some encoder-side templates are "
        "listed for completeness but are not reachable from `check`; the column says so.\n"
    )
    lines.append("| File | Level | Template | Reachable from `check` |")
    lines.append("| --- | --- | --- | --- |")
    reachable = {
        "Unexpected character {…}": "yes",
        "Expected {…}, got {…}": "yes",
        "Expected 'scene' or 'film' declaration, got '{…}'": "yes",
        "Unexpected trailing token '{…}'": "yes",
        "Unknown scene statement '{…}'": "yes",
        "Unknown film statement '{…}'": "yes",
        "Unknown frame statement '{…}'": "yes",
        "Unclosed 'scene' block": "yes",
        "Unclosed 'film' block": "yes",
        "Unclosed 'def {…}' block": "yes",
        "Unclosed 'frame' block": "yes",
        "Unsupported statement '{…}' inside def block": "yes",
        "Expected ':' after attribute '{…}'": "yes",
        "Undefined palette color '${…}'": "yes",
        "Unknown function '{…}'": "yes",
        "Expected expression, got '{…}'": "yes",
    }
    for row in inventory():
        tmpl = row["template"].replace("\n", " ")
        reach = reachable.get(tmpl)
        if reach is None:
            if row["file"] == "rings.py":
                unreachable = (
                    "requires at least 3 vertices" in tmpl
                    or "collapses to" in tmpl
                    or "Empty quarter-pixel" in tmpl
                    or "must contain ':'" in tmpl
                )
                if unreachable:
                    reach = "no (encoder-only or unreachable through a document)"
                else:
                    reach = "yes (wrapped as `Layer … has invalid ring payload: …`)"
            else:
                reach = "yes"
        tmpl_md = tmpl.replace("|", "\\|")
        lines.append(f"| `{row['file']}` | {row['level']} | `{tmpl_md}` | {reach} |")
    lines.append("")

    lines.append("## Reproduced diagnostics\n")
    lines.append(
        "Each case is a complete `.ncel` file that was run through `check`; the output "
        "shown is exactly what the tool printed. The file is always called "
        "`broken.ncel`, so the path prefix is stable. Diagnostic inputs use `text` "
        "fences, not the `ncel` tag reserved for valid runnable programs.\n"
    )
    for i, res in enumerate(results, 1):
        lines.append(f"### {i}. {res['title']}\n")
        lines.append(f"*Case id:* `{res['id']}`\n")
        if res["source"] is not None:
            lines.append("<!-- case-source -->")
            lines.append("```text")
            lines.append(res["source"].rstrip())
            lines.append("```\n")
            lines.append("```console")
            lines.append("$ northcel check broken.ncel")
            for w in res["warnings"]:
                lines.append(f"broken.ncel:{w}")
            for e in res["errors"]:
                lines.append(f"broken.ncel:{e}")
            lines.append(f"# exit {res['exit']}")
            lines.append("```\n")
        else:
            lines.append("```console")
            lines.append("$ northcel check missing.ncel")
            for e in res["errors"]:
                lines.append(f"missing.ncel:{e}")
            lines.append(f"# exit {res['exit']}")
            lines.append("```\n")
        lines.append(f"**Cause.** {res['cause']}\n")
        lines.append(f"**Fix.** {res['fix']}\n")
    lines.append("## What is not a diagnostic\n")
    lines.append(
        "- A successful `check` with a warning still renders. Read the warning; it is "
        "usually a stale `rings:` count.\n"
        "- A clean JS pre-check is not full validation. `partial: true` and exit `2` "
        "mean only that no full validator ran.\n"
        "- A valid file can still look wrong. Rendering is the only proof of the "
        "picture; see the [guide](guide/README.md).\n"
        "- `check` does not evaluate the drawing at every frame. A time-dependent "
        "expression that divides by zero at one `f` is a render-time problem, not a "
        "check-time diagnostic.\n"
    )
    return "\n".join(lines).rstrip("\n") + "\n"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--check", action="store_true", help="regenerate and compare with the committed page")
    args = ap.parse_args()
    text = build()
    if args.check:
        current = PAGE.read_text() if PAGE.exists() else ""
        if current != text:
            print("docs/errors.md is stale: run docs/scripts/gen_errors.py", file=sys.stderr)
            return 1
        print(f"docs/errors.md is current ({len(CASES)} cases)")
        return 0
    PAGE.write_text(text)
    print(f"wrote {PAGE.relative_to(REPO)} ({len(CASES)} cases)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
