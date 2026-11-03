# NorthCel (`.ncel`) — Official Programming Language Readiness Checklist

| # | Item | Status | Evidence / Notes |
| --- | --- | :---: | --- |
| 1 | **Name & File Extension (`NorthCel`, `.ncel`, `northcel`, `ncel`)** | **Done** | Single config in `packages/northcel/northcel/config.py`; Aztec Noir collision resolved. |
| 2 | **Versioned Language Specification (`0.1.0-draft`)** | **Done** | `docs/northcel/spec/SPEC-0.1.0-draft.md` (normative EBNF, encodings, rendering semantics, tolerances). |
| 3 | **Reference Implementation & CLI (`packages/northcel/`)** | **Done** | Pure-Python + NumPy 4×4 subpixel renderer, lexer/parser with `line:column` diagnostics, validator, formatter. |
| 4 | **Conformance Suite & Automated Tests** | **Done** | `packages/northcel/northcel/conformance/` + 13 unit/golden/error/round-trip/determinism tests in `tests/test_northcel.py`. |
| 5 | **PyPI Package (`northcel` `0.1.0`)** | **Done** | Built, verified in fresh venv, and published to PyPI via `NORTH_NOIR_PYPI_API`. |
| 6 | **npm Package (`northcel` `0.1.0`)** | **Needs Owner Token** | Package built & tested (`packages/northcel/package.json`, `js/index.cjs`, `bin/northcel.js`), `npm pack` tarball ready; VPS has no `NPM_TOKEN` / `~/.npmrc` auth. |
| 7 | **Public Website Documentation (`https://northnoir.com/northcel`)** | **Done** | `src/pages/NorthCelDocs.tsx`, static crawler shell `dist/northcel/index.html`, `public/sitemap.xml`, deployed via guarded flow. |
| 8 | **Editor Support (TextMate Grammar & VS Code Extension)** | **Done (Local) / Marketplace Later** | `packages/northcel/editors/vscode/` (`source.northcel` grammar tested against all samples; publishing to VS Code Marketplace needs a `VSCE_PAT` later). |
| 9 | **Living Tracking Docs (`CHANGELOG.md` & `DECISIONS.md`)** | **Done** | `docs/northcel/CHANGELOG.md` and `docs/northcel/DECISIONS.md`. |
| 10 | **AI-Agent Guide (`agent-guide.md`)** | **Done** | `docs/northcel/agent-guide.md`. |
| 11 | **License (`LICENSE`)** | **Needs Owner Confirmation** | Currently matches `packages/northnoir-cli` (`Proprietary` with free local authoring/rendering rights); owner can switch to MIT/Apache-2.0 if desired for open-source ecosystem adoption. |
| 12 | **Security Policy & Contributing Guide** | **Done** | `docs/northcel/SECURITY.md` and `docs/northcel/CONTRIBUTING.md`. |
| 13 | **Repository Location (Monorepo vs. Standalone Repo)** | **Needs Owner Decision** | Currently lives cleanly at `packages/northcel/` + `docs/northcel/` in `syver777/NorthNoir`. A standalone public repo (`syver777/northcel`) is recommended later for GitHub Linguist & external stars. |
| 14 | **GitHub Linguist & Tree-Sitter Registration** | **Later** | Requirements documented in `docs/northcel/reference.md` (Linguist requires multi-repo public usage in a public repo). |
| 15 | **Interactive Browser Playground** | **Later** | Planned for Phase B using the JS validator + WebGL2/Canvas2D preview on `/northcel`. |
| 16 | **Trademark Check** | **Needs Owner** | Not performed; owner should verify `NorthCel` trademark availability if registering a mark. |
| 17 | **Dedicated Domain** | **Not Needed** | Hosted officially on `https://northnoir.com/northcel`, PyPI, npm, and GitHub per owner decision. |
