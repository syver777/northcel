#!/usr/bin/env node
"use strict";

const { spawnSync } = require("node:child_process");
const fs = require("node:fs");
const path = require("node:path");
const { CONFIG, checkNcelSource } = require("../js/index.cjs");

const args = process.argv.slice(2);

function delegate(command, prefix = []) {
  // Older Python releases already do a full check but don't know this flag.
  const forwarded = args[0] === "check" ? args.filter(a => a !== "--require-full") : args;
  const run = spawnSync(command, [...prefix, ...forwarded], { stdio: "inherit" });
  if (run.error || run.signal) console.error(`Python validator did not finish: ${run.error?.message || run.signal}`);
  process.exit(run.status ?? 1);
}

if (args[0] === "guide") {
  if (args.length !== 1) { console.error("Usage: northcel guide"); process.exit(2); }
  process.stdout.write(fs.readFileSync(path.join(__dirname, "../northcel/AGENT-GUIDE.md"), "utf8"));
  process.exit(0);
}

// Try delegating to the Python reference CLI if installed so `render` / `film` work seamlessly
for (const py of ["python3", "python"]) {
  const probe = spawnSync(py, ["-c", "import northcel.cli"], { stdio: "ignore" });
  if (probe.status === 0) {
    delegate(py, ["-m", "northcel.cli"]);
  }
}

// pipx exposes a Python entrypoint, not its environment's Python module. Find
// that script too, but never recurse into this npm bridge (including aliases).
for (const directory of (process.env.PATH || "").split(path.delimiter)) {
  for (const name of ["northcel", "ncel"]) {
    const candidate = path.resolve(directory || ".", name);
    try {
      if (fs.realpathSync(candidate) === fs.realpathSync(__filename)) continue;
      fs.accessSync(candidate, fs.constants.X_OK);
      const fd = fs.openSync(candidate, "r");
      const header = Buffer.alloc(256);
      let count;
      try { count = fs.readSync(fd, header, 0, header.length, 0); }
      finally { fs.closeSync(fd); }
      if (/^#![^\n]*\bpython[\d.]*(?:\s|$)/.test(header.toString("utf8", 0, count).split("\n", 1)[0])) delegate(candidate);
    } catch { /* Not a Python entrypoint; continue to the honest JS fallback. */ }
  }
}

// Fallback pure-JS CLI for --version and check
if (args.includes("--version") || args.includes("-v")) {
  console.log(`${CONFIG.CLI_COMMAND} ${CONFIG.PACKAGE_VERSION} (spec ${CONFIG.SPEC_VERSION}, js-validator)`);
  process.exit(0);
}

const help = "NorthCel npm: guide | check <file.ncel> [--json] [--require-full] | --version\nJS checks are PARTIAL. Install `pipx install northcel` for full validation, render, film, fmt and info.";
if (args.includes("--help") || args.includes("-h")) { console.log(help); process.exit(0); }

if (args[0] === "check") {
  const flags = new Set(["--json", "--require-full"]);
  const files = args.slice(1).filter(a => !flags.has(a));
  if (files.length !== 1 || files[0].startsWith("-")) { console.error(help); process.exit(2); }
  const file = path.resolve(files[0]);
  let res;
  try { res = checkNcelSource(fs.readFileSync(file, "utf8")); }
  catch (err) {
    // I/O failure is never a successful partial check; keep --json parseable.
    res = { ...checkNcelSource(""), ok: false, errors: [`1:1: error: Cannot read file (${err.code || err.name})`] };
  }
  const exitCode = !res.ok ? 1 : args.includes("--require-full") ? 2 : 0;
  if (args.includes("--json")) {
    const { specVersion, ...rest } = res;
    console.log(JSON.stringify({ ...rest, file, spec_version: specVersion, exit_code: exitCode }, null, 2));
  } else {
    console.log(`${file}: PARTIAL (JS pre-check only; ${res.ok ? "no pre-check errors found" : "errors found"} — install \`pipx install northcel\` for full validation)`);
    for (const warning of res.warnings) console.error(`${file}:${warning}`);
    for (const err of res.errors) console.error(`${file}:${err}`);
    if (exitCode === 2) console.error("Full validation required but unavailable. Expose Python northcel on PATH and repeat this command.");
  }
  process.exit(exitCode);
}

console.error(help);
process.exit(1);
