# Common errors and diagnostics

This page is **generated** by `docs/scripts/gen_errors.py` from the real parser, validator and ring decoder, and every example below is run through the real `northcel check` before it is written here. CI regenerates the page and compares it with this file, so a message cannot drift from the code.

## How a diagnostic is shaped

```text
path.ncel:5:20: error: Unknown function 'oklch'
            │  │   │      └─ what is wrong
            │  │   └─ level (error or warning)
            │  └─ column, 1-based
            └─ line, 1-based
```

`northcel check` prints diagnostics to stderr and exits `1` when there is at least one error. `--json` returns the same strings in `errors` and `warnings`; the process exit code remains the reliable signal. `ok: true` means *this validator found no error*, not that the picture is right. A warning never blocks a render.

The npm package without Python can only run a structural pre-check. It reports `partial: true`, `validator: "js"` and `--require-full` exits `2` when no full validator is available. See [the validation contract](reference.md#validation-contract).

## Message inventory (from the source)

These are the message templates raised by `parser.py`, `validator.py` and `rings.py`. `{…}` marks an interpolated value. Some encoder-side templates are listed for completeness but are not reachable from `check`; the column says so.

| File | Level | Template | Reachable from `check` |
| --- | --- | --- | --- |
| `parser.py` | error | `Expected expression, got '{…}'` | yes |
| `parser.py` | error | `Invalid color attribute value` | yes |
| `parser.py` | error | `opacity must be a number or expression in 0..1` | yes |
| `parser.py` | error | `Unexpected character {…}` | yes |
| `parser.py` | error | `Expected {…}, got {…}` | yes |
| `parser.py` | error | `Unexpected trailing token '{…}'` | yes |
| `parser.py` | error | `morph '{…}' requires a u: expression` | yes |
| `parser.py` | error | `morph u must be a number or expression` | yes |
| `parser.py` | error | `mix() takes exactly 3 arguments` | yes |
| `parser.py` | error | `Expected 'scene' or 'film' declaration, got '{…}'` | yes |
| `parser.py` | error | `Unclosed 'scene' block` | yes |
| `parser.py` | error | `Unclosed 'film' block` | yes |
| `parser.py` | error | `Frame range bounds must be integers` | yes |
| `parser.py` | error | `Frame range {…}..{…} is reversed; write {…}..{…}` | yes |
| `parser.py` | error | `Unclosed 'frame' block` | yes |
| `parser.py` | error | `Palette entry '{…}' cannot be a mix(); palette colours are static` | yes |
| `parser.py` | error | `Unclosed 'def {…}' block` | yes |
| `parser.py` | error | `Unknown transform attribute '{…}'` | yes |
| `parser.py` | error | `Expected a numeric transform component` | yes |
| `parser.py` | error | `transform.{…} requires 2 components` | yes |
| `parser.py` | error | `Unknown morph attribute '{…}'` | yes |
| `parser.py` | error | `morph samples must be an integer` | yes |
| `parser.py` | error | `Expected ':' after attribute '{…}'` | yes |
| `parser.py` | error | `Undefined palette color '${…}'` | yes |
| `parser.py` | error | `mix() expects two colours and a number: mix(#RRGGBB, $name, u)` | yes |
| `parser.py` | error | `Expected version string or number after 'northcel'` | yes |
| `parser.py` | error | `Unknown function '{…}'` | yes |
| `parser.py` | error | `{…} expects {…} arguments` | yes |
| `parser.py` | error | `Unsupported statement '{…}' inside def block` | yes |
| `parser.py` | error | `Unknown scene statement '{…}'` | yes |
| `parser.py` | error | `Unknown frame statement '{…}'` | yes |
| `parser.py` | error | `Unknown film statement '{…}'` | yes |
| `validator.py` | error | `Unsupported NorthCel version '{…}'. Supported: {…}` | yes |
| `validator.py` | error | `Canvas dimensions {…}x{…} out of valid range [1..8192]` | yes |
| `validator.py` | error | `FPS {…} out of valid range [1..240]` | yes |
| `validator.py` | error | `Unsupported precision '{…}' (expected '0.25px', '0.25px-b63', or '1px')` | yes |
| `validator.py` | error | `paper.antialias_grid must be 1, 2, 4, or 8 (got {…})` | yes |
| `validator.py` | error | `Color channel {…}={…} out of range [0..255]` | yes |
| `validator.py` | warning | `opacity is a spec 0.4 attribute and is ignored in a '{…}' document; declare northcel "0.4.0-draft" to use it` | yes |
| `validator.py` | error | `{…} requires northcel "0.4.0-draft" (this document declares '{…}')` | yes |
| `validator.py` | error | `Film frames count must be >= 1 (got {…})` | yes |
| `validator.py` | error | `Frame override index {…} out of range [0..{…}]` | yes |
| `validator.py` | error | `Frame range {…}..{…} out of range [0..{…}]` | yes |
| `validator.py` | warning | `Layer '{…}' declares rings: {…}, but payload contains {…} rings` | yes |
| `validator.py` | error | `Layer '{…}' has invalid ring payload: {…}` | yes |
| `validator.py` | error | `Swarm '{…}' must have agents >= 1 (got {…})` | yes |
| `validator.py` | warning | `Frame range {…}..{…} overlaps {…}..{…} (line {…}); the later block wins for frames {…}..{…}` | yes |
| `validator.py` | error | `Swarm '{…}' payload decoded to 0 rings` | yes |
| `validator.py` | error | `Swarm '{…}' has invalid ring payload: {…}` | yes |
| `validator.py` | error | `Stroke '{…}' requires at least 2 control points` | yes |
| `validator.py` | error | `Stroke '{…}' widths must be > 0` | yes |
| `validator.py` | error | `Ribbon '{…}' requires at least 2 (x, y, width) points` | yes |
| `validator.py` | error | `Morph '{…}' samples must be {…}..{…} (got {…})` | yes |
| `validator.py` | error | `Morph '{…}' has invalid ring payload: {…}` | yes |
| `validator.py` | error | `Morph '{…}' pairs ring i with ring i, but its sides have {…} and {…} rings` | yes |
| `validator.py` | error | `Use of undefined def block '{…}'` | yes |
| `rings.py` | error | `A polygon ring requires at least 3 vertices.` | no (encoder-only or unreachable through a document) |
| `rings.py` | error | `Ring collapses to fewer than 3 distinct quarter-pixel vertices.` | no (encoder-only or unreachable through a document) |
| `rings.py` | error | `Empty quarter-pixel ring string.` | no (encoder-only or unreachable through a document) |
| `rings.py` | error | `Decoded ring has only {…} vertices (< 3).` | yes (wrapped as `Layer … has invalid ring payload: …`) |
| `rings.py` | error | `Ring collapses to fewer than 3 distinct vertices.` | no (encoder-only or unreachable through a document) |
| `rings.py` | error | `Base-63 ring string must contain ':' after 'x0,y0'.` | no (encoder-only or unreachable through a document) |
| `rings.py` | error | `Base-63 ring header must be 'x0,y0'.` | yes (wrapped as `Layer … has invalid ring payload: …`) |
| `rings.py` | error | `Base-63 delta tail must have an even number of characters.` | yes (wrapped as `Layer … has invalid ring payload: …`) |
| `rings.py` | error | `Decoded Base-63 ring has only {…} vertices (< 3).` | yes (wrapped as `Layer … has invalid ring payload: …`) |
| `rings.py` | error | `Expected 'dx,dy' pair at token {…} ('{…}').` | yes (wrapped as `Layer … has invalid ring payload: …`) |
| `rings.py` | error | `Invalid Base-63 start coordinates '{…}'.` | yes (wrapped as `Layer … has invalid ring payload: …`) |
| `rings.py` | error | `Invalid Base-63 character pair '{…}{…}' at offset {…}.` | yes (wrapped as `Layer … has invalid ring payload: …`) |
| `rings.py` | error | `Non-integer quarter-pixel delta '{…}'.` | yes (wrapped as `Layer … has invalid ring payload: …`) |
| `rings.py` | error | `Ring {…}: {…}` | yes (wrapped as `Layer … has invalid ring payload: …`) |

## Reproduced diagnostics

Each case is a complete `.ncel` file that was run through `check`; the output shown is exactly what the tool printed. The file is always called `broken.ncel`, so the path prefix is stable.

### 1. An unknown transform attribute

*Case id:* `p-transform-attribute`

<!-- case-source -->
```ncel
northcel "0.3.0-draft"
scene X { transform all(opacity: 1) }
```

```console
$ northcel check broken.ncel
broken.ncel:2:11: error: Unknown transform attribute 'opacity'
# exit 1
```

**Cause.** Only scale, rotate, anchor and translate are transform attributes.

**Fix.** Use a supported attribute. Since spec 0.4, opacity is an attribute of primitives and of `use`, not of transforms.

### 2. A transform anchor with one component

*Case id:* `p-transform-pair`

<!-- case-source -->
```ncel
northcel "0.3.0-draft"
scene X { transform all(anchor: 3) }
```

```console
$ northcel check broken.ncel
broken.ncel:2:11: error: transform.anchor requires 2 components
# exit 1
```

**Cause.** Anchors and translations are explicit two-component tuples.

**Fix.** Write anchor: (x,y).

### 3. A nonnumeric transform component

*Case id:* `p-transform-number`

<!-- case-source -->
```ncel
northcel "0.3.0-draft"
scene X { transform all(rotate: #FFF) }
```

```console
$ northcel check broken.ncel
broken.ncel:2:11: error: Expected a numeric transform component
# exit 1
```

**Cause.** Every transform component is a number or pure expression, not a colour.

**Fix.** Use a numeric component.

### 4. An easing function with the wrong arity

*Case id:* `p-easing-arity`

<!-- case-source -->
```ncel
northcel "0.3.0-draft"
scene X { transform all(scale: ease(1,2)) }
```

```console
$ northcel check broken.ncel
broken.ncel:2:32: error: ease expects 1 arguments
# exit 1
```

**Cause.** ease needs one argument; smoothstep needs three.

**Fix.** Write ease(t) or smoothstep(0,1,t).

### 5. A frame range written backwards

*Case id:* `p-frame-range-reversed`

<!-- case-source -->
```ncel
northcel "0.4.0-draft"
film F(frames: 9) {
  frame 5..2 { }
}
```

```console
$ northcel check broken.ncel
broken.ncel:3:9: error: Frame range 5..2 is reversed; write 2..5
# exit 1
```

**Cause.** `frame A..B` covers A through B inclusive and needs A <= B.

**Fix.** Swap the bounds: `frame 2..5`.

### 6. A mix() inside a palette

*Case id:* `p-mix-in-palette`

<!-- case-source -->
```ncel
northcel "0.4.0-draft"
scene S {
  palette { dusk: mix(#203040, #F0A060, 0.5) }
}
```

```console
$ northcel check broken.ncel
broken.ncel:3:3: error: Palette entry 'dusk' cannot be a mix(); palette colours are static
# exit 1
```

**Cause.** Palette entries are static colours; `mix` is evaluated per frame.

**Fix.** Keep both colours in the palette and write `color: mix($a, $b, u)` on the primitive or paper.

### 7. A mix() whose first argument is not a colour

*Case id:* `p-mix-arguments`

<!-- case-source -->
```ncel
northcel "0.4.0-draft"
scene S {
  layer a(color: mix(0, #FFFFFF, 0.5)) { "0,0 4,0 0,4" }
}
```

```console
$ northcel check broken.ncel
broken.ncel:3:22: error: mix() expects two colours and a number: mix(#RRGGBB, $name, u)
# exit 1
```

**Cause.** `mix(a, b, u)` takes two colours (hex, rgb(), $name or mix) and a number.

**Fix.** Write `mix(#000000, #FFFFFF, t)`; for a grey use its hex value.

### 8. A morph without u

*Case id:* `p-morph-u`

<!-- case-source -->
```ncel
northcel "0.4.0-draft"
scene S {
  morph m(tone: 0) { "0,0 4,0 0,4" => "0,0 8,0 0,8" }
}
```

```console
$ northcel check broken.ncel
broken.ncel:3:3: error: morph 'm' requires a u: expression
# exit 1
```

**Cause.** A morph needs the interpolation factor; there is no implicit time.

**Fix.** Add `u: <expression>`, for example `u: smoothstep(11, 18, f)`.

### 9. A morph whose sides have different ring counts

*Case id:* `v-morph-rings`

<!-- case-source -->
```ncel
northcel "0.4.0-draft"
scene S {
  morph m(tone: 0, u: 0.5) { "0,0 4,0 0,4|8,8 4,0 0,4" => "0,0 8,0 0,8" }
}
```

```console
$ northcel check broken.ncel
broken.ncel:3:3: error: Morph 'm' pairs ring i with ring i, but its sides have 2 and 1 rings
# exit 1
```

**Cause.** Ring i of the first payload pairs with ring i of the second. The vertex counts may differ, the ring counts may not.

**Fix.** Split the morph into one morph per ring pair, or give both sides the same number of rings.

### 10. A spec 0.4 construct in a 0.3 document

*Case id:* `v-spec04-header`

<!-- case-source -->
```ncel
northcel "0.3.0-draft"
film F(frames: 6) {
  frame 1..3 { layer a(tone: 0) { "0,0 4,0 0,4" } }
}
```

```console
$ northcel check broken.ncel
broken.ncel:3:3: error: frame-range requires northcel "0.4.0-draft" (this document declares '0.3.0-draft')
# exit 1
```

**Cause.** `mix`, `morph` and frame ranges are spec 0.4. A document that declares an older version must not use them; the native runtime (spec 0.3) cannot render them.

**Fix.** Change the header to `northcel "0.4.0-draft"` (the file then renders with the Python reference).

### 11. opacity in a 0.3 document

*Case id:* `v-opacity-old-header`

<!-- case-source -->
```ncel
northcel "0.3.0-draft"
scene S {
  layer a(tone: 0, opacity: 0.5) { "0,0 4,0 0,4" }
}
```

```console
$ northcel check broken.ncel
broken.ncel:3:3: warning: opacity is a spec 0.4 attribute and is ignored in a '0.3.0-draft' document; declare northcel "0.4.0-draft" to use it
# exit 0
```

**Cause.** Before spec 0.4 an `opacity` attribute was accepted and ignored. A document with an older header keeps that meaning.

**Fix.** Change the header to `northcel "0.4.0-draft"` to apply it, or delete the attribute.

### 12. Overlapping frame ranges

*Case id:* `v-frame-range-overlap`

<!-- case-source -->
```ncel
northcel "0.4.0-draft"
film F(frames: 10) {
  frame 0..5 { layer a(tone: 0) { "0,0 4,0 0,4" } }
  frame 4..9 { layer a(tone: 90) { "0,0 4,0 0,4" } }
}
```

```console
$ northcel check broken.ncel
broken.ncel:4:3: warning: Frame range 4..9 overlaps 0..5 (line 3); the later block wins for frames 4..5
# exit 0
```

**Cause.** Exactly one frame block applies to a frame: an exact `frame N`, else the last range that contains it. Blocks are not merged.

**Fix.** Make the ranges disjoint, or keep the overlap on purpose: the warning names the frames where the later block wins.

### 13. A number that starts with a dot

*Case id:* `p-unexpected-char`

<!-- case-source -->
```ncel
northcel "0.2.0-draft"

scene BoilBad(width: 360, height: 210) {
  stroke wobble(color: #202830, width: 4px, boil: .5px) {
    (40, 90), (120, 70), (200, 100), (280, 80)
  }
}
```

```console
$ northcel check broken.ncel
broken.ncel:4:51: error: Unexpected character '.'
# exit 1
```

**Cause.** NorthCel numbers must start with a digit. `.5px` is not a token; the tokenizer stops at the dot.

**Fix.** Write `0.5px`.

### 14. A missing comma in a header

*Case id:* `p-expected-token`

<!-- case-source -->
```ncel
northcel "0.2.0-draft"

scene HeaderBad(width: 320, height: 180 {
  paper { color: #F6F1E7 }
}
```

```console
$ northcel check broken.ncel
broken.ncel:3:41: error: Expected IDENT, got '{'
# exit 1
```

**Cause.** The header's attribute list must close with `)`. The `{` arrived while the parser was still inside the list.

**Fix.** Close the attributes: `width: 320, height: 180)` then `{`.

### 15. A statement with no root container

*Case id:* `p-no-root`

<!-- case-source -->
```ncel
northcel "0.2.0-draft"

layer sky(color: #BFD8E8, rings: 1) { "0,0 1920,0 0,1080 -1920,0" }
```

```console
$ northcel check broken.ncel
broken.ncel:3:1: error: Expected 'scene' or 'film' declaration, got 'layer'
# exit 1
```

**Cause.** A document must start with `scene` or `film`. A bare primitive has nowhere to paint.

**Fix.** Wrap the statements in `scene Name(...) { ... }` or `film Name(...) { ... }`.

### 16. Text after the closing brace

*Case id:* `p-trailing-token`

<!-- case-source -->
```ncel
northcel "0.2.0-draft"

scene Trailing(width: 320, height: 180) {
  paper { color: #F6F1E7 }
}

extra
```

```console
$ northcel check broken.ncel
broken.ncel:7:1: error: Unexpected trailing token 'extra'
# exit 1
```

**Cause.** One document, one root. A second statement after the root's closing `}` is a trailing token.

**Fix.** Delete the extra text, or move it inside the root (and give it a valid statement).

### 17. A film attribute inside a scene body

*Case id:* `p-scene-statement`

<!-- case-source -->
```ncel
northcel "0.2.0-draft"

scene SceneFrames(width: 320, height: 180, fps: 12) {
  paper { color: #F6F1E7 }
  frames: 12
}
```

```console
$ northcel check broken.ncel
broken.ncel:5:3: error: Unknown scene statement 'frames'
# exit 1
```

**Cause.** `frames` is a `film` header attribute. It is not a scene statement.

**Fix.** Use `film Name(..., frames: N)` if you want a timeline; a scene has one frame.

### 18. A film attribute inside the film body

*Case id:* `p-film-statement`

<!-- case-source -->
```ncel
northcel "0.2.0-draft"

film FilmFrames(width: 320, height: 180, fps: 12) {
  frames: 12
  paper { color: #F6F1E7 }
}
```

```console
$ northcel check broken.ncel
broken.ncel:4:3: error: Unknown film statement 'frames'
# exit 1
```

**Cause.** `frames` belongs in the `film` header, not among the body statements.

**Fix.** Move it: `film Name(..., frames: 12) { ... }`.

### 19. A header attribute inside a frame override

*Case id:* `p-frame-statement`

<!-- case-source -->
```ncel
northcel "0.2.0-draft"

film FrameStmt(width: 320, height: 180, fps: 12, frames: 2) {
  paper { color: #F6F1E7 }
  frame 0 {
    frames: 2
  }
}
```

```console
$ northcel check broken.ncel
broken.ncel:6:5: error: Unknown frame statement 'frames'
# exit 1
```

**Cause.** A `frame k { ... }` block holds primitives, defs, palette and paper — not header attributes.

**Fix.** Put `frames`/`fps`/`seed` only in the film header.

### 20. A missing closing brace

*Case id:* `p-unclosed-scene`

<!-- case-source -->
```ncel
northcel "0.2.0-draft"

scene Unclosed(width: 320, height: 180) {
  paper { color: #F6F1E7 }
  layer sky(color: #BFD8E8, rings: 1) { "0,0 1920,0 0,1080 -1920,0" }
```

```console
$ northcel check broken.ncel
broken.ncel:3:1: error: Unclosed 'scene' block
# exit 1
```

**Cause.** The parser reached end of file inside the `scene` block. The position points at where the block started, not at the missing brace.

**Fix.** Close the block with `}`.

### 21. A missing brace in a def

*Case id:* `p-unclosed-def`

<!-- case-source -->
```ncel
northcel "0.2.0-draft"

scene DefUnclosed(width: 320, height: 180) {
  def Mark(dx: 0) {
    stroke line(color: #202830, width: 2) { (0, 0), (10, 10) }
```

```console
$ northcel check broken.ncel
broken.ncel:4:3: error: Unclosed 'def Mark' block
# exit 1
```

**Cause.** The parser reached end of file inside a `def` block.

**Fix.** Close the `def` block. The error names the def and its opening position.

### 22. A missing brace in a film

*Case id:* `p-unclosed-film`

<!-- case-source -->
```ncel
northcel "0.2.0-draft"

film FilmOpen(width: 320, height: 180, fps: 12, frames: 2) {
  paper { color: #F6F1E7 }
```

```console
$ northcel check broken.ncel
broken.ncel:3:1: error: Unclosed 'film' block
# exit 1
```

**Cause.** The parser reached end of file inside the `film` block.

**Fix.** Close the film with `}`.

### 23. A missing brace in a frame override

*Case id:* `p-unclosed-frame`

<!-- case-source -->
```ncel
northcel "0.2.0-draft"

film FrameOpen(width: 320, height: 180, fps: 12, frames: 2) {
  paper { color: #F6F1E7 }
  frame 0 {
    layer sky(color: #BFD8E8, rings: 1) { "0,0 1920,0 0,1080 -1920,0" }
```

```console
$ northcel check broken.ncel
broken.ncel:5:3: error: Unclosed 'frame' block
# exit 1
```

**Cause.** The parser reached end of file inside a `frame k` block.

**Fix.** Close the override; the error points at the `frame` keyword.

### 24. A `use` inside a `def`

*Case id:* `p-def-statement`

<!-- case-source -->
```ncel
northcel "0.2.0-draft"

scene DefUse(width: 320, height: 180) {
  def Inner(dx: 0) {
    stroke line(color: #202830, width: 2) { (0, 0), (10, 10) }
  }
  def Outer(dx: 0) {
    use Inner(dx: 4)
  }
  use Outer(dx: 10)
}
```

```console
$ northcel check broken.ncel
broken.ncel:8:5: error: Unsupported statement 'use' inside def block
# exit 1
```

**Cause.** A `def` body may contain only layer/wash/cel, swarm, stroke and ribbon primitives. Nesting `use` is not supported.

**Fix.** Expand the other def at the call site instead, or copy the primitive into this def.

### 25. A missing colon after an attribute name

*Case id:* `p-attr-colon`

<!-- case-source -->
```ncel
northcel "0.2.0-draft"

scene AttrBad(width: 320, height: 180) {
  layer sky(color #BFD8E8, rings: 1) { "0,0 1920,0 0,1080 -1920,0" }
}
```

```console
$ northcel check broken.ncel
broken.ncel:4:19: error: Expected ':' after attribute 'color'
# exit 1
```

**Cause.** Every attribute is `name: value`. The parser found the name and then something that is not `:`.

**Fix.** Write `color: #RRGGBB`.

### 26. A palette colour used before it exists

*Case id:* `p-palette-undefined`

<!-- case-source -->
```ncel
northcel "0.2.0-draft"

scene PaletteBad(width: 320, height: 180) {
  palette { ink: #202830 }
  layer sky(color: $blue, rings: 1) { "0,0 1920,0 0,1080 -1920,0" }
}
```

```console
$ northcel check broken.ncel
broken.ncel:5:21: error: Undefined palette color '$blue'
# exit 1
```

**Cause.** `$name` is resolved while the body is parsed. A name declared later (or never) is undefined at the reference.

**Fix.** Declare the colour earlier in the same body, or use a literal.

### 27. A function NorthCel does not have

*Case id:* `p-unknown-function`

<!-- case-source -->
```ncel
northcel "0.2.0-draft"

scene FunBad(width: 320, height: 180) {
  paper { color: #F6F1E7 }
  layer sky(color: oklch(0.7, 0.08, 220), rings: 1) { "0,0 1920,0 0,1080 -1920,0" }
}
```

```console
$ northcel check broken.ncel
broken.ncel:5:20: error: Unknown function 'oklch'
# exit 1
```

**Cause.** Only `lerp`, `sin`, `cos` and `step` are expression functions. `oklch(...)` parses as a call and is rejected by name.

**Fix.** Use `rgb(r, g, b)` / `#RRGGBB`, or precompute the sRGB value and put it in the palette.

### 28. An empty attribute value

*Case id:* `p-expected-expression`

<!-- case-source -->
```ncel
northcel "0.2.0-draft"

scene ExprBad(width: 320, height: 180) {
  layer sky(color: , rings: 1) { "0,0 1920,0 0,1080 -1920,0" }
}
```

```console
$ northcel check broken.ncel
broken.ncel:4:20: error: Expected expression, got ','
# exit 1
```

**Cause.** The parser expected an expression after `color:` and found `)`.

**Fix.** Give the attribute a value.

### 29. A version header with no version

*Case id:* `p-version-value`

<!-- case-source -->
```ncel
northcel scene

scene Bad(width: 320, height: 180) {
  paper { color: #F6F1E7 }
}
```

```console
$ northcel check broken.ncel
broken.ncel:1:10: error: Expected version string or number after 'northcel'
# exit 1
```

**Cause.** `northcel` must be followed by a quoted version string or a number, then the root declaration.

**Fix.** Write `northcel "0.2.0-draft"` or drop the header line.

### 30. A colour attribute that is not a colour

*Case id:* `p-colour-value`

<!-- case-source -->
```ncel
northcel "0.2.0-draft"

scene Bad(width: 320, height: 180) {
  layer sky(color: (1, 2), rings: 1) { "0,0 1280,0 0,720 -1280,0" }
}
```

```console
$ northcel check broken.ncel
broken.ncel:4:3: error: Invalid color attribute value
# exit 1
```

**Cause.** A tuple is a valid attribute value (for `translate:` and `taper:`), but it is not a colour.

**Fix.** Use `#RRGGBB`, `rgb(r, g, b)`, `tone: N` or `$palette`.

### 31. An unsupported specification version

*Case id:* `v-version`

<!-- case-source -->
```ncel
northcel "9.9.0"

scene Bad(width: 320, height: 180) {
  layer sky(color: #88AACC, rings: 1) { "0,0 1920,0 0,1080 -1920,0" }
}
```

```console
$ northcel check broken.ncel
broken.ncel:1:1: error: Unsupported NorthCel version '9.9.0'. Supported: ('0.1', '0.1.0', '0.1.0-draft', '0.2', '0.2.0', '0.2.0-draft', '0.3', '0.3.0', '0.3.0-draft', '0.4', '0.4.0', '0.4.0-draft')
# exit 1
```

**Cause.** The version claim must be one of `0.1`, `0.1.0`, `0.1.0-draft`, `0.2`, `0.2.0`, `0.2.0-draft`.

**Fix.** Use `northcel "0.2.0-draft"` (or drop the header).

### 32. A canvas larger than 8192

*Case id:* `v-canvas`

<!-- case-source -->
```ncel
northcel "0.2.0-draft"

scene TooWide(width: 9000, height: 360) {
  paper { color: #F6F1E7 }
}
```

```console
$ northcel check broken.ncel
broken.ncel:3:1: error: Canvas dimensions 9000x360 out of valid range [1..8192]
# exit 1
```

**Cause.** Each side is limited to 8192 pixels so a typo cannot request an impossible allocation.

**Fix.** Render tiles, or use a realistic size.

### 33. An fps outside 1..240

*Case id:* `v-fps`

<!-- case-source -->
```ncel
northcel "0.2.0-draft"

scene FpsBad(width: 320, height: 180, fps: 0) {
  paper { color: #F6F1E7 }
}
```

```console
$ northcel check broken.ncel
broken.ncel:3:1: error: FPS 0 out of valid range [1..240]
# exit 1
```

**Cause.** `fps` drives timing and the MP4; zero would divide by zero.

**Fix.** Use a value in `1..240`.

### 34. An unknown contour precision

*Case id:* `v-precision`

<!-- case-source -->
```ncel
northcel "0.2.0-draft"

scene PrecBad(width: 320, height: 180, precision: 0.5px) {
  paper { color: #F6F1E7 }
}
```

```console
$ northcel check broken.ncel
broken.ncel:3:1: error: Unsupported precision '0.5px' (expected '0.25px', '0.25px-b63', or '1px')
# exit 1
```

**Cause.** Only `0.25px`, `0.25px-b63` and `1px` are decoders.

**Fix.** Pick one of those three.

### 35. A colour channel outside 0..255

*Case id:* `v-colour-channel`

<!-- case-source -->
```ncel
northcel "0.2.0-draft"

scene ColourBad(width: 320, height: 180) {
  layer sky(color: rgb(300, 0, 0), rings: 1) { "0,0 1920,0 0,1080 -1920,0" }
}
```

```console
$ northcel check broken.ncel
broken.ncel:4:3: error: Color channel r=300 out of range [0..255]
# exit 1
```

**Cause.** Colours are 8-bit RGB. The validator checks `rgb()` channels and hex-derived values.

**Fix.** Clamp the channel to `0..255`.

### 36. An unsupported antialias grid

*Case id:* `v-antialias`

<!-- case-source -->
```ncel
northcel "0.2.0-draft"

scene AaBad(width: 320, height: 180) {
  paper { color: #F6F1E7, antialias_grid: 3 }
}
```

```console
$ northcel check broken.ncel
broken.ncel:4:3: error: paper.antialias_grid must be 1, 2, 4, or 8 (got 3)
# exit 1
```

**Cause.** The rasteriser integrates a square grid; only 1, 2, 4 and 8 are supported.

**Fix.** Use `4` (default) or `8` for finer edges.

### 37. A ring count that disagrees with the payload

*Case id:* `v-rings-warning`

<!-- case-source -->
```ncel
northcel "0.2.0-draft"

scene RingsWarn(width: 320, height: 180) {
  layer sky(color: #BFD8E8, rings: 3) { "0,0 1920,0 0,1080 -1920,0" }
}
```

```console
$ northcel check broken.ncel
broken.ncel:4:3: warning: Layer 'sky' declares rings: 3, but payload contains 1 rings
# exit 0
```

**Cause.** `rings:` is documentation. When it disagrees, the validator warns and still renders.

**Fix.** Update `rings:` to the number of `|`-separated rings (or delete it).

### 38. A swarm with no agents

*Case id:* `v-swarm-agents`

<!-- case-source -->
```ncel
northcel "0.2.0-draft"

scene SwarmBad(width: 320, height: 180) {
  bend_swarm dots(agents: 0, color: #202830) { "0,0 10,10 10,-10" }
}
```

```console
$ northcel check broken.ncel
broken.ncel:4:3: error: Swarm 'dots' must have agents >= 1 (got 0)
# exit 1
```

**Cause.** `agents` is the declared number of agents and must be at least 1.

**Fix.** Declare the number of rings you actually put in the payload.

### 39. A swarm whose payload decodes to no rings

*Case id:* `v-swarm-empty`

<!-- case-source -->
```ncel
northcel "0.2.0-draft"

scene SwarmEmpty(width: 320, height: 180) {
  bend_swarm dots(agents: 2, color: #202830) { "" }
}
```

```console
$ northcel check broken.ncel
broken.ncel:4:3: error: Swarm 'dots' payload decoded to 0 rings
# exit 1
```

**Cause.** A swarm must paint at least one agent; an empty payload paints nothing.

**Fix.** Add at least one `|`-separated ring.

### 40. A swarm with a malformed ring

*Case id:* `v-swarm-ring`

<!-- case-source -->
```ncel
northcel "0.2.0-draft"

scene SwarmRing(width: 320, height: 180) {
  bend_swarm dots(agents: 1, color: #202830) { "0,0 40,0" }
}
```

```console
$ northcel check broken.ncel
broken.ncel:4:3: error: Swarm 'dots' has invalid ring payload: Ring 0: Decoded ring has only 2 vertices (< 3).
# exit 1
```

**Cause.** Swarm payloads go through the same ring decoder as layers. A two-vertex ring is not an area.

**Fix.** Give the agent at least three vertices.

### 41. A stroke with one point

*Case id:* `v-stroke-points`

<!-- case-source -->
```ncel
northcel "0.2.0-draft"

scene StrokeBad(width: 320, height: 180) {
  stroke dot(color: #202830, width: 4px) { (40, 40) }
}
```

```console
$ northcel check broken.ncel
broken.ncel:4:3: error: Stroke 'dot' requires at least 2 control points
# exit 1
```

**Cause.** A stroke needs a direction; one point cannot be offset into a polygon.

**Fix.** Give it two points (a dot is a tiny layer, or a two-point stroke).

### 42. A stroke with zero width

*Case id:* `v-stroke-width`

<!-- case-source -->
```ncel
northcel "0.2.0-draft"

scene WidthBad(width: 320, height: 180) {
  stroke line(color: #202830, width: 0) { (40, 40), (80, 40) }
}
```

```console
$ northcel check broken.ncel
broken.ncel:4:3: error: Stroke 'line' widths must be > 0
# exit 1
```

**Cause.** Widths must be positive; zero would produce an empty polygon.

**Fix.** Use a positive width (the renderer clamps ribbon widths below 0.25 to 0.25, but validation rejects zero stroke widths first).

### 43. A ribbon with one point

*Case id:* `v-ribbon-points`

<!-- case-source -->
```ncel
northcel "0.2.0-draft"

scene RibbonBad(width: 320, height: 180) {
  ribbon line(color: #202830) { (40, 40, 4) }
}
```

```console
$ northcel check broken.ncel
broken.ncel:4:3: error: Ribbon 'line' requires at least 2 (x, y, width) points
# exit 1
```

**Cause.** A ribbon needs two `(x, y, width)` points to have a length.

**Fix.** Add a second point.

### 44. A use of an undefined def

*Case id:* `v-undefined-def`

<!-- case-source -->
```ncel
northcel "0.2.0-draft"

scene UseBad(width: 320, height: 180) {
  use Wave(dx: 10, dy: 0)
}
```

```console
$ northcel check broken.ncel
broken.ncel:4:3: error: Use of undefined def block 'Wave'
# exit 1
```

**Cause.** `use` is resolved against the defs in the same body (and, inside a frame, the film's defs too).

**Fix.** Declare `def Name(...) { ... }` before the use.

### 45. A film with zero frames

*Case id:* `v-film-frames`

<!-- case-source -->
```ncel
northcel "0.2.0-draft"

film FramesBad(width: 320, height: 180, fps: 12, frames: 0) {
  paper { color: #F6F1E7 }
}
```

```console
$ northcel check broken.ncel
broken.ncel:3:1: error: Film frames count must be >= 1 (got 0)
# exit 1
```

**Cause.** A timeline must have at least one frame.

**Fix.** Set `frames` to a positive integer.

### 46. A frame override beyond the film

*Case id:* `v-frame-range`

<!-- case-source -->
```ncel
northcel "0.2.0-draft"

film RangeBad(width: 320, height: 180, fps: 12, frames: 4) {
  paper { color: #F6F1E7 }
  layer sky(color: #BFD8E8, rings: 1) { "0,0 1920,0 0,1080 -1920,0" }
  frame 6 { drop sky }
}
```

```console
$ northcel check broken.ncel
broken.ncel:6:3: error: Frame override index 6 out of range [0..3]
# exit 1
```

**Cause.** Override indices are checked against the current `frames` header.

**Fix.** Fix `frames`, or delete/move the override.

### 47. A plain payload token without a comma

*Case id:* `r-q25-pair`

<!-- case-source -->
```ncel
northcel "0.2.0-draft"

scene RingPair(width: 320, height: 180) {
  layer sky(color: #BFD8E8, rings: 1) { "0,0 40 0,40" }
}
```

```console
$ northcel check broken.ncel
broken.ncel:4:3: error: Layer 'sky' has invalid ring payload: Ring 0: Expected 'dx,dy' pair at token 1 ('40').
# exit 1
```

**Cause.** Every plain quarter-pixel token is `dx,dy`; a bare number cannot be split.

**Fix.** Write both components, e.g. `0,0 40,0 0,40`.

### 48. A decimal in a quarter-pixel payload

*Case id:* `r-q25-noninteger`

<!-- case-source -->
```ncel
northcel "0.2.0-draft"

scene RingDecimal(width: 320, height: 180) {
  layer sky(color: #BFD8E8, rings: 1) { "0,0 1.5,0 0,40" }
}
```

```console
$ northcel check broken.ncel
broken.ncel:4:3: error: Layer 'sky' has invalid ring payload: Ring 0: Non-integer quarter-pixel delta '1.5,0'.
# exit 1
```

**Cause.** The plain encoding stores integers in quarter pixels, not floating-point pixels.

**Fix.** Multiply by four and write integers: `1.5px` becomes `6`.

### 49. A two-vertex ring

*Case id:* `r-q25-vertices`

<!-- case-source -->
```ncel
northcel "0.2.0-draft"

scene RingTwo(width: 320, height: 180) {
  layer sky(color: #BFD8E8, rings: 1) { "0,0 40,0" }
}
```

```console
$ northcel check broken.ncel
broken.ncel:4:3: error: Layer 'sky' has invalid ring payload: Ring 0: Decoded ring has only 2 vertices (< 3).
# exit 1
```

**Cause.** A closed contour needs at least three vertices.

**Fix.** Use a stroke for a line, or add a third vertex.

### 50. A Base-63 header without a comma

*Case id:* `r-b63-header`

<!-- case-source -->
```ncel
northcel "0.2.0-draft"

scene B63Head(width: 320, height: 180, precision: 0.25px-b63) {
  layer sky(color: #BFD8E8, rings: 1) { "abc:lxlxlx" }
}
```

```console
$ northcel check broken.ncel
broken.ncel:4:3: error: Layer 'sky' has invalid ring payload: Ring 0: Base-63 ring header must be 'x0,y0'.
# exit 1
```

**Cause.** The start coordinates are `x0,y0` before the colon.

**Fix.** Write `x0,y0:PAIRS`.

### 51. Non-integer Base-63 start coordinates

*Case id:* `r-b63-start`

<!-- case-source -->
```ncel
northcel "0.2.0-draft"

scene B63Start(width: 320, height: 180, precision: 0.25px-b63) {
  layer sky(color: #BFD8E8, rings: 1) { "a,b:lxlxlx" }
}
```

```console
$ northcel check broken.ncel
broken.ncel:4:3: error: Layer 'sky' has invalid ring payload: Ring 0: Invalid Base-63 start coordinates 'a,b'.
# exit 1
```

**Cause.** The start coordinates are plain integers.

**Fix.** Write integers: `720,360`.

### 52. An odd Base-63 delta tail

*Case id:* `r-b63-odd`

<!-- case-source -->
```ncel
northcel "0.2.0-draft"

scene B63Odd(width: 320, height: 180, precision: 0.25px-b63) {
  layer sky(color: #BFD8E8, rings: 1) { "720,360:lxlxl" }
}
```

```console
$ northcel check broken.ncel
broken.ncel:4:3: error: Layer 'sky' has invalid ring payload: Ring 0: Base-63 delta tail must have an even number of characters.
# exit 1
```

**Cause.** Each delta is exactly two characters; an odd tail cannot be split.

**Fix.** Remove or add one character.

### 53. A character outside the Base-63 alphabet

*Case id:* `r-b63-pair`

<!-- case-source -->
```ncel
northcel "0.2.0-draft"

scene B63Pair(width: 320, height: 180, precision: 0.25px-b63) {
  layer sky(color: #BFD8E8, rings: 1) { "720,360:lx!!lx" }
}
```

```console
$ northcel check broken.ncel
broken.ncel:4:3: error: Layer 'sky' has invalid ring payload: Ring 0: Invalid Base-63 character pair '!!' at offset 2.
# exit 1
```

**Cause.** Only `0-9A-Za-z_` are deltas. `!` is not.

**Fix.** Use a valid character pair.

### 54. A Base-63 ring with fewer than three vertices

*Case id:* `r-b63-vertices`

<!-- case-source -->
```ncel
northcel "0.2.0-draft"

scene B63Two(width: 320, height: 180, precision: 0.25px-b63) {
  layer sky(color: #BFD8E8, rings: 1) { "720,360:lx" }
}
```

```console
$ northcel check broken.ncel
broken.ncel:4:3: error: Layer 'sky' has invalid ring payload: Ring 0: Decoded Base-63 ring has only 2 vertices (< 3).
# exit 1
```

**Cause.** The start plus one pair is two vertices.

**Fix.** Add at least one more pair.

### 55. A file that does not exist

*Case id:* `v-file-not-found`

```console
$ northcel check missing.ncel
missing.ncel:1:1: error: File not found: missing.ncel
# exit 1
```

**Cause.** The path passed to `check` was not a readable file.

**Fix.** Pass the right path. This diagnostic is produced before parsing.

## What is not a diagnostic

- A successful `check` with a warning still renders. Read the warning; it is usually a stale `rings:` count.
- A clean JS pre-check is not full validation. `partial: true` and exit `2` mean only that no full validator ran.
- A valid file can still look wrong. Rendering is the only proof of the picture; see the [guide](guide/README.md).
- `check` does not evaluate the drawing at every frame. A time-dependent expression that divides by zero at one `f` is a render-time problem, not a check-time diagnostic.
