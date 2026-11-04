# GitHub Actions

CI lives at **`.github/workflows/ci.yml`** and runs on every push to `main`, on every
pull request, and on demand (`workflow_dispatch`) from the Actions tab. The badge in
the top-level README points at it.

| Job | Runner | What it proves |
| --- | --- | --- |
| `python 3.10` / `3.11` / `3.12` / `3.13` | ubuntu-latest | the reference implementation imports, lints (3.12 only: ruff) and passes its suite on every supported Python |
| `node 20` / `node 22` | ubuntu-latest | generated assets are in sync, the launcher/pre-check tests pass — including the two that spawn the *real* Python reference, so numpy and Pillow are installed for them — and `npm pack` ships exactly the expected files |
| `wheel build + install smoke test` | ubuntu-latest | sdist + wheel build, `twine check`, install into a clean venv, and `northcel`/`ncel`/`check`/`info`/`render` behave; the render receipt says `python-reference` / `native: false` |
| `conformance (both implementations)` | ubuntu-latest | reference probes and forward/reverse determinism; native agreement is reported as **SKIP**, never as a pass, because no native bundle ships in CI |
| `licence copies in sync` | ubuntu-latest | every `LICENSE-MIT`/`LICENSE-APACHE` copy is byte-identical to the root texts |
| `docs (snippets render, images match, errors reproduce)` | ubuntu-latest | every guide snippet checks and renders to the committed pixels, every `examples/patterns/*.ncel` renders and its contact sheet matches, every diagnostic in `docs/errors.md` is regenerated from the source, and every relative link/image resolves |
| `native build + conformance (manual)` | ubuntu-24.04 | provisions the 101 MB MoonBit toolchain, builds the C GL host with Mesa/EGL, runs `native/tests/run-tests.sh` and compares native frames to the reference |

## Running the heavy native job

It only runs when you ask for it, because it downloads a large toolchain and builds C:

```sh
gh workflow run ci.yml                       # Actions → CI → Run workflow also works
gh run watch "$(gh run list --workflow ci.yml --limit 1 --json databaseId -q '.[0].databaseId')"
```

Repeat a single job locally instead when you only changed the Python or the JS side:

```sh
make test        # Python reference suite + JS tests + conformance
make lint        # ruff, node --check, generated-asset check, licence copies
```
