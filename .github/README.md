# GitHub Actions

`ci.yml` is the CI definition. It is **not active yet**, and that is
deliberate rather than an oversight:

> GitHub refuses to let a repository token create or update files under
> `.github/workflows/` unless that token carries the **`workflow`** scope. The
> credential used for the initial extraction had `repo` scope only, so any file inside
> `.github/workflows/` — whatever its extension — could not be pushed at all, so the
> definition lives one directory up until the scope is granted.

To enable CI, rename the file (and give the pushing credential the `workflow`
scope, or add the file through the GitHub web editor):

```sh
mkdir -p .github/workflows && git mv .github/ci.yml .github/workflows/ci.yml
git commit -m "Enable CI" && git push
```

What the workflow does once enabled:

| Job | What it proves |
| --- | --- |
| `python` (3.10–3.13) | the reference implementation imports, lints and passes its suite on every supported Python |
| `js` (Node 20/22) | the launcher and pre-check tests pass, generated assets are in sync, and `npm pack` ships exactly the expected files |
| `wheel` | the sdist and wheel build, pass `twine check`, install into a clean venv, and a render is honestly labelled `python-reference` |
| `conformance` | reference probes and forward/reverse determinism (native agreement is reported as SKIP, never as a pass, because no bundle ships in CI) |
| `licences` | every licence copy is byte-identical to the root texts |
| `native` (manual) | builds the MoonBit + Bend/HVM2 + GLSL tree, runs the native suite, and compares native frames to the reference |

Nothing in this repository is red because of it: the workflow is inert until it is
in `workflows/`.
