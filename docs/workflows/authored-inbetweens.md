# NorthNoir CLI: author deltas before assembly

**Optional companion documentation, owned by the `northnoir` CLI.** Nothing on
this page is required to use the drawing language or its standalone tools. This
repository does not ship this CLI. The workflow describes the **Phase 5 source
implementation**, not a claim that a 2.0.0 release is published. Use a source
build whose `northnoir polish inbetween --help` and `northnoir polish assemble
--help` expose these commands; a public install may not have them. Follow the
CLI's runtime/optional-feature diagnostics if vector support is unavailable.

The AI decides for each transition: **observe → decompose → decide (copy, move,
warp, recolour or redraw) → edit the delta → verify → iterate**. Scaffolding and
assembly supply files and timing, not a character rig, motion preset or quality
approval. The [editable-drawing method](../guide/17-editable-drawings.md) contains
five deliberately different illustrations, not templates.

## Start from an existing vector plan

Use an existing `polish` receipt with its vector source and original keys. This
example assumes key ids `1` and `2` really exist in that receipt; substitute its
actual ids and paths. Work in a writable directory and keep the original plan
and references unchanged.

```sh
northnoir polish inbetween --plan polish/receipt.json --from 1 --to 2 --out authored/a-b
```

The scaffold copies key A onto the plan's **global** frame grid and inventories
both keys without inventing semantic groups. Read `manifest.json`, the copied
source, both neighbour sources/images and the suggested verification commands.
The manifest records the requested/actual sample, transition-window `u`, and
source fingerprint. `u` is strictly between keys; a sample is not an original key.

Do not mistake the initial copy or a tool-availability probe for authored work
or an executed measurement. Optional perception hints are suggestions; a guide
image is never an output frame or acceptance evidence.

## Author only what changes

Edit the scaffold's authored `.ncel` input. Keep the film header (dimensions,
fps, frames, precision and seed), original keys and hold frames intact. Keep
necessary definitions and palette declarations local to its exact/range frame
blocks: assembly accepts this self-contained subset, not arbitrary top-level
definition imports. Expressions retain the original global `f`/`t` values.

Copy unchanged geometry and modify only named regions. A range needs a deliberate
per-frame delta; sparse samples do not automatically create smooth motion. Render
each authored frame and compare it to **both** original neighbours, inspect onion
overlays/contact sheets and review scale/position continuity. Read the scaffold's
verifier usage and generated commands; availability alone means `executed: false`,
not a pass. A copied key is not an in-between just because it validates.

Request a new drawing only for author-confirmed missing information: `new_angle`,
`new_pose`, `unseen_prop` or `topology`, with a reason. The `needs_keys.json`
`transitions` list is for those confirmed requests; automatic low/unknown
correspondence gaps belong in `authored`. A failed match is not proof that an
image model is needed. No paid generation is part of this workflow.

## Assemble, then review the whole film

Point assembly at the authored root; keep scaffold manifests and their authored
inputs together. Both commands require `--out`; choose a fresh output directory
outside the authored-input tree.

```sh
northnoir polish assemble --plan polish/receipt.json --inbetweens authored --out assembled
```

Read the assembly receipt and output paths. Assembly rejects stale plans,
changed metadata/seed, conflicting palettes, cross-file overlaps and attempts to
replace original keys or holds. It retains authored pixels and timeline
precedence; it does not synthesize unprovided motion. Preserve the recorded
relative asset paths when moving a plan or scaffold. Use a fresh output location
and never point source/reference files at output paths.

The receipt supplies audio unless explicitly overridden. Rendering an MP4 needs
the CLI's local video prerequisites; short audio must not shorten the original
frame count/duration, and long audio must not extend them. Inspect the assembled
frames, transitions, dimensions, fps and duration, and run the generated full-film
continuity/distinct checks. Those measurements and successful assembly are not
artistic acceptance. Full-size visual review and independent public-doc review
remain separate gates.
