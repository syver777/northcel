# NorthCel (`.ncel`) — Official Programming Language Readiness Checklist

| # | Item | Status | Evidence / Notes |
| --- | --- | :---: | --- |
| 1 | **Name & File Extension (`NorthCel`, `.ncel`, `northcel`, `ncel`)** | **Done** | Single config in `python/northcel/config.py`; Aztec Noir collision resolved. |
| 2 | **Versioned Language Specification (`0.2.0-draft`)** | **Done** | Unchanged in tools 0.2.1; `0.1.0-draft` backward compatibility retained. |
| 3 | **Reference Implementation & CLI (`python/`)** | **Done** | Pure-Python + NumPy 4×4 subpixel renderer, lexer/parser with `line:column` diagnostics, validator, formatter. |
| 4 | **Conformance Suite & Automated Tests** | **Done** | 18 Python + 51 Node tests; 3 conformance cases/10 exact pixel probes, 2 real GLSL golden frames, out-of-order determinism, all 9 checked-in examples plus broken variants and generated-asset freshness. Two Node-only trials later fully validated/rendered. |
| 5 | **PyPI Package (`northcel` `0.2.1`)** | **Published & verified** | 2026-11-04: one upload; registry and downloaded wheel/sdist hashes verified, fresh official-index install and both 36-frame trial renders verified. Receipt in `work/prompts/northcel-021-report.md`. |
| 6 | **npm Package (`northcel` `0.2.1`)** | **Planner publishes with owner** | Verified tarball only; worker must not run npm publish. npm 0.2.0 is the prior published release. |
| 7 | **Public Website Documentation (`https://northnoir.com/northcel`)** | **Done** | `src/pages/NorthCelDocs.tsx`, static crawler shell `dist/northcel/index.html`, `public/sitemap.xml`, deployed via guarded flow. |
| 8 | **Editor Support (TextMate Grammar & VS Code Extension)** | **Done (Local) / Marketplace Later** | `editors/vscode/` (`source.northcel` grammar tested against all samples; publishing to VS Code Marketplace needs a `VSCE_PAT` later). |
| 9 | **Living Tracking Docs (`CHANGELOG.md` & `DECISIONS.md`)** | **Done** | `docs/CHANGELOG.md` and `docs/DECISIONS.md`. |
| 10 | **AI-Agent Guide (`agent-guide.md`)** | **Done** | Canonical compact section generates packaged offline `northcel guide`; partial/full contract and local Python/North Noir render paths included. |
| 11 | **License (`LICENSE`)** | **Needs Owner Confirmation** | Currently matches `packages/northnoir-cli` (`Proprietary` with free local authoring/rendering rights); owner can switch to MIT/Apache-2.0 if desired for open-source ecosystem adoption. |
| 12 | **Security Policy & Contributing Guide** | **Done** | `docs/SECURITY.md` and `docs/CONTRIBUTING.md`. |
| 13 | **Repository Location (Monorepo vs. Standalone Repo)** | **Needs Owner Decision** | Currently lives cleanly at `python/` + `docs/` in `syver777/NorthNoir`. A standalone public repo (`syver777/northcel`) is recommended later for GitHub Linguist & external stars. |
| 14 | **GitHub Linguist & Tree-Sitter Registration** | **Later** | Requirements documented in `docs/reference.md` (Linguist requires multi-repo public usage in a public repo). |
| 15 | **Interactive Browser Playground** | **Later** | Planned for Phase B using the JS validator + WebGL2/Canvas2D preview on `/northcel`. |
| 16 | **Trademark Check** | **Needs Owner** | Not performed; owner should verify `NorthCel` trademark availability if registering a mark. |
| 17 | **Dedicated Domain** | **Not Needed** | Hosted officially on `https://northnoir.com/northcel`, PyPI, npm, and GitHub per owner decision. |
