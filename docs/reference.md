# Format & tooling reference: CLI, check contract, editors

This page is the short lookup. The language itself is taught in the
[writing guide](guide/README.md); the normative grammar is
[SPEC-0.2.0-draft](spec/SPEC-0.2.0-draft.md).

## CLI (`northcel` / `ncel`)

| Command | What it does |
| --- | --- |
| `northcel doctor [--json]` | every stage, version, shader hash and the platform verdict; exit `0` only when native is usable, `3` with the reason otherwise |
| `northcel verify [--json]` | renders the pinned conformance frame and a 6-frame film twice, compares hashes |
| `northcel check FILE [--json] [--require-full]` | parse + validate; exit `1` on an error |
| `northcel info FILE [--json]` | metadata: bytes, kind, size, frames, fps, layers, rings, vertices |
| `northcel render FILE [-o OUT.png] [--frame N] [--seed N] [--json]` | one frame to PNG |
| `northcel film FILE -o OUTDIR [--frames 0..N] [--mp4 OUT.mp4] [--json]` | frame sequence and optional MP4 |
| `northcel fmt FILE [-w] [--check]` | canonical formatting (reference only) |
| `northcel guide` | the compact offline agent guide |
| `northcel toolchain <status\|install>` | the optional MoonBit compiler for rebuilding the native tree |

Global `--no-native` forces the labelled Python reference path. On a platform
without a native bundle, the launcher prints one line and labels the receipt
`"renderer": "python-reference"`; it never claims a native render.

## Validation contract

**Tools 0.3.1, spec 0.2.0-draft.** The `northcel` distribution is the reference
parser, validator, formatter and CPU renderer *and* the launcher that runs the
native runtime. The npm `northcel` package runs the same launcher and adds a
zero-dependency structural JS pre-check, the embedded guide and a Python bridge;
it has no JS formatter or renderer.

The npm wrapper probes `python3`, then `python`, on PATH for `northcel.cli`, then
looks for a Python-shebang `northcel`/`ncel` entrypoint on PATH (including pipx
installs). It skips its own npm entrypoints to prevent recursion. Once a probe
succeeds it delegates, preserving stdout, stderr and the exit code; it never
retries a failing Python check in JS. A terminated/unlaunchable Python process is
nonzero. `--require-full` is consumed by the bridge for compatibility with older
full Python CLIs. `guide` is always the npm-bundled guide. `--version` reports the
launcher version and the native-runtime state. The npm package does not require
Python for guide/doctor/version/help, and `check` falls back to the partial
pre-check when neither the native bundle nor Python is available.

| Path/result | Text / JSON | Exit |
| --- | --- | ---: |
| Python/native valid | `OK (NorthCel <spec>)`; `ok: true, partial: false` | 0 |
| Invalid | Exact parser/semantic diagnostics; `ok: false` | 1 |
| JS clean | `PARTIAL (JS pre-check only; no pre-check errors found — install \`pipx install northcel\` for full validation)` | 0 |
| JS detected error or unreadable file | `PARTIAL ... errors found` plus line:column diagnostics | 1 |
| JS clean with `--require-full` | The partial result plus a full-validator-unavailable diagnostic | 2 |
| Invalid check arguments / unsupported flags | Usage (not a validation result) | 2 |
| Node-only `render` / `film` | Install-Python guidance, no render claimed | 1 |

Every JS API result and `check --json` result contains `partial: true`,
`validator: "js"`, `reason`, `next`, `ok`, `errors`, `warnings`. CLI JSON
additionally has `file`, `spec_version`, `exit_code` (the API retains
`specVersion`). `ok` means *no errors found by this validator*, not full validity.
Thus a clean `--require-full --json` without Python has
`ok: true, partial: true, exit_code: 2`. Check the process exit code **and** the
partial marker; never treat `ok` alone as full success.

### JS pre-check coverage (not full grammar/conformance)

| Case | JS pre-check | Python/reference or render still needed |
|---|---|---|
| Root, version, trailing tokens; balanced braces/quotes/parentheses; comments | Error on detected structural mistakes | Does not evaluate the document |
| Unknown statements in scene/film/frame/def | Error; allowed sets generated from the reference parser | Reference parser remains authority |
| `frames:` in body, malformed palette/cel/stroke/ribbon/def/use headers | Error with line:column | Attribute meaning, function arity, expression evaluation |
| Ring characters, integer pairs, Base-63 odd tail, fewer than 3 vertices | Error | Does not judge geometry or artistic suitability |
| Duplicate primitive/layer names in one block | **Warning** (replacement is legal) | Expanded def/use collisions and paint order need inspection |
| Unknown `$palette` names | Error; declaration order and frame-local scope followed | Palette value types/colour range |
| Width/height/fps/frame ranges, agents, stroke widths, undefined def | Not checked | Python semantic validator |
| Variable binding, time-dependent arithmetic, rendered quality | Not checked | Real renders and visual review |

The structural scanner is intentionally not advertised as a complete JS parser.
An invalid file can pass the pre-check (e.g. `film F(fps: 0) { use Missing }`).
Generated `js/rules.json` takes version constants, statement sets and the Base-63
alphabet from Python. The compact packaged guide is extracted verbatim from
marked text in [agent-guide.md](agent-guide.md); `scripts/sync-assets.py --check`
and package tests prevent stale copies at release time. Run
`python3 js/northcel/scripts/sync-assets.py` after editing the marked section.

## Editor support, GitHub Linguist and Tree-sitter

- **VS Code / TextMate:** a highlighting grammar (`source.northcel`, not a
  validator) and a VS Code extension manifest live in `editors/vscode/`.
- **GitHub Linguist requirements:** wide public usage across multiple
  repositories; then an entry in `languages.yml` mapping `.ncel` to
  `tm_scope: source.northcel`, `type: programming`, `color: "#8E24AA"`, pointing
  at the grammar repository.
- **Tree-sitter:** a `grammar.js` mirroring the EBNF in the spec (`scene`/`film`,
  `paper`, `def`/`use`, `layer`/`bend_swarm`/`stroke`/`ribbon`, `Expr`).
