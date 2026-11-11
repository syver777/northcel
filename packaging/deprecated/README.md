# Deprecated names — alias packages

These packages exist so that an existing install or a saved `pip install ncel` /
`npm i @ncel/linux-x64` keeps working after the rename. **They contain no code and
no binaries: they only depend on the real packages.**

| Deprecated | Type | Now depends on | What a user should run |
| --- | --- | --- | --- |
| `ncel` | PyPI | `northcel==0.7.1` | `pip install northcel` |
| `ncel-native` | PyPI | `northcel-native==0.4.0` (Linux x86_64) | `pip install northcel` |
| `@ncel/linux-x64` | npm | `northcel-linux-x64@0.4.0` | `npm install -g northcel` |

They are built and published **after** the real packages exist, and each publish
is followed by a deprecation notice:

```sh
# PyPI
python -m twine upload dist/deprecated/*
# npm (sets the deprecated flag shown to every installer)
npm deprecate "@ncel/linux-x64@0.2.1" "NorthCel is one package now: npm install -g northcel"
```

There is deliberately **no** npm `ncel` alias: npm rejected the bare name as too
similar to other packages, and `ncel` remains available as a *command* inside
`northcel`.

`@ncel/cli` was never published and is not part of this plan.
