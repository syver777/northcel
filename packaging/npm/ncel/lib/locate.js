'use strict';

/**
 * Locate the native bundle for the `ncel` npm launcher.
 *
 * Resolution order:
 *   1. NCEL_NATIVE_BUNDLE (explicit override, e.g. a checkout or a CI cache);
 *   2. the `@ncel/linux-x64` optional dependency (normal installation);
 *   3. nothing -> an honest platform verdict, never a pretend renderer.
 */

const fs = require('fs');
const os = require('os');
const path = require('path');

const PACKAGE_VERSION = '0.2.1';
const NATIVE_RUNTIME_VERSION = '0.2.0';
const SPEC_VERSION = '0.2.0-draft';
const EXIT_NO_NATIVE = 3;

function glibcVersion() {
  try {
    const report = process.report && process.report.getReport();
    if (report && report.header && report.header.glibcVersionRuntime) {
      return report.header.glibcVersionRuntime.split('.').slice(0, 2).join('.');
    }
  } catch (err) {
    /* fall through */
  }
  return null;
}

function platformVerdict() {
  const platform = process.platform;
  const arch = process.arch;
  const reasons = [];

  if (platform !== 'linux') {
    reasons.push(
      `the native runtime is built and conformance-verified on Linux x86_64 only; this is ` +
        `${platform}/${arch}. macOS needs Vulkan/MoltenVK or a tested GL 4.1 path ` +
        `(see native/ncel/BUILD.md section 7) and Windows is untouched.`
    );
  } else if (arch !== 'x64') {
    reasons.push(`the native runtime is x86_64 only; this machine is ${arch}.`);
  } else {
    const glibc = glibcVersion();
    if (glibc && compareVersions(glibc, '2.39') < 0) {
      reasons.push(
        `glibc ${glibc} is older than the required 2.39 (the pinned Bend/HVM binaries ` +
          `need GLIBC_2.39). Ubuntu 24.04+, Debian 13, Fedora 40+ and RHEL 10 satisfy it.`
      );
    }
  }

  if (reasons.length === 0 && !hasEgl()) {
    reasons.push(
      'no libEGL.so.1 found: GLSL is compiled by the GL driver, so the Mesa/EGL runtime ' +
        'is required (apt install libegl1 libgl1 mesa-libgallium | ' +
        'dnf install mesa-libEGL mesa-dri-drivers).'
    );
  }

  return { platform, arch, glibc: glibcVersion(), supported: reasons.length === 0, reasons };
}

function compareVersions(a, b) {
  const pa = String(a).split('.').map(Number);
  const pb = String(b).split('.').map(Number);
  for (let i = 0; i < Math.max(pa.length, pb.length); i += 1) {
    const x = pa[i] || 0;
    const y = pb[i] || 0;
    if (x !== y) return x < y ? -1 : 1;
  }
  return 0;
}

function hasEgl() {
  const candidates = [
    '/usr/lib/x86_64-linux-gnu/libEGL.so.1',
    '/usr/lib64/libEGL.so.1',
    '/usr/lib/libEGL.so.1',
    '/lib/x86_64-linux-gnu/libEGL.so.1',
  ];
  return candidates.some((p) => fs.existsSync(p));
}

function bundleDir() {
  if (process.env.NCEL_NATIVE_BUNDLE) {
    const explicit = path.resolve(process.env.NCEL_NATIVE_BUNDLE);
    if (fs.existsSync(path.join(explicit, 'bin', 'ncel-native'))) return explicit;
  }
  try {
    const pkg = require.resolve('@ncel/linux-x64/package.json');
    const candidate = path.join(path.dirname(pkg), 'bundle');
    if (fs.existsSync(path.join(candidate, 'bin', 'ncel-native'))) return candidate;
  } catch (err) {
    /* optional dependency not installed for this platform */
  }
  return null;
}

function nativeBinary() {
  const dir = bundleDir();
  return dir ? path.join(dir, 'bin', 'ncel-native') : null;
}

function manifest() {
  const dir = bundleDir();
  if (!dir) return null;
  const file = path.join(dir, 'bundle-manifest.json');
  if (!fs.existsSync(file)) return null;
  try {
    return JSON.parse(fs.readFileSync(file, 'utf8'));
  } catch (err) {
    return null;
  }
}

function verifyBundle() {
  const dir = bundleDir();
  const doc = manifest();
  if (!dir || !doc) {
    return { checked: 0, failed: [], missing: [], available: false };
  }
  const crypto = require('crypto');
  const failed = [];
  const missing = [];
  let checked = 0;
  for (const entry of doc.files || []) {
    const target = path.join(dir, entry.path);
    if (!fs.existsSync(target)) {
      missing.push(entry.path);
      continue;
    }
    const digest = crypto.createHash('sha256').update(fs.readFileSync(target)).digest('hex');
    checked += 1;
    if (digest !== entry.sha256) failed.push({ path: entry.path, expected: entry.sha256, actual: digest });
  }
  return { checked, failed, missing, available: true };
}

module.exports = {
  PACKAGE_VERSION,
  NATIVE_RUNTIME_VERSION,
  SPEC_VERSION,
  EXIT_NO_NATIVE,
  bundleDir,
  nativeBinary,
  platformVerdict,
  verifyBundle,
  manifest,
};
