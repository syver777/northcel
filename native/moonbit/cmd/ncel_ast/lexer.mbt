// NorthCel native runtime - lexer.
// Token classes and maximal-munch rules mirror the NorthCel 0.2 reference
// lexer exactly (including the signed-number and Base-63 unit edge cases).

///| One source token. `value` keeps the raw text (strings include their quotes).
struct Token {
  kind : String
  value : String
  line : Int
  col : Int
}

///| ASCII decimal digit test.
fn is_digit(c : Char) -> Bool {
  c >= '0' && c <= '9'
}

///| ASCII hexadecimal digit test.
fn is_hex_digit(c : Char) -> Bool {
  (c >= '0' && c <= '9') || (c >= 'a' && c <= 'f') || (c >= 'A' && c <= 'F')
}

///| Identifier / word-boundary character test.
fn is_word_char(c : Char) -> Bool {
  (c >= 'a' && c <= 'z') || (c >= 'A' && c <= 'Z') || (c >= '0' && c <= '9') || c == '_'
}

///| Identifier start test.
fn is_ident_start(c : Char) -> Bool {
  (c >= 'a' && c <= 'z') || (c >= 'A' && c <= 'Z') || c == '_'
}

///| Does `lit` occur in `chars` starting at `pos`?
fn matches_at(chars : Array[Char], pos : Int, lit : String) -> Bool {
  let l = lit.length()
  if pos + l > chars.length() {
    return false
  }
  for k in 0..<l {
    if chars[pos + k] != lit.get_char(k).unwrap() {
      return false
    }
  }
  true
}

///| Tokenize a NorthCel source string. Raises a line:column diagnostic on bad input.
fn lex(source : String) -> Array[Token] raise NcelError {
  let chars = source.to_array()
  let n = chars.length()
  let out : Array[Token] = []
  let mut i = 0
  let mut line = 1
  let mut line_start = 0
  while i < n {
    let c = chars[i]
    if c == ' ' || c == '\t' || c == '\r' {
      i = i + 1
      continue
    }
    if c == '\n' {
      line = line + 1
      i = i + 1
      line_start = i
      continue
    }
    if c == '/' && i + 1 < n && chars[i + 1] == '/' {
      while i < n && chars[i] != '\n' {
        i = i + 1
      }
      continue
    }
    let col = i - line_start + 1
    if c == '"' {
      let start = i
      i = i + 1
      let mut closed = false
      while i < n {
        let d = chars[i]
        if d == '\\' {
          i = i + 2
          continue
        }
        if d == '"' {
          i = i + 1
          closed = true
          break
        }
        i = i + 1
      }
      if !closed {
        raise NcelError({ line: line, col: col, msg: "Unexpected character '\"'" })
      }
      out.push({ kind: "STRING", value: String::from_array(chars[start:i]), line: line, col: col })
      continue
    }
    if c == '#' {
      let start = i
      let mut j = i + 1
      let mut count = 0
      while j < n && count < 6 && is_hex_digit(chars[j]) {
        j = j + 1
        count = count + 1
      }
      let bounded = j >= n || !is_word_char(chars[j])
      if count >= 3 && bounded {
        out.push({ kind: "HEX", value: String::from_array(chars[start:j]), line: line, col: col })
        i = j
      } else {
        out.push({ kind: "PUNCT", value: "#", line: line, col: col })
        i = i + 1
      }
      continue
    }
    if is_digit(c) || (c == '-' && i + 1 < n && is_digit(chars[i + 1])) {
      let start = i
      let mut j = i
      if chars[j] == '-' {
        j = j + 1
      }
      while j < n && is_digit(chars[j]) {
        j = j + 1
      }
      if j + 1 < n && chars[j] == '.' && is_digit(chars[j + 1]) {
        j = j + 1
        while j < n && is_digit(chars[j]) {
          j = j + 1
        }
      }
      // Unit suffix (must end on a word boundary, like the reference regex).
      let mut unit_len = 0
      let probe = j
      if matches_at(chars, probe, "px-b63") && (probe + 6 >= n || !is_word_char(chars[probe + 6])) {
        unit_len = 6
      } else if matches_at(chars, probe, "px") && (probe + 2 >= n || !is_word_char(chars[probe + 2])) {
        unit_len = 2
      } else if matches_at(chars, probe, "deg") && (probe + 3 >= n || !is_word_char(chars[probe + 3])) {
        unit_len = 3
      }
      if unit_len > 0 {
        out.push({ kind: "UNIT", value: String::from_array(chars[start:j + unit_len]), line: line, col: col })
        i = j + unit_len
      } else {
        out.push({ kind: "NUMBER", value: String::from_array(chars[start:j]), line: line, col: col })
        i = j
      }
      continue
    }
    if is_ident_start(c) {
      let start = i
      while i < n && is_word_char(chars[i]) {
        i = i + 1
      }
      out.push({ kind: "IDENT", value: String::from_array(chars[start:i]), line: line, col: col })
      continue
    }
    let punct = "{}()[]:,;+-*/=$"
    if punct.contains_char(c) {
      out.push({ kind: "PUNCT", value: c.to_string(), line: line, col: col })
      i = i + 1
      continue
    }
    raise NcelError({ line: line, col: col, msg: "Unexpected character '" + c.to_string() + "'" })
  }
  out.push({ kind: "EOF", value: "", line: line, col: i - line_start + 1 })
  out
}
