"""The booklet generator can consume a declared external source tree."""

from __future__ import annotations

import importlib.util
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "gen_booklet.py"


def test_declared_inputs_and_output_work_outside_checkout(tmp_path: Path) -> None:
    algorithms = tmp_path / "inputs" / "algo"
    arrays = algorithms / "arrays"
    arrays.mkdir(parents=True)
    (arrays / "two_sum.py").write_text(
        '"""Two Sum.\n\nProblem:\n    Find a pair.\n"""\n\ndef solve():\n    return 42\n'
    )
    appendix = tmp_path / "appendix.json"
    appendix.write_text("[]")
    output = tmp_path / "generated.tex"

    result = subprocess.run(
        [
            sys.executable,
            str(SCRIPT),
            "--algo-src",
            str(algorithms),
            "--appendix-data",
            str(appendix),
            "--output",
            str(output),
        ],
        cwd=tmp_path,
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0, result.stderr
    rendered = output.read_text()
    assert "Two Sum" in rendered
    assert "return 42" in rendered
    assert "Find a pair" in rendered
    assert "Dijkstra" not in rendered.split(r"\chapter{Arrays", 1)[1]


def test_repeated_source_render_is_identical() -> None:
    spec = importlib.util.spec_from_file_location("gen_booklet", SCRIPT)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    rendered = module.render_booklet()
    assert rendered == module.render_booklet()
    assert r"\end{document}" in rendered
