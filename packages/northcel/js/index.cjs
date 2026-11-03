"use strict";

/**
 * Pure JavaScript parser, validator, and formatter for NorthCel (.ncel) v0.1.0-draft.
 * Zero external dependencies.
 */

const CONFIG = Object.freeze({
  LANGUAGE_NAME: "NorthCel",
  FILE_EXTENSION: ".ncel",
  CLI_COMMAND: "northcel",
  CLI_SHORT_ALIAS: "ncel",
  PACKAGE_VERSION: "0.2.0",
  SPEC_VERSION: "0.2.0-draft",
  SUPPORTED_SPEC_VERSIONS: ["0.1", "0.1.0", "0.1.0-draft", "0.2", "0.2.0", "0.2.0-draft"],
  DOCS_URL: "https://northnoir.com/northcel",
});

const B63_ALPHABET = "0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz_";
const B63_MAP = new Map([...B63_ALPHABET].map((ch, i) => [ch, i - 31]));

function decodeRingQ25(ringStr) {
  const s = ringStr.trim();
  if (!s) throw new Error("Empty quarter-pixel ring string.");
  const tokens = s.split(/\s+/);
  let x = 0;
  let y = 0;
  const pts = [];
  for (let i = 0; i < tokens.length; i++) {
    const tok = tokens[i];
    const comma = tok.indexOf(",");
    if (comma === -1) throw new Error(`Expected 'dx,dy' at token ${i} ('${tok}')`);
    const dx = Number.parseInt(tok.slice(0, comma), 10);
    const dy = Number.parseInt(tok.slice(comma + 1), 10);
    if (Number.isNaN(dx) || Number.isNaN(dy)) {
      throw new Error(`Non-integer quarter-pixel delta '${tok}'`);
    }
    x += dx;
    y += dy;
    pts.push([x * 0.25, y * 0.25]);
  }
  if (pts.length < 3) throw new Error(`Decoded ring has only ${pts.length} vertices (< 3).`);
  return pts;
}

function decodeRingB63(ringStr) {
  const s = ringStr.trim();
  const colon = s.indexOf(":");
  if (colon === -1) throw new Error("Base-63 ring string must contain ':' after 'x0,y0'.");
  const head = s.slice(0, colon);
  const tail = s.slice(colon + 1);
  const comma = head.indexOf(",");
  if (comma === -1) throw new Error("Base-63 ring header must be 'x0,y0'.");
  let x = Number.parseInt(head.slice(0, comma), 10);
  let y = Number.parseInt(head.slice(comma + 1), 10);
  if (Number.isNaN(x) || Number.isNaN(y)) throw new Error(`Invalid Base-63 start '${head}'`);
  if (tail.length % 2 !== 0) throw new Error("Base-63 tail must have even length.");
  const pts = [[x, y]];
  for (let i = 0; i < tail.length; i += 2) {
    const dx = B63_MAP.get(tail[i]);
    const dy = B63_MAP.get(tail[i + 1]);
    if (dx === undefined || dy === undefined) {
      throw new Error(`Invalid Base-63 pair '${tail.slice(i, i + 2)}'`);
    }
    x += dx;
    y += dy;
    pts.push([x, y]);
  }
  if (pts.length < 3) throw new Error(`Decoded Base-63 ring has only ${pts.length} vertices (< 3).`);
  return pts;
}

function decodeRingsPayload(payload, precision = "0.25px") {
  const raw = payload.trim();
  if (!raw) return [];
  return raw
    .split("|")
    .map((p) => p.trim())
    .filter(Boolean)
    .map((part) => {
      if (part.includes(":") && !part.includes(" ")) {
        if (precision === "0.25px-b63") {
          return decodeRingB63(part).map(([x, y]) => [x * 0.25, y * 0.25]);
        }
        return decodeRingB63(part);
      }
      if (precision === "1px" && part.includes(":")) return decodeRingB63(part);
      return decodeRingQ25(part);
    });
}

function checkNcelSource(source) {
  const errors = [];
  const warnings = [];
  const lines = source.split(/\r?\n/);
  let hasRoot = false;
  let specVersion = CONFIG.SPEC_VERSION;

  const verMatch = source.match(/^\s*northcel\s+"([^"]+)"/);
  if (verMatch) {
    specVersion = verMatch[1];
    if (!CONFIG.SUPPORTED_SPEC_VERSIONS.includes(specVersion)) {
      errors.push(`1:1: error: Unsupported NorthCel version '${specVersion}'`);
    }
  }

  for (let idx = 0; idx < lines.length; idx++) {
    const lineNo = idx + 1;
    const raw = lines[idx].replace(/\/\/.*$/, "").trim();
    if (!raw) continue;
    if (/^(scene|film)\s+[A-Za-z_][A-Za-z0-9_]*/.test(raw)) {
      hasRoot = true;
    }
    const payloadMatch = raw.match(/^(layer|wash|bend_swarm|swarm)\s+([A-Za-z_][A-Za-z0-9_]*)\(([^)]*)\)\s*\{\s*"([^"]*)"\s*\}/);
    if (payloadMatch) {
      const name = payloadMatch[2];
      const payload = payloadMatch[4];
      try {
        const rings = decodeRingsPayload(payload);
        if (rings.length === 0) {
          errors.push(`${lineNo}:1: error: Block '${name}' decoded to 0 rings`);
        }
      } catch (err) {
        errors.push(`${lineNo}:1: error: Block '${name}' invalid ring payload: ${err.message}`);
      }
    }
  }

  if (!hasRoot) {
    errors.push("1:1: error: Missing 'scene' or 'film' root declaration");
  }
  return { ok: errors.length === 0, specVersion, errors, warnings };
}

module.exports = {
  CONFIG,
  decodeRingQ25,
  decodeRingB63,
  decodeRingsPayload,
  checkNcelSource,
};
