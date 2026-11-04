# Security policy

## Execution model

A `.ncel` file is **data and pure arithmetic**, not a script:

- It cannot import modules, read or write files, open sockets, or run commands.
- Expressions are pure arithmetic (`+`, `-`, `*`, `/`) and bounded functions
  (`lerp`, `sin`, `cos`, `step`).
- Canvas dimensions are bounded (`1..8192`) and the `antialias_grid` is restricted
  to `(1, 2, 4, 8)`, which bounds memory per frame.
- The native runtime receives a binary IR from its own MoonBit stage; it does not
  execute user text as code and never shells out to user-controlled arguments.

NorthCel does **not** claim to be a sandbox for untrusted *implementations*. A
third-party renderer that reads `.ncel` is responsible for its own bounds checking;
the conformance suite defines what a correct renderer must accept and reject.

## Supported versions

Security fixes land on the latest minor release. The `0.1.x` line is archival.

| Version | Supported |
| --- | --- |
| 0.3.x | yes |
| 0.2.x | critical fixes only |
| 0.1.x | no |

## Reporting a vulnerability

Report privately to `contact@northnoir.com` with `[NorthCel Security]` in the
subject line. Please include the version (`northcel --version`), the platform
(`northcel doctor --json`), and a minimal `.ncel` file or command line.

- Do not open a public issue for a vulnerability.
- We aim to acknowledge within 3 working days and to ship a fix or a mitigation
  plan within 30 days.
- Please give us a reasonable window before public disclosure; we will credit you
  in the changelog unless you prefer otherwise.

## What is in scope

- Crashes, hangs or unbounded memory use caused by a `.ncel` file (parser, ring
  decoder, renderer, native IR reader).
- Any way to make the CLI execute code, read files or reach the network through
  `.ncel` input.
- Supply-chain issues in the published packages: `northcel` (PyPI),
  `northcel-native` (PyPI), `northcel` (npm), `northcel-linux-x64` (npm). Every
  bundled native file is sha256-pinned in `bundle-manifest.json` and verified at
  `northcel doctor` time.

## What is out of scope

- A drawing that looks wrong. That is a bug report, not a vulnerability.
- Third-party mirrors of the packages.
- Denial of service by rendering a deliberately huge but legal canvas on your own
  machine.
