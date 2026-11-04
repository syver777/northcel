"""EGL discovery: the launcher must see the library the loader would actually use.

Regression cover for the bug the Homebrew tap exposed: `find_egl_runtime()` only looked
at distribution paths and `ldconfig -p`, so on a host whose Mesa comes from Homebrew
(keg-only) or from `LD_LIBRARY_PATH`, the gate said "no libEGL.so.1 found" and refused
to use a native runtime that was sitting right there.

Nothing here needs a real GL driver: each test builds a throwaway directory that
contains a file *named* `libEGL.so.1` and asserts that the probe finds it, which is
exactly the filesystem question the probe answers. The well-known Homebrew prefixes
and the distribution directories are neutralised per test (`patch.dict` of the module
constants plus an empty environment), so the result never depends on what this host
happens to have installed.
"""

from __future__ import annotations

import os
import sys
import tempfile
import unittest
from contextlib import contextmanager
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from northcel.launcher import platform_info  # noqa: E402


def _fake_egl(directory: Path) -> Path:
    directory.mkdir(parents=True, exist_ok=True)
    lib = directory / "libEGL.so.1"
    lib.write_bytes(b"not a real ELF; the probe only stats the path")
    return lib


@contextmanager
def probe(env: dict[str, str]):
    """Run the probe with only `env` set, no Homebrew prefixes and no distro paths."""
    clean = {"PATH": "", "HOME": "", **env}
    with mock.patch.dict(os.environ, clean, clear=True):
        with mock.patch.multiple(
            platform_info, HOMEBREW_PREFIXES=(), DISTRO_LIB_DIRS=()
        ):
            yield


class TestEglDiscovery(unittest.TestCase):
    def test_ld_library_path_is_consulted_before_everything_else(self):
        with tempfile.TemporaryDirectory() as tmp:
            lib = _fake_egl(Path(tmp) / "custom-mesa")
            with probe({"LD_LIBRARY_PATH": str(lib.parent)}):
                self.assertEqual(platform_info.find_egl_runtime(), str(lib))

    def test_several_ld_library_path_entries_are_searched_in_order(self):
        with tempfile.TemporaryDirectory() as tmp:
            first = Path(tmp) / "first"
            second = Path(tmp) / "second"
            first.mkdir()
            lib = _fake_egl(second)
            with probe({"LD_LIBRARY_PATH": os.pathsep.join([str(first), str(second)])}):
                self.assertEqual(platform_info.find_egl_runtime(), str(lib))

    def test_homebrew_prefix_is_consulted_without_ld_library_path(self):
        # The Homebrew formula wraps the launcher with LD_LIBRARY_PATH, but a user who
        # runs `northcel` from a plain shell must still find a Homebrew Mesa.
        with tempfile.TemporaryDirectory() as tmp:
            prefix = Path(tmp) / "linuxbrew"
            lib = _fake_egl(prefix / "lib")
            with probe({"HOMEBREW_PREFIX": str(prefix)}):
                self.assertEqual(platform_info.find_egl_runtime(), str(lib))

    def test_keg_only_mesa_inside_a_homebrew_prefix_is_found(self):
        # mesa is keg-only: `$PREFIX/opt/mesa` is a symlink to the versioned Cellar
        # directory and is never linked into `$PREFIX/lib`.
        with tempfile.TemporaryDirectory() as tmp:
            prefix = Path(tmp) / "linuxbrew"
            lib = _fake_egl(prefix / "opt" / "mesa" / "lib")
            with probe({"HOMEBREW_PREFIX": str(prefix)}):
                self.assertEqual(platform_info.find_egl_runtime(), str(lib))

    def test_home_directory_linuxbrew_is_found(self):
        with tempfile.TemporaryDirectory() as tmp:
            lib = _fake_egl(Path(tmp) / ".linuxbrew" / "lib")
            with mock.patch.object(platform_info, "HOMEBREW_PREFIXES", ()):
                with mock.patch.object(platform_info, "DISTRO_LIB_DIRS", ()):
                    with mock.patch.dict(
                        os.environ, {"PATH": "", "HOME": tmp}, clear=True
                    ):
                        self.assertEqual(platform_info.find_egl_runtime(), str(lib))

    def test_missing_library_still_reports_none_honestly(self):
        with tempfile.TemporaryDirectory() as tmp:
            with probe({"HOMEBREW_PREFIX": str(Path(tmp) / "nope")}):
                self.assertIsNone(platform_info.find_egl_runtime())

    def test_distribution_paths_are_still_the_last_resort(self):
        # Parity with the old behaviour: the classic Ubuntu/Debian/Fedora paths are
        # still probed, in their original order, after every other source.
        names = [directory for _label, directory in platform_info._egl_search_dirs()]
        for directory in (
            "/usr/lib/x86_64-linux-gnu",
            "/usr/lib64",
            "/usr/lib",
            "/lib/x86_64-linux-gnu",
        ):
            self.assertIn(directory, names)
        self.assertLess(names.index("/usr/lib"), names.index("/lib64"))

    def test_platform_reason_names_the_places_that_were_searched(self):
        with tempfile.TemporaryDirectory() as tmp:
            with mock.patch.dict(os.environ, {"PATH": "", "HOME": tmp}, clear=True):
                with mock.patch.object(
                    platform_info, "find_egl_runtime", return_value=None
                ):
                    with mock.patch.object(platform_info, "machine", return_value="x86_64"):
                        with mock.patch.object(
                            platform_info, "glibc_version", return_value="2.39"
                        ):
                            plat = platform_info.platform_info()
        self.assertFalse(plat.supported)
        joined = " ".join(plat.reasons)
        self.assertIn("LD_LIBRARY_PATH", joined)
        self.assertIn("Homebrew prefix", joined)
        self.assertIn("libegl1", joined)  # still tells the user how to fix it


if __name__ == "__main__":
    unittest.main()
