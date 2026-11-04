# Homebrew tap formula for `ncel` (Linux x86_64).
#
# This lives in the repository so it can be reviewed and tested; the GitHub tap
# repository (`syver777/homebrew-ncel`) is created by the planner, not by an agent.
# `brew install ncel` alone does NOT work: homebrew-core does not accept new
# formulae without a maintainer review, so the honest command is
#
#   brew tap syver777/ncel
#   brew install ncel
#
# or, before the tap exists, straight from this file:
#
#   brew install --build-from-source ./packaging/homebrew/Formula/ncel.rb
#
# Everything below installs PREBUILT, sha256-pinned wheels: nothing is compiled and
# nothing is downloaded at first run.
class Ncel < Formula
  include Language::Python::Virtualenv

  desc "NorthCel (.ncel) CLI with the native MoonBit + Bend/HVM2 + GLSL runtime"
  homepage "https://northnoir.com/northcel"
  url "https://files.pythonhosted.org/packages/d6/cd/c0e17d241484e28c46c9be9359d2c92f41351cd75843722e8a9b3640b62a/ncel-0.2.1.tar.gz"
  sha256 "8ad7c9c0357d0104785dddd57da455add50303ce0d30af91193e20b04149db36"
  license :cannot_represent # Proprietary, North Noir
  version "0.2.1"

  depends_on :linux
  depends_on "python@3.12"
  depends_on "mesa" # the GL runtime: libEGL + llvmpipe, which compiles the GLSL

  # The launcher wheel (this is what the formula installs; the sdist above is the
  # formula's identity/version source).
  resource "ncel" do
    url "https://files.pythonhosted.org/packages/75/fd/3dd3fe02ebd500cc7f05665542a3fbc7511484357ff075d554d5695a01ab/ncel-0.2.1-py3-none-any.whl"
    sha256 "85f5a73cd0745085a182731d8ff23e83a033c3a670fdecd319181cd57c8b46a1"
  end

  # The native runtime bundle: MoonBit-compiled stage, Bend 0.2.38, HVM 2.0.22,
  # GLSL shaders. Linux x86_64, glibc >= 2.39 (manylinux_2_39).
  resource "ncel-native" do
    url "https://files.pythonhosted.org/packages/ee/a3/c77c60acb74a125486cc7710d66de189dc8f655156038bba5e0c6dc39b7c/ncel_native-0.2.1-py3-none-manylinux_2_39_x86_64.whl"
    sha256 "0b5f6f74ee41ed904e5c7e8b83f168c2bcf922b3ea7da2792c3babff7f88d06e"
  end

  # The Python reference parser/validator/formatter (the conformance oracle and the
  # labelled fallback; `ncel fmt` uses it).
  resource "northcel" do
    url "https://files.pythonhosted.org/packages/81/40/d069656e05b755f930f5a2a38210bba4626de779d5467f72b1e30acccb59/northcel-0.2.1-py3-none-any.whl"
    sha256 "d24a8ee793bcc0cbe5637b40686c8237833e115cf1f5ebfaca0990f81aa61472"
  end

  resource "numpy" do
    url "https://files.pythonhosted.org/packages/43/a3/c799c62e19c337e6d3770b08e475887fb30ce8477d3c09efca6b2f0228a6/numpy-2.5.4-cp312-cp312-manylinux_2_27_x86_64.manylinux_2_28_x86_64.whl"
    sha256 "fbde6962867ee75b48b0ee29b2b9372ec5d617799dbaf38e82dc0596f2f7738a"
  end

  resource "pillow" do
    url "https://files.pythonhosted.org/packages/e6/99/fdf65cc539e266ab93546c261bdf98411fe165c6e4e13f9dbf597097192b/pillow-13.0.0-cp312-cp312-manylinux_2_27_x86_64.manylinux_2_28_x86_64.whl"
    sha256 "42d63be3af4f9b951b199b0a9d23365d37ab14687e6d77b74940432c8515c4ca"
  end

  def install
    # Order matters only for readability: pip finds every dependency already
    # installed, so no wheel is fetched from the network.
    venv = virtualenv_create(libexec, "python3.12")
    %w[numpy pillow northcel ncel-native ncel].each do |name|
      venv.pip_install resource(name)
    end
    bin.install_symlink libexec/"bin/ncel"
  end

  def caveats
    <<~EOS
      The native runtime needs Mesa's EGL/llvmpipe GL driver (installed as a
      dependency) and glibc >= 2.39. Prove the installation with:

        ncel doctor
        ncel verify

      `ncel verify` renders the bundled conformance frame and a 6-frame film twice
      and compares hashes. macOS and Windows are not supported in this release.
    EOS
  end

  test do
    assert_match "ncel 0.2.1", shell_output("#{bin}/ncel version")
    assert_match "\"ok\": true", shell_output("#{bin}/ncel doctor --json")
    system bin/"ncel", "verify"
  end
end
