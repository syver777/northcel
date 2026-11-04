# ncel (deprecated alias)

**NorthCel is one package now: install `northcel`.**

```sh
pip install northcel
```

This package exists only so that an existing `pip install ncel` keeps working. It
contains no code and no binaries; it depends on `northcel==0.3.1`, which provides
both the `northcel` command and the `ncel` short alias.

- Source, docs and issues: <https://github.com/syver777/northcel>
- Why the rename: one install name everywhere (`northcel`); `ncel` is a command
  alias, not a package.

Licence: MIT OR Apache-2.0.
