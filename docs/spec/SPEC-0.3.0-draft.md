# NorthCel Language Specification (`0.3.0-draft`)

Date: 2026-11-05. Tools release: 0.4.0. This is an additive extension of
[0.2.0-draft](SPEC-0.2.0-draft.md); every rule in that draft remains normative
unless extended here. Valid 0.1/0.2 documents MUST render unchanged.

## 1. Why this extension

A fitted drawing must be movable without rewriting (and requantising) every
vertex. Frame-by-frame animation also needs bounded easing, not only linear
interpolation. These needs were observed in scale/position discontinuities in a
90-drawing film. This extension does not infer poses, anatomy or correspondence.

## 2. Grammar (normative)

```ebnf
SceneStmt     = PrimStmt | UseStmt | DropStmt | TransformStmt ;
TransformStmt = "transform" Ident AttrList [ ";" ] ;
FuncCall      = ( "lerp" | "sin" | "cos" | "step" | "ease" | "smoothstep" )
                "(" [ Expr { "," Expr } ] ")" ;
```

`transform` is permitted in scenes, films, frame overrides and def bodies.
Its identifier is an already painted layer name, or `all`. Only `scale`,
`rotate`, `anchor` and `translate` are permitted attributes. `scale` is a scalar
or `(sx, sy)`, default 1. `rotate` is clockwise degrees, default 0. `anchor`
and `translate` are two-component tuples, default `(0, 0)`. Every component is
a pure per-frame expression. Tuple arity and unknown attributes are syntax errors.

## 3. Geometry semantics (normative)

The transform acts immediately on geometry painted before it, after decoding,
swarm evaluation, boil and outline/stroke expansion; later declarations are not
affected. It changes every matching paint-list entry, plus a coupled
`name__outline`. `all` changes all prior geometry but never the paper rectangle
or its grain. A missing named target is an evaluation error with the transform's
source location. Zero and negative scales are legal (collapse and reflection).

For point `(x,y)`, anchor `(ax,ay)`, scale `(sx,sy)`, angle `r` in radians and
translation `(dx,dy)`, implementations MUST use:

```text
u = (x - ax) * sx; v = (y - ay) * sy
x' = ax + u*cos(r) - v*sin(r) + dx
y' = ay + u*sin(r) + v*cos(r) + dy
```

Thus expanded line widths scale with their drawing. Repeated transforms compose
in source order. Film base transforms run before frame-override statements; a
frame-local camera should therefore be placed last in that override.

`ease(u)` clamps `u` to `[0,1]` and returns `u*u*u*(u*(u*6 - 15) + 10)`.
`smoothstep(a,b,x)` sets `u=clamp((x-a)/(b-a),0,1)` and returns `u*u*(3-2*u)`.
For `a==b`, it returns 0 if `x<a`, otherwise 1. Reversed endpoints are allowed.
`ease` requires exactly 1 argument; `smoothstep` exactly 3. Evaluation is stateless.

## 4. Fitting and tween authoring tools (non-normative)

`northcel fit` traces a raster into ordinary palette/contour source. The input
image is an **offline authoring input**, never embedded, referenced or read by a
renderer. Optional numerical libraries perform colour quantisation and contour
tracing, not artistic acceptance. Receipts count all geometry bytes and report
round-trip error. `northcel tween` resamples explicit vector rings by arclength,
aligns winding/start and bakes ordinary `.ncel` film geometry. A topology mismatch
requires an explicit hold fallback; no opacity blending, optical flow, semantic
segmentation or image synthesis is used. Tools cannot declare a tween good.

## 5. Native pipeline and conformance (normative)

MoonBit owns the new AST, diagnostics, expression and transform evaluation and
emits transformed f64 edges in unchanged NCIR v1. Bend/HVM2 continues evaluating
independent swarm agents before transforms; GLSL still integrates even-odd
coverage at each subpixel. No stage is replaced by the authoring tools. The
Python reference applies the identical rules. New fixtures MUST cover transformed
fill/outline, stroke, ribbon, swarm, reflection, rotation, easing endpoints,
missing targets and out-of-order film rendering in both implementations.

All 0.2 conformance probes and golden images remain mandatory. Cross-renderer
tolerance remains that of spec 0.1 §6 (pure polygons ≤0.05 MAE). Tool versions and
spec versions are independent: an additive grammar change increments the spec
minor, while packaging alone does not. Archived drafts MUST NOT be edited.
Headerless documents default to `0.3.0-draft` in tools 0.4.0; explicit older
headers remain supported and their rendering semantics are unchanged.
