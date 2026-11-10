# Tools 0.7.0 / spec 0.6 — staged Phase 7 release copy

**Staged copy.** The current published Python/Homebrew/installer release is
tools 0.6.0 (spec 0.5); npm is 0.4.0. This checkout is tools 0.7.0 (spec 0.6).

## Publication gate (Phase 7, not this change)

- Publish and verify the intended artifacts through the release process.
- Repin `packaging/install.sh` and the Homebrew formula to the verified 0.7.0
  artifacts and their real checksums in the release change; retain native 0.4.0
  unless a separately verified native release replaces it.
- Publish the platform wheels of the optional `northcel-vello` package
  (`northcel[vello]`); the tolerance tier must remain optional.
- Verify clean installs report tools 0.7.0 and accept/render the spec-0.6
  conformance file, including the Node-only PARTIAL path and Python bridge.
- Change the unreleased changelog heading to the actual release date.
- Only then replace the published-version paragraphs in the README, docs index,
  reference, package READMEs and agent guide with the copy below. Advertise npm
  0.6.0 only if that channel has actually been published and verified too.

## Ready copy — use only after the gate

> PyPI, Homebrew and the one-line installer install tools **0.7.0**, implementing
> spec **0.6.0-draft** in the labelled Python reference. Homebrew and the
> installer support Linux x86_64 only; macOS uses pipx/pip. The native runtime
> **0.4.0** still implements spec **0.3**. Both launchers route spec 0.4/0.5/0.6
> documents, including headerless documents, to Python rather than silently
> passing them to the older native runtime.

> New in **0.7.0**: `warp(mode: arap)` as-rigid-as-possible deformation; NCIR v2
> and the optional Vello tolerance renderer (`northcel render|film --renderer
> vello`, `northcel[vello]`); the `northcel[perceive]` extra; and the 0.6
> specification. The Python reference remains the exact tier.

Current instructions remain in the [README](../README.md#install) and
[getting-started guide](guide/01-getting-started.md).
