// NorthCel native runtime - recursive-descent parser.
// Grammar and evaluation order mirror the NorthCel 0.2 reference parser:
// signed-number lexing, optional commas, paren/brace attribute blocks,
// palette resolution at parse time, and `frame k { ... }` deltas.

///| Parser state. `active_palette` mirrors the reference parser's palette scope.
struct Parser {
  toks : Array[Token]
  mut idx : Int
  mut active_palette : Map[String, Color]
}

///| Current token.
fn Parser::cur(self : Parser) -> Token {
  self.toks[self.idx]
}

///| Token at `off` tokens ahead (clamped to EOF).
fn Parser::peek_at(self : Parser, off : Int) -> Token {
  let i = if self.idx + off < self.toks.length() { self.idx + off } else { self.toks.length() - 1 }
  self.toks[i]
}

///| Consume and return the current token.
fn Parser::adv(self : Parser) -> Token {
  let t = self.toks[self.idx]
  if self.idx < self.toks.length() - 1 {
    self.idx = self.idx + 1
  }
  t
}

///| Diagnostic helper.
fn mkerr(line : Int, col : Int, msg : String) -> NcelError {
  NcelError({ line: line, col: col, msg: msg })
}

///| Expected-a-token error text (matches the reference wording).
fn expected_msg(expected : String, tok : Token) -> String {
  let got = if tok.value.length() > 0 { "'" + tok.value + "'" } else { tok.kind }
  "Expected " + expected + ", got " + got
}

///| Require a token kind.
fn Parser::expect_kind(self : Parser, kind : String) -> Token raise NcelError {
  let t = self.cur()
  if t.kind != kind {
    raise mkerr(t.line, t.col, expected_msg(kind, t))
  }
  self.adv()
}

///| Require a specific punctuation token.
fn Parser::expect_punct(self : Parser, value : String) -> Token raise NcelError {
  let t = self.cur()
  if !(t.kind == "PUNCT" && t.value == value) {
    raise mkerr(t.line, t.col, expected_msg("'" + value + "'", t))
  }
  self.adv()
}

///| Require an identifier with a specific text.
fn Parser::expect_ident(self : Parser, value : String) -> Token raise NcelError {
  let t = self.cur()
  if !(t.kind == "IDENT" && t.value == value) {
    raise mkerr(t.line, t.col, expected_msg("'" + value + "'", t))
  }
  self.adv()
}

///| True when the current token is the given punctuation.
fn Parser::is_punct(self : Parser, value : String) -> Bool {
  let t = self.cur()
  t.kind == "PUNCT" && t.value == value
}

///| Consume punctuation if present.
fn Parser::eat_punct(self : Parser, value : String) -> Bool {
  if self.is_punct(value) {
    self.adv() |> ignore
    true
  } else {
    false
  }
}

///| Python-compatible round-half-to-even.
fn py_round(x : Double) -> Int {
  let f = x.floor()
  let diff = x - f
  if diff > 0.5 {
    f.to_int() + 1
  } else if diff < 0.5 {
    f.to_int()
  } else {
    let fi = f.to_int()
    if fi % 2 == 0 {
      fi
    } else {
      fi + 1
    }
  }
}

///| Strip a unit suffix (px-b63 | px | deg) from a raw numeric string.
fn strip_unit(s : String) -> String {
  let t = s.trim().to_owned()
  if t.has_suffix("px-b63") {
    t.substring(start=0, end=t.length() - 6)
  } else if t.has_suffix("deg") {
    t.substring(start=0, end=t.length() - 3)
  } else if t.has_suffix("px") {
    t.substring(start=0, end=t.length() - 2)
  } else {
    t
  }
}

///| Parse a double, converting failures into a located diagnostic.
fn parse_double_at(s : String, line : Int, col : Int) -> Double raise NcelError {
  try {
    @string.parse_double(s)
  } catch {
    _ => raise mkerr(line, col, "Invalid number '" + s + "'")
  }
}

///| Parse an integer, converting failures into a located diagnostic.
fn parse_int_at(s : String, line : Int, col : Int) -> Int raise NcelError {
  try {
    @string.parse_int(s)
  } catch {
    _ => raise mkerr(line, col, "Invalid integer '" + s + "'")
  }
}

///| Attribute list `( key: value, ... )` (commas optional, like the reference).
fn Parser::parse_attr_list(self : Parser) -> Map[String, AVal] raise NcelError {
  self.expect_punct("(") |> ignore
  let attrs : Map[String, AVal] = Map::new()
  while !self.is_punct(")") {
    let key = self.expect_kind("IDENT")
    let t = self.cur()
    if t.kind == "PUNCT" && (t.value == ":" || t.value == "=") {
      self.adv() |> ignore
    } else {
      raise mkerr(t.line, t.col, "Expected ':' after attribute '" + key.value + "'")
    }
    attrs.set(key.value, self.parse_attr_value())
    self.eat_punct(",") |> ignore
  }
  self.expect_punct(")") |> ignore
  attrs
}

///| Brace-or-paren attribute block used by `palette` and `paper`.
fn Parser::parse_kv_block(self : Parser) -> Map[String, AVal] raise NcelError {
  if self.is_punct("(") {
    return self.parse_attr_list()
  }
  self.expect_punct("{") |> ignore
  let attrs : Map[String, AVal] = Map::new()
  while !self.is_punct("}") {
    let key = self.expect_kind("IDENT")
    self.expect_punct(":") |> ignore
    attrs.set(key.value, self.parse_attr_value())
    self.eat_punct(",") |> ignore
  }
  self.expect_punct("}") |> ignore
  attrs
}

///| Hex colour literal -> RGB.
fn color_from_hex(s : String) -> Color {
  let mut h = s
  if h.has_prefix("#") {
    h = h.substring(start=1, end=h.length())
  }
  if h.length() == 3 {
    let r = h.get_char(0).unwrap()
    let g = h.get_char(1).unwrap()
    let b = h.get_char(2).unwrap()
    let s2 = String::from_array([r, r, g, g, b, b])
    h = s2
  }
  let r = parse_hex2(h.substring(start=0, end=2))
  let g = parse_hex2(h.substring(start=2, end=4))
  let b = parse_hex2(h.substring(start=4, end=6))
  CRgb(r, g, b)
}

///| Two hex digits -> 0..255.
fn parse_hex2(s : String) -> Int {
  let a = hex_digit(s.get_char(0).unwrap())
  let b = hex_digit(s.get_char(1).unwrap())
  a * 16 + b
}

///| One hex digit value.
fn hex_digit(c : Char) -> Int {
  if c >= '0' && c <= '9' {
    c.to_int() - '0'.to_int()
  } else if c >= 'a' && c <= 'f' {
    c.to_int() - 'a'.to_int() + 10
  } else {
    c.to_int() - 'A'.to_int() + 10
  }
}

///| One attribute value (colour, string/unit, numeric expression, or tuple).
fn Parser::parse_attr_value(self : Parser) -> AVal raise NcelError {
  let tok = self.cur()
  if tok.kind == "HEX" {
    self.adv() |> ignore
    return AColor(color_from_hex(tok.value))
  }
  if tok.kind == "PUNCT" && tok.value == "$" {
    self.adv() |> ignore
    let ref_tok = self.expect_kind("IDENT")
    match self.active_palette.get(ref_tok.value) {
      Some(c) => return AColor(c)
      None =>
        raise mkerr(ref_tok.line, ref_tok.col, "Undefined palette color '$" + ref_tok.value + "'")
    }
  }
  if tok.kind == "STRING" {
    self.adv() |> ignore
    return AStr(tok.value.substring(start=1, end=tok.value.length() - 1))
  }
  if tok.kind == "UNIT" {
    self.adv() |> ignore
    return AStr(tok.value)
  }
  if tok.kind == "IDENT" && tok.value == "rgb" && self.peek_at(1).value == "(" {
    self.adv() |> ignore
    self.expect_punct("(") |> ignore
    let r = py_round(self.eval_const(ANum(self.parse_expr())))
    self.expect_punct(",") |> ignore
    let g = py_round(self.eval_const(ANum(self.parse_expr())))
    self.expect_punct(",") |> ignore
    let b = py_round(self.eval_const(ANum(self.parse_expr())))
    self.expect_punct(")") |> ignore
    return AColor(CRgb(r, g, b))
  }
  if tok.kind == "PUNCT" && tok.value == "(" {
    self.adv() |> ignore
    let items : Array[AVal] = []
    items.push(self.parse_attr_value())
    while self.eat_punct(",") {
      items.push(self.parse_attr_value())
    }
    self.expect_punct(")") |> ignore
    return ATuple(items)
  }
  ANum(self.parse_expr())
}

///| Expression: term { (+|-) term }.
fn Parser::parse_expr(self : Parser) -> Expr raise NcelError {
  let mut node = self.parse_term()
  while self.is_punct("+") || self.is_punct("-") {
    let op = self.adv().value
    let rhs = self.parse_term()
    node = if op == "+" {
      EAdd(node, rhs)
    } else {
      ESub(node, rhs)
    }
  }
  node
}

///| Term: factor { (*|/) factor }.
fn Parser::parse_term(self : Parser) -> Expr raise NcelError {
  let mut node = self.parse_factor()
  while self.is_punct("*") || self.is_punct("/") {
    let op = self.adv().value
    let rhs = self.parse_factor()
    node = if op == "*" {
      EMul(node, rhs)
    } else {
      EDiv(node, rhs)
    }
  }
  node
}

///| Factor: unary minus, number, unit number, function call, variable, or group.
fn Parser::parse_factor(self : Parser) -> Expr raise NcelError {
  let tok = self.cur()
  if tok.kind == "PUNCT" && tok.value == "-" {
    self.adv() |> ignore
    return ENeg(self.parse_factor())
  }
  if tok.kind == "NUMBER" {
    self.adv() |> ignore
    return EConst(parse_double_at(tok.value, tok.line, tok.col))
  }
  if tok.kind == "UNIT" {
    self.adv() |> ignore
    return EConst(parse_double_at(strip_unit(tok.value), tok.line, tok.col))
  }
  if tok.kind == "IDENT" {
    let ident = self.adv().value
    if self.is_punct("(") {
      self.adv() |> ignore
      let args : Array[Expr] = []
      if !self.is_punct(")") {
        args.push(self.parse_expr())
        while self.eat_punct(",") {
          args.push(self.parse_expr())
        }
      }
      self.expect_punct(")") |> ignore
      if ident == "lerp" {
        if args.length() != 3 {
          raise mkerr(tok.line, tok.col, "lerp expects 3 arguments")
        }
        return ELerp(args[0], args[1], args[2])
      } else if ident == "sin" {
        if args.length() != 1 {
          raise mkerr(tok.line, tok.col, "sin expects 1 argument")
        }
        return ESin(args[0])
      } else if ident == "cos" {
        if args.length() != 1 {
          raise mkerr(tok.line, tok.col, "cos expects 1 argument")
        }
        return ECos(args[0])
      } else if ident == "step" {
        if args.length() != 2 {
          raise mkerr(tok.line, tok.col, "step expects 2 arguments")
        }
        return EStep(args[0], args[1])
      } else {
        raise mkerr(tok.line, tok.col, "Unknown function '" + ident + "'")
      }
    }
    return EVar(ident)
  }
  if tok.kind == "PUNCT" && tok.value == "(" {
    self.adv() |> ignore
    let inner = self.parse_expr()
    self.expect_punct(")") |> ignore
    return inner
  }
  raise mkerr(tok.line, tok.col, "Expected expression, got '" + (if tok.value.length() > 0 { tok.value } else { tok.kind }) + "'")
}

///| Evaluate a pure expression against an environment.
fn eval_expr(e : Expr, env : Map[String, Double]) -> Double raise NcelError {
  match e {
    EConst(v) => v
    EVar(name) =>
      match env.get(name) {
        Some(v) => v
        None => raise mkerr(1, 1, "Undefined parameter or variable '" + name + "'")
      }
    ENeg(a) => -eval_expr(a, env)
    EAdd(a, b) => eval_expr(a, env) + eval_expr(b, env)
    ESub(a, b) => eval_expr(a, env) - eval_expr(b, env)
    EMul(a, b) => eval_expr(a, env) * eval_expr(b, env)
    EDiv(a, b) => {
      let num = eval_expr(a, env)
      let den = eval_expr(b, env)
      if den.abs() > 0.000000000001 {
        num / den
      } else {
        num / 1.0
      }
    }
    ELerp(a, b, u) => {
      let uu = eval_expr(u, env)
      let c = if uu < 0.0 { 0.0 } else if uu > 1.0 { 1.0 } else { uu }
      let av = eval_expr(a, env)
      let bv = eval_expr(b, env)
      av + (bv - av) * c
    }
    ESin(a) => @math.sin(eval_expr(a, env))
    ECos(a) => @math.cos(eval_expr(a, env))
    EStep(edge, x) => {
      let ed = eval_expr(edge, env)
      let xv = eval_expr(x, env)
      if xv < ed { 0.0 } else { 1.0 }
    }
  }
}

///| Evaluate an attribute value as a compile-time constant.
fn Parser::eval_const(self : Parser, v : AVal) -> Double raise NcelError {
  match v {
    AStr(s) => parse_double_at(strip_unit(s), 1, 1)
    ANum(e) => eval_expr(e, default_env())
    AColor(_) => raise mkerr(1, 1, "Cannot evaluate a colour as a number")
    ATuple(_) => raise mkerr(1, 1, "Cannot evaluate a tuple as a number")
  }
}

///| Default constant environment used by `_eval_const`.
fn default_env() -> Map[String, Double] {
  let env : Map[String, Double] = Map::new()
  env.set("t", 0.0)
  env.set("f", 0.0)
  env.set("seed", 42.0)
  env
}

///| Convert an attribute value to an expression (for translate components).
fn val_to_expr(self_parser : Parser, v : AVal) -> Expr raise NcelError {
  match v {
    ANum(e) => e
    AStr(s) => EConst(parse_double_at(strip_unit(s), 1, 1))
    _ => raise mkerr(1, 1, "Expected a numeric attribute value")
  }
}

///| Resolve a colour attribute value to an RGB colour.
fn Parser::resolve_color(self : Parser, v : AVal) -> Color raise NcelError {
  match v {
    AColor(c) => c
    AStr(s) =>
      if s.has_prefix("#") {
        color_from_hex(s)
      } else {
        raise mkerr(1, 1, "Invalid color attribute value")
      }
    ANum(e) =>
      match e {
        EVar(name) =>
          match self.active_palette.get(name) {
            Some(c) => c
            None => raise mkerr(1, 1, "Invalid color attribute value")
          }
        _ => raise mkerr(1, 1, "Invalid color attribute value")
      }
    ATuple(_) => raise mkerr(1, 1, "Invalid color attribute value")
  }
}

///| Colour extraction: `color`/`fill`, then `tone`, then a default tone.
fn Parser::extract_color(self : Parser, attrs : Map[String, AVal], default_tone : Int) -> Color raise NcelError {
  match attrs.get("color") {
    Some(v) => return self.resolve_color(v)
    None => ()
  }
  match attrs.get("fill") {
    Some(v) => return self.resolve_color(v)
    None => ()
  }
  match attrs.get("tone") {
    Some(v) => {
      let t = py_round(self.eval_const(v))
      return CTone(t)
    }
    None => ()
  }
  CTone(default_tone)
}

///| Outline extraction for `cel` / `outline:` / `ink_width:`.
fn Parser::extract_outline(self : Parser, attrs : Map[String, AVal], is_cel : Bool) -> (Color?, Double) raise NcelError {
  let has_outline = attrs.contains("outline")
  let has_ink_width = attrs.contains("ink_width")
  if !has_outline && !has_ink_width && !is_cel {
    return (None, 0.0)
  }
  let default_col = match self.active_palette.get("ink") {
    Some(c) => c
    None => CRgb(13, 13, 13)
  }
  if has_outline {
    let ov = attrs.get("outline").unwrap()
    match ov {
      ATuple(items) =>
        if items.length() == 2 {
          let col = self.resolve_color(items[0])
          let w = self.eval_const(items[1])
          return (Some(col), w)
        } else {
          let w = self.eval_const(ov)
          return (Some(default_col), w)
        }
      _ => {
        let w = self.eval_const(ov)
        return (Some(default_col), w)
      }
    }
  }
  if has_ink_width {
    let w = self.eval_const(attrs.get("ink_width").unwrap())
    let col = match attrs.get("ink") {
      Some(v) => self.resolve_color(v)
      None => default_col
    }
    return (Some(col), w)
  }
  (None, 0.0)
}

///| Boil extraction: bare amplitude or `(amplitude, frequency)`.
fn Parser::extract_boil(self : Parser, attrs : Map[String, AVal]) -> Boil? raise NcelError {
  match attrs.get("boil") {
    None => None
    Some(b) =>
      match b {
        ATuple(items) =>
          if items.length() >= 2 {
            Some({ amp: self.eval_const(items[0]), freq: self.eval_const(items[1]) })
          } else {
            Some({ amp: self.eval_const(b), freq: 1.0 })
          }
        _ => Some({ amp: self.eval_const(b), freq: 1.0 })
      }
  }
}

///| Translate extraction: `translate: (dx, dy)` or separate `dx`/`dy`.
fn Parser::extract_translate(self : Parser, attrs : Map[String, AVal]) -> (Expr, Expr) raise NcelError {
  match attrs.get("translate") {
    Some(ATuple(items)) =>
      if items.length() == 2 {
        return (val_to_expr(self, items[0]), val_to_expr(self, items[1]))
      }
    _ => ()
  }
  let dx = match attrs.get("dx") {
    Some(v) => val_to_expr(self, v)
    None => EConst(0.0)
  }
  let dy = match attrs.get("dy") {
    Some(v) => val_to_expr(self, v)
    None => EConst(0.0)
  }
  (dx, dy)
}

///| Palette declaration.
fn Parser::parse_palette(self : Parser) -> Map[String, Color] raise NcelError {
  self.expect_ident("palette") |> ignore
  let raw = self.parse_kv_block()
  let out : Map[String, Color] = Map::new()
  for k, v in raw {
    match v {
      AColor(c) => out.set(k, c)
      ANum(e) => {
        let t = py_round(eval_expr(e, default_env()))
        out.set(k, CTone(t))
      }
      AStr(s) =>
        if s.has_prefix("#") {
          out.set(k, color_from_hex(s))
        }
      ATuple(_) => ()
    }
  }
  out
}

///| Paper declaration.
fn Parser::parse_paper(self : Parser) -> PaperSpec raise NcelError {
  let kw = self.expect_ident("paper")
  let attrs = self.parse_kv_block()
  let color = self.extract_color(attrs, 239)
  let aa = match attrs.get("antialias_grid") {
    Some(v) => self.eval_const(v).to_int()
    None => 4
  }
  let grain = match attrs.get("grain") {
    Some(v) => self.eval_const(v)
    None => 0.0
  }
  { color: color, aa: aa, grain: grain, line: kw.line, col: kw.col }
}

///| Layer/wash/cel statement.
fn Parser::parse_layer(self : Parser, is_cel : Bool) -> LayerNode raise NcelError {
  let kw = self.adv()
  let name_tok = self.expect_kind("IDENT")
  let attrs = self.parse_attr_list()
  self.expect_punct("{") |> ignore
  let payload_tok = self.expect_kind("STRING")
  self.expect_punct("}") |> ignore
  let color = self.extract_color(attrs, 14)
  let (rings_count, has_rings_count) = match attrs.get("rings") {
    Some(v) => (py_round(self.eval_const(v)), true)
    None => (0, false)
  }
  let boil = self.extract_boil(attrs)
  let (tx, ty) = self.extract_translate(attrs)
  let (outline_color, outline_width) = self.extract_outline(attrs, is_cel)
  {
    name: name_tok.value,
    color: color,
    rings_count: rings_count,
    has_rings_count: has_rings_count,
    payload: payload_tok.value.substring(start=1, end=payload_tok.value.length() - 1),
    boil: boil,
    tx: tx,
    ty: ty,
    outline_color: outline_color,
    outline_width: outline_width,
    line: kw.line,
    col: kw.col,
  }
}

///| Swarm statement.
fn Parser::parse_swarm(self : Parser) -> SwarmNode raise NcelError {
  let kw = self.adv()
  let name_tok = self.expect_kind("IDENT")
  let attrs = self.parse_attr_list()
  self.expect_punct("{") |> ignore
  let payload_tok = self.expect_kind("STRING")
  self.expect_punct("}") |> ignore
  let color = self.extract_color(attrs, 14)
  let agents = match attrs.get("agents") {
    Some(v) => self.eval_const(v).to_int()
    None => 1
  }
  let boil = self.extract_boil(attrs)
  let (tx, ty) = self.extract_translate(attrs)
  {
    name: name_tok.value,
    agents: agents,
    color: color,
    payload: payload_tok.value.substring(start=1, end=payload_tok.value.length() - 1),
    boil: boil,
    tx: tx,
    ty: ty,
    line: kw.line,
    col: kw.col,
  }
}

///| Stroke statement.
fn Parser::parse_stroke(self : Parser) -> StrokeNode raise NcelError {
  let kw = self.expect_ident("stroke")
  let name_tok = self.expect_kind("IDENT")
  let attrs = self.parse_attr_list()
  self.expect_punct("{") |> ignore
  let points : Array[(Expr, Expr)] = []
  while !self.is_punct("}") {
    self.expect_punct("(") |> ignore
    let x = self.parse_expr()
    self.expect_punct(",") |> ignore
    let y = self.parse_expr()
    self.expect_punct(")") |> ignore
    self.eat_punct(",") |> ignore
    points.push((x, y))
  }
  self.expect_punct("}") |> ignore
  let color = self.extract_color(attrs, 14)
  let (w0, w1) = match attrs.get("taper") {
    Some(ATuple(items)) =>
      if items.length() == 2 {
        (self.eval_const(items[0]), self.eval_const(items[1]))
      } else {
        let w = self.eval_const(attrs.get("width").unwrap_or(ANum(EConst(2.5))))
        (w, w)
      }
    _ => {
      let w = self.eval_const(attrs.get("width").unwrap_or(ANum(EConst(2.5))))
      (w, w)
    }
  }
  let boil = self.extract_boil(attrs)
  {
    name: name_tok.value,
    color: color,
    width_start: w0,
    width_end: w1,
    points: points,
    boil: boil,
    line: kw.line,
    col: kw.col,
  }
}

///| Ribbon statement.
fn Parser::parse_ribbon(self : Parser) -> RibbonNode raise NcelError {
  let kw = self.expect_ident("ribbon")
  let name_tok = self.expect_kind("IDENT")
  let attrs = if self.is_punct("(") {
    self.parse_attr_list()
  } else {
    Map::new()
  }
  self.expect_punct("{") |> ignore
  let points : Array[(Expr, Expr, Double)] = []
  while !self.is_punct("}") {
    self.expect_punct("(") |> ignore
    let x = self.parse_expr()
    self.expect_punct(",") |> ignore
    let y = self.parse_expr()
    self.expect_punct(",") |> ignore
    let w = self.eval_const(ANum(self.parse_expr()))
    self.expect_punct(")") |> ignore
    self.eat_punct(",") |> ignore
    points.push((x, y, w))
  }
  self.expect_punct("}") |> ignore
  let color = self.extract_color(attrs, 14)
  let boil = self.extract_boil(attrs)
  {
    name: name_tok.value,
    color: color,
    points: points,
    boil: boil,
    line: kw.line,
    col: kw.col,
  }
}

///| def block.
fn Parser::parse_def(self : Parser) -> DefBlock raise NcelError {
  let kw = self.expect_ident("def")
  let name_tok = self.expect_kind("IDENT")
  let params : Map[String, Double] = Map::new()
  if self.is_punct("(") {
    let raw = self.parse_attr_list()
    for k, v in raw {
      params.set(k, self.eval_const(v))
    }
  }
  self.expect_punct("{") |> ignore
  let items : Array[Item] = []
  while !self.is_punct("}") {
    let tok = self.cur()
    if tok.kind == "EOF" {
      raise mkerr(kw.line, kw.col, "Unclosed 'def " + name_tok.value + "' block")
    }
    if tok.kind == "IDENT" && (tok.value == "layer" || tok.value == "wash" || tok.value == "cel") {
      items.push(ILayer(self.parse_layer(tok.value == "cel")))
    } else if tok.kind == "IDENT" && (tok.value == "bend_swarm" || tok.value == "swarm") {
      items.push(ISwarm(self.parse_swarm()))
    } else if tok.kind == "IDENT" && tok.value == "stroke" {
      items.push(IStroke(self.parse_stroke()))
    } else if tok.kind == "IDENT" && tok.value == "ribbon" {
      items.push(IRibbon(self.parse_ribbon()))
    } else {
      raise mkerr(tok.line, tok.col, "Unsupported statement '" + tok.value + "' inside def block")
    }
  }
  self.expect_punct("}") |> ignore
  { name: name_tok.value, params: params, items: items }
}

///| use statement.
fn Parser::parse_use(self : Parser) -> UseNode raise NcelError {
  let kw = self.expect_ident("use")
  let name_tok = self.expect_kind("IDENT")
  let args = if self.is_punct("(") {
    self.parse_attr_list()
  } else {
    Map::new()
  }
  self.eat_punct(";") |> ignore
  { def_name: name_tok.value, args: args, line: kw.line, col: kw.col }
}

///| drop statement.
fn Parser::parse_drop(self : Parser) -> DropNode raise NcelError {
  let kw = self.expect_ident("drop")
  let name_tok = self.expect_kind("IDENT")
  self.eat_punct(";") |> ignore
  { target: name_tok.value, line: kw.line, col: kw.col }
}

///| Determine a scene/film attribute as a string (precision).
fn attr_as_string(attrs : Map[String, AVal], key : String, fallback : String) -> String {
  match attrs.get(key) {
    Some(AStr(s)) => s
    _ => fallback
  }
}

///| Parse the body shared by `scene`, `film` and `frame k`.
fn Parser::parse_scene_body(
  self : Parser,
  kw : Token,
  label : String,
  width : Int,
  height : Int,
  fps : Int,
  precision : String,
  seed : Int,
  paper0 : PaperSpec,
  palette : Map[String, Color],
) -> (PaperSpec, Map[String, DefBlock], Array[Item]) raise NcelError {
  let defs : Map[String, DefBlock] = Map::new()
  let items : Array[Item] = []
  let mut paper = paper0
  while !self.is_punct("}") {
    let tok = self.cur()
    if tok.kind == "EOF" {
      raise mkerr(kw.line, kw.col, "Unclosed '" + label + "' block")
    }
    if tok.kind == "IDENT" && tok.value == "palette" {
      let p = self.parse_palette()
      for k, v in p {
        palette.set(k, v)
      }
    } else if tok.kind == "IDENT" && tok.value == "paper" {
      paper = self.parse_paper()
    } else if tok.kind == "IDENT" && tok.value == "def" {
      let d = self.parse_def()
      defs.set(d.name, d)
    } else if tok.kind == "IDENT" && tok.value == "use" {
      items.push(IUse(self.parse_use()))
    } else if tok.kind == "IDENT" && tok.value == "drop" {
      items.push(IDrop(self.parse_drop()))
    } else if tok.kind == "IDENT" && (tok.value == "layer" || tok.value == "wash" || tok.value == "cel") {
      items.push(ILayer(self.parse_layer(tok.value == "cel")))
    } else if tok.kind == "IDENT" && (tok.value == "bend_swarm" || tok.value == "swarm") {
      items.push(ISwarm(self.parse_swarm()))
    } else if tok.kind == "IDENT" && tok.value == "stroke" {
      items.push(IStroke(self.parse_stroke()))
    } else if tok.kind == "IDENT" && tok.value == "ribbon" {
      items.push(IRibbon(self.parse_ribbon()))
    } else {
      raise mkerr(tok.line, tok.col, "Unknown " + label + " statement '" + tok.value + "'")
    }
  }
  self.expect_punct("}") |> ignore
  (paper, defs, items)
}

///| scene declaration.
fn Parser::parse_scene_decl(self : Parser) -> SceneNode raise NcelError {
  let kw = self.expect_ident("scene")
  let name_tok = self.expect_kind("IDENT")
  let attrs = if self.is_punct("(") {
    self.parse_attr_list()
  } else {
    Map::new()
  }
  self.expect_punct("{") |> ignore
  let width = self.attr_int(attrs, "width", 1024)
  let height = self.attr_int(attrs, "height", 1024)
  let fps = self.attr_int(attrs, "fps", 6)
  let seed = self.attr_int(attrs, "seed", 42)
  let precision = attr_as_string(attrs, "precision", "0.25px")
  let palette : Map[String, Color] = Map::new()
  let prev_palette = self.active_palette
  self.active_palette = palette
  let paper0 : PaperSpec = { color: CTone(239), aa: 4, grain: 0.0, line: kw.line, col: kw.col }
  let (paper, defs, items) = self.parse_scene_body(kw, "scene", width, height, fps, precision, seed, paper0, palette)
  self.active_palette = prev_palette
  {
    name: name_tok.value,
    width: width,
    height: height,
    fps: fps,
    precision: precision,
    seed: seed,
    paper: paper,
    defs: defs,
    items: items,
    line: kw.line,
    col: kw.col,
  }
}

///| Read an integer attribute with a default.
fn Parser::attr_int(self : Parser, attrs : Map[String, AVal], key : String, fallback : Int) -> Int raise NcelError {
  match attrs.get(key) {
    Some(v) => self.eval_const(v).to_int()
    None => fallback
  }
}

///| `frame k { ... }` delta inside a film.
fn Parser::parse_frame_override(
  self : Parser,
  width : Int,
  height : Int,
  fps : Int,
  precision : String,
  seed : Int,
  default_paper : PaperSpec,
  parent_palette : Map[String, Color],
) -> (Int, SceneNode) raise NcelError {
  let kw = self.expect_ident("frame")
  let idx_tok = self.expect_kind("NUMBER")
  let f_idx = parse_double_at(idx_tok.value, idx_tok.line, idx_tok.col).to_int()
  self.expect_punct("{") |> ignore
  let local_palette = parent_palette.copy()
  let prev_palette = self.active_palette
  self.active_palette = local_palette
  let paper0 = default_paper
  let (paper, defs, items) = self.parse_scene_body(kw, "frame", width, height, fps, precision, seed, paper0, local_palette)
  self.active_palette = prev_palette
  let node : SceneNode = {
    name: "frame_" + f_idx.to_string(),
    width: width,
    height: height,
    fps: fps,
    precision: precision,
    seed: seed,
    paper: paper,
    defs: defs,
    items: items,
    line: kw.line,
    col: kw.col,
  }
  (f_idx, node)
}

///| film declaration.
fn Parser::parse_film_decl(self : Parser) -> FilmNode raise NcelError {
  let kw = self.expect_ident("film")
  let name_tok = self.expect_kind("IDENT")
  let attrs = if self.is_punct("(") {
    self.parse_attr_list()
  } else {
    Map::new()
  }
  self.expect_punct("{") |> ignore
  let width = self.attr_int(attrs, "width", 1024)
  let height = self.attr_int(attrs, "height", 1024)
  let fps = self.attr_int(attrs, "fps", 6)
  let frames = self.attr_int(attrs, "frames", 2)
  let seed = self.attr_int(attrs, "seed", 42)
  let precision = attr_as_string(attrs, "precision", "0.25px")
  let palette : Map[String, Color] = Map::new()
  let prev_palette = self.active_palette
  self.active_palette = palette
  let paper0 : PaperSpec = { color: CTone(239), aa: 4, grain: 0.0, line: kw.line, col: kw.col }
  let defs : Map[String, DefBlock] = Map::new()
  let items : Array[Item] = []
  let overrides : Map[Int, SceneNode] = Map::new()
  let mut paper = paper0
  while !self.is_punct("}") {
    let tok = self.cur()
    if tok.kind == "EOF" {
      raise mkerr(kw.line, kw.col, "Unclosed 'film' block")
    }
    if tok.kind == "IDENT" && tok.value == "palette" {
      let p = self.parse_palette()
      for k, v in p {
        palette.set(k, v)
      }
    } else if tok.kind == "IDENT" && tok.value == "paper" {
      paper = self.parse_paper()
    } else if tok.kind == "IDENT" && tok.value == "def" {
      let d = self.parse_def()
      defs.set(d.name, d)
    } else if tok.kind == "IDENT" && tok.value == "use" {
      items.push(IUse(self.parse_use()))
    } else if tok.kind == "IDENT" && tok.value == "drop" {
      items.push(IDrop(self.parse_drop()))
    } else if tok.kind == "IDENT" && (tok.value == "layer" || tok.value == "wash" || tok.value == "cel") {
      items.push(ILayer(self.parse_layer(tok.value == "cel")))
    } else if tok.kind == "IDENT" && (tok.value == "bend_swarm" || tok.value == "swarm") {
      items.push(ISwarm(self.parse_swarm()))
    } else if tok.kind == "IDENT" && tok.value == "stroke" {
      items.push(IStroke(self.parse_stroke()))
    } else if tok.kind == "IDENT" && tok.value == "ribbon" {
      items.push(IRibbon(self.parse_ribbon()))
    } else if tok.kind == "IDENT" && tok.value == "frame" {
      let (fi, node) = self.parse_frame_override(width, height, fps, precision, seed, paper, palette)
      overrides.set(fi, node)
    } else {
      raise mkerr(tok.line, tok.col, "Unknown film statement '" + tok.value + "'")
    }
  }
  self.expect_punct("}") |> ignore
  self.active_palette = prev_palette
  {
    name: name_tok.value,
    width: width,
    height: height,
    fps: fps,
    frames: frames,
    precision: precision,
    seed: seed,
    paper: paper,
    defs: defs,
    items: items,
    overrides: overrides,
    line: kw.line,
    col: kw.col,
  }
}

///| Parse a full document.
fn parse_document(source : String) -> Document raise NcelError {
  let toks = lex(source)
  let p : Parser = { toks: toks, idx: 0, active_palette: Map::new() }
  let mut spec = "0.2.0-draft"
  let first = p.cur()
  if first.kind == "IDENT" && first.value == "northcel" {
    p.adv() |> ignore
    let ver = p.cur()
    if ver.kind == "STRING" {
      spec = ver.value.substring(start=1, end=ver.value.length() - 1)
      p.adv() |> ignore
    } else if ver.kind == "NUMBER" {
      spec = ver.value
      p.adv() |> ignore
    } else {
      raise mkerr(ver.line, ver.col, "Expected version string or number after 'northcel'")
    }
    p.eat_punct(";") |> ignore
  }
  let root_tok = p.cur()
  let root = if root_tok.kind == "IDENT" && root_tok.value == "scene" {
    RScene(p.parse_scene_decl())
  } else if root_tok.kind == "IDENT" && root_tok.value == "film" {
    RFilm(p.parse_film_decl())
  } else {
    raise mkerr(
      root_tok.line,
      root_tok.col,
      "Expected 'scene' or 'film' declaration, got '" + (if root_tok.value.length() > 0 { root_tok.value } else { root_tok.kind }) + "'",
    )
  }
  if p.cur().kind != "EOF" {
    let extra = p.cur()
    raise mkerr(extra.line, extra.col, "Unexpected trailing token '" + extra.value + "'")
  }
  { spec_version: spec, root: root }
}
