# Contributing to NorthCel (`.ncel`)

1. **Specification Changes:** Any change to the lexical grammar, syntactic EBNF, ring-chain encoding, or rendering semantics must first be proposed against `docs/northcel/spec/SPEC-0.2.0-draft.md` (preserve archival specs) and recorded in `docs/northcel/DECISIONS.md` and `docs/northcel/CHANGELOG.md`.
2. **Determinism Requirement:** Every PR touching `packages/northcel/northcel/renderer.py` must pass the out-of-order determinism test (`TestDeterminismAndV01Features.test_out_of_order_film_determinism`) and the conformance suite (`TestConformanceAndGoldenShower.test_conformance_suite`).
3. **Running Tests Locally:**
   ```sh
    PYTHONPATH=packages/northcel python3 -m unittest discover -s packages/northcel/tests -v
    ```
   ```sh
   npm test --prefix packages/northcel
   python3 packages/northcel/scripts/sync-assets.py --check
   ```
4. **Generated npm Assets:** Edit the compact marked section of
   `docs/northcel/agent-guide.md`, not its packaged copy. Run
   `python3 packages/northcel/scripts/sync-assets.py` to regenerate the guide and
   structural rule metadata. npm runtime remains zero-dependency/Node-only;
   Python is used only by maintainers to generate/check release assets.
