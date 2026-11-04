// NorthCel native runtime - typed AST for NorthCel 0.2 grammar.
// This file is the MoonBit half of the native pipeline: it defines the typed
// scene/film AST, colours, boil specs, and expression nodes.

///| Structured diagnostic with 1-based line and column (matches the Python CLI).
struct Diag {
  line : Int
  col : Int
  msg : String
}

///| Fatal parse/evaluation error carrying a line:column diagnostic.
suberror NcelError {
  NcelError(Diag)
}

///| An RGB colour. Greyscale `tone` values expand to (n, n, n).
enum Color {
  CTone(Int)
  CRgb(Int, Int, Int)
}

///| Resolve a colour to its three channels.
fn Color::channels(self : Color) -> (Int, Int, Int) {
  match self {
    CTone(v) => (v, v, v)
    CRgb(r, g, b) => (r, g, b)
  }
}

///| A stateless line-boil specification (`boil: 0.75px` or `boil: (amp, freq)`).
struct Boil {
  amp : Double
  freq : Double
}

///| Pure expression node. `f`, `t`, `seed`, def params and `use` args are variables.
enum Expr {
  EConst(Double)
  EVar(String)
  ENeg(Expr)
  EAdd(Expr, Expr)
  ESub(Expr, Expr)
  EMul(Expr, Expr)
  EDiv(Expr, Expr)
  ELerp(Expr, Expr, Expr)
  ESin(Expr)
  ECos(Expr)
  EStep(Expr, Expr)
}

///| Attribute value union (colour, unit/string, numeric expression, or tuple).
enum AVal {
  AColor(Color)
  AStr(String)
  ANum(Expr)
  ATuple(Array[AVal])
}

///| A `layer` / `wash` / `cel` primitive.
struct LayerNode {
  name : String
  color : Color
  rings_count : Int
  has_rings_count : Bool
  payload : String
  boil : Boil?
  tx : Expr
  ty : Expr
  outline_color : Color?
  outline_width : Double
  line : Int
  col : Int
}

///| A `bend_swarm` / `swarm` primitive (agent swarm).
struct SwarmNode {
  name : String
  agents : Int
  color : Color
  payload : String
  boil : Boil?
  tx : Expr
  ty : Expr
  line : Int
  col : Int
}

///| A `stroke` primitive with optional taper.
struct StrokeNode {
  name : String
  color : Color
  width_start : Double
  width_end : Double
  points : Array[(Expr, Expr)]
  boil : Boil?
  line : Int
  col : Int
}

///| A `ribbon` primitive with per-vertex widths.
struct RibbonNode {
  name : String
  color : Color
  points : Array[(Expr, Expr, Double)]
  boil : Boil?
  line : Int
  col : Int
}

///| `use Name(args)`
struct UseNode {
  def_name : String
  args : Map[String, AVal]
  line : Int
  col : Int
}

///| `drop name`
struct DropNode {
  target : String
  line : Int
  col : Int
}

///| A scene item (paint-order primitive, def use, or frame delta).
enum Item {
  ILayer(LayerNode)
  ISwarm(SwarmNode)
  IStroke(StrokeNode)
  IRibbon(RibbonNode)
  IUse(UseNode)
  IDrop(DropNode)
}

///| A reusable `def` block.
struct DefBlock {
  name : String
  params : Map[String, Double]
  items : Array[Item]
}

///| A paper declaration.
struct PaperSpec {
  color : Color
  aa : Int
  grain : Double
  line : Int
  col : Int
}

///| A `scene` declaration (also used as a frame override body).
struct SceneNode {
  name : String
  width : Int
  height : Int
  fps : Int
  precision : String
  seed : Int
  paper : PaperSpec
  defs : Map[String, DefBlock]
  items : Array[Item]
  line : Int
  col : Int
}

///| A `film` declaration with `frame k { ... }` overrides.
struct FilmNode {
  name : String
  width : Int
  height : Int
  fps : Int
  frames : Int
  precision : String
  seed : Int
  paper : PaperSpec
  defs : Map[String, DefBlock]
  items : Array[Item]
  overrides : Map[Int, SceneNode]
  line : Int
  col : Int
}

///| Document root: either a static scene or a film.
enum Root {
  RScene(SceneNode)
  RFilm(FilmNode)
}

///| Parsed document with its declared spec version.
struct Document {
  spec_version : String
  root : Root
}
