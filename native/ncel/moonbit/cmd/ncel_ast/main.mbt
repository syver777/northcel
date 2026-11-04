// NorthCel native runtime - `ncel-ast` command line.
// Subcommands: check, info, emit-bend, emit-ir. This binary performs the
// typed-AST and contour work; the C `ncel-native` CLI orchestrates Bend and GL.

///| File IO through the shipped C stub.
#borrow(path)
extern "C" fn ncel_read_file(path : Bytes) -> Bytes = "ncel_read_file"

///| Write raw bytes to a path (0 = success).
#borrow(path, data)
extern "C" fn ncel_write_file(path : Bytes, data : Bytes) -> Int = "ncel_write_file"

///| Read a file through the native stub. An unreadable path yields "".
fn read_source(path : String) -> String {
  let b = ncel_read_file(@utf8.encode(path))
  try {
    @utf8.decode(b)
  } catch {
    _ => ""
  }
}

///| Write a file through the native stub. Returns false on failure.
fn write_file(path : String, data : String) -> Bool {
  ncel_write_file(@utf8.encode(path), @utf8.encode(data)) == 0
}

///| Write raw bytes through the native stub. Returns false on failure.
fn write_bytes_file(path : String, data : Bytes) -> Bool {
  ncel_write_file(@utf8.encode(path), data) == 0
}

///| JSON string escaping.
fn json_escape(s : String) -> String {
  let out : Array[Char] = []
  for c in s {
    if c == '"' {
      out.push('\\')
      out.push('"')
    } else if c == '\\' {
      out.push('\\')
      out.push('\\')
    } else if c == '\n' {
      out.push('\\')
      out.push('n')
    } else if c == '\r' {
      out.push('\\')
      out.push('r')
    } else if c == '\t' {
      out.push('\\')
      out.push('t')
    } else if c.to_int() < 32 {
      out.push('?')
    } else {
      out.push(c)
    }
  }
  String::from_array(out[:])
}

///| JSON array of strings.
fn json_str_array(items : Array[String]) -> String {
  let parts : Array[String] = []
  for it in items {
    parts.push("\"" + json_escape(it) + "\"")
  }
  "[" + parts.join(",") + "]"
}

///| Validation result.
struct Validation {
  errors : Array[String]
  warnings : Array[String]
}

///| Push an error string.
fn push_diag(arr : Array[String], level : String, line : Int, col : Int, msg : String) -> Unit {
  arr.push(line.to_string() + ":" + col.to_string() + ": " + level + ": " + msg)
}

///| Check colour channel ranges.
fn check_color(c : Color, line : Int, col : Int, errs : Array[String]) -> Unit {
  let (r, g, b) = c.channels()
  if r < 0 || r > 255 {
    push_diag(errs, "error", line, col, "Color channel r=" + r.to_string() + " out of range [0..255]")
  }
  if g < 0 || g > 255 {
    push_diag(errs, "error", line, col, "Color channel g=" + g.to_string() + " out of range [0..255]")
  }
  if b < 0 || b > 255 {
    push_diag(errs, "error", line, col, "Color channel b=" + b.to_string() + " out of range [0..255]")
  }
}

///| Validate one item list.
fn validate_items(
  items : Array[Item],
  defs : Map[String, DefBlock],
  precision : String,
  errs : Array[String],
  warns : Array[String],
) -> Unit {
  for item in items {
    match item {
      ILayer(l) => {
        check_color(l.color, l.line, l.col, errs)
        match try_decode_rings(fn () { decode_rings_payload(l.payload, precision, l.line, l.col) }) {
          OkRings(rings) => {
            if l.has_rings_count && l.rings_count != rings.length() {
              push_diag(
                warns,
                "warning",
                l.line,
                l.col,
                "Layer '" + l.name + "' declares rings: " + l.rings_count.to_string() + ", but payload contains " + rings.length().to_string() + " rings",
              )
            }
          }
          ErrRings(msg) => push_diag(errs, "error", l.line, l.col, "Layer '" + l.name + "' has invalid ring payload: " + msg)
        }
      }
      ISwarm(s) => {
        check_color(s.color, s.line, s.col, errs)
        if s.agents <= 0 {
          push_diag(errs, "error", s.line, s.col, "Swarm '" + s.name + "' must have agents >= 1 (got " + s.agents.to_string() + ")")
        }
        match try_decode_rings(fn () { decode_rings_payload(s.payload, precision, s.line, s.col) }) {
          OkRings(rings) =>
            if rings.length() == 0 {
              push_diag(errs, "error", s.line, s.col, "Swarm '" + s.name + "' payload decoded to 0 rings")
            }
          ErrRings(msg) => push_diag(errs, "error", s.line, s.col, "Swarm '" + s.name + "' has invalid ring payload: " + msg)
        }
      }
      IStroke(st) => {
        check_color(st.color, st.line, st.col, errs)
        if st.points.length() < 2 {
          push_diag(errs, "error", st.line, st.col, "Stroke '" + st.name + "' requires at least 2 control points")
        }
        if st.width_start <= 0.0 || st.width_end <= 0.0 {
          push_diag(errs, "error", st.line, st.col, "Stroke '" + st.name + "' widths must be > 0")
        }
      }
      IRibbon(rb) => {
        check_color(rb.color, rb.line, rb.col, errs)
        if rb.points.length() < 2 {
          push_diag(errs, "error", rb.line, rb.col, "Ribbon '" + rb.name + "' requires at least 2 (x, y, width) points")
        }
      }
      IUse(u) =>
        if !defs.contains(u.def_name) {
          push_diag(errs, "error", u.line, u.col, "Use of undefined def block '" + u.def_name + "'")
        }
      IDrop(_) => ()
    }
  }
}

///| Validate a parsed document (mirrors the reference validator).
fn validate_document(doc : Document) -> Validation {
  let errs : Array[String] = []
  let warns : Array[String] = []
  let ok_versions = "0.1', '0.1.0', '0.1.0-draft', '0.2', '0.2.0', '0.2.0-draft"
  let mut supported = false
  for v in ["0.1", "0.1.0", "0.1.0-draft", "0.2", "0.2.0", "0.2.0-draft"] {
    if doc.spec_version == v {
      supported = true
    }
  }
  if !supported {
    push_diag(errs, "error", 1, 1, "Unsupported NorthCel version '" + doc.spec_version + "'. Supported: ('" + ok_versions + "')")
  }
  match doc.root {
    RScene(s) => {
      check_scene_root(s, errs, warns)
      for _name, d in s.defs {
        validate_items(d.items, s.defs, s.precision, errs, warns)
      }
      validate_items(s.items, s.defs, s.precision, errs, warns)
    }
    RFilm(f) => {
      check_canvas(f.width, f.height, f.fps, f.precision, f.paper, f.line, f.col, errs)
      for _name, d in f.defs {
        validate_items(d.items, f.defs, f.precision, errs, warns)
      }
      validate_items(f.items, f.defs, f.precision, errs, warns)
      if f.frames <= 0 {
        push_diag(errs, "error", f.line, f.col, "Film frames count must be >= 1 (got " + f.frames.to_string() + ")")
      }
      for idx, ov in f.overrides {
        if idx < 0 || idx >= f.frames {
          push_diag(
            errs,
            "error",
            ov.line,
            ov.col,
            "Frame override index " + idx.to_string() + " out of range [0.." + (f.frames - 1).to_string() + "]",
          )
        }
        let merged = f.defs.copy()
        for k, v in ov.defs {
          merged.set(k, v)
        }
        validate_items(ov.items, merged, f.precision, errs, warns)
      }
    }
  }
  { errors: errs, warnings: warns }
}

///| Validate scene-level constraints.
fn check_scene_root(s : SceneNode, errs : Array[String], warns : Array[String]) -> Unit {
  let _ = warns
  check_canvas(s.width, s.height, s.fps, s.precision, s.paper, s.line, s.col, errs)
}

///| Canvas / fps / precision / paper checks.
fn check_canvas(
  width : Int,
  height : Int,
  fps : Int,
  precision : String,
  paper : PaperSpec,
  line : Int,
  col : Int,
  errs : Array[String],
) -> Unit {
  if width <= 0 || height <= 0 || width > 8192 || height > 8192 {
    push_diag(errs, "error", line, col, "Canvas dimensions " + width.to_string() + "x" + height.to_string() + " out of valid range [1..8192]")
  }
  if fps <= 0 || fps > 240 {
    push_diag(errs, "error", line, col, "FPS " + fps.to_string() + " out of valid range [1..240]")
  }
  if !(precision == "0.25px" || precision == "0.25px-b63" || precision == "1px") {
    push_diag(errs, "error", line, col, "Unsupported precision '" + precision + "' (expected '0.25px', '0.25px-b63', or '1px')")
  }
  check_color(paper.color, paper.line, paper.col, errs)
  if !(paper.aa == 1 || paper.aa == 2 || paper.aa == 4 || paper.aa == 8) {
    push_diag(errs, "error", paper.line, paper.col, "paper.antialias_grid must be 1, 2, 4, or 8 (got " + paper.aa.to_string() + ")")
  }
}

///| Read and parse a source file, returning (source, document) or an error.
fn load_document(path : String) -> (String, Document) raise NcelError {
  let src = read_source(path)
  let doc = parse_document(src)
  (src, doc)
}

///| `check` subcommand.
fn cmd_check(args : Array[String]) -> Int raise NcelError {
  let mut path = ""
  let mut json = false
  for i in 2..<args.length() {
    if args[i] == "--json" {
      json = true
    } else {
      path = args[i]
    }
  }
  let src = read_source(path)
  let mut spec : String? = None
  let mut errors : Array[String] = []
  let mut warnings : Array[String] = []
  let parsed = try {
    let doc = parse_document(src)
    spec = Some(doc.spec_version)
    let v = validate_document(doc)
    errors = v.errors
    warnings = v.warnings
    true
  } catch {
    NcelError(d) => {
      errors.push(d.line.to_string() + ":" + d.col.to_string() + ": error: " + d.msg)
      false
    }
  }
  let ok = parsed && errors.length() == 0
  if json {
    let spec_json = match spec {
      Some(s) => "\"" + json_escape(s) + "\""
      None => "null"
    }
    println(
      "{\"ok\":" + ok.to_string() + ",\"partial\":false,\"validator\":\"native\",\"file\":\"" + json_escape(path) + "\",\"spec_version\":" + spec_json + ",\"errors\":" + json_str_array(errors) + ",\"warnings\":" + json_str_array(warnings) + "}",
    )
  } else {
    for w in warnings {
      eprintln(path + ":" + w)
    }
    for e in errors {
      eprintln(path + ":" + e)
    }
    if ok {
      let sv = match spec {
        Some(s) => s
        None => ""
      }
      println(path + ": OK (NorthCel " + sv + ")")
    }
  }
  if ok {
    0
  } else {
    1
  }
}

///| `info` subcommand.
fn cmd_info(args : Array[String]) -> Int raise NcelError {
  let mut path = ""
  for i in 2..<args.length() {
    if args[i] != "--json" {
      path = args[i]
    }
  }
  let (src, doc) = load_document(path)
  let (w, h, fps, frames) = document_meta(doc)
  let mut rings = 0
  let mut verts = 0
  let (kind, name, precision, seed, defs_count) = match doc.root {
    RScene(s) => {
      let plan = expand_frame(doc, 0, None, Map::new())
      rings = plan.rings
      verts = plan.vertices
      ("scene", s.name, s.precision, s.seed, s.defs.length())
    }
    RFilm(f) => {
      let plan = expand_frame(doc, 0, None, Map::new())
      rings = plan.rings
      verts = plan.vertices
      ("film", f.name, f.precision, f.seed, f.defs.length())
    }
  }
  let _ = defs_count
  println(
    "{\"file\":\"" + json_escape(path) + "\",\"bytes\":" + @utf8.encode(src).length().to_string() + ",\"spec_version\":\"" + json_escape(doc.spec_version) + "\",\"kind\":\"" + kind + "\",\"name\":\"" + json_escape(name) + "\",\"width\":" + w.to_string() + ",\"height\":" + h.to_string() + ",\"fps\":" + fps.to_string() + ",\"frames\":" + frames.to_string() + ",\"precision\":\"" + json_escape(precision) + "\",\"seed\":" + seed.to_string() + ",\"total_rings\":" + rings.to_string() + ",\"total_vertices\":" + verts.to_string() + "}",
  )
  0
}

///| Parse `--seed N` (optional override).
fn arg_seed(args : Array[String]) -> Int? {
  for i in 1..<args.length() {
    if args[i] == "--seed" && i + 1 < args.length() {
      return Some(
        try {
          @string.parse_int(args[i + 1])
        } catch {
          _ => 0
        },
      )
    }
  }
  None
}

///| Parse `--frame N`.
fn arg_frame(args : Array[String]) -> Int {
  let mut frame = 0
  for i in 1..<args.length() {
    if args[i] == "--frame" && i + 1 < args.length() {
      frame = try {
        @string.parse_int(args[i + 1])
      } catch {
        _ => 0
      }
    }
  }
  frame
}

///| Parse `--bend-results PATH`.
fn arg_value(args : Array[String], key : String) -> String? {
  for i in 1..<args.length() {
    if args[i] == key && i + 1 < args.length() {
      return Some(args[i + 1])
    }
  }
  None
}

///| Positional arguments (skipping flags and their values).
fn positional(args : Array[String]) -> Array[String] {
  let out : Array[String] = []
  let mut i = 2
  while i < args.length() {
    let a = args[i]
    if a == "--frame" || a == "--bend-results" || a == "--seed" {
      i = i + 2
    } else if a == "--json" {
      i = i + 1
    } else {
      out.push(a)
      i = i + 1
    }
  }
  out
}

///| `emit-bend` subcommand: write the generated Bend/HVM2 swarm program.
fn cmd_emit_bend(args : Array[String]) -> Int raise NcelError {
  let pos = positional(args)
  if pos.length() < 2 {
    raise mkerr(1, 1, "usage: ncel-ast emit-bend <file> <out.bend> [--frame N]")
  }
  let frame = arg_frame(args)
  let (_src, doc) = load_document(pos[0])
  let v = validate_document(doc)
  if v.errors.length() > 0 {
    println("{\"ok\":false,\"errors\":" + json_str_array(v.errors) + "}")
    return 1
  }
  let plan = expand_frame(doc, frame, arg_seed(args), Map::new())
  let (w, h, _fps, _frames) = document_meta(doc)
  let scale = bend_scale(w, h)
  let program = generate_bend(plan.tasks, scale)
  if !write_file(pos[1], program) {
    raise mkerr(1, 1, "Could not write " + pos[1])
  }
  let mut agents = 0
  let mut points = 0
  for t in plan.tasks {
    agents = agents + t.rings.length()
    for r in t.rings {
      points = points + r.length()
    }
  }
  println(
    "{\"ok\":true,\"frame\":" + frame.to_string() + ",\"tasks\":" + plan.tasks.length().to_string() + ",\"agents\":" + agents.to_string() + ",\"points\":" + points.to_string() + ",\"scale\":" + scale.to_string() + ",\"bend\":\"" + json_escape(pos[1]) + "\"}",
  )
  0
}

///| `emit-ir` subcommand: expand a frame and write NCIR v1.
fn cmd_emit_ir(args : Array[String]) -> Int raise NcelError {
  let pos = positional(args)
  if pos.length() < 2 {
    raise mkerr(1, 1, "usage: ncel-ast emit-ir <file> <out.ir> [--frame N] [--bend-results PATH]")
  }
  let frame = arg_frame(args)
  let (src, doc) = load_document(pos[0])
  let v = validate_document(doc)
  if v.errors.length() > 0 {
    println("{\"ok\":false,\"errors\":" + json_str_array(v.errors) + "}")
    return 1
  }
  // First pass: collect the swarm tasks so Bend results can be validated.
  let probe = expand_frame(doc, frame, arg_seed(args), Map::new())
  let mut results : Map[Int, Array[Array[(Double, Double)]]] = Map::new()
  if probe.tasks.length() > 0 {
    match arg_value(args, "--bend-results") {
      None => {
        let msgs : Array[String] = ["Bend/HVM2 swarm stage required: this frame contains " + probe.tasks.length().to_string() + " bend_swarm task(s) but no --bend-results were provided"]
        println("{\"ok\":false,\"errors\":" + json_str_array(msgs) + "}")
        return 1
      }
      Some(p) => {
        let text = read_source(p)
        let (w, h, _fps, _frames) = document_meta(doc)
        let scale = bend_scale(w, h)
        results = parse_bend_results(text, probe.tasks, scale)
      }
    }
  }
  let plan = expand_frame(doc, frame, arg_seed(args), results)
  // Re-check that the second expansion produced the same task ids.
  let (width, height, fps, declared) = document_meta(doc)
  let flags = match doc.root {
    RScene(_) => 0
    RFilm(_) => 1
  }
  let (name, precision) = match doc.root {
    RScene(s) => (s.name, s.precision)
    RFilm(f) => (f.name, f.precision)
  }
  let seed = match arg_seed(args) {
    Some(v) => v
    None =>
      match doc.root {
        RScene(s) => s.seed
        RFilm(f) => f.seed
      }
  }
  let warnings : Array[IrWarning] = []
  for w in v.warnings {
    warnings.push({ line: 0, col: 0, msg: w })
  }
  let plans : Array[(Int, FramePlan)] = [(frame, plan)]
  let bytes = write_ir(
    width,
    height,
    fps,
    declared,
    seed,
    doc.spec_version,
    name,
    precision,
    flags,
    @utf8.encode(src).length(),
    warnings,
    plans,
  )
  if !write_bytes_file(pos[1], bytes) {
    raise mkerr(1, 1, "Could not write " + pos[1])
  }
  let kind = if flags == 1 { "film" } else { "scene" }
  println(
    "{\"ok\":true,\"frame\":" + frame.to_string() + ",\"width\":" + width.to_string() + ",\"height\":" + height.to_string() + ",\"fps\":" + fps.to_string() + ",\"declared_frames\":" + declared.to_string() + ",\"kind\":\"" + kind + "\",\"spec_version\":\"" + json_escape(doc.spec_version) + "\",\"name\":\"" + json_escape(name) + "\",\"precision\":\"" + json_escape(precision) + "\",\"layers\":" + plan.layers.length().to_string() + ",\"rings\":" + plan.rings.to_string() + ",\"vertices\":" + plan.vertices.to_string() + ",\"tasks\":" + plan.tasks.length().to_string() + ",\"source_bytes\":" + @utf8.encode(src).length().to_string() + ",\"ir\":\"" + json_escape(pos[1]) + "\",\"ir_bytes\":" + bytes.length().to_string() + "}",
  )
  0
}

///| Dispatch.
fn run_command(args : Array[String]) -> Int raise NcelError {
  if args.length() < 2 {
    eprintln("usage: ncel-ast <check|info|emit-bend|emit-ir> ...")
    return 2
  }
  match args[1] {
    "check" => cmd_check(args)
    "info" => cmd_info(args)
    "emit-bend" => cmd_emit_bend(args)
    "emit-ir" => cmd_emit_ir(args)
    _ => {
      eprintln("unknown subcommand: " + args[1])
      2
    }
  }
}

///| Entry point.
fn main {
  let args = @env.args()
  let code = try {
    run_command(args)
  } catch {
    NcelError(d) => {
      println("{\"ok\":false,\"errors\":[\"" + json_escape(d.line.to_string() + ":" + d.col.to_string() + ": error: " + d.msg) + "\"]}")
      1
    }
    _ => {
      println("{\"ok\":false,\"errors\":[\"internal error\"]}")
      1
    }
  }
  @env.exit(code)
}
