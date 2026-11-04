# NorthCel Language Specification (`0.1.0-draft`)

- **Language Name:** NorthCel
- **File Extension:** `.ncel`
- **CLI Commands:** `northcel`, `ncel`
- **Spec Version:** `0.1.0-draft`
- **Status:** Draft Specification (Released with reference implementation `northcel` 0.1.0)
- **Date:** 2026-11-03

---

## 1. Conformance & Normative vs. Non-Normative Sections

*(Normative)* The key words **MUST**, **MUST NOT**, **REQUIRED**, **SHALL**, **SHOULD**, and **MAY** in this document are to be interpreted as described in RFC 2119.

- **Normative sections:** Sections 2, 4, 5, 6, 7, 8, and 9 define the normative lexical grammar, syntactic grammar, coordinate/ring-chain encodings, paint order, subpixel rasterization semantics, determinism guarantees, and conformance suite requirements.
- **Non-normative sections:** Section 3 (Design Rationale: Combining MoonBit, Bend, and GLSL) and Section 10 (Roadmap Proposals) are informative and explain the architectural origins and planned future extensions.

---

## 2. Purpose & Core Principles (Normative)

NorthCel (`.ncel`) is a domain-specific programming language designed for AI coding agents and human creators to author, inspect, and surgically edit 2D hand-drawn images and frame-by-frame animated videos in code.

1. **Pure Frame Function (`frame(n, seed) -> pixels`):** Every frame of a `.ncel` scene or film MUST be a pure, deterministic function of the document AST, the zero-based integer `frame_index`, and the integer `seed`. Sequential random number generators (`random()`), wall-clock time (`millis()`), and cross-frame mutable state are strictly forbidden. Any frame `f` MUST produce byte-identical pixels whether rendered alone, forward (`0..N-1`), or in reverse (`N-1..0`).
2. **Geometry Counted as Code, Zero Embedded Raster:** A `.ncel` file MUST NOT embed raster bitmaps, base64 images, per-pixel lookup tables, or reference image paths. Every visible mark is computed from explicit vector/contour geometry, strokes, ribbons, or parallel agent swarms. When benchmarking compactness, all geometry payloads inside the `.ncel` file MUST be counted as part of the source code and token budget.
3. **Surgical Local Editability:** Scene layers (`layer`/`wash`, `stroke`, `ribbon`) and detail swarms (`bend_swarm`) are named, isolated blocks. Modifying one named block (e.g., adjusting `water_droplets` or `beard_and_chest_bristles`) MUST NOT alter the coordinates or pixels of any unrelated block.

---

## 3. Design Rationale: The MoonBit + Bend + GLSL Triad (Non-Normative)

NorthCel was created after benchmarking five unconventional language combinations on the 2-frame 1024×1024 *Man in the Shower* reconstruction task (`f0001` and `f0002`). Our core experimental rule holds: **a different programming language is an execution paradigm, not a source of extra visual information.**

NorthCel deliberately combines the single strongest attribute of three layers we proved in that benchmark:

1. **From MoonBit — Typed, Compact, Declarative Scene Structure:**
   - *What it contributes:* Algebraic scene organization (`Scene`, `Film`, `Wash`, `Stroke`, `Ribbon`, `Swarm`, `Def`), compact relative contour string decoding, and strict `line:column` diagnostics that an LLM can read and repair in one turn.
   - *What it does not add:* MoonBit does not invent anatomy on its own; its role is keeping the scene tree strongly typed, human/AI-readable, and fast to validate/decode.
2. **From Bend (HVM2) — Deterministic Massively Parallel Agent Evaluation:**
   - *What it contributes:* Classical hand-drawn frames contain hundreds of self-similar micro-elements (96 water spray droplets, 64+ beard/chest bristles, wet hair strands, and vertex line boil). Modeling these as independent, stateless parallel agents (`bend_swarm`) indexed by `(seed, frame_index, agent_id)` guarantees that evaluation order never changes the picture and that frames/swarms can be evaluated in parallel across CPU/GPU threads.
   - *What it does not add:* An interaction-combinator tree does not make a bad contour look good; arbitrary tangent curl or spring physics hurt visual similarity when applied blindly.
3. **From GLSL — Per-Pixel Continuous Coverage & 4×4 Subpixel Supersampling:**
   - *What it contributes:* Evaluating even-odd winding parity on an `N×N` subpixel grid (`antialias_grid: 4`, i.e., `0.25px` resolution) with 8-row spatial band acceleration and box integration gives crisp, antialiased ink edges, clean aperture cutouts (water droplets on tile/skin/hair), and deterministic paper grain.
   - *Execution independence:* While NorthCel can compile to native MoonBit + Bend + OpenGL/EGL GLSL where those toolchains are installed, the **normative reference implementation (`packages/northcel`) is a pure-Python + NumPy renderer** that reproduces the GLSL reference renders within `0.0115` greyscale MAE (`0.99999+` SSIM) with zero external compiler dependencies.

---

## 4. Lexical & Syntactic Grammar — EBNF (Normative)

Files are UTF-8 encoded text with extension `.ncel`. Line comments start with `//` and run to `\n`.

```ebnf
Document       = [ VersionHeader ] ( SceneDecl | FilmDecl ) ;
VersionHeader  = "northcel" ( StringLit | NumberLit ) [ ";" ] ;

SceneDecl      = "scene" Ident [ AttrList ] "{" SceneBody "}" ;
FilmDecl       = "film"  Ident [ AttrList ] "{" FilmBody  "}" ;

SceneBody      = [ PaperDecl ] { DefDecl | SceneStmt } ;
FilmBody       = [ PaperDecl ] { DefDecl | SceneStmt | FrameDecl } ;
FrameDecl      = "frame" IntLit "{" [ PaperDecl ] { DefDecl | SceneStmt } "}" ;

PaperDecl      = "paper" ( AttrBrace | AttrList ) ;
DefDecl        = "def" Ident [ AttrList ] "{" { PrimStmt } "}" ;

SceneStmt      = PrimStmt | UseStmt ;
PrimStmt       = LayerStmt | SwarmStmt | StrokeStmt | RibbonStmt ;
UseStmt        = "use" Ident [ AttrList ] [ ";" ] ;

LayerStmt      = ( "layer" | "wash" ) Ident AttrList "{" StringLit "}" ;
SwarmStmt      = ( "bend_swarm" | "swarm" ) Ident AttrList "{" StringLit "}" ;
StrokeStmt     = "stroke" Ident AttrList "{" Point2List "}" ;
RibbonStmt     = "ribbon" Ident [ AttrList ] "{" Point3List "}" ;

Point2List     = Point2 { [ "," ] Point2 } [ "," ] ;
Point2         = "(" Expr "," Expr ")" ;

Point3List     = Point3 { [ "," ] Point3 } [ "," ] ;
Point3         = "(" Expr "," Expr "," Expr ")" ;

AttrList       = "(" [ AttrItem { "," AttrItem } [ "," ] ] ")" ;
AttrBrace      = "{" [ AttrItem { "," AttrItem } [ "," ] ] "}" ;
AttrItem       = Ident ( ":" | "=" ) AttrValue ;
AttrValue      = HexColor | RgbColor | StringLit | UnitNum | TupleExpr | Expr ;

RgbColor       = "rgb" "(" Expr "," Expr "," Expr ")" ;
TupleExpr      = "(" Expr { "," Expr } ")" ;

Expr           = Term { ( "+" | "-" ) Term } ;
Term           = Factor { ( "*" | "/" ) Factor } ;
Factor         = [ "-" ] ( NumberLit | UnitNum | FuncCall | Ident | "(" Expr ")" ) ;
FuncCall       = ( "lerp" | "sin" | "cos" | "step" ) "(" [ Expr { "," Expr } ] ")" ;

Ident          = ( "A".."Z" | "a".."z" | "_" ) { "A".."Z" | "a".."z" | "0".."9" | "_" } ;
IntLit         = [ "-" ] Digit { Digit } ;
NumberLit      = [ "-" ] Digit { Digit } [ "." Digit { Digit } ] ;
UnitNum        = NumberLit ( "px" | "deg" ) ;
HexColor       = "#" HexDigit HexDigit HexDigit [ HexDigit HexDigit HexDigit ] ;
StringLit      = '"' { Character } '"' ;
```

---

## 5. Types, Coordinates & Ring-Chain Encodings (Normative)

### 5.1 Canvas & Coordinate System
- Canvas origin `(0, 0)` is the **top-left corner**; `+x` points right (`0 .. width`), `+y` points down (`0 .. height`).
- Valid `width` and `height` range: `1 .. 8192` pixels. Valid `fps` range: `1 .. 240`.
- Built-in pure variables in expressions:
  - `f`: current zero-based frame index (`0.0, 1.0, ...`).
  - `t`: normalized timeline progress in `[0.0, 1.0]`, defined as `f / max(1, frames - 1)` for `film` and `0.0` for static `scene`.
  - `seed`: integer scene/film seed.

### 5.2 Color Model (`tone` and `color`)
- Greyscale shorthand: `tone: N` where `N ∈ [0..255]` expands to RGB `(N, N, N)`.
- Full RGB color: `color: #RRGGBB`, `color: #RGB`, or `color: rgb(r, g, b)` with `r, g, b ∈ [0..255]`.

### 5.3 Quarter-Pixel (`0.25px`) Relative Ring-Chain Encoding (`precision: 0.25px`)
- Default precision mode. Coordinates are quantized to quarter-pixel integers `(qx, qy) = (round(x * 4), round(y * 4))`.
- Multiple rings in a layer or swarm payload are separated by `|`.
- Each ring is space-separated `dx,dy` integer pairs starting from `(0, 0)`:
  - First token `qx0,qy0` sets the starting vertex `(x_0, y_0) = (qx0 / 4.0, qy0 / 4.0)`.
  - Each subsequent token `dx_i,dy_i` updates `(qx_i, qy_i) = (qx_{i-1} + dx_i, qy_{i-1} + dy_i)` and appends vertex `(qx_i / 4.0, qy_i / 4.0)`.
- Every ring MUST decode to at least 3 vertices and is implicitly closed from its last vertex back to its first vertex.

### 5.4 Compact 1-Pixel Base-63 Relative Ring-Chain Encoding (`precision: 1px`)
- Compact mode for tight token budgets. Uses the 63-character alphabet:
  `0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz_`
  where character index `idx ∈ [0..62]` encodes delta `d = idx - 31 ∈ [-31..+31]` pixels.
- Format per ring: `x0,y0:c1c2c3c4...` where `x0,y0` is the integer start coordinate and each pair of characters `(c_{2k}, c_{2k+1})` adds `(dx, dy)` in `[-31..+31]`.

---

## 6. Rendering Semantics (Normative)

1. **Supersampling Grid:** For `paper.antialias_grid = N` (`N ∈ {1, 2, 4, 8}`, default `4`), each pixel `(px, py)` is subdivided into `N×N` subpixel sample centers:
   $$x_{s} = px + \frac{sx + 0.5}{N}, \quad y_{s} = py + \frac{sy + 0.5}{N}, \quad sx, sy \in \{0, \dots, N-1\}$$
2. **Subpixel Initialization:** All subpixels initialize to `paper.color`.
3. **Deterministic Line Boil:** When a primitive specifies `boil: Apx` or `boil: (A, freq)`, each vertex `(x, y)` at `(item_idx, ring_idx, vert_idx)` is displaced by `(nx * A, ny * A)` derived from the stateless 32-bit hash `_hash_u32(seed, floor(f * freq), item_idx, ring_idx, vert_idx)`.
4. **Stroke & Ribbon Expansion:**
   - `stroke` expands its polyline `[(x_0, y_0), ..., (x_{m-1}, y_{m-1})]` with linearly interpolated width `w(u) = lerp(w_start, w_end, i / (m - 1))` along vertex normals into a single closed polygon ring.
   - `ribbon` expands its polyline `[(x_i, y_i, w_i)]` using explicit per-vertex widths `w_i` along vertex normals into a single closed polygon ring.
5. **Even-Odd Winding Rule & Layer Paint Order:**
   - For each expanded layer in declaration order, a subpixel sample `(x_s, y_s)` is inside the layer if and only if a horizontal ray from `(-\infty, y_s)` to `(x_s, y_s)` crosses an **odd** number of ring edges satisfying `(y_a > y_s) != (y_b > y_s)` and `x_s < x_a + (y_s - y_a) * (x_b - x_a) / (y_b - y_a)`.
   - If inside, the subpixel is overwritten with the layer's color (opaque paint wash).
   - Because even-odd parity is evaluated across all rings in a layer, interior rings automatically cut clean apertures (e.g., bright water droplets inside a tile wall or eye highlights inside dark ink).
6. **Box Integration:** Each final pixel channel is the arithmetic mean of its `N×N` subpixels, plus optional deterministic paper grain `sin(hash(x, y, seed) * 0.0001) * 0.5 * grain * 255`, rounded via `clamp(floor(val + 0.5), 0, 255)`.
7. **Implementation Tolerance:** Any conforming renderer MUST match the reference implementation within a whole-frame Mean Absolute Error (MAE) of `<= 1.0` greyscale/RGB level (on `0..255`) on all conformance suite cases and within `<= 0.05` MAE on pure polygon scenes.

---

## 7. Error Model & Diagnostics (Normative)

All lexical, syntactic, and semantic errors MUST report 1-based `line:column` coordinates in the format:
`<file>:<line>:<column>: error: <message>` (or structured JSON when `--json` is passed).

---

## 8. Versioning & Compatibility Policy (Normative)

- Documents SHOULD start with `northcel "0.1.0-draft"`. Documents omitting the header default to `"0.1.0-draft"`.
- Patch/draft versions (`0.1.x`) MUST preserve backward compatibility for all valid `0.1.0-draft` files.

---

## 9. Conformance Suite (Normative)

The official conformance suite lives in `packages/northcel/northcel/conformance/` (`conformance_manifest.json` + `01_evenodd_aperture.ncel`, `02_color_stroke_ribbon.ncel`, `03_film_def_use_boil.ncel`). A third-party implementation conforms to NorthCel `0.1.0-draft` if it passes all syntax/validation checks, satisfies every pixel probe in `conformance_manifest.json`, and produces identical hashes across forward and reverse frame rendering orders.

---

## 10. Roadmap Proposals Beyond v0.1 (Non-Normative)

The following features are **not** part of `0.1.0-draft` and are scheduled for `0.2.0`:
- **Hierarchical Joint Rigs (`rig` / `joint`):** Forward/inverse 2D bone chains with angle inheritance.
- **Smooth SDF Boolean Blends (`smin`):** Polynomial smooth-minimum blending between overlapping washes.
- **Procedural Audio Cues (`cue`):** Embedded frame-accurate sound effect triggers for `northnoir mix`.
