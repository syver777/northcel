# northcel-vello — optional Vello renderer for NorthCel

Python binding for the NCIR v2 → Vello/wgpu renderer. It is the **tolerance
tier**: Vello uses analytic area antialiasing, so edge pixels differ from the
Python reference's `aa x aa` subpixel integration. The reference remains the
exact, normative tier.

Install from PyPI as the optional extra (per-platform wheels are built by
`.github/workflows/vello.yml`):

```sh
pip install "northcel[vello]"
```

Build locally for the host platform:

```sh
bash packaging/scripts/build_vello.sh
```

API used by the NorthCel launcher:

```python
import northcel_vello
northcel_vello.render_frame(ncir_bytes, "frame.png")     # -> JSON receipt string
northcel_vello.render_sequence([...], "out_dir")         # -> JSON list
northcel_vello.adapter()                                 # -> adapter info JSON
```

The module never parses `.ncel` and never falls back silently: the CLI raises a
clear install error when `northcel[vello]` is not installed.
