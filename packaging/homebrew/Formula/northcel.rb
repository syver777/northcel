# typed: false
# frozen_string_literal: true

# Homebrew formula for NorthCel — the `.ncel` drawing language CLI with the
# native MoonBit + Bend/HVM2 + GLSL runtime.
#
# This formula lives in the public tap:
#
#   brew tap syver777/northcel
#   brew install northcel          # or: brew install syver777/northcel/northcel
#
# `northcel` is the single install name; `ncel` is the short command alias the
# package itself installs. The reference implementation is built from this
# formula's own pinned sdist; the launcher and the native bundle are sha256-pinned
# wheels. Nothing is downloaded on first run.
#
# Upstream source, issues and releases: https://github.com/syver777/northcel
# (the project home). The product page is https://northnoir.com/northcel.
class Northcel < Formula
  include Language::Python::Virtualenv

  desc "Drawing language for AI-drawn video with a native MoonBit + Bend + GLSL runtime"
  homepage "https://github.com/syver777/northcel"
  url "https://files.pythonhosted.org/packages/59/a9/8f1be6743916c73d7af84974264452975884eb4df15c2af86dc728df4dcc/northcel-0.2.1.tar.gz"
  sha256 "b9c5ff520e3926936242b7b34d2c9bc50983a2c469e0dfc75820686aeb08f66d"
  license any_of: ["MIT", "Apache-2.0"]

  depends_on arch: :x86_64
  depends_on :linux
  depends_on "mesa" # libEGL + llvmpipe: the GL driver that compiles the GLSL
  depends_on "python@3.12" # the pinned wheels are cp312

  # numpy and Pillow are required by the Python reference renderer, which is also
  # the conformance oracle and the only formatter (`northcel fmt`, `--no-native`).
  resource "numpy" do
    url "https://files.pythonhosted.org/packages/43/a3/c799c62e19c337e6d3770b08e475887fb30ce8477d3c09efca6b2f0228a6/numpy-2.5.4-cp312-cp312-manylinux_2_27_x86_64.manylinux_2_28_x86_64.whl"
    sha256 "fbde6962867ee75b48b0ee29b2b9372ec5d617799dbaf38e82dc0596f2f7738a"
  end

  resource "pillow" do
    url "https://files.pythonhosted.org/packages/e6/99/fdf65cc539e266ab93546c261bdf98411fe165c6e4e13f9dbf597097192b/pillow-13.0.0-cp312-cp312-manylinux_2_27_x86_64.manylinux_2_28_x86_64.whl"
    sha256 "42d63be3af4f9b951b199b0a9d23365d37ab14687e6d77b74940432c8515c4ca"
  end

  # Build tools for this formula's own sdist (the reference implementation), pinned
  # so the install builds with `--no-build-isolation` and nothing else is fetched.
  resource "setuptools" do
    url "https://files.pythonhosted.org/packages/ef/55/6dc6d6bb953bdfc52519a0059592c52b6e3b8ad51cf8256dffceb55b0610/setuptools-84.2.1-py3-none-any.whl"
    sha256 "ca140b45d5325a9478f880e351484f62fef15f336462e449ca0c03c873d589c2"
  end

  resource "wheel" do
    url "https://files.pythonhosted.org/packages/2e/29/69cfbb602cd91690c55d38ba9fe53e6a7e76a6fa647bf38f19c138d25449/wheel-0.48.0-py3-none-any.whl"
    sha256 "3217dcc807155e45db462d7ef2431f5ddda0d7273b700d05a67b271ceb1287ab"
  end

  # The native bundle: MoonBit-compiled typed AST stage, Bend 0.2.38, HVM 2.0.22,
  # the EGL surfaceless GL host and both GLSL shaders. manylinux_2_39 => glibc 2.39.
  resource "ncel-native" do
    url "https://files.pythonhosted.org/packages/ee/a3/c77c60acb74a125486cc7710d66de189dc8f655156038bba5e0c6dc39b7c/ncel_native-0.2.1-py3-none-manylinux_2_39_x86_64.whl"
    sha256 "0b5f6f74ee41ed904e5c7e8b83f168c2bcf922b3ea7da2792c3babff7f88d06e"
  end

  # The launcher: platform verdict, native dispatch, labelled Python fallback,
  # doctor/verify/check/info/render/film/fmt/guide/toolchain. Installed last so
  # its `ncel` script wins over the reference package's shorter one.
  resource "ncel" do
    url "https://files.pythonhosted.org/packages/75/fd/3dd3fe02ebd500cc7f05665542a3fbc7511484357ff075d554d5695a01ab/ncel-0.2.1-py3-none-any.whl"
    sha256 "85f5a73cd0745085a182731d8ff23e83a033c3a670fdecd319181cd57c8b46a1"
  end

  def install
    venv = virtualenv_create(libexec, "python3.12")

    # Homebrew's pip runs with --no-deps, so every dependency is installed first
    # and explicitly.
    %w[numpy pillow setuptools wheel].each { |name| install_wheel(venv, name) }

    # `buildpath` is this formula's pinned northcel sdist: the reference parser,
    # validator, formatter and renderer (the conformance oracle).
    venv.pip_install buildpath, build_isolation: false

    %w[ncel-native ncel].each { |name| install_wheel(venv, name) }

    # The declared `mesa` dependency is the GL runtime actually used: point the
    # dynamic loader at it so this install is self-contained instead of quietly
    # borrowing the distribution's Mesa. A Homebrew `mesa` upgrade is picked up
    # through `opt_lib` without rebuilding this formula.
    (bin/"northcel").write_env_script libexec/"bin/ncel",
                                      LD_LIBRARY_PATH: "#{formula_opt_lib("mesa")}:${LD_LIBRARY_PATH}"

    # One install name: `northcel`. `ncel` stays as the package's short alias.
    bin.install_symlink "northcel" => "ncel"
  end

  def caveats
    <<~EOS
      NorthCel renders natively on Linux x86_64 with glibc >= 2.39, using Mesa's
      EGL/llvmpipe driver (installed as a dependency) — no GPU is required.

      Prove the installation, then render something:

        northcel doctor          # MoonBit, Bend/HVM2, GLSL and exact versions
        northcel verify          # conformance frame + 6-frame film, rendered twice
        northcel guide           # offline authoring guide

      `ncel` is the same command. `northcel --no-native` (and `northcel fmt`) use
      the bundled Python reference implementation, which labels its output as
      non-native. macOS and Windows are not supported by this formula.

      If `northcel doctor` reports "no libEGL.so.1 found", the launcher's platform
      probe (ncel 0.2.1) only looks in the distribution's standard library paths.
      Install the distribution's EGL runtime once and nothing else changes:
        Debian/Ubuntu: sudo apt install libegl1 libgl1
        Fedora/RHEL:   sudo dnf install mesa-libEGL mesa-dri-drivers
      Rendering itself still uses the Mesa installed by this formula.
    EOS
  end

  test do
    assert_match "0.2.1", shell_output("#{bin}/northcel version")
    assert_match "0.2.1", shell_output("#{bin}/ncel version")
    assert_match "\"ok\": true", shell_output("#{bin}/northcel doctor --json")
    system bin/"northcel", "verify"

    # A real render from the bundled fixture, through the installed command only.
    starter = libexec/"lib/python3.12/site-packages/ncel/data/starter.ncel"
    assert_path_exists starter
    system bin/"northcel", "render", starter, "-o", testpath/"frame.png"
    assert_path_exists testpath/"frame.png"
  end

  private

  # Homebrew stages a resource into the download itself, so pip must be handed the
  # .whl file inside that directory: pip cannot install a directory without a
  # build system, which is what every prebuilt wheel would otherwise look like.
  def install_wheel(venv, name)
    resource(name).stage do
      venv.pip_install Pathname.glob("*.whl").first
    end
  end
end
