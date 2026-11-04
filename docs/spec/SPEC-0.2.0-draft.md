# NorthCel Language Specification (`0.2.0-draft`)

- **Language Name:** NorthCel
- **File Extension:** `.ncel`
- **CLI Commands:** `northcel`, `ncel`
- **Spec Version:** `0.2.0-draft` (Backward compatible with `0.1.0-draft`)
- **Status:** Draft Specification (Released with reference implementation `northcel` 0.2.0)
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
3. **Surgical Local Editability:** Scene layers (`layer`/`wash`/`cel`, `stroke`, `ribbon`) and detail swarms (`bend_swarm`) are named, isolated blocks. Modifying one named block MUST NOT alter the coordinates or pixels of any unrelated block.

---

## 3. Design Rationale: The MoonBit + Bend + GLSL Triad (Non-Normative)

NorthCel was created after benchmarking five unconventional language combinations on the 2-frame 1024×1024 *Man in the Shower* reconstruction task (`f0001` and `f0002`) and refined in Phase B on the 90-frame 1536×864 *Test Video 7* film. Our core experimental rule holds: **a different programming language is an execution paradigm, not a source of extra visual information.**

NorthCel deliberately combines the single strongest attribute of three layers we proved in that benchmark:

1. **From MoonBit — Typed, Compact, Declarative Scene Structure:**
   - *What it contributes:* Algebraic scene organization (`Scene`, `Film`, `Palette`, `Wash`/`Cel`, `Stroke`, `Ribbon`, `Swarm`, `Def`, `Drop`), compact relative contour string decoding (`0.25px`, `0.25px-b63`, and `1px` Base-63), and strict `line:column` diagnostics that an LLM can read and repair in one turn.
2. **From Bend (HVM2) — Deterministic Massively Parallel Agent Evaluation:**
   - *What it contributes:* Modeling repetitive organic micro-elements (`bend_swarm` droplets, bristles, grass tufts, and stateless vertex `boil`) as independent parallel agents indexed by `(seed, frame_index, agent_id)` guarantees order-independence and parallel frame evaluation.
3. **From GLSL — Per-Pixel Continuous Coverage & 4×4 Subpixel Supersampling:**
   - *What it contributes:* Evaluating even-odd winding parity on an `N×N` subpixel grid (`antialias_grid: 4`, i.e., `0.25px` resolution) with 8-row spatial band acceleration and box integration gives crisp antialiased ink edges, automatic aperture cutouts, and deterministic paper grain.
   - *Execution independence:* The **normative reference implementation (`packages/northcel`) is a pure-Python + NumPy renderer** that reproduces the GLSL reference renders within `0.0115` greyscale MAE (`0.99999+` SSIM) with zero external compiler dependencies.

---

## 4. Lexical & Syntactic Grammar — EBNF (Normative)

Files are UTF-8 encoded text with extension `.ncel`. Line comments start with `//` and run to `\n`.

```ebnf
Document       = [ VersionHeader ] ( SceneDecl | FilmDecl ) ;
VersionHeader  = "northcel" ( StringLit | NumberLit ) [ ";" ] ;

SceneDecl      = "scene" Ident [ AttrList ] "{" SceneBody "}" ;
FilmDecl       = "film"  Ident [ AttrList ] "{" FilmBody  "}" ;

SceneBody      = [ PaletteDecl ] [ PaperDecl ] { DefDecl | SceneStmt } ;
FilmBody       = [ PaletteDecl ] [ PaperDecl ] { DefDecl | SceneStmt | FrameDecl } ;
FrameDecl      = "frame" IntLit "{" [ PaletteDecl ] [ PaperDecl ] { DefDecl | SceneStmt } "}" ;

PaletteDecl    = "palette" ( AttrBrace | AttrList ) ;
PaperDecl      = "paper" ( AttrBrace | AttrList ) ;
DefDecl        = "def" Ident [ AttrList ] "{" { PrimStmt } "}" ;

SceneStmt      = PrimStmt | UseStmt | DropStmt ;
PrimStmt       = LayerStmt | SwarmStmt | StrokeStmt | RibbonStmt ;
UseStmt        = "use" Ident [ AttrList ] [ ";" ] ;
DropStmt       = "drop" Ident [ ";" ] ;

LayerStmt      = ( "layer" | "wash" | "cel" ) Ident AttrList "{" StringLit "}" ;
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
AttrValue      = HexColor | PaletteRef | RgbColor | StringLit | UnitNum | TupleExpr | Expr ;

PaletteRef     = "$" Ident ;
RgbColor       = "rgb" "(" Expr "," Expr "," Expr ")" ;
TupleExpr      = "(" AttrValue { "," AttrValue } ")" ;

Expr           = Term { ( "+" | "-" ) Term } ;
Term           = Factor { ( "*" | "/" ) Factor } ;
Factor         = [ "-" ] ( NumberLit | UnitNum | FuncCall | Ident | "(" Expr ")" ) ;
FuncCall       = ( "lerp" | "sin" | "cos" | "step" ) "(" [ Expr { "," Expr } ] ")" ;

Ident          = ( "A".."Z" | "a".."z" | "_" ) { "A".."Z" | "a".."z" | "0".."9" | "_" } ;
IntLit         = [ "-" ] Digit { Digit } ;
NumberLit      = [ "-" ] Digit { Digit } [ "." Digit { Digit } ] ;
UnitNum        = NumberLit ( "px-b63" | "px" | "deg" ) ;
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

### 5.2 Color Model (`tone`, `color`, and `palette`)
- Greyscale shorthand: `tone: N` where `N ∈ [0..255]` expands to RGB `(N, N, N)`.
- Full RGB color: `color: #RRGGBB`, `color: #RGB`, or `color: rgb(r, g, b)` with `r, g, b ∈ [0..255]`.
- Named Palette (`v0.2`): `palette { sky: #70CCF5, ink: #0D0D0D }` defines reusable named colors referenced via `color: $sky` or `outline: ($ink, 5px)`.

### 5.3 Quarter-Pixel (`0.25px`) Relative Ring-Chain Encoding (`precision: 0.25px`)
- Space-separated `dx,dy` integer pairs in quarter-pixel units (`round(x * 4), round(y * 4)`).

### 5.4 Compact 1-Pixel Base-63 Relative Ring-Chain Encoding (`precision: 1px`)
- Uses the 63-character alphabet `0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz_` where index `idx ∈ [0..62]` encodes delta `d = idx - 31 ∈ [-31..+31]` whole pixels (`x0,y0:c1c2...`).

### 5.5 Quarter-Pixel Base-63 Relative Ring-Chain Encoding (`precision: 0.25px-b63`, Added in v0.2)
- Combines full `0.25px` quarter-pixel accuracy with Base-63 2-character-per-step compactness (`qx0,qy0:c1c2...` where `qx0,qy0` are quarter-pixel integers and each character pair encodes `(dqx, dqy) ∈ [-31..+31]` quarter-pixels).
- Segments longer than `31` quarter-pixels are subdivided into `K = ceil(max(|dqx|, |dqy|) / 31)` equal collinear steps so diagonal lines never staircase.

### 5.6 Coupled `cel` Outlines and Film Frame Deltas (`drop`, Added in v0.2)
- **`cel` & `outline: ($ink, Wpx)`:** First paints the even-odd interior fill in `color`, and then automatically expands and paints a closed ink stroke of width `W` along every ring boundary in the layer.
- **In-Place Layer Replacement & `drop <name>` in `film`:** Inside a `film` `frame k { ... }` block, declaring a `layer` or `cel` with the same name as an inherited base layer replaces that layer at its original paint-order position. Declaring `drop <name>` removes the inherited layer (and any coupled `outline`) for frame `k`.

---

## 6. Rendering Semantics, Diagnostics, Versioning & Conformance (Normative)

 Sections 6–9 follow the exact `N×N` subpixel (`antialias_grid: 4`) even-odd winding rules, `line:column` diagnostic format, backward-compatible versioning policy (`0.1.0-draft` and `0.2.0-draft`), and conformance suite (`packages/northcel/northcel/conformance/`) established in `0.1.0-draft`.
