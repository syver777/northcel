# 1. Getting started

NorthCel is a drawing language. A `.ncel` file describes paper, shapes, ink and
timing, and the `northcel` command turns it into PNG frames. Nothing is hidden in
a bitmap: every mark in this guide is computed from the text you can read.

This page takes you from nothing to a rendered frame, then shows the one check
that catches most first-file mistakes.

## Install

One name everywhere: **`northcel`**. The command `ncel` is a short alias for the
same binary.

| You have | Run | Native runtime? |
| --- | --- | --- |
| Python 3.10–3.13 | `pip install northcel` (or `pipx install northcel`) | Yes on Linux x86_64; the labelled reference renderer elsewhere |
| Node 20+ | `npm install -g northcel` | **0.4.0 launcher only** — older than 0.5.0; use PyPI or Homebrew for the current version |
| Homebrew on Linux | `brew tap syver777/northcel && brew install northcel` | Yes |
| A shell + curl | `curl -fsSL https://github.com/syver777/northcel/releases/latest/download/install.sh \| bash` | Yes on Linux x86_64 |

Published tools version **0.5.0**, specification **0.4.0-draft**. `0.1.0-draft`, `0.2.0-draft` and
`0.3.0-draft` files still load and render as before. The native runtime 0.4.0 implements spec
0.3; spec 0.4 documents render with the labelled Python reference (the sample below is from a
0.4.0 install).

This numbered guide targets the published install. **Tools 0.6.0 / spec 0.5 are
source-only and unreleased**; the [current spec additions](../spec/SPEC-0.5.0-draft.md)
and [agent guide](../agent-guide.md) require this checkout installed in a venv
with `python3 -m pip install -e './python[fit]'`. A published 0.5.0 install must not
be given a 0.5-header example with `group`, `warp` or `nudge`.

## Prove the install

```console
$ northcel doctor
northcel 0.4.0  (NorthCel spec 0.3.0-draft)
platform      linux-x86_64 glibc 2.39
supported     yes
native        0.4.0  (bundle checksums verified, stage MoonBit+Bend+GLSL)
...
$ northcel verify
  [PASS] starter-render / shower-f0001-conformance / family-film-6-frames /
         determinism / film-frames-differ      → result: all checks passed   (5/5)
```

`doctor` exits `0` only when the native runtime is genuinely usable. On macOS or
Windows it exits `3` and explains what is missing; rendering there is done by the
reference renderer and every receipt says `"renderer": "python-reference"`. That
is a real renderer, not a claim of native support.

## Your first file

Save this as `first_light.ncel`. Coordinates are pixels, origin at the top-left,
`+x` right and `+y` down. The quoted strings are contour payloads; page
[10](10-contour-encodings.md) explains their encoding in detail.

<!-- render: assets/guide/01-first-light.png -->
```ncel
northcel "0.2.0-draft"

scene FirstLight(width: 640, height: 360, fps: 12, precision: 0.25px, seed: 7) {
  paper { color: #F6F1E7, antialias_grid: 4, grain: 0.008 }

  layer sky(color: #BFD8E8, rings: 1) { "0,0 2560,0 0,1440 -2560,0" }
  layer hill(color: #6E9A76, rings: 1) { "0,880 2560,0 0,560 -2560,0" }
  layer sun(color: #E8A33D, rings: 1) { "2400,360 -47,113 -113,47 -113,-47 -47,-113 47,-113 113,-47 113,47" }
}
```

![First light: paper, sky, hill and sun](../assets/guide/01-first-light.png)

```console
$ northcel check first_light.ncel
first_light.ncel: OK (NorthCel 0.2.0-draft)
$ northcel render first_light.ncel -o first_light.png
$ northcel fmt -w first_light.ncel        # optional: canonical formatting
```

Three things are worth noticing now, because every later page builds on them:

1. The file starts with `northcel "0.2.0-draft"`. The version is a claim about
   the grammar you used, and the checker verifies it.
2. `scene` holds one frame. A `film` holds a timeline; page
   [8](08-films-and-frame-overrides.md) covers it.
3. Statements paint in order. `sky` is behind `hill`, and `sun` is on top. Later
   pages use that order instead of z-index attributes.

## What goes wrong

`frames:` is a **film** header attribute. Putting it inside a `scene` body is the
most common first-file mistake: the parser does not know the statement there.

<!-- expect-error: 5:3: error: Unknown scene statement 'frames' -->
```text
northcel "0.2.0-draft"

scene FirstLight(width: 640, height: 360, fps: 12, precision: 0.25px, seed: 7) {
  paper { color: #F6F1E7, antialias_grid: 4, grain: 0.008 }
  frames: 12
  layer sky(color: #BFD8E8, rings: 1) { "0,0 2560,0 0,1440 -2560,0" }
}
```

```console
$ northcel check broken.ncel
broken.ncel:5:3: error: Unknown scene statement 'frames'
```

The fix is not to delete the idea, but to move it: a still scene has no frame
count. If you want several frames, use `film Name(..., frames: 12) { ... }`.
The full list of messages is in [Common errors](../errors.md).

## The loop you will repeat

```console
$ northcel check file.ncel --json     # grammar, semantics, exact line:column
$ northcel render file.ncel -o f.png  # look at a still
$ northcel film file.ncel -o out/     # look at the motion
```

A successful `check` is not a claim that the picture looks right. Render it and
look. The agent-oriented version of this loop, including the partial npm check
and how to verify a frame, is in the [AI-agent guide](../agent-guide.md).

Next: [2. The scene model](02-the-scene-model.md).
