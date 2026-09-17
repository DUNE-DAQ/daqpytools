from pathlib import Path

import pytest

from daqpytools.uml import style_pyreverse


def test_run_pyreverse_ignores_existing_dot_files(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    output_dir = tmp_path / "pics"
    output_dir.mkdir()
    existing_dot = output_dir / "directory_color_legend.dot"
    existing_dot.write_text("existing legend", encoding="utf-8")
    raw_dot = output_dir / "packages.dot"
    raw_dot.write_text("old packages", encoding="utf-8")

    class FakeRun:
        def __init__(self, args: list[str]) -> None:
            self.args = args

        def run(self) -> int:
            output_index = self.args.index("--output-directory") + 1
            staging_dir = Path(self.args[output_index])
            (staging_dir / "packages.dot").write_text(
                "new packages", encoding="utf-8"
            )
            return 0

    monkeypatch.setattr(style_pyreverse, "Run", FakeRun)

    dot_files = style_pyreverse.run_pyreverse(["daqpytools"], output_dir)

    assert dot_files == [raw_dot]
    assert raw_dot.read_text(encoding="utf-8") == "new packages"
    assert existing_dot.read_text(encoding="utf-8") == "existing legend"
    assert not list(output_dir.glob(".pyreverse-*"))