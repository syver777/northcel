# NorthCel (`.ncel`) — Official Programming Language Readiness Checklist

| # | Item | Status | Evidence / Notes |
| --- | --- | :---: | --- |
| 1 | **Name & File Extension (`NorthCel`, `.ncel`, `northcel`, `ncel`)** | **Done** | Single config in `python/northcel/config.py`; Aztec Noir collision resolved. |
| 2 | **Versioned Language Specification (`0.2.0-draft`)** | **Done** | Unchanged in tools 0.3.1; `0.1.0-draft` backward compatibility retained. |
| 3 | **Reference Implementation & CLI (`python/`)** | **Done** | Pure-Python + NumPy 4×4 subpixel renderer, lexer/parser with `line:column` diagnostics, validator, formatter. |
| 4 | **Conformance Suite & Automated Tests** | **Done** | 18 Python + 55 Node tests; 3 conformance cases/10 exact pixel probes, 2 real GLSL golden frames (0.0115 MAE, 0.05 gate), out-of-order determinism, native-vs-reference agreement 0 differing pixels on all 3 cases, every checked-in example plus broken variants, generated-asset freshness. `tests/conformance.py` runs it in CI. |
| 5 | **PyPI Package (`northcel`)** | **Done — 0.3.1 published** | `pip install northcel` installs one distribution (reference + launcher, scripts `northcel` and `ncel`) that depends on the `northcel-native` 0.3.1 platform wheel. Published 2026-11-04 and verified from a fresh venv against the public index: `doctor` exit 0 with all native stages, `verify` 5/5, a native render matching the pinned conformance hash. `ncel`/`ncel-native` are deprecated aliases at 0.3.1. |
| 6 | **npm Package (`northcel`)** | **Done — 0.3.1 published** | npm carries `northcel@0.3.1` and the platform bundle `northcel-linux-x64@0.3.1`: one merged launcher (`northcel` with the `ncel` alias), the EGL discovery fix and the dual licence. Published 2026-11-04 and installed from the public registry; `@ncel/linux-x64@0.2.1` remains as a deprecated alias. |
| 7 | **Public Website Documentation (`https://northnoir.com/northcel`)** | **Done** | `src/pages/NorthCelDocs.tsx`, static crawler shell `dist/northcel/index.html`, `public/sitemap.xml`, deployed via guarded flow. |
| 8 | **Editor Support (TextMate Grammar & VS Code Extension)** | **Done (Local) / Marketplace Later** | `editors/vscode/` (`source.northcel` grammar tested against all samples; publishing to VS Code Marketplace needs a `VSCE_PAT` later). |
| 9 | **Living Tracking Docs (`CHANGELOG.md` & `DECISIONS.md`)** | **Done** | `CHANGELOG.md` (repository root) and `docs/DECISIONS.md`. |
| 10 | **AI-Agent Guide (`agent-guide.md`)** | **Done** | Canonical compact section generates packaged offline `northcel guide`; partial/full contract and local Python/North Noir render paths included. |
| 11 | **License** | **Done — dual MIT OR Apache-2.0** | Owner decision 2026-11-04: the language is open source under dual MIT OR Apache-2.0 (`LICENSE-MIT`, `LICENSE-APACHE`). The owner may still choose a single licence; NorthNoir itself is not relicensed. |
| 12 | **Security Policy, Contributing Guide & Code of Conduct** | **Done** | `SECURITY.md`, `CONTRIBUTING.md` and `CODE_OF_CONDUCT.md` in the repository root. |
| 13 | **Repository Location (Monorepo vs. Standalone Repo)** | **Done — standalone public repo** | <https://github.com/syver777/northcel>, extracted from NorthNoir with the history of all four trees preserved, MIT OR Apache-2.0, CI, releases. NorthNoir keeps only a pointer (`NORTHCEL.md`). |
| 14 | **GitHub Linguist & Tree-Sitter Registration** | **Later** | Requirements documented in `docs/reference.md`. Linguist needs sustained multi-repo public usage; the public repository now exists, so this can be proposed. |
| 15 | **Interactive Browser Playground** | **Later** | Planned for Phase B using the JS validator + WebGL2/Canvas2D preview on `/northcel`. |
| 16 | **Trademark Check** | **Needs Owner** | Not performed; owner should verify `NorthCel` trademark availability if registering a mark. |
| 17 | **Dedicated Domain** | **Not Needed** | Hosted officially on `https://northnoir.com/northcel`, PyPI, npm, and GitHub per owner decision. |
