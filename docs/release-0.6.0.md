# Tools 0.6.0 / spec 0.5 — staged Phase 7 release copy

**Not published. Do not use this page as current installation instructions.**
The current published Python/Homebrew/installer release is tools 0.5.0 (spec
0.4); npm is 0.4.0. This checkout is source-only tools 0.6.0 (spec 0.5).

## Publication gate (Phase 7, not this change)

- Publish and verify the intended artifacts through the release process.
- Repin `packaging/install.sh` and the Homebrew formula to the verified 0.6.0
  artifacts and their real checksums in the release change; retain native 0.4.0
  unless a separately verified native release replaces it.
- Verify clean installs report tools 0.6.0 and accept/render the spec-0.5
  conformance file, including the Node-only PARTIAL path and Python bridge.
- Change the unreleased changelog heading to the actual release date.
- Only then replace the published-version paragraphs in the README, docs index,
  reference, package READMEs and agent guide with the copy below. Advertise npm
  0.6.0 only if that channel has actually been published and verified too.

## Ready copy — use only after the gate

> PyPI, Homebrew and the one-line installer install tools **0.6.0**, implementing
> spec **0.5.0-draft** in the labelled Python reference. Homebrew and the
> installer support Linux x86_64 only; macOS uses pipx/pip. The native runtime
> **0.4.0** still implements spec **0.3**. Both launchers route spec 0.4/0.5
> documents, including headerless documents, to Python rather than silently
> passing them to the older native runtime.

> New in **0.6.0**: named groups with pivots, opacity, clipping and optional
> parenting; group transforms, handle-based warp and per-vertex nudge; reusable
> key-plus-delta frames; stable fit ids and `northcel shapes` queries. These are
> general authoring constructs, not subject-specific recipes or presets.

Current instructions remain in the [README](../README.md#install) and
[getting-started guide](guide/01-getting-started.md).
