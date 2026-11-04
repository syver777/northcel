# Security Policy — NorthCel (`.ncel`)

## Safe-by-Design Execution Model

Unlike general-purpose scripting formats (`scene.html` or arbitrary Python scripts), a `.ncel` file is a **pure data and mathematical expression AST**:
- `.ncel` files cannot import modules, access the filesystem, make network requests, or execute shell commands.
- Expressions are restricted to pure arithmetic (`+`, `-`, `*`, `/`) and bounded mathematical functions (`lerp`, `sin`, `cos`, `step`).
- Canvas dimensions are bounded (`1..8192`) and supersampling grids are restricted to `(1, 2, 4, 8)` to prevent memory-exhaustion denial-of-service attacks.

## Reporting a Vulnerability

Please report security issues to `contact@northnoir.com` with `[NorthCel Security]` in the subject line.
