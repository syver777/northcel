"""`ncel` — the one-command NorthCel CLI.

The native runtime (MoonBit typed AST + Bend/HVM2 swarms + GLSL via Mesa/EGL) is
the implementation this CLI calls whenever it is available. The Python reference
renderer (`northcel`) is used only when the native stages genuinely cannot run on
the current platform, and then the tool says so and labels the result.
"""

__version__ = "0.2.1"

#: Version of the bundled native runtime build (native/ncel, commit 3ad5f7e).
NATIVE_RUNTIME_VERSION = "0.2.0"

#: NorthCel language specification implemented by both implementations.
SPEC_VERSION = "0.2.0-draft"

#: Exit code used when the native runtime is unavailable on this platform.
EXIT_NO_NATIVE = 3
