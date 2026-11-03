#!/usr/bin/env node
"use strict";

const { spawnSync } = require("node:child_process");
const fs = require("node:fs");
const path = require("node:path");
const { CONFIG, checkNcelSource } = require("../js/index.cjs");

const args = process.argv.slice(2);

// Try delegating to the Python reference CLI if installed so `render` / `film` work seamlessly
for (const py of ["python3", "python"]) {
  const probe = spawnSync(py, ["-c", "import northcel.cli"], { stdio: "ignore" });
  if (probe.status === 0) {
    const run = spawnSync(py, ["-m", "northcel.cli", ...args], { stdio: "inherit" });
    process.exit(run.status ?? 0);
  }
}

// Fallback pure-JS CLI for --version and check
if (args.includes("--version") || args.includes("-v")) {
  console.log(`${CONFIG.CLI_COMMAND} ${CONFIG.PACKAGE_VERSION} (spec ${CONFIG.SPEC_VERSION}, js-validator)`);
  process.exit(0);
}

if (args[0] === "check" && args[1]) {
  const file = path.resolve(args[1]);
  if (!fs.existsSync(file)) {
    console.error(`${file}:1:1: error: File not found`);
    process.exit(1);
  }
  const res = checkNcelSource(fs.readFileSync(file, "utf8"));
  if (args.includes("--json")) {
    console.log(JSON.stringify({ ok: res.ok, file, spec_version: res.specVersion, errors: res.errors, warnings: res.warnings }, null, 2));
  } else if (res.ok) {
    console.log(`${file}: OK (${CONFIG.LANGUAGE_NAME} ${res.specVersion})`);
  } else {
    for (const err of res.errors) console.error(`${file}:${err}`);
  }
  process.exit(res.ok ? 0 : 1);
}

console.error("NorthCel JS fallback supports `check <file.ncel>` and `--version`. Install Python package `pip install northcel` for full `render` and `film` rasterization.");
process.exit(1);
