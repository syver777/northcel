# NorthCel 0.5.0-draft — groups, warps, nudges and frame deltas

Status: draft implemented by **tools 0.6.0 from source (unreleased)**. Published
tools 0.5.0 implement spec 0.4 and cannot parse the 0.5 examples on this page.
Install this checkout in a venv with `python3 -m pip install -e './python[fit]'`
before running them. It is a **Python-reference**
feature set: the native runtime 0.4.0 implements spec 0.3 and every 0.5
document is routed to the labelled reference renderer.

Spec 0.4 remains valid and unchanged. A 0.5 document uses the same scene/film
model, palette, paper, primitives, `def`/`use`, `transform`, `frame A..B`,
`mix`, `morph` and `opacity`. This document specifies the additions.

## Why

NorthCel is a language for an AI to reproduce a drawing in code and then make
small, deliberate changes to create new frames. A drawing is not one anonymous
pile of paint: a face, an arm, a flower and a cloud are regions with identities.
The 0.5 constructs make those regions addressable:

* **group** a set of paints and give it a pivot, a clip and a parent;
* **transform** a whole group (translate / rotate / scale), not only one name;
* **warp** a group with a few handle points for squash, sway, cloth and petals;
* **nudge** one vertex of one named shape;
* **copy a key** with `use` and declare only the `nudge`/`transform` delta;
* optionally **attach** a group to a parent group so it follows its transform.

The language supplies general building blocks. It does not contain subject
recipes, character rigs or preset motions; the author decides what a group is
and what moves.

## Grammar additions

```ebnf
GroupStmt = "group" Ident [ AttrList ] "{" { GroupBodyStmt } "}" ;
WarpStmt  = "warp" Ident AttrList [ ";" ] ;
NudgeStmt = "nudge" Ident AttrList [ ";" ] ;

GroupBodyStmt = SceneBodyStmt | GroupStmt | WarpStmt | NudgeStmt | UseStmt ;
```

`GroupStmt` may appear wherever a scene statement may appear: scene, film,
frame block, def body and another group. A group body may contain primitives,
`use`, `transform`, `group`, `warp` and `nudge`; it does not contain `drop` or
`frame`.

Group attributes:

| Attribute | Value | Meaning |
| --- | --- | --- |
| `pivot` | `(x, y)` | rotation/scale centre for `transform <group>`; default `(0, 0)` |
| `opacity` | expression | paints the group on a saved canvas, then blends it; default 1 |
| `clip` | name | paint only where the named entry/group covers the canvas |
| `parent` | name | optional rigging link: the group joins the parent's transform path |

`warp` attributes:

| Attribute | Value | Meaning |
| --- | --- | --- |
| `handles` | `((x, y, dx, dy), ...)` | at least one handle; expressions allowed |
| `radius` | number | falloff radius in pixels; default 120 |

`nudge` attributes:

| Attribute | Value | Meaning |
| --- | --- | --- |
| `vertex` | integer ≥ 0 | vertex index in the chosen ring |
| `ring` | integer ≥ 0 | ring index; default 0 |
| `dx`, `dy` | number/expression | offset in pixels; default 0 |

## Semantics

### Groups and paint order

A group paints its body in source order at the group's position in the paint
list. Every paint produced inside the group carries the group path
`(outer, ..., inner)`. Nested groups paint in their own body order and keep
the outer path.

`opacity: u` opens one group-opacity scope: the group is painted into a saved
canvas and blended back with `floor(c + (s - c) * u + 0.5)` on the 8-bit
subpixel canvas, so overlaps inside the group do not compound. Nested opacity
scopes nest.

`clip: mask` restricts every paint in the group to the coverage of the named
entry or group. If the name resolves to a group, the union of its paints is
the mask. A clip target may be declared before or after the group; resolution
happens after the paint list is built. A missing clip target is a located
evaluation error. The mask itself still paints unless the author makes it
invisible (for example `opacity: 0`).
`check` performs parse/static validation, not paint-list evaluation; use `render`
or `shapes` to catch a missing clip target (including frame-dependent targets).

`parent: arm` adds `arm` to the group path before the group name. A transform
or warp targeting `arm` therefore includes the child group. A parent group
declared with a pivot contributes that pivot to the child path. The parent
may be declared before or after the child, but must be painted before a transform
that targets it, like any named entry.

### Group transforms

`transform <group>(scale: ..., rotate: ..., translate: ..., anchor: ...)`
applies to every paint whose path contains `<group>` (including outlines and
nested groups). The rotation/scale centre is `anchor` when that attribute is
explicit; otherwise the group's `pivot`. The transform is evaluated per frame
with the usual expressions, and it mutates the already-painted geometry in
source order. A transform of a name that has not been painted is a located
error.

The existing single-name `transform` is unchanged, including its default
anchor `(0, 0)` and its `all` target.

### Warp

`warp <group-or-name>(handles: ((x, y, dx, dy), ...), radius: r)` applies a
smooth free-form deformation to every targeted point:

```text
for each handle with distance d < r:
    w = (1 - (d/r)^2)^2
point += sum(w * (dx, dy)) / sum(w)
```

Outside every radius the point is unchanged. A point with no positive weight
is unchanged. The weighted average keeps the deformation bounded; overlapping
handles blend instead of adding. `radius` and the handle components are
per-frame expressions. Warp is deterministic and does not use random state.
For a rigid move use `transform`; warp is for non-rigid changes (a petal
bending, cloth folding, a cloud squashing).

### Nudge and frame deltas

`nudge <shape>(vertex: i, ring: k, dx: ..., dy: ...)` adds the offset to one
vertex of one named paint after that paint is produced. It is evaluated per
frame. It is not a silent no-op: an unknown target, ring or vertex is a
located error.

A frame delta reuses a key and declares only the changes:

```ncel
northcel "0.5.0-draft"
film Turn(width: 640, height: 360, fps: 24, frames: 8) {
  paper { color: #FFF8EC }
  def KeyA {
    group face(pivot: (320, 180)) {
      layer face_fill(color: #F2C6A0) { "240,120 160,0 0,120 -160,0" }
      layer eye_l(color: #202830) { "280,150 12,0 0,12 -12,0" }
    }
  }
  frame 0..3 { use KeyA }
  frame 4..7 {
    use KeyA
    nudge eye_l(vertex: 2, dx: 3px, dy: -1px)
    transform face(rotate: 2)
  }
}
```

`use KeyA` paints the key once at its position; the following `nudge` and
`transform` are deltas. A frame block may also replace a named entry in place
(the 0.4 rule) instead of nudging it.

### Addressable fit output

`northcel fit IMAGE --stacked -o shapes.ncel --receipt shapes.json` assigns every
fitted shape a stable id: `s` plus a 10-hex SHA-1 prefix (colour + quantised ring),
suffixed `_2`, `_3`, … on collision. `stacked_source` writes those ids as the
layer names. The fit receipt contains `shape_manifest`, one row per shape with:

```json
{"id": "s…", "color": [r, g, b], "area": 123.4, "kind": "region|gap|underpaint",
 "bbox": [x0, y0, x1, y1], "centroid": [x, y], "parent": "s…|null",
 "children": ["s…"], "neighbours": ["s…"]}
```

`northcel shapes FILE [--frame N]` lists or queries evaluated shapes with
`--ids`, `--color`, `--area-min`, `--area-max`, `--bbox x0,y0,x1,y1`,
`--centroid x,y,r`, `--parent` and `--mask IMAGE`. It returns JSON ids,
colours, areas, bboxes, centroids, parents, children and neighbours. The tool
suggests; the author decides.

Fit receipts and queries share geometry rows computed from the emitted
quarter-pixel rings (not unrounded fitting areas). Centroids are area-weighted
ring centroids; areas sum absolute ring areas. Parent/children use the smallest
larger bbox containing the centroid, and neighbours use centroid Manhattan
distance. These are geometry heuristics, not semantic rig parents, occlusion or
visible clipped area. Queries recompute them after any frame edits; receipt
`kind` is fitting metadata and query colours are hex rather than receipt RGB arrays.

## Rendering and versioning

Groups, warps and nudges are evaluated per frame in the reference renderer.
The native runtime 0.4.0 does not implement them; a document that uses any of
them, declares a 0.5 header, or has no header, is routed to the labelled Python reference by
both launchers. A document with an older header that uses a 0.5 construct is a
validation error naming `0.5.0-draft`. `opacity` and the 0.4 constructs keep
their existing rules. Headerless documents in tools 0.6.0 are
`0.5.0-draft`; documents with an explicit 0.1–0.4 header render as before.

The clip implementation intersects subpixel span intervals; the mask union is
exact for even-odd shape coverage. Clip coverage is binary at the subpixel level:
no feathering, soft edges or image masks; only named entry/group coverage.
Warp uses the smooth falloff above, not ARAP; a rigid rotation/scale belongs in
`transform`. Groups do not create
independent instances of a def: a repeated `use` still replaces same-named
paints at their paint position, as in 0.4.

## Worked illustration (not a template)

```ncel
northcel "0.5.0-draft"
film Petal(width: 320, height: 180, fps: 24, frames: 12) {
  palette { ink: #202830, pink: #E8A0B8, paper: #FFF8EC }
  paper { color: $paper }
  def Flower {
    group flower(pivot: (160, 150)) {
      stroke stem(color: $ink, width: 3) { (160, 150) (158, 70) }
      group head(pivot: (158, 60)) {
        layer petal(color: $pink) { "632,240 160,0 -80,-120 -80,-120" }
      }
    }
  }
  frame 0..5 { use Flower }
  frame 6..11 {
    use Flower
    warp head(handles: ((200, 30, 6 * sin(t * 6.28318), -2),), radius: 80)
    transform head(rotate: 4)
  }
}
```

This is an illustration of the constructs, not a preset: the author chooses
the groups, pivot, handles and delta for each film. It is a partial illustration:
group `opacity`, `clip` and `parent` are specified above, not exercised here.

## Compatibility summary

* 0.1–0.4 documents keep their pixels; `opacity` in a pre-0.4 document is
  still ignored with a warning.
* `mix`, `morph`, `frame A..B` and `opacity` require 0.4+; `group`, `warp` and
  `nudge` require 0.5+.
* The native runtime stays at spec 0.3; 0.4/0.5 documents use the labelled
  Python reference on every platform.
* Deterministic: no clocks, network, mutable cross-frame state or raster
  bitmaps in source documents.
