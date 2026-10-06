"""The compiler bundle is deterministic and rejects changed resource bytes."""

from __future__ import annotations

import hashlib
import json
import subprocess
import sys
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "build_support" / "gen_tex_bundle.py"


def test_bundle_roundtrip_and_tamper_detection(tmp_path: Path) -> None:
    content = b"\\documentclass{report}\n"
    source = tmp_path / "report.cls"
    source.write_bytes(content)
    lock = tmp_path / "lock.json"
    lock.write_text(
        json.dumps(
            {
                "resources": [
                    {
                        "name": source.name,
                        "length": len(content),
                        "sha256": hashlib.sha256(content).hexdigest(),
                    }
                ]
            }
        )
    )
    command = [
        sys.executable,
        str(SCRIPT),
        "--lock",
        str(lock),
        "--input-dir",
        str(tmp_path),
        "--output",
    ]
    first, second = tmp_path / "first.zip", tmp_path / "second.zip"
    subprocess.run([*command, str(first)], check=True)
    subprocess.run([*command, str(second)], check=True)
    assert first.read_bytes() == second.read_bytes()
    with zipfile.ZipFile(first) as bundle:
        assert bundle.read("report.cls") == content
        assert len(bundle.read("SHA256SUM")) == 64
    source.write_bytes(b"changed")
    failure = subprocess.run(
        [*command, str(second)], capture_output=True, text=True, check=False
    )
    assert failure.returncode != 0
    assert "resource differs from lock" in failure.stderr
