"""Generate npm metadata/structural rules and compact guide from authoritative sources.

Run with Python 3 (no installed NorthCel dependencies needed). --check is a CI gate.
The output is `rules.json` (consumed by index.cjs) and the compact guide shipped to npm.
This does not generate a full JS parser or change the language grammar.
"""
from __future__ import annotations

import ast
import json
from pathlib import Path
import runpy
import sys

ROOT = Path(__file__).resolve().parents[1]   # js/northcel
REPO = ROOT.parents[1]                       # repository root
PY = REPO / "python" / "northcel"            # the reference implementation


def generated_assets() -> dict[Path, str]:
    config = runpy.run_path(str(PY / "config.py"))
    tree = ast.parse((PY / "parser.py").read_text())
    methods = {
        n.name: n for n in ast.walk(tree)
        if isinstance(n, ast.FunctionDef)
    }

    def statements(method: str) -> list[str]:
        names: set[str] = set()
        for node in ast.walk(methods[method]):
            if not isinstance(node, ast.Compare) or len(node.ops) != 1:
                continue
            if ast.unparse(node.left) != "tok.value":
                continue
            right = node.comparators[0]
            if isinstance(node.ops[0], ast.Eq) and isinstance(right, ast.Constant):
                names.add(right.value)
            elif isinstance(node.ops[0], ast.In) and isinstance(right, ast.Tuple):
                names.update(ast.literal_eval(right))
        return sorted(names)

    rules = {
        "generated_from": "python/northcel/{config,parser,rings}.py; js/northcel/scripts/sync-assets.py",
        "config": {k: config[k] for k in (
            "LANGUAGE_NAME", "FILE_EXTENSION", "CLI_COMMAND", "CLI_SHORT_ALIAS",
            "PACKAGE_VERSION", "SPEC_VERSION", "SUPPORTED_SPEC_VERSIONS", "DOCS_URL",
        )},
        "statements": {scope: statements(method) for scope, method in (
            ("scene", "parse_scene"), ("film", "parse_film"),
            ("frame", "parse_frame_override"), ("def", "parse_def"),
        )},
        "b63_alphabet": runpy.run_path(str(PY / "rings.py"))["B63_ALPHABET"],
    }
    guide = (REPO / "docs" / "agent-guide.md").read_text()
    compact = guide.split("<!-- npm-guide:start -->\n", 1)[1].split("<!-- npm-guide:end -->", 1)[0]
    return {
        ROOT / "rules.json": json.dumps(rules, indent=2) + "\n",
        ROOT / "northcel/AGENT-GUIDE.md": compact,
    }


if __name__ == "__main__":
    stale = []
    for path, content in generated_assets().items():
        if "--check" in sys.argv:
            if not path.exists() or path.read_text() != content:
                stale.append(str(path.relative_to(ROOT)))
        else:
            path.write_text(content)
    if stale:
        sys.exit("Stale generated assets; run scripts/sync-assets.py: " + ", ".join(stale))
