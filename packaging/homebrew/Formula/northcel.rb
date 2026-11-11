# typed: false
# frozen_string_literal: true

# Homebrew formula for NorthCel — the `.ncel` drawing language CLI.
#
# What "native" means in this formula: MoonBit (`ncel-ast`) for parsing, typed AST,
# ring decoding and Bend codegen; Bend 0.2.38 / HVM 2.0.22 for `bend_swarm` agents;
# GLSL 4.30 compiled by a Mesa/EGL (llvmpipe) context for the pixels. Linux x86_64
# only, glibc >= 2.39 — the formula refuses macOS, Windows and other architectures
# instead of installing a runtime that cannot render natively. The Python
# implementation in the same package is the normative reference *oracle* and the
# labelled fallback renderer (`--no-native`, `fmt`); it is never called native.
#
# This formula lives in the public tap:
#
#   brew tap syver777/northcel
#   brew install northcel          # or: brew install syver777/northcel/northcel
#
# `northcel` is the single install name; `ncel` is the short command alias the
# package itself installs. Two artifacts are pinned: this formula's own `url`
# (the `northcel` sdist, which is both the reference implementation and the
# launcher) and the `northcel-native` platform wheel. Nothing is downloaded on
# first run.
#
# Upstream source, issues and releases: https://github.com/syver777/northcel
# (the project home). The product page is https://northnoir.com/northcel.
class Northcel < Formula
  include Language::Python::Virtualenv

  desc "Drawing language for AI-drawn video; native MoonBit + Bend/HVM2 + GLSL"
  homepage "https://github.com/syver777/northcel"
  url "https://files.pythonhosted.org/packages/08/07/7ee0deed94cc9bcd339ee56f2ed75118cb51adf09f428d41027f5d4f8725/northcel-0.7.1.tar.gz"
  sha256 "5a6c1c6b3362d4309a1ce2222d0267e677566fc301aa810e64a41f9806a6b5f7"
  license any_of: ["MIT", "Apache-2.0"]

  depends_on arch: :x86_64
  depends_on :linux
  depends_on "mesa" # libEGL + llvmpipe: the GL driver that compiles the GLSL
  depends_on "python@3.12" # the pinned wheel is cp312

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
  # Homebrew requires a resource name to differ from the formula name, which is why
  # the main package is the `url` and only the platform wheel is a resource.
  resource "northcel-native" do
    url "https://files.pythonhosted.org/packages/12/f6/00416cfde23a8824f6718109885679cb87e0ae715aeb7d72dcec33bda654/northcel_native-0.4.0-py3-none-manylinux_2_39_x86_64.whl"
    sha256 "ee2e0551fdb3d410de1ad8fca658b923aabd6befcf240630a880386c31c4304b"
  end

  def install
    venv = virtualenv_create(libexec, "python3.12")

    # Homebrew's pip runs with --no-deps, so every dependency is installed first
    # and explicitly. Since 0.3.1 there is one Python distribution: the sdist is the
    # reference implementation *and* the launcher (scripts `northcel` and `ncel`).
    %w[numpy pillow setuptools wheel].each { |name| install_wheel(venv, name) }

    venv.pip_install buildpath, build_isolation: false

    install_wheel(venv, "northcel-native")

    # The declared `mesa` dependency is the GL runtime actually used: point the
    # dynamic loader at it so this install is self-contained instead of quietly
    # borrowing the distribution's Mesa. A Homebrew `mesa` upgrade is picked up
    # through `opt_lib` without rebuilding this formula — and since 0.3.1 the
    # launcher's own EGL probe reads LD_LIBRARY_PATH, so it sees this Mesa too.
    (bin/"northcel").write_env_script libexec/"bin/northcel",
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

      The launcher finds EGL in this formula's Mesa through LD_LIBRARY_PATH (it also
      searches HOMEBREW_PREFIX and the distribution paths). If `northcel doctor`
      still reports "no libEGL.so.1 found", install the distribution's EGL runtime
      once and nothing else changes:
        Debian/Ubuntu: sudo apt install libegl1 libgl1
        Fedora/RHEL:   sudo dnf install mesa-libEGL mesa-dri-drivers
    EOS
  end

  test do
    assert_match "0.7.1", shell_output("#{bin}/northcel version")
    assert_match "0.7.1", shell_output("#{bin}/ncel version")
    assert_match "\"ok\": true", shell_output("#{bin}/northcel doctor --json")
    system bin/"northcel", "verify"

    # A real render from the bundled fixture, through the installed command only.
    # Since 0.3.1 the fixtures ship inside the `northcel` package (they were in the
    # separate `ncel` distribution before), under `examples/`.
    starter = libexec/"lib/python3.12/site-packages/northcel/examples/starter.ncel"
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
