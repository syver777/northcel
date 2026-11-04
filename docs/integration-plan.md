# NorthCel (`.ncel`) — North Noir CLI & MCP Integration Plan (Plan Only)

> **Status:** Architecture & Interface Plan (`2026-11-03`). Per Phase A rules, no changes were made to `packages/northnoir-cli`, `denodeploy/`, or `supabase/functions/`.

---

## 1. Engine Boundary: How NorthCel Sits Next to Ruvil 2.1 and Ruvil 7.3

North Noir's product positioning and two existing models remain clear and distinct:

| Model / Format | Role in North Noir | Frame Rate & Representation | How `Adjust` Works |
| --- | --- | --- | --- |
| **Ruvil 2.1 (`ruvil_2_1_js`, default)** | Default `.js`-drawn engine | 30 fps HTML5 Canvas (`scene.html`), AnidoodleDraw + RuvilMarks kits, 3 self-review rounds | AI surgically edits the JavaScript drawing code for that section |
| **Ruvil 7.3 (`ruvil_7_3` / `latest`, selectable)** | Selectable images-as-frames model | 6 fps 2D frame illustrations saved to the section frame strip | Creator inspects, downloads, or re-rolls a single frame in place |
| **NorthCel (`.ncel`, `northcel` CLI/MCP)** | Declarative typed drawing language (MoonBit AST + Bend swarms + 4×4 subpixel shader) | 6–30 fps deterministic `.ncel` scene/film files | AI or creator edits a single named `layer`, `stroke`, `ribbon`, or `bend_swarm` block; all other layers stay byte-identical |

---

## 2. Planned North Noir CLI Integration (`packages/northnoir-cli`)

When Phase B implements CLI integration, `northnoir` will gain native `.ncel` support without breaking any existing `scene.html` or `r73` commands:

1. **Auto-detect `.ncel` in `northnoir check` and `northnoir render`:**
   - `northnoir check scene.ncel --still` -> invokes `northcel.cli` validation + renders frame 0 + runs North Noir's readability/contrast quality flags.
   - `northnoir render film.ncel -o out.mp4` -> invokes `northcel.renderer.render_film_frames` and mixes any declared audio cues via `northnoir mix`.
2. **Scaffold Starter `.ncel` Projects:**
   - `northnoir init my-shot --format ncel --duration 4 --fps 12` -> scaffolds `my-shot/scene.ncel` with a starter `film` block, `paper`, `def`, `layer`, and `bend_swarm`.
3. **Files in `packages/northnoir-cli` that would change in Phase B:**
   - `packages/northnoir-cli/pyproject.toml` (add `northcel>=0.1.0` dependency).
   - `packages/northnoir-cli/northnoir_cli/cli.py` (dispatch `.ncel` files in `check`, `render`, and `init --format ncel`).
   - `.opencode/skills/northnoir-draw/SKILL.md` (document the `.ncel` authoring loop alongside `scene.html`).

---

## 3. Planned North Noir MCP Integration (`denodeploy/src/northnoir-mcp/`)

To let Claude Desktop, Claude Code, Cursor, and OpenCode create and edit `.ncel` videos through the North Noir MCP server:

1. **New MCP Tools (Phase B):**
   - `validate_northcel`: Runs the zero-dependency JS validator (`js/northcel/index.cjs`) inside Deno Deploy to return instant `line:column` syntax/ring-chain diagnostics before rendering.
   - `render_northcel_frame` / `render_northcel_film`: Sends validated `.ncel` source to the rendering worker, stores each rendered frame in the section's frame strip (`RF3_frames` compatible), and returns a preview URL + contact sheet.
   - `adjust_northcel_layer`: Surgically replaces or updates a single named `layer`, `stroke`, `ribbon`, or `bend_swarm` block in an existing `.ncel` document and re-renders only affected frames.
2. **Files in `denodeploy/` and `supabase/functions/` that would change in Phase B:**
   - `denodeploy/src/northnoir-mcp/tools.northcel.ts` (new tool definitions for `validate_northcel`, `render_northcel_film`, `adjust_northcel_layer`).
   - `supabase/functions/mcp-gateway/index.ts` (gateway actions routing `.ncel` render jobs).
   - `src/features/mg-studio/Rf3FrameStrip.tsx` (optional "View / Edit `.ncel` Layer" drawer per frame/section).
