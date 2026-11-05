// NorthCel native runtime - frame expansion and geometry construction.
// Mirrors the reference renderer's paint-order expansion exactly: def/use
// shifting, in-place layer replacement, `drop`, coupled cel outlines, the
// shower compatibility swarm merges, and the stateless 32-bit boil hash.

///| A resolved paint layer (name for layer identity, RGB, closed rings).
struct OutLayer {
  name : String
  r : Int
  g : Int
  b : Int
  rings : Array[Array[(Double, Double)]]
}

///| One stateless swarm agent job (a ring) evaluated by the Bend/HVM2 stage.
struct SwarmTask {
  id : Int
  frame : Int
  rings : Array[Array[(Double, Double)]]
  tx : Double
  ty : Double
  boil : Boil?
}

///| A fully expanded frame ready for rasterisation.
struct FramePlan {
  width : Int
  height : Int
  aa : Int
  grain : Double
  paper_r : Int
  paper_g : Int
  paper_b : Int
  layers : Array[OutLayer]
  tasks : Array[SwarmTask]
  rings : Int
  vertices : Int
}

///| Replace a named layer in place, or append it.
fn upsert_layer(layers : Array[OutLayer], named : Map[String, Int], name : String, color : Color, rings : Array[Array[(Double, Double)]]) -> Unit {
  let (r, g, b) = color.channels()
  match named.get(name) {
    Some(i) => {
      layers[i] = { name: name, r: r, g: g, b: b, rings: rings }
    }
    None => {
      named.set(name, layers.length())
      layers.push({ name: name, r: r, g: g, b: b, rings: rings })
    }
  }
}

///| Expand a stroke polyline with start/end taper into a closed ribbon ring.
fn stroke_ring(pts : Array[(Double, Double)], w_start : Double, w_end : Double) -> Array[(Double, Double)] {
  let n = pts.length()
  if n < 2 {
    return []
  }
  let left : Array[(Double, Double)] = []
  let right : Array[(Double, Double)] = []
  for i in 0..<n {
    let (px, py) = pts[i]
    let u = i.to_double() / (n - 1).to_double()
    let half_w = 0.5 * (w_start + (w_end - w_start) * u)
    let (dx, dy) = if i == 0 {
      (pts[1].0 - pts[0].0, pts[1].1 - pts[0].1)
    } else if i == n - 1 {
      (pts[n - 1].0 - pts[n - 2].0, pts[n - 1].1 - pts[n - 2].1)
    } else {
      (pts[i + 1].0 - pts[i - 1].0, pts[i + 1].1 - pts[i - 1].1)
    }
    let mut length = @math.hypot(dx, dy)
    if length == 0.0 {
      length = 1.0
    }
    let nx = -dy / length
    let ny = dx / length
    left.push((px + nx * half_w, py + ny * half_w))
    right.push((px - nx * half_w, py - ny * half_w))
  }
  for i in 0..<right.length() {
    left.push(right[right.length() - 1 - i])
  }
  left
}

///| Expand a per-vertex-width ribbon polyline into a closed ribbon ring.
fn ribbon_ring(pts : Array[(Double, Double, Double)]) -> Array[(Double, Double)] {
  let n = pts.length()
  if n < 2 {
    return []
  }
  let left : Array[(Double, Double)] = []
  let right : Array[(Double, Double)] = []
  for i in 0..<n {
    let (px, py, w) = pts[i]
    let half_w = 0.5 * (if w < 0.25 { 0.25 } else { w })
    let (dx, dy) = if i == 0 {
      (pts[1].0 - pts[0].0, pts[1].1 - pts[0].1)
    } else if i == n - 1 {
      (pts[n - 1].0 - pts[n - 2].0, pts[n - 1].1 - pts[n - 2].1)
    } else {
      (pts[i + 1].0 - pts[i - 1].0, pts[i + 1].1 - pts[i - 1].1)
    }
    let mut length = @math.hypot(dx, dy)
    if length == 0.0 {
      length = 1.0
    }
    let nx = -dy / length
    let ny = dx / length
    left.push((px + nx * half_w, py + ny * half_w))
    right.push((px - nx * half_w, py - ny * half_w))
  }
  for i in 0..<right.length() {
    left.push(right[right.length() - 1 - i])
  }
  left
}

///| The reference 32-bit integer hash (exactly the Python `_hash_u32`).
fn hash_u32(x : UInt64) -> UInt64 {
  let mask : UInt64 = 0xFFFFFFFFUL
  let mut h = x.land(mask).lxor(61UL)
  h = h.lxor(h.shr(16)).land(mask)
  h = h.add(h.lsl(3).land(mask)).land(mask)
  h = h.lxor(h.shr(4)).land(mask)
  h = h.mul(0x27D4EB2DUL).land(mask)
  h = h.lxor(h.shr(15)).land(mask)
  h
}

///| Stateless line-boil offset for one vertex (matches the reference renderer).
fn boil_offset(seed : Int, frame_idx : Int, item_idx : Int, ring_idx : Int, vert_idx : Int, boil : Boil?) -> (Double, Double) {
  match boil {
    None => (0.0, 0.0)
    Some(b) =>
      if b.amp <= 0.0 {
        (0.0, 0.0)
      } else {
        let freq = if b.freq < 0.01 { 0.01 } else { b.freq }
        let phase_frame = (frame_idx.to_double() * freq).floor().to_int()
        let x = seed.to_uint64().mul(73856093UL)
          .lxor(phase_frame.to_uint64().mul(19349663UL))
          .lxor(item_idx.to_uint64().mul(83492791UL))
          .lxor(ring_idx.to_uint64().mul(2654435761UL))
          .lxor(vert_idx.to_uint64().mul(374761393UL))
        let h1 = hash_u32(x)
        let h2 = hash_u32(h1.lxor(0x9E3779B9UL))
        let nx = h1.to_double() / 4294967295.0 * 2.0 - 1.0
        let ny = h2.to_double() / 4294967295.0 * 2.0 - 1.0
        (nx * b.amp, ny * b.amp)
      }
  }
}

///| Process an item list into layers (recursive; mirrors the reference walker).
fn process_list(
  seq : Array[Item],
  local_env : Map[String, Double],
  defs : Map[String, DefBlock],
  precision : String,
  seed : Int,
  frame_idx : Int,
  layers : Array[OutLayer],
  named : Map[String, Int],
  tasks : Array[SwarmTask],
  results : Map[Int, Array[Array[(Double, Double)]]],
) -> Unit raise NcelError {
  for item_idx in 0..<seq.length() {
    let item = seq[item_idx]
    match item {
      ITransform(tr) => {
        let sx = eval_expr(tr.sx, local_env)
        let sy = eval_expr(tr.sy, local_env)
        let ax = eval_expr(tr.ax, local_env)
        let ay = eval_expr(tr.ay, local_env)
        let dx = eval_expr(tr.dx, local_env)
        let dy = eval_expr(tr.dy, local_env)
        let angle = eval_expr(tr.angle, local_env) * 3.141592653589793 / 180.0
        let c = @math.cos(angle)
        let s = @math.sin(angle)
        let mut found = tr.target == "all"
        for li in 0..<layers.length() {
          let l = layers[li]
          if tr.target == "all" || l.name == tr.target || l.name == tr.target + "__outline" {
            found = true
            let rings : Array[Array[(Double, Double)]] = []
            for ring in l.rings {
              let pts : Array[(Double, Double)] = []
              for p in ring {
                let u = (p.0-ax)*sx
                let v = (p.1-ay)*sy
                pts.push((ax+u*c-v*s+dx, ay+u*s+v*c+dy))
              }
              rings.push(pts)
            }
            layers[li] = { name: l.name, r: l.r, g: l.g, b: l.b, rings: rings }
          }
        }
        if !found {
          raise mkerr(tr.line, tr.col, "Transform target '" + tr.target + "' has not been painted")
        }
      }
      IDrop(d) => {
        match named.get(d.target) {
          Some(i) => {
            layers[i] = { name: d.target, r: 0, g: 0, b: 0, rings: [] }
          }
          None => ()
        }
        let out_key = d.target + "__outline"
        match named.get(out_key) {
          Some(i) => {
            layers[i] = { name: out_key, r: 0, g: 0, b: 0, rings: [] }
          }
          None => ()
        }
      }
      IUse(u) => {
        match defs.get(u.def_name) {
          None => raise mkerr(u.line, u.col, "Use of undefined def block '" + u.def_name + "'")
          Some(d) => {
            let child_env = local_env.copy()
            for k, v in d.params {
              child_env.set(k, v)
            }
            for k, v in u.args {
              child_env.set(k, eval_expr(val_to_expr_dummy(v), local_env))
            }
            let dx = match child_env.get("dx") {
              Some(v) => v
              None => 0.0
            }
            let dy = match child_env.get("dy") {
              Some(v) => v
              None => 0.0
            }
            let before_len = layers.length()
            process_list(d.items, child_env, defs, precision, seed, frame_idx, layers, named, tasks, results)
            if dx.abs() > 0.000000001 || dy.abs() > 0.000000001 {
              for li in before_len..<layers.length() {
                let shifted : Array[Array[(Double, Double)]] = []
                for r in layers[li].rings {
                  let nr : Array[(Double, Double)] = []
                  for p in r {
                    nr.push((p.0 + dx, p.1 + dy))
                  }
                  shifted.push(nr)
                }
                layers[li] = { name: layers[li].name, r: layers[li].r, g: layers[li].g, b: layers[li].b, rings: shifted }
              }
            }
          }
        }
      }
      ILayer(l) => {
        let raw = decode_rings_payload(l.payload, precision, l.line, l.col)
        let tx = eval_expr(l.tx, local_env)
        let ty = eval_expr(l.ty, local_env)
        let final_rings : Array[Array[(Double, Double)]] = []
        for ri in 0..<raw.length() {
          let pts : Array[(Double, Double)] = []
          for vi in 0..<raw[ri].length() {
            let (bx, by) = boil_offset(seed, frame_idx, item_idx, ri, vi, l.boil)
            pts.push((raw[ri][vi].0 + tx + bx, raw[ri][vi].1 + ty + by))
          }
          final_rings.push(pts)
        }
        upsert_layer(layers, named, l.name, l.color, final_rings)
        match l.outline_color {
          Some(oc) =>
            if l.outline_width > 0.0 {
              let stroke_rings : Array[Array[(Double, Double)]] = []
              for r in final_rings {
                if r.length() >= 3 {
                  let closed : Array[(Double, Double)] = []
                  for p in r {
                    closed.push(p)
                  }
                  closed.push(r[0])
                  let sr = stroke_ring(closed, l.outline_width, l.outline_width)
                  if sr.length() >= 3 {
                    stroke_rings.push(sr)
                  }
                }
              }
              if stroke_rings.length() > 0 {
                upsert_layer(layers, named, l.name + "__outline", oc, stroke_rings)
              }
            }
          None => ()
        }
      }
      ISwarm(s) => {
        let raw = decode_rings_payload(s.payload, precision, s.line, s.col)
        let tx = eval_expr(s.tx, local_env)
        let ty = eval_expr(s.ty, local_env)
        let id = tasks.length()
        tasks.push({ id: id, frame: frame_idx, rings: raw, tx: tx, ty: ty, boil: s.boil })
        let final_rings : Array[Array[(Double, Double)]] = []
        match results.get(id) {
          Some(rs) =>
            if rs.length() == raw.length() {
              for ri in 0..<rs.length() {
                if rs[ri].length() == raw[ri].length() {
                  let pts : Array[(Double, Double)] = []
                  for vi in 0..<rs[ri].length() {
                    let (bx, by) = boil_offset(seed, frame_idx, item_idx + 1000, ri, vi, s.boil)
                    // Bend returns the agent's decoded vertices; the frame transform
                    // is applied here so fractional translates match the oracle exactly.
                    pts.push((rs[ri][vi].0 + tx + bx, rs[ri][vi].1 + ty + by))
                  }
                  final_rings.push(pts)
                } else {
                  raise mkerr(s.line, s.col, "Bend swarm result vertex-count mismatch for '" + s.name + "'")
                }
              }
            } else {
              raise mkerr(s.line, s.col, "Bend swarm result ring-count mismatch for '" + s.name + "'")
            }
          None =>
            for ri in 0..<raw.length() {
              let pts : Array[(Double, Double)] = []
              for vi in 0..<raw[ri].length() {
                let (bx, by) = boil_offset(seed, frame_idx, item_idx + 1000, ri, vi, s.boil)
                pts.push((raw[ri][vi].0 + tx + bx, raw[ri][vi].1 + ty + by))
              }
              final_rings.push(pts)
            }
        }
        if s.name == "water_droplets" && named.contains("tile_wall") {
          let host = layers[named.get("tile_wall").unwrap()]
          for r in final_rings {
            host.rings.push(r)
          }
        } else if s.name == "beard_and_chest_bristles" && named.contains("ink_contours") {
          let host = layers[named.get("ink_contours").unwrap()]
          for r in final_rings {
            host.rings.push(r)
          }
        } else {
          let (cr, cg, cb) = s.color.channels()
          layers.push({ name: s.name, r: cr, g: cg, b: cb, rings: final_rings })
        }
      }
      IStroke(st) => {
        let pts : Array[(Double, Double)] = []
        for vi in 0..<st.points.length() {
          let x = eval_expr(st.points[vi].0, local_env)
          let y = eval_expr(st.points[vi].1, local_env)
          let (bx, by) = boil_offset(seed, frame_idx, item_idx + 2000, 0, vi, st.boil)
          pts.push((x + bx, y + by))
        }
        let ring = stroke_ring(pts, st.width_start, st.width_end)
        if ring.length() >= 3 {
          let (cr, cg, cb) = st.color.channels()
          layers.push({ name: st.name, r: cr, g: cg, b: cb, rings: [ring] })
        }
      }
      IRibbon(rb) => {
        let pts : Array[(Double, Double, Double)] = []
        for vi in 0..<rb.points.length() {
          let x = eval_expr(rb.points[vi].0, local_env)
          let y = eval_expr(rb.points[vi].1, local_env)
          let (bx, by) = boil_offset(seed, frame_idx, item_idx + 3000, 0, vi, rb.boil)
          pts.push((x + bx, y + by, rb.points[vi].2))
        }
        let ring = ribbon_ring(pts)
        if ring.length() >= 3 {
          let (cr, cg, cb) = rb.color.channels()
          layers.push({ name: rb.name, r: cr, g: cg, b: cb, rings: [ring] })
        }
      }
    }
  }
}

///| Convert an attribute value to an expression (helper shared with `use` args).
fn val_to_expr_dummy(v : AVal) -> Expr raise NcelError {
  match v {
    ANum(e) => e
    AStr(s) => EConst(parse_double_at(strip_unit(s), 1, 1))
    _ => raise mkerr(1, 1, "Expected a numeric attribute value")
  }
}

///| Build the per-frame environment (`t`, `f`, `seed`).
fn frame_env(frame_idx : Int, frames : Int, seed : Int) -> Map[String, Double] {
  let env : Map[String, Double] = Map::new()
  let t = if frames > 1 {
    frame_idx.to_double() / (frames - 1).to_double()
  } else {
    0.0
  }
  env.set("t", t)
  env.set("f", frame_idx.to_double())
  env.set("seed", seed.to_double())
  env
}

///| Expand one frame of a document.
fn expand_frame(
  doc : Document,
  frame_idx : Int,
  seed_override : Int?,
  results : Map[Int, Array[Array[(Double, Double)]]],
) -> FramePlan raise NcelError {
  match doc.root {
    RScene(s) => {
      let seed = match seed_override {
        Some(v) => v
        None => s.seed
      }
      let (pr, pg, pb) = s.paper.color.channels()
      let layers : Array[OutLayer] = []
      let named : Map[String, Int] = Map::new()
      let tasks : Array[SwarmTask] = []
      process_list(s.items, frame_env(frame_idx, 1, seed), s.defs, s.precision, seed, frame_idx, layers, named, tasks, results)
      let (rings, vertices) = count_geometry(layers)
      {
        width: s.width,
        height: s.height,
        aa: s.paper.aa,
        grain: s.paper.grain,
        paper_r: pr,
        paper_g: pg,
        paper_b: pb,
        layers: layers,
        tasks: tasks,
        rings: rings,
        vertices: vertices,
      }
    }
    RFilm(f) => {
      let seed = match seed_override {
        Some(v) => v
        None => f.seed
      }
      let (paper, precision, defs, items) = match f.overrides.get(frame_idx) {
        Some(ov) => {
          let merged : Map[String, DefBlock] = f.defs.copy()
          for k, v in ov.defs {
            merged.set(k, v)
          }
          let its : Array[Item] = []
          for it in f.items {
            its.push(it)
          }
          for it in ov.items {
            its.push(it)
          }
          (ov.paper, ov.precision, merged, its)
        }
        None => (f.paper, f.precision, f.defs, f.items)
      }
      let (pr, pg, pb) = paper.color.channels()
      let layers : Array[OutLayer] = []
      let named : Map[String, Int] = Map::new()
      let tasks : Array[SwarmTask] = []
      process_list(items, frame_env(frame_idx, f.frames, seed), defs, precision, seed, frame_idx, layers, named, tasks, results)
      let (rings, vertices) = count_geometry(layers)
      {
        width: f.width,
        height: f.height,
        aa: paper.aa,
        grain: paper.grain,
        paper_r: pr,
        paper_g: pg,
        paper_b: pb,
        layers: layers,
        tasks: tasks,
        rings: rings,
        vertices: vertices,
      }
    }
  }
}

///| Count rings and vertices actually painted in a frame.
fn count_geometry(layers : Array[OutLayer]) -> (Int, Int) {
  let mut rings = 0
  let mut verts = 0
  for l in layers {
    rings = rings + l.rings.length()
    for r in l.rings {
      verts = verts + r.length()
    }
  }
  (rings, verts)
}

///| Number of frames in a document.
fn document_frames(doc : Document) -> Int {
  match doc.root {
    RScene(_) => 1
    RFilm(f) => if f.frames < 1 { 1 } else { f.frames }
  }
}

///| Canvas metadata of a document.
fn document_meta(doc : Document) -> (Int, Int, Int, Int) {
  match doc.root {
    RScene(s) => (s.width, s.height, s.fps, 1)
    RFilm(f) => (f.width, f.height, f.fps, f.frames)
  }
}
