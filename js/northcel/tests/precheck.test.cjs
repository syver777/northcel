"use strict";
const { test } = require("node:test");
const assert = require("node:assert/strict");
const fs = require("node:fs");
const os = require("node:os");
const path = require("node:path");
const { spawnSync } = require("node:child_process");
const { checkNcelSource, decodeRingQ25, decodeRingB63, decodeRingsPayload, CONFIG } = require("../js/index.cjs");
const root = path.resolve(__dirname, "..");
const repo = path.resolve(root, "../..");
const cli = path.join(root, "bin/northcel.js");
const temp = fs.mkdtempSync(path.join(os.tmpdir(), "northcel-js-"));
const valid = path.join(temp, "valid.ncel");
const invalid = path.join(temp, "invalid.ncel");
fs.writeFileSync(valid, "film Good(frames: 36, fps: 12) {}");
fs.writeFileSync(invalid, "film B { frames: 2 }");
process.on("exit", () => fs.rmSync(temp, { recursive: true, force: true }));

function run(args, env = {}) {
  return spawnSync(process.execPath, [cli, ...args], {
    encoding: "utf8", env: { ...process.env, PYTHONPATH: "", PATH: temp, ...env },
  });
}

test("JS API never claims full validation, even for failures", () => {
  for (const src of ["film F {}", "", "film B { frames: 2 }"]) {
    const r = checkNcelSource(src);
    assert.equal(r.partial, true); assert.equal(r.validator, "js");
    assert.ok(r.reason); assert.match(r.next, /--require-full/);
  }
  assert.match(checkNcelSource("film B { frames: 2 }").errors[0], /1:10: error: Unknown film statement 'frames'/);
});

test("Node-only CLI text/JSON and require-full exit contract", () => {
  const r = run(["check", valid]);
  assert.equal(r.status, 0); assert.match(r.stdout, /PARTIAL/); assert.doesNotMatch(r.stdout, /\bOK\b/);
  for (const flags of [[], ["--require-full"]]) {
    const good = run(["check", valid, "--json", ...flags]);
    assert.equal(good.status, flags.length ? 2 : 0);
    const json = JSON.parse(good.stdout);
    assert.equal(json.partial, true); assert.equal(json.validator, "js");
    assert.equal(json.ok, true); assert.equal(json.exit_code, good.status);
    const bad = run(["check", "--json", invalid, ...flags]);
    assert.equal(bad.status, 1); assert.equal(JSON.parse(bad.stdout).ok, false);
  }
});

test("Node-only invalid arguments, I/O errors and missing renderer never pass", () => {
  for (const args of [["check"], ["check", valid, "extra"], ["check", "--typo"], ["check", valid, "--typo"]]) {
    assert.equal(run(args).status, 2);
  }
  for (const file of [path.join(temp, "missing.ncel"), temp]) {
    const r = run(["check", file, "--json"]);
    assert.equal(r.status, 1); assert.equal(JSON.parse(r.stdout).partial, true);
  }
  for (const command of ["render", "film", "fmt"]) assert.equal(run([command, valid]).status, 1);
  assert.equal(run(["--version"]).status, 0);
  assert.match(run(["--version"]).stdout, /0\.2\.1.*js-validator/);
  assert.equal(run(["check", "--help"]).status, 0);
});

test("guide is offline and exactly the generated canonical section", () => {
  const r = run(["guide"]);
  assert.equal(r.status, 0);
  assert.equal(r.stdout, fs.readFileSync(path.join(root, "northcel/AGENT-GUIDE.md"), "utf8"));
  assert.match(r.stdout, /Five language features/);
  assert.equal(run(["guide", "--typo"]).status, 2);
});

test("Python delegation preserves diagnostics and nonzero status; flag stripped for old CLI", () => {
  const fake = path.join(temp, "fake-python");
  fs.mkdirSync(fake);
  fs.writeFileSync(path.join(fake, "python3"), '#!/bin/sh\nif [ "$1" = "-c" ]; then exit 0; fi\nprintf "%s\\n" "$@"\nprintf "authoritative diagnostic\\n" >&2\nexit 17\n', { mode: 0o755 });
  const r = run(["check", invalid, "--require-full", "--json"], { PATH: fake });
  assert.equal(r.status, 17); assert.match(r.stderr, /authoritative diagnostic/);
  assert.doesNotMatch(r.stdout, /--require-full|PARTIAL/);
  fs.writeFileSync(path.join(fake, "python3"), '#!/bin/sh\nif [ "$1" = "-c" ]; then exit 0; fi\nkill -TERM $$\n', { mode: 0o755 });
  const killed = run(["check", valid], { PATH: fake });
  assert.equal(killed.status, 1); assert.match(killed.stderr, /did not finish/);
});

test("actual Python reference check delegates, not JS fallback", () => {
  const pythonPath = spawnSync("python3", ["-c", "import os,sys;print(os.path.dirname(sys.executable))"], { encoding: "utf8" });
  assert.equal(pythonPath.status, 0);
  for (const [file, code] of [[valid, 0], [invalid, 1]]) {
    const r = run(["check", file, "--require-full", "--json"], { PATH: pythonPath.stdout.trim(), PYTHONPATH: root });
    assert.equal(r.status, code, r.stderr);
    const data = JSON.parse(r.stdout);
    assert.equal(data.partial, false); assert.equal(data.validator, "python");
  }
});

test("pipx-style Python entrypoint on PATH delegates without a Python executable on PATH", () => {
  const scripts = path.join(temp, "pipx-bin");
  fs.mkdirSync(scripts);
  const py = spawnSync("python3", ["-c", "import sys;print(sys.executable)"], { encoding: "utf8" }).stdout.trim();
  fs.writeFileSync(path.join(scripts, "northcel"), `#!${py}\nimport sys\nsys.path.insert(0, ${JSON.stringify(root)})\nfrom northcel.cli import main\nraise SystemExit(main())\n`, { mode: 0o755 });
  const r = run(["check", valid, "--require-full", "--json"], { PATH: scripts });
  assert.equal(r.status, 0, r.stderr);
  assert.equal(JSON.parse(r.stdout).validator, "python");
  // The npm aliases may both be on PATH; neither may recurse into this bridge.
  fs.symlinkSync(cli, path.join(scripts, "ncel"));
  fs.unlinkSync(path.join(scripts, "northcel"));
  fs.symlinkSync(cli, path.join(scripts, "northcel"));
  assert.equal(run(["check", valid, "--require-full", "--json"], { PATH: scripts }).status, 2);
});

const badCases = {
  "missing root": 'northcel "0.2.0-draft"',
  "unclosed brace": "film F {",
  "extra brace": "film F {} }",
  "unclosed quote": 'film F { layer a() { "0,0 4,0 0,4 } }',
  "wrong scene statement": "scene F { frame 1 {} }",
  "wrong film statement": "film F { frames: 2 }",
  "wrong frame statement": "film F { frame 1 { fps: 6 } }",
  "wrong def statement": "film F { def X { use Y } }",
  "malformed frames header": "film F(frames 2) {}",
  "malformed frames value": "film F(frames:) {}",
  "malformed palette header": "film F { palette Named { ink: #000 } }",
  "malformed palette entry": "film F { palette { ink #000 } }",
  "malformed cel header": 'film F { cel a { "0,0 4,0 0,4" } }',
  "malformed stroke header": "film F { stroke a { (0,0), (1,1) } }",
  "malformed ribbon header": "film F { ribbon (color: #000) { (0,0,1) } }",
  "malformed def header": "film F { def (dx: 0) {} }",
  "malformed use header": "film F { use (dx: 0) }",
  "illegal use body": "film F { use A {} }",
  "wrong stroke point": "film F { stroke a() { (0,0,1), (1,1,1) } }",
  "wrong ribbon point": "film F { ribbon a { (0,0), (1,1) } }",
  "bad decimal delta": 'film F { cel a() { "0,0 4.5,0 0,4" } }',
  "bad suffix delta": 'film F { cel a() { "0,0 4px,0 0,4" } }',
  "bad b63 character": 'film F { cel a() { "0,0:AA??" } }',
  "odd b63 tail": 'film F { cel a() { "0,0:AAA" } }',
  "bad b63 origin": 'film F { cel a() { "0x,0:AAAA" } }',
  "too few vertices": 'film F { cel a() { "0,0 4,0" } }',
  "unknown palette": 'film F { cel a(color: $missing) { "0,0 4,0 0,4" } }',
  "palette before declaration": 'film F { cel a(color: $ink) { "0,0 4,0 0,4" } palette { ink: #000 } }',
  "frame palette leak": 'film F { frame 1 { palette { local: #000 } } cel a(color: $local) { "0,0 4,0 0,4" } }',
  "unsupported spec": 'northcel "9.9" film F {}',
};
for (const [name, src] of Object.entries(badCases)) test(`structural regression: ${name}`, () => {
  const r = checkNcelSource(src);
  assert.equal(r.ok, false, JSON.stringify(r));
  assert.match(r.errors[0], /^\d+:\d+: error:/);
});

test("duplicate primitive names warn without banning replacement or frame overrides", () => {
  const r = checkNcelSource('film F { cel a() { "0,0 4,0 0,4" } cel a() { "0,0 8,0 0,8" } frame 1 { cel a() { "0,0 4,0 0,4" } } }');
  assert.equal(r.ok, true); assert.equal(r.warnings.length, 1);
});

test("pre-check deliberately leaves semantic validation to Python", () => {
  const r = checkNcelSource("film F(fps: 0, width: -10) { use Missing stroke s(width: -2) { (unknown, 0) } }");
  assert.equal(r.ok, true); assert.equal(r.partial, true);
});

test("ring decoders reject parseInt truncation and retain precision dispatch", () => {
  assert.throws(() => decodeRingQ25("0,0 4x,0 0,4"));
  assert.throws(() => decodeRingB63("0x,0:AAAA"));
  assert.deepEqual(decodeRingsPayload("4,8:WVWX", "0.25px-b63")[0][0], [1, 2]);
  assert.deepEqual(decodeRingsPayload("4,8:WVWX", "1px")[0][0], [4, 8]);
});

test("comments and escaped quotes are not structural delimiters", () => {
  assert.equal(checkNcelSource('// film Fake {\nfilm F { // }\n paper { color: #FFF }\n }').ok, true);
  assert.equal(checkNcelSource('film F(note: "// escaped \\\" { }") {}').ok, true);
});

// Every checked-in example/conformance file, not a manually selected subset.
const examples = spawnSync("git", ["ls-files", "*.ncel"], { cwd: repo, encoding: "utf8" });
assert.equal(examples.status, 0);
for (const file of examples.stdout.trim().split("\n").filter(Boolean)) {
  test(`repo example + broken variants: ${file}`, () => {
    const src = fs.readFileSync(path.join(repo, file), "utf8");
    assert.equal(checkNcelSource(src).ok, true);
    assert.equal(checkNcelSource(src + " }").ok, false);
    assert.equal(checkNcelSource(src.replace(/\b(scene|film)\s+\w+/, "broken Root")).ok, false);
    assert.equal(checkNcelSource(src.replace(/\{/, "{ unknown_stmt: 2 ")).ok, false);
    assert.equal(checkNcelSource(src.slice(0, src.lastIndexOf("}"))).ok, false);
  });
}

test("generated rule/guide freshness and version parity", () => {
  const r = spawnSync("python3", [path.join(root, "scripts/sync-assets.py"), "--check"], { encoding: "utf8" });
  assert.equal(r.status, 0, r.stderr);
  assert.equal(CONFIG.PACKAGE_VERSION, require("../package.json").version);
});
