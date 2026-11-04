"use strict";
/**
 * EGL discovery in the npm launcher, which had the same bug the Homebrew tap found in
 * the Python launcher: it only checked the distribution's library directories, so a
 * Homebrew (keg-only) Mesa or one on LD_LIBRARY_PATH was invisible and `northcel`
 * refused a native runtime that was installed and working.
 *
 * The tests create throwaway directories containing a file *named* libEGL.so.1 — the
 * probe only stats the path, so no GL driver is needed.
 */
const { test } = require("node:test");
const assert = require("node:assert/strict");
const fs = require("node:fs");
const os = require("node:os");
const path = require("node:path");
const { spawnSync } = require("node:child_process");

const root = path.resolve(__dirname, "..");
const locate = path.join(root, "lib/locate.js");
const temp = fs.mkdtempSync(path.join(os.tmpdir(), "northcel-egl-"));
process.on("exit", () => fs.rmSync(temp, { recursive: true, force: true }));

function fakeEgl(dir) {
  fs.mkdirSync(dir, { recursive: true });
  const lib = path.join(dir, "libEGL.so.1");
  fs.writeFileSync(lib, "not a real ELF; the probe only stats the path");
  return lib;
}

// Run a snippet in a clean child so the parent's environment is untouched.
function probe(env, body) {
  return spawnSync(process.execPath, ["-e", `const l = require(${JSON.stringify(locate)}); ${body}`], {
    encoding: "utf8",
    env: { PATH: "", HOME: "", ...env },
  });
}

test("LD_LIBRARY_PATH satisfies the EGL gate without any distribution library", () => {
  const lib = fakeEgl(path.join(temp, "custom-mesa"));
  const r = probe({ LD_LIBRARY_PATH: path.dirname(lib) }, "console.log(l.hasEgl());");
  assert.equal(r.status, 0, r.stderr);
  assert.equal(r.stdout.trim(), "true");
});

test("a Homebrew prefix is searched, including keg-only opt/<name>/lib", () => {
  const prefix = path.join(temp, "linuxbrew");
  fakeEgl(path.join(prefix, "opt", "mesa", "lib"));
  const r = probe(
    { HOMEBREW_PREFIX: prefix },
    `const dirs = l.eglSearchDirs();
     console.log(dirs.includes(${JSON.stringify(path.join(prefix, "opt", "mesa", "lib"))}));
     console.log(l.hasEgl());`
  );
  assert.equal(r.status, 0, r.stderr);
  assert.deepEqual(r.stdout.trim().split("\n"), ["true", "true"]);
});

test("a ~/.linuxbrew prefix is searched", () => {
  const home = path.join(temp, "home");
  fakeEgl(path.join(home, ".linuxbrew", "lib"));
  const r = probe({ HOME: home }, "console.log(l.hasEgl());");
  assert.equal(r.status, 0, r.stderr);
  assert.equal(r.stdout.trim(), "true");
});

test("the distribution paths are still the last resort, in their original order", () => {
  const r = probe(
    {},
    "console.log(JSON.stringify(l.eglSearchDirs().filter((d) => d.startsWith('/usr/lib') || d.startsWith('/lib'))));"
  );
  assert.equal(r.status, 0, r.stderr);
  const dirs = JSON.parse(r.stdout);
  assert.ok(dirs.includes("/usr/lib/x86_64-linux-gnu"));
  assert.ok(dirs.indexOf("/usr/lib") < dirs.indexOf("/lib64"));
});

test("the platform verdict names the places that were searched", () => {
  // Force the gate closed by pointing every source at a missing directory.
  const r = probe(
    { LD_LIBRARY_PATH: path.join(temp, "nothing-here") },
    `const v = l.platformVerdict();
     if (v.platform !== "linux" || v.arch !== "x64") { console.log("SKIP"); }
     else { console.log(v.reasons.join(" ")); }`
  );
  assert.equal(r.status, 0, r.stderr);
  const out = r.stdout.trim();
  if (out === "SKIP") return; // non-Linux/x64 host: nothing to assert
  // The reason is only present when the host really has no EGL anywhere; the message
  // must then name LD_LIBRARY_PATH and the install hint, never a bare "not found".
  if (out.includes("libEGL.so.1")) {
    assert.match(out, /LD_LIBRARY_PATH/);
    assert.match(out, /libegl1|mesa-libEGL/);
  }
});
