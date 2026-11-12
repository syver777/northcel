# T1 — palette gaps at fit time

## What changed

- Added `northcel.fitting.palette_gaps(image, palette, threshold=60.0, min_area=150, limit=20)`.
  It reports 8-connected regions whose pixels are farther than `threshold` from
  every palette colour, after two 3×3 binary openings remove anti-aliased edges.
  Regions are largest first, with median RGB, nearest palette colour, distance,
  area and half-open source-pixel bbox; `suggested` merges medians closer than
  the threshold transitively to the largest region in each group.
- `northcel fit --palette FILE` now writes `palette_gaps` into the receipt and
  prints one stderr line when `count > 0`. The same happens in `--stacked` and
  `--figure` modes. `--palette-threshold` and `--palette-min-area` set the
  defaults (60 and 150).
- Without `--palette`, no key is added and no stderr line is printed.
- The fitted `.ncel` source is untouched: the report is computed after fitting and
  never feeds back into quantisation, tracing or stacking.

Implementation commit: `71909c0` (`python: report palette gaps during fit`).
Tests commit: `bf2ad1a`. Docs/changelog commit: `496966e`.

## Commands used

Environment:

```console
$ export PATH=$HOME/its-fix/env/bin:$PATH
$ cd /home/dev/its-fix/tn
```

Baseline suite, before any change:

```console
$ PYTHONPATH=python python -m pytest python/tests -q
# 272 passed, 6 skipped, 73 subtests passed in 8.62s
```

After the change:

```console
$ PYTHONPATH=python python -m pytest python/tests -q
# 279 passed, 6 skipped, 73 subtests passed in 9.58s
$ PYTHONPATH=python python -m pytest python/tests/test_palette_gaps.py -q
# 7 passed in 1.26s
```

There were no pre-existing test failures to list. `ruff check` on the changed
Python files also passes.

## Tests 1–2 on the real drawing

Inputs (read-only checkout):

- `/home/dev/its-fix/final/sources/cels/f0062.jpg` — 1536×1024
- `/home/dev/its-fix/final/process/polish/palette.json` — the 11 colours

Test 1, `palette_gaps` with defaults (`threshold=60`, `min_area=150`):

```json
{
  "threshold": 60.0,
  "min_area_px2": 150,
  "count": 1,
  "regions": [
    {
      "rgb": [253, 138, 129],
      "nearest": [252, 200, 158],
      "distance": 68.45436436049933,
      "area_px2": 995,
      "bbox": [698, 533, 745, 565]
    }
  ],
  "suggested": [[253, 138, 129]]
}
```

The median `[253, 138, 129]` is 3.74 from `(250, 140, 130)`, and the bbox is in
the open-mouth area. The suggested colour is `[253, 138, 129]`, also within 25 of
the expected pink.

Test 2, same image and palette plus `[250, 140, 130]`: `count` is `0`,
`regions` and `suggested` are empty lists.

## Fitted output is unchanged

Before making any edit, on the same working tree, I fitted `f0062.jpg` with the
palette, saved the `.ncel`, then repeated the same commands after the change:

```console
$ PYTHONPATH=python python -m northcel fit \
    /home/dev/its-fix/final/sources/cels/f0062.jpg \
    -o OUT.ncel --palette /home/dev/its-fix/final/process/polish/palette.json \
    --receipt OUT.json
$ PYTHONPATH=python python -m northcel fit \
    /home/dev/its-fix/final/sources/cels/f0062.jpg \
    -o OUT.ncel --stacked --palette /home/dev/its-fix/final/process/polish/palette.json \
    --receipt OUT.json
$ PYTHONPATH=python python -m northcel fit \
    /home/dev/its-fix/final/sources/cels/f0062.jpg \
    -o OUT.ncel --receipt OUT.json
```

SHA-256 of the `.ncel` before and after (identical):

| Mode | SHA-256 |
| --- | --- |
| planar, palette | `0ef1d5ce5ec83db81b4081da9cfe1325ecfc2b9b020f47cc5a27169c323c8d02` |
| stacked, palette | `59c4112e5e071831b803f1488621ff9e575b44af53afa2da41cbe428b5fc9a17` |
| planar, no palette | `ab279ffa9068a5a591904931f2a44d8d00879828ef6da01e6055d1a102a90229` |

With the palette, both planar and stacked receipts contain `palette_gaps` and
both print exactly one stderr line:

```text
northcel fit: palette_gaps: 1 region(s) >= 150 px^2 have no palette colour within 60; suggested #FD8A81
```

`--stacked --figure` on `f0062.jpg` also reports the same one region. Without a
palette, the receipt has no `palette_gaps` key and stderr is empty (0 bytes).

The two new options were also exercised on the real image:

```console
$ ... --palette-threshold 40 --palette-min-area 500 ...
# threshold 40.0, min_area_px2 500.0, count 1, rgb [252, 139, 130], area 1364
```

## Other tests

- Synthetic palette-coloured rectangle with a 4× supersampled anti-aliased black
  outline: `count == 0` for outline widths 1–4 px.
- Synthetic off-palette rectangle through `fit`: receipt has the gap,
  `.ncel` equals the direct `fit_image` output byte-for-byte, one stderr line.
- `--stacked` and `--stacked --figure` synthetic runs both carry the gap report.
- A no-palette synthetic fit has no key and no stderr.
- Suggestion merging was checked with three chained medians: the two 40-apart
  neighbours and the 80-apart end merge transitively to the largest colour under
  threshold 60.
- The pure-NumPy connected-component fallback was exercised on `f0062.jpg` with
  `cv2` blocked; it produced the same region numbers as the OpenCV path.

## Not verified

- I did not run the native or JavaScript test suites; this change touches only the
  Python fitter and its docs, and the renderer/native/spec trees were not edited.
- I did not run `docs/scripts/check_docs.py` (the Python package suite and ruff
  were run). No docs links or `ncel` fences were added or changed.
- The real-image tests skip when `~/its-fix/final` is absent, as the repository
  has no fixture-copy convention for that checkout.
- I did not test other Python/dependency versions beyond this environment
  (Python 3.12.3, numpy 2.5.3, Pillow 12.3.0, OpenCV 5.0.0, scikit-image 0.26.0).
- Nothing was pushed or published, and no package version/tag was changed.
