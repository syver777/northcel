// NorthCel native runtime - ring-chain decoders.
// Implements the three normative encodings: 0.25px relative, 1px Base-63 and
// 0.25px-b63 (added in 0.2). Error text follows the reference decoder.

///| Base-63 alphabet (index -> delta = index - 31).
let b63_alphabet : String = "0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz_"

///| Split a string on any run of ASCII whitespace (Python's str.split()).
fn split_whitespace(s : String) -> Array[String] {
  let chars = s.to_array()
  let out : Array[String] = []
  let mut i = 0
  while i < chars.length() {
    while i < chars.length() && (chars[i] == ' ' || chars[i] == '\t' || chars[i] == '\r' || chars[i] == '\n') {
      i = i + 1
    }
    let start = i
    while i < chars.length() && !(chars[i] == ' ' || chars[i] == '\t' || chars[i] == '\r' || chars[i] == '\n') {
      i = i + 1
    }
    if i > start {
      out.push(String::from_array(chars[start:i]))
    }
  }
  out
}

///| Decode a `0.25px` relative delta chain (`x0,y0 dx,dy ...`).
fn decode_ring_q25(s : String, line : Int, col : Int) -> Array[(Double, Double)] raise NcelError {
  let trimmed = s.trim().to_owned()
  if trimmed.length() == 0 {
    raise mkerr(line, col, "Empty quarter-pixel ring string.")
  }
  let tokens = split_whitespace(trimmed)
  let pts : Array[(Double, Double)] = []
  let mut x = 0
  let mut y = 0
  for idx in 0..<tokens.length() {
    let tok = tokens[idx]
    match tok.find(",") {
      None => raise mkerr(line, col, "Expected 'dx,dy' pair at token " + idx.to_string() + " ('" + tok + "').")
      Some(ci) => {
        let dxs = tok.substring(start=0, end=ci)
        let dys = tok.substring(start=ci + 1, end=tok.length())
        let dx = try {
          @string.parse_int(dxs)
        } catch {
          _ => raise mkerr(line, col, "Non-integer quarter-pixel delta '" + tok + "'.")
        }
        let dy = try {
          @string.parse_int(dys)
        } catch {
          _ => raise mkerr(line, col, "Non-integer quarter-pixel delta '" + tok + "'.")
        }
        x = x + dx
        y = y + dy
        pts.push((x.to_double() * 0.25, y.to_double() * 0.25))
      }
    }
  }
  if pts.length() < 3 {
    raise mkerr(line, col, "Decoded ring has only " + pts.length().to_string() + " vertices (< 3).")
  }
  pts
}

///| Map one Base-63 character to its delta (-31..31), or None.
fn b63_value(c : Char) -> Int? {
  for i in 0..<b63_alphabet.length() {
    if b63_alphabet.get_char(i).unwrap() == c {
      return Some(i - 31)
    }
  }
  None
}

///| Decode a Base-63 relative chain (`x0,y0:c1c2...`) with the given inverse scale.
fn decode_ring_b63(s : String, inv_scale : Double, line : Int, col : Int) -> Array[(Double, Double)] raise NcelError {
  let trimmed = s.trim().to_owned()
  match trimmed.find(":") {
    None => raise mkerr(line, col, "Base-63 ring string must contain ':' after 'x0,y0'.")
    Some(ci) => {
      let head = trimmed.substring(start=0, end=ci)
      let tail = trimmed.substring(start=ci + 1, end=trimmed.length())
      match head.find(",") {
        None => raise mkerr(line, col, "Base-63 ring header must be 'x0,y0'.")
        Some(hci) => {
          let x0s = head.substring(start=0, end=hci)
          let y0s = head.substring(start=hci + 1, end=head.length())
          let mut x = try {
            @string.parse_int(x0s)
          } catch {
            _ => raise mkerr(line, col, "Invalid Base-63 start coordinates '" + head + "'.")
          }
          let mut y = try {
            @string.parse_int(y0s)
          } catch {
            _ => raise mkerr(line, col, "Invalid Base-63 start coordinates '" + head + "'.")
          }
          if tail.length() % 2 != 0 {
            raise mkerr(line, col, "Base-63 delta tail must have an even number of characters.")
          }
          let pts : Array[(Double, Double)] = [(x.to_double() * inv_scale, y.to_double() * inv_scale)]
          let mut i = 0
          while i < tail.length() {
            let c1 = tail.get_char(i).unwrap()
            let c2 = tail.get_char(i + 1).unwrap()
            let d1 = match b63_value(c1) {
              Some(v) => v
              None => raise mkerr(line, col, "Invalid Base-63 character pair '" + c1.to_string() + c2.to_string() + "' at offset " + i.to_string() + ".")
            }
            let d2 = match b63_value(c2) {
              Some(v) => v
              None => raise mkerr(line, col, "Invalid Base-63 character pair '" + c1.to_string() + c2.to_string() + "' at offset " + i.to_string() + ".")
            }
            x = x + d1
            y = y + d2
            pts.push((x.to_double() * inv_scale, y.to_double() * inv_scale))
            i = i + 2
          }
          if pts.length() < 3 {
            raise mkerr(line, col, "Decoded Base-63 ring has only " + pts.length().to_string() + " vertices (< 3).")
          }
          pts
        }
      }
    }
  }
}

///| Decode a `|`-separated multi-ring payload according to the scene precision.
fn decode_rings_payload(payload : String, precision : String, line : Int, col : Int) -> Array[Array[(Double, Double)]] raise NcelError {
  let raw = payload.trim().to_owned()
  let rings : Array[Array[(Double, Double)]] = []
  if raw.length() == 0 {
    return rings
  }
  let parts = raw.split("|")
  let mut idx = 0
  for part in parts {
    let part_s = part.trim().to_owned()
    if part_s.length() > 0 {
      let has_colon = part_s.find(":") is Some(_)
      let has_space = part_s.find(" ") is Some(_)
      // Re-wrap ring-level errors with the ring index, like the reference decoder.
      let res = try_decode(fn () {
        if has_colon && !has_space {
          if precision == "0.25px-b63" {
            decode_ring_b63(part_s, 0.25, line, col)
          } else {
            decode_ring_b63(part_s, 1.0, line, col)
          }
        } else if precision == "1px" && has_colon {
          decode_ring_b63(part_s, 1.0, line, col)
        } else {
          decode_ring_q25(part_s, line, col)
        }
      })
      match res {
        Ok(r) => rings.push(r)
        Err(msg) => raise mkerr(line, col, "Ring " + idx.to_string() + ": " + msg)
      }
    }
    idx = idx + 1
  }
  rings
}

///| Tiny Result re-wrap so ring errors can be prefixed with their index.
enum RingRes {
  Ok(Array[(Double, Double)])
  Err(String)
}

///| Result wrapper for a full payload decode.
enum RingsRes {
  OkRings(Array[Array[(Double, Double)]])
  ErrRings(String)
}

///| Run a payload decoder and capture its message.
fn try_decode_rings(f : () -> Array[Array[(Double, Double)]] raise NcelError) -> RingsRes {
  try {
    OkRings(f())
  } catch {
    NcelError(d) => ErrRings(d.msg)
  }
}

///| Run a decoder and capture its message (used for ring-index prefixes).
fn try_decode(f : () -> Array[(Double, Double)] raise NcelError) -> RingRes {
  try {
    Ok(f())
  } catch {
    NcelError(d) => Err(d.msg)
  }
}
