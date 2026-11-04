#!/usr/bin/env node
'use strict';

/**
 * `ncel` — npm launcher for the native NorthCel runtime.
 *
 * There is no JavaScript renderer here and none is claimed. On a platform where
 * the native bundle exists this spawns it and passes argv/stdout/stderr/exit code
 * through unchanged. Where it does not exist, the launcher prints the exact
 * platform verdict (which is also what a macOS/Windows user sees) and exits 3.
 */

const crypto = require('crypto');
const fs = require('fs');
const os = require('os');
const path = require('path');
const { spawn, spawnSync } = require('child_process');

const locate = require('../lib/locate');

const DATA = path.join(__dirname, '..', 'data');

const USAGE = `ncel — NorthCel (.ncel) command line (npm launcher)

usage: ncel <command> [options]

  doctor  [--json]                     stage availability, exact versions, platform verdict
  verify  [--json] [--keep DIR]        render the bundled fixtures with the native runtime
  check   FILE [--json]                parse + validate
  info    FILE [--json]                scene/film metadata
  render  FILE [-o OUT.png] [--frame N] [--seed N] [--json]
  film    FILE -o OUTDIR [--frames 0..5] [--mp4 OUT.mp4] [--json]
  guide                                offline authoring guide
  version, --version                   versions (launcher, native runtime, spec)

Not available from npm (use pip/pipx for these): fmt — formatting is the Python
reference renderer (\`pip install northcel\`).
Platform: Linux x86_64, glibc >= 2.39, Mesa EGL/llvmpipe. macOS/Windows are not
supported in this release; \`ncel doctor\` explains exactly what is missing.
`;

function fail(message, code) {
  process.stderr.write(message.endsWith('\n') ? message : message + '\n');
  process.exit(code);
}

function requireNative() {
  const verdict = locate.platformVerdict();
  const binary = locate.nativeBinary();
  if (!verdict.supported) {
    fail(
      'ncel: native runtime unavailable on this platform.\n' +
        verdict.reasons.map((r) => 'ncel: ' + r).join('\n') +
        '\nncel: this release ships Linux x86_64 only. `pip install ncel` on macOS/Windows ' +
        'installs the labelled Python reference renderer; this npm package never pretends to render.',
      locate.EXIT_NO_NATIVE
    );
  }
  if (!binary) {
    fail(
      'ncel: the native bundle package (@ncel/linux-x64) is not installed.\n' +
        'ncel: install with `npm install ncel` (it is an optionalDependency), or set ' +
        'NCEL_NATIVE_BUNDLE to a native/ncel build tree.',
      locate.EXIT_NO_NATIVE
    );
  }
  return binary;
}

function passthrough(command, args) {
  const binary = requireNative();
  const child = spawn(binary, [command].concat(args), { stdio: 'inherit' });
  child.on('exit', (code, signal) => {
    if (signal) process.kill(process.pid, signal);
    process.exit(code === null ? 1 : code);
  });
  child.on('error', (err) => fail('ncel: failed to run the native runtime: ' + err.message, 1));
}

function sha256(file) {
  return crypto.createHash('sha256').update(fs.readFileSync(file)).digest('hex');
}

function nativeDoctor() {
  const binary = locate.nativeBinary();
  if (!binary) return null;
  const res = spawnSync(binary, ['doctor'], { encoding: 'utf8' });
  if (!res.stdout) return null;
  try {
    return JSON.parse(res.stdout);
  } catch (err) {
    return null;
  }
}

function doctor(jsonOut) {
  const binary = locate.nativeBinary();
  const verdict = locate.platformVerdict();
  const native = binary ? nativeDoctor() : null;
  const checks = locate.verifyBundle();
  const errors = [];
  if (!verdict.supported) errors.push(...verdict.reasons);
  if (!binary) errors.push('native bundle (@ncel/linux-x64) is not installed');
  if (checks.failed.length) errors.push('bundle checksum mismatch: ' + checks.failed.map((f) => f.path).join(', '));
  if (checks.missing.length) errors.push('bundle is missing files: ' + checks.missing.join(', '));
  if (binary && !native) errors.push('`ncel-native doctor` did not return a usable report');

  const stageState = native
    ? native.moonbit_stage && native.gl_stage && !!native.bend_path && !!native.hvm_path
    : false;

  const doc = {
    ok: verdict.supported && !!binary && !checks.failed.length && !checks.missing.length && !!native && !!native.ok,
    launcher: { name: 'ncel', version: locate.PACKAGE_VERSION, kind: 'npm' },
    platform: verdict,
    native: {
      available: !!native && !!native.ok,
      runtime_version: (native && native.version) || locate.NATIVE_RUNTIME_VERSION,
      spec_version: (native && native.spec_version) || locate.SPEC_VERSION,
      bundle: locate.bundleDir(),
      checksums: { verified: checks.checked, failed: checks.failed, missing: checks.missing },
      stage: stageState ? 'MoonBit+Bend+GLSL' : null,
    },
    stages: {
      moonbit: { present: !!(native && native.moonbit_stage), binary: 'ncel-ast' },
      bend: { present: !!(native && native.bend_path), version: (native && native.bend_version || '').trim() || null },
      hvm: { present: !!(native && native.hvm_path), version: (native && native.hvm_version || '').trim() || null },
      gl: native
        ? {
            present: !!(native.gl && native.gl.ok),
            version: (native.gl || {}).gl_version || null,
            renderer: (native.gl || {}).gl_renderer || null,
            glsl: (native.gl || {}).glsl_version || null,
          }
        : { present: false },
      glsl_shaders: Object.fromEntries(
        Object.entries((native && native.shaders) || {}).map(([name, data]) => [
          name,
          { sha256: data.sha256, compiles: !!(data.compile && data.compile.ok) },
        ])
      ),
      ffmpeg: { present: !!(native && native.ffmpeg), optional: true },
    },
    errors,
  };

  if (jsonOut) {
    process.stdout.write(JSON.stringify(doc, null, 2) + '\n');
  } else {
    const out = [];
    out.push(`ncel ${doc.launcher.version}  (npm launcher, NorthCel spec ${doc.native.spec_version})`);
    out.push(`platform      ${doc.platform.platform}-${doc.platform.arch}${doc.platform.glibc ? ' glibc ' + doc.platform.glibc : ''}`);
    out.push(`supported     ${doc.platform.supported ? 'yes' : 'NO'}`);
    for (const r of doc.platform.reasons) out.push(`              - ${r}`);
    out.push(
      doc.native.available
        ? `native        ${doc.native.runtime_version}  (bundle checksums ${doc.native.checksums.verified} verified, stage ${doc.native.stage})`
        : `native        NOT AVAILABLE${doc.native.bundle ? ' (bundle ' + doc.native.bundle + ')' : ''}`
    );
    const s = doc.stages;
    out.push(`  MoonBit       stage present: ${s.moonbit.present ? 'yes' : 'NO'}  binary ${s.moonbit.binary}`);
    out.push(`  Bend          ${s.bend.version || 'missing'}`);
    out.push(`  HVM2          ${s.hvm.version || 'missing'}`);
    out.push(`  GL runtime    ${s.gl.version || 'missing'}  ${s.gl.renderer || ''}  GLSL ${s.gl.glsl || '?'}`);
    const shaders = Object.entries(s.glsl_shaders || {}).map(
      ([name, data]) => `${name} ${String(data.sha256).slice(0, 12)}… ${data.compiles ? 'compiles' : 'FAILED'}`
    );
    if (shaders.length) out.push(`  GLSL          ${shaders.join('  ')}`);
    out.push(`  ffmpeg        ${s.ffmpeg.present ? 'present (optional, --mp4)' : 'absent (optional)'}`);
    out.push('  reference     not bundled — `pip install ncel` for the Python reference renderer');
    if (errors.length) {
      out.push('errors:');
      errors.forEach((e) => out.push('  - ' + e));
    }
    process.stdout.write(out.join('\n') + '\n');
  }
  process.exit(doc.ok ? 0 : locate.EXIT_NO_NATIVE);
}

function runJson(binary, args) {
  const res = spawnSync(binary, args, { encoding: 'utf8' });
  const text = (res.stdout || '').trim();
  let doc = null;
  const lines = text.split('\n').reverse();
  for (const line of lines) {
    const trimmed = line.trim();
    if (trimmed.startsWith('{')) {
      try {
        doc = JSON.parse(trimmed);
      } catch (err) {
        doc = null;
      }
      break;
    }
  }
  return { code: res.status === null ? 1 : res.status, doc, stderr: (res.stderr || '').trim() };
}

function verify(args) {
  const binary = requireNative();
  const jsonOut = args.includes('--json');
  const keepIndex = args.indexOf('--keep');
  const keep = keepIndex >= 0 ? args[keepIndex + 1] : null;
  const workdir = keep || fs.mkdtempSync(path.join(os.tmpdir(), 'ncel-verify-'));

  let pins = {};
  try {
    pins = JSON.parse(fs.readFileSync(path.join(DATA, 'pins.json'), 'utf8'));
  } catch (err) {
    pins = {};
  }
  const expectedShower = pins.oracle && pins.oracle.shower_f0001 && pins.oracle.shower_f0001.sha256;
  const checks = [];
  const add = (name, ok, detail, extra) => checks.push(Object.assign({ name, ok: !!ok, detail }, extra || {}));

  const starter = path.join(DATA, 'starter.ncel');
  const out1 = path.join(workdir, 'starter.png');
  let r = runJson(binary, ['render', starter, '-o', out1, '--frame', '0', '--json']);
  const size = (r.doc && r.doc.size) || {};
  add('starter-render', r.code === 0 && fs.existsSync(out1) && size.width === 320,
    `exit ${r.code}, ${size.width}x${size.height}` + (r.code ? `; stderr: ${r.stderr}` : ''),
    { sha256: fs.existsSync(out1) ? sha256(out1) : null });

  const shower = path.join(DATA, 'shower_f0001.ncel');
  const out2 = path.join(workdir, 'shower_f0001.png');
  r = runJson(binary, ['render', shower, '-o', out2, '--frame', '0', '--json']);
  const got = fs.existsSync(out2) ? sha256(out2) : null;
  add('shower-f0001-conformance', r.code === 0 && got === expectedShower,
    `exit ${r.code}, sha256 ${got} vs pinned ${expectedShower}`, { sha256: got, expected: expectedShower });

  const film = path.join(DATA, 'lantern_film.ncel');
  const outdir = path.join(workdir, 'film');
  r = runJson(binary, ['film', film, '-o', outdir, '--frames', '0..5', '--json']);
  const frames = fs.existsSync(outdir)
    ? fs.readdirSync(outdir).filter((f) => /^f\d+\.png$/.test(f)).sort()
    : [];
  add('film-6-frames', r.code === 0 && frames.length === 6, `exit ${r.code}, ${frames.length} frame(s)`);

  const repeat = path.join(workdir, 'shower_f0001_repeat.png');
  const repeatDir = path.join(workdir, 'film_repeat');
  const ra = runJson(binary, ['render', shower, '-o', repeat, '--frame', '0', '--json']);
  const rb = runJson(binary, ['film', film, '-o', repeatDir, '--frames', '0..5', '--json']);
  const sameStill = fs.existsSync(repeat) && got !== null && sha256(repeat) === got;
  const repeatFrames = fs.existsSync(repeatDir)
    ? fs.readdirSync(repeatDir).filter((f) => /^f\d+\.png$/.test(f)).sort()
    : [];
  const sameFilm = repeatFrames.length === frames.length &&
    frames.every((name, i) => sha256(path.join(outdir, name)) === sha256(path.join(repeatDir, repeatFrames[i])));
  add('determinism', ra.code === 0 && rb.code === 0 && sameStill && sameFilm,
    `still identical: ${sameStill}; film identical: ${sameFilm}`);

  const unique = new Set(frames.map((f) => sha256(path.join(outdir, f)))).size;
  add('film-frames-differ', frames.length === 6 && unique === 6, `${unique}/6 distinct frame hashes`);

  const ok = checks.every((c) => c.ok);
  const result = { ok, runtime: 'native', launcher: 'npm', workdir, checks };
  if (jsonOut) {
    process.stdout.write(JSON.stringify(result, null, 2) + '\n');
  } else {
    const lines = ['ncel verify — native runtime self-test (npm launcher)'];
    checks.forEach((c) => lines.push(`  [${c.ok ? 'PASS' : 'FAIL'}] ${c.name}: ${c.detail}`));
    lines.push(`  artifacts: ${workdir}`);
    lines.push(`result: ${ok ? 'all checks passed' : 'FAILED'}`);
    process.stdout.write(lines.join('\n') + '\n');
  }
  process.exit(ok ? 0 : 1);
}

function main() {
  const argv = process.argv.slice(2);
  const command = argv[0];
  const rest = argv.slice(1);

  if (!command || command === '-h' || command === '--help' || command === 'help') {
    process.stdout.write(USAGE);
    return;
  }
  if (command === '--version' || command === 'version' || command === '-V') {
    const native = locate.nativeBinary() ? nativeDoctor() : null;
    const state = native && native.ok ? 'native' : 'native unavailable';
    process.stdout.write(
      `ncel ${locate.PACKAGE_VERSION} (npm launcher, native runtime ${(native && native.version) || locate.NATIVE_RUNTIME_VERSION}, ` +
        `spec ${locate.SPEC_VERSION}, ${state})\n`
    );
    return;
  }
  if (command === 'doctor') return doctor(rest.includes('--json'));
  if (command === 'verify') return verify(rest);

  if (command === 'guide') {
    process.stdout.write(fs.readFileSync(path.join(DATA, 'AGENT-GUIDE.md'), 'utf8'));
    return;
  }
  if (command === 'fmt') {
    fail(
      'ncel: `fmt` is provided by the Python reference (`northcel`); the native runtime has no\n' +
        'ncel: formatter and the npm package does not ship one. Install it with\n' +
        'ncel:   pip install northcel==0.2.1 && python -m northcel fmt FILE',
      1
    );
  }
  if (['check', 'info', 'render', 'film'].includes(command)) {
    return passthrough(command, rest.filter((a) => a !== '--no-native'));
  }

  fail(`ncel: unknown command ${JSON.stringify(command)}\n\n` + USAGE, 2);
}

main();
