# Licence notes

The NorthCel native runtime (`ncel-native`, `ncel-ast` sources, `ncel-gl`, the
GLSL shaders and the test fixtures in this tree) is dual licensed under MIT OR
Apache-2.0, matching this repository's root licence texts. The old proprietary
wording here predated the standalone open-source repository and was stale.

Third-party components:

| Component | Version | Licence | Form |
| --- | --- | --- | --- |
| MoonBit build system + core | moon 0.1.20261102 / moonc 0.10.19+bee578715 | build system/core Apache-2.0; compiler under upstream toolchain terms | build-time download only; the compiler is not redistributed; `ncel-ast` is compiled from our sources |
| bend-lang (`bend`) | 0.2.38 | Apache-2.0 | vendored binary (`vendor/linux-x86_64/bin/bend`) |
| hvm (`hvm`) | 2.0.22 | Apache-2.0 | vendored binary (`vendor/linux-x86_64/bin/hvm`) |
| stb_image_write | 1.16 | Public domain / MIT | vendored header (`src/gl/stb_image_write.h`) |
| Mesa / llvmpipe / libEGL | system (25.2.8) | MIT | system package, `dlopen`ed at runtime |
| GCC | system 13.3 | GPL-3.0-or-later with GCC runtime exception | build tool only |

Provenance and sha256 pins are recorded in `toolchain.lock`.

The Bend and HVM binaries are unmodified builds from the pinned crates
(`cargo install bend-lang --version 0.2.38 --locked`,
`cargo install hvm --version 2.0.22 --features c --locked`).
