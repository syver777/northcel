"""`northcel` command-line entry point (also installed as `ncel`).

Dispatch rule (this is the whole product promise): if the native runtime can run
here, run it. If it cannot, say why, use the Python reference and label the result.

There is one install (`pip install northcel`); `northcel` is the command, `ncel` is
the short alias, and both reach this module.
"""

from __future__ import annotations

import sys

from . import (
    EXIT_NO_NATIVE,
    NATIVE_RUNTIME_VERSION,
    SPEC_VERSION,
    __version__,
    fallback,
    native,
    paths,
)
from . import doctor as doctor_mod
from . import toolchain as toolchain_mod
from . import verify as verify_mod

USAGE = """northcel — NorthCel (.ncel) command line

usage: northcel <command> [options]        (short alias: ncel)

  doctor  [--json]                     stage availability, exact versions, platform verdict
  verify  [--json] [--keep DIR]        render the bundled fixtures with the native runtime
  check   FILE [--json]                parse + validate (native when available)
  info    FILE [--json]                scene/film metadata, layers, rings, vertices
  shapes  FILE [--frame N] [--ids …] [--color …] [--area-min …]
                                       list/query evaluated shapes with stable ids
  diff    FILE --against IMAGE […]   render vs reference error, per group/region, heatmap
  onion   FILE -o OUT.png […]        onion-skin neighbouring frames or a reference
  contact FILE -o OUT.png|DIR […]    contact sheet(s), optionally one per transition
  continuity FILE --group NAME […]   per-frame bbox/scale/position continuity
  distinct FILE […]                  distinct frames/s (320x180 film-proof metric)
  perceive <segment|vectorize|flow|guide> […] --out PATH [--json]
                                       optional offline helpers; tools suggest, the AI decides
  render  FILE [-o OUT.png] [--frame N] [--seed N] [--json]
  film    FILE -o OUTDIR [--frames 0..5] [--mp4 OUT.mp4] [--json]
  fmt     FILE [-w|--write] [--check]  canonical formatting (Python reference)
  fit     IMAGE -o FILE [--colors N]  offline vector contour fitting (requires [fit])
  tween   A.ncel B.ncel -o FILE [--match]
                                       contour in-betweens (--match: across topology
                                       mismatch, spec 0.4 film); never a quality judge
  fit     IMAGE -o FILE --stacked      painter's-order solid shapes instead of a planar map
  guide                                offline authoring guide
  toolchain <status|install> [--json] [--dry-run]
  version, --version                   versions (native runtime + spec)

Global: --no-native  force the labelled Python reference path (never called "native")
Spec 0.4/0.5 documents (mix, morph, opacity, frame A..B, groups, warp, nudge) always
use the labelled Python reference: the native runtime 0.4.0 implements spec 0.3.
Platform: Linux x86_64, glibc >= 2.39, Mesa EGL/llvmpipe. macOS/Windows are not
supported natively in this release; `northcel doctor` explains exactly what is
missing and every render there is labelled `python-reference`.
"""


def _version_line() -> str:
    native_version = NATIVE_RUNTIME_VERSION
    usable, _ = native.available()
    if usable:
        doc = native.doctor_json() or {}
        if doc.get("version"):
            native_version = doc["version"]
    state = "native" if usable else "python-reference only"
    return (f"northcel {__version__} (native runtime {native_version} implements spec 0.3.0-draft, "
            f"spec {SPEC_VERSION}, {state})")


def _pop_flag(args: list[str], *names: str) -> bool:
    hit = False
    for name in names:
        while name in args:
            args.remove(name)
            hit = True
    return hit


def _pop_option(args: list[str], *names: str) -> str | None:
    for name in names:
        for index, token in enumerate(args):
            if token == name and index + 1 < len(args):
                value = args[index + 1]
                del args[index : index + 2]
                return value
            if token.startswith(name + "="):
                value = token.split("=", 1)[1]
                del args[index]
                return value
    return None


#: The newest spec minor the bundled native runtime implements (spec 0.3).
NATIVE_SPEC_MINOR = 3


def spec04_reason(args: list[str]) -> str | None:
    """Why a document must use the reference: its interpreted spec exceeds native 0.3.

    The native runtime implements spec 0.3. A document that uses `mix`, `morph`,
    `frame A..B`, `opacity`, `group`, `warp` or `nudge`, or has a 0.4+ spec, is routed to the
    labelled Python reference instead of being rendered (or rejected) by a runtime
    that does not know those rules. Old-spec files the reference cannot parse go
    to native unchanged. Newer/headerless files keep reference syntax diagnostics.
    Headerless files use the current spec, not the native runtime's older default.
    """
    files = [a for a in args if not a.startswith("-")]
    if not files:
        return None
    try:
        from pathlib import Path

        from ..parser import NorthCelSyntaxError, parse_ncel, tokenize
        from ..validator import spec04_features, spec05_features, spec_minor

        source = Path(files[0]).read_text(encoding="utf-8")
        tokens = tokenize(source)
        declared = tokens[0].value == "northcel"
    except (OSError, UnicodeDecodeError, NorthCelSyntaxError, ValueError):
        return None
    try:
        doc = parse_ncel(source)
    except (NorthCelSyntaxError, ValueError):
        doc = None
    if doc:
        version = doc.spec_version
    elif declared:
        version = tokens[1].value.strip('"')
    else:
        version = SPEC_VERSION if tokens[0].value in ("scene", "film") else "0.3"
    features = sorted({name for name, _line, _col in spec04_features(doc)}
                      | {name for name, _line, _col in spec05_features(doc)}) if doc else []
    if features:
        label = "spec 0.4/0.5 features" if any(f in ("group", "warp", "nudge") for f in features) else "spec 0.4 features"
        return (
            f"{files[0]} uses {label} ({', '.join(features)}); the native runtime "
            f"{NATIVE_RUNTIME_VERSION} implements spec 0.3 only"
        )
    if spec_minor(version) > NATIVE_SPEC_MINOR:
        interpretation = "declares" if declared else "defaults to"
        return (
            f"{files[0]} {interpretation} spec {version}; the native runtime "
            f"{NATIVE_RUNTIME_VERSION} implements spec 0.3 only"
        )
    return None


def _native_or_reason(args: list[str], command: str) -> tuple[bool, str | None]:
    if _pop_flag(args, "--no-native", "--python"):
        return False, "explicitly requested with --no-native"
    usable, reason = native.available() if command != "" else (False, None)
    if usable:
        newer = spec04_reason(args)
        if newer:
            return False, newer
    return usable, reason


def _passthrough(command: str, args: list[str], strip_native_only: bool = True) -> int:
    usable, reason = _native_or_reason(args, command)
    if strip_native_only:
        _pop_flag(args, "--require-full")
    if not usable:
        fallback.notify(reason)
        return fallback.delegate([command, *args])
    return native.run([command, *args]).returncode


def _renderer_choice(args: list[str]) -> str:
    for i, arg in enumerate(args):
        if arg == "--renderer" and i + 1 < len(args):
            return args[i + 1]
        if arg.startswith("--renderer="):
            return arg.split("=", 1)[1]
    return "reference"


def _cmd_render(args: list[str]) -> int:
    if _renderer_choice(args) == "vello":
        # Vello reads NCIR v2 from the Python evaluator; never the native tier.
        from ..cli import main as reference_main

        return reference_main(["render", *args])
    usable, reason = _native_or_reason(args, "render")
    if usable:
        return native.run(["render", *args]).returncode
    fallback.notify(reason)
    as_json = _pop_flag(args, "--json")
    out = _pop_option(args, "-o", "--out")
    frame_raw = _pop_option(args, "-f", "--frame") or "0"
    seed_raw = _pop_option(args, "--seed")
    files = [a for a in args if not a.startswith("-")]
    if not files:
        print("usage: northcel render FILE [-o OUT.png] [--frame N] [--seed N]", file=sys.stderr)
        return 2
    try:
        frame = int(frame_raw)
        seed = int(seed_raw) if seed_raw is not None else None
    except ValueError:
        print("northcel: --frame/--seed must be integers", file=sys.stderr)
        return 2
    return fallback.render(files[0], out, frame, seed, as_json)


def _cmd_film(args: list[str]) -> int:
    if _renderer_choice(args) == "vello":
        from ..cli import main as reference_main

        return reference_main(["film", *args])
    usable, reason = _native_or_reason(args, "film")
    if usable:
        return native.run(["film", *args]).returncode
    fallback.notify(reason)
    as_json = _pop_flag(args, "--json")
    out_dir = _pop_option(args, "-o", "--out-dir")
    frames = _pop_option(args, "--frames")
    mp4 = _pop_option(args, "--mp4")
    files = [a for a in args if not a.startswith("-")]
    if not files or not out_dir:
        print("usage: northcel film FILE -o OUTDIR [--frames 0..5] [--mp4 OUT.mp4]", file=sys.stderr)
        return 2
    return fallback.film(files[0], out_dir, frames, mp4, as_json)


def _cmd_guide(args: list[str]) -> int:
    if paths.GUIDE.is_file():
        sys.stdout.write(paths.GUIDE.read_text(encoding="utf-8"))
        return 0
    return fallback.delegate(["guide", *args])


def _cmd_toolchain(args: list[str]) -> int:
    as_json = _pop_flag(args, "--json")
    dry_run = _pop_flag(args, "--dry-run")
    action = next((a for a in args if not a.startswith("-")), "status")
    return toolchain_mod.cmd_toolchain(action, as_json, dry_run)


def main(argv: list[str] | None = None) -> int:
    args = list(sys.argv[1:] if argv is None else argv)
    if not args or args[0] in {"-h", "--help", "help"}:
        print(USAGE, end="")
        return 0

    leading = []
    while args and args[0] in {"--no-native", "--python"}:
        leading.append(args.pop(0))
    if not args:
        print(USAGE, end="")
        return 0
    command, rest = args[0], leading + args[1:]
    if command == "fit":
        from ..fitting import main as fit_main
        return fit_main(rest)
    if command == "tween":
        from ..tween import main as tween_main
        return tween_main(rest)
    if command == "perceive":
        return fallback.delegate(["perceive", *rest])

    if command in {"--version", "version", "-V"}:
        print(_version_line())
        return 0

    if command == "doctor":
        return doctor_mod.cmd_doctor(_pop_flag(rest, "--json"))

    if command == "verify":
        as_json = _pop_flag(rest, "--json")
        keep = _pop_option(rest, "--keep")
        return verify_mod.cmd_verify(as_json, keep)

    if command == "check":
        return _passthrough("check", rest)
    if command == "info":
        return _passthrough("info", rest)
    if command == "shapes":
        return fallback.delegate(["shapes", *rest])
    if command in {"diff", "onion", "contact", "continuity", "distinct"}:
        # Verification tools are reference-only CPU tools; they are not native stages.
        # Consume launcher routing flags before delegating to the reference parser.
        _pop_flag(rest, "--no-native", "--python")
        return fallback.delegate([command, *rest])

    if command == "fmt":
        # The native runtime has no formatter; formatting is the Python reference.
        return fallback.delegate(["fmt", *rest])

    if command == "guide":
        return _cmd_guide(rest)

    if command == "render":
        return _cmd_render(rest)
    if command == "film":
        return _cmd_film(rest)

    if command == "toolchain":
        return _cmd_toolchain(rest)

    if command in {"--json-doctor"}:
        return doctor_mod.cmd_doctor(True)

    print(f"northcel: unknown command {command!r}\n", file=sys.stderr)
    print(USAGE, end="", file=sys.stderr)
    return 2


__all__ = ["main", "EXIT_NO_NATIVE"]
