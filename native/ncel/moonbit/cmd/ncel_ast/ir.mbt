// NorthCel native runtime - IR writer, Bend/HVM2 swarm program generation and
// result ingestion.

///| Little-endian byte builder.
struct ByteBuf {
  data : Array[Byte]
}

///| New empty buffer.
fn ByteBuf::new() -> ByteBuf {
  { data: [] }
}

///| Append one byte.
fn ByteBuf::u8(self : ByteBuf, v : Int) -> Unit {
  let x = v & 0xFF
  self.data.push(x.to_byte())
}

///| Append a little-endian u32.
fn ByteBuf::u32(self : ByteBuf, v : Int) -> Unit {
  let x = v.to_int64()
  self.u8((x & 0xFF).to_int())
  self.u8(((x >> 8) & 0xFF).to_int())
  self.u8(((x >> 16) & 0xFF).to_int())
  self.u8(((x >> 24) & 0xFF).to_int())
}

///| Append a little-endian i32.
fn ByteBuf::i32(self : ByteBuf, v : Int) -> Unit {
  self.u32(v)
}

///| Append a little-endian u64.
fn ByteBuf::u64(self : ByteBuf, v : UInt64) -> Unit {
  for i in 0..<8 {
    self.u8(((v.shr(i * 8)) & 0xFFUL).to_int())
  }
}

///| Append a little-endian f64.
fn ByteBuf::f64(self : ByteBuf, v : Double) -> Unit {
  self.u64(v.reinterpret_as_uint64())
}

///| Append a length-prefixed UTF-8 string.
fn ByteBuf::str(self : ByteBuf, s : String) -> Unit {
  let b = @utf8.encode(s)
  self.u32(b.length())
  for i in 0..<b.length() {
    self.data.push(b.at(i))
  }
}

///| Finish the buffer as immutable bytes.
fn ByteBuf::finish(self : ByteBuf) -> Bytes {
  Bytes::from_array(self.data[:])
}

///| Build the edges and per-band spans for one layer (reference raster prep).
fn build_edges(layer : OutLayer, height : Int) -> (Array[(Double, Double, Double, Double)], Array[(Int, Int)]) {
  let edges : Array[(Double, Double, Double, Double)] = []
  for ring in layer.rings {
    if ring.length() >= 3 {
      for i in 0..<ring.length() {
        let a = ring[i]
        let b = ring[(i + 1) % ring.length()]
        if a.1 != b.1 {
          edges.push((a.0, a.1, b.0, b.1))
        }
      }
    }
  }
  let band_count = (height + 7) / 8
  // The banded array repeats an edge in every 8-row band it crosses, matching
  // the reference renderer's contiguous per-band spans.
  let banded : Array[(Double, Double, Double, Double)] = []
  let spans : Array[(Int, Int)] = []
  for band in 0..<band_count {
    let b0 = (band * 8).to_double()
    let b1 = ((band + 1) * 8).to_double()
    let start = banded.length()
    for e in edges {
      let ymin = if e.1 < e.3 { e.1 } else { e.3 }
      let ymax = if e.1 < e.3 { e.3 } else { e.1 }
      if ymin < b1 && ymax > b0 {
        banded.push(e)
      }
    }
    spans.push((start, banded.length()))
  }
  (banded, spans)
}

///| Warning record serialised into the IR.
struct IrWarning {
  line : Int
  col : Int
  msg : String
}

///| Serialise expanded frames into NCIR v1 bytes.
fn write_ir(
  width : Int,
  height : Int,
  fps : Int,
  declared_frames : Int,
  seed : Int,
  spec_version : String,
  name : String,
  precision : String,
  flags : Int,
  source_bytes : Int,
  warnings : Array[IrWarning],
  plans : Array[(Int, FramePlan)],
) -> Bytes {
  let b = ByteBuf::new()
  b.data.push(b'N')
  b.data.push(b'C')
  b.data.push(b'I')
  b.data.push(b'R')
  b.u32(1)
  b.u32(width)
  b.u32(height)
  b.u32(fps)
  b.u32(declared_frames)
  b.u32(flags)
  b.u32(source_bytes)
  b.u64(seed.to_uint64())
  b.str(spec_version)
  b.str(name)
  b.str(precision)
  b.u32(warnings.length())
  for w in warnings {
    b.u32(w.line)
    b.u32(w.col)
    b.str(w.msg)
  }
  b.u32(plans.length())
  for entry in plans {
    let (idx, plan) = entry
    b.i32(idx)
    b.u32(plan.aa)
    b.f64(plan.grain)
    b.u32(plan.paper_r)
    b.u32(plan.paper_g)
    b.u32(plan.paper_b)
    b.u32(plan.layers.length())
    for layer in plan.layers {
      b.str(layer.name)
      b.u32(layer.r)
      b.u32(layer.g)
      b.u32(layer.b)
      let (edges, spans) = build_edges(layer, plan.height)
      b.u32(spans.length())
      b.u32(edges.length())
      for sp in spans {
        b.u32(sp.0)
        b.u32(sp.1)
      }
      for e in edges {
        b.f64(e.0)
        b.f64(e.1)
        b.f64(e.2)
        b.f64(e.3)
      }
    }
  }
  b.finish()
}

///| Coordinate scale used by the Bend stage: 1/1024 px when it fits in U24,
///| otherwise 1/256 px (still far below the 0.25px contour grid).
fn bend_scale(width : Int, height : Int) -> Double {
  let max_px = if width > height { width } else { height }
  if max_px.to_double() * 4.0 * 256.0 < 8000000.0 {
    1024.0
  } else {
    256.0
  }
}

///| Convert a pixel coordinate to the integer unit used by the Bend program.
fn bend_units(px : Double, scale : Double) -> Int {
  py_round(px * scale)
}

///| Generate the Bend/HVM2 swarm program for the collected tasks.
///| Each agent (ring) is its own small def; main forks a balanced binary tree of
///| agent ids, so the compiler sees small definitions while HVM2 evaluates the
///| whole swarm in parallel. This is the shape the shower experiment proved.
fn generate_bend(tasks : Array[SwarmTask], scale : Double) -> String {
  let agents : Array[String] = []
  for t in tasks {
    for ri in 0..<t.rings.length() {
      let terms : Array[String] = []
      terms.push("!(S/Agent { task: " + t.id.to_string() + ", ring: " + ri.to_string() + " })")
      for p in t.rings[ri] {
        let xu = bend_units(p.0, scale)
        let yu = bend_units(p.1, scale)
        terms.push("!(S/Pt { x: " + xu.to_string() + ", y: " + yu.to_string() + " })")
      }
      let mut body = "0"
      for i in 0..<terms.length() {
        body = "(" + terms[terms.length() - 1 - i] + ", " + body + ")"
      }
      agents.push(body)
    }
  }
  let mut out = "# NorthCel native swarm stage (generated by ncel-ast).\n"
  out = out + "# " + agents.length().to_string() + " stateless agents; order-independent.\n"
  out = out + "type S:\n  Agent { task, ring }\n  Pt { x, y }\n\n"
  if agents.length() == 0 {
    return out + "def main:\n  return 0\n"
  }
  // Balanced dispatch tree over agent ids with the agent bodies inline, the
  // same shape the shower experiment used (HVM accepts the large function def;
  // only the root definition is size-limited).
  out = out + "def eval_agent(id):\n"
  out = out + dispatch_tree(agents, 0, agents.length() - 1, "  ")
  out = out + "\ndef main:\n"
  let depth = ceil_log2(agents.length())
  out = out + "  bend d = 0, id = 0:\n"
  out = out + "    when d < " + depth.to_string() + ":\n"
  out = out + "      res = ![fork(d + 1, id * 2), fork(d + 1, id * 2 + 1)]\n"
  out = out + "    else:\n"
  out = out + "      if id < " + agents.length().to_string() + ":\n"
  out = out + "        res = eval_agent(id)\n"
  out = out + "      else:\n"
  out = out + "        res = 0\n"
  out = out + "  return res\n"
  out
}

///| Smallest d with 2^d >= n.
fn ceil_log2(n : Int) -> Int {
  let mut d = 0
  let mut v = 1
  while v < n {
    v = v * 2
    d = d + 1
  }
  d
}

///| Nested `if id <= mid` dispatch tree with inline agent bodies.
fn dispatch_tree(agents : Array[String], lo : Int, hi : Int, indent : String) -> String {
  if lo == hi {
    indent + "return " + agents[lo] + "\n"
  } else {
    let mid = (lo + hi) / 2
    let mut out = indent + "if id <= " + mid.to_string() + ":\n"
    out = out + dispatch_tree(agents, lo, mid, indent + "  ")
    out = out + indent + "else:\n"
    out = out + dispatch_tree(agents, mid + 1, hi, indent + "  ")
    out
  }
}

///| Scan an integer at `pos` in a char array.
fn scan_int_chars(chars : Array[Char], pos : Int) -> (Int, Int)? {
  let n = chars.length()
  let mut i = pos
  while i < n && (chars[i] == ' ' || chars[i] == '\n' || chars[i] == '\t' || chars[i] == '\r') {
    i = i + 1
  }
  let mut neg = false
  if i < n && chars[i] == '-' {
    neg = true
    i = i + 1
  }
  let digits_start = i
  while i < n && is_digit(chars[i]) {
    i = i + 1
  }
  if i == digits_start {
    return None
  }
  let s = String::from_array(chars[digits_start:i])
  let v = try {
    @string.parse_int(s)
  } catch {
    _ => 0
  }
  if neg {
    Some((-v, i))
  } else {
    Some((v, i))
  }
}

///| Ingest Bend/HVM2 output into per-task ring vertex lists.
fn parse_bend_results(
  text : String,
  tasks : Array[SwarmTask],
  scale : Double,
) -> Map[Int, Array[Array[(Double, Double)]]] raise NcelError {
  let results : Map[Int, Array[Array[(Double, Double)]]] = Map::new()
  for t in tasks {
    let rings : Array[Array[(Double, Double)]] = []
    for _r in t.rings {
      rings.push([])
    }
    results.set(t.id, rings)
  }
  let chars = text.to_array()
  let n = chars.length()
  let mut pos = 0
  let mut cur_task = -1
  let mut cur_ring = 0
  while pos < n {
    let agent_at = if matches_at(chars, pos, "S/Agent/tag") {
      Some(pos + 11)
    } else if matches_at(chars, pos, "S/Agent") {
      Some(pos + 7)
    } else {
      None
    }
    let point_at = if matches_at(chars, pos, "S/Pt/tag") {
      Some(pos + 8)
    } else if matches_at(chars, pos, "S/Pt") {
      Some(pos + 4)
    } else {
      None
    }
    if agent_at is Some(start) {
      match scan_int_chars(chars, start) {
        Some((tv, np1)) => {
          match scan_int_chars(chars, np1) {
            Some((rv, np2)) => {
              cur_task = tv
              cur_ring = rv
              if !results.contains(tv) {
                raise mkerr(1, 1, "Bend output names an unknown task " + tv.to_string())
              }
              pos = np2
            }
            None => raise mkerr(1, 1, "Malformed Bend agent header")
          }
        }
        None => raise mkerr(1, 1, "Malformed Bend agent header")
      }
    } else if point_at is Some(ppos) {
      match scan_int_chars(chars, ppos) {
        Some((xv, np1)) => {
          match scan_int_chars(chars, np1) {
            Some((yv, np2)) => {
              if cur_task < 0 {
                raise mkerr(1, 1, "Bend output point before agent header")
              }
              let px = xv.to_double() / scale
              let py = yv.to_double() / scale
              let rings = results.get(cur_task).unwrap()
              if cur_ring < 0 || cur_ring >= rings.length() {
                raise mkerr(1, 1, "Bend output ring index out of range")
              }
              rings[cur_ring].push((px, py))
              pos = np2
            }
            None => raise mkerr(1, 1, "Malformed Bend point")
          }
        }
        None => raise mkerr(1, 1, "Malformed Bend point")
      }
    } else {
      pos = pos + 1
    }
  }
  // Verify every agent returned exactly the expected number of vertices.
  for t in tasks {
    match results.get(t.id) {
      None => raise mkerr(1, 1, "Missing Bend result for task " + t.id.to_string())
      Some(rings) => {
        if rings.length() != t.rings.length() {
          raise mkerr(1, 1, "Task " + t.id.to_string() + ": ring count mismatch")
        }
        for ri in 0..<rings.length() {
          if rings[ri].length() != t.rings[ri].length() {
            raise mkerr(
              1,
              1,
              "Task " + t.id.to_string() + " ring " + ri.to_string() + ": vertex count mismatch (" + rings[ri].length().to_string() + " != " + t.rings[ri].length().to_string() + ")",
            )
          }
        }
      }
    }
  }
  results
}
