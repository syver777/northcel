# NorthCel Language Specification (`0.4.0-draft`)

- **Language:** NorthCel, file extension `.ncel`, commands `northcel` and `ncel`
- **Spec version:** `0.4.0-draft`
- **Tools release:** 0.5.0 (Python reference, launchers, JS pre-check)
- **Native runtime:** 0.4.0, which implements spec `0.3.0-draft` only (§10)
- **Date:** 2026-11-09

This is the complete specification. It restates every rule of
[0.1.0-draft](SPEC-0.1.0-draft.md), [0.2.0-draft](SPEC-0.2.0-draft.md) and
[0.3.0-draft](SPEC-0.3.0-draft.md) that is still normative and adds colour
expressions (`mix`), the `morph` primitive, inclusive frame ranges
(`frame A..B`) and opacity. The archived drafts are not edited. Valid 0.1, 0.2
and 0.3 documents render with the same pixels as before (§9).

## 1. Conformance language

The key words MUST, MUST NOT, SHOULD and MAY are used as in RFC 2119. Sections
2–10 are normative; §11 (authoring tools) and §12 (rationale) are not.

## 2. Principles

1. **A frame is a pure function.** Every frame is a deterministic function of
   the document, the zero-based integer frame index `f` and the integer seed.
   There is no random number generator state, clock or cross-frame state.
   Rendering frame `f` alone, in a forward pass or in a reverse pass MUST give
   identical pixels.
2. **Geometry is code.** A document MUST NOT embed raster images, base64 data,
   per-pixel lookup tables or paths to images. Every mark is computed from
   vector rings, strokes, ribbons, swarms or morphs written in the document.
3. **Named, local edits.** Primitives are named blocks. Changing one block MUST
   NOT change the geometry of an unrelated block (overlap can still change
   which pixels of it are visible).

## 3. Lexical structure

Files are UTF-8. `//` starts a comment that runs to the end of the line.
Whitespace separates tokens and is otherwise insignificant. Tokens:

```ebnf
String   = '"' { any character except an unescaped '"' } '"' ;
Hex      = "#" 3 to 6 hex digits ;                 (* #RGB or #RRGGBB *)
UnitNum  = Number ( "px-b63" | "px" | "deg" ) ;
Number   = [ "-" ] Digit { Digit } [ "." Digit { Digit } ] ;
Ident    = ( Letter | "_" ) { Letter | Digit | "_" } ;
Range    = ".." ;                                   (* new in 0.4 *)
Arrow    = "=>" ;                                   (* new in 0.4 *)
Punct    = "{" | "}" | "(" | ")" | "[" | "]" | ":" | "," | ";" | "+" | "-"
         | "*" | "/" | "=" | "$" ;
```

`12..18` lexes as `Number Range Number`. A number cannot start with a dot.

## 4. Grammar

```ebnf
Document      = [ VersionHeader ] ( SceneDecl | FilmDecl ) ;
VersionHeader = "northcel" ( String | Number ) [ ";" ] ;

SceneDecl     = "scene" Ident [ AttrList ] "{" { SceneBodyStmt } "}" ;
FilmDecl      = "film"  Ident [ AttrList ] "{" { FilmBodyStmt } "}" ;
SceneBodyStmt = PaletteDecl | PaperDecl | DefDecl | SceneStmt ;
FilmBodyStmt  = SceneBodyStmt | FrameDecl ;
FrameDecl     = "frame" IntLit [ ".." IntLit ] "{" { SceneBodyStmt } "}" ;

PaletteDecl   = "palette" ( AttrBrace | AttrList ) ;
PaperDecl     = "paper" ( AttrBrace | AttrList ) ;
DefDecl       = "def" Ident [ AttrList ] "{" { PrimStmt | TransformStmt } "}" ;

SceneStmt     = PrimStmt | UseStmt | DropStmt | TransformStmt ;
PrimStmt      = LayerStmt | SwarmStmt | StrokeStmt | RibbonStmt | MorphStmt ;
UseStmt       = "use" Ident [ AttrList ] [ ";" ] ;
DropStmt      = "drop" Ident [ ";" ] ;
TransformStmt = "transform" Ident AttrList [ ";" ] ;

LayerStmt     = ( "layer" | "wash" | "cel" ) Ident AttrList "{" String "}" ;
SwarmStmt     = ( "bend_swarm" | "swarm" ) Ident AttrList "{" String "}" ;
StrokeStmt    = "stroke" Ident AttrList "{" Point2List "}" ;
RibbonStmt    = "ribbon" Ident [ AttrList ] "{" Point3List "}" ;
MorphStmt     = "morph" Ident AttrList "{" String "=>" String "}" ;

Point2List    = Point2 { [ "," ] Point2 } [ "," ] ;
Point2        = "(" Expr "," Expr ")" ;
Point3List    = Point3 { [ "," ] Point3 } [ "," ] ;
Point3        = "(" Expr "," Expr "," Expr ")" ;

AttrList      = "(" [ AttrItem { [ "," ] AttrItem } [ "," ] ] ")" ;
AttrBrace     = "{" [ AttrItem { [ "," ] AttrItem } [ "," ] ] "}" ;
AttrItem      = Ident ( ":" | "=" ) AttrValue ;     (* "=" only inside AttrList *)
AttrValue     = Colour | String | UnitNum | TupleExpr | Expr ;
TupleExpr     = "(" AttrValue { "," AttrValue } ")" ;

Colour        = Hex | PaletteRef | RgbColour | MixColour ;
PaletteRef    = "$" Ident ;
RgbColour     = "rgb" "(" Expr "," Expr "," Expr ")" ;
MixColour     = "mix" "(" Colour "," Colour "," Expr ")" ;      (* new in 0.4 *)

Expr          = Term { ( "+" | "-" ) Term } ;
Term          = Factor { ( "*" | "/" ) Factor } ;
Factor        = [ "-" ] ( Number | UnitNum | FuncCall | Ident | "(" Expr ")" ) ;
FuncCall      = ( "lerp" | "sin" | "cos" | "step" | "ease" | "smoothstep" )
                "(" [ Expr { "," Expr } ] ")" ;
```

A bare palette name (`color: ink`) is accepted where a colour is expected and
the name is in the palette. `rgb(...)` components are evaluated once, at parse
time. `frame` blocks are only allowed in a `film`. A `def` body holds primitives
and transforms, not `use`, `drop` or `frame`.

## 5. Values and coordinates

### 5.1 Canvas and expressions

The origin is the top-left corner; `+x` is right, `+y` is down; units are
pixels. `width` and `height` are 1..8192, `fps` 1..240, film `frames` ≥ 1
(defaults: 1024, 1024, 6, 2; `precision: 0.25px`; `seed: 42`).

Expressions are evaluated with these variables: `f` (frame index as a number),
`t = f / max(1, frames - 1)` in a film and 0 in a scene, `seed`, and inside a
`def` its parameters (defaults from the `def`, overridden by the `use`
arguments, which are evaluated in the caller's scope). Functions:
`sin`, `cos` (radians), `lerp(a, b, u)` with `u` clamped to [0, 1],
`step(edge, x)` = 0 if `x < edge` else 1, `ease(u)` =
`u*u*u*(u*(u*6 - 15) + 10)` with `u` clamped, and `smoothstep(a, b, x)` with
`u = clamp((x - a)/(b - a), 0, 1)` returning `u*u*(3 - 2u)`; for `a == b` it
returns 0 if `x < a`, else 1. Division by a value with magnitude ≤ 1e-12
divides by 1. `ease` takes exactly one argument, `smoothstep` exactly three.

Header attributes (`width`, `height`, `fps`, `frames`, `seed`), stroke widths,
ribbon widths, boil and outline widths are evaluated once at parse time.
Coordinates in strokes/ribbons, `translate`/`dx`/`dy`, transform components,
`mix` factors, `morph` `u` and `opacity` are evaluated per frame.

### 5.2 Colours

- `tone: N` (0..255) is the grey `(N, N, N)`.
- `color:` (or `fill:`) takes `#RGB`, `#RRGGBB`, `rgb(r, g, b)`, `$name`, or
  `mix(...)`. Channels are 0..255.
- `palette { name: #RRGGBB, ... }` defines names; a reference must follow its
  definition. A frame block may define a local palette that inherits the film
  palette. A palette entry MUST be a static colour; `mix` in a palette is a
  syntax error.

**`mix(a, b, u)` (new in 0.4).** `a` and `b` are colours, including `$name`
and nested `mix`. `u` is an expression evaluated for the frame (with `def`
parameters in scope) and clamped to [0, 1]. Each channel is computed in sRGB
values, without linearisation:

```text
c = floor(a + (b - a) * u + 0.5)
```

so the result is again an 8-bit RGB colour. `mix` is accepted for `layer`,
`wash`, `cel`, `bend_swarm`, `stroke`, `ribbon` and `morph` colours, for the
colour of an `outline`, and for `paper`.

### 5.3 Ring encodings

A ring payload is a string of rings separated by `|`. Every ring MUST decode to
at least 3 vertices and is implicitly closed.

- **`precision: 0.25px`** — space-separated integer pairs in quarter pixels:
  the first pair is the start `(qx0, qy0)`, every next pair is a delta; vertex
  `i` is `(qx_i / 4, qy_i / 4)`.
- **`precision: 1px`** — `x0,y0:` followed by pairs of characters from
  `0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz_`; index
  `k` encodes the delta `k - 31` pixels.
- **`precision: 0.25px-b63`** — as `1px`, but start and deltas are in quarter
  pixels. Encoders split a longer segment into
  `K = ceil(max(|dqx|, |dqy|) / 31)` equal collinear steps.

### 5.4 Primitives

| Statement | Paints | Attributes |
| --- | --- | --- |
| `layer`, `wash` | the even-odd fill of its rings | colour, `rings` (count check, warning only), `boil`, `translate` or `dx`/`dy`, `outline`, `opacity` |
| `cel` | the fill, then `name__outline`: a closed stroke of width `W` along every ring | as `layer`; `outline: ($ink, Wpx)` (`ink`/`ink_width` also accepted; default ink is `$ink` or `#0D0D0D`) |
| `bend_swarm`, `swarm` | its rings as one layer | colour, `agents` ≥ 1, `boil`, `translate`, `opacity` |
| `stroke` | a polyline expanded to a closed ring | colour, `width` or `taper: (w0, w1)` (> 0), `boil`, `opacity` |
| `ribbon` | a polyline with per-point widths | colour, `boil`, `opacity` |
| `morph` (0.4) | an interpolation of two ring payloads (§6.4) | colour, `u` (required), `samples`, `outline`, `opacity` |

Strokes and ribbons need at least two points. Stroke width is
`lerp(w0, w1, i / (m - 1))` at point `i`; ribbon half-width is
`0.5 * max(0.25, w_i)`; the ring is the left offsets followed by the reversed
right offsets along vertex normals (end points use the end segment, interior
points the central difference).

## 6. Evaluation

### 6.1 The paint list of a frame

For a `scene`, the paint list is its statements. For a `film`, it is the film's
statements followed by the statements of **the one frame block that applies to
`f`** (§6.2); the frame block's paper (or the film paper), and its palette
scope, are used. `def`s of the film and of that frame block are visible.

Statements are processed in order:

- **Primitives** append a named entry to the paint list. A `layer`/`wash`/`cel`/
  `morph` whose name already exists **replaces that entry in place** (same
  paint position), including its `__outline`; swarms, strokes and ribbons always
  append. (Spec 0.1 compatibility: a swarm named `water_droplets` is merged into
  an existing `tile_wall`, and `beard_and_chest_bristles` into `ink_contours`.)
- **`use D(args)`** processes the `def` body with its parameter scope, then
  translates the entries it appended by `dx`, `dy`.
- **`drop name`** empties `name` and `name__outline` if present.
- **`transform name(...)`** / **`transform all(...)`** changes geometry already
  in the paint list (§6.3). A missing named target is an evaluation error with
  the transform's location.

Ring vertices are decoded, translated, then displaced by boil:
`(nx * A, ny * A)` from the 32-bit hash of
`(seed, floor(f * max(0.01, freq)), item, ring, vertex)` defined in the
reference implementation (`boil_offset`).

### 6.2 Frame blocks and ranges (0.4)

`frame N { ... }` applies to frame `N`. `frame A..B { ... }` applies to every
frame `A ≤ f ≤ B` (inclusive). Bounds are integers with `A ≤ B`; a reversed
range is a syntax error; a range outside `0..frames-1` is a validation error.
Exactly one block applies to a frame:

1. an exact `frame f` block, if there is one (a later exact block with the same
   index replaces an earlier one);
2. otherwise the **last** range in source order that contains `f`;
3. otherwise none (the film statements alone).

Blocks are not merged: a frame inside two ranges sees only the later one. The
validator warns about overlapping ranges, naming the frames where the later one
wins. Inside a range block, `f` and `t` are the actual frame's values; there is
no implicit local time (write e.g. `smoothstep(A - 1, B + 1, f)`).

### 6.3 Transforms

`transform` takes `scale` (scalar or `(sx, sy)`, default 1), `rotate`
(clockwise degrees, default 0), `anchor` and `translate` (pairs, default
`(0, 0)`); any other attribute is a syntax error. For each point:

```text
u = (x - ax) * sx; v = (y - ay) * sy; r = rotate * pi / 180
x' = ax + u*cos(r) - v*sin(r) + dx
y' = ay + u*sin(r) + v*cos(r) + dy
```

A named transform changes entries named `name` and `name__outline`; `all`
changes every entry painted so far, never the paper. Transforms compose in
source order and do not affect later statements.

### 6.4 `morph` (0.4)

```text
morph name(color: <colour>, u: <expr>[, samples: N][, outline: (<colour>, Wpx)][, opacity: <expr>])
  { "<rings A>" => "<rings B>" }
```

Both payloads use the document precision and MUST have the same number of rings
(≥ 1); ring `i` of A pairs with ring `i` of B. Vertex counts may differ.
`samples` is an integer 3..1024; when absent it is
`min(1024, max(8, nA, nB))` for each pair (`nA`, `nB` = decoded vertex counts).
With `u` evaluated and clamped to [0, 1]:

- `u ≤ 0` paints the decoded rings of A exactly; `u ≥ 1` those of B.
- Otherwise, for each pair:
  1. **Winding.** With the shoelace sum
     `S = ½ Σ (x_i y_{i+1} − x_{i+1} y_i)`, a ring with `S < 0` is reversed
     (vertex order `n-1 … 0`).
  2. **Resampling.** With cumulative edge lengths `c_0 = 0 … c_n = L` from
     vertex 0 around the closed ring, sample `k` (0 ≤ k < m) is the point at
     arclength `s_k = k · L / m`, on the edge `j` with `c_j ≤ s_k < c_{j+1}`,
     at `v_j + (v_{j+1} − v_j) (s_k − c_j) / |e_j|`. A ring with `L = 0`
     resamples to `m` copies of vertex 0.
  3. **Start alignment.** With `a` and `b` the two sample lists and `ā`, `b̄`
     their means, choose the shift `k` in 0..m−1 minimising
     `Σ_j |(a_j − ā) − (b_{(j+k) mod m} − b̄)|²`; ties take the smallest `k`.
  4. **Interpolation.** Point `j` is `a_j + (b_{(j+k) mod m} − a_j) · u`.

The result is one paint-list entry named `name` (replaceable, droppable and
transformable like a layer); an `outline` adds `name__outline` built from the
interpolated rings exactly as for a `cel`. Morphing is geometry only: it does
not guarantee that the in-betweens look right, and it does not choose which
ring corresponds to which.

### 6.5 Opacity (0.4)

`opacity: <expr>` on `layer`, `wash`, `cel` (fill and outline), `bend_swarm`,
`stroke`, `ribbon` and `morph` is evaluated per frame and clamped to [0, 1].
Absent means 1.

`use D(..., opacity: <expr>)` is **group opacity** for everything that `use`
paints. The value is also bound as the parameter `opacity` inside the `def`.

## 7. Rasterisation

1. **Subpixels.** With `N = paper.antialias_grid` (1, 2, 4 or 8; default 4),
   each pixel `(px, py)` has `N×N` sample centres
   `(px + (sx + 0.5)/N, py + (sy + 0.5)/N)`.
2. **Paper.** Every subpixel starts as the evaluated paper colour.
3. **Coverage.** For each paint-list entry in order, a sample is inside when a
   horizontal ray from `−∞` to it crosses an odd number of the entry's edges,
   counting edge `(a, b)` when `(y_a > y_s) != (y_b > y_s)` and
   `x_s < x_a + (y_s − y_a)(x_b − x_a)/(y_b − y_a)`. All rings of an entry share
   one parity, so inner rings cut holes.
4. **Painting.** An entry with opacity 1 overwrites the 8-bit RGB value of every
   covered subpixel with its colour. An entry with opacity `0 < α < 1` sets
   each channel of every covered subpixel to
   `floor(c + (s − c) · α + 0.5)` (`c` the current value, `s` the entry's
   colour), computed in IEEE double precision. An entry with opacity 0, or no
   rings, changes nothing.
5. **Groups.** For a `use` with group opacity `0 < g < 1`, the subpixel canvas
   is saved before the first entry of that `use` that paints; its entries are
   painted normally (rules 3–4, including nested groups); after the last one,
   every subpixel channel becomes `floor(c₀ + (c₁ − c₀) · g + 0.5)` with `c₀`
   the saved and `c₁` the painted value. Entries of a group with `g = 0` paint
   nothing; `g = 1` is an ordinary `use`. A group is one contiguous run of
   painting entries: if an entry from outside the group is painted between two
   of its entries (possible only through in-place replacement), the group is
   blended as two runs.
6. **Integration.** Each pixel channel is the mean of its `N×N` subpixels, plus,
   when `paper.grain > 0`, `sin(h · 0.0001) · 0.5 · grain · 255` with
   `h = (x·374761393 + y·668265263 + seed·1442695041) mod 2³²`, then
   `clamp(floor(v + 0.5), 0, 255)`.

A dissolve between two drawings is therefore
`use A` followed by `use B(opacity: u)`, where `B` begins with a full-canvas
layer in its paper colour: every subpixel moves from A's value towards B's.

## 8. Diagnostics

Every error and warning has a 1-based `line:column` and is printed as
`<file>:<line>:<column>: <error|warning>: <message>` (or as JSON strings with
`--json`). Evaluation errors (a missing transform target) carry the location of
the statement. `docs/errors.md` lists every message and is generated from the
source.

## 9. Versions and compatibility

- Recognised headers: `0.1`, `0.1.0`, `0.1.0-draft`, `0.2…`, `0.3…`, `0.4`,
  `0.4.0`, `0.4.0-draft`. A document without a header is `0.4.0-draft` in tools
  0.5.0 (it was `0.3.0-draft` in tools 0.4.0).
- `mix`, `morph` and frame ranges in a document whose header is older than 0.4
  are validation errors that name the required header.
- `opacity` was accepted and ignored before 0.4. In a document with an older
  header it is still ignored, with a warning; only 0.4 documents (or headerless
  ones) apply it, including group opacity on `use`.
- With these rules every valid 0.1–0.3 document renders exactly as before; the
  conformance probes, golden images and the documentation images are unchanged.
- The tools version and the spec version are independent. An archived draft is
  never edited.

## 10. Conformance and the native runtime

The conformance suite is `python/northcel/conformance/` (manifest plus fixtures
`01`–`05`). An implementation of spec 0.4 MUST pass every probe of every case
within the manifest tolerance (MAE ≤ 1.0 per probe; ≤ 0.05 on pure polygon
scenes) and render identical pixels in forward and reverse frame order. Case
`05_spec04_mix_morph_opacity` covers `mix` on paper, layer opacity, `morph` at
`u` = 0, ½ and 1, and range/exact-frame precedence.

**The native MoonBit + Bend/HVM2 + GLSL runtime 0.4.0 implements spec 0.3
only.** It is not changed by this draft. Case `05` is marked
`reference_only` and the conformance runner reports it as a SKIP for native,
never as a pass; `native/tests/fixtures/conformance` remains the spec 0.3
suite. The `northcel` launchers (Python and npm) therefore MUST NOT hand a
document that uses `mix`, `morph`, a frame range or `opacity`, or that declares
a 0.4 header, to the native runtime: the Python launcher renders it with the
Python reference and labels the result `"renderer": "python-reference"`; the
npm launcher uses Python when it can reach it and otherwise exits 3 naming the
features. A future native release that implements spec 0.4 must pass case `05`
in both directions before the routing is removed.

## 11. Authoring tools (non-normative)

These tools write ordinary documents; nothing they read is referenced by the
output.

- `northcel fit IMAGE -o FILE` traces a raster into a palette and a planar map
  (one layer per colour, holes by even-odd). `--stacked` instead writes
  painter's-order solid shapes, biggest first: every region becomes its outer
  contour; a hole whose source pixels are mostly paper (`--gap-fraction`,
  default 0.5) stays as a paper-coloured shape; a hole in the ink colour larger
  than `--underpaint-min-area` (default 300 px²) is filled with the most common
  other colour inside it. The stacked output uses only spec 0.3 constructs.
- `northcel tween A B -o FILE` pairs rings in source order (identical topology
  required, or an explicit `--fallback hold`).
- `northcel tween A B -o FILE --match` stacks both drawings, matches shapes by a
  colour-aware Hungarian assignment on centroid distance and area ratio (colour
  changes only along pairs the author allows), propagates motion to unmatched
  shapes inside matched ones, and writes one spec 0.4 film with `morph`, `mix`,
  `opacity` and frame ranges. Very large same-colour shapes switch at `u = ½`
  instead of morphing. When the matched area fraction is below `--min-match` or
  the weighted displacement above `--max-displacement`, the transition becomes a
  cut (or, with `--fallback dissolve`, a dissolve) and the receipt says why.
  The Python API is `northcel.correspond` (see the
  [polishing pattern](../patterns/12-polishing-ai-frames.md)).

A successful match means that contours can be interpolated without folding. It
says nothing about anatomy: a crouch becoming a jump needs a drawn in-between.

## 12. Rationale (non-normative)

The additions come from polishing a 15-second film whose frames were separate
AI-drawn images (6 fps, traced with `fit`) to 20 fps. Without them, every
in-between was a separate scene with baked `rgb()` colours (300 files, 15 MB),
`tween` could not be used because independent drawings never share topology,
a planar map leaked paper as soon as it moved, and cuts were the only fallback.
`mix`, `morph`, ranges and opacity let one film keep each key drawing once and
describe the in-betweens as expressions.
