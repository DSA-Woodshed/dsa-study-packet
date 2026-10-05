"""Record verified public resource ranges after a deliberate TeX bundle update."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cache", type=Path, required=True)
    parser.add_argument("--bundle-digest", required=True)
    parser.add_argument("--url", required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    directory = args.cache / "bundles" / "data"
    index = {
        name: (int(offset), int(length))
        for name, offset, length in (
            line.split()
            for line in (directory / f"{args.bundle_digest}.index")
            .read_text()
            .splitlines()
        )
    }
    resources = []
    for path in sorted((directory / args.bundle_digest).iterdir()):
        data = path.read_bytes()
        offset, length = index[path.name]
        if len(data) != length:
            raise ValueError(f"partial resource in cache: {path.name}")
        resources.append(
            {
                "name": path.name,
                "offset": offset,
                "length": length,
                "sha256": hashlib.sha256(data).hexdigest(),
            }
        )
    lock = {
        "url": args.url,
        "origin_bundle_digest": args.bundle_digest,
        "resources": resources,
    }
    args.output.write_text(json.dumps(lock, indent=2) + "\n", encoding="utf-8")
    print(
        f"Locked {len(resources)} resources ({sum(r['length'] for r in resources)} bytes)"
    )


if __name__ == "__main__":
    main()
