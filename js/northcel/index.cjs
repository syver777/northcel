"use strict";

// Zero-dependency structural PRE-CHECK, not the reference parser or renderer.
const rules = require("./rules.json");
const CONFIG = Object.freeze(rules.config);
const B63_ALPHABET = rules.b63_alphabet;
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
    if (!/^[+-]?\d+,[+-]?\d+$/.test(tok)) {
      throw new Error(`Non-integer quarter-pixel delta '${tok}'`);
    }
    const [dx, dy] = tok.split(",").map(Number);
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
  if (!/^[+-]?\d+,[+-]?\d+$/.test(head)) throw new Error(`Invalid Base-63 start '${head}'`);
  let [x, y] = head.split(",").map(Number);
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

class PrecheckError extends Error {
  constructor(token, message) {
    super(`${token.line}:${token.column}: error: ${message}`);
  }
}

// Same token classes/order as the reference lexer, without evaluation or ASTs.
function tokenize(source) {
  const re = /(?:[ \t\r]+)|(?:\n)|(?:\/\/[^\n]*)|(?:"(?:\\[\s\S]|[^"\\])*")|(?:#[0-9A-Fa-f]{3,6}\b)|(?:-?(?:\d+\.\d+|\d+)(?:px-b63|px|deg)\b)|(?:-?(?:\d+\.\d+|\d+))|(?:[A-Za-z_][A-Za-z0-9_]*)|(?:[{}()\[\]:,;+\-*/=$])/y;
  const out = [];
  let pos = 0, line = 1, column = 1;
  while (pos < source.length) {
    re.lastIndex = pos;
    const match = re.exec(source);
    const at = { line, column };
    if (!match) throw new PrecheckError(at, source[pos] === '"'
      ? "Unclosed quote" : `Unexpected character '${source[pos]}'`);
    const value = match[0];
    if (!/^\s|^\/\//.test(value)) {
      const kind = value[0] === '"' ? "string" : /^[A-Za-z_]/.test(value) ? "ident"
        : /^-?\d/.test(value) ? (/\d$/.test(value) ? "number" : "unit")
          : value[0] === "#" ? "hex" : "punct";
      out.push({ kind, value, ...at });
    }
    const lines = value.split("\n");
    column = lines.length > 1 ? lines.at(-1).length + 1 : column + value.length;
    line += lines.length - 1;
    pos += value.length;
  }
  out.push({ kind: "eof", value: "", line, column });
  return out;
}

class Precheck {
  constructor(tokens, result) { this.tokens = tokens; this.i = 0; this.result = result; }
  cur() { return this.tokens[this.i]; }
  take() { const t = this.cur(); if (t.kind !== "eof") this.i++; return t; }
  fail(message, at = this.cur()) { throw new PrecheckError(at, message); }
  match(value) { if (this.cur().value === value) { this.take(); return true; } return false; }
  expect(value) { if (!this.match(value)) this.fail(`Expected '${value}', got '${this.cur().value || "EOF"}'`); }
  kind(kind) { if (this.cur().kind !== kind) this.fail(`Expected ${kind}, got '${this.cur().value || "EOF"}'`); return this.take(); }
  warn(at, message) { this.result.warnings.push(`${at.line}:${at.column}: warning: ${message}`); }
  document() {
    if (this.match("northcel")) {
      const t = this.take();
      if (!["string", "number"].includes(t.kind)) this.fail("Expected version string or number", t);
      this.result.specVersion = t.kind === "string" ? t.value.slice(1, -1) : t.value;
      if (!CONFIG.SUPPORTED_SPEC_VERSIONS.includes(this.result.specVersion)) this.fail(`Unsupported NorthCel version '${this.result.specVersion}'`, t);
      this.match(";");
    }
    const root = this.take();
    if (!["scene", "film"].includes(root.value)) this.fail("Missing 'scene' or 'film' root declaration", root);
    this.kind("ident");
    // Deliberately no numeric/range evaluation: that belongs to Python.
    const attrs = this.cur().value === "(" ? this.attrs(new Set()) : {};
    const precision = attrs.precision?.[0]?.value || "0.25px";
    this.body(root.value, new Set(), precision);
    if (this.cur().kind !== "eof") this.fail(`Unexpected trailing token '${this.cur().value}'`);
  }
  body(scope, palette, precision) {
    this.expect("{");
    const names = new Set();
    while (!this.match("}")) {
      const t = this.kind("ident");
      if (!rules.statements[scope].includes(t.value)) this.fail(`Unknown ${scope} statement '${t.value}'`, t);
      if (t.value === "palette" || t.value === "paper") {
        const attrs = this.attrs(palette, true);
        if (t.value === "palette") for (const name of Object.keys(attrs)) palette.add(name);
      } else if (t.value === "frame") {
        this.kind("number");
        this.body("frame", new Set(palette), precision);
      } else if (t.value === "use" || t.value === "drop") {
        this.kind("ident");
        if (t.value === "use" && this.cur().value === "(") this.attrs(palette);
        this.match(";");
      } else {
        const name = this.kind("ident");
        if (t.value === "def") {
          if (this.cur().value === "(") this.attrs(palette);
          this.body("def", palette, precision);
          continue;
        }
        if (names.has(name.value)) this.warn(name, `Duplicate primitive name '${name.value}': layers/cels replace; strokes/ribbons append. Verify intent.`);
        names.add(name.value);
        if (this.cur().value === "(" || t.value !== "ribbon") this.attrs(palette);
        this.expect("{");
        if (["layer", "wash", "cel", "bend_swarm", "swarm"].includes(t.value)) {
          const payload = this.kind("string");
          try { decodeRingsPayload(payload.value.slice(1, -1), precision.replaceAll('"', "")); }
          catch (err) { this.fail(`Block '${name.value}' invalid ring payload: ${err.message}`, payload); }
        } else {
          this.points(t.value === "stroke" ? 2 : 3);
        }
        this.expect("}");
      }
    }
  }
  attrs(palette, braceAllowed = false) {
    const close = braceAllowed && this.match("{") ? "}" : (this.expect("("), ")");
    const attrs = Object.create(null);
    while (!this.match(close)) {
      const name = this.kind("ident");
      if (!(this.match(":") || (close === ")" && this.match("=")))) this.fail(`Expected ':' after attribute '${name.value}'`);
      const start = this.i;
      this.value(palette);
      attrs[name.value] = this.tokens.slice(start, this.i);
      this.match(","); // Reference parser also accepts omitted separators.
    }
    return attrs;
  }
  value(palette) {
    if (this.match("$")) {
      const ref = this.kind("ident");
      if (!palette.has(ref.value)) this.fail(`Undefined palette color '$${ref.value}'`, ref);
    } else if (["hex", "string", "unit"].includes(this.cur().kind)) this.take();
    else if (this.match("(")) {
      this.value(palette);
      while (this.match(",")) this.value(palette);
      this.expect(")");
    } else if (this.cur().value === "rgb") {
      this.take(); this.expect("(");
      this.expr(); this.expect(","); this.expr(); this.expect(","); this.expr(); this.expect(")");
    } else this.expr();
  }
  points(size) {
    while (this.cur().value !== "}") {
      this.expect("(");
      for (let j = 0; j < size; j++) { if (j) this.expect(","); this.expr(); }
      this.expect(")"); this.match(",");
    }
  }
  // Recognize expression shape only. No variable binding, function arity,
  // constant/range checking or execution (a partial check cannot promise those).
  expr() {
    this.term();
    while (["+", "-"].includes(this.cur().value)) { this.take(); this.term(); }
  }
  term() {
    this.factor();
    while (["*", "/"].includes(this.cur().value)) { this.take(); this.factor(); }
  }
  factor() {
    if (this.match("-")) return this.factor();
    if (["number", "unit"].includes(this.cur().kind)) { this.take(); return; }
    if (this.cur().kind === "ident") {
      this.take();
      if (this.match("(")) {
        if (!this.match(")")) {
          this.expr(); while (this.match(",")) this.expr(); this.expect(")");
        }
      }
    } else if (this.match("(")) { this.expr(); this.expect(")"); }
    else this.fail(`Expected expression, got '${this.cur().value || "EOF"}'`);
  }
}

function checkNcelSource(source) {
  const result = {
    ok: false, partial: true, validator: "js", specVersion: CONFIG.SPEC_VERSION,
    reason: "JS structural pre-check only; the Python reference parser/semantic validator did not run.",
    next: "Install `pipx install northcel`, expose that Python on PATH, then run `npx northcel check <file.ncel> --require-full`.",
    errors: [], warnings: [],
  };
  try { new Precheck(tokenize(source), result).document(); }
  catch (err) {
    if (!(err instanceof PrecheckError)) throw err;
    result.errors.push(err.message);
  }
  result.ok = result.errors.length === 0;
  return result;
}

module.exports = {
  CONFIG,
  decodeRingQ25,
  decodeRingB63,
  decodeRingsPayload,
  checkNcelSource,
};
