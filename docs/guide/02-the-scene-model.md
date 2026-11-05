# 2. The scene model

A `.ncel` document is one root container plus an ordered list of statements.
Everything else in this guide is a detail of those two facts.

## Two roots

| Root | Frames | Use it for |
| --- | --- | --- |
| `scene` | one frame (`t = 0`, `f = 0`) | a still, a key pose, a cel you will trace |
| `film` | `frames` frames, `t = f / max(1, frames - 1)` | timing, motion, hand-drawn animation |

Both take the same header attributes:

| Attribute | Default | Meaning |
| --- | --- | --- |
| `width`, `height` | `1024` | canvas in pixels, `1..8192` |
| `fps` | `6` | frames per second, `1..240`; duration is `frames / fps` |
| `precision` | `0.25px` | contour encoding: `0.25px`, `0.25px-b63` or `1px` |
| `seed` | `42` | the integer that makes `boil` and swarms reproducible |

`frames` exists only on `film`. The header line is also where the optional
version claim goes: `northcel "0.2.0-draft"`.

## One ordered body

The body is painted top to bottom. There is no z-index. The permitted statements
are:

| Statement | Paints | Page |
| --- | --- | --- |
| `palette` | nothing; declares named colours | [4](04-palette-and-colour.md) |
| `paper` | the background, before everything | [3](03-paper-and-canvas.md) |
| `def` | nothing; declares a reusable group | [7](07-def-use-and-parameters.md) |
| `layer` / `wash` / `cel` | a filled contour | [5](05-cels-layers-and-outlines.md) |
| `stroke` / `ribbon` | ink along a path | [6](06-strokes-and-ribbons.md) |
| `bend_swarm` / `swarm` | many small contours at once | [11](11-bend-swarm.md) |
| `use` | the contents of a `def`, translated | [7](07-def-use-and-parameters.md) |
| `drop` | removes an inherited layer (film only) | [8](08-films-and-frame-overrides.md) |

`palette`, `paper` and `def` are declarations; order matters for `palette`
references, but their position in the paint list does not. Layers, strokes,
ribbons and swarms paint in the order they appear.

## A three-layer scene

<!-- render: assets/guide/02-depth-order.png -->
```ncel
northcel "0.2.0-draft"

scene DepthOrder(width: 480, height: 270, fps: 12, precision: 0.25px, seed: 11) {
  paper { color: #F4EFE4, antialias_grid: 4 }

  layer far_hill(color: #A9C4B8, rings: 1) { "0,480 1920,-96 0,216 -1920,8" }
  layer near_hill(color: #6E9A76, rings: 1) { "0,672 600,-112 720,120 600,-80 0,480 -1920,0" }
  layer moon(color: #F2D48A, rings: 1) { "1688,248 -24,75 -64,47 -80,0 -64,-47 -24,-75 24,-75 64,-47 80,0 64,47" }
}
```

![A far hill, a near hill and a moon, painted in that order](../assets/guide/02-depth-order.png)

The moon is listed last, so it paints over both hills. Moving its block above
`far_hill` would hide it behind the hills — the file would still be valid, and the
picture would be different. That is the whole layering model.

## Moving drawings (0.2 and 0.3)

In spec 0.2 the ways to move a drawn thing are:

- write different coordinates (fine for a still);
- `translate: (dx, dy)` on a layer or swarm (page [8](08-films-and-frame-overrides.md));
- `dx`/`dy` parameters on a `def` used with `use` (page [7](07-def-use-and-parameters.md));
- replace a named layer inside a `frame k { ... }` override (page [8](08-films-and-frame-overrides.md)).

Strokes and ribbons are not translatable; their points are expressions, so write
the motion into the point coordinates.

Spec 0.3 adds immediate named and whole-stage `transform` statements with scale,
rotation, anchors and translation, including on expanded strokes and ribbons.
See [chapter 15](15-fitting-transforms-and-inbetweens.md). This does not change
the meaning of any older `use` parameter named `scale`.

## What goes wrong

A document must start with `scene` or `film`. A bare statement at the root has
nowhere to paint.

<!-- expect-error: 3:1: error: Expected 'scene' or 'film' declaration, got 'layer' -->
```ncel
northcel "0.2.0-draft"

layer sky(color: #BFD8E8, rings: 1) { "0,0 1920,0 0,1080 -1920,0" }
```

```console
$ northcel check broken.ncel
broken.ncel:3:1: error: Expected 'scene' or 'film' declaration, got 'layer'
```

Wrap the statement in `scene Name(...) { ... }`. The error points at the token,
not at an indentation level, so a missing brace earlier in the file shows up as
the first token the parser could not fit.

## What a valid file still does not promise

`check` proves the grammar, the ring payloads and the numeric ranges. It does not
prove that the picture is good, that shapes are where you meant them, or that the
motion reads. Render the frame. Page [12](12-diagnostics-and-errors.md) is the
full validation contract.

Next: [3. Paper and canvas](03-paper-and-canvas.md).
