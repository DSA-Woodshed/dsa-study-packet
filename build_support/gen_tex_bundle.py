"""Assemble pinned TeX resources into a deterministic offline Tectonic bundle."""

from __future__ import annotations

import argparse
import hashlib
import json
import zipfile
from pathlib import Path


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--lock", type=Path, required=True)
    parser.add_argument("--input-dir", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    lock = json.loads(args.lock.read_text(encoding="utf-8"))
    digest = hashlib.sha256(
        json.dumps(lock, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()
    files = {"SHA256SUM": digest.encode()}
    for resource in lock["resources"]:
        data = (args.input_dir / resource["name"]).read_bytes()
        if (
            len(data) != resource["length"]
            or hashlib.sha256(data).hexdigest() != resource["sha256"]
        ):
            raise ValueError(f"resource differs from lock: {resource['name']}")
        files[resource["name"]] = data
    with zipfile.ZipFile(args.output, "w") as bundle:
        for name, data in sorted(files.items()):
            info = zipfile.ZipInfo(name, date_time=(1980, 1, 1, 0, 0, 0))
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = 0o644 << 16
            bundle.writestr(info, data, compresslevel=9)


if __name__ == "__main__":
    main()
