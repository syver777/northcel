# Patterns cookbook

Eleven complete `.ncel` programs for AI-drawn video. Every file compiles, renders
and has a contact sheet of all its frames. The point is not to copy these
drawings; it is to copy the **structure** — when to use a `frame` override, when
one expression is enough, and where a swarm earns its place.

Each page has the full source, the measured file/token size, why the pattern
works, the pitfalls, and the commands that reproduce it. The files live in
[`examples/patterns/`](../../examples/patterns/). Everything here is rendered by
the reference renderer so the committed images are byte-reproducible; the docs
check does exactly that in CI.

| # | Pattern | What it teaches | Frames | Bytes | Tokens |
| ---: | --- | --- | ---: | ---: | ---: |
| 1 | [Head turn in 6 fps cels](01-head-turn-6fps.md) | two `step` quarter turns, silhouette swap, one-frame profile | 6 @ 6 fps | 2,339 | 1,107 |
| 2 | [Blink](02-blink.md) | dropping eyeballs, appending lid strokes for two frames | 8 @ 12 fps | 1,818 | 833 |
| 3 | [Jump with anticipation and squash](03-jump-anticipation-squash.md) | one travel expression, four key-pose body shapes | 8 @ 8 fps | 3,301 | 1,690 |
| 4 | [Colour filling at a specific beat](04-colour-beat.md) | a full colour plate gated by `step`, painted over a grey base | 8 @ 8 fps | 1,907 | 867 |
| 5 | [Cloud drift](05-cloud-drift.md) | three sine amplitudes as parallax, phased layers, coupled outlines | 10 @ 10 fps | 1,540 | 736 |
| 6 | [Character assembled progressively](06-progressive-assembly.md) | one part per beat, staged off-canvas, paint order | 8 @ 6 fps | 1,714 | 784 |
| 7 | [Duck walk](07-duck-walk.md) | opposite leg phases, body bob, strokes carrying the swing | 12 @ 12 fps | 1,683 | 787 |
| 8 | [Line boil that reads as hand-drawn](08-line-boil.md) | per-element boil amplitudes on a still drawing | 4 @ 8 fps | 1,020 | 469 |
| 9 | [A crowd as a swarm of small marks](09-crowd-swarm.md) | two swarms (heads, bodies), one drift, `agents` as declaration | 6 @ 6 fps | 2,346 | 1,339 |
| 10 | [A two-shot film with a frame override](10-two-shot.md) | both shots in one file, a `step` cut, a one-frame bird | 8 @ 8 fps | 2,151 | 1,004 |
| 11 | [Intact cel motion](11-intact-cel-motion.md) | one anchored matrix for fill and outline, continuous travel and eased scale/rotation | 9 @ 24 fps | 522 | 233 |

The original ten total **19,821 bytes, 9,616 cl100k tokens** for ten finished,
animated shots. That is the compactness argument in one line, and every number
is measured by the docs build rather than copied from a slide.

## How to read a pattern

1. Run `northcel check` on the file.
2. Render the frames and look at the contact sheet.
3. Change one number and re-render. The useful question is not "what does this
   file do" but "what happens if I change the step edge / amplitude / phase".
4. Read the pitfalls before adapting it. Most of them are failures that still
   compile and still render — the expensive kind.

## Which construct should this be?

| You want | Reach for | Pattern |
| --- | --- | --- |
| a pose change that a hand would redraw | `frame k` override | 1, 2, 3, 10 |
| continuous travel or cyclic motion | expressions of `t`/`f` | 3, 5, 7 |
| colour or a prop to arrive on a cue | `step` gate + replacement layers | 4, 6 |
| many similar small marks | `bend_swarm` | 9 |
| a living line on a still drawing | `boil` | 8 |
| reused geometry at several sizes | `def`/`use` | guide [7](../guide/07-def-use-and-parameters.md) |
| move/scale/rotate a drawing without changing its pose | `transform` + `ease` | 11; guide [15](../guide/15-fitting-transforms-and-inbetweens.md) |

If a pattern needs two constructs that disagree (for example a swarm that must
move per-agent, or a `cel` whose outline must lag), it is usually a sign that the
drawing should be split into named layers instead.
