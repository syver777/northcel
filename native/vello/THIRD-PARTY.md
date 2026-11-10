# Dependency licence inventory

Read-only inventory from the locked Linux x86_64 dependency graph:

```sh
cargo metadata --locked --format-version 1 --filter-platform x86_64-unknown-linux-gnu
```

There are 97 external packages (98 including this prototype). Expressions below
are copied from Cargo metadata, including legacy slash notation. They cover
resolved packages, not a claim that every package is linked into the binary.
Other targets/features can resolve additional packages in `Cargo.lock`.

The direct dependencies are Vello 0.11.0, wgpu 30.0.1, pollster 1.0.1, serde
1.0.229, serde_json 1.0.154 and png 0.18.1. These are permissively dual-licensed
MIT/Apache-2.0. The full graph also has Zlib-only and ISC components and a
Unicode-3.0 notice obligation. No GPL/AGPL dependency appears in this graph.

| Declared licence expression | Packages and pinned versions |
| --- | --- |
| `(MIT OR Apache-2.0) AND Unicode-3.0` | unicode-ident 1.0.27 |
| `0BSD OR MIT OR Apache-2.0` | adler2 2.0.1 |
| `Apache-2.0` | codespan-reporting 0.13.1, spirv 0.4.0+sdk-1.4.341.0 |
| `Apache-2.0 OR MIT` | autocfg 1.5.1, bit-set 0.10.0, bit-vec 0.9.1, color 0.3.3, equivalent 1.0.3, indexmap 2.14.2, kurbo 0.13.1, linebender_resource_handle 0.1.1, peniko 0.6.1, vello 0.11.0, vello_encoding 0.11.0, vello_shaders 0.11.0 |
| `Apache-2.0/MIT` | pollster 1.0.1, rustc-hash 1.1.0 |
| `BSD-2-Clause OR Apache-2.0 OR MIT` | zerocopy 0.8.63, zerocopy-derive 0.8.63 |
| `ISC` | libloading 0.8.9 |
| `MIT` | cfg_aliases 0.2.2, dlib 0.5.3, libm 0.2.16, ordered-float 5.5.1, simd-adler32 0.3.10, wayland-sys 0.31.11, zmij 1.0.23 |
| `MIT OR Apache-2.0` | allocator-api2 0.2.21, arrayvec 0.7.8, ash 0.38.0+1.3.281, bitflags 2.13.2, cfg-if 1.0.5, crc32fast 1.5.4, document-features 0.2.12, euclid 0.22.14, fdeflate 0.3.7, flate2 1.1.11, font-types 0.12.7, futures-core 0.3.34, futures-intrusive 0.5.0, gpu-allocator 0.28.0, half 2.7.1, hashbrown 0.16.1, hashbrown 0.17.1, itoa 1.0.19, libc 0.2.191, litrs 1.0.1, lock_api 0.4.14, log 0.4.35, naga 30.0.1, naga-types 30.0.1, num-traits 0.2.19, once_cell 1.21.4, parking_lot 0.12.5, parking_lot_core 0.9.12, pkg-config 0.3.34, png 0.18.1, polycool 0.4.0, presser 0.3.1, proc-macro2 1.0.107, profiling 1.0.18, quote 1.0.47, read-fonts 0.41.0, renderdoc-sys 1.1.0, scopeguard 1.2.0, serde 1.0.229, serde_core 1.0.229, serde_derive 1.0.229, serde_json 1.0.154, skrifa 0.44.0, smallvec 1.16.5, static_assertions 1.1.0, syn 2.0.119, syn 3.0.10, thiserror 2.0.21, thiserror-impl 2.0.21, unicode-width 0.2.3, wgpu 30.0.1, wgpu-core 30.0.1, wgpu-core-deps-windows-linux-android 30.0.1, wgpu-hal 30.0.1, wgpu-naga-bridge 30.0.1, wgpu-types 30.0.1 |
| `MIT OR Apache-2.0 OR Zlib` | glow 0.17.0, raw-window-handle 0.6.2 |
| `MIT OR Zlib OR Apache-2.0` | miniz_oxide 0.8.9, miniz_oxide 0.9.1 |
| `MIT/Apache-2.0` | guillotiere 0.7.0, khronos-egl 6.0.0, svg_fmt 0.4.5 |
| `Unlicense OR MIT` | memchr 2.8.3, termcolor 1.4.1 |
| `Zlib` | foldhash 0.2.0, zlib-rs 0.6.8 |
| `Zlib OR Apache-2.0 OR MIT` | bytemuck 1.25.2, bytemuck_derive 1.12.1 |

No dependency source, compiled runtime, model, font, or external image asset is
vendored here. Cargo fetches dependencies with the checksums in `Cargo.lock`.
The generated source/geometry fixture belongs to this prototype, rather than
being a downloaded illustration. The package inherits the repository's
MIT/Apache-2.0 licensing (`../../LICENSE-MIT`, `../../LICENSE-APACHE`).

Python NumPy/Pillow and the Ubuntu Mesa/LLVM Vulkan runtime are external test
and runtime prerequisites, not Cargo dependencies or redistributed artifacts.
Mesa is a collection of components with differing permissive notices; this
inventory does not purport to license that external distribution.

This file is not a replacement for upstream licence/copyright texts. Before
distributing a binary, collect all applicable notices (especially Apache NOTICE,
Unicode, ISC, and Zlib notices), honour the chosen licence alternatives, and
review the exact shipped artifacts. No publication/distribution is performed
in Phase 4.
