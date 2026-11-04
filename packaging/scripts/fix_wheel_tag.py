#!/usr/bin/env python3
"""Re-tag a built wheel to the platform tag the bundle actually requires.

`ncel-native` ships prebuilt Linux x86_64 ELF binaries, so `py3-none-any` would be
a false claim ("installable everywhere"). setuptools' `bdist_wheel` insists on
`any` for a package without extension modules, so the tag is rewritten here:
filename, `WHEEL` metadata and the `RECORD` entry for `WHEEL` are kept consistent.

    python3 packaging/scripts/fix_wheel_tag.py dist/ncel_native-0.2.1-py3-none-any.whl \
        --platform manylinux_2_39_x86_64
"""

from __future__ import annotations

import argparse
import base64
import hashlib
import sys
import zipfile
from pathlib import Path

FIXED_DATE = (1980, 1, 1, 0, 0, 0)


def _record_hash(data: bytes) -> str:
    digest = base64.urlsafe_b64encode(hashlib.sha256(data).digest()).rstrip(b"=")
    return "sha256=" + digest.decode()


def retag(wheel: Path, platform_tag: str) -> Path:
    with zipfile.ZipFile(wheel) as source:
        items = [(info, source.read(info.filename)) for info in source.infolist()]

    names = [info.filename for info, _ in items]
    dist_info = next(
        name.split("/")[0] for name in names if name.endswith(".dist-info/WHEEL")
    )
    wheel_path = f"{dist_info}/WHEEL"
    record_path = f"{dist_info}/RECORD"

    payload = {info.filename: data for info, data in items}

    meta = payload[wheel_path].decode("utf-8")
    kept = [
        line
        for line in meta.splitlines()
        if line.strip() and not line.startswith(("Tag:", "Root-Is-Purelib:"))
    ]
    kept.append("Root-Is-Purelib: false")
    kept.append(f"Tag: py3-none-{platform_tag}")
    payload[wheel_path] = ("\n".join(kept) + "\n").encode("utf-8")

    new_lines = []
    for line in payload[record_path].decode("utf-8").splitlines():
        if not line.strip():
            continue
        path = line.rsplit(",", 2)[0]
        if path == wheel_path:
            data = payload[wheel_path]
            new_lines.append(f"{path},{_record_hash(data)},{len(data)}")
        else:
            new_lines.append(line)
    payload[record_path] = ("\n".join(new_lines) + "\n").encode("utf-8")

    new_name = wheel.name.replace("-py3-none-any.whl", f"-py3-none-{platform_tag}.whl")
    if new_name == wheel.name:
        raise SystemExit(f"error: {wheel.name} is not a py3-none-any wheel")
    target = wheel.with_name(new_name)

    with zipfile.ZipFile(target, "w", zipfile.ZIP_DEFLATED) as out:
        for info, _ in items:
            new_info = zipfile.ZipInfo(info.filename, date_time=FIXED_DATE)
            new_info.compress_type = zipfile.ZIP_DEFLATED
            new_info.external_attr = info.external_attr
            out.writestr(new_info, payload[info.filename])

    wheel.unlink()
    return target


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("wheel", type=Path)
    parser.add_argument("--platform", required=True, help="e.g. manylinux_2_39_x86_64")
    args = parser.parse_args()
    target = retag(args.wheel, args.platform)
    print(f"retagged -> {target.name} ({target.stat().st_size} bytes)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
