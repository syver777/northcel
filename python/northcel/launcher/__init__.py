"""`northcel` launcher — one command line for both NorthCel implementations.

The native runtime (MoonBit typed AST + Bend/HVM2 swarms + GLSL via Mesa/EGL) is
the implementation this CLI calls whenever it is available. The Python reference
implementation is used only when the native stages genuinely cannot run on the
current platform, and then the tool says so and labels the result.

This module ships inside the single `northcel` distribution: `northcel` is the
command, `ncel` is the short alias, and both are installed by `pip install
northcel`. The native binaries come from the platform wheel `northcel-native`.
"""

from ..config import PACKAGE_VERSION as __version__
from ..config import SPEC_VERSION

#: Version of the bundled native runtime build (`native/`, commit 3ad5f7e).
NATIVE_RUNTIME_VERSION = "0.2.0"

#: Exit code used when the native runtime is unavailable on this platform.
EXIT_NO_NATIVE = 3

__all__ = ["__version__", "SPEC_VERSION", "NATIVE_RUNTIME_VERSION", "EXIT_NO_NATIVE"]
