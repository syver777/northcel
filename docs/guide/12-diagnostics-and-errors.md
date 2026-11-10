# 12. Diagnostics and errors

NorthCel reports problems at parse time, at validation time, or at render time.
The first two are **diagnostics** with a `line:column`; they are the ones you can
fix from the message alone. Render-time failures are much rarer and usually mean
the file is not the problem.

## The shape of a diagnostic

```text
path.ncel:5:20: error: Unknown function 'oklch'
            │  │   │      └─ what is wrong
            │  │   └─ error or warning
            │  └─ column (1-based)
            └─ line (1-based)
```

`check` prints diagnostics to stderr and exits `1` if there is at least one
error. With `--json` the same strings appear in `errors` and `warnings`, and the
process exit code is still the reliable signal:

```console
$ northcel check file.ncel --json
$ echo $?
0
```

`ok: true` means *this validator found no error*. It is not a claim that the
picture looks right.

## Errors versus warnings

| Level | Blocks rendering? | Example |
| --- | --- | --- |
| `error` | yes | malformed ring, undefined palette name, out-of-range size |
| `warning` | no | `rings: 2` declared over a payload that decodes to 3 rings |

Warnings are printed by `check` (and included in `--json`). They are still worth
reading: the declared ring count is documentation, and drift means the file and
its comment disagree.

## Three ways to run a check

| Command | What runs | Honest label |
| --- | --- | --- |
| `northcel check f.ncel` (pip / brew / native Linux) | native checker when available, else the reference | `validator: "native"` or `"python"` |
| `npx northcel check f.ncel` with Python on PATH | the same reference through the bridge | `validator: "python"` |
| `npx northcel check f.ncel --require-full` with no Python | a structural JS pre-check only | `partial: true`, `validator: "js"`, exit `2` |

Exit `2` with `--require-full` means *no full validator was available*, not
"clean". Exit `1` is a detected problem. Never treat a partial check as full
validation; the contract is spelled out in
[the format reference](../reference.md#validation-contract).

## A real diagnostic and its fix

The colour below is a perfectly good CSS colour and a perfectly bad NorthCel
attribute: only `#hex`, `rgb(...)`, `tone:` and `$palette` names are colours.

<!-- expect-error: 5:20: error: Unknown function 'oklch' -->
```text
northcel "0.2.0-draft"

scene DiagnosticBad(width: 360, height: 210) {
  paper { color: #F6F1E7 }
  layer sky(color: oklch(0.7, 0.08, 220), rings: 1) { "0,0 1440,0 0,840 -1440,0" }
}
```

```console
$ northcel check broken.ncel
broken.ncel:5:20: error: Unknown function 'oklch'
```

Spec 0.2 provides `lerp`, `sin`, `cos` and `step`; spec 0.3 adds `ease` and
`smoothstep`. The fix is to use an RGB
literal (or declare `oklch`'s nearest sRGB value in the palette):

<!-- render: assets/guide/12-diagnostic-fixed.png -->
```ncel
northcel "0.2.0-draft"

scene DiagnosticFixed(width: 360, height: 210, fps: 12, precision: 0.25px, seed: 2) {
  palette { sky: rgb(122, 158, 182) }
  paper { color: #F6F1E7, antialias_grid: 4 }
  layer sky(color: $sky, rings: 1) { "0,0 1440,0 0,840 -1440,0" }
}
```

![The fixed file renders: a plain sky-blue field](../assets/guide/12-diagnostic-fixed.png)

## The ten messages you will actually meet

| Message (after `line:column: error:`) | Cause | Fix |
| --- | --- | --- |
| `Unknown scene statement 'X'` / `Unknown film statement 'X'` | statement in the wrong container, or `frames:` in the body | move it to the header, or use the right statement |
| `Expected 'scene' or 'film' declaration, got 'X'` | missing root container | wrap statements in `scene`/`film` |
| `Unclosed 'scene' block` (or `film`, `def`, `frame`) | missing `}` | close it; the position is where the block started |
| `Undefined palette color '$x'` | reference before declaration | declare it earlier in the same body |
| `Layer 'x' has invalid ring payload: ...` | malformed ring | see page [10](10-contour-encodings.md) |
| `Use of undefined def block 'X'` | use without def | declare the def in the same body |
| `Frame override index N out of range [0..M]` | override beyond `frames` | fix `frames` or the index |
| `paper.antialias_grid must be 1, 2, 4, or 8` | unsupported grid | pick one |
| `Canvas dimensions WxH out of valid range [1..8192]` | size | resize |
| `Stroke 'x' requires at least 2 control points` | one-point ink | add a point |

The complete, generated list — every message the parser, validator and ring
decoder can emit, with a reproducing file and the fix — is
[Common errors](../errors.md). It is generated from the source and checked by
CI, so it cannot drift from the code.

## What a check cannot tell you

- whether the composition reads;
- whether the motion is smooth or the timing right;
- whether the ink is too thick;
- whether a shape is where you meant it (the numbers are valid, the picture is
  wrong).

Those need `render` and eyes. The look-and-fix loop is in the
[agent guide](../agent-guide.md).

Next: [13. Performance and limits](13-performance-and-limits.md).
