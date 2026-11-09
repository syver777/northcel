'use strict';

/**
 * Locate the native bundle for the `northcel` npm launcher.
 *
 * Resolution order:
 *   1. NCEL_NATIVE_BUNDLE (explicit override, e.g. a checkout or a CI cache);
 *   2. the `northcel-linux-x64` optional dependency (normal installation);
 *      0.2.1's `@ncel/linux-x64` is still honoured if it is what is installed;
 *   3. nothing -> an honest platform verdict, never a pretend renderer.
 */

const fs = require('fs');
const os = require('os');
const path = require('path');
const { spawnSync } = require('child_process');

const PACKAGE_VERSION = '0.5.0';
const NATIVE_RUNTIME_VERSION = '0.4.0';
const SPEC_VERSION = '0.4.0-draft';
// The bundled native runtime 0.4.0 implements spec 0.3; spec 0.4 documents use the Python reference.
const NATIVE_SPEC_VERSION = '0.3.0-draft';
const EXIT_NO_NATIVE = 3;

// Mirrors the Python launcher (northcel/launcher/platform_info.py): the loader
// searches LD_LIBRARY_PATH and the Homebrew prefixes, so the platform gate must too.
const HOMEBREW_PREFIXES = ['/home/linuxbrew/.linuxbrew', '/usr/local'];
const DISTRO_LIB_DIRS = [
  '/usr/lib/x86_64-linux-gnu',
  '/usr/lib64',
  '/usr/lib',
  '/lib/x86_64-linux-gnu',
  '/lib64',
  '/lib',
];

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
        `(see native/BUILD.md section 7) and Windows is untouched.`
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
      'no libEGL.so.1 found in LD_LIBRARY_PATH, the Homebrew prefix, or the ' +
        'distribution library paths: GLSL is compiled by the GL driver, so the ' +
        'Mesa/EGL runtime is required (apt install libegl1 libgl1 mesa-libgallium | ' +
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

function eglSearchDirs() {
  // The gate must see what `dlopen("libEGL.so.1")` sees, or it refuses to render a
  // machine that can render: Homebrew installs Mesa keg-only under its prefix (never
  // in $PREFIX/lib), and LD_LIBRARY_PATH is precisely what the loader would use.
  const dirs = [];
  for (const entry of (process.env.LD_LIBRARY_PATH || '').split(path.delimiter)) {
    if (entry) dirs.push(entry);
  }
  const prefixes = [];
  if (process.env.HOMEBREW_PREFIX) prefixes.push(process.env.HOMEBREW_PREFIX);
  prefixes.push(...HOMEBREW_PREFIXES);
  if (process.env.HOME) prefixes.push(path.join(process.env.HOME, '.linuxbrew'));
  for (const prefix of prefixes) {
    dirs.push(path.join(prefix, 'lib'), path.join(prefix, 'lib64'));
    let kegs = [];
    try {
      kegs = fs.readdirSync(path.join(prefix, 'opt')).sort();
    } catch (err) {
      /* no kegs under this prefix */
    }
    for (const keg of kegs) {
      dirs.push(path.join(prefix, 'opt', keg, 'lib'), path.join(prefix, 'opt', keg, 'lib64'));
    }
  }
  dirs.push(...DISTRO_LIB_DIRS);
  return dirs;
}

function hasEgl() {
  if (eglSearchDirs().some((p) => fs.existsSync(path.join(p, 'libEGL.so.1')))) return true;
  // Last resort, matching the Python launcher: ask the loader cache.
  try {
    const out = spawnSync('ldconfig', ['-p'], { encoding: 'utf8', timeout: 10000 });
    return String(out.stdout || '')
      .split('\n')
      .some((line) => line.includes('libEGL.so.1') && line.includes('=>'));
  } catch (err) {
    return false;
  }
}

function firstResolvable(names) {
  for (const name of names) {
    try {
      return require.resolve(name);
    } catch (err) {
      /* try the next name */
    }
  }
  throw new Error('none of ' + names.join(', ') + ' is installed');
}

function bundleDir() {
  if (process.env.NCEL_NATIVE_BUNDLE) {
    const explicit = path.resolve(process.env.NCEL_NATIVE_BUNDLE);
    if (fs.existsSync(path.join(explicit, 'bin', 'ncel-native'))) return explicit;
  }
  try {
    const pkg = firstResolvable(['northcel-linux-x64/package.json', '@ncel/linux-x64/package.json']);
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
  NATIVE_SPEC_VERSION,
  EXIT_NO_NATIVE,
  bundleDir,
  nativeBinary,
  platformVerdict,
  verifyBundle,
  manifest,
  // exposed for the EGL regression test; not part of the CLI surface
  eglSearchDirs,
  hasEgl,
};
